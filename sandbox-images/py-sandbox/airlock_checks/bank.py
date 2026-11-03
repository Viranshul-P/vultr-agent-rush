"""Bank identifier validation (no network, no external data)."""

from __future__ import annotations

import re

# Expected IBAN lengths for common countries (ISO 13616). Unknown countries
# fall back to the generic 15-34 range.
_IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24,
    "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27,
    "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "RO": 24,
    "SA": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "TR": 26,
}


def normalize_iban(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).upper()


def iban(s: str) -> dict:
    """Validate an IBAN with the ISO 7064 mod-97 checksum."""
    n = normalize_iban(s)
    result = {"valid": False, "country": n[:2] or None, "bank_code": None, "normalized": n, "reason": ""}
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", n):
        result["reason"] = "bad format"
        return result
    expected = _IBAN_LENGTHS.get(n[:2])
    if expected and len(n) != expected:
        result["reason"] = f"length {len(n)} != {expected} for {n[:2]}"
        return result
    rearranged = n[4:] + n[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    if int(digits) % 97 != 1:
        result["reason"] = "checksum failed"
        return result
    result["valid"] = True
    result["bank_code"] = n[4:8]
    return result


def aba(s: str) -> bool:
    """US ABA routing number checksum (weights 3,7,1)."""
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) != 9:
        return False
    w = (3, 7, 1) * 3
    return sum(int(x) * y for x, y in zip(d, w)) % 10 == 0


def same_account(a: dict | None, b: dict | None) -> bool:
    """Compare two bank dicts ({iban|account_number, routing}) after normalisation."""
    a, b = a or {}, b or {}
    ia, ib = normalize_iban(a.get("iban") or ""), normalize_iban(b.get("iban") or "")
    if ia or ib:
        return ia == ib
    na = re.sub(r"\D", "", a.get("account_number") or "")
    nb = re.sub(r"\D", "", b.get("account_number") or "")
    ra = re.sub(r"\D", "", a.get("routing") or "")
    rb = re.sub(r"\D", "", b.get("routing") or "")
    return bool(na) and na == nb and ra == rb
