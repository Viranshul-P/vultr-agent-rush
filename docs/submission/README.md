# Submission kit: Airlock (Team Beyonders)

Everything needed to submit on lablab.ai. Deadline: **Sun 8 Nov 2026, 21:00 IST** (earliest reading of the rules).

| Item | Status | Where |
|---|---|---|
| Live demo | Ready | https://app.beyonders.duckdns.org |
| Repo | Ready (private until submission) | https://github.com/Viranshul-P/vultr-agent-rush |
| Slides (10, PDF) | Draft ready: set the price on slide 9, then export as PDF | Deck artifact (owner's claude.ai account); export with Download, then PDF |
| Cover image 16:9 | Ready | [`cover.png`](cover.png) (1920×1080) |
| Screenshots | Ready | [`img/`](img/) |
| Video (MP4, 4:24, with voice-over) | Ready to upload | `video/out/airlock-demo.mp4` (built from [`video/`](../../video/README.md); not in git, 71 MB); narration: [`voiceover-script.md`](voiceover-script.md) |
| lablab form text | Ready | below |
| VM snapshots (OPS-02) | To do in the Vultr console | before recording |
| Billing alert | To do in the Vultr console | |
| Repo public + tag `v1.0-submission` | At submission time | |

---

## Video script (target 4:30)

**Before recording** (checklist from docs/04 Part 16):
- Snapshot both VMs first.
- Open the live site in a fresh window (new workspace), with browser zoom at 110%, light theme, and notifications off.
- Pre-warm the models: in a second window, click **Process inbox** once and let it finish.
- Record at 1920×1080, 30 fps, and test the mic.

| Time | On screen | Say (roughly) |
|---|---|---|
| 0:00–0:25 | Cover slide, then the Orchard Cloud invoice PDF | “This invoice is asking for $48,000, and it isn’t trying to fool your team. It’s trying to fool your AI. Business email compromise cost $3.05 billion in reported losses in 2025, and 76% of organisations faced payments fraud. Now AP teams are adding AI agents, and the invoice becomes a way to attack the agent.” |
| 0:25–0:50 | **How it works** page: architecture diagram, then the dual-LLM diagram | “Airlock is an accounts-payable agent that opens every invoice inside a disposable sandbox on Vultr. Two VMs: the control plane holds the keys, and the sandbox VM, running gVisor, holds nothing worth stealing. Every model call goes through Vultr Serverless Inference.” |
| 0:50–1:40 | **Inbox**: click **Process inbox**; the outcome strip fills. Open **Brightline: office supplies**: the pipeline, the **Sandbox runs** timeline, open the Extract run drawer (code the model wrote, network none, env vars 0, runsc), then **Approve & post**, then the **Ledger** | “The model doesn’t act on the invoice. It writes Python to parse it, and that code runs in a fresh gVisor container with no network and no secrets, destroyed after the run. Then nine checks, including a three-way match. A clean invoice still only waits, because a person has to approve it before anything reaches the ledger.” |
| **1:40–2:40** | **Containment moments.** Open **Northpeak: HVAC maintenance**: the hidden-text panel (it asks for `os.environ`), the timeline, then **Contained · Quarantined** and **Blast radius 0 / 0 / 0**. Then **Kestrel: storage (pay via link)**: the credential-harvest badge, click the screenshot, then the download hash `275a021b…fd0f` and the CPU busy-loop line | “This one hides white-on-white text telling the AI to send out its environment variables and approve itself. Even if the model goes along with it, the sandbox has no env vars, no network and no approval tool. Quarantined, blast radius zero. This one links to a fake login page. A sandboxed browser behind an egress proxy opens it, a vision model flags the credential harvest, and the forced download is hashed and never opened.” |
| 2:40–3:05 | **Orchard Cloud: new bank details** (R3, R4), then **Brightline: ‘second notice’** (R5) | “A bank-detail swap from a lookalike domain is blocked, and so is a duplicate ‘second notice’. These rules are plain code, not a model’s opinion.” |
| 3:05–3:35 | **Signed receipt**: **Signature valid**. **Red Team**: **Run all drills**, ending at **11/11 contained**. **Metrics**: 40/40 and 22/22 | “Every invoice gets an Ed25519-signed receipt. Anyone can run our eleven attack drills, including a fork bomb, a memory bomb, cloud-metadata SSRF and exfiltration, and all eleven are contained on the Vultr sandbox VM. On 40 labelled invoices, 22 of them attacks, Airlock got every outcome right, with no false positives, at about a cent per invoice.” |
| 3:35–4:15 | Slide 9 (Business), then slide 10 (Roadmap) | “Airlock is for AP teams and AP-automation platforms that want AI on the inbox without handing it the keys. It’s priced by invoice volume, and it costs under a cent in model calls per invoice. Next: mailbox intake and ERP connectors, then the same airlock for any untrusted document.” |
| 4:15–4:30 | Slide 10 (team), then the live URL | “Built on Vultr Cloud Compute, Serverless Inference, VPC and Firewall Groups, Object Storage, Managed PostgreSQL and Container Registry. We’re Team Beyonders, and this is Airlock.” |

**Containment moments in the final cut:** 1:49 (prompt injection) and 2:14 (phishing link). The table above was the original plan; the rendered video follows [`voiceover-script.md`](voiceover-script.md).

---

## lablab.ai form text

**Project title:** Airlock

**Short description (one line):**
An accounts-payable AI agent that opens every invoice in a disposable Vultr sandbox, so a malicious invoice can fool the AI but can’t reach your money, secrets or servers.

**Long description:**
Accounts-payable teams open hundreds of invoices from strangers every day, and that’s how invoice fraud gets in. Business email compromise caused $3.05B in reported losses in 2025 (FBI IC3). As AP teams add AI agents, an invoice can also attack the agent itself: hidden instructions, phishing pay links, requests to dump secrets.

Airlock treats every invoice as hostile. A fixed program scans the PDF for hidden text. The model writes Python to extract the fields, and that code runs in a single-use gVisor sandbox on a separate Vultr VM, with no network, no environment variables and a read-only root. Validation covers totals, IBAN checksums, a three-way match, duplicates and lookalike sender domains. Any “pay here” link is opened by a sandboxed browser behind an egress proxy and judged by a vision model. A deterministic policy engine, with no AI in it, decides between clear, hold, block and quarantine, and only a human can approve a payment. Every invoice gets an Ed25519-signed evidence receipt.

On the live site, 40 labelled invoices (22 attacks) got 40/40 correct outcomes with 0% false positives, a p95 of 36 s and $0.0094 in model cost per invoice. All 11 red-team containment drills pass on the Vultr sandbox VM.

**Tags:** Vultr, Vultr Serverless Inference, AI Agents, Agent Security, gVisor, Docker, Playwright, FastAPI, React, Fintech, Cybersecurity

**Demo / app URL:** https://app.beyonders.duckdns.org
**Repository:** https://github.com/Viranshul-P/vultr-agent-rush
**Team:** Viranshul (Viranshul-P), Kuldeep (Kuldeeep18), Priyanshu Doshi (Priyanshu-byte-coder)
