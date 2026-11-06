# Airlock — a sandboxed accounts-payable agent

> **Team Beyonders** · Vultr: Agent Rush Hackathon · Challenge 1 (Blast Radius Zero)

**Airlock opens every invoice inside a disposable Vultr sandbox. A malicious invoice can fool the AI, but it can't reach your money, your secrets, or your servers.**

Accounts-payable teams open hundreds of untrusted invoices from strangers every day — exactly how invoice fraud and prompt-injection attacks get in. Business email compromise caused **$3.05B** in reported losses in 2025 (FBI IC3), and **76%** of organisations faced payments fraud in 2025 (AFP). As AP teams add AI agents, an invoice becomes a way to attack the agent itself. Airlock treats every invoice as hostile and does all the risky work — parsing, validating, opening links — inside throwaway sandboxes, with a human approving any payment.

- **Live demo:** https://app.beyonders.duckdns.org. Open it and click **Process inbox** (no sign-up; every visitor gets their own workspace).
- **Demo video:** _link_ · **Slides:** _link_ · **Submission kit:** [docs/submission](docs/submission/README.md)
- **Containment moments in the video:** 1:49 (prompt injection) and 2:14 (phishing link)

---

## What it does (real executed work, not described)

| Step | What happens | Where |
|---|---|---|
| Scan | A fixed program reads the PDF and flags hidden/white text | sandbox |
| Extract (**Pattern A**) | The model *writes Python*; it runs in the sandbox; errors feed back for up to 3 retries → typed `InvoiceFields` | sandbox |
| Validate | Totals, IBAN/ABA checksum, 3-way match (PO + goods receipt), duplicate, sender-domain lookalike | sandbox + control plane |
| Inspect links (**Pattern B**) | A sandboxed Playwright browser opens any pay-link behind an egress proxy; a vision model + rules judge it | sandbox |
| Decide | A **deterministic policy engine (no LLM)** sets the outcome | control plane |
| Approve | A human must click before anything posts to the ERP | control plane |

Outcomes: **CLEAR** → await approval → **POSTED** · **HOLD** · **BLOCK** · **QUARANTINE**.

### Two containment moments (from the use case itself)
1. **Prompt-injection invoice** — hidden white text tells the AI to exfiltrate `os.environ` and auto-approve. Even when the model is fooled into writing that code, the sandbox has **no env vars and no network**, the attempt is logged, and the approval tool is unreachable → **QUARANTINE, blast radius 0**.
2. **Phishing pay-link**: a sandboxed browser opens a lookalike login page and the vision model flags the credential harvest. The forced download is quarantined and hashed, never opened. Its sha256 `275a021b…fd0f` is the EICAR test file. The page's CPU loop runs under the 1-CPU cap, and the container is destroyed after the run → **QUARANTINE**.

---

## How Vultr powers it

| Vultr service | Role |
|---|---|
| **Cloud Compute (VM-1)** | Control plane: web app + API + policy + approvals |
| **Cloud Compute (VM-2)** | Isolated sandbox host (gVisor); holds **no secrets** |
| **Serverless Inference** | **Every** agent LLM call (`https://api.vultrinference.com/v1`): coder, planner, vision, safety |
| **VPC + Firewall Groups** | Private control↔sandbox link; runner never public |
| **Object Storage** | Uploads, screenshots, signed evidence receipts |
| **Container Registry** | Private registry for sandbox images (created; the current deploy builds the images on VM-2 and pins them by digest) |
| **Managed PostgreSQL** | Application data |

### Architecture
```
Judge/clerk ──HTTPS──> VM-1 (Caddy, web, API, policy, approvals, evidence)
                          │  Serverless Inference (LLM)   Object Storage   Managed PG
                          │  VPC (only VM-1 → VM-2:8700, bearer token)
                          ▼
                        VM-2  runner ──> gVisor sandboxes
                          ├─ code:    --network none, read-only, no env, caps dropped, mem/cpu/pid/time caps, --rm
                          └─ browser: internal network → egress proxy (denies private ranges incl. 169.254.169.254, logs all)
```

