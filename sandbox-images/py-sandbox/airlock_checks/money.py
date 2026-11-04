"""Locale-tolerant money parsing with Decimal."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_STRIP = re.compile(r"[^\d,.\-()]")


def parse(value, locale_hint: str | None = None) -> Decimal:
    """Parse '1,234.50', '12.460,50', '€ 1 234,56', '(99.00)' into Decimal.

    locale_hint: 'eu' treats a lone '.' followed by exactly 3 digits as a
    thousands separator ('1.234' -> 1234); otherwise it is a decimal point.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip()
    negative = s.startswith("(") and s.endswith(")") or s.startswith("-") or s.endswith("-")
    s = _STRIP.sub("", s).replace("(", "").replace(")", "").strip("-")
    if not s:
        raise ValueError(f"no digits in money value: {value!r}")

    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.56
            s = s.replace(",", "")
    elif has_comma:
        head, _, tail = s.rpartition(",")
        if len(tail) in (1, 2) and s.count(",") == 1:  # 12,5 / 12,50 decimal comma
            s = head.replace(",", "") + "." + tail
        else:  # 1,234 or 1,234,567 thousands
            s = s.replace(",", "")
    elif has_dot:
        if s.count(".") > 1:  # 1.234.567
            s = s.replace(".", "")
        else:
            head, _, tail = s.partition(".")
            if locale_hint == "eu" and len(tail) == 3:
                s = head + tail
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"unparseable money value: {value!r}") from exc
    return -d if negative else d


def q2(d) -> Decimal:
    """Round to 2 decimal places, half-up (accounting rounding)."""
    return parse(d).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def close(a, b, tol: str = "0.01") -> bool:
    return abs(parse(a) - parse(b)) <= Decimal(tol)


# ------------------------------------------------------------ extraction helpers
def amount_after(doc: str, labels, locale_hint: str | None = None, default=None):
    """The LAST amount on the first line containing one of `labels` (e.g. 'Subtotal',
    ['VAT', 'Sales tax']). Taking the last number skips rates like '(19%)'."""
    import re as _re

    for label in ([labels] if isinstance(labels, str) else list(labels)):
        lab = _re.compile(r"(?<![A-Za-z])" + _re.escape(label), _re.I)  # 'Total' must not match 'Subtotal'
        for line in (doc or "").splitlines():
            hit = lab.search(line)
            if hit:
                rest = line[hit.end():]
                rest = _re.sub(r"\(?\d+(?:[.,]\d+)?\s*%\)?", " ", rest)  # drop percentages
                nums = [n for n in _re.findall(r"\d[\d.,]*\d|\d", rest)]
                if nums:
                    try:
                        return parse(nums[-1], locale_hint)
                    except Exception:  # noqa: BLE001
                        continue
    return default


def line_items(doc: str, locale_hint: str | None = None, tol: str = "0.02") -> list[dict]:
    """Rows shaped '<description> <qty> <unit price> <amount>' whose qty * unit == amount.

    The arithmetic check is what rejects look-alike lines (IBANs, phone numbers, totals)."""
    import re as _re

    rows = []
    pat = _re.compile(r"^(?P<desc>.*?\S)\s+(?P<qty>\d+(?:[.,]\d+)?)\s+(?P<unit>\d[\d.,]*)\s+(?P<amt>\d[\d.,]*)\s*$")
    for line in (doc or "").splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        try:
            qty = parse(m["qty"], locale_hint)
            unit = parse(m["unit"], locale_hint)
            amt = parse(m["amt"], locale_hint)
        except Exception:  # noqa: BLE001
            continue
        if qty > 0 and close(qty * unit, amt, tol):
            rows.append({"description": m["desc"].strip(), "qty": qty, "unit_price": unit, "amount": amt})
    return rows
