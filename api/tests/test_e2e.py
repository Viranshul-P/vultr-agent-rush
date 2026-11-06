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


def test_process_all_runs_in_parallel_and_never_double_queues():
    """A second 'Process inbox' click while the first batch runs must not queue anything twice."""
    from airlock_api import orchestrator
    client.post("/api/workspace/reset")
    first = client.post("/api/inbox/process-all").json()["started"]
    second = client.post("/api/inbox/process-all").json()["started"]
    assert len(first) == 6 and not set(first) & set(second)
    deadline = time.time() + 120
    while time.time() < deadline and any(orchestrator.is_inflight(i) for i in first):
        time.sleep(0.3)
    statuses = {client.get(f"/api/invoices/{i}").json()["invoice"]["status"] for i in first}
    assert statuses <= TERMINAL, statuses


def test_run_screenshot_serves_only_listed_pngs():
    from airlock_api.db import Run, session
    from airlock_api.storage import store
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    store.put("runs/t/shot.png", png, "image/png")
    store.put("runs/t/payload.bin", b"MZ evil", "application/octet-stream")
    client.post("/api/session")
    inv_id = client.get("/api/invoices").json()["invoices"][0]["id"]
    with session() as s:
        s.add(Run(id="run-shot-test", invoice_id=inv_id, kind="browse", attempt=1, tier="test", container_id="c", image_digest="d",
                  artifacts=[{"name": "shot.png", "key": "runs/t/shot.png"}, {"name": "payload.bin", "key": "runs/t/payload.bin"}]))
        s.commit()
    r = client.get("/api/runs/run-shot-test/screenshots/shot.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == png
    assert client.get("/api/runs/run-shot-test/screenshots/payload.bin").status_code == 404
    assert client.get("/api/runs/run-shot-test/screenshots/other.png").status_code == 404
    assert client.get("/api/runs/nope/screenshots/shot.png").status_code == 404
    # another visitor can't read this workspace's runs, screenshots or receipts
    other = TestClient(app)
    other.post("/api/session")
    assert other.get("/api/runs/run-shot-test").status_code == 404
    assert other.get("/api/runs/run-shot-test/screenshots/shot.png").status_code == 404
    assert other.post(f"/api/receipts/{inv_id}/verify").status_code == 404
    assert client.get("/api/runs/run-shot-test").status_code == 200


def test_receipt_pubkey_route_is_reachable():
    r = client.get("/api/receipts/pubkey")
    assert r.status_code == 200 and r.json()["algorithm"] == "Ed25519"



def test_a_decided_invoice_cannot_be_reprocessed_or_paid_twice(inbox):
    """Re-running a POSTED invoice used to reset it to AWAIT_APPROVAL, so it could be approved and posted again."""
    client.post("/api/workspace/reset")
    inv = next(i for i in client.get("/api/invoices").json()["invoices"] if i["filename"] == "01_brightline_clean.pdf")
    client.post(f"/api/invoices/{inv['id']}/process")
    for _ in range(120):
        st = client.get(f"/api/invoices/{inv['id']}").json()["invoice"]["status"]
        if st == "AWAIT_APPROVAL":
            break
        time.sleep(0.25)
    assert client.post(f"/api/invoices/{inv['id']}/decision", json={"decision": "approve"}).status_code == 200
    r = client.post(f"/api/invoices/{inv['id']}/process")
    assert r.status_code == 409 and "POSTED" in r.json()["detail"]
    assert client.get(f"/api/invoices/{inv['id']}").json()["invoice"]["status"] == "POSTED"
    mine = [p for p in client.get("/api/erp/postings").json()["postings"] if p["invoice_id"] == inv["id"]]
    assert len(mine) == 1


def test_approval_refused_when_a_posting_already_exists():
    from airlock_api.db import ErpPosting, Invoice, session
    client.post("/api/workspace/reset")
    inv_id = client.get("/api/invoices").json()["invoices"][0]["id"]
    with session() as s:
        inv = s.get(Invoice, inv_id)
        inv.status = "AWAIT_APPROVAL"
        s.add(inv)
        s.add(ErpPosting(workspace_id=inv.workspace_id, invoice_id=inv_id, vendor_id="V", invoice_number="X", amount="1", currency="USD"))
        s.commit()
    r = client.post(f"/api/invoices/{inv_id}/decision", json={"decision": "approve"})
    assert r.status_code == 409 and "already been posted" in r.json()["detail"]
