"""Browser sandbox harness: open one untrusted URL, observe, record, exit.

Runs inside the browser-sandbox container (gVisor, internal network, all
traffic through the egress proxy). Writes /out/browse.json, two screenshots,
and any downloads into /out/quarantine/ (saved, hashed by the runner, never opened).

    python harness.py --url URL --run-id ID --timeout 45 --proxy http://egress-proxy:8080 --out /out
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

FORMS_JS = """
() => {
  const forms = [...document.querySelectorAll('form')].map(f => ({
    action: f.getAttribute('action') || '',
    fields: [...f.querySelectorAll('input,select,textarea')].map(i => (i.type || i.tagName).toLowerCase() + ':' + (i.name || i.id || ''))
  }));
  const loose = [...document.querySelectorAll('input[type=password]')].filter(i => !i.closest('form')).length;
  return {forms, loose_password_inputs: loose};
}
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--out", default="/out")
    a = ap.parse_args()

    out = a.out
    qdir = os.path.join(out, "quarantine")
    os.makedirs(qdir, exist_ok=True)
    result = {"url": a.url, "final_url": None, "status": None, "title": None, "redirects": [], "page_text": "",
              "forms": [], "loose_password_inputs": 0, "screenshots": [], "downloads_attempted": [],
              "console_errors": 0, "error": None, "timing_ms": {}}
    t0 = time.monotonic()

    with sync_playwright() as p:
        launch = {"args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]}
        if a.proxy:
            launch["proxy"] = {"server": a.proxy}
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True,  # the egress proxy intercepts TLS to log requests
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"X-Airlock-Run": a.run_id},  # proxy uses (and strips) this to attribute logs
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36",
        )
        page = ctx.new_page()

        def on_download(d):
            name = re.sub(r"[^A-Za-z0-9._-]", "_", d.suggested_filename or "download.bin")[:80]
            result["downloads_attempted"].append(name)
            try:
                d.save_as(os.path.join(qdir, name))  # quarantined: never opened or executed
            except PWError as exc:
                result["downloads_attempted"][-1] += f" (save failed: {exc})"

        page.on("download", on_download)
        page.on("console", lambda m: result.__setitem__("console_errors", result["console_errors"] + (m.type == "error")))
        page.on("framenavigated", lambda f: f == page.main_frame and result["redirects"].append(f.url))

        try:
            resp = page.goto(a.url, wait_until="load", timeout=a.timeout * 1000)
            result["status"] = resp.status if resp else None
            if resp:
                chain, r = [], resp.request
                while r.redirected_from:
                    r = r.redirected_from
                    chain.insert(0, r.url)
                result["redirects"] = chain + [u for u in result["redirects"] if u not in chain]
            result["timing_ms"]["load"] = int((time.monotonic() - t0) * 1000)
            page.screenshot(path=os.path.join(out, "landing.png"))
            result["screenshots"].append("landing.png")
            page.wait_for_timeout(5000)  # let auto-downloads / scripts fire
            page.screenshot(path=os.path.join(out, "after-5s.png"))
            result["screenshots"].append("after-5s.png")
            result["final_url"] = page.url
            result["title"] = page.title()[:200]
            result["page_text"] = page.inner_text("body")[:20000]
            f = page.evaluate(FORMS_JS)
            result["forms"], result["loose_password_inputs"] = f["forms"][:10], f["loose_password_inputs"]
            # How much CPU did the page manage to burn? (pages may expose a counter; see demo-sites)
            try:
                result["page_cpu_counter"] = page.evaluate("() => window.__airlockBurn || null")
            except PWError:
                pass
        except PWError as exc:
            result["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
            try:
                page.screenshot(path=os.path.join(out, "error.png"))
                result["screenshots"].append("error.png")
            except PWError:
                pass
        finally:
            result["timing_ms"]["total"] = int((time.monotonic() - t0) * 1000)
            ctx.close()
            browser.close()

    with open(os.path.join(out, "browse.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    print("browse complete" if not result["error"] else "browse finished with error")


if __name__ == "__main__":
    main()
