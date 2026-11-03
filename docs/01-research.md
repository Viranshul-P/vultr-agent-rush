# 01 · Research — Vultr: Agent Rush

> Researched 1 Nov 2026 from the lablab event page, live page, rule book, Vultr docs, the live model list, Vultr's blog, and the public team roster. Re-check anything marked ⚠️ at kickoff.

---

## 1. Hard facts and constraints

| Item | Finding | Source |
|---|---|---|
| Build window | Online, 3–8 Nov 2026 | event page |
| Kickoff | ⚠️ Live page says **15:00 UTC (20:30 IST)**; event page says 11:00 AM EST (16:00 UTC, 21:30 IST). Join at 20:30 IST. | live page / event page |
| **Deadline** | ⚠️ Live page: **8 Nov, 22:00 UTC = 9 Nov, 03:30 IST**. Event page: 6:00 PM EST = 23:00 UTC = 04:30 IST. **Plan to 03:30 IST.** The rule book adds a 5-minute grace period and nothing more. | live page, rule book |
| Team | 1–6 people (we're 3) | event page |
| Scale | ~1,850 registered builders, ~437 teams as of 1 Nov | live page |
| Prize pool | One shared ranking across both challenges: $5k + $3k credits / $3k + $1k / $1k + $1k | event page |
| Credits | $200 per person, gift code given at kickoff, fresh email required. **$600 total for the team.** | event page |
| GPUs | None. All model calls go through Serverless Inference. | event page |
| Submission | On lablab.ai: title, short/long description, tags, cover image (16:9), **video (MP4/MOV)**, **slides (PDF)**, **public GitHub repo**, demo platform, **app URL** | event page, rule book |
| README must cover | Vultr services used, backend/deployment architecture, the agent's use case and how it executes real tasks, plus (C1) a containment moment in the video | event page |
| Licence | "Original and MIT-compliant", so we ship an MIT LICENSE | event page |
| Judging checks | Judges look at the GitHub repo. Commits should be spread across the event window, not dumped in one final push. | lablab "How to win" guide |

### Challenge 1 (Blast Radius Zero): non-negotiables
- Backend on a Vultr VM, and the web app also deployed on Vultr.
- **Every agent LLM call goes through Vultr Serverless Inference** (`https://api.vultrinference.com/v1`, OpenAI-compatible).
- The agent does real work (writes and runs code, or drives a real browser) **inside an isolated sandbox**. Docker is strongly recommended.
- Containment rules: **process isolation**, **no secrets in the sandbox**, **time and memory caps on every run**, **sandbox reset or destroyed after each task**.
- Pattern A (code exec with error-retry loop) and/or Pattern B (Playwright in a container, screenshots, vision verification, **human approval before final actions**).
- The video must show **at least one containment moment**. lablab's announcement was titled *"Your agent has to try to break something on camera."*

### Challenge 2 (Future of Work)
Enterprise multi-step workflow (sales ops, finance, HR, support, procurement) on a Vultr VM backend. Serverless Inference is optional. It's ranked in the same prize pool as C1.

---

## 2. How judging actually works

There are four criteria, each scored **1–5** (rule book rubric):

| Criterion | What earns a 4–5 |
|---|---|
| **Presentation** | Problem, solution and value proposition in **under 5 min**. Videos **shorter than 3 min are scored down**. A 4 needs market analysis, revenue model and future plans. A 5 also needs a **competitive analysis**. |
| **Business value** | Clear market, large customer base, revenue path, scalability. |
| **Application of technology** | Demo video shows **all features**, the demo link **works smoothly**, and the GitHub code is real and well thought out. A 5 means the model use goes beyond expectations, not a chatbot wrapper. |
| **Originality** | An unconventional method or unexpected application. A copy of the example list scores 2. |

**Judges (from the event page):** senior engineers at Meta, Amazon, Walmart and Amex; a **Principal Engineer in Cloud & Network Security at Palo Alto Networks**; a **McKinsey management consultant**; a **Director at Prudential Financial**; PMs from Microsoft and Walmart; the CTO of NativelyAI; and founders.
→ Most of the panel is enterprise or finance, and at least one judge is a security specialist. A use case that touches money and security will land with both groups. A pure dev tool appeals to fewer of them.

---

## 3. What Vultr has rewarded before

**Agent Arena Hackathon (Vultr × Cerebral Valley, SF, 2026), all three winners** ([Vultr blog](https://blogs.vultr.com/agent-arena-hackathon-cerebral-valley-2026)):
1. **Nusa**: an agent that rewrites inference kernels for VX1 CPUs. *"Every attempt running in a throwaway microVM with no network"*, with a **measured result**: up to 2× faster decode.
2. **Skeleton Key**: turns websites with no API into APIs. *"Vultr is the entire control plane"*: Cloud Compute, **VPC, Container Registry, Object Storage**, Serverless Inference. Sandbox-verified operations, with personal data redacted.
3. **RL Forge**: paper → RL environment, with sandbox execution plus reward verification and **measured gains** (2/20 → 5/20, 3/20 → 7/20).

**AI Agent Olympics (lablab, Vultr track, May 2026):** 2nd place went to **PlutusAudit AI**: *"5 AI agents process any invoice in 45 seconds — detect fraud, classify under GAAP/IFRS, verify their own reasoning, tamper-proof audit trail."*

**Patterns that win with Vultr:**
- **Numbers.** Every winner quoted a measured outcome. Bring an eval with real metrics.
- **Breadth of Vultr services.** Using Vultr as the whole control plane (VPC, registry, object storage, API) scores better than one VM plus an API key.
- **Throwaway, network-less execution.** This is the property Vultr itself highlights.
- **Verification and audit trails.** "Prove it" outputs, not described outputs.
- **Finance plus fraud** has already placed in a Vultr track.

---

## 4. Technology research

### 4.1 Vultr Serverless Inference: models live on 1 Nov 2026
OpenAI-compatible API with tool calling via `tools` / `tool_choice`. ⚠️ The model list changes, so re-pull `GET /v1/models` at kickoff and keep model IDs in env vars.

| Use in an agent | Candidate model IDs | Notes |
|---|---|---|
| Planner / coder (tool calling) | `glm-5.3`, `glm-5.3-flash`, `deepseek-v4.1-flash-1017`, `minimax-m3.1-flash`, `qwen3.8-27b` | All support `tools`, `response_format`, `reasoning_effort`. `glm-5.3` is "post-trained for complex coding and long-horizon agentic work". Flash variants cost 5–10× less. |
| Vision verifier (screenshots) | `qwen3.8-flash-next`, `glm-5.3-flash`, `mimo-v2.6-pro`, `muse-glimmer-30b` | Image input plus tool calling |
| Safety / injection classifier | `nemotron-3.5-content-safety` | Multimodal moderation of prompts, images and responses |
| Calibrated yes/no decisions | `pplx-decider-v1.2`, `clef`, `clef-flash`, `d3` | "Returns calibrated answer probabilities for every question in a single read." Useful for risk scoring. ⚠️ API shape not yet verified. |
| Embeddings / rerank | `qwen3-embedding-4b`, `bge-reranker-v2-m3`, `vultron-retriever-*` | Fuzzy vendor matching, RAG |
| Speech (optional) | `whisper-large-v3-turbo`, `qwen3-tts-12hz-1.7b`, `chatterbox` | Voice input, narration |
| Image gen (cover art) | `z-image-turbo`, `moss-image` | Cover image (16:9) |

**Price:** roughly $0.01–$3.10 per million tokens depending on model (Vultr pricing page). An agent run of ~20k tokens costs well under one cent. **Inference cost is not a constraint.**

### 4.2 Sandboxing options

| Option | Isolation | Effort | Verdict |
|---|---|---|---|
| **Docker + hardening** (`--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, non-root, `--memory`, `--cpus`, `--pids-limit`, `--rm`) | Shared kernel | Low | Baseline. Officially "strongly recommended". |
| **Docker + gVisor (`--runtime=runsc`)** | User-space kernel intercepts syscalls | Low (apt install + `daemon.json`) | **Our primary choice.** Same Docker workflow with much stronger isolation, and a good talking point. |
| **Microsandbox** (microVM per sandbox, libkrun/KVM) | Separate kernel per sandbox | Medium. Needs `/dev/kvm`; Vultr's own guide runs it on **VX1** | Stretch upgrade. Using Vultr's own published guide earns credit with Vultr judges. Python SDK: `Sandbox.create(image, cpus, memory)`. |
| **Throwaway Vultr VM via API** | Full VM, destroyed after use | Medium. ~1–2 min boot | Stretch "maximum quarantine" tier for the highest-risk items. Shows the Vultr API in use. |
| E2B / OpenSandbox | Varies | Medium–high to self-host | Skip. Adds a dependency without improving the story. |

**Containment details worth knowing:**
- Vultr's **instance metadata service is at `169.254.169.254`**. A classic SSRF/exfiltration target, so block it explicitly and show it blocked.
- Running the sandbox on a **separate VM** from the app (reached only over **Vultr VPC**) makes "execution never touches the host or app runtime" literally true.
- Chromium under gVisor generally works but may need `--no-sandbox` / `--disable-dev-shm-usage`. The outer sandbox justifies that. ⚠️ Verify in the Day-1 spike.

### 4.3 Vultr services and budget

| Service | Use | Approx. cost for the event week |
|---|---|---|
| Cloud Compute (2 vCPU / 4 GB) | Control plane: web app + API | ~$5 |
| **VX1** (4 vCPU, KVM-capable) | Sandbox host | ~$0.24/hr → ~$40 if left on 24/7 |
| Serverless Inference | All LLM calls | <$20 |
| Object Storage | Uploads + evidence bundles | ~$6/mo minimum |
| Container Registry | Sandbox images | small |
| Managed PostgreSQL (optional) | App DB | ~$15/mo |
| VPC + Firewall Groups | Private runner network | free |

⚠️ **Judging can take 2–4 weeks after submission** (lablab history), and **the demo URL must stay live the whole time**. After submission, downsize to what the demo needs; we have ~$600 of credits.

---

## 5. Competitive landscape (public team roster, 1 Nov)

437 teams. From the ~80 team descriptions we read, the ideas fall into clusters:

| Cluster | Examples | Crowding |
|---|---|---|
| Generic "secure sandboxed agent platform" | Cage (8 containment drills + Ed25519 evidence), Zero Radius, Vulcan Shield, Ouroborous, AgentForge, ANSHIFT, NovaDev, KK | **Very high** |
| Picks straight from the example list | Self-Healing Runner (Sandbox Syndicate), Prove-It Code Reviewer (Blast Radius Zero BR), Site QA Sweep (V_Tech) | High |
| Browser task agents | Vex, quantaradotcv, IXIA (law-firm intake form filler), Do It With AI | Medium |
| Commerce / sales | JARVIS ProofOps (storefront QA with prompt-injection resistance), Kenitra (local-business sales), VultrNova (e-commerce listing), TechnoDone (sales desk) | Medium |
| Niche / vertical | Silicon Sage (Verilog/RTL verification), Team Rohit (healthcare), Hexacore (talent) | Low |
| **Finance / accounts payable / fraud** | **none seen** | **Empty** |

**Takeaways**
- Containment drills, evidence bundles and approval gates are **table stakes**. Strong rivals like Cage already plan them, so they can't be our differentiator.
- The open space is a **business vertical where containment is the product**, not a compliance checkbox. Finance/AP is uncontested in the roster and matches the judging panel.

---

## 6. What this means for our entry

1. **Pick Challenge 1** (the headline challenge, and where Vultr's requirements and story focus) **but give it Challenge-2-grade business value.** Most C1 teams will build dev tools.
2. **Make the containment moment come from the use case itself.** It should be something a real attacker would send, not a staged `rm -rf /`.
3. **Use both patterns** (A: code, B: browser) because both earn tech points.
4. **Use Vultr broadly:** separate sandbox VM, VPC, Container Registry, Object Storage, Serverless Inference with 3+ model types, and the API for a throwaway-VM tier.
5. **Ship an eval with numbers:** detection rate, false positives, cost and latency per task, drills passed.
6. **Deploy on Day 1.** A working public URL plus a 4–5 minute video plus a real repo is the floor for the "Application of technology" score.
7. **Submit by 21:00 IST on 8 Nov**, 6.5 hours before the earliest possible deadline.

---

## 7. Questions to ask in the kickoff Discord Q&A (3 Nov, 22:30 IST)
1. Is the deadline 22:00 UTC or 23:00 UTC? (The two pages disagree.)
2. Can design and planning done before kickoff be used, as long as product code is written during the event?
3. Is a sandbox running on a **separate Vultr VM** reached over VPC acceptable (or preferred) for "process isolation"?
4. How long must the demo URL stay live after submission?
5. Can a C1 project target an enterprise workflow (finance) without being judged as C2?
6. Are the decision models (`pplx-decider`, `clef`) supported for production use during the event?
