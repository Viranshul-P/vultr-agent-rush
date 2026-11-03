"""DEV-ONLY backend. NOT A SANDBOX.

Runs programs as plain subprocesses on the developer's machine so the full
pipeline can be exercised on a laptop without Docker. It passes no secrets in
the environment, but there is NO process, filesystem or network isolation.
It refuses to start unless RUNNER_ALLOW_UNSAFE_DEV=1, and every result is
labelled tier="DEV-UNSAFE" so it can never be mistaken for the real thing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .common import cap_text, classify_kill, collect_artifacts, now_iso, prepare_run_dir
from .models import BrowseRequest, ExecRequest, RunResult

ROOT = Path(__file__).resolve().parents[2]
CHECKS_PATH = ROOT / "sandbox-images" / "py-sandbox"
HARNESS = ROOT / "sandbox-images" / "browser-sandbox" / "harness.py"


def _rewrite_paths(code: str, mapping: dict[str, Path]) -> str:
    for src, dst in mapping.items():
        code = re.sub(rf"(?<![\w.]){re.escape(src)}(?=[/\"'\s)]|$)", dst.as_posix(), code)
    return code


class SubprocessBackend:
    name = "subprocess-unsafe-dev"
    tier = "DEV-UNSAFE"

    def __init__(self, runs_root: str):
        if os.environ.get("RUNNER_ALLOW_UNSAFE_DEV") != "1":
            raise RuntimeError("SubprocessBackend is not a sandbox. Set RUNNER_ALLOW_UNSAFE_DEV=1 for local dev only.")
        self.runs_root = Path(runs_root).resolve()  # absolute: we chdir into tmp when running
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def health(self) -> dict:
        return {"backend": self.name, "tier": self.tier, "runtime": "none", "runtime_available": False,
                "images": {"py": "local-python", "browser": "local-playwright" if _has_playwright() else "missing"},
                "running_sandboxes": 0, "warning": "DEV ONLY: no isolation"}

    def _isolation(self) -> dict:
        return {"runtime": "none (DEV-UNSAFE subprocess)", "network": "host", "env_vars_passed": 0,
                "read_only_root": False, "user": "developer", "caps": "host", "warning": "not a sandbox"}

    def _env(self, tmp: Path) -> dict:
        env = {"PYTHONPATH": str(CHECKS_PATH), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
               "HOME": str(tmp), "PATH": os.environ.get("PATH", "")}
        if os.name == "nt":  # Windows needs these for Python to start at all
            for k in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
                if k in os.environ:
                    env[k] = os.environ[k]
        return env

    def exec(self, req: ExecRequest) -> RunResult:
        base, in_dir, out_dir = prepare_run_dir(self.runs_root, req.run_id, req.files, req.code)
        tmp = base / "tmp"
        tmp.mkdir()
        code = _rewrite_paths(req.code, {"/input": in_dir, "/out": out_dir, "/tmp": tmp})
        (in_dir / "main.py").write_text(code, encoding="utf-8")
        created = now_iso()
        t0 = time.monotonic()
        timed_out = False
        try:
            p = subprocess.run([sys.executable, str(in_dir / "main.py")], cwd=tmp, env=self._env(tmp),
                               capture_output=True, timeout=req.limits.timeout_s)
            exit_code, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out, exit_code, out, err = True, None, exc.stdout or b"", exc.stderr or b""
        duration = int((time.monotonic() - t0) * 1000)
        stderr = cap_text(err)
        arts, over = collect_artifacts(out_dir, req.limits.out_max_mb * 1_048_576)
        killed = classify_kill(timed_out, False, exit_code, stderr) or ("output_cap" if over else None)
        shutil.rmtree(base, ignore_errors=True)
        return RunResult(run_id=req.run_id, kind=req.kind, container_id=f"dev-{req.run_id[-8:]}", image_digest="local",
                         tier=self.tier, exit_code=exit_code, killed_reason=killed, stdout=cap_text(out), stderr=stderr,
                         artifacts=arts, created_at=created, started_at=created, destroyed_at=now_iso(),
                         duration_ms=duration, isolation=self._isolation(), limits=req.limits.model_dump())

    def browse(self, req: BrowseRequest) -> RunResult:
        base, _in, out_dir = prepare_run_dir(self.runs_root, req.run_id, [], "")
        (out_dir / "quarantine").mkdir()
        created = now_iso()
        t0 = time.monotonic()
        if not _has_playwright():
            stderr, exit_code = "playwright not installed in dev environment", 2
        else:
            p = subprocess.run([sys.executable, str(HARNESS), "--url", req.url, "--run-id", req.run_id,
                                "--timeout", str(req.timeout_s), "--out", str(out_dir)],
                               capture_output=True, timeout=req.timeout_s + 30)
            stderr, exit_code = cap_text(p.stderr), p.returncode
        arts, _ = collect_artifacts(out_dir, 50 * 1_048_576)
        extra = {}
        for a in arts:
            if a.name == "browse.json" and a.b64:
                import base64

                extra = json.loads(base64.b64decode(a.b64))
        extra["proxy_log"] = []
        extra["downloads"] = [{"name": a.name.split("/", 1)[1], "sha256": a.sha256, "size": a.size, "quarantined": True}
                              for a in arts if a.name.startswith("quarantine/")]
        shutil.rmtree(base, ignore_errors=True)
        return RunResult(run_id=req.run_id, kind="browse", container_id=f"dev-{req.run_id[-8:]}", image_digest="local",
                         tier=self.tier, exit_code=exit_code, stderr=stderr, artifacts=arts, created_at=created,
                         started_at=created, destroyed_at=now_iso(), duration_ms=int((time.monotonic() - t0) * 1000),
                         isolation=self._isolation(), limits=req.limits.model_dump(), extra=extra)


def _has_playwright() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False
