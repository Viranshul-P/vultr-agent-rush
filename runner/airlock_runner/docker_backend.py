"""Production backend: one hardened, gVisor-isolated container per run.

Every run gets: runsc runtime, no network (code) or an internal-only network
behind the egress proxy (browser), read-only root, all capabilities dropped,
no-new-privileges, non-root user, memory/CPU/pids caps, a wall-clock kill,
zero environment variables passed, and removal right after collection.

NOTE: bind-mount paths are HOST paths. When the runner itself runs in a
container, mount RUNS_ROOT and PROXY_LOG_DIR at the same path on host and in
the runner container (see deploy/docker-compose.sandbox.yml).
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from pathlib import Path

import docker
from docker.types import Ulimit
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import ReadTimeout

from .common import cap_text, classify_kill, collect_artifacts, now_iso, prepare_run_dir
from .models import BrowseRequest, ExecRequest, RunResult

log = logging.getLogger("airlock.runner.docker")


class DockerBackend:
    name = "docker"

    def __init__(self, *, image_py: str, image_browser: str, runs_root: str, proxy_log_dir: str,
                 runtime: str = "runsc", browser_network: str = "sbx-browser",
                 proxy_url: str = "http://egress-proxy:8080"):
        self.client = docker.from_env()
        self.image_py, self.image_browser = image_py, image_browser
        self.runs_root, self.proxy_log_dir = Path(runs_root), Path(proxy_log_dir)
        self.runtime, self.browser_network, self.proxy_url = runtime, browser_network, proxy_url
        self.tier = "T1-gvisor" if runtime == "runsc" else f"T1-{runtime}"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.proxy_log_dir.mkdir(parents=True, exist_ok=True)
        self._stop = threading.Event()
        threading.Thread(target=self._sweeper, daemon=True, name="orphan-sweeper").start()

    # ---------------------------------------------------------------- health
    def health(self) -> dict:
        info = self.client.info()
        running = self.client.containers.list(filters={"label": "airlock=sbx"})
        return {
            "backend": self.name, "tier": self.tier, "runtime": self.runtime,
            "runtime_available": self.runtime in (info.get("Runtimes") or {}),
            "images": {"py": self._digest(self.image_py), "browser": self._digest(self.image_browser)},
            "running_sandboxes": len(running),
        }

    def _digest(self, image: str) -> str:
        try:
            img = self.client.images.get(image)
            return (img.attrs.get("RepoDigests") or [img.id])[0]
        except docker.errors.ImageNotFound:
            return "missing"

    # ---------------------------------------------------------------- common
    def _isolation(self, network: str, user: str) -> dict:
        return {"runtime": self.runtime, "network": network, "env_vars_passed": 0, "read_only_root": True,
                "user": user, "caps": [], "no_new_privileges": True, "seccomp": "gVisor + docker default",
                "host": "dedicated sandbox VM (no secrets)", "docker_socket": "not mounted"}

    def _host_pids_cap(self, guest_pids: int) -> int:
        if self.runtime == "runsc":
            return max(512, guest_pids * 8)
        return guest_pids

    def _hardening(self, limits, run_id: str, kind: str) -> dict:
        return dict(
            runtime=self.runtime,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            mem_limit=f"{limits.memory_mb}m",
            memswap_limit=f"{limits.memory_mb}m",
            nano_cpus=int(limits.cpus * 1e9),
            # The process cap is enforced INSIDE the sandbox with RLIMIT_NPROC (gVisor's Sentry
            # returns EAGAIN, just like Linux). Under runsc/systrap the host pids cgroup also counts
            # gVisor's own helper threads, so a host cap equal to the guest cap makes the Sentry
            # panic after ~20 guest forks. Keep the host cgroup as a backstop with headroom.
            pids_limit=self._host_pids_cap(limits.pids),
            ulimits=[Ulimit(name="fsize", soft=50_000_000, hard=50_000_000),
                     Ulimit(name="nofile", soft=256, hard=256),
                     Ulimit(name="nproc", soft=limits.pids, hard=limits.pids)],
            environment={},
            labels={"airlock": "sbx", "airlock.run_id": run_id, "airlock.kind": kind},
            name=f"sbx-{run_id}",
            hostname="sandbox",
            detach=True,
        )

    def _run_container(self, create_kwargs: dict, limits, base: Path, out_dir: Path, run_id: str, kind: str,
                       image: str, isolation: dict) -> RunResult:
        created_at = now_iso()
        container = self.client.containers.create(**create_kwargs)
        peak = {"mb": None}
        done = threading.Event()

        def sample():
            while not done.is_set():
                try:
                    s = container.stats(stream=False)
                    ms = s.get("memory_stats") or {}
                    mb = (ms.get("max_usage") or ms.get("usage") or 0) / 1_048_576
                    if mb and (peak["mb"] is None or mb > peak["mb"]):
                        peak["mb"] = round(mb, 1)
                except Exception:  # stats are best-effort under gVisor
                    pass
                done.wait(0.5)

        timed_out = False
        started_at = now_iso()
        t0 = time.monotonic()
        try:
            container.start()
            threading.Thread(target=sample, daemon=True).start()
            try:
                container.wait(timeout=limits.timeout_s)
            except (ReadTimeout, ReqConnectionError):
                timed_out = True
                try:
                    container.kill()
                except docker.errors.APIError:
                    pass
                container.wait(timeout=10)
            duration_ms = int((time.monotonic() - t0) * 1000)
            done.set()
            container.reload()
            state = container.attrs.get("State", {})
            exit_code = state.get("ExitCode")
            stdout = cap_text(container.logs(stdout=True, stderr=False))
            stderr = cap_text(container.logs(stdout=False, stderr=True))
            artifacts, over = collect_artifacts(out_dir, limits.out_max_mb * 1_048_576)
            killed = classify_kill(timed_out, bool(state.get("OOMKilled")), exit_code, stderr)
            if over and not killed:
                killed = "output_cap"
            return RunResult(run_id=run_id, kind=kind, container_id=container.id[:12], image_digest=self._digest(image),
                             tier=self.tier, exit_code=exit_code, killed_reason=killed, stdout=stdout, stderr=stderr,
                             artifacts=artifacts, created_at=created_at, started_at=started_at,
                             duration_ms=duration_ms, peak_mem_mb=peak["mb"], isolation=isolation,
                             limits=limits.model_dump())
        finally:
            done.set()
            try:
                container.remove(force=True)
            except docker.errors.APIError as exc:
                log.warning("remove failed for %s: %s", run_id, exc)
            shutil.rmtree(base, ignore_errors=True)

    # ---------------------------------------------------------------- exec
    def exec(self, req: ExecRequest) -> RunResult:
        base, in_dir, out_dir = prepare_run_dir(self.runs_root, req.run_id, req.files, req.code)
        user = "65534:65534"
        kwargs = dict(
            image=self.image_py,
            command=["python", "/input/main.py"],
            network_mode="none",
            tmpfs={"/tmp": "rw,size=64m,mode=1777"},
            user=user,
            working_dir="/tmp",
            volumes={str(in_dir): {"bind": "/input", "mode": "ro"}, str(out_dir): {"bind": "/out", "mode": "rw"}},
            **self._hardening(req.limits, req.run_id, req.kind),
        )
        res = self._run_container(kwargs, req.limits, base, out_dir, req.run_id, req.kind, self.image_py,
                                  self._isolation("none", user))
        res.destroyed_at = now_iso()
        return res

    # ---------------------------------------------------------------- browse
    def browse(self, req: BrowseRequest) -> RunResult:
        base, in_dir, out_dir = prepare_run_dir(self.runs_root, req.run_id, [], "# browse run\n")
        (out_dir / "quarantine").mkdir()
        (out_dir / "quarantine").chmod(0o777)
        proxy_log = self.proxy_log_dir / f"{req.run_id}.jsonl"
        limits = req.limits
        limits.timeout_s = max(limits.timeout_s, req.timeout_s + 15)
        kwargs = dict(
            image=self.image_browser,
            command=["python", "/opt/harness.py", "--url", req.url, "--run-id", req.run_id,
                     "--timeout", str(req.timeout_s), "--proxy", self.proxy_url, "--out", "/out"],
            network=self.browser_network,  # internal network: the only way out is the egress proxy
            tmpfs={"/tmp": "rw,size=256m,mode=1777"},
            shm_size="256m",
            working_dir="/tmp",
            volumes={str(out_dir): {"bind": "/out", "mode": "rw"}},
            **self._hardening(limits, req.run_id, "browse"),
        )
        res = self._run_container(kwargs, limits, base, out_dir, req.run_id, "browse", self.image_browser,
                                  self._isolation(f"{self.browser_network} (internal) → egress proxy", "pwuser"))
        res.destroyed_at = now_iso()
        res.extra = _browse_extra(res, proxy_log)
        return res

    # ---------------------------------------------------------------- sweeper
    def _sweeper(self):
        while not self._stop.wait(30):
            try:
                for c in self.client.containers.list(all=True, filters={"label": "airlock=sbx"}):
                    created = c.attrs.get("Created", "")
                    age = time.time() - _parse_docker_ts(created)
                    if age > 120:
                        log.warning("sweeping orphan sandbox %s (age %.0fs)", c.name, age)
                        c.remove(force=True)
                for d in self.runs_root.iterdir():
                    if d.is_dir() and time.time() - d.stat().st_mtime > 600:
                        shutil.rmtree(d, ignore_errors=True)
            except Exception as exc:
                log.warning("sweeper error: %s", exc)


def _parse_docker_ts(s: str) -> float:
    import datetime as dt

    try:
        s = s.split(".")[0].rstrip("Z")
        return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return time.time()


def _browse_extra(res: RunResult, proxy_log: Path) -> dict:
    """Pull browse.json out of the artifacts and attach the proxy log."""
    extra: dict = {}
    for a in list(res.artifacts):
        if a.name == "browse.json" and a.b64:
            import base64

            try:
                extra = json.loads(base64.b64decode(a.b64))
            except ValueError:
                extra = {"error": "unreadable browse.json"}
    entries = []
    if proxy_log.exists():
        for line in proxy_log.read_text(encoding="utf-8", errors="replace").splitlines()[:500]:
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
        proxy_log.unlink(missing_ok=True)
    extra["proxy_log"] = entries
    extra["downloads"] = [{"name": a.name.split("/", 1)[1], "sha256": a.sha256, "size": a.size, "quarantined": True}
                          for a in res.artifacts if a.name.startswith("quarantine/")]
    return extra
