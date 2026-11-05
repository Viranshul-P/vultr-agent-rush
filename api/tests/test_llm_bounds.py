"""Reasoning models can burn the whole budget and return no content; that must fall back, not stall."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(ROOT / 'var' / 'llm-test.db').as_posix()}")

from airlock_api import llm  # noqa: E402
from airlock_api.config import settings  # noqa: E402
from airlock_api.db import init_db  # noqa: E402


def _resp(content, finish="stop"):
    return NS(choices=[NS(message=NS(content=content), finish_reason=finish)],
              usage=NS(prompt_tokens=10, completion_tokens=12000 if finish == "length" else 50))


def test_empty_reasoning_output_falls_back_and_sends_bounds(monkeypatch):
    init_db()
    calls = []

    def create(**kw):
        calls.append(kw)
        return _resp("", "length") if kw["model"] != settings.model_fallback else _resp("```python\nprint(1)\n```")

    monkeypatch.setattr(llm, "_openai", lambda: NS(chat=NS(completions=NS(create=create))))
    out = llm._chat("primary-model", [{"role": "user", "content": "x"}], role="coder_extract", invoice_id=None)
    assert "print(1)" in out
    assert [c["model"] for c in calls] == ["primary-model", settings.model_fallback]
    assert all(c["max_tokens"] == settings.llm_coder_max_tokens for c in calls)
    assert all(c["extra_body"] == {"reasoning_effort": settings.llm_coder_reasoning_effort} for c in calls)


def test_non_coder_roles_use_fast_bounds(monkeypatch):
    init_db()
    calls = []
    monkeypatch.setattr(llm, "_openai", lambda: NS(chat=NS(completions=NS(
        create=lambda **kw: calls.append(kw) or _resp('{"ok": true}')))))
    llm._chat("m", [{"role": "user", "content": "x"}], role="classifier", invoice_id=None)
    assert calls[0]["max_tokens"] == settings.llm_max_tokens
    assert calls[0]["extra_body"] == {"reasoning_effort": settings.llm_reasoning_effort}


def test_stuck_call_goes_to_fallback_without_retrying_the_same_model(monkeypatch):
    """A timeout used to be retried on the same model first (2 x timeout before the fallback ran)."""
    init_db()
    calls = []

    def create(**kw):
        calls.append(kw)
        if kw["model"] != settings.model_fallback:
            raise TimeoutError("stuck")
        return _resp('{"score": 0.1}')

    monkeypatch.setattr(settings, "llm_max_retries", 0)
    monkeypatch.setattr(llm, "_openai", lambda: NS(chat=NS(completions=NS(create=create))))
    llm._chat("primary-model", [{"role": "user", "content": "x"}], role="classifier", invoice_id=None)
    assert [c["model"] for c in calls] == ["primary-model", settings.model_fallback]


def test_max_retries_adds_fallback_attempts_then_raises(monkeypatch):
    init_db()
    calls = []

    def create(**kw):
        calls.append(kw["model"])
        raise TimeoutError("stuck")

    monkeypatch.setattr(settings, "llm_max_retries", 1)
    monkeypatch.setattr(llm, "_openai", lambda: NS(chat=NS(completions=NS(create=create))))
    try:
        llm._chat("primary-model", [{"role": "user", "content": "x"}], role="planner", invoice_id=None)
        raise AssertionError("expected the last failure to propagate")
    except TimeoutError:
        pass
    assert calls == ["primary-model", settings.model_fallback, settings.model_fallback]


def test_per_role_timeouts(monkeypatch):
    init_db()
    seen = {}
    monkeypatch.setattr(llm, "_openai", lambda: NS(chat=NS(completions=NS(
        create=lambda **kw: seen.__setitem__(kw["model"], kw["timeout"]) or _resp('{"ok": true}')))))
    for role in ("classifier", "coder_extract", "vision"):
        llm._chat(role, [{"role": "user", "content": "x"}], role=role, invoice_id=None)
    assert seen["classifier"] == settings.llm_fast_timeout_s
    assert seen["coder_extract"] == settings.llm_timeout_s
    assert seen["vision"] == settings.llm_timeout_s  # images take longer; not cut short
