# Airlock — Handoff (Team Beyonders)

> Updated 5 Nov 2026 (evening). **Live on Vultr:** https://app.beyonders.duckdns.org (real Vultr models, real gVisor sandboxes).
> Submit target: **Sun 8 Nov, 21:00 IST** (earliest deadline reading: Mon 9 Nov, 03:30 IST). Budget cap: $40.

Plans: [docs/01-research.md](docs/01-research.md) · [02-problem-statements.md](docs/02-problem-statements.md) · [03-implementation-plan.md](docs/03-implementation-plan.md) · [04-build-guide.md](docs/04-build-guide.md)
What changed while deploying, and what was set up on Vultr: [CHANGES.md](CHANGES.md).

## Decisions
- Project **Airlock**, Challenge 1 (Blast Radius Zero), Patterns A + B.
- **Domain:** `beyonders.duckdns.org` (free DuckDNS) + Caddy with Let's Encrypt. Hosts: `app.`, `brightline.` (benign vendor portal), `filecourier-secure.` (inert phishing SIMULATION).
- **Sandbox VM:** regular Cloud Compute 2 vCPU/4 GB + **gVisor** (`runsc`, systrap platform, no KVM needed). VX1/Microsandbox dropped.
- **Frontend:** Vite + React + TS (hand-rolled CSS), built static and served by Caddy.
- **Sandbox images** are built on VM-2 and pinned by digest. The Container Registry exists but the images aren't pushed (optional).
- **Skipped on purpose:** login/per-user quotas (judges must click "Process inbox" without signing up), two buckets (the code uses one), full backups (seeded demo data only).

## Status

### Verified on the real stack ✅
| Area | Result |
|---|---|
| Infra | VPC, VM-1 `airlock-control`, VM-2 `airlock-sandbox` (no public exposure), Managed PG, Object Storage, Serverless Inference: all provisioned and hardened (details in CHANGES.md §5) |
| gVisor drills D1–D10b | **11/11 pass** on VM-2 · [docs/evidence/drills-vultr-2026-11-04.json](docs/evidence/drills-vultr-2026-11-04.json) |
| 6 golden invoices on the live URL | **6/6 correct**, incl. approve → ERP posting → signed receipt, and phishing → EICAR download quarantined |
| Latest live eval (40 invoices, build `d6fb6d3`, varied injections) | **40/40** correct, 22/22 attacks, 0% false positives, 0 timeouts, p50 20 s / p95 36 s, $0.0094 per invoice at real prices · [eval/results/2026-11-05-1527.json](eval/results/2026-11-05-1527.json). Earlier: 92.5% (20:53), 85% (13:10) |
| Tests | API 72, runner 11, web build clean |

### Run it locally (mock LLM, no Vultr)
```bash
cd api && uv sync && uv run pytest -q        # 74 passed
cd runner && uv sync && uv run pytest -q     # 11 passed
cd web && npm install && npm run build       # builds clean
```
The full local stack command is in the README ("Run it locally").

## Left to do ⏳ (in order)
0. ✅ CHANGES.md §8 deployed to the live VMs (drills 11/11, golden 5/6; see §8 for #4 and rollback).
   Invoice #4 (bank change): fixed on 5 Nov by raising the injection classifier threshold to 0.8 (CHANGES.md §11); now BLOCKED by R3/R4.
1. ✅ Latency fixed and measured (CHANGES.md §10): PR #3 deployed to VM-1 on 5 Nov, eval 40/40, p95 36 s. Re-run the eval with `eval/run.py --base https://app.beyonders.duckdns.org --note "<deployed commit>"` (`--max-cost-usd` / `--max-minutes` cap a run). Never quote a number the eval didn't produce.
1b. ✅ Real model prices: `pricing.py` uses Vultr's published flat rate, $0.55 / $2.75 per 1M input / output tokens (docs page updated 26 Oct 2026). Costs are stored when each call is made, so eval files before this change used the old placeholder prices and understate cost.
1c. ✅ Live click-through fixes (CHANGES.md §11, PR #4) and parallel "Process inbox" (§12, PR #5): one visitor's inbox ~1 min, 5 visitors at once 30/30 correct. README has models, limitations and team sections.
   **Deploying:** auto mode blocks Claude from running deploys on the VMs; it uploads the package to `~/stage/` and a teammate runs `ssh ... 'bash ~/stage/airlock-remote.sh'`. Web builds must replace the *contents* of `web/dist` (Caddy bind-mounts the directory; renaming it needs a Caddy restart).
2. **Snapshot both VMs** before recording the video, and write down how to roll back.
3. **Submission assets:** video (4:30 with the containment moments; plan in docs/03 §11.1 and the checklist in docs/04 Part 16), 10-slide PDF, 16:9 cover image, lablab form (drafts in docs/03 §11.4). Fill in the video/slides links and the containment timestamp at the top of README.md.
4. **Vultr billing alert** (console only).
5. Optional: push the sandbox images to the registry and pin `IMAGE_*` to registry digests.
6. Optional: restrict the (rotated) Vultr API key's access list to known IPs; add an ACME email to the Caddyfile for certificate expiry notices.
7. **Before submitting:** make the repo public, tag `v1.0-submission`, and have one teammate follow the setup docs from scratch.
8. **After submitting:** keep the demo live through judging (daily `/api/health` check). Don't touch production during the buffer.

## Secrets
Secrets live only in the gitignored root `.env`, `deploy/.env.control` (VM-1) and `deploy/.env.sandbox` (VM-2). Never commit, paste or screenshot them. The only secret on VM-2 is `RUNNER_TOKEN`. SSH to the VMs uses `~/.ssh/airlock_ed25519` as user `airlock` (two keys are authorized: `airlock-deploy` and `airlock-viranshul-laptop`); VM-2 is reached only through VM-1 (`ProxyJump`).

## Known limitations (by design)
- Locally, Pattern B (the browser) needs the VM, so link invoices HOLD via the R12 fail-safe in mock mode.
- The mock LLM is a regex parser; the real Vultr models parse messy invoices far better.
- The dev runner has **no isolation** and is gated behind `RUNNER_ALLOW_UNSAFE_DEV=1`. Real containment is gVisor on VM-2.
- Vultr Inference models are reasoning models: keep `LLM_REASONING_EFFORT` / `LLM_CODER_REASONING_EFFORT` set, or calls "think" for minutes and return nothing.
