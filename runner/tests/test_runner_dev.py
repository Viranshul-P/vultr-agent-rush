"""Runner API tests against the DEV-UNSAFE subprocess backend (no Docker needed).

These test the API contract, limits plumbing and result shape. Real isolation
is tested by the drills on the gVisor VM (see docs/04-build-guide.md, Part 7).
"""

import base64
import os
import sys
from pathlib import Path

import pytest

TOKEN = "t" * 40
os.environ.update(RUNNER_TOKEN=TOKEN, RUNNER_BACKEND="subprocess-unsafe-dev", RUNNER_ALLOW_UNSAFE_DEV="1",
                  RUNS_ROOT=str(Path(__file__).resolve().parents[1] / "var" / "test-runs"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from airlock_runner.main import app  # noqa: E402

client = TestClient(app)
H = {"Authorization": f"Bearer {TOKEN}"}


def run(code, **kw):
    body = {"run_id": f"test-{os.urandom(4).hex()}", "code": code, **kw}
    r = client.post("/v1/exec", json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_required():
    assert client.post("/v1/exec", json={"run_id": "abcdef", "code": "print(1)"}).status_code == 401
    assert client.get("/v1/health", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_exec_stdout_and_artifacts():
    r = run("import json\nprint('hi')\njson.dump({'a': 1}, open('/out/result.json', 'w'))\n")
    assert r["exit_code"] == 0 and r["stdout"].strip() == "hi"
    assert [a["name"] for a in r["artifacts"]] == ["result.json"]
    assert base64.b64decode(r["artifacts"][0]["b64"]) == b'{"a": 1}'
    assert r["tier"] == "DEV-UNSAFE" and r["destroyed_at"]


def test_input_files_visible():
    data = base64.b64encode(b"hello file").decode()
    r = run("print(open('/input/x.txt').read())", files=[{"name": "x.txt", "b64": data}])
    assert r["stdout"].strip() == "hello file"


def test_no_secrets_in_env():
    os.environ["SUPER_SECRET_API_KEY"] = "leak-me"
    r = run("import os, json; print(json.dumps(sorted(os.environ)))")
    assert "SUPER_SECRET_API_KEY" not in r["stdout"] and "RUNNER_TOKEN" not in r["stdout"]


def test_nonzero_exit_and_stderr():
    r = run("raise ValueError('boom')")
    assert r["exit_code"] == 1 and "ValueError: boom" in r["stderr"]


def test_timeout_kill():
    r = run("while True: pass", limits={"timeout_s": 2})
    assert r["killed_reason"] == "timeout"


def test_bad_inputs_rejected():
    assert client.post("/v1/exec", json={"run_id": "../../etc", "code": "x"}, headers=H).status_code == 422
    bad_file = {"run_id": "abcdef12", "code": "x", "files": [{"name": "../evil", "b64": ""}]}
    assert client.post("/v1/exec", json=bad_file, headers=H).status_code == 422


@pytest.mark.parametrize("drill", ["D3", "D8", "D9"])
def test_dev_safe_drills_pass(drill):
    r = client.post(f"/v1/drills/{drill}", headers=H).json()
    assert r["passed"] is True, r


def test_isolation_drills_skipped_on_dev():
    r = client.post("/v1/drills/D7", headers=H).json()
    assert r["passed"] is None and "skipped" in r["actual"]
