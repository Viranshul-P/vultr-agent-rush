"""Fixed (team-written, not model-written) scan program run in the sandbox.

The control plane never parses untrusted files itself. It sends this program
plus the invoice into a sandbox and receives plain JSON back.

Usage inside the sandbox:  python -c "from airlock_checks.scan import main; main()"
"""

from __future__ import annotations

import os

from . import jsonio, pdf

MAX_TEXT = 60_000


def main(src: str = "/input/invoice.pdf", dst: str = "/out/scan.json") -> None:
    result = {"ok": True, "error": None}
    try:
        txt = pdf.text(src)
        result.update({
            "text": txt[:MAX_TEXT],
            "text_truncated": len(txt) > MAX_TEXT,
            "hidden_text": pdf.hidden_text(src)[:50],
            "links": pdf.links(src)[:20],
            "metadata": pdf.metadata(src),
            "size_bytes": os.path.getsize(src),
        })
    except Exception as exc:  # report, don't crash: a broken file is itself a signal
        result.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]})
    jsonio.write_json(dst, result)
    print("scan complete" if result["ok"] else "scan failed")


if __name__ == "__main__":
    main()
