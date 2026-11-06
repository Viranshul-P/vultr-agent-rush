# Voice-over script: Airlock demo video

Read each line while the video plays; the times are where it appears in the final cut. The same text is burned in as captions,
so small timing differences are fine. Leave a breath between lines rather than rushing to fill the gaps.

## 0:00.0 · Intro (title, no speech)
_(no narration)_

## 0:08.5 · The problem
- **0:09.1 to 0:13.9**: Business email compromise cost $3.05 billion in reported losses in 2025.
- **0:13.9 to 0:18.9**: Now AP teams are adding AI agents, and the invoice can attack the agent.
- **0:18.9 to 0:22.1**: Airlock assumes every invoice is hostile.

## 0:22.0 · How it works
- **0:22.5 to 0:28.0**: Airlock opens every invoice inside a disposable sandbox on Vultr.
- **0:28.0 to 0:33.3**: One VM holds the keys. The gVisor sandbox VM holds nothing worth stealing.
- **0:33.5 to 0:41.3**: The model that reads the raw invoice has no tools, and plain-code policy makes every decision.
- **0:41.5 to 0:45.0**: Every sandbox: no network, no secrets, single use.

## 0:44.5 · The live inbox
- **0:44.8 to 0:48.9**: Six demo invoices on the live site: two clean, four attacks.
- **0:49.1 to 0:59.7**: Each one opens in its own sandbox, six at a time.
- **1:00.0 to 1:08.0**: Two cleared. Two blocked. Two quarantined.
- **1:08.2 to 1:11.8**: Nothing reaches the ledger without a person.

## 1:11.3 · A clean invoice
- **1:11.6 to 1:14.9**: A clean invoice from a known vendor.
- **1:15.0 to 1:19.3**: The model doesn’t act on the invoice. It writes code to parse it.
- **1:19.4 to 1:23.9**: Nine checks, recomputed outside the sandbox: totals, IBAN, three-way match.
- **1:24.0 to 1:26.8**: Every sandbox run is a fresh container, destroyed after.
- **1:26.9 to 1:35.3**: No network. Zero environment variables. Read-only root. gVisor runtime.
- **1:35.4 to 1:39.1**: This is the parsing code the model wrote, run inside the sandbox.
- **1:39.3 to 1:43.4**: Even a cleared invoice waits for a person.
- **1:43.5 to 1:47.1**: Approved: posted to the ledger, and the evidence is signed.
- **1:47.2 to 1:49.9**: Only human-approved invoices ever reach the ledger.

## 1:49.5 · Containment moment 1: prompt injection
- **1:49.9 to 1:57.0**: This invoice hides white-on-white text telling the AI to send out its environment and approve itself.
- **1:57.1 to 2:02.9**: Even if the model is fooled, there are no secrets, no network and no approval tool. Blast radius: zero.
- **2:03.0 to 2:11.7**: The hidden instructions, shown here as inert text.
- **2:11.8 to 2:14.8**: Quarantined. A person reviews it, and nothing is paid.

## 2:14.3 · Containment moment 2: phishing link
- **2:14.8 to 2:20.0**: This invoice says “pay here”, and links to a lookalike login page.
- **2:20.1 to 2:29.8**: A browser opens it in its own sandbox, behind an egress proxy, and a vision model flags the credential harvest.
- **2:29.9 to 2:36.5**: This is what the sandboxed browser saw.
- **2:36.6 to 2:41.4**: The forced download is hashed and quarantined, never opened. It’s the EICAR test file.
- **2:41.5 to 2:44.0**: The page’s CPU loop ran under a one-CPU cap, then the container was destroyed.

## 2:43.5 · Fraud signals
- **2:43.9 to 2:49.6**: A “new bank account”, from orchardcl0ud: a lookalike domain with a zero.
- **2:49.7 to 2:56.3**: Blocked by plain-code rules, not by a model’s opinion.
- **2:56.4 to 3:00.8**: A duplicate “second notice” for an invoice already paid: blocked.

## 3:00.3 · Signed receipt
- **3:00.9 to 3:06.0**: Every invoice gets an Ed25519-signed evidence receipt.
- **3:06.1 to 3:12.5**: Change one byte and verification fails. Anyone can check it.

## 3:12.0 · Red Team drills
- **3:12.3 to 3:14.9**: Eleven real attacks, run inside the same sandbox an invoice gets.
- **3:15.0 to 3:20.9**: Host escape, env dump, metadata SSRF, fork bomb, memory bomb, exfiltration.
- **3:21.0 to 3:30.3**: All eleven contained on the Vultr sandbox VM.
- **3:30.4 to 3:33.9**: Each result names the sandbox run and container that produced it.

## 3:33.4 · Results
- **3:33.9 to 3:38.9**: On 40 labelled invoices, 22 of them attacks, every outcome was right.
- **3:38.9 to 3:43.1**: No false positives, and under a cent of model cost per invoice.

## 3:42.9 · Business
- **3:43.4 to 3:48.7**: Airlock is for AP teams, and for AP-automation platforms adding AI agents.
- **3:48.8 to 3:53.5**: It’s priced by invoice volume, and it costs under a cent in model calls per invoice.
- **3:53.6 to 3:58.6**: Others process invoices or isolate code. Airlock does AP checks inside a sandbox, with a human gate.

## 3:58.4 · Roadmap
- **3:58.9 to 4:07.1**: Next: mailbox intake and ERP connectors, then the same airlock for any untrusted document.

## 4:06.9 · Close
- **4:07.5 to 4:12.9**: Built on Vultr: Cloud Compute, Serverless Inference, VPC, Object Storage, Managed PostgreSQL.
- **4:13.1 to 4:18.5**: We’re Team Beyonders, and this is Airlock.

Total length: **4:18.9**.
