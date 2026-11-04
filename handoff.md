# Airlock — Handoff (Team Beyonders)

> Updated 4 Nov 2026. **Live on Vultr:** https://app.beyonders.duckdns.org (real Vultr models, real gVisor sandboxes).
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
| First live eval (40 invoices) | 85% outcome accuracy, 24/24 attacks caught, 33% false positives on clean invoices · [eval/results/2026-11-04-1310.json](eval/results/2026-11-04-1310.json) |
| Tests | API 66, runner 11, web build clean |

### Run it locally (mock LLM, no Vultr)
```bash
cd api && uv sync && uv run pytest -q        # 66 passed
cd runner && uv sync && uv run pytest -q     # 11 passed
cd web && npm install && npm run build       # builds clean
```
The full local stack command is in the README ("Run it locally").

## Left to do ⏳ (in order)
0. **Deploy the CHANGES.md §8 changes to the live VMs.** Needs SSH access (the original deploy key isn't available; a new key must be added through the Vultr console). Ship code with `git archive` and extract in place; keep the env files already on the VMs. VM-2: rebuild `py-sandbox` (the `text.after` fix lives in the image) and re-pin `IMAGE_PY`. VM-1: rebuild the API and web.
1. **Re-run the eval** on the varied-injection set (`python eval/generate.py --domain beyonders.duckdns.org`, then `eval/run.py --base https://app.beyonders.duckdns.org --note "<deployed commit>"`). It measures commit `4f14b3e` (IBAN/vendor fix) and the §8 changes. The run uploads 40 invoices: either raise `UPLOADS_PER_HOUR_PER_IP` on VM-1 for the run and set it back to 10, or leave it and let `run.py` wait out the limit (about 4 hours). Never quote a number the eval didn't produce.
1b. **Real model prices** in `api/airlock_api/pricing.py` (currently placeholders, so "cost per invoice" is an estimate). Take them from the Vultr console / pricing page.
2. **Snapshot both VMs** before recording the video, and write down how to roll back.
3. **Submission assets:** video (4:30 with the containment moments; plan in docs/03 §11.1 and the checklist in docs/04 Part 16), 10-slide PDF, 16:9 cover image, lablab form (drafts in docs/03 §11.4). Fill in the video/slides links and the containment timestamp at the top of README.md.
4. **Vultr billing alert** (console only).
5. Optional: push the sandbox images to the registry and pin `IMAGE_*` to registry digests.
6. Optional: restrict the (rotated) Vultr API key's access list to known IPs; add an ACME email to the Caddyfile for certificate expiry notices.
7. **Before submitting:** make the repo public, tag `v1.0-submission`, and have one teammate follow the setup docs from scratch.
8. **After submitting:** keep the demo live through judging (daily `/api/health` check). Don't touch production during the buffer.

## Secrets
Secrets live only in the gitignored root `.env`, `deploy/.env.control` (VM-1) and `deploy/.env.sandbox` (VM-2). Never commit, paste or screenshot them. The only secret on VM-2 is `RUNNER_TOKEN`. SSH to the VMs uses `~/.ssh/airlock_ed25519`; VM-2 is reached only through VM-1.

## Known limitations (by design)
- Locally, Pattern B (the browser) needs the VM, so link invoices HOLD via the R12 fail-safe in mock mode.
- The mock LLM is a regex parser; the real Vultr models parse messy invoices far better.
- The dev runner has **no isolation** and is gated behind `RUNNER_ALLOW_UNSAFE_DEV=1`. Real containment is gVisor on VM-2.
- Vultr Inference models are reasoning models: keep `LLM_REASONING_EFFORT` / `LLM_CODER_REASONING_EFFORT` set, or calls "think" for minutes and return nothing.
