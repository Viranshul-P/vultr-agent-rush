"""LLM client. EVERY agent model call goes through Vultr Serverless Inference.

Two clients enforce the dual-LLM split in code:
  - quarantined(): the only function allowed to receive untrusted document text.
    It takes NO tools and returns raw text (a code block or JSON). A successful
    prompt-injection therefore has nothing to call.
  - privileged(): accepts only already-structured, schema-validated data. It
    rejects raw strings so untrusted text can never reach it by accident.

A keyless "mock" mode returns benign canned structures so the whole pipeline
runs on a laptop with no API key. Mock is never used when an API key is set.
"""

from __future__ import annotations

import json
import re
import time

from .config import settings
from .db import LlmUsage, session
from .pricing import cost_usd

_client = None


def _openai():
    global _client
    if _client is None:
        from openai import OpenAI

        # No SDK-level retries: a retry of the same model after a timeout doubled the wait (2 x LLM_TIMEOUT_S)
        # before the fallback was even tried. _chat() does the retrying, moving on to the fallback model.
        _client = OpenAI(base_url=settings.inference_base_url, api_key=settings.inference_api_key,
                         timeout=settings.llm_timeout_s, max_retries=0)
    return _client


# Short classification/summary calls; they normally finish in seconds, so a long wait means a stuck call.
_FAST_ROLES = {"classifier", "safety", "planner"}


def _timeout_for(role: str) -> float:
    return settings.llm_fast_timeout_s if role in _FAST_ROLES else settings.llm_timeout_s


def _record(invoice_id, role, model, usage, latency_ms, ok=True):
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    with session() as s:
        s.add(LlmUsage(invoice_id=invoice_id, role=role, model=model, prompt_tokens=pt, completion_tokens=ct,
                       cost_usd=cost_usd(model, pt, ct), latency_ms=latency_ms, ok=ok))
        s.commit()


class EmptyCompletion(RuntimeError):
    """The model spent its whole budget (e.g. hidden reasoning) and returned no content."""


def _create(kwargs):
    resp = _openai().chat.completions.create(**kwargs)
    choice = resp.choices[0]
    if not (choice.message.content or "").strip() or choice.finish_reason == "length":
        raise EmptyCompletion(f"{kwargs['model']}: finish={choice.finish_reason}, "
                              f"{getattr(resp.usage, 'completion_tokens', '?')} tokens, no usable content")
    return resp


def _chat(model, messages, *, role, invoice_id, json_mode=False, temperature=None):
    kwargs = {"model": model, "messages": messages,
              "temperature": settings.llm_temperature if temperature is None else temperature,
              # Vultr's models are reasoning models: unbounded, they "think" for 10k+ tokens and
              # time out with no answer. Low effort + a hard cap keeps every call bounded.
              "max_tokens": settings.llm_max_tokens}
    # Code-writing needs more thought than classification/summaries; everything else stays fast.
    coder = role.startswith("coder")
    effort = settings.llm_coder_reasoning_effort if coder else settings.llm_reasoning_effort
    if coder:
        kwargs["max_tokens"] = settings.llm_coder_max_tokens
    if effort:
        kwargs["extra_body"] = {"reasoning_effort": effort}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    kwargs["timeout"] = _timeout_for(role)
    # The requested model once, then the fallback (retried LLM_MAX_RETRIES times). Every attempt is
    # recorded, failed ones with ok=False, so cost and latency figures stay honest.
    attempts = [model] + [settings.model_fallback] * (1 + max(0, settings.llm_max_retries))
    if model == settings.model_fallback:
        attempts = attempts[1:]
    for i, m in enumerate(attempts):
        kwargs["model"] = m
        t0 = time.monotonic()
        try:
            resp = _create(kwargs)
        except Exception:
            _record(invoice_id, role, m, None, int((time.monotonic() - t0) * 1000), ok=False)
            if i == len(attempts) - 1:
                raise
            continue
        _record(invoice_id, role, m, getattr(resp, "usage", None), int((time.monotonic() - t0) * 1000))
        return resp.choices[0].message.content or ""
    raise AssertionError("unreachable")


# --------------------------------------------------------------- public API

