"""mitmproxy addon: the browser sandbox's only way out.

- Denies private, loopback, link-local (incl. Vultr metadata 169.254.169.254),
  CGNAT, multicast and the VPC range, after resolving the hostname.
- Logs every request per run to /logs/<run_id>.jsonl (run id from the
  X-Airlock-Run header, which is stripped before forwarding).
- Caps response bytes per run.

    mitmdump -s airlock_addon.py --listen-port 8080 --set block_global=false
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import time
from collections import defaultdict

from mitmproxy import http

LOG_DIR = os.environ.get("PROXY_LOG_DIR", "/logs")
MAX_BYTES = int(os.environ.get("PROXY_MAX_BYTES_PER_RUN", str(20 * 1024 * 1024)))
EXTRA_DENY = [ipaddress.ip_network(c.strip()) for c in os.environ.get("PROXY_DENY_CIDRS", "").split(",") if c.strip()]
_RUN = re.compile(r"^[A-Za-z0-9_-]{6,64}$")

_bytes: dict[str, int] = defaultdict(int)


def _blocked(ip: str) -> str | None:
    addr = ipaddress.ip_address(ip)
    if addr.is_loopback:
        return "loopback"
    if addr.is_link_local:
        return "link-local (cloud metadata)"
    if addr.is_private:
        return "private range"
    if addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return "reserved range"
    if addr.version == 4 and addr in ipaddress.ip_network("100.64.0.0/10"):
        return "CGNAT range"
    for net in EXTRA_DENY:
        if addr in net:
            return f"denied range {net}"
    return None


def _log(run_id: str, entry: dict) -> None:
    """Best-effort: a logging failure must never turn into an allowed request."""
    if not _RUN.match(run_id or ""):
        run_id = "unattributed"
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, f"{run_id}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        print(f"airlock egress: log write failed ({exc}); decision was {entry.get('decision')}", flush=True)


def _deny(flow: http.HTTPFlow, status: int, reason: str) -> None:
    flow.response = http.Response.make(status, f"airlock egress: blocked ({reason})".encode(),
                                       {"Content-Type": "text/plain"})


class AirlockEgress:
    def request(self, flow: http.HTTPFlow) -> None:
        # FAIL CLOSED: any unexpected error denies the request. The decision (flow.response)
        # is always set BEFORE logging, so a logging problem can never let a request through.
        run_id = "unattributed"
        entry: dict = {"ts": time.time()}
        try:
            run_id = flow.request.headers.pop("X-Airlock-Run", "unattributed")
            flow.metadata["airlock_run"] = run_id
            host = flow.request.pretty_host
            entry.update(method=flow.request.method, host=host, path=flow.request.path[:200])
            decision = self._decide(flow, host, run_id, entry)
        except Exception as exc:  # noqa: BLE001
            entry.update(decision="deny", reason=f"internal error: {type(exc).__name__}")
            _deny(flow, 403, "internal error")
            decision = None
        if decision:
            status, reason = decision
            entry.update(decision="deny", reason=reason)
            _deny(flow, status, reason)
        elif "decision" not in entry:
            entry.update(decision="allow")
        _log(run_id, entry)

    def _decide(self, flow: http.HTTPFlow, host: str, run_id: str, entry: dict) -> tuple[int, str] | None:
        """Return (status, reason) to deny, or None to allow."""
        try:
            infos = socket.getaddrinfo(host, flow.request.port, proto=socket.IPPROTO_TCP)
            ips = sorted({i[4][0] for i in infos})
        except socket.gaierror as exc:
            return 502, f"dns failure: {exc}"
        if not ips:
            return 502, "dns failure: no addresses"
        entry["ip"] = ips[0]
        for ip in ips:
            reason = _blocked(ip)
            if reason:
                return 403, reason
        if _bytes[run_id] > MAX_BYTES:
            return 429, "byte cap reached"
        # Known residual risk: DNS rebinding between this check and mitmproxy's own connect.
        # Acceptable here because the browser container has no route anywhere except this proxy,
        # and the sandbox VM itself holds no secrets.
        return None

    def response(self, flow: http.HTTPFlow) -> None:
        run_id = flow.metadata.get("airlock_run", "unattributed")
        if flow.response and flow.response.raw_content:
            _bytes[run_id] += len(flow.response.raw_content)


addons = [AirlockEgress()]
