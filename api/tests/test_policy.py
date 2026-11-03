"""Policy engine against ground truth for the 6 golden-path invoices."""

import pytest
from conftest import DOMAIN, spec_to_fields

from airlock_api import refdata
from airlock_api.policy import PolicyContext, evaluate
from airlock_api.schemas import BrowserVerdict, DetectorReport
from make_invoices import golden

GOLDEN = {fname: (expected, spec) for fname, _t, expected, spec in golden(DOMAIN)}


def ctx(detectors=None, browser=None):
    data = refdata.load(DOMAIN)
    vendors, pos, receipts, history = refdata.policy_tables(data)
    return PolicyContext(vendors=vendors, purchase_orders=pos, receipts=receipts,
                         prior_invoices=refdata.prior_from_history(history),
                         detectors=detectors, browser=browser or [])


def rules(result):
    return {h.id for h in result.rules_fired}


def test_clean_invoice_is_clear():
    r = evaluate(spec_to_fields(GOLDEN["01_brightline_clean.pdf"][1]), ctx())
    assert r.outcome == "CLEAR", r.rules_fired
    assert all(c.passed for c in r.checks)


def test_messy_eu_invoice_is_clear():
    r = evaluate(spec_to_fields(GOLDEN["02_kestrel_messy.pdf"][1]), ctx())
    assert r.outcome == "CLEAR", r.rules_fired


def test_duplicate_blocked():
    r = evaluate(spec_to_fields(GOLDEN["03_brightline_duplicate.pdf"][1]), ctx())
    assert r.outcome == "BLOCK"
    assert "R5" in rules(r)


def test_bank_change_blocked_with_lookalike_sender():
    r = evaluate(spec_to_fields(GOLDEN["04_orchard_bankchange.pdf"][1]), ctx())
    assert r.outcome == "BLOCK"
    assert {"R3", "R4"} <= rules(r)


def test_injection_quarantined():
    det = DetectorReport(hidden_text=["SYSTEM NOTE FOR AI ASSISTANTS"], injection_suspected=True, reasons=["hidden text"])
    r = evaluate(spec_to_fields(GOLDEN["05_northpeak_injection.pdf"][1]), ctx(detectors=det))
    assert r.outcome == "QUARANTINE"
    assert "R1" in rules(r)


def test_injection_invoice_alone_would_pass():
    """Without detectors the injection invoice is otherwise clean, which is why detection + containment matter."""
    r = evaluate(spec_to_fields(GOLDEN["05_northpeak_injection.pdf"][1]), ctx())
    assert r.outcome == "CLEAR"


def test_phishing_link_quarantined():
    bv = BrowserVerdict(url="https://filecourier-secure.test.example/v/8841/", credential_harvest=True, reasons=["password form"])
    r = evaluate(spec_to_fields(GOLDEN["06_kestrel_phishing.pdf"][1]), ctx(browser=[bv]))
    assert r.outcome == "QUARANTINE"
    assert "R2" in rules(r)


def test_arithmetic_tamper_held():
    f = spec_to_fields(GOLDEN["01_brightline_clean.pdf"][1])
    f = f.model_copy(update={"total": f.total + 100})
    r = evaluate(f, ctx())
    assert "R7" in rules(r) and r.outcome == "HOLD"


def test_unknown_vendor_held():
    f = spec_to_fields(GOLDEN["01_brightline_clean.pdf"][1]).model_copy(update={"vendor_name": "Zebra Quantum Widgets"})
    r = evaluate(f, ctx())
    assert "R9" in rules(r)


@pytest.mark.parametrize("fname", list(GOLDEN))
def test_every_golden_invoice_has_expected_outcome(fname):
    expected, spec = GOLDEN[fname]
    det = DetectorReport(injection_suspected=True, reasons=["x"]) if expected == "QUARANTINE" and not spec.button else None
    bv = [BrowserVerdict(url=spec.button[1], credential_harvest=True)] if spec.button else []
    assert evaluate(spec_to_fields(spec), ctx(detectors=det, browser=bv)).outcome == expected