def quarantined(system: str, untrusted_text: str, task: str, *, role: str, invoice_id: str,
                json_mode: bool = False, doc_id: str = "doc") -> str:
    """The ONLY entry point that may see untrusted document text. No tools exposed."""
    marked = "\n".join("⟦d⟧ " + ln for ln in untrusted_text.splitlines())
    user = (f'<untrusted_document id="{doc_id}">\n{marked}\n</untrusted_document>\n\n{task}')
    if settings.mode == "mock":
        return _mock(role, untrusted_text, invoice_id)
    return _chat(_model_for(role), [{"role": "system", "content": system}, {"role": "user", "content": user}],
                 role=role, invoice_id=invoice_id, json_mode=json_mode)


def privileged(system: str, structured: dict, *, role: str, invoice_id: str, json_mode: bool = True) -> str:
    """Planner/explainer. Accepts ONLY structured data; raw strings are rejected."""
    if not isinstance(structured, dict):
        raise TypeError("privileged() takes structured data only, never raw text")
    if settings.mode == "mock":
        return _mock(role, json.dumps(structured), invoice_id)
    user = "Input data (JSON):\n" + json.dumps(structured, ensure_ascii=False)
    return _chat(settings.model_planner, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                 role=role, invoice_id=invoice_id, json_mode=json_mode)


def vision(system: str, images_b64: list[str], structured: dict, *, invoice_id: str) -> str:
    if settings.mode == "mock":
        return _mock("vision", json.dumps(structured), invoice_id)
    content = [{"type": "text", "content": json.dumps(structured)}] if False else []
    parts = [{"type": "text", "text": "Context:\n" + json.dumps(structured)}]
    for b in images_b64[:3]:
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}})
    return _chat(settings.model_vision, [{"role": "system", "content": system}, {"role": "user", "content": parts}],
                 role="vision", invoice_id=invoice_id, json_mode=True)


def _model_for(role: str) -> str:
    return {"coder_extract": settings.model_coder, "coder_validate": settings.model_coder,
            "classifier": settings.model_planner, "safety": settings.model_safety}.get(role, settings.model_coder)


