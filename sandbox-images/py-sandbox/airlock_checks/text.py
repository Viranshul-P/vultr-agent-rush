"""Fuzzy text matching."""

from __future__ import annotations

import re

try:
    from rapidfuzz import fuzz as _fuzz
except ImportError:  # pragma: no cover - fallback when rapidfuzz isn't installed
    _fuzz = None


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def fuzzy(a: str, b: str) -> float:
    """Similarity 0..1 between two strings (order-insensitive token match)."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if _fuzz is not None:
        return _fuzz.token_sort_ratio(a, b) / 100.0
    from difflib import SequenceMatcher

    return SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()


def ratio(a: str, b: str) -> float:
    """Plain character similarity 0..1 (good for invoice numbers)."""
    a, b = str(a or "").upper().strip(), str(b or "").upper().strip()
    if not a or not b:
        return 0.0
    if _fuzz is not None:
        return _fuzz.ratio(a, b) / 100.0
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio()
