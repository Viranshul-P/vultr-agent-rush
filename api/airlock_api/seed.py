"""Load reference data + golden-path invoices into the DB and per-visitor workspaces."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from sqlmodel import delete, select

from .config import settings
from .db import (ErpHistory, ErpPosting, Event, Invoice, PurchaseOrder, Receipt, Run,
                 SeedInvoice, Vendor, Workspace, new_id, session)
from .refdata import load
from .storage import store

SEED = Path(settings.seed_dir)


def ensure_invoices_built() -> Path:
    inv_dir = SEED / "invoices"
    if not (inv_dir / "manifest.json").exists():
        subprocess.run([sys.executable, str(SEED / "make_invoices.py"), "--domain", settings.domain,
                        "--out", str(inv_dir)], check=True)
    return inv_dir


def load_reference():
    data = load(settings.domain)
    with session() as s:
        for v in data["vendors"]:
            s.merge(Vendor(id=v["id"], name=v["name"], aliases=v.get("aliases", []),
                           email_domains=v.get("email_domains", []), web_hosts=v.get("web_hosts", []),
                           phone=v.get("phone", ""), currency=v.get("currency", "USD"), bank=v.get("bank", {})))
        for p in data["purchase_orders"]:
            s.merge(PurchaseOrder(po_number=p["po_number"], vendor_id=p["vendor_id"], currency=p["currency"],
                                  status=p["status"], lines=p["lines"]))
        for r in data["receipts"]:
            s.merge(Receipt(po_number=r["po_number"], lines=r["lines"]))
        s.exec(delete(ErpHistory))
        for h in data["erp_history"]:
            s.add(ErpHistory(**h))
        s.commit()


def load_seed_invoices():
    import json
    inv_dir = ensure_invoices_built()
    manifest = json.loads((inv_dir / "manifest.json").read_text())
    with session() as s:
        for item in manifest["invoices"]:
            raw = (inv_dir / item["filename"]).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            key = f"seed/{item['filename']}"
            store.put(key, raw, "application/pdf")
            s.merge(SeedInvoice(filename=item["filename"], order=item["order"], title=item["title"],
                                expected=item["expected"], file_key=key, sha256=sha))
        s.commit()


def seed_all():
    load_reference()
    load_seed_invoices()


def workspace(ws_id: str | None) -> str:
    """Return an existing workspace or create one seeded with the golden-path invoices."""
    with session() as s:
        if ws_id and s.get(Workspace, ws_id):
            return ws_id
        ws_id = new_id("ws")
        s.add(Workspace(id=ws_id))
        seeds = list(s.exec(select(SeedInvoice).order_by(SeedInvoice.order)))
        for sd in seeds:
            s.add(Invoice(workspace_id=ws_id, order=sd.order, title=sd.title, filename=sd.filename,
                          file_key=sd.file_key, sha256=sd.sha256, source="seed",
                          expected=sd.expected, status="NEW"))
        s.commit()
    return ws_id


def reset_workspace(ws_id: str):
    with session() as s:
        invs = list(s.exec(select(Invoice).where(Invoice.workspace_id == ws_id)))
        ids = [i.id for i in invs]
        for i in invs:
            s.delete(i)
        for i in ids:
            for ev in s.exec(select(Event).where(Event.invoice_id == i)):
                s.delete(ev)
            for r in s.exec(select(Run).where(Run.invoice_id == i)):
                s.delete(r)
        for p in s.exec(select(ErpPosting).where(ErpPosting.workspace_id == ws_id)):
            s.delete(p)
        s.commit()
    # recreate from seed
    with session() as s:
        for sd in s.exec(select(SeedInvoice).order_by(SeedInvoice.order)):
            s.add(Invoice(workspace_id=ws_id, order=sd.order, title=sd.title, filename=sd.filename,
                          file_key=sd.file_key, sha256=sd.sha256, source="seed", expected=sd.expected, status="NEW"))
        s.commit()
