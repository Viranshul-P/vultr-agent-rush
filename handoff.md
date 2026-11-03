# Airlock — Handoff (Team Beyonders)

> Updated 1 Nov 2026. **Nothing is committed** (hackathon starts 3 Nov; commit during the event). The whole backend + frontend works locally with no Vultr account, via a mock LLM and a dev-only in-process runner.

Plans: [docs/01-research.md](docs/01-research.md) · [02-problem-statements.md](docs/02-problem-statements.md) · [03-implementation-plan.md](docs/03-implementation-plan.md) · [04-build-guide.md](docs/04-build-guide.md)

## Decisions
- Project **Airlock**, Challenge 1. **Zero cash cost:** runs on Vultr credits only (each member's own $200 account).
- **HTTPS:** free DuckDNS subdomain + Caddy. No domain purchase.
- **Sandbox VM:** regular Cloud Compute 2 vCPU/4 GB + **gVisor** (needs no KVM). VX1/Microsandbox dropped.
- **Frontend:** Vite + React + TS (hand-rolled CSS), built static and served by Caddy.

## Status: working end to end (locally, mock mode)
```bash
cd api && uv sync && uv run pytest -q        # 41 passed (incl. full pipeline e2e)
cd runner && uv sync && uv run pytest -q     # 11 passed
cd web && npm install && npm run build       # builds clean
```
Run the stack locally (mock LLM + in-process dev runner) — see README “Run it locally”. All 6 golden invoices reach the right outcome except the 2 that need the **sandboxed browser** (phishing/benign link), which only runs on the Vultr VM.

### Done ✅
| Area | Where | Notes |
|---|---|---|
| Sandbox helper lib | `sandbox-images/py-sandbox/airlock_checks/` | money/bank/domains/text/pdf/scan; unit-tested |
| py-sandbox + browser images, egress proxy | `sandbox-images/*`, `egress-proxy/` | Dockerfiles + harness + mitmproxy addon written; **built/run only on VM** |
| Seed + invoice generator | `seed/` | 4 vendors, 6 POs, ERP history, 6 golden PDFs |
| Schemas | `api/airlock_api/schemas.py` | |
| **Policy engine** | `api/airlock_api/policy.py` | R1–R12, deterministic, recomputes every check; 33 unit tests |
| LLM client (+mock) | `api/airlock_api/llm.py` | quarantined/privileged split; Vultr OpenAI-compatible; mock for keyless dev |
| Detectors + static scan | `api/airlock_api/detectors.py` | hidden text, keywords, safety model, classifier, AST scan |
| Orchestrator | `api/airlock_api/orchestrator.py` | full state machine, retries, blast-radius, SSE events |
| Evidence receipts | `api/airlock_api/evidence.py` | Ed25519 sign + verify, Object Storage |
| Runner | `runner/airlock_runner/` | docker+gVisor backend; dev-unsafe backend; 11 drills; 11 tests |
| API | `api/airlock_api/main.py` | all routes (inbox, SSE, approval, runs, receipts, drills, metrics, ERP, health) |
| Web app | `web/` | inbox, invoice timeline, run drawer, containment panel, red-team, metrics, receipt, ERP, about |
| Demo sites | `demo-sites/` | benign vendor portal + inert SIMULATION suspicious page (EICAR test string) |
| Eval | `eval/` | seed-aligned generator + scorer; a sample result is in `eval/results/` |
| Deploy | `deploy/`, `api/Dockerfile`, `runner/Dockerfile`, `.github/workflows/ci.yml` | compose ×2, Caddyfile, env examples, VM setup script, CI + LLM-endpoint guard |

### Left to do ⏳ (all on the Vultr VMs, during the event)
1. **Provision** VM-1, VM-2, VPC, firewall, Object Storage, Container Registry, Managed PG (docs/04 Part 2). Fill `deploy/.env.control` and `.env.sandbox` from the `.example` files.
2. **Build + push** the two sandbox images to Container Registry; put their `@sha256:` digests in `.env.sandbox`.
3. **Verify on VM-2** (the only things untestable on this laptop):
   - `docker run --rm --runtime=runsc hello-world`
   - drills D1–D10 actually pass under gVisor (pids cap, OOM detect, metadata blocked, exfil blocked)
   - Playwright Chromium runs under runsc through the egress proxy; screenshots return; EICAR download quarantined; CPU cap observed
4. **Confirm model IDs** at `GET /v1/models` at kickoff; adjust `MODEL_*` if any changed. Set `LLM_MODE=vultr`.
5. **Deploy** both compose files; point DuckDNS A-records at VM-1; Caddy gets HTTPS automatically.
6. **Run the real eval** (`eval/run.py --base https://app.<domain>`) to get the numbers for slides/video. Never quote a number the eval didn't produce.
7. **Submission assets:** video (4:30, containment moment), slides (PDF), cover image (16:9), lablab form. Drafts in docs/03 Part 11.

## What I need from you (user actions)
- [ ] Each member: own Vultr account (fresh email); redeem the $200 gift code at kickoff.
- [ ] Create a DuckDNS subdomain (e.g. `beyonders-airlock`) + 2 sub-hosts (`brightline.`, `filecourier-secure.`); keep the token out of the repo.
- [ ] At kickoff: create a Serverless Inference subscription; put the key in `deploy/.env.control` only.
- [ ] Decide when to make the first commit (plan: during the event, spread across days — judges check history).

## Known local limitations (by design)
- Browser/Pattern B needs the VM (no Playwright/Docker here) → link invoices HOLD locally via the R12 fail-safe.
- Mock LLM is a regex parser; the real Vultr models parse messy invoices far better.
- Dev runner has **no isolation** and is gated behind `RUNNER_ALLOW_UNSAFE_DEV=1`; real containment is gVisor on VM-2.
