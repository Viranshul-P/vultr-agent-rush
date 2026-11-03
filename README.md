# Airlock — a sandboxed accounts-payable agent

> **Team Beyonders** · Vultr: Agent Rush Hackathon · Challenge 1 (Blast Radius Zero)

**Airlock opens every invoice inside a disposable Vultr sandbox. A malicious invoice can fool the AI, but it can't reach your money, your secrets, or your servers.**

Accounts-payable teams open hundreds of untrusted invoices from strangers every day — exactly how invoice fraud and prompt-injection attacks get in. Business email compromise caused **$3.05B** in reported losses in 2025 (FBI IC3), and **76%** of organisations faced payments fraud in 2025 (AFP). As AP teams add AI agents, an invoice becomes a way to attack the agent itself. Airlock treats every invoice as hostile and does all the risky work — parsing, validating, opening links — inside throwaway sandboxes, with a human approving any payment.

- **Live demo:** https://app.beyonders-airlock.duckdns.org  *(set after deploy)*
- **Demo video:** _link_ · **Slides:** _link_
- **Containment moment in the video:** ~1:40

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
2. **Phishing pay-link** — a sandboxed browser opens a lookalike login page; the forced download is quarantined (never opened) and the CPU-burn script hits the cap; the container is destroyed → **QUARANTINE**.

---

## How Vultr powers it

| Vultr service | Role |
|---|---|
| **Cloud Compute (VM-1)** | Control plane: web app + API + policy + approvals |
| **Cloud Compute (VM-2)** | Isolated sandbox host (gVisor); holds **no secrets** |
| **Serverless Inference** | **Every** agent LLM call (`https://api.vultrinference.com/v1`): coder, planner, vision, safety |
| **VPC + Firewall Groups** | Private control↔sandbox link; runner never public |
| **Object Storage** | Uploads, screenshots, signed evidence receipts |
| **Container Registry** | Sandbox images, pinned by digest |
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
- **Proof** — 11 one-click **Red Team drills** (`/red-team`) run real attacks (host-escape, env dump, metadata SSRF, fork/memory bombs, exfiltration, browser→private-range) and check containment. Every invoice gets an **Ed25519-signed evidence receipt**.

**Dual-LLM design:** the model that reads the raw invoice has **no tools** (a successful injection has nothing to call); the model that writes the summary **never sees the raw document**; the policy engine, in plain code, owns every decision, and **no model can trigger a payment**.

---

## Run it locally (no Vultr, no API key, no Docker)

A mock LLM and an in-process **dev-only** runner let the whole pipeline run on a laptop. The dev runner is **not a sandbox** and refuses to start without `RUNNER_ALLOW_UNSAFE_DEV=1`.

```bash
# backend tests (policy, checks, runner, full end-to-end pipeline)
cd api && uv sync && uv run pytest -q          # 41 passing
cd ../runner && uv sync && uv run pytest -q     # 11 passing

# run the API with mock LLM + in-process runner, then open the web app
cd ../api
DATABASE_URL="sqlite:///../var/airlock.db" STORAGE_DIR=../var/store \
RUNNER_URL=inprocess RUNNER_TOKEN=$(python -c "print('x'*40)") RUNNER_ALLOW_UNSAFE_DEV=1 \
RUNS_ROOT="$PWD/../var/runs" LLM_MODE=mock DOMAIN=localhost \
PYTHONPATH="../sandbox-images/py-sandbox:../seed:../runner:." \
uv run uvicorn airlock_api.main:app --port 8000

cd ../web && npm install && npm run dev        # http://localhost:5173
```

## Deploy on Vultr
See [`deploy/`](deploy/) and the runbook in [`docs/04-build-guide.md`](docs/04-build-guide.md) (Part 2):
provision VM-1, VM-2, VPC, firewall, Object Storage, Container Registry, Managed PG; `deploy/setup-sandbox-vm.sh` installs Docker + gVisor; then `docker compose` with the two compose files. Free HTTPS via DuckDNS + Caddy.

## Evaluation
`eval/generate.py` builds a labelled, seed-aligned invoice set; `eval/run.py` scores a live instance and writes a JSON the **Metrics** page reads. Latest local run (mock LLM, browser disabled): core fraud classes (injection, duplicate, bank-change, clean) **100%**; link cases require the sandboxed browser on the VM.

## Repo layout
`api/` control plane · `runner/` sandbox runner · `sandbox-images/` gVisor images + `airlock_checks` · `egress-proxy/` · `demo-sites/` · `seed/` · `eval/` · `web/` · `deploy/` · `docs/` plans · `handoff.md`.

## Safety note
All vendors, invoices and demo sites are **fictional**. IBANs are standard documentation examples. The "malicious" demo content is inert: injections are harmless hidden text, the simulated suspicious page submits nowhere, the "download" is the standard EICAR anti-virus **test** string, and the CPU loop is bounded. Pages are clearly marked **SIMULATION**.

## License
MIT — see [LICENSE](LICENSE).
