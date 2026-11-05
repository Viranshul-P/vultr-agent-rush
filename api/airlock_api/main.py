"""Airlock control-plane API (FastAPI)."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from . import evidence, runner_client, seed
from .config import settings
from .db import (Approval, DrillResult, ErpPosting, Event, Invoice, LlmUsage, PurchaseOrder,
                 Run, Vendor, init_db, new_id, session, to_dict, utcnow)
from .events import bus
from .schemas import InvoiceFields


def bootstrap():
    init_db()
    try:
        seed.seed_all()
        app.state.seed_error = None
    except Exception as exc:  # non-fatal; health will show it
        app.state.seed_error = str(exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bootstrap()
    yield


app = FastAPI(title="Airlock", version="0.1.0", lifespan=lifespan)
app.state.seed_error = None

_uploads: dict[str, deque] = defaultdict(deque)


# --------------------------------------------------------------- helpers

def _ws(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)) -> str:
    ws = seed.workspace(airlock_ws)
    if ws != airlock_ws:
        resp.set_cookie("airlock_ws", ws, max_age=86400 * 7, httponly=True, samesite="lax")
    return ws


def _inv_or_404(inv_id: str, ws: str) -> Invoice:
    with session() as s:
        inv = s.get(Invoice, inv_id)
    if not inv or inv.workspace_id != ws:
        raise HTTPException(404, "invoice not found")
    return inv


def _public(inv: Invoice) -> dict:
    from .orchestrator import is_inflight
    d = to_dict(inv)
    d.pop("file_key", None)
    # Waiting for a free pipeline worker (several visitors at once): show it, rather than a silent "new".
    d["queued"] = inv.status == "NEW" and is_inflight(inv.id)
    return d


# --------------------------------------------------------------- session + inbox

@app.post("/api/session")
def create_session(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    return {"workspace": _ws(req, resp, airlock_ws)}


@app.post("/api/workspace/reset")
def reset(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    seed.reset_workspace(ws)
    return {"ok": True, "workspace": ws}


@app.get("/api/invoices")
def list_invoices(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    with session() as s:
        rows = s.exec(select(Invoice).where(Invoice.workspace_id == ws).order_by(Invoice.order, Invoice.created_at))
        return {"workspace": ws, "invoices": [_public(i) for i in rows]}


@app.get("/api/invoices/{inv_id}")
def get_invoice(inv_id: str, req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    inv = _inv_or_404(inv_id, ws)
    with session() as s:
        runs = [to_dict(r) for r in s.exec(select(Run).where(Run.invoice_id == inv_id).order_by(Run.created_at))]
        events = [to_dict(e) for e in s.exec(select(Event).where(Event.invoice_id == inv_id).order_by(Event.id))]
        # Per-call timings (no prompts or outputs), so slow invoices can be explained from outside.
        llm_calls = [{"role": u.role, "model": u.model, "latency_ms": u.latency_ms, "ok": u.ok,
                      "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
                      "ts": u.ts.isoformat()}
                     for u in s.exec(select(LlmUsage).where(LlmUsage.invoice_id == inv_id).order_by(LlmUsage.id))]
    return {"invoice": _public(inv), "runs": runs, "events": events, "llm_calls": llm_calls}


@app.post("/api/invoices")
async def upload(req: Request, resp: Response, file: UploadFile, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    ip = req.client.host if req.client else "?"
    now = time.time()
    q = _uploads[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= settings.uploads_per_hour_per_ip:
        raise HTTPException(429, "upload limit reached, try later")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1_048_576:
        raise HTTPException(413, f"file over {settings.max_upload_mb} MB")
    if not data[:5] == b"%PDF-":
        raise HTTPException(415, "only PDF invoices are accepted")
    q.append(now)
    from .storage import store
    sha = hashlib.sha256(data).hexdigest()
    key = f"uploads/{ws}/{sha}.pdf"
    store.put(key, data, "application/pdf")
    with session() as s:
        order = (max([i.order for i in s.exec(select(Invoice).where(Invoice.workspace_id == ws))], default=0)) + 1
        inv = Invoice(workspace_id=ws, order=order, title=file.filename or "uploaded.pdf",
                      filename=file.filename or "uploaded.pdf", file_key=key, sha256=sha, source="upload", status="NEW")
        s.add(inv)
        s.commit()
        s.refresh(inv)
    return _public(inv)


@app.post("/api/invoices/{inv_id}/process")
def process_one(inv_id: str, req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    inv = _inv_or_404(inv_id, ws)
    from .orchestrator import is_inflight, submit
    if inv.status in ("SCANNING", "EXTRACTING", "VALIDATING", "INSPECTING_LINKS", "DECIDING") or is_inflight(inv_id):
        raise HTTPException(409, "already processing")
    submit(inv_id)
    return {"ok": True, "invoice_id": inv_id}


@app.post("/api/inbox/process-all")
def process_all(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    from .orchestrator import submit
    with session() as s:
        ids = [inv.id for inv in s.exec(select(Invoice).where(Invoice.workspace_id == ws, Invoice.status == "NEW")
                                         .order_by(Invoice.order))]
    return {"started": [i for i in ids if submit(i)]}


@app.get("/api/invoices/{inv_id}/events")
async def stream(inv_id: str, req: Request, airlock_ws: str | None = Cookie(default=None)):
    ws = seed.workspace(airlock_ws)
    _inv_or_404(inv_id, ws)

    async def gen():
        import json
        q = bus.subscribe(inv_id)
        try:
            with session() as s:
                for e in s.exec(select(Event).where(Event.invoice_id == inv_id).order_by(Event.id)):
                    yield {"event": e.type, "data": json.dumps(to_dict(e))}
            while True:
                if await req.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield {"event": msg["type"], "data": json.dumps(msg)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(inv_id, q)

    return EventSourceResponse(gen())


# --------------------------------------------------------------- approval + ERP

@app.post("/api/invoices/{inv_id}/decision")
def decide(inv_id: str, body: dict, req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    inv = _inv_or_404(inv_id, ws)
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve or reject")
    if inv.status != "AWAIT_APPROVAL":
        raise HTTPException(409, f"invoice is {inv.status}, not awaiting approval")
    with session() as s:
        s.add(Approval(invoice_id=inv_id, decision=decision, note=str(body.get("note", ""))[:500]))
        inv = s.get(Invoice, inv_id)
        if decision == "approve":
            f = inv.fields or {}
            s.add(ErpPosting(workspace_id=ws, invoice_id=inv_id, vendor_id=(inv.policy or {}).get("vendor_id"),
                             invoice_number=f.get("invoice_number", ""), amount=str(f.get("total", "0")),
                             currency=f.get("currency", "")))
            inv.status = "POSTED"
        else:
            inv.status = "REJECTED"
        inv.updated_at = utcnow()
        s.add(inv)
        s.commit()
    bus.publish(inv_id, "approval.decided", {"decision": decision})
    if decision == "approve":
        f = inv.fields or {}
        bus.publish(inv_id, "erp.posted", {"amount": str(f.get("total", "0")), "currency": f.get("currency", "")})
    from .orchestrator import _finish
    _finish(inv_id, inv.status)
    return {"ok": True, "status": inv.status}


@app.get("/api/erp/postings")
def erp(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    with session() as s:
        rows = s.exec(select(ErpPosting).where(ErpPosting.workspace_id == ws).order_by(ErpPosting.ts.desc()))
        return {"postings": [to_dict(p) for p in rows]}


@app.get("/api/vendors")
def vendors():
    with session() as s:
        return {"vendors": [to_dict(v) for v in s.exec(select(Vendor))]}


# --------------------------------------------------------------- runs + receipts

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with session() as s:
        r = s.get(Run, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return to_dict(r)


@app.get("/api/receipts/{inv_id}")
def receipt(inv_id: str, req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    _inv_or_404(inv_id, ws)
    from .db import Evidence
    with session() as s:
        ev = s.get(Evidence, inv_id)
    if not ev:
        raise HTTPException(404, "no receipt yet")
    from .storage import store
    manifest = store.get(ev.manifest_key).decode()
    return {"manifest": manifest, "signature": ev.signature_b64, "manifest_sha256": ev.manifest_sha256,
            "public_key": evidence.public_key_b64()}


@app.post("/api/receipts/{inv_id}/verify")
def verify_receipt(inv_id: str):
    return evidence.verify(inv_id)


@app.get("/api/receipts/pubkey")
def pubkey():
    return {"public_key": evidence.public_key_b64(), "algorithm": "Ed25519"}


# --------------------------------------------------------------- red team + metrics

@app.get("/api/drills")
def drills():
    try:
        cat = runner_client.drills_catalogue()
    except Exception as exc:
        raise HTTPException(502, f"runner unreachable: {exc}")
    with session() as s:
        last = {d.drill_id: to_dict(d) for d in s.exec(select(DrillResult).order_by(DrillResult.ts))}
    return {**cat, "last_results": last}


@app.post("/api/drills/{drill_id}/run")
def run_drill(drill_id: str):
    try:
        res = runner_client.run_drill(drill_id)
    except Exception as exc:
        raise HTTPException(502, f"runner error: {exc}")
    with session() as s:
        s.add(DrillResult(drill_id=drill_id, passed=res.get("passed"), actual=res.get("actual", ""),
                          tier=res.get("runs", [{}])[0].get("tier", "") if res.get("runs") else "", data=res))
        s.commit()
    return res


@app.post("/api/drills/run-all")
def run_all_drills():
    out = {}
    for d in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10a", "D10b"):
        try:
            out[d] = run_drill(d)
        except HTTPException as exc:
            out[d] = {"error": exc.detail}
    return out


@app.get("/api/metrics")
def metrics(req: Request, resp: Response, airlock_ws: str | None = Cookie(default=None)):
    ws = _ws(req, resp, airlock_ws)
    import json as _json
    from pathlib import Path
    results_dir = Path(settings.seed_dir).parent / "eval" / "results"
    latest = None
    if results_dir.exists():
        files = sorted(results_dir.glob("*.json"))
        if files:
            latest = _json.loads(files[-1].read_text())
    with session() as s:
        # "Live" counters are scoped to the caller's workspace, as the Metrics page says.
        ws_invoices = select(Invoice.id).where(Invoice.workspace_id == ws)
        usage = list(s.exec(select(LlmUsage).where(LlmUsage.invoice_id.in_(ws_invoices))))
        posted = len(list(s.exec(select(ErpPosting).where(ErpPosting.workspace_id == ws))))
    total_cost = round(sum(u.cost_usd for u in usage), 4)
    return {"eval": latest, "live": {"llm_calls": len(usage), "llm_cost_usd": total_cost, "invoices_posted": posted}}


@app.get("/api/health")
def health():
    out = {"ok": True, "mode": settings.mode, "domain": settings.domain, "seed_error": getattr(app.state, "seed_error", None)}
    try:
        out["runner"] = runner_client.health()
    except Exception as exc:
        out["runner"] = {"error": str(exc)[:200]}
        out["ok"] = False
    from .storage import store
    out["storage"] = store.kind
    return JSONResponse(out)
