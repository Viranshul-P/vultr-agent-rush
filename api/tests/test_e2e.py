"""End-to-end pipeline: real API + real orchestrator + in-process sandbox + mock LLM.

No Docker and no API key needed. This proves wiring, the state machine, policy
integration, approvals, ERP posting and signed receipts. Real isolation and
real model behaviour are covered by the drills + live eval on the Vultr VMs.
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "api", ROOT / "sandbox-images" / "py-sandbox", ROOT / "seed", ROOT / "runner"):
    sys.path.insert(0, str(p))

os.environ.update(
    DATABASE_URL=f"sqlite:///{(ROOT / 'var' / 'e2e.db').as_posix()}",
    STORAGE_DIR=str(ROOT / "var" / "e2e-storage"),
    RUNNER_URL="inprocess",
    RUNNER_TOKEN="x" * 40,
    RUNNER_ALLOW_UNSAFE_DEV="1",
    RUNS_ROOT=str(ROOT / "var" / "e2e-runs"),
    LLM_MODE="mock",
    DOMAIN="beyonders-airlock.duckdns.org",
)
for f in [ROOT / "var" / "e2e.db"]:
    f.unlink(missing_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from airlock_api.main import app, bootstrap  # noqa: E402

bootstrap()
client = TestClient(app)
TERMINAL = {"POSTED", "BLOCKED", "HELD", "QUARANTINED", "AWAIT_APPROVAL", "ERROR", "REJECTED"}


@pytest.fixture(scope="module")
def inbox():
    client.post("/api/session")
    r = client.get("/api/invoices")
    assert r.status_code == 200
    return {i["filename"]: i for i in r.json()["invoices"]}


def _process(inv_id, timeout=60):
    client.post(f"/api/invoices/{inv_id}/process")
    deadline = time.time() + timeout
    while time.time() < deadline:
        inv = client.get(f"/api/invoices/{inv_id}").json()["invoice"]
        if inv["status"] in TERMINAL:
            return inv
        time.sleep(0.3)
    raise AssertionError(f"timeout; last status {inv['status']}")


def test_inbox_has_six(inbox):
    assert len(inbox) == 6


def test_clean_invoice_reaches_approval_then_posts(inbox):
    inv = _process(inbox["01_brightline_clean.pdf"]["id"])
    assert inv["status"] == "AWAIT_APPROVAL", inv.get("policy")
    assert inv["blast_radius"]["secrets_exposed"] == 0
    r = client.post(f"/api/invoices/{inv['id']}/decision", json={"decision": "approve"})
    assert r.json()["status"] == "POSTED"
    postings = client.get("/api/erp/postings").json()["postings"]
    assert any(p["invoice_id"] == inv["id"] for p in postings)


def test_duplicate_blocked(inbox):
    inv = _process(inbox["03_brightline_duplicate.pdf"]["id"])
    assert inv["status"] == "BLOCKED"
    assert "R5" in {h["id"] for h in inv["policy"]["rules_fired"]}


def test_bank_change_blocked(inbox):
    inv = _process(inbox["04_orchard_bankchange.pdf"]["id"])
    assert inv["status"] == "BLOCKED"
    assert {"R3", "R4"} & {h["id"] for h in inv["policy"]["rules_fired"]}


def test_injection_quarantined(inbox):
    inv = _process(inbox["05_northpeak_injection.pdf"]["id"])
    assert inv["status"] == "QUARANTINED"
    assert inv["detectors"]["injection_suspected"] is True
    assert inv["detectors"]["hidden_text"]


def test_receipt_is_signed_and_verifies(inbox):
    inv = _process(inbox["03_brightline_duplicate.pdf"]["id"])  # already terminal
    v = client.post(f"/api/receipts/{inv['id']}/verify").json()
    assert v["found"] and v["sha256_ok"] and v["signature_ok"]


def test_no_secret_env_in_any_run(inbox):
    """Nothing in the pipeline should ever leak RUNNER_TOKEN etc. into a sandbox run."""
    inv = client.get(f"/api/invoices/{inbox['01_brightline_clean.pdf']['id']}").json()
    for run in inv["runs"]:
        assert run["isolation"].get("env_vars_passed", 0) == 0


def test_health_reports_mock_and_inprocess():
    h = client.get("/api/health").json()
    assert h["mode"] == "mock"
    assert "DEV-UNSAFE" in h["runner"]["tier"]


def test_metrics_live_counters_are_per_workspace(inbox):
    mine = client.get("/api/metrics").json()["live"]
    assert mine["invoices_posted"] >= 1 and mine["llm_calls"] >= 1
    other = TestClient(app)  # fresh cookie jar -> new workspace
    other.post("/api/session")
    theirs = other.get("/api/metrics").json()["live"]
    assert theirs == {"llm_calls": 0, "llm_cost_usd": 0, "invoices_posted": 0}
