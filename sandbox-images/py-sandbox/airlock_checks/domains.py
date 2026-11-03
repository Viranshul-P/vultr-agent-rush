"""Host/domain helpers and lookalike scoring.

We compare full hostnames, not registrable domains: on shared suffixes such
as duckdns.org, `brightline.x.duckdns.org` and `filecourier-secure.x.duckdns.org`
share a registrable domain but belong to different parties.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit

_CONFUSABLES = [("rn", "m"), ("vv", "w"), ("0", "o"), ("1", "l"), ("3", "e"), ("5", "s"), ("|", "l"), ("i", "l")]
_BAIT_TOKENS = {"billing", "secure", "pay", "payment", "payments", "invoice", "invoices", "portal",
                "verify", "account", "accounts", "support", "login", "docs", "online", "mail"}


def of(email_or_url: str) -> str:
    """Return the lowercase host for an email address or URL ('' if none)."""
    s = str(email_or_url or "").strip()
    if not s:
        return ""
    if "@" in s and "://" not in s:
        return s.rsplit("@", 1)[1].strip(" >").lower().rstrip(".")
    if "://" not in s:
        s = "http://" + s
    host = urlsplit(s).hostname or ""
    return host.lower().rstrip(".")


def host_matches(host: str, known_hosts: list[str]) -> bool:
    """True if host equals a known host or is a subdomain of one."""
    host = of(host)
    for k in known_hosts or []:
        k = of(k)
        if k and (host == k or host.endswith("." + k)):
            return True
    return False


def _fold(s: str) -> str:
    s = s.lower()
    for a, b in _CONFUSABLES:
        s = s.replace(a, b)
    return s


def _core(host: str) -> str:
    """Strip TLD-ish last label and bait words: 'brightline-billing.example' -> 'brightline'."""
    labels = host.split(".")
    if len(labels) > 1:
        labels = labels[:-1]
    tokens = [t for t in re.split(r"[.\-_]+", ".".join(labels)) if t and t not in _BAIT_TOKENS]
    return "".join(tokens)


def lookalike(host: str, known_hosts: list[str]) -> float:
    """0..1 score that `host` imitates one of `known_hosts` without being one of them.

    1.0 = identical after folding confusables (orchardcl0ud vs orchardcloud).
    0.0 = genuinely matches a known host, or looks nothing alike.
    """
    host = of(host)
    if not host or host_matches(host, known_hosts):
        return 0.0
    best = 0.0
    fh, ch = _fold(host), _fold(_core(host))
    for k in known_hosts or []:
        k = of(k)
        if not k:
            continue
        fk = _fold(k)
        if fh == fk:
            return 1.0
        ck = _fold(_core(k))
        if ch and ck and (ch == ck or (len(ck) >= 5 and ck in ch) or (len(ch) >= 5 and ch in ck)):
            best = max(best, 0.9)
        best = max(best, SequenceMatcher(None, fh, fk).ratio() * 0.95)
    return round(best, 3)
