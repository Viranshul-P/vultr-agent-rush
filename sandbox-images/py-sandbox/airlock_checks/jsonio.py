"""JSON output with Decimal/date support."""

from __future__ import annotations

import datetime as _dt
import json
from decimal import Decimal


def _default(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def dumps(obj) -> str:
    return json.dumps(obj, default=_default, ensure_ascii=False, indent=2)


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(obj))


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
