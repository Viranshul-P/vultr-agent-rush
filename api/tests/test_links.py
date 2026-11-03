"""A pay-link the sandboxed browser couldn't really inspect must fail safe (R12 HOLD)."""

from conftest import DOMAIN, spec_to_fields

from airlock_api import refdata
from airlock_api.links import unavailable_reason
from airlock_api.policy import PolicyContext, evaluate
from airlock_api.schemas import BrowserVerdict
from make_invoices import golden

URL = "https://filecourier-secure.example.com/v/8841/"


def browse(status=200, error=None, final_url=URL, proxy_log=None, exit_code=0):
    return {"exit_code": exit_code, "extra": {"url": URL, "final_url": final_url, "status": status,
                                              "error": error, "proxy_log": proxy_log or []}}


def test_loaded_page_is_inspectable():
    assert unavailable_reason(browse(), URL) is None


def test_proxy_dns_failure_502_is_unavailable():
    # Exactly what the egress proxy + harness return when the host doesn't resolve:
    # an error page "loads", so the harness reports no error.
    res = browse(status=502, proxy_log=[{"method": "GET", "host": "filecourier-secure.example.com",
                                         "path": "/v/8841/", "decision": "deny",
                                         "reason": "dns failure: [Errno -2] Name or service not known"}])
    why = unavailable_reason(res, URL)
    assert why and "denied" in why


def test_proxy_deny_alone_is_unavailable():
    res = browse(status=None, proxy_log=[{"host": "filecourier-secure.example.com", "decision": "deny",
                                          "reason": "private range"}])
    assert unavailable_reason(res, URL)


def test_deny_for_other_host_does_not_count():
    res = browse(proxy_log=[{"host": "tracker.example.net", "decision": "deny", "reason": "private range"}])
    assert unavailable_reason(res, URL) is None


def test_http_error_status_is_unavailable():
    assert unavailable_reason(browse(status=404), URL) == "page returned HTTP 404"


def test_runner_failure_and_harness_error_still_unavailable():
    assert unavailable_reason(browse(exit_code=2), URL)
    assert unavailable_reason(browse(error="TimeoutError: nav", final_url=None), URL)


def test_unavailable_link_holds_otherwise_clean_invoice():
    spec = {f: s for f, _t, _e, s in golden(DOMAIN)}["06_kestrel_phishing.pdf"]
    data = refdata.load(DOMAIN)
    vendors, pos, receipts, history = refdata.policy_tables(data)
    ctx = PolicyContext(vendors=vendors, purchase_orders=pos, receipts=receipts,
                        prior_invoices=refdata.prior_from_history(history),
                        browser=[BrowserVerdict(url=URL, final_url=URL, source="unavailable",
                                                reasons=["link could not be inspected: page returned HTTP 502"])])
    r = evaluate(spec_to_fields(spec), ctx)
    assert r.outcome == "HOLD", r.rules_fired
    assert "R12" in {h.id for h in r.rules_fired}
