"""Seed PDFs must be rebuilt when DOMAIN changes, so pay-links never point at a stale host."""

import json

from airlock_api import seed


def _fake_build(calls):
    def run(cmd, check):
        calls.append(cmd)
        out = cmd[cmd.index("--out") + 1]
        dom = cmd[cmd.index("--domain") + 1]
        from pathlib import Path
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "manifest.json").write_text(json.dumps({"domain": dom, "invoices": []}))
    return run


def test_rebuilds_on_domain_change_only(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(seed, "SEED", tmp_path)
    monkeypatch.setattr(seed.subprocess, "run", _fake_build(calls))
    monkeypatch.setattr(seed.settings, "domain", "a.example")
    seed.ensure_invoices_built()
    seed.ensure_invoices_built()
    assert len(calls) == 1                      # cached for the same domain
    monkeypatch.setattr(seed.settings, "domain", "b.example")
    seed.ensure_invoices_built()
    assert len(calls) == 2                      # rebuilt for the new domain
    assert json.loads((tmp_path / "invoices" / "manifest.json").read_text())["domain"] == "b.example"