### Containment (how each rule is met, and proved)
- **Process isolation** — gVisor user-space kernel on a separate VM; non-root; `cap-drop ALL`; read-only rootfs; no docker socket in sandboxes.
- **Secret hygiene** — zero env vars passed; **no API keys exist on the sandbox VM** (LLM calls happen only on VM-1).
- **Resource limits** — memory, CPU, pids, output and wall-clock caps on every run.
- **Lifecycle** — one container per run, destroyed after; a sweeper kills orphans.
- **Proof**: 11 one-click **Red Team drills** (`/red-team`) run real attacks (host escape, env dump, metadata SSRF, fork and memory bombs, exfiltration, browser → private range) and check containment. **All 11 pass under gVisor on the Vultr sandbox VM.** Raw results are in [`docs/evidence/drills-vultr-2026-11-04.json`](docs/evidence/drills-vultr-2026-11-04.json). Every invoice gets an **Ed25519-signed evidence receipt**.

### Verified on the real stack (2026-11-04/05)
| Check | Result |
|---|---|
| gVisor on Vultr Cloud Compute | `runsc` works without KVM (systrap platform); the kernel inside the sandbox is `4.19.0-gvisor` |
| Red Team drills D1–D10b | **11/11 pass** (fork bomb stopped at 63 processes, memory bomb OOM-killed, metadata and private IPs denied by the proxy) |
| Chromium inside gVisor | Loads pages through the egress proxy and returns screenshots |
| 6 golden invoices on the live URL | **6/6 correct outcome**; every sandbox run on gVisor; blast radius 0 |
| Approval gate | Approve → posted to ERP; approving twice or approving an unprocessed invoice → refused (409) |
| Evidence receipts | sha256 and Ed25519 signature verify |
| Isolation between visitors | Another visitor's invoice → 404 |
| VM-2 exposure | Not reachable from the internet; runner bound to the VPC only, token required |
| Several judges at once (5 Nov) | 5 visitors clicking Process inbox together: 30/30 correct, no errors; one visitor's six invoices finish in about 1 minute |

**Dual-LLM design:** the model that reads the raw invoice has **no tools** (a successful injection has nothing to call); the model that writes the summary **never sees the raw document**; the policy engine, in plain code, owns every decision, and **no model can trigger a payment**.

---

## Run it locally (no Vultr, no API key, no Docker)

A mock LLM and an in-process **dev-only** runner let the whole pipeline run on a laptop. The dev runner is **not a sandbox** and refuses to start without `RUNNER_ALLOW_UNSAFE_DEV=1`.

```bash
# backend tests (policy, checks, runner, full end-to-end pipeline)
cd api && uv sync && uv run pytest -q          # 76 passing
cd ../runner && uv sync && uv run pytest -q     # 11 passing

# run the API with mock LLM + in-process runner, then open the web app
cd ../api
DATABASE_URL="sqlite:///../var/airlock.db" STORAGE_DIR=../var/store \
RUNNER_URL=inprocess RUNNER_TOKEN=$(python -c "print('x'*40)") RUNNER_ALLOW_UNSAFE_DEV=1 \
RUNS_ROOT="$PWD/../var/runs" LLM_MODE=mock DOMAIN=localhost \
PYTHONPATH="../sandbox-images/py-sandbox:../seed:../runner:." \
uv run uvicorn airlock_api.main:app --port 8000

# Windows (Git Bash): separate PYTHONPATH entries with ';' instead of ':'

cd ../web && npm install && npm run dev        # http://localhost:5173
# or develop the UI against the live API: API_TARGET=https://app.beyonders.duckdns.org npm run dev
```

