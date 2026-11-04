# Changes: 2026-11-04 (Kuldeep, with Claude Code)

This covers the work that took Airlock from "works locally in mock mode" to **running live on Vultr** at
https://app.beyonders.duckdns.org. It's split into what changed in the repo and what was set up on Vultr,
which isn't in the repo.

Every bug below was found by running the real stack (gVisor on a Vultr VM, real Vultr Inference
models). None of them showed up in local mock mode.

---

## 1. Security fixes

| What was wrong | Impact | Fix | Where |
|---|---|---|---|
| **The egress proxy failed open.** The addon wrote its log *before* applying a deny. The log write crashed (wrong path inside the container, wrong owner), so mitmproxy forwarded the request. | 🔴 The sandboxed browser could read **Vultr instance metadata** (169.254.169.254) and reach the runner's private API. Drill D10b caught it. | The decision is applied first, any internal error denies, and logging is best-effort. The proxy log path inside the container is `/logs`, and the log dir is owned by uid 1000 (mitmdump's user). Verified live: a log write failed and the request was still denied. | `egress-proxy/airlock_addon.py`, `deploy/docker-compose.sandbox.yml`, `deploy/setup-sandbox-vm.sh` |
| An unreachable pay-link failed open (earlier PR #1) | A link that couldn't be inspected was treated as clean | Fail-safe HOLD (rule R12) | `api/airlock_api/links.py`, `orchestrator.py` |
| A bad IBAN could have disappeared during extraction | An invalid account number might never reach the invalid-IBAN rule | `bank.find_iban` still returns a printed IBAN that fails the checksum, so R6 blocks it | `sandbox-images/py-sandbox/airlock_checks/bank.py` |

## 2. gVisor / sandbox fixes (needed for real runsc on a VM without KVM)

| Problem | Fix | Where |
|---|---|---|
| **D6 fork bomb crashed gVisor itself.** Under systrap the host pids cgroup also counts gVisor's helper threads, so `--pids-limit 64` made the Sentry panic after about 20 forks. | Enforce the process cap *inside* the sandbox with `RLIMIT_NPROC` (EAGAIN, like Linux). Keep the host cgroup as a backstop with headroom (`max(512, 8x)`). | `runner/airlock_runner/docker_backend.py` |
| **The browser could not reach any page.** gVisor's netstack bypasses Docker's embedded DNS (127.0.0.11), so `egress-proxy` never resolved. | The proxy gets a fixed IP `172.30.0.10` on `sbx-browser`, and `PROXY_URL` uses that IP. | `deploy/docker-compose.sandbox.yml`, `deploy/.env.sandbox.example` |
| Shell scripts broke when deployed from Windows (CRLF) | `.gitattributes` forces LF for `*.sh`, Dockerfiles, YAML and the Caddyfile | `.gitattributes` |

**Result: all 11 security drills (D1–D10b) pass under gVisor on the Vultr VM.** Raw results are in
[`docs/evidence/drills-vultr-2026-11-04.json`](docs/evidence/drills-vultr-2026-11-04.json).

## 3. AI pipeline fixes (needed for real Vultr models)

| Problem | Fix | Where |
|---|---|---|
| **Each code-writing call took ~295 s.** The models are reasoning models: unbounded, `glm-5.3` thought for 12k+ tokens, returned nothing, timed out 3 times, then fell back. | Send `reasoning_effort` (coder roles `medium`, others `low`) and a `max_tokens` cap on every call. Empty or truncated replies trigger the fallback model. Failed calls are recorded (`ok=False`), so cost and latency figures are honest. Retries are configurable. | `api/airlock_api/llm.py`, `config.py` |
| The model's extraction code was brittle: guessed helper signatures, `.group(1)` on group-less regex, labels mid-line in two-column layouts, tax `VAT (19%) 1.926,60` read as 191926.60, IBAN lines read as line items, address lines read as the vendor name, the IBAN's last group dropped | The prompts now carry the exact helper API, a short skeleton and field rules. New helpers that never raise: `text.find`, `text.after`, `text.iso_date`, `money.amount_after`, `money.line_items` (rows kept only when qty × unit = amount) and `bank.find_iban` (checksum-validated). The model still writes the program (Pattern A). | `api/airlock_api/prompts.py`, `airlock_checks/text.py`, `money.py`, `bank.py` |
| Harmless nulls failed validation | The schema normalises `tax`/`notes`/`links` nulls and the case of `currency`. Over-long fields still fail on purpose. | `api/airlock_api/schemas.py` |

**Result: all 6 golden invoices reach the correct outcome on the live site.** That includes
approval → ERP posting → signed receipt, and phishing → EICAR download quarantined.

## 4. Other bugs fixed

| Problem | Fix | Where |
|---|---|---|
| `/api/metrics` "live" counters were global, though the page says "this workspace" | Scoped to the caller's workspace (with a test) | `api/airlock_api/main.py` |
| The phishing invoice kept a stale domain: cached seed PDFs were never rebuilt when `DOMAIN` changed | Rebuild when the manifest's domain ≠ `DOMAIN` (with a test) | `api/airlock_api/seed.py` |
| **Behind Caddy, all visitors shared one upload quota** (every request came from Caddy's IP) | uvicorn `--proxy-headers`. The API has no published port, so only Caddy can reach it. | `deploy/docker-compose.control.yml` |
| Caddy's ACME email was `you@example.com`, which Let's Encrypt rejects | Removed (the email is optional) | `deploy/Caddyfile` |
| `deploy/.env.*.example` files were missing, and `.gitignore` would have hidden them | Added both templates; un-ignored `.env.*.example` | `deploy/`, `.gitignore` |
| `RUNNER_BIND` in the example used the wrong format | `IP:8700` | `deploy/.env.sandbox.example` |
| `web/tsconfig.tsbuildinfo` was committed (build artefact) | Untracked; `*.tsbuildinfo` ignored | `.gitignore` |
| Drill evidence placed in `eval/results/` would have replaced the eval numbers on the Metrics page | Moved to `docs/evidence/` | |
| The eval aborted on a single slow status poll | Retries the poll | `eval/run.py` |
| The real domain is `beyonders.duckdns.org` (the docs said `beyonders-airlock`) | Example env updated. README/handoff still need updating. | `deploy/.env.control.example` |

Tests: **API 55 passing** (was 41), **runner 11 passing**, web build clean.

---

## 5. Set up on Vultr (not in the repo)

All in `ewr`. Budget cap $40 (approved). Spend on day 1 was well under $1.

- **VPC** `airlock-vpc` 10.10.0.0/24.
- **VM-1 `airlock-control`** (vc2-2c-4gb, Ubuntu 24.04): Caddy, API, web app.
  - Key-only SSH as user `airlock`; root and password login disabled.
  - Firewall allows 22/80/443 only.
- **VM-2 `airlock-sandbox`** (vc2-2c-4gb, Ubuntu 24.04): Docker + gVisor `runsc` (systrap, no KVM), runner and egress proxy.
  - **Not reachable from the internet.** SSH works only through VM-1.
  - The runner listens only on the VPC IP and needs a bearer token.
  - The only secret on the VM is the runner token.
- **Managed PostgreSQL 16**: VPC host, SSL on, trusted sources restricted to VM-1.
- **Object Storage**: private bucket, anonymous access denied.
- **Container Registry** `ewr.vultrcr.com/beyondersairlock`: created; images not pushed yet (VM-2 builds them itself).
- **Serverless Inference** subscription: all configured model IDs confirmed with `GET /v1/models`.
- **DuckDNS** `beyonders.duckdns.org` → VM-1. Let's Encrypt certificates for `app.`, `brightline.` and `filecourier-secure.`.

Secrets exist only in the gitignored `.env`, `deploy/.env.control` and `deploy/.env.sandbox` (chmod 600 on the VMs).
A scan of all git history found no committed credentials.

## 6. Later on 2026-11-04

### Live evaluation (first real numbers)
40 invoices through https://app.beyonders.duckdns.org with real models and real gVisor sandboxes.
Raw file: [`eval/results/2026-11-04-1310.json`](eval/results/2026-11-04-1310.json). The build is the one *before* commit `4f14b3e`.

| Metric | Result |
|---|---|
| Outcome accuracy | **85%** (34/40) |
| Attacks caught | **24/24** (phishing 4/4, injection 6/6, duplicate 6/6, bank change 6/6) |
| Benign links | 2/2 |
| Clean invoices passed | 10/16 (6 held or blocked: fail-safe, never paid) |
| False-positive rate | 33% (6/18 clean + benign) |
| Latency | p50 19 s, p95 60 s |
| Cost | $0.0048 per invoice |

An earlier eval attempt aborted after 11 invoices on a slow status poll in the eval *client*. `eval/run.py` now retries.
For the eval only, the upload limit on VM-1 was temporarily raised (`UPLOADS_PER_HOUR_PER_IP`) and then set back to 10.

### Repo changes after the first CHANGES.md
| Change | Where |
|---|---|
| README: live URL, a "Verified on the real stack" table, live eval numbers (replacing the mock "100%"), deploy gotchas, test count 55, honest wording on the registry and the phishing CPU loop | `README.md` |
| The Metrics page can now show eval results on the live site (results folder mounted into the API container; it wasn't in the image) | `deploy/docker-compose.control.yml` |
| Live eval results file | `eval/results/2026-11-04-1310.json` |
| This section | `CHANGES.md` |

## 7. Still open
- Deploy commit `4f14b3e` (IBAN/vendor fix) and re-run the eval to measure it.
- Update `handoff.md` for the `beyonders.duckdns.org` domain (README is done).
- Optionally push the sandbox images to the registry and pin them by registry digest.
- Snapshot both VMs before recording the demo video. Then the video, slides and cover image.
- The Vultr API key shown in a session log on 2026-11-04 has been rotated. Optionally restrict the new key's access list to known IPs.
