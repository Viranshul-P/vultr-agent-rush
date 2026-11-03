"""PDF inspection helpers (sandbox only; requires pdfplumber)."""

from __future__ import annotations

import re

import pdfplumber

_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


def text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def chars(path: str) -> list[dict]:
    out = []
    with pdfplumber.open(path) as pdf:
        for i, p in enumerate(pdf.pages):
            shapes = list(p.rects or []) + list(p.curves or [])  # rounded rects are curves
            dark_fills = [r for r in shapes if r.get("fill") and not _is_white(_color(r.get("non_stroking_color")))]
            for c in p.chars:
                out.append({
                    "text": c.get("text", ""),
                    "size": round(float(c.get("size") or 0), 2),
                    "color": _color(c.get("non_stroking_color")),
                    "x": round(float(c.get("x0") or 0), 1),
                    "y": round(float(c.get("top") or 0), 1),
                    "page": i,
                    "off_page": _off_page(c, p),
                    "on_dark_fill": any(_inside(c, r) for r in dark_fills),
                })
    return out


def _inside(c, r) -> bool:
    cx = (float(c["x0"]) + float(c["x1"])) / 2
    cy = (float(c["top"]) + float(c["bottom"])) / 2
    return float(r["x0"]) <= cx <= float(r["x1"]) and float(r["top"]) <= cy <= float(r["bottom"])


def _color(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return (float(v),)
    try:
        return tuple(float(x) for x in v)
    except (TypeError, ValueError):
        return None


def _is_white(color) -> bool:
    if not color:
        return False
    if len(color) == 1:  # grayscale
        return color[0] >= 0.95
    if len(color) == 3:  # RGB
        return all(x >= 0.95 for x in color)
    if len(color) == 4:  # CMYK: white = no ink
        return all(x <= 0.05 for x in color)
    return False


def _off_page(c, page) -> bool:
    x0, top = float(c.get("x0") or 0), float(c.get("top") or 0)
    return x0 < -1 or top < -1 or x0 > float(page.width) + 1 or top > float(page.height) + 1


def hidden_text(path: str, min_len: int = 3) -> list[str]:
    """Strings drawn white-on-white, in a font smaller than 2pt, or off the page."""
    runs: dict[tuple, list[str]] = {}
    order: list[tuple] = []
    for c in chars(path):
        white_on_white = _is_white(c["color"]) and not c["on_dark_fill"]
        hidden = white_on_white or c["size"] < 2 or c["off_page"]
        if not hidden:
            continue
        key = (c["page"], round(c["y"]))
        if key not in runs:
            runs[key] = []
            order.append(key)
        runs[key].append(c["text"])
    out = []
    for k in order:
        s = re.sub(r"\s+", " ", "".join(runs[k])).strip()
        if len(s) >= min_len:
            out.append(s)
    return out


def links(path: str) -> list[str]:
    found: list[str] = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            for h in (p.hyperlinks or []):
                uri = h.get("uri")
                if uri and uri not in found:
                    found.append(uri)
            for m in _URL.findall(p.extract_text() or ""):
                m = m.rstrip(".,;")
                if m not in found:
                    found.append(m)
    return found


def metadata(path: str) -> dict:
    with pdfplumber.open(path) as pdf:
        return {str(k): str(v)[:500] for k, v in (pdf.metadata or {}).items()}


def tables(path: str) -> list[list[list[str | None]]]:
    out = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            out.extend(p.extract_tables() or [])
    return out