## Deploy on Vultr
See [`deploy/`](deploy/) and the runbook in [`docs/04-build-guide.md`](docs/04-build-guide.md) (Part 2):
provision VM-1, VM-2, VPC, firewall, Object Storage, Container Registry, Managed PG; `deploy/setup-sandbox-vm.sh` installs Docker + gVisor; then `docker compose` with the two compose files. Free HTTPS via DuckDNS + Caddy.

- **Config:** copy `deploy/.env.control.example` → `deploy/.env.control` (VM-1) and `deploy/.env.sandbox.example` → `deploy/.env.sandbox` (VM-2). Both filled files are gitignored, so never commit them. Our domain is `beyonders.duckdns.org`.
- **Firewall groups:** a Vultr firewall group with **no rules allows everything**. VM-2's group must contain at least one narrow rule (we allow SSH only from VM-1), or it is publicly reachable.
- **Deploying from Windows:** ship code with `git -c core.autocrlf=false archive` (CRLF breaks the shell scripts) and extract it **in place**. Replacing the `~/airlock` folder leaves Caddy's mounts pointing at a deleted directory, and the demo pages return 404.
- **Vultr Inference models are reasoning models.** Keep `LLM_REASONING_EFFORT` / `LLM_CODER_REASONING_EFFORT` set. Unbounded, a call "thinks" for minutes and returns nothing.
- **gVisor without KVM:** the process cap is enforced inside the sandbox (`RLIMIT_NPROC`), and the browser reaches the egress proxy by fixed IP (`172.30.0.10`), because Docker DNS doesn't work inside gVisor.

All changes made while deploying are listed in [`CHANGES.md`](CHANGES.md).

## Evaluation
`eval/generate.py` builds a labelled, seed-aligned invoice set; `eval/run.py` scores a live instance and writes a JSON the **Metrics** page reads.

**Latest live run, 2026-11-05 15:27 IST**: 40 invoices through https://app.beyonders.duckdns.org, real Vultr models, real gVisor sandboxes, build `d6fb6d3`. Injections are hidden 5 different ways (white text, tiny text, off-page text, PDF metadata, a visible note). Raw output: [`eval/results/2026-11-05-1527.json`](eval/results/2026-11-05-1527.json).

| Metric | Latest (15:27) | Previous (20:53, build `bdbdd69`) | First (13:10) |
|---|---|---|---|
| Outcome accuracy | **100%** (40/40) | 92.5% (37/40) | 85% (34/40) |
| Attacks caught | **22/22**: injection 6/6, phishing 4/4, duplicate 6/6, bank change 6/6 | 21/22 | 22/22 (white-text injections only) |
| Benign links passed | 2/2 | 2/2 | 2/2 |
| Clean invoices passed | **16/16** | 14/16 | 10/16 |
| False-positive rate (clean + benign) | **0%** (0/18) | 11% | 33% |
| Timeouts | **0** | 3 (eval waited 120 s) | 0 |
| Precision of every outcome | 100% | 100% | not computed |
| Security drills (gVisor) | 11/11 | 11/11 | 11/11 |
| Latency per invoice | **p50 20 s · p95 36 s** (slowest 41 s) | p50 34 s · p95 121 s | p50 19 s · p95 60 s |
| LLM cost per invoice | **$0.0094** at Vultr's published rate ($0.55 / $2.75 per 1M input / output tokens) | $0.0040 (placeholder prices) | $0.0048 (placeholder prices) |

Per model call in the latest run (all 206 calls succeeded): safety p50 0.7 s, classifier 1.3 s, planner 1.8 s, extraction code 2.0 s, vision 2.5 s, validation code 7.0 s (max 12.8 s).

What changed for the latest run: the safety model and injection classifier now run alongside extraction, and a stuck model call goes straight to the fallback model instead of being retried on the same model first. No call failed or timed out in this run, so the failover path itself wasn't exercised; part of the latency gain may also be lighter load on the inference service. 40/40 is one run of 40 invoices, not a guarantee.

