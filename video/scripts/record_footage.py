"""Record the Airlock demo footage from the live site, one clip per video segment.

Each segment is its own Playwright page (same browser context, so one demo workspace), recorded at 1920x1080.
A fake cursor follows the real mouse events, with a ripple on every click, so viewers can follow along.
Action timestamps (seconds from the start of each clip) go to clips/marks.json for caption timing.
"""
import json, os, sys, time
from playwright.sync_api import sync_playwright

B = "https://app.beyonders.duckdns.org"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "clips")
os.makedirs(OUT, exist_ok=True)
W, H, ZOOM = 1920, 1080, 1.25        # true 1080p viewport; the app is zoomed to 125% so text reads well on video
PROC = ("NEW", "SCANNING", "EXTRACTING", "VALIDATING", "INSPECTING_LINKS", "DECIDING")

CURSOR_JS = r"""
(() => {
  if (window.__fakeCursor) return; window.__fakeCursor = 1;
  const Z = 1.25;
  const zoomIt = () => { if (document.documentElement) document.documentElement.style.zoom = String(Z); };
  zoomIt(); document.addEventListener('readystatechange', zoomIt); document.addEventListener('DOMContentLoaded', zoomIt);
  new MutationObserver(zoomIt).observe(document, {childList: true});
  const mk = () => {
    const c = document.createElement('div');
    c.id = '__cursor';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.6 14.8 L11.6 21.4 L14.4 20.2 L11.4 13.7 L17.6 13.4 Z" fill="#0d1420" stroke="#ffffff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'0px', top:'0px', zoom:String(1/Z), zIndex:2147483647, pointerEvents:'none', transform:'translate(-3px,-2px)', transition:'none', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.3))'});
    document.documentElement.appendChild(c);
    return c;
  };
  let c = null;
  const ensure = () => (c && c.isConnected) ? c : (c = mk());
  window.addEventListener('mousemove', e => { const k = ensure(); k.style.left = e.clientX + 'px'; k.style.top = e.clientY + 'px'; }, true);
  window.addEventListener('mousedown', e => {
    const r = document.createElement('div');
    Object.assign(r.style, {position:'fixed', zoom:String(1/Z), left:(e.clientX-18)+'px', top:(e.clientY-18)+'px', width:'36px', height:'36px', borderRadius:'50%',
      border:'3px solid rgba(43,85,240,.85)', background:'rgba(43,85,240,.18)', zIndex:2147483646, pointerEvents:'none',
      transform:'scale(.4)', opacity:'1', transition:'transform .45s cubic-bezier(.16,1,.3,1), opacity .5s ease'});
    document.documentElement.appendChild(r);
    requestAnimationFrame(() => { r.style.transform = 'scale(1.6)'; r.style.opacity = '0'; });
    setTimeout(() => r.remove(), 600);
  }, true);
  document.addEventListener('DOMContentLoaded', ensure);
})();
"""

marks = {}


class Clip:
    def __init__(self, ctx, name):
        self.name, self.pg, self.t0 = name, ctx.new_page(), time.time()
        self.pos = (W * 0.5, H * 0.55)
        marks[name] = []

    def mark(self, label):
        marks[self.name].append({"t": round(time.time() - self.t0, 2), "label": label})

    def wait(self, ms):
        self.pg.wait_for_timeout(ms)

    def move_to(self, x, y, ms=650):
        steps = max(8, int(ms / 16))
        x0, y0 = self.pos
        for i in range(1, steps + 1):
            p = i / steps
            e = 1 - (1 - p) ** 3  # ease-out
            self.pg.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            self.pg.wait_for_timeout(ms / steps)
        self.pos = (x, y)

    def point(self, locator, ms=650, dx=0.5, dy=0.5):
        locator.scroll_into_view_if_needed()
        b = locator.bounding_box()
        self.move_to(b["x"] + b["width"] * dx, b["y"] + b["height"] * dy, ms)
        return b

    def click(self, locator, label=None, ms=650, after=700):
        self.point(locator, ms)
        self.wait(180)
        self.pg.mouse.down(); self.wait(70); self.pg.mouse.up()
        if label: self.mark(label)
        self.wait(after)

    def scroll(self, dy, ms=900):
        steps = max(10, int(ms / 16))
        for _ in range(steps):
            self.pg.mouse.wheel(0, dy / steps)
            self.pg.wait_for_timeout(ms / steps)

    def scroll_to(self, locator, offset=110, ms=1000):
        b = locator.bounding_box()
        self.scroll(b["y"] - offset, ms)

    def goto(self, path, settle=2500):
        self.pg.goto(B + path)
        self.pg.mouse.move(*self.pos)
        self.wait(settle)

    def close(self):
        self.mark("end")
        v = self.pg.video
        self.pg.close()
        dest = os.path.join(OUT, f"{self.name}.webm")
        if os.path.exists(dest): os.remove(dest)
        v.save_as(dest)
        print("saved", dest, flush=True)


