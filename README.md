# Vultr: Agent Rush Hackathon — Team Beyonders

> **Status:** Starts 3 Nov 2026 · **Submissions close 8 Nov 2026, 6:00 PM EST = 9 Nov 2026, 4:30 AM IST**
> Info collected 1 Nov 2026 from the lablab.ai event page. Confirm the final schedule on the [live page](https://lablab.ai/ai-hackathons/vultr-hackathon/live).

---

## Team

| Member | GitHub |
|---|---|
| Viranshul | [@Viranshul-P](https://github.com/Viranshul-P) |
| Priyanshu Doshi | [@Priyanshu-byte-coder](https://github.com/Priyanshu-byte-coder) |
| Kuldeep Goklani | [@Kuldeeep18](https://github.com/Kuldeeep18) |

---

## Quick links

| What | Link |
|---|---|
| Event page | https://lablab.ai/ai-hackathons/vultr-hackathon |
| Live page (schedule/deadline) | https://lablab.ai/ai-hackathons/vultr-hackathon/live |
| lablab Discord | https://discord.gg/lablabai |
| lablab rule book | https://lablab.ai/hackathon-rules |
| Hackathon guidelines | https://lablab.ai/ai-articles/hackathon-guidelines |
| Getting started guide | https://lablab.ai/getting-started-guide |
| Vultr Community showcase (optional) | https://community.vultr.com/e/vultr-agent-rush-hackathon |
| Twitch | https://www.twitch.tv/lablabai |

---

## About

**"Build AI agents that do real work, safely sandboxed on Vultr."**

- **Organisers:** lablab.ai × Vultr (with NativelyAI)
- **Format:** Hybrid. Online build **3–8 Nov 2026**, plus an optional on-site day on **8 Nov** at Pierpont Place, 163 W Pierpont Ave, Salt Lake City, UT (travel not covered).
- **Team size:** 1–6
- **Cost:** Free. Open to all experience levels.
- **Submission:** **Must be submitted on lablab.ai** to be judged. Vultr Community is optional extra exposure.
- **Originality:** Submissions must be original and MIT-compliant. Prize payout can take up to 90 days.

---

## Schedule

| Event | EST | IST |
|---|---|---|
| Kick-off | Tue 3 Nov, 11:00 AM | Tue 3 Nov, 9:30 PM |
| Discord Q&A | Tue 3 Nov, 12:00 PM | Tue 3 Nov, 10:30 PM |
| On-site doors open (SLC) | Sun 8 Nov, 11:00 AM | Sun 8 Nov, 9:30 PM |
| Welcoming remarks (on-site) | Sun 8 Nov, 11:30 AM | Sun 8 Nov, 10:00 PM |
| **End of submissions** | **Sun 8 Nov, 6:00 PM** | **Mon 9 Nov, 4:30 AM** |
| On-site doors close | Sun 8 Nov, 8:00 PM | Mon 9 Nov, 6:30 AM |

---

## Vultr credits ($200 per participant)

1. Register at https://www.vultr.com/register/ with an email that has **never been used for a Vultr account**.
2. Verify the email.
3. At kickoff, open https://console.vultr.com/billing/?promo=HACKATHON, enter the **gift code** shared at kickoff, and click **Apply Gift Code**.
4. Check that the account shows **$200.00 Remaining Credit**.
5. Credits cover Compute Instances, Managed Databases, Kubernetes, and other Vultr services. Add a payment method if we want to keep deployments running after the event.

> ⚠️ **No Vultr GPUs for this event.**

---

## Challenges (pick one)

### 01 · Blast Radius Zero
Build a **web-based agent that does real work** (writes and runs code, or drives a real browser) with **every action inside an isolated sandbox on Vultr**. The system acts as a central control layer: it plans a task, sends it to an isolated execution environment, and returns verifiable output.

> "An agent that only chats is a demo; an agent that executes safely is a product."

**Required tech:** Vultr VM backend · Web app on Vultr · **Vultr Serverless Inference for ALL agent LLM calls** · Isolated sandbox (Docker strongly recommended)

**Execution patterns (build one or both):**
- **Pattern A: Sandboxed code execution.** User asks → model writes code → code runs in a container → real output returns → model explains. Errors feed back for retries.
- **Pattern B: Sandboxed browser use.** User gives a goal → model plans → Playwright runs in a container → screenshots return → vision model verifies → **human approval before final actions**.

**Containment rules:**
- **Process isolation:** Execution never touches the host or app runtime.
- **Secret hygiene:** No API keys or credentials inside the sandbox.
- **Resource limits:** Time and memory caps on every run.
- **Lifecycle discipline:** Reset or destroy the environment after each task.

**Example directions:** CSV Analyst · Prove-It Code Reviewer · Chart Anything · File Fixer · Self-Healing Runner · Comparison Shopper · Form Filler · Site QA Sweep · Research with Receipts · Page Watcher

**Submission expectations:** GitHub repo with setup docs · Vultr VM backend deployment · public demo URL · recorded demo video · clear architecture and use-case explanation · **at least one containment moment shown in the video**

### 02 · Powering the Future of Work
Build and deploy an **enterprise AI solution** that coordinates realistic multi-step workflows. It should be a real platform or operational workflow, not a one-off demo.

**Required tech:** Vultr VM backend · Web deployment on Vultr · (Serverless Inference optional)

**Focus areas:**
- **Sales Ops:** qualify leads, research prospects, update CRM, draft outreach, follow up
- **Finance & Accounting:** process invoices, reconcile transactions, flag anomalies, payment follow-ups
- **HR & Recruitment:** screen candidates, schedule interviews, onboarding, employee workflows
- **Customer Support:** resolve tickets across systems, investigate, act, escalate to humans
- **Procurement:** monitor needs, compare vendors, request quotes, track orders, chase delays

**Product expectations:** accessible from a public web browser · real product-style UX with clear user flows · Vultr as the central backend for planning, workflows, and operations · platform thinking

---

## What to submit (on lablab.ai)

| Section | Items |
|---|---|
| 📋 Basic info | Project title · Short description · Long description · Technology & category tags |
| 📸 Presentation | Cover image · **Video presentation** · **Slide presentation** |
| 💻 Hosting & repo | **Public GitHub repository** · Demo application platform · **Application URL** |

**Vultr-specific README requirements** (no separate report needed):
- Which Vultr services and infrastructure we used
- Backend/deployment architecture and how Vultr powers it
- The agent's use case and **how it executes real tasks**
- (Challenge 1) Demo video shows **at least one containment moment**

> ⚠️ This repo is **private** for now. Make it **public** before submitting.

---

## Judging criteria
1. **Application of Technology:** How well the chosen model(s) are integrated
2. **Presentation:** Clarity and effectiveness of the pitch
3. **Business Value:** Impact and practical value for business areas
4. **Originality:** Uniqueness and creativity, including demonstrated behaviours

---

## Prizes — up to $15,000

| Place | Cash | Vultr credits |
|---|---|---|
| 🥇 1st | $5,000 | + $3,000 |
| 🥈 2nd | $3,000 | + $1,000 |
| 🥉 3rd | $1,000 | + $1,000 |

Plus an on-site raffle in SLC (PS5, AirPods 5, Razer DeathAdder V3 HyperSpeed) for in-person attendees only.

---

## Tech resources

**Core Vultr**
- Serverless Inference (OpenAI-compatible) base URL: `https://api.vultrinference.com/v1`
- Inference docs: https://docs.vultr.com/products/serverless/inference/provisioning
- Live model list: https://api.vultrinference.com/v1/models
- Vultr API: https://www.vultr.com/api/

**Agent sandboxing**
- Vultr sandboxing guide: https://docs.vultr.com/how-to-set-up-agent-sandboxing-on-vultr-cloud-compute
- OpenSandbox: https://github.com/opensandbox-group/OpenSandbox
- gVisor: https://gvisor.dev/
- E2B: https://github.com/e2b-dev/e2b
- Microsandbox
- (Challenge 1 may use the Vultr API to spin up throwaway instances.)

**App deployment**
- Next.js + Supabase on Vultr: https://docs.vultr.com/how-to-deploy-a-nextjs-application-with-vultr-supabase-marketplace-app · [video](https://www.youtube.com/watch?v=icJzcsP59Ks)
- Coolify on Vultr: https://docs.vultr.com/how-to-deploy-an-application-with-vultr-coolify-marketplace-app · [video](https://www.youtube.com/watch?v=P0wZ2LYufGU)

---

## Reuse note
Vultr infra and Serverless Inference are mandatory (for Challenge 1), so this build is standalone and won't share well with our other hackathons.

---

## Pre-submission checklist
- [ ] Each member: new Vultr account + $200 gift code applied at kickoff
- [ ] Team registered on lablab.ai + joined Discord
- [ ] Challenge picked: ☐ Blast Radius Zero ☐ Future of Work
- [ ] Backend on a Vultr VM; web app deployed on Vultr; public URL works
- [ ] (C1) All LLM calls go through Vultr Serverless Inference
- [ ] (C1) Sandbox: isolation, no secrets inside, time/memory caps, destroyed after each task
- [ ] README: Vultr services, architecture diagram, how the agent executes real tasks
- [ ] Video (with a containment moment for C1) + slide deck + cover image
- [ ] Repo **public**
- [ ] Submitted on **lablab.ai** before **9 Nov, 4:30 AM IST**
