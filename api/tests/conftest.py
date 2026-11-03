import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "api", ROOT / "sandbox-images" / "py-sandbox", ROOT / "seed"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DOMAIN = "test.example"


def spec_to_fields(spec):
    """Ground-truth InvoiceFields for a seed InvoiceSpec (what a perfect extractor returns)."""
    from airlock_api.schemas import InvoiceFields

    return InvoiceFields(
        vendor_name=spec.vendor_name,
        sender_email=spec.sender_email,
        invoice_number=spec.invoice_number,
        invoice_date=dt.date.fromisoformat(spec.invoice_date),
        due_date=dt.date.fromisoformat(spec.due_date),
        po_number=spec.po_number,
        currency=spec.currency,
        lines=[{"description": l.description, "qty": l.qty, "unit_price": l.unit_price, "amount": l.amount} for l in spec.lines],
        subtotal=spec.subtotal, tax=spec.tax, total=spec.total,
        bank={k: v for k, v in spec.bank.items() if k in ("iban", "account_number", "routing", "swift", "account_name")},
        links=[spec.button[1]] if spec.button else [],
    )
