# Airlock: submission guide (Team Beyonders)

Everything for the lablab.ai submission (Vultr: Agent Rush Hackathon, Challenge 1, Blast Radius Zero) is in this folder.

**Deadline: Sun 8 Nov 2026, 21:00 IST** (the earliest reading of the rules; the latest is Mon 9 Nov, 03:30 IST).

## What's in this folder

| File | What it is | Form field |
|---|---|---|
| `airlock-demo.mp4` | Demo video, 4:24, 1920×1080, with voice-over (71 MB, **not in git**) | Video: https://youtu.be/fOS1BW82LaI |
| `airlock-slides.pdf` | 10-slide deck | Slides / presentation |
| `cover.png` | Cover image, 16:9, 1920×1080 | Cover image / thumbnail |
| `screenshots/inbox.png` | Inbox after **Process inbox**, with the outcome strip | Screenshots |
| `screenshots/injection.png` | Prompt-injection invoice, quarantined, blast radius 0 | Screenshots |
| `screenshots/phishing.png` | Phishing pay link: credential harvest flagged, download hashed | Screenshots |
| `screenshots/redteam.png` | Red Team: 11/11 drills contained | Screenshots |
| `voiceover-script.md` | Narration with timestamps (for reference or captions) | — |

The video only exists on the laptop that rendered it. To rebuild it, see [`video/README.md`](../video/README.md).

## Steps, in order

1. **Optional: snapshot both VMs** in the Vultr console (`airlock-control` and `airlock-sandbox`) as a rollback point, and set a **billing alert**. The API key only accepts allowlisted IPs, so this has to be done in the console.
2. ✅ Slides exported: `airlock-slides.pdf` (in git) and `airlock-slides.pptx` (local only).
3. ✅ Video uploaded: https://youtu.be/fOS1BW82LaI
4. ✅ README links filled in.
5. ✅ Tag `v1.0-submission` on the final commit.
6. **Check that the live demo is up:** https://app.beyonders.duckdns.org/api/health should return `"ok":true`.
7. **Fill in the lablab.ai form** with the text below and upload the files from this folder.
8. **After submitting:** keep the demo live through judging. Check `/api/health` once a day and don't change production.

## Before you click submit

- [ ] Video plays with sound; the containment moments are at **1:49** and **2:14**
- [ ] Slides PDF has 10 pages, and slide 9 shows the price ($299/month for 1,000 invoices)
- [ ] Cover image and 4 screenshots attached
- [ ] Repo is public: https://github.com/Viranshul-P/vultr-agent-rush
- [ ] Live demo works without signing in: open it, click **Process inbox**
- [ ] All three team members are added to the lablab team

---

## lablab.ai form text (copy and paste)

**Project title:** Airlock

**Short description:**
An accounts-payable AI agent that opens every invoice in a disposable Vultr sandbox, so a malicious invoice can fool the AI but can't reach your money, secrets or servers.

**Long description:**
Accounts-payable teams open hundreds of invoices from strangers every day, and that's how invoice fraud gets in. Business email compromise caused $3.05B in reported losses in 2025 (FBI IC3). As AP teams add AI agents, an invoice can also attack the agent itself: hidden instructions, phishing pay links, requests to dump secrets.

Airlock treats every invoice as hostile. A fixed program scans the PDF for hidden text. The model writes Python to extract the fields, and that code runs in a single-use gVisor sandbox on a separate Vultr VM, with no network, no environment variables and a read-only root. Validation covers totals, IBAN checksums, a three-way match, duplicates and lookalike sender domains. Any "pay here" link is opened by a sandboxed browser behind an egress proxy and judged by a vision model. A deterministic policy engine, with no AI in it, decides between clear, hold, block and quarantine, and only a human can approve a payment. Every invoice gets an Ed25519-signed evidence receipt.

On the live site, 40 labelled invoices (22 attacks) got 40/40 correct outcomes with 0% false positives, a p95 of 36 s and $0.0094 in model cost per invoice. All 11 red-team containment drills pass on the Vultr sandbox VM.

**Tags:** Vultr, Vultr Serverless Inference, AI Agents, Agent Security, gVisor, Docker, Playwright, FastAPI, React, Fintech, Cybersecurity

**Challenge:** Challenge 1, Blast Radius Zero

**Demo / app URL:** https://app.beyonders.duckdns.org

**Repository:** https://github.com/Viranshul-P/vultr-agent-rush

**Video:** https://youtu.be/fOS1BW82LaI

**Slides:** https://github.com/Viranshul-P/vultr-agent-rush/blob/main/submissions/airlock-slides.pdf (or upload airlock-slides.pdf)

**Team Beyonders:** Viranshul (Viranshul-P), Kuldeep (Kuldeeep18), Priyanshu Doshi (Priyanshu-byte-coder)

**Vultr services used:** Cloud Compute (control-plane VM and isolated sandbox VM), Serverless Inference (every model call), VPC and Firewall Groups, Object Storage, Managed PostgreSQL, Container Registry

---

## Supporting evidence (in the repo)

| What | Where |
|---|---|
| Full write-up and how to run it | [`README.md`](../README.md) |
| 40-invoice live eval (40/40) | [`eval/results/2026-11-05-1527.json`](../eval/results/2026-11-05-1527.json) |
| Red-team drills on the Vultr VM (11/11) | [`docs/evidence/drills-vultr-2026-11-04.json`](../docs/evidence/drills-vultr-2026-11-04.json) |
| What was set up on Vultr | [`CHANGES.md`](../CHANGES.md) |
