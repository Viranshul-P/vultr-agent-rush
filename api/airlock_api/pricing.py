"""Per-model token prices (USD per token).

Source: Vultr docs, "How Do I Monitor the Usage and Cost of My Vultr Serverless Inference
Subscription?" (updated 26 Oct 2026, read 5 Nov 2026): "Requests are billed at $0.55 per
1,000,000 input tokens and $2.75 per 1,000,000 output tokens." The page gives one rate and no
per-model table, so every model uses it. Failed calls are recorded with zero tokens (cost 0).
Override per model via api/pricing.json if Vultr publishes model-specific rates.
"""

from __future__ import annotations

import json
from pathlib import Path

# USD per 1M tokens (input, output).
_VULTR_FLAT = (0.55, 2.75)
_PER_M = {
    "glm-5.3": _VULTR_FLAT,
    "glm-5.3-flash": _VULTR_FLAT,
    "qwen3.8-flash-next": _VULTR_FLAT,
    "deepseek-v4.1-flash-1017": _VULTR_FLAT,
    "nemotron-3.5-content-safety": _VULTR_FLAT,
    "_default": _VULTR_FLAT,
}

_override = Path(__file__).resolve().parent.parent / "pricing.json"
if _override.exists():
    try:
        _PER_M.update(json.loads(_override.read_text()))
    except ValueError:
        pass


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = _PER_M.get(model, _PER_M["_default"])
    return round(prompt_tokens / 1e6 * pin + completion_tokens / 1e6 * pout, 6)
