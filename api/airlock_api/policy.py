"""Deterministic policy engine. No LLM is involved in any decision here.

Inputs are schema-validated fields plus reference data from our own database.
The sandbox's own check results are NOT trusted: every check is recomputed
here from the extracted fields, so a compromised sandbox run can't talk its
way past the policy.

Outcome precedence: QUARANTINE > BLOCK > HOLD > CLEAR (CLEAR = await human approval).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from airlock_checks import bank as bankmod
from airlock_checks import domains, text

from .schemas import BrowserVerdict, Check, DetectorReport, InvoiceFields, PolicyResult, RuleHit

TOL = Decimal("0.01")
PRICE_TOL = Decimal("0.02")
DUP_NUMBER_SIM = 0.9
DUP_WINDOW_DAYS = 45
LOOKALIKE_BLOCK = 0.8
VENDOR_NAME_SIM = 0.8
LINE_MATCH_SIM = 0.6

_RANK = {"QUARANTINE": 3, "BLOCK": 2, "HOLD": 1, "CLEAR": 0}


@dataclass
class PriorInvoice:
    vendor_id: str
    invoice_number: str
    total: Decimal
    currency: str
    invoice_date: dt.date | None
    source: str  # "erp_history" | "workspace:<invoice_id>"


@dataclass
class PolicyContext:
    vendors: list[dict]
    purchase_orders: dict[str, dict]  # po_number -> po
    receipts: dict[str, dict]  # po_number -> receipt
    prior_invoices: list[PriorInvoice] = field(default_factory=list)
    detectors: DetectorReport | None = None
    browser: list[BrowserVerdict] = field(default_factory=list)


def match_vendor(fields: InvoiceFields, vendors: list[dict]) -> tuple[dict | None, float]:
    best, best_score = None, 0.0
    for v in vendors:
        for name in [v["name"], *v.get("aliases", [])]:
            s = text.fuzzy(fields.vendor_name, name)
            if s > best_score:
                best, best_score = v, s
    return (best, best_score) if best_score >= VENDOR_NAME_SIM else (None, best_score)


def _match_line(desc: str, candidates: list[dict]) -> tuple[dict | None, float]:
    best, score = None, 0.0
    for c in candidates:
        s = text.fuzzy(desc, c["description"])
        if s > score:
            best, score = c, s
    return (best, score) if score >= LINE_MATCH_SIM else (None, score)


def compute_checks(fields: InvoiceFields, ctx: PolicyContext) -> tuple[list[Check], dict | None]:
    vendor, vscore = match_vendor(fields, ctx.vendors)
    checks: list[Check] = []

    # vendor_known
    checks.append(Check(id="vendor_known", passed=vendor is not None,
                        detail=f"matched {vendor['name']} ({vscore:.2f})" if vendor else f"no vendor match (best {vscore:.2f})"))

    # arith
    line_errs = [l.description[:40] for l in fields.lines if abs(l.qty * l.unit_price - l.amount) > TOL]
    sum_lines = sum((l.amount for l in fields.lines), Decimal("0"))
    arith_ok = not line_errs and abs(sum_lines - fields.subtotal) <= TOL and abs(fields.subtotal + fields.tax - fields.total) <= TOL
    checks.append(Check(id="arith", passed=arith_ok,
                        detail=f"lines {sum_lines} + tax {fields.tax} = {sum_lines + fields.tax}, invoice says {fields.total}"
                        + (f"; bad lines: {', '.join(line_errs)}" if line_errs else "")))

    # iban_valid (or ABA for US accounts)
    b = fields.bank
    if b.iban:
        r = bankmod.iban(b.iban)
        checks.append(Check(id="iban_valid", passed=r["valid"], detail=f"IBAN {r['normalized']}: {'valid' if r['valid'] else r['reason']}"))
    elif b.routing:
        ok = bankmod.aba(b.routing)
        checks.append(Check(id="iban_valid", passed=ok, detail=f"ABA {b.routing}: {'valid' if ok else 'checksum failed'}"))
    else:
        checks.append(Check(id="iban_valid", passed=False, detail="no bank account on invoice"))

    # bank_matches_master
    if vendor:
        same = bankmod.same_account(b.model_dump(), vendor.get("bank"))
        on_file = vendor.get("bank", {}).get("iban") or vendor.get("bank", {}).get("account_number")
        shown = b.iban or b.account_number or "none"
        checks.append(Check(id="bank_matches_master", passed=same,
                            detail="matches vendor master" if same else f"invoice account {shown} differs from account on file ({_mask(on_file)})"))
    else:
        checks.append(Check(id="bank_matches_master", passed=False, detail="vendor unknown"))

    # sender_domain
    host = domains.of(fields.sender_email or "")
    if not host:
        checks.append(Check(id="sender_domain", passed=False, detail="no sender address"))
    elif vendor and domains.host_matches(host, vendor.get("email_domains", [])):
        checks.append(Check(id="sender_domain", passed=True, detail=f"{host} is on file"))
    else:
        known = vendor.get("email_domains", []) if vendor else [d for v in ctx.vendors for d in v.get("email_domains", [])]
        score = domains.lookalike(host, known)
        checks.append(Check(id="sender_domain", passed=False,
                            detail=f"{host} imitates {', '.join(known[:2])} (lookalike {score:.2f})" if score >= LOOKALIKE_BLOCK
                            else f"{host} is not on file for this vendor"))

    # duplicate
    dup = None
    if vendor:
        for p in ctx.prior_invoices:
            if p.vendor_id != vendor["id"]:
                continue
            num_sim = text.ratio(fields.invoice_number, p.invoice_number)
            same_amount = p.currency == fields.currency and abs(p.total - fields.total) <= TOL
            recent = p.invoice_date is None or abs((fields.invoice_date - p.invoice_date).days) <= DUP_WINDOW_DAYS
            if num_sim >= DUP_NUMBER_SIM or (same_amount and recent):
                dup = (p, num_sim, same_amount)
                break
    if dup:
        p, num_sim, same_amount = dup
        where = "already paid (ERP history)" if p.source == "erp_history" else "already in this inbox"
        checks.append(Check(id="duplicate", passed=False,
                            detail=f"matches {p.invoice_number} {p.currency} {p.total} {where}; number similarity {num_sim:.2f}"
                            + (", same amount" if same_amount else "")))
    else:
        checks.append(Check(id="duplicate", passed=True, detail="no prior invoice matches"))

    # po_exists + three-way match
    po = ctx.purchase_orders.get((fields.po_number or "").strip().upper())
    if not po:
        checks.append(Check(id="po_exists", passed=False, detail=f"PO {fields.po_number or '(none)'} not found"))
        checks.append(Check(id="three_way_qty", passed=False, detail="no PO to match"))
        checks.append(Check(id="three_way_price", passed=False, detail="no PO to match"))
    else:
        po_ok = vendor is not None and po["vendor_id"] == vendor["id"] and po["currency"] == fields.currency
        checks.append(Check(id="po_exists", passed=po_ok,
                            detail=f"{po['po_number']} ({po['currency']}, {po['status']})" if po_ok
                            else f"{po['po_number']} belongs to another vendor or currency"))
        receipt = ctx.receipts.get(po["po_number"], {"lines": []})
        qty_problems, price_problems = [], []
        for l in fields.lines:
            pl, _ = _match_line(l.description, po["lines"])
            if not pl:
                qty_problems.append(f"'{l.description[:30]}' not on PO")
                continue
            rl, _ = _match_line(l.description, receipt["lines"])
            received = Decimal(rl["qty"]) if rl else Decimal("0")
            if l.qty > received:
                qty_problems.append(f"'{l.description[:30]}' billed {l.qty}, received {received}")
            po_price = Decimal(pl["unit_price"])
            if po_price and abs(l.unit_price - po_price) / po_price > PRICE_TOL:
                price_problems.append(f"'{l.description[:30]}' {l.unit_price} vs PO {po_price}")
        checks.append(Check(id="three_way_qty", passed=not qty_problems,
                            detail="; ".join(qty_problems)[:300] or "billed qty ≤ received qty"))
        checks.append(Check(id="three_way_price", passed=not price_problems,
                            detail="; ".join(price_problems)[:300] or "unit prices within 2% of PO"))
    return checks, vendor


def evaluate(fields: InvoiceFields, ctx: PolicyContext) -> PolicyResult:
    checks, vendor = compute_checks(fields, ctx)
    c = {ch.id: ch for ch in checks}
    hits: list[RuleHit] = []

    det = ctx.detectors
    if det and det.injection_suspected:
        hits.append(RuleHit(id="R1", outcome="QUARANTINE", message="Invoice contains instructions aimed at AI systems.",
                            detail="; ".join(det.reasons)[:300]))
    for bv in ctx.browser:
        if bv.credential_harvest:
            hits.append(RuleHit(id="R2", outcome="QUARANTINE", message="Linked page is a credential-harvesting lookalike.",
                                detail=f"{bv.final_url or bv.url}: {'; '.join(bv.reasons)}"[:300]))
    for bv in ctx.browser:
        if bv.source == "unavailable":
            hits.append(RuleHit(id="R12", outcome="HOLD", message="A payment link could not be safely inspected.",
                                detail=f"{bv.url}: {'; '.join(bv.reasons)}"[:300]))
    if vendor and not c["bank_matches_master"].passed:
        hits.append(RuleHit(id="R3", outcome="BLOCK", message="Bank details changed. Verify by phone using the number on file.",
                            detail=f"{c['bank_matches_master'].detail}; call {vendor.get('phone', 'the vendor')}"[:300]))
    if not c["sender_domain"].passed and "imitates" in c["sender_domain"].detail:
        hits.append(RuleHit(id="R4", outcome="BLOCK", message="Sender domain imitates the vendor.", detail=c["sender_domain"].detail))
    if not c["duplicate"].passed:
        hits.append(RuleHit(id="R5", outcome="BLOCK", message="Likely duplicate invoice.", detail=c["duplicate"].detail))
    if not c["iban_valid"].passed and (fields.bank.iban or fields.bank.routing):
        hits.append(RuleHit(id="R6", outcome="BLOCK", message="Invalid bank account number.", detail=c["iban_valid"].detail))
    if not c["arith"].passed:
        hits.append(RuleHit(id="R7", outcome="HOLD", message="Totals don't add up.", detail=c["arith"].detail))
    if not (c["po_exists"].passed and c["three_way_qty"].passed and c["three_way_price"].passed):
        bad = [ch.detail for ch in (c["po_exists"], c["three_way_qty"], c["three_way_price"]) if not ch.passed]
        hits.append(RuleHit(id="R8", outcome="HOLD", message="3-way match failed.", detail="; ".join(bad)[:300]))
    if not vendor:
        hits.append(RuleHit(id="R9", outcome="HOLD", message="Vendor not in master data.", detail=c["vendor_known"].detail))
    if not c["sender_domain"].passed and "imitates" not in c["sender_domain"].detail:
        hits.append(RuleHit(id="R10", outcome="HOLD", message="Sender address not on file for this vendor.", detail=c["sender_domain"].detail))
    if not c["iban_valid"].passed and not (fields.bank.iban or fields.bank.routing):
        hits.append(RuleHit(id="R11", outcome="HOLD", message="No bank account on the invoice.", detail=c["iban_valid"].detail))

    outcome = max((h.outcome for h in hits), key=lambda o: _RANK[o], default="CLEAR")
    return PolicyResult(outcome=outcome, rules_fired=hits, checks=checks, vendor_id=vendor["id"] if vendor else None)


def _mask(s: str | None) -> str:
    if not s:
        return "none"
    s = str(s).replace(" ", "")
    return f"…{s[-4:]}" if len(s) > 4 else s
