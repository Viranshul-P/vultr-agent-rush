# QA results: Airlock Manual QA Test Cases (37 checks), 6 Nov 2026

Run by Claude Code for Team Beyonders, scripted with real HTTP requests and a real Chrome browser (Playwright).

- **Live:** https://app.beyonders.duckdns.org, build `index-DTxV6YiH.js` (PR #8; the fixes from PR #10 onwards are **not deployed yet**). Real Vultr models, gVisor (`T1-gvisor`, `runsc`).
- **Local mock:** API on `127.0.0.1:8000` (`LLM_MODE=mock`, in-process runner) and web on `127.0.0.1:5173`, from `main` plus this branch.
- SEC-06 was run **locally only**. Running it on the live site would lock the tester's IP out of uploads for an hour, and the PDF says not to run it against a shared or demo IP.

## Summary

| Result | Count | Checks |
|---|---|---|
| Pass | **32** | everything not listed below |
| Fail, fixed in this branch | **4** | FLOW-08 (P1, double payment), ENV-02 (P0, favicon 404), UI-03 (P1), UI-04 (P1) |
| Blocked | **1** | OPS-02 (needs the Vultr console) |

**Most important finding: FLOW-08.** Calling "process" on an invoice that was already **POSTED** re-ran the pipeline. That reset the invoice to AWAIT_APPROVAL, and approving it again created a **second ERP posting for the same invoice**. The duplicate check didn't catch it, because it compares an invoice only with *other* invoices. Fixed in two layers: processing is refused (409) unless the invoice is NEW or ERROR, and approval is refused if the invoice already has an ERP posting. Two regression tests cover it. **The live site has this bug until the next deploy.**

## Results

### 1. Environment and golden workflows
| ID | P | Result | Evidence |
|---|---|---|---|
| ENV-01 | P0 | Pass | `200`, ok=true, mode=mock, seed_error=null, runner backend `subprocess-unsafe-dev`, tier `DEV-UNSAFE` |
| ENV-02 | P0 | **Fail, then fixed** | Home and Inbox load (6 rows), with no failed `/api` requests. One console error: `404` for `/favicon.ico` (no icon declared; the live site does the same). Fixed with an inline SVG favicon in `web/index.html`; rerun: **0 console errors** |
| ENV-03 | P0 | Pass | Local: A processed `01` (AWAIT_APPROVAL); B still has 6 NEW invoices with its own ids; B reading A's invoice gives `404`. Live: same (workspaces `ws_7d87…`, `ws_1e14…`) |
| ENV-04 | P1 | Pass | `POST /api/workspace/reset` gives `200`; A is back to 6 NEW invoices and 0 ERP postings; B is unchanged |
| FLOW-01 | P0 | Pass | `01` reached AWAIT_APPROVAL, approve gave `200` and POSTED; ERP has 1 posting (INV-2026-0412, USD 4643.93); receipt sha256 and Ed25519 both verify (manifest `918a3e4a…`) |
| FLOW-02 | P0 | Pass | AWAIT_APPROVAL; EUR 12066.60, date 2026-10-27; 9/9 checks; arithmetic 10140.00 + 1926.60 = 12066.60; 3-way: billed quantity ≤ received, prices within 2% of PO |
| FLOW-03 | P0 | Pass | BLOCKED by R5: "matches INV-2026-0397 USD 1078.17 already paid (ERP history); number similarity 0.93, same amount"; no approve button |
| FLOW-04 | P0 | Pass | BLOCKED by R3 and R4: account GB33BUKB… differs from the one on file (…6789); `orchardcl0ud.example` imitates `orchardcloud.example`; never queued for approval |
| FLOW-05 | P0 | Pass | QUARANTINED by R1; 4 hidden text runs, classifier 1.0; blast radius 0 secrets, 0 env vars, 0 outbound, 0 host files; every run `T1-gvisor`, network `none`, env vars 0 |
| FLOW-06 | P0 | Pass | QUARANTINED by R2; credential harvest detected (confidence 0.9); download `invoice_viewer.bin` sha256 `275a021b…fd0f` (EICAR) quarantined; screenshots `landing.png` and `after-5s.png` served (200); run `browse-ca5ae402939f` on `T1-gvisor` |
| FLOW-07 | P0 | Pass | Live: 2 AWAIT_APPROVAL, 2 BLOCKED, 2 QUARANTINED in 37 s; nothing lost |
| FLOW-08 | P1 | **Fail, then fixed** | Live: processing a POSTED invoice gave `200`, it went to EXTRACTING and then AWAIT_APPROVAL, approving again gave `200`, and **ERP postings went to 2**. Processing a BLOCKED invoice also gave `200` (it re-ran and was blocked again). A double click while in flight was correct (`200`, then `409 already processing`). Fix: `api/airlock_api/main.py`, plus the tests `test_a_decided_invoice_cannot_be_reprocessed_or_paid_twice` and `test_approval_refused_when_a_posting_already_exists` |

