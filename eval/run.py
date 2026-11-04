"""Run the eval set through a live Airlock API and score it.

    python eval/run.py --base https://app.<domain> --invoices eval/invoices --out eval/results

Writes a timestamped JSON the Metrics page reads. Numbers in the slides/video
must come from a file this produced.

Each row records *why* the pipeline decided what it did (rules fired, failed
checks, key extracted fields, errors), so false positives can be diagnosed from
the results file alone.

The API limits uploads per IP per hour. On HTTP 429 this script waits and
retries (up to --max-wait-min per invoice) instead of skipping the invoice, so
a run is never silently smaller than the labelled set. Skipped invoices, if
any, are listed in the result.
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
STATUS_TO_OUTCOME = {s: o for o, ss in OK_OUTCOMES.items() for s in ss}
TERMINAL = {"AWAIT_APPROVAL", "POSTED", "BLOCKED", "HELD", "QUARANTINED", "ERROR", "REJECTED"}
CLEAN_CLASSES = ("clean", "benign_link")
DRILL_IDS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10a", "D10b")


# ------------------------------------------------------------------ scoring (pure)

def _pct(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def _p95(values: list[int]) -> int | None:
    if not values:
        return None
    s = sorted(values)
    return int(s[max(0, -(-len(s) * 95 // 100) - 1)])  # nearest-rank


def score(rows: list[dict]) -> dict:
    """Aggregate metrics from scored rows. Rows need: class, expected, status, ok, latency_ms."""
    correct = sum(r["ok"] for r in rows)
    clean = [r for r in rows if r["class"] in CLEAN_CLASSES]
    attacks = [r for r in rows if r["class"] not in CLEAN_CLASSES]
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]

    # Precision is defined per *outcome* (several classes share one: duplicate and
    # bank_change both expect BLOCK). Of everything the pipeline sent to outcome X,
    # how much truly belonged there?
    per_outcome = {}
    for outcome in sorted({r["expected"] for r in rows}):
        truth = [r for r in rows if r["expected"] == outcome]
        predicted = [r for r in rows if STATUS_TO_OUTCOME.get(r["status"]) == outcome]
        tp = sum(1 for r in predicted if r["expected"] == outcome)
        per_outcome[outcome] = {"recall": _pct(tp, len(truth)), "precision": _pct(tp, len(predicted)),
                                "n_true": len(truth), "n_predicted": len(predicted)}

    per_class = {}
    for cls in sorted({r["class"] for r in rows}):
        rs = [r for r in rows if r["class"] == cls]
        per_class[cls] = {"recall": _pct(sum(r["ok"] for r in rs), len(rs)),
                          "precision": per_outcome[rs[0]["expected"]]["precision"],  # of this class's outcome
                          "n": len(rs)}

    # How the misses ended up (e.g. clean -> HELD by R8). Useful for tuning.
    miss_breakdown: dict[str, int] = {}
    for r in rows:
        if not r["ok"]:
            rules = ",".join(sorted(h["id"] for h in r.get("rules_fired", []))) or "-"
            key = f"{r['class']} -> {r['status']} [{rules}]"
            miss_breakdown[key] = miss_breakdown.get(key, 0) + 1

    return {
        "n": len(rows),
        "outcome_accuracy": _pct(correct, len(rows)) or 0,
        "false_positive_rate": _pct(sum(1 for r in clean if not r["ok"]), len(clean)) or 0,
        "attacks_caught": {"caught": sum(r["ok"] for r in attacks), "total": len(attacks)},
        "latency_p50_ms": int(statistics.median(lat)) if lat else None,
        "latency_p95_ms": _p95(lat),
        "per_class": per_class,
        "per_outcome": per_outcome,
        "miss_breakdown": dict(sorted(miss_breakdown.items(), key=lambda kv: -kv[1])),
    }


def explain(inv: dict) -> dict:
    """Pull the decision trail out of an invoice detail record (all fields optional)."""
    policy = inv.get("policy") or {}
    fields = inv.get("fields") or {}
    det = inv.get("detectors") or {}
    bank = fields.get("bank") or {}
    return {
        "rules_fired": [{"id": h.get("id"), "outcome": h.get("outcome"), "detail": (h.get("detail") or "")[:200]}
                        for h in policy.get("rules_fired", [])],
        "failed_checks": [{"id": c.get("id"), "detail": (c.get("detail") or "")[:200]}
                          for c in policy.get("checks", []) if not c.get("passed")],
        "extracted": {k: fields.get(k) for k in ("vendor_name", "invoice_number", "po_number", "sender_email",
                                                 "currency", "total") if k in fields} |
                     ({"iban": bank.get("iban")} if bank.get("iban") else {}),
        "injection_suspected": det.get("injection_suspected"),
        "detector_reasons": (det.get("reasons") or [])[:4],
        "error": (inv.get("error") or "")[:300] or None,
    }


# ------------------------------------------------------------------ live run

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("AIRLOCK_BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--invoices", default=os.path.join(os.path.dirname(__file__), "invoices"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    ap.add_argument("--timeout", type=int, default=120, help="seconds to wait for one invoice to finish")
    ap.add_argument("--max-wait-min", type=float, default=70,
                    help="minutes to keep retrying one upload after HTTP 429 (rate limit) before skipping it")
    ap.add_argument("--note", default="", help="free-text note stored in the result (e.g. the deployed commit)")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    labels_doc = json.load(open(os.path.join(args.invoices, "labels.json")))
    labels = labels_doc["labels"]

    c = httpx.Client(base_url=args.base, timeout=60, follow_redirects=True)
    c.post("/api/session")

    rows, skipped = [], []
    started = time.time()
    for item in labels:
        inv = _upload(c, os.path.join(args.invoices, item["filename"]), item["filename"], args.max_wait_min)
        if isinstance(inv, str):
            print(f"{item['filename']:28} SKIPPED: {inv}")
            skipped.append({"filename": item["filename"], "class": item["class"], "reason": inv})
            continue
        t0 = time.monotonic()
        c.post(f"/api/invoices/{inv['id']}/process")
        status, detail = _wait(c, inv["id"], args.timeout)
        dt_ms = int((time.monotonic() - t0) * 1000)
        ok = status in OK_OUTCOMES.get(item["expected"], set())
        rows.append({**item, "status": status, "ok": ok, "latency_ms": dt_ms, **explain(detail)})
        why = ",".join(h["id"] for h in rows[-1]["rules_fired"]) or "-"
        print(f"{item['filename']:28} expect {item['expected']:14} got {status:16} {'OK  ' if ok else 'MISS'} [{why}]")

    metrics = c.get("/api/metrics").json()
    result = {
        "run_date": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "base": args.base,
        "dataset": {"domain": labels_doc.get("domain"), "seed": labels_doc.get("seed"), "n_labelled": len(labels)},
        "note": args.note or None,
        "duration_s": int(time.time() - started),
        **score(rows),
        "cost_per_invoice_usd": round(metrics["live"]["llm_cost_usd"] / max(1, len(rows)), 5),
        "skipped": skipped,
        "rows": rows,
    }
    result.update(_drills(c))
    fname = os.path.join(args.out, dt.datetime.now().strftime("%Y-%m-%d-%H%M") + ".json")
    json.dump(result, open(fname, "w"), indent=2)
    print(f"\naccuracy {result['outcome_accuracy']*100:.0f}%  FP {result['false_positive_rate']*100:.0f}%  "
          f"attacks {result['attacks_caught']['caught']}/{result['attacks_caught']['total']}  "
          f"p50 {result['latency_p50_ms']}ms  skipped {len(skipped)}  -> {fname}")
    for k, v in result["miss_breakdown"].items():
        print(f"  miss: {v} x {k}")


def _upload(c, path, filename, max_wait_min) -> dict | str:
    deadline = time.time() + max_wait_min * 60
    while True:
        with open(path, "rb") as fh:
            r = c.post("/api/invoices", files={"file": (filename, fh, "application/pdf")})
        if r.status_code == 200 and "id" in r.json():
            return r.json()
        if r.status_code == 429 and time.time() < deadline:
            print(f"  (upload rate limit hit; waiting 60 s before retrying {filename})")
            time.sleep(60)
            continue
        return f"upload failed: {r.status_code} {r.text[:120]}"


def _wait(c, inv_id, timeout) -> tuple[str, dict]:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        try:
            last = c.get(f"/api/invoices/{inv_id}").json()["invoice"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:  # one slow poll must not abort a 40-invoice run
            print(f"  (poll error, retrying: {type(exc).__name__})")
            time.sleep(3)
            continue
        if last.get("status") in TERMINAL:
            return last["status"], last
        time.sleep(2)
    return "TIMEOUT", last


def _drills(c) -> dict:
    """Latest saved drill results (read-only; does not run any drill)."""
    try:
        last = c.get("/api/drills").json().get("last_results", {})
    except (httpx.HTTPError, ValueError):
        return {}
    ran = [d for d in DRILL_IDS if d in last]
    if not ran:
        return {}
    return {"drills_passed": sum(1 for d in ran if last[d].get("passed")), "drills_total": len(DRILL_IDS),
            "drills_missing": [d for d in DRILL_IDS if d not in last]}


if __name__ == "__main__":
    main()
