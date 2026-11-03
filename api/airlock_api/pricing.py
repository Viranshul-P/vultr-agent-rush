"""Per-model token prices (USD per token). Fill from the Vultr pricing page at kickoff.

Values below are placeholders in the right ballpark so the metrics page shows a
realistic cost-per-invoice during development. Override via api/pricing.json.
"""

from __future__ import annotations

import json
from pathlib import Path

# USD per 1M tokens (input, output) -> stored as per-token below.
_PER_M = {
    "glm-5.3": (0.30, 1.20),
    "glm-5.3-flash": (0.10, 0.30),
    "qwen3.8-flash-next": (0.10, 0.30),
    "deepseek-v4.1-flash-1017": (0.13, 0.38),
    "nemotron-3.5-content-safety": (0.15, 0.15),
    "_default": (0.30, 1.00),
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