def extract_code_block(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            return json.loads(text[s:e + 1])
        raise


# --------------------------------------------------------------- mock mode
# Benign canned outputs so the pipeline runs with no API key. The mock does NOT
# simulate any attack; it returns clean parsing code / neutral verdicts. Real
# containment behaviour is exercised against the live model and the sandbox.

def _mock(role: str, text: str, invoice_id: str) -> str:
    _record(invoice_id, role, "mock", None, 1)
    if role == "coder_extract":
        return "```python\n" + _MOCK_EXTRACT + "\n```"
    if role == "coder_validate":
        return "```python\n" + _MOCK_VALIDATE + "\n```"
    if role == "classifier":
        hits = bool(re.search(r"system note|ai assistant|automated parser|pre-approved|ignore (all|previous)", text, re.I))
        return json.dumps({"score": 0.95 if hits else 0.02, "quotes": ["(mock) instruction-like text"] if hits else []})
    if role == "safety":
        return json.dumps({"flag": False})
    if role == "vision":
        return json.dumps({"credential_harvest": False, "brand_claimed": None, "domain_matches_vendor": True,
                           "downloads_seen": 0, "confidence": 0.3, "reasons": ["(mock) no screenshot analysis"]})
    if role == "planner":
        return json.dumps({"headline": "Review complete (mock)", "reasons": ["Generated without a live model."],
                           "recommended_action": "Enable Vultr inference for real summaries."})
    return "{}"


# The mock extractor reads the scan text the orchestrator drops at /input/context.json.
_MOCK_EXTRACT = r'''
import json, re, datetime as dt
from airlock_checks import money, pdf, io

def to_date(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except Exception:
            pass
    return "2026-01-01"

text = pdf.text("/input/invoice.pdf")
eu = bool(re.search(r"mwst|rechnung|zwischensumme|gesamt", text, re.I))
hint = "eu" if eu else None
flat = text.replace("\n", " ")

lines = []
for m in re.finditer(r"^(.+?)\s+(\d[\d.,]*)\s+([\d.,]+)\s+([\d.,]+)\s*$", text, re.M):
    desc, qty, unit, amt = m.groups()
    low = desc.lower()
    if any(w in low for w in ("subtotal", "total", "tax", "vat", "mwst", "zwischensumme", "gesamt",
                              "invoice number", "iban", "swift", "bic", "account", "routing", "sort code",
                              "due date", "po number", "bestellnr")):
        continue
    try:
        lines.append({"description": desc.strip()[:200], "qty": str(money.parse(qty, hint)),
                      "unit_price": str(money.parse(unit, hint)), "amount": str(money.parse(amt, hint))})
    except Exception:
        pass

def grab(pat, src=None, d=""):
    m = re.search(pat, src if src is not None else text, re.I)
    return m.group(1).strip() if m else d

# totals: search flattened text; lookbehind so "Total" doesn't match inside "Subtotal",
# and take the LAST total (it appears after subtotal and tax).
_totals = re.findall(r"(?<![A-Za-z])(?:Total|Gesamt)\b[^0-9]*([0-9][\d.,]*)", flat, re.I)
total = _totals[-1] if _totals else ""
sub = grab(r"(?:Subtotal|Zwischensumme)[^0-9]*([0-9][\d.,]*)", flat) or total
taxm = re.search(r"(?:Sales\s*tax|\bTax\b|\bVAT\b|MwSt)[^%0-9]*\(?\s*[\d.,]*\s*%?\s*\)?[^0-9]*([0-9][\d.,]*)", flat, re.I)
cur = "EUR" if eu else "USD"
mc = re.search(r"\b(USD|EUR|GBP)\b", text)
if mc:
    cur = mc.group(1)
iban = grab(r"IBAN[:\s]*([A-Z]{2}[0-9A-Z ]{13,34})").replace(" ", "")

# vendor name: first meaningful line that isn't a header word or a field label
header = re.compile(r"^(invoice|rechnung|tax invoice|bill|facture)\b", re.I)
label = re.compile(r"(number|date|no\.?|bill to|description|qty|: )", re.I)
vendor = "Unknown"
for ln in (l.strip() for l in text.splitlines() if l.strip()):
    if header.match(ln) or label.search(ln) or not re.search(r"[A-Za-z]{3}", ln):
        continue
    vendor = ln[:120]
    break

fields = {
    "vendor_name": vendor,
    "sender_email": grab(r"([\w.+-]+@[\w.-]+\.[a-z]{2,})"),
    "invoice_number": grab(r"(?:Invoice (?:No\.?|Number)|Invoice No\.?|Rechnungsnr\.?)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]+)", flat),
    "invoice_date": to_date(grab(r"(?:Invoice Date|Datum(?: / Date)?)\s*[:]?\s*([0-9]{2,4}[-./][0-9]{1,2}[-./][0-9]{1,4})", flat)),
    "due_date": to_date(grab(r"(?:Due Date|Due|F.?llig(?: / Due)?)\s*[:]?\s*([0-9]{2,4}[-./][0-9]{1,2}[-./][0-9]{1,4})", flat)),
    "po_number": grab(r"(?:PO Number|Bestellnr\.?(?: / PO)?|\bPO\b)\s*[:]?\s*(PO-[A-Za-z0-9]+|[A-Za-z0-9]{3,}-?[A-Za-z0-9]*)", flat),
    "currency": cur,
    "lines": lines,
    "subtotal": str(money.parse(sub, hint)) if sub else "0",
    "tax": str(money.parse(taxm.group(1), hint)) if taxm else "0",
    "total": str(money.parse(total, hint)) if total else "0",
    "bank": {"iban": iban or None, "account_name": None},
    "links": pdf.links("/input/invoice.pdf"),
    "notes": "",
}
io.write_json("/out/result.json", fields)
print("extracted", len(lines), "lines")
'''

_MOCK_VALIDATE = '''
import json
from decimal import Decimal
from airlock_checks import bank, domains, text as T, io
f = json.load(open("/input/fields.json"))
ctx = json.load(open("/input/context.json"))
checks = []
def add(i, p, d): checks.append({"id": i, "passed": bool(p), "detail": d[:300]})
# This sandbox check is advisory; the control plane recomputes everything.
sub = sum(Decimal(l["amount"]) for l in f["lines"])
add("arith", abs(sub + Decimal(f.get("tax","0")) - Decimal(f["total"])) <= Decimal("0.01"),
    f"lines {sub} + tax {f.get('tax')} vs total {f['total']}")
b = f.get("bank") or {}
if b.get("iban"):
    r = bank.iban(b["iban"]); add("iban_valid", r["valid"], r.get("reason","ok"))
else:
    add("iban_valid", False, "no iban")
io.write_json("/out/checks.json", {"checks": checks})
print("validated", len(checks), "checks")
'''
