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


# ------------------------------------------------------------ extraction helpers
# Building blocks for model-written extraction programs. They never raise on a
# missing match: they return `default`, so a program degrades instead of crashing.

def find(doc: str, pattern: str, default=None, flags: int = re.I | re.M):
    """First match of `pattern`: group(1) if the pattern has a group, else the whole match."""
    m = re.search(pattern, doc or "", flags)
    if not m:
        return default
    val = m.group(1) if m.re.groups else m.group(0)
    return val.strip() if isinstance(val, str) else default


def after(doc: str, labels, default=None, token: bool = False):
    """Value after a label such as 'Invoice Number:' anywhere on a line.

    `labels` is one label or a list of alternatives ('Invoice No.', 'Rechnungsnr.').
    Returns the rest of that line, or just its first whitespace-separated token
    when token=True (use that for ids, dates and numbers in two-column layouts).
    """
    for label in ([labels] if isinstance(labels, str) else list(labels)):
        lab = re.escape(label.rstrip(": ")) + r"\s*[:#]?\s*"
        m = re.search(lab + r"(.+)$", doc or "", re.I | re.M)
        if m:
            val = m.group(1).strip()
            # Bilingual label pairs, e.g. "Rechnungsnr. / Invoice No.: X": the matched label is
            # followed by "/ <other label>:" rather than the value. Skip that part.
            pair = re.match(r"^[/|]\s*[^:/|]{1,40}:\s*(.*)$", val)
            if pair:
                val = pair.group(1).strip()
            if re.fullmatch(r"[/|:#\s-]*", val):  # a bare separator is not a value
                continue
            if token:
                val = val.split()[0] if val.split() else ""
            if val:
                return val
    return default


def iso_date(s, default=None):
    """'2026-10-28', '27.10.2026', '27/10/2026' or '28 Oct 2026' -> '2026-10-28'."""
    import datetime as _dt

    s = str(s or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4}", s)
    return iso_date(m.group(0), default) if m and m.group(0) != s else default
