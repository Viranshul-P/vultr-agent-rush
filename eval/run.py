"""Run the eval set through a live Airlock API and score it.

    python eval/run.py --base https://app.<domain> --invoices eval/invoices --out eval/results

Writes a timestamped JSON the Metrics page reads. Numbers in the slides/video
must come from a file this produced.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import time

import httpx

OK_OUTCOMES = {
    "CLEAR/POSTED": {"AWAIT_APPROVAL", "POSTED"},
    "BLOCK": {"BLOCKED"}, "QUARANTINE": {"QUARANTINED"}, "HOLD": {"HELD"},
}
TERMINAL = {"AWAIT_APPROVAL", "POSTED", "BLOCKED", "HELD", "QUARANTINED", "ERROR", "REJECTED"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("AIRLOCK_BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--invoices", default=os.path.join(os.path.dirname(__file__), "invoices"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    labels = json.load(open(os.path.join(args.invoices, "labels.json")))["labels"]

    c = httpx.Client(base_url=args.base, timeout=60, follow_redirects=True)
    c.post("/api/session")

    rows, latencies = [], []
    per_class: dict[str, dict] = {}
    for item in labels:
        path = os.path.join(args.invoices, item["filename"])
        with open(path, "rb") as fh:
            r = c.post("/api/invoices", files={"file": (item["filename"], fh, "application/pdf")})
        if r.status_code != 200 or "id" not in r.json():
            print(f"{item['filename']:28} upload failed: {r.status_code} {r.text[:120]}")
            continue
        inv = r.json()
        t0 = time.monotonic()
        c.post(f"/api/invoices/{inv['id']}/process")
        status = _wait(c, inv["id"], args.timeout)
        dt_ms = int((time.monotonic() - t0) * 1000)
        latencies.append(dt_ms)
        ok = status in OK_OUTCOMES.get(item["expected"], set())
        rows.append({**item, "status": status, "ok": ok, "latency_ms": dt_ms})
        pc = per_class.setdefault(item["class"], {"n": 0, "correct": 0})
        pc["n"] += 1
        pc["correct"] += int(ok)
        print(f"{item['filename']:28} expect {item['expected']:14} got {status:16} {'OK' if ok else 'MISS'}")

    metrics = c.get("/api/metrics").json()
    correct = sum(r["ok"] for r in rows)
    clean = [r for r in rows if r["class"] in ("clean", "benign_link")]
    fp = sum(1 for r in clean if not r["ok"])
    result = {
        "run_date": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n": len(rows),
        "outcome_accuracy": round(correct / len(rows), 3) if rows else 0,
        "false_positive_rate": round(fp / len(clean), 3) if clean else 0,
        "latency_p50_ms": int(statistics.median(latencies)) if latencies else None,
        "latency_p95_ms": int(sorted(latencies)[int(len(latencies) * 0.95) - 1]) if latencies else None,
        "cost_per_invoice_usd": round(metrics["live"]["llm_cost_usd"] / max(1, len(rows)), 5),
        "per_class": {k: {"recall": round(v["correct"] / v["n"], 3), "precision": None, "n": v["n"]}
                      for k, v in per_class.items()},
        "rows": rows,
    }
    fname = os.path.join(args.out, dt.datetime.now().strftime("%Y-%m-%d-%H%M") + ".json")
    json.dump(result, open(fname, "w"), indent=2)
    print(f"\naccuracy {result['outcome_accuracy']*100:.0f}%  FP {result['false_positive_rate']*100:.0f}%  "
          f"p50 {result['latency_p50_ms']}ms  -> {fname}")


def _wait(c, inv_id, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = c.get(f"/api/invoices/{inv_id}").json()["invoice"]["status"]
        except httpx.HTTPError as exc:  # one slow poll must not abort a 40-invoice run
            print(f"  (poll error, retrying: {type(exc).__name__})")
            time.sleep(3)
            continue
        if s in TERMINAL:
            return s
        time.sleep(2)
    return "TIMEOUT"


if __name__ == "__main__":
    main()