def invoices(pg):
    return pg.evaluate("fetch('/api/invoices').then(r=>r.json())")["invoices"]


def wait_done(pg, limit=360):
    t0 = time.time()
    while time.time() - t0 < limit:
        L = invoices(pg)
        if all(i["status"] not in PROC and not i.get("queued") for i in L): return L
        pg.wait_for_timeout(1500)
    return invoices(pg)


def main(only=None):
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        # Pre-warm the models in a throwaway workspace (not recorded).
        warm = br.new_context(); wp = warm.new_page(); wp.goto(B + "/inbox"); wp.wait_for_timeout(1000)
        wp.evaluate("fetch('/api/inbox/process-all',{method:'POST'})"); wait_done(wp); warm.close()
        print("pre-warmed", flush=True)

        ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, color_scheme="light",
                             record_video_dir=os.path.join(OUT, "_raw"), record_video_size={"width": 1920, "height": 1080})
        ctx.add_init_script(CURSOR_JS)
        ctx.add_init_script("try{localStorage.setItem('airlock-theme','light')}catch(e){}")

        # 1. Overview hero + How it works (architecture, dual-LLM)
        c = Clip(ctx, "s01_overview"); c.goto("/", 3500); c.mark("hero")
        c.wait(5000); c.scroll(700, 1600); c.wait(2500); c.scroll(-700, 1200)
        c.click(c.pg.locator("nav.nav a:has-text('How it works')"), "nav how-it-works", after=2500)
        c.mark("architecture"); c.wait(4500)
        c.scroll_to(c.pg.locator(".panel:has-text('Dual-LLM safety')").first, 90, 1400); c.mark("dual-llm"); c.wait(5000)
        c.scroll_to(c.pg.locator(".panel:has(.tiles)").first, 90, 1200); c.mark("containment tiles"); c.wait(3500)
        c.close()

        # 2. Inbox: process all six
        c = Clip(ctx, "s02_inbox"); c.goto("/inbox", 3000); c.mark("inbox new")
        c.wait(2500)
        c.click(c.pg.locator("button:has-text('Process inbox')").first, "process inbox", after=500)
        L = wait_done(c.pg); c.mark("all done"); c.wait(1500)
        c.point(c.pg.locator(".strip").first, 900); c.wait(3500)
        c.click(c.pg.locator(".seg button:has-text('Contained')").first, "filter contained", after=2500)
        c.click(c.pg.locator(".seg button:has-text('All')").first, "filter all", after=1500)
        c.close()
        ids = {i["filename"][:2]: i["id"] for i in L}
        statuses = {i["filename"][:2]: i["status"] for i in L}
        print("outcomes", statuses, flush=True)

        # 3. Clean invoice: pipeline, code drawer, run timeline, approve, ledger
        c = Clip(ctx, "s03_clean"); c.goto("/inbox", 2000)
        c.click(c.pg.locator("tr:has-text('INV-2026-0412')").first, "open clean", after=2800)
        c.point(c.pg.locator(".pipe").first, 900); c.mark("pipeline"); c.wait(2500)
        c.scroll_to(c.pg.locator(".panel:has(.checks)").first, 100, 1200); c.mark("checks ring"); c.wait(2500)
        c.scroll_to(c.pg.locator(".panel:has(.gantt)").first, 100, 1200); c.mark("run timeline"); c.wait(2000)
        c.click(c.pg.locator(".g-row:has-text('Extract')").first, "open extract run", after=2500)
        c.mark("isolation tiles"); c.wait(3000)
        c.scroll(500, 1400); c.mark("model code"); c.wait(3500)
        c.pg.keyboard.press("Escape"); c.mark("close drawer"); c.wait(900)
        c.scroll(-4000, 1200); c.wait(800)
        c.click(c.pg.locator("button:has-text('Approve')").first, "approve", after=3200)
        c.click(c.pg.locator("nav.nav a:has-text('Ledger')"), "open ledger", after=3500)
        c.close()

        # 4. Prompt injection
        c = Clip(ctx, "s04_injection"); c.goto(f"/invoices/{ids['05']}", 3000); c.mark("verdict")
        c.point(c.pg.locator(".verdict h2").first, 900); c.wait(3500)
        c.point(c.pg.locator(".blast").first, 900); c.mark("blast radius"); c.wait(3000)
        c.scroll_to(c.pg.locator(".panel:has-text('Hidden text found')").first, 100, 1300); c.mark("hidden text")
        c.point(c.pg.locator(".panel:has-text('Hidden text found') pre").first, 900); c.wait(5000)
        c.point(c.pg.locator(".tl-item:has-text('Hidden instructions')").first, 900); c.mark("detector event"); c.wait(3000)
        c.close()

        # 5. Phishing link
        c = Clip(ctx, "s05_phishing"); c.goto(f"/invoices/{ids['06']}", 3000); c.mark("verdict")
        c.wait(2500)
        lp = c.pg.locator(".panel:has-text('Link inspection')").first
        c.scroll_to(lp, 100, 1400); c.mark("link inspection")
        c.pg.evaluate("Promise.all([...document.querySelectorAll('.shot-btn img')].map(i=>i.decode()))"); c.wait(1500)
        c.point(c.pg.locator(".panel:has-text('Link inspection') .badge").first, 800); c.wait(2500)
        c.click(c.pg.locator(".shot-btn").first, "open screenshot", after=4000)
        c.pg.keyboard.press("Escape"); c.wait(900)
        c.point(c.pg.locator("ul.contain li").first, 900); c.mark("download hash"); c.wait(3500)
        c.point(c.pg.locator("ul.contain li").nth(1), 700); c.mark("cpu loop"); c.wait(2500)
        c.close()

        # 6. Bank swap + duplicate
        c = Clip(ctx, "s06_blocked"); c.goto(f"/invoices/{ids['04']}", 3000); c.mark("bank swap verdict")
        c.point(c.pg.locator(".verdict h2").first, 800); c.wait(2500)
        c.scroll_to(c.pg.locator(".panel:has(.checks)").first, 100, 1200); c.mark("failed checks")
        c.point(c.pg.locator(".check.fail").first, 800); c.wait(3000)
        c.goto(f"/invoices/{ids['03']}", 2800); c.mark("duplicate verdict")
        c.point(c.pg.locator(".verdict h2").first, 800); c.wait(3500)
        c.close()

        # 7. Signed receipt for the approved invoice
        c = Clip(ctx, "s07_receipt"); c.goto(f"/receipts/{ids['01']}", 3500); c.mark("signature valid")
        c.point(c.pg.locator(".seal").first, 900); c.wait(2500)
        c.click(c.pg.locator("button:has-text('Verify again')").first, "verify again", after=2500)
        c.scroll(500, 1200); c.mark("manifest"); c.wait(2500)
        c.close()

        # 8. Red Team drills
        c = Clip(ctx, "s08_redteam"); c.goto("/red-team", 3000); c.mark("red team")
        c.click(c.pg.locator("button:has-text('Run all drills')").first, "run all", after=500)
        c.pg.wait_for_selector("button:has-text('Run all drills'):not([disabled])", timeout=180000); c.mark("drills done")
        c.wait(1500); c.point(c.pg.locator(".score").first, 900); c.wait(3000)
        c.scroll(600, 1500); c.mark("drill rows"); c.wait(3500)
        c.close()

        # 9. Metrics
        c = Clip(ctx, "s09_metrics"); c.goto("/metrics", 3500); c.mark("metrics")
        c.wait(3000); c.scroll(700, 1800); c.mark("breakdown"); c.wait(4000)
        c.close()

        ctx.close(); br.close()
    json.dump(marks, open(os.path.join(OUT, "marks.json"), "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