The first run's false positives were extraction slips on clean invoices, fixed since then (checksum-validated `bank.find_iban`, vendor-name guidance, bilingual labels in `text.after`). Its attack count was written as "24/24" in earlier docs; the set has 22 attack invoices. The earlier "100%" figure came from a mock-LLM local run and is not a live result.

## Models (all via Vultr Serverless Inference)

| Role | Model | Why |
|---|---|---|
| Extraction and validation code (Pattern A) | `glm-5.3` | The larger GLM model, used where correctness matters most: it writes the programs that run in the sandbox. Runs at `reasoning_effort=medium` with a 14k-token cap, so it reasons enough to write working parsers without stalling |
| Decision summary, injection classifier | `glm-5.3-flash` | Short structured JSON answers; fast (p50 1–2 s) |
| Phishing-page vision verdict (Pattern B) | `qwen3.8-flash-next` | Multimodal: reads the screenshots the sandboxed browser takes |
| Content-safety check | `nemotron-3.5-content-safety` | Purpose-built safety classifier; p50 0.7 s |
| Fallback for every role | `deepseek-v4.1-flash-1017` | A different model family, so one model's outage or stall doesn't stop the pipeline |

Every model is set by an env var (`MODEL_*`), so swapping one is config only. A stuck call fails over to the fallback after 45 s (short calls) or 150 s (code and vision), and every call, including failed ones, is logged with its tokens, cost and latency. The invoice API exposes these per-call timings, without prompts or outputs. Vendor matching uses deterministic fuzzy string matching, not a model.

## Known limitations
- **Detection is probabilistic; containment is not.** A cleverly written injection could get past the hidden-text heuristic, the safety model and the classifier (threshold 0.8). If it does, the model that reads it still has no tools, no network and no secrets, and the deterministic policy engine and a human make every payment decision.
- **Capacity:** one sandbox VM (2 vCPU / 4 GB). Up to 6 invoices are processed at once across all visitors; more visitors queue and see **Queued…**. Measured: 5 visitors at once, 30/30 correct, no errors, slowest inbox 186 s.
- **No sign-in, by design** (judges must be able to click straight in). Each visitor gets an isolated workspace by cookie; uploads are limited to 10 per hour per IP.
- **The sandboxed validation is advisory.** The model-written checks run in the sandbox for transparency, but the control plane recomputes every check authoritatively. When the two differ, the timeline shows a "disagreement" warning; the decision always uses the control plane's result.
- **Egress proxy:** blocks private, link-local and cloud-metadata addresses and logs every request. A DNS-rebinding window between its check and its connect remains; the browser container has no other route out, and the sandbox VM holds no secrets.
- **Costs** use Vultr's published flat rate ($0.55 / $2.75 per 1M input / output tokens) on real token counts.
- **Sandbox images** are built on the sandbox VM and pinned by digest; the Container Registry exists but isn't used by the live deploy.
- **Demo only:** fictional vendors and invoices, a mock ERP, no real payments. Locally, the mock LLM is a regex parser and the dev runner has no isolation (gated behind `RUNNER_ALLOW_UNSAFE_DEV=1`).

## Team Beyonders
| Member | GitHub |
|---|---|
| Viranshul | Viranshul-P |
| Kuldeep | Kuldeeep18 |
| Priyanshu Doshi | Priyanshu-byte-coder |

Built during the Vultr Agent Rush hackathon (Nov 2026) with Claude Code.

## Repo layout
`api/` control plane · `runner/` sandbox runner · `sandbox-images/` gVisor images + `airlock_checks` · `egress-proxy/` · `demo-sites/` · `seed/` · `eval/` · `web/` · `deploy/` · `docs/` plans · `handoff.md`.

## Safety note
All vendors, invoices and demo sites are **fictional**. IBANs are standard documentation examples. The "malicious" demo content is inert: injections are harmless hidden text, the simulated suspicious page submits nowhere, the "download" is the standard EICAR anti-virus **test** string, and the CPU loop is bounded. Pages are clearly marked **SIMULATION**.

## License
MIT — see [LICENSE](LICENSE).
