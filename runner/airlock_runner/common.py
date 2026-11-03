from __future__ import annotations

import base64
import datetime as dt
import hashlib
import os
import shutil
from pathlib import Path

from .models import Artifact, InFile

OUT_TEXT_CAP = 256 * 1024


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def cap_text(b: bytes | str, limit: int = OUT_TEXT_CAP) -> str:
    if isinstance(b, bytes):
        b = b.decode("utf-8", errors="replace")
    return b if len(b) <= limit else b[:limit] + f"\n…[truncated {len(b) - limit} chars]"


def prepare_run_dir(root: Path, run_id: str, files: list[InFile], code: str) -> tuple[Path, Path, Path]:
    base = root / run_id
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    in_dir, out_dir = base / "in", base / "out"
    in_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)
    for f in files:
        (in_dir / f.name).write_bytes(base64.b64decode(f.b64))
    (in_dir / "main.py").write_text(code, encoding="utf-8")
    # Sandboxes run as uid 65534: inputs readable, output dir writable, nothing else.
    for p in in_dir.iterdir():
        os.chmod(p, 0o644)
    os.chmod(in_dir, 0o755)
    os.chmod(out_dir, 0o777)
    return base, in_dir, out_dir


def collect_artifacts(out_dir: Path, max_bytes: int) -> tuple[list[Artifact], bool]:
    """Return (artifacts, over_cap). Files under quarantine/ are hashed but never returned."""
    arts, total, over = [], 0, False
    for p in sorted(out_dir.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        data = p.read_bytes()
        rel = p.relative_to(out_dir).as_posix()
        quarantined = rel.startswith("quarantine/")
        total += len(data)
        if total > max_bytes:
            over = True
            break
        arts.append(Artifact(name=rel, sha256=hashlib.sha256(data).hexdigest(), size=len(data),
                             b64=None if quarantined else base64.b64encode(data).decode()))
    return arts, over


def classify_kill(timed_out: bool, oom: bool, exit_code: int | None, stderr: str) -> str | None:
    if timed_out:
        return "timeout"
    if oom:
        return "oom"
    if ("fork" in stderr or "Thread" in stderr) and ("Resource temporarily unavailable" in stderr or "BlockingIOError" in stderr):
        return "pids"
    if exit_code == 137:
        return "oom"
    if "MemoryError" in stderr:
        return "oom"
    return None