### 2. Approval, isolation and capacity
| ID | P | Result | Evidence |
|---|---|---|---|
| SEC-01 | P0 | Pass | Approving a NEW invoice, a BLOCKED one and a QUARANTINED one each gave `409` ("invoice is X, not awaiting approval") |
| SEC-02 | P0 | Pass | A second approve gave `409` ("invoice is POSTED…"); ERP still has 1 posting |
| SEC-03 | P0 | Pass | Verify reports sha256 and signature OK; the manifest holds the invoice id, all 3 run ids, the status POSTED and the outcome CLEAR |
| SEC-04 | P0 | Pass | Workspace B reading A's invoice, reading its receipt and approving it each gave `404`. *Extra, beyond the PDF:* B could read A's **sandbox run** by id (`200`) on live; fixed in PR #10 (not deployed yet) |
| SEC-05 | P1 | Pass, with a documented exception | Non-PDF gives `415` "only PDF invoices are accepted"; 6 MB gives `413` "file over 5 MB" (live and local); a valid PDF is accepted. A malformed file that *starts with* `%PDF-` is accepted at upload, then ends as **ERROR, held** ("extraction failed after retries") and can never be approved. This is by design: the control plane never parses untrusted PDFs, only the sandbox does |
| SEC-06 | P1 | Pass (local) | Limit is 10 per hour per IP. After 2 earlier uploads, 12 more gave `200` ×8 and then `429` "upload limit reached, try later" ×4; earlier uploads are intact (16 invoices) |
| SEC-07 | P1 | Pass | Live: 3 fresh workspaces started at the same instant; all finished (43 s, 67 s, 85 s), each with 2/2/2 outcomes; up to 12 invoices shown as Queued; each workspace saw only its own ids. The cap is a fixed pool of 6 workers (`PIPELINE_WORKERS`); one sample counted 7 active only because the three workspaces were polled one after another |

### 3. Live containment drills (gVisor, run through the built-in Red Team endpoint)
Each drill's run id and container id are in the API response. One example: D1, run `drill-d1-24997bd9a5`, container `be43b0cc8fcb`, image `airlock/py-sandbox@sha256:2365b4f2…`. Health afterwards: ok, 0 sandboxes left running.

| ID | Drill | Result | Actual |
|---|---|---|---|
| RED-01 | D1 host escape | Pass | `docker.sock=False, mount rc=32, uid=65534, secret-like env=none, kernel 4.19.0-gvisor` |
| RED-02 | D2 write outside /out | Pass | all writes outside /out blocked; /out writable |
| RED-03 | D3 environment dump | Pass | 11 env vars, all from the image; secret-like: none |
| RED-04 | D4 credential hunt | Pass | no credential files or directories reachable |
| RED-05 | D5 metadata SSRF | Pass | `Network is unreachable` |
| RED-06 | D6 fork bomb | Pass | stopped after 63 processes (pids cap) |
| RED-07 | D7 memory bomb | Pass | killed: oom, after allocating 450 MB |
| RED-08 | D8 infinite loop | Pass | killed: timeout after 5259 ms |
| RED-09 | D9 persistence | Pass | run 2 saw /tmp flag=False, /out flag=False |
| RED-10 | D10a exfiltration | Pass | DNS failed, TCP to 1.1.1.1 unreachable, HTTP POST failed |
| RED-11 | D10b browser to private range | Pass | 169.254.169.254 and 10.10.0.4:8700 denied by the proxy |

### 4. UI and operations
| ID | P | Result | Evidence |
|---|---|---|---|
| UI-01 | P1 | Pass | Clear: "Cleared by policy", no rules fired, next step "Approve for payment as normal", approve button shown. Blocked: R3 and R4 with the reason, next step "Do not pay; call the vendor…", no approve button. Quarantined (injection, phishing): R1 / R2, a specific next step, no approve button |
| UI-02 | P1 | Pass | Metrics shows 100% correct (40/40), 22/22 attacks, 0% false positives, 19.7 s median (the PDF's "20 s" is the same figure rounded), 36.3 s p95, $0.0094 per invoice, 11/11 drills; matches `eval/results/2026-11-05-1527.json` |
| UI-03 | P1 | **Fail on live, then fixed** | Pass/fail is clear: the score reads 11/11 contained on T1-gvisor, and a failure can't show as a pass (the row needs `passed === true`). But the page didn't show which run produced a result. Fix: each drill row now shows its run id, container id and tier |
| UI-04 | P1 | **Fail on live, then fixed** | One posting with the right invoice reference (INV-2026-0412) and amount (USD 4,643.93), but the live Ledger has **no vendor column** and no link to the receipt. Fixed in PR #10 (vendor, invoice link, receipt link, local time); not deployed yet |
| UI-05 | P1 | Pass | All 8 routes load at 1360 px and 390 px; the nav highlights the right page (invoice and receipt pages highlight Inbox); no sideways scroll; the phone menu opens; no page errors |
| OPS-01 | P0 | Pass | 2026-11-06 15:57 IST: `/api/health` gives 200, mode vultr, tier T1-gvisor, runtime runsc, Object Storage; the public Inbox loads in a fresh session |
| OPS-02 | P0 | **Blocked** | Needs the Vultr console to take or confirm snapshots of `airlock-control` and `airlock-sandbox`. The existing VM-1 rollback point is `~/airlock-backup-20261105-pre-redesign.tgz` with image `deploy-api:20261105-pre-redesign` (CHANGES.md §13) |

## To close out
1. **Deploy** PR #10 and this branch (web build plus `api/airlock_api/main.py`), then re-run FLOW-08, UI-03, UI-04 and SEC-04 (run detail) on the live site.
2. **OPS-02:** snapshot both VMs in the Vultr console and record the snapshot ids here.
