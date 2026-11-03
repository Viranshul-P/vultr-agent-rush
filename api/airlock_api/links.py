"""Decide whether a sandboxed browse actually inspected the page.

If it didn't, the link must be treated as "unavailable" so the policy HOLDs
(rule R12). Kept free of side effects so it is easy to unit-test.
"""

from __future__ import annotations


def unavailable_reason(res: dict, url: str) -> str | None:
    """Return why the browse result can't be trusted, or None if it can.

    Fails safe on:
      - a non-zero runner exit code,
      - a harness error with no page loaded,
      - an HTTP error status (>= 400) for the page, which includes the 502
        the egress proxy serves when it denies or can't resolve a host,
      - an egress-proxy deny for the link's own host.
    """
    from airlock_checks import domains

    extra = res.get("extra") or {}
    if res.get("exit_code") not in (0, None):
        return f"browser exited with code {res.get('exit_code')}"
    if extra.get("error") and not extra.get("final_url"):
        return str(extra["error"])

    hosts = {h for h in (domains.of(url), domains.of(extra.get("final_url") or "")) if h}
    for entry in extra.get("proxy_log") or []:
        if entry.get("decision") == "deny" and str(entry.get("host", "")).lower() in hosts:
            return f"egress proxy denied {entry.get('host')}: {entry.get('reason', 'denied')}"

    status = extra.get("status")
    if isinstance(status, int) and status >= 400:
        return f"page returned HTTP {status}"
    return None
