"""Reference data (vendor master, POs, receipts, ERP history) from seed/data.json."""

from __future__ import annotations

import datetime as dt
import json
import os
from decimal import Decimal
from pathlib import Path

SEED_DIR = Path(os.environ.get("AIRLOCK_SEED_DIR", Path(__file__).resolve().parents[2] / "seed"))


def load(domain: str, path: Path | None = None) -> dict:
    raw = (path or SEED_DIR / "data.json").read_text(encoding="utf-8").replace("{DOMAIN}", domain)
    return json.loads(raw)


def policy_tables(data: dict):
    """(vendors, purchase_orders_by_number, receipts_by_po, erp_history)"""
    pos = {p["po_number"].upper(): p for p in data["purchase_orders"]}
    receipts = {r["po_number"].upper(): r for r in data["receipts"]}
    return data["vendors"], pos, receipts, data["erp_history"]


def prior_from_history(history: list[dict]):
    from .policy import PriorInvoice

    return [PriorInvoice(vendor_id=h["vendor_id"], invoice_number=h["invoice_number"], total=Decimal(h["total"]),
                         currency=h["currency"], invoice_date=dt.date.fromisoformat(h["invoice_date"]), source="erp_history")
            for h in history]
