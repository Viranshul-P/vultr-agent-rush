"""HTTP client for the sandbox runner (on the sandbox VM, reached over VPC)."""

from __future__ import annotations

import base64

import httpx

from .config import settings


class RunnerError(RuntimeError):
    pass


# In-process backend for local dev/tests: RUNNER_URL="inprocess". Uses the DEV-UNSAFE
# subprocess backend directly (no HTTP, no Docker). Never selected in production,
# where RUNNER_URL points at the sandbox VM over VPC.
_inproc = None


def _inprocess():
    global _inproc
    if _inproc is None:
        import os
        os.environ.setdefault("RUNNER_ALLOW_UNSAFE_DEV", "1")
        from airlock_runner.subprocess_backend import SubprocessBackend  # type: ignore
        _inproc = SubprocessBackend(runs_root=os.environ.get("RUNS_ROOT", "var/runs"))
    return _inproc


def _is_inprocess() -> bool:
    return settings.runner_url == "inprocess"


def _headers():
    return {"Authorization": f"Bearer {settings.runner_token}"}


def _post(path: str, body: dict, timeout: float) -> dict:
    try:
        r = httpx.post(f"{settings.runner_url}{path}", json=body, headers=_headers(), timeout=timeout)
    except httpx.HTTPError as exc:
        raise RunnerError(f"runner unreachable: {exc}") from exc
    if r.status_code != 200:
        raise RunnerError(f"runner {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def exec_code(run_id: str, code: str, *, kind: str = "extract", files: list[tuple[str, bytes]] | None = None,
              limits: dict | None = None) -> dict:
    body = {"run_id": run_id, "kind": kind, "code": code,
            "files": [{"name": n, "b64": base64.b64encode(b).decode()} for n, b in (files or [])],
            "limits": limits or {}}
    if _is_inprocess():
        from airlock_runner.models import ExecRequest  # type: ignore
        return _inprocess().exec(ExecRequest(**body)).model_dump()
    return _post("/v1/exec", body, timeout=(limits or {}).get("timeout_s", 30) + 30)


def browse(run_id: str, url: str, *, timeout_s: int = 45) -> dict:
    if _is_inprocess():
        from airlock_runner.models import BrowseRequest  # type: ignore
        return _inprocess().browse(BrowseRequest(run_id=run_id, url=url, timeout_s=timeout_s)).model_dump()
    return _post("/v1/browse", {"run_id": run_id, "url": url, "timeout_s": timeout_s}, timeout=timeout_s + 40)


def drills_catalogue() -> dict:
    if _is_inprocess():
        from airlock_runner import drills  # type: ignore
        b = _inprocess()
        return {"backend": b.name, "tier": b.tier, "drills": drills.catalogue()}
    return get("/v1/drills")


def run_drill(drill_id: str) -> dict:
    if _is_inprocess():
        from airlock_runner import drills  # type: ignore
        return drills.run_drill(_inprocess(), drill_id)
    return post(f"/v1/drills/{drill_id}")


def get(path: str, timeout: float = 10) -> dict:
    r = httpx.get(f"{settings.runner_url}{path}", headers=_headers(), timeout=timeout)
    r.raise_for_status()
    return r.json()


def post(path: str, timeout: float = 120) -> dict:
    r = httpx.post(f"{settings.runner_url}{path}", headers=_headers(), timeout=timeout)
    r.raise_for_status()
    return r.json()


def health() -> dict:
    if _is_inprocess():
        return _inprocess().health()
    r = httpx.get(f"{settings.runner_url}/v1/health", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def artifact_bytes(run_result: dict, name: str) -> bytes | None:
    for a in run_result.get("artifacts", []):
        if a["name"] == name and a.get("b64"):
            return base64.b64decode(a["b64"])
    return None
