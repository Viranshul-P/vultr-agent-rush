"""Event bus: every pipeline step is persisted and pushed live to SSE subscribers."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from .db import Event, session, utcnow


class Bus:
    def __init__(self):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def publish(self, invoice_id: str, type_: str, payload: dict | None = None) -> dict:
        with session() as s:
            ev = Event(invoice_id=invoice_id, type=type_, payload=payload or {}, ts=utcnow())
            s.add(ev)
            s.commit()
            s.refresh(ev)
        msg = {"id": ev.id, "ts": ev.ts.isoformat(), "invoice_id": invoice_id, "type": type_, "payload": ev.payload}
        for q in list(self._subs.get(invoice_id, ())):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass
        return msg

    def subscribe(self, invoice_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[invoice_id].add(q)
        return q

    def unsubscribe(self, invoice_id: str, q: asyncio.Queue) -> None:
        self._subs[invoice_id].discard(q)


bus = Bus()
