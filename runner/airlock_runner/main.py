"""Runner HTTP API. Bind to the VPC address only; every call needs the bearer token.

    RUNNER_BACKEND=docker                  production (gVisor containers)
    RUNNER_BACKEND=subprocess-unsafe-dev   laptop dev only, needs RUNNER_ALLOW_UNSAFE_DEV=1
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import drills
from .models import BrowseRequest, ExecRequest, RunResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("airlock.runner")

TOKEN = os.environ.get("RUNNER_TOKEN", "")
if len(TOKEN) < 32:
    raise RuntimeError("RUNNER_TOKEN must be set (>= 32 chars)")


def _make_backend():
    kind = os.environ.get("RUNNER_BACKEND", "docker")
    runs_root = os.environ.get("RUNS_ROOT", "/srv/airlock-runs")
    if kind == "docker":
        from .docker_backend import DockerBackend

        return DockerBackend(
            image_py=os.environ["IMAGE_PY"], image_browser=os.environ.get("IMAGE_BROWSER", "airlock/browser-sandbox:latest"),
            runs_root=runs_root, proxy_log_dir=os.environ.get("PROXY_LOG_DIR", "/srv/airlock-proxy-logs"),
            runtime=os.environ.get("SANDBOX_RUNTIME", "runsc"),
            browser_network=os.environ.get("BROWSER_NETWORK", "sbx-browser"),
            proxy_url=os.environ.get("PROXY_URL", "http://egress-proxy:8080"),
        )
    if kind == "subprocess-unsafe-dev":
        from .subprocess_backend import SubprocessBackend

        log.warning("!!! DEV-UNSAFE subprocess backend: NO ISOLATION. Never use this in production. !!!")
        return SubprocessBackend(runs_root=os.environ.get("RUNS_ROOT", os.path.join(os.getcwd(), "var", "runs")))
    raise RuntimeError(f"unknown RUNNER_BACKEND={kind}")


backend = _make_backend()
exec_slots = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT_EXEC", "4")))
browse_slots = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT_BROWSE", "2")))
app = FastAPI(title="Airlock runner", docs_url=None, redoc_url=None)


def auth(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "unauthorized")


async def _with_slot(sem: asyncio.Semaphore, fn, *args):
    try:
        await asyncio.wait_for(sem.acquire(), timeout=60)
    except asyncio.TimeoutError:
        raise HTTPException(503, "sandbox capacity busy, retry shortly")
    try:
        return await run_in_threadpool(fn, *args)
    finally:
        sem.release()


@app.get("/v1/health", dependencies=[Depends(auth)])
async def health():
    return await run_in_threadpool(backend.health)


@app.post("/v1/exec", response_model=RunResult, dependencies=[Depends(auth)])
async def exec_(req: ExecRequest):
    log.info("exec run_id=%s kind=%s", req.run_id, req.kind)
    return await _with_slot(exec_slots, backend.exec, req)


@app.post("/v1/browse", response_model=RunResult, dependencies=[Depends(auth)])
async def browse(req: BrowseRequest):
    log.info("browse run_id=%s url=%s", req.run_id, req.url)
    return await _with_slot(browse_slots, backend.browse, req)


@app.get("/v1/drills", dependencies=[Depends(auth)])
async def list_drills():
    return {"backend": backend.name, "tier": backend.tier, "drills": drills.catalogue()}


@app.post("/v1/drills/{drill_id}", dependencies=[Depends(auth)])
async def run_drill(drill_id: str):
    try:
        return await _with_slot(exec_slots, drills.run_drill, backend, drill_id)
    except KeyError:
        raise HTTPException(404, "unknown drill")
