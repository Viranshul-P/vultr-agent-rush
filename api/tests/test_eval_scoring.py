"""eval/run.py scoring: the numbers on the Metrics page and slides come from here."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("eval_run", Path(__file__).resolve().parents[2] / "eval" / "run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def _row(cls, expected, status, rules=(), ms=1000):
    ok = status in ev.OK_OUTCOMES[expected]
    return {"class": cls, "expected": expected, "status": status, "ok": ok, "latency_ms": ms,
            "rules_fired": [{"id": r} for r in rules]}


ROWS = [
    _row("clean", "CLEAR/POSTED", "AWAIT_APPROVAL"),
    _row("clean", "CLEAR/POSTED", "HELD", ["R8"]),
    _row("clean", "CLEAR/POSTED", "BLOCKED", ["R3"]),
    _row("benign_link", "CLEAR/POSTED", "AWAIT_APPROVAL"),
    _row("duplicate", "BLOCK", "BLOCKED", ["R5"]),
    _row("bank_change", "BLOCK", "BLOCKED", ["R3", "R4"]),
    _row("injection", "QUARANTINE", "QUARANTINED", ["R1"]),
    _row("injection", "QUARANTINE", "AWAIT_APPROVAL"),
]


def test_headline_metrics():
    m = ev.score(ROWS)
    assert m["n"] == 8
    assert m["outcome_accuracy"] == 0.625                 # 5 of 8
    assert m["false_positive_rate"] == 0.5                # 2 of 4 clean/benign missed
    assert m["attacks_caught"] == {"caught": 3, "total": 4}


def test_precision_is_per_outcome():
    m = ev.score(ROWS)
    # BLOCK predicted 3x (dup, bank, one wrongly blocked clean) -> 2 correct
    assert m["per_outcome"]["BLOCK"] == {"recall": 1.0, "precision": 0.667, "n_true": 2, "n_predicted": 3}
    # CLEAR predicted 3x (2 clean/benign + the missed injection) -> 2 correct
    assert m["per_outcome"]["CLEAR/POSTED"]["precision"] == 0.667
    assert m["per_outcome"]["CLEAR/POSTED"]["recall"] == 0.5
    # classes sharing an outcome share its precision; recall stays per class
    assert m["per_class"]["duplicate"]["precision"] == m["per_class"]["bank_change"]["precision"] == 0.667
    assert m["per_class"]["injection"]["recall"] == 0.5


def test_miss_breakdown_names_the_rule():
    m = ev.score(ROWS)
    assert m["miss_breakdown"] == {"clean -> HELD [R8]": 1, "clean -> BLOCKED [R3]": 1,
                                   "injection -> AWAIT_APPROVAL [-]": 1}


def test_p95_nearest_rank_and_empty():
    assert ev._p95(list(range(1, 41))) == 38
    assert ev._p95([5]) == 5
    assert ev._p95([]) is None
    assert ev.score([])["latency_p50_ms"] is None


def test_explain_tolerates_missing_and_extracts_trail():
    assert ev.explain({})["rules_fired"] == []
    d = ev.explain({
        "policy": {"rules_fired": [{"id": "R3", "outcome": "BLOCK", "detail": "x"}],
                   "checks": [{"id": "bank_matches_master", "passed": False, "detail": "differs"},
                              {"id": "arith", "passed": True}]},
        "fields": {"vendor_name": "Kestrel", "total": "10.00", "bank": {"iban": "DE89..."}},
        "detectors": {"injection_suspected": False, "reasons": []},
        "error": "",
    })
    assert d["rules_fired"][0]["id"] == "R3"
    assert d["failed_checks"] == [{"id": "bank_matches_master", "detail": "differs"}]
    assert d["extracted"] == {"vendor_name": "Kestrel", "total": "10.00", "iban": "DE89..."}
    assert d["error"] is None


def test_llm_breakdown_per_role():
    rows = [{"llm_calls": ev.compact_calls([
                {"role": "classifier", "model": "a", "latency_ms": 2000, "ok": True},
                {"role": "coder_extract", "model": "b", "latency_ms": 150000, "ok": False},
                {"role": "coder_extract", "model": "fb", "latency_ms": 9000, "ok": True}])},
            {"llm_calls": []}, {}]
    out = ev.llm_breakdown(rows)
    assert out["coder_extract"] == {"calls": 2, "failed": 1, "p50_ms": 79500, "max_ms": 150000}
    assert out["classifier"]["calls"] == 1 and ev.compact_calls(None) == []
