"""Signed evidence receipts (Ed25519). One tamper-evident manifest per invoice."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import settings
from .db import Evidence, Run, session, utcnow
from .storage import store

_priv: Ed25519PrivateKey | None = None


def _key() -> Ed25519PrivateKey:
    global _priv
    if _priv is None:
        if settings.signing_key_b64:
            _priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(settings.signing_key_b64))
        else:  # ephemeral dev key (stable within a process)
            _priv = Ed25519PrivateKey.generate()
    return _priv


def public_key_b64() -> str:
    return base64.b64encode(_key().public_key().public_bytes_raw()).decode()


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def build_manifest(inv, runs: list[Run], usage: list[dict]) -> dict:
    return {
        "version": 1,
        "workspace": inv.workspace_id,
        "invoice": {"id": inv.id, "sha256": inv.sha256, "filename": inv.filename},
        "runs": [{
            "run_id": r.id, "kind": r.kind, "attempt": r.attempt, "tier": r.tier,
            "image_digest": r.image_digest, "container_id": r.container_id,
            "code_sha256": hashlib.sha256((r.code or "").encode()).hexdigest() if r.code else None,
            "limits": r.limits, "isolation": r.isolation, "exit_code": r.exit_code,
            "killed_reason": r.killed_reason, "static_flags": r.static_flags,
            "artifacts": [{"name": a["name"], "sha256": a["sha256"]} for a in (r.artifacts or [])],
            "created_at": r.created_at, "destroyed_at": r.destroyed_at,
        } for r in runs],
        "llm_calls": usage,
        "detectors": inv.detectors, "checks": inv.sandbox_checks, "browser": inv.browser,
        "policy": inv.policy, "summary": inv.summary, "blast_radius": inv.blast_radius,
        "status": inv.status, "sealed_at": utcnow().isoformat(),
    }


def seal(inv) -> Evidence:
    with session() as s:
        runs = _runs(s, inv.id)
        usage = _usage(s, inv.id)
    manifest = build_manifest(inv, runs, usage)
    blob = canonical(manifest)
    sha = hashlib.sha256(blob).hexdigest()
    sig = base64.b64encode(_key().sign(blob)).decode()
    key = f"evidence/{inv.workspace_id}/{inv.id}.json"
    store.put(key, blob, "application/json")
    store.put(key + ".sig", sig.encode(), "text/plain")
    ev = Evidence(invoice_id=inv.id, manifest_key=key, manifest_sha256=sha, signature_b64=sig, sealed_at=utcnow())
    with session() as s:
        s.merge(ev)
        s.commit()
    return ev


def verify(invoice_id: str) -> dict:
    from sqlmodel import select

    with session() as s:
        ev = s.get(Evidence, invoice_id)
        if not ev:
            return {"found": False}
    blob = store.get(ev.manifest_key)
    ok_sha = hashlib.sha256(blob).hexdigest() == ev.manifest_sha256
    try:
        Ed25519PublicKey.from_public_bytes(_key().public_key().public_bytes_raw()).verify(
            base64.b64decode(ev.signature_b64), blob)
        ok_sig = True
    except Exception:
        ok_sig = False
    return {"found": True, "sha256_ok": ok_sha, "signature_ok": ok_sig,
            "manifest_sha256": ev.manifest_sha256, "public_key": public_key_b64()}


def _runs(s, invoice_id):
    from sqlmodel import select

    return list(s.exec(select(Run).where(Run.invoice_id == invoice_id).order_by(Run.created_at)))


def _usage(s, invoice_id):
    from sqlmodel import select

    from .db import LlmUsage
    rows = s.exec(select(LlmUsage).where(LlmUsage.invoice_id == invoice_id))
    return [{"role": u.role, "model": u.model, "prompt_tokens": u.prompt_tokens,
             "completion_tokens": u.completion_tokens, "cost_usd": u.cost_usd} for u in rows]
