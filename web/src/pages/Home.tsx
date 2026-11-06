import React from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowRight, Ban, Boxes, Check, CheckCircle2, Cloud, Code2, Cpu, Database, EyeOff, FileSearch, FileText, Gavel, HardDrive,
  KeyRound, Link2, Network, PauseCircle, Play, ScanLine, Server, ShieldAlert, ShieldCheck, Swords, UserCheck, Wrench,
} from "lucide-react";
import { api, Invoice, Status } from "../api";
import { STATUS_LABEL } from "../pipeline";
import { CountUp, Pipeline, StatusBadge, ease } from "../ui";

/* ---------- hero walkthrough: the six demo invoices' real outcomes, replayed ---------- */
type Scenario = {
  key: string; tab: string; vendor: string; number: string; amount: string; path: Status[];
  final: Status; line: string; links?: boolean; injection?: boolean; failed?: number; phishing?: boolean;
};
const SCENARIOS: Scenario[] = [
  { key: "clean", tab: "Clean invoice", vendor: "Brightline Office Supply Ltd", number: "INV-2026-0412", amount: "USD 4,643.93",
    path: ["SCANNING", "EXTRACTING", "VALIDATING", "DECIDING"], final: "AWAIT_APPROVAL", line: "All 9 checks pass. It waits for a person to approve." },
  { key: "bank", tab: "Bank swap", vendor: "Orchard Cloud Services Inc.", number: "OCS-88213", amount: "USD 48,000.00",
    path: ["SCANNING", "EXTRACTING", "VALIDATING", "DECIDING"], final: "BLOCKED", failed: 2, line: "New bank account, and a sender domain imitating the vendor. Blocked." },
  { key: "inject", tab: "Prompt injection", vendor: "Northpeak Facilities SAS", number: "NP-2026-1187", amount: "EUR 9,200.00",
    path: ["SCANNING", "EXTRACTING", "VALIDATING", "DECIDING"], final: "QUARANTINED", injection: true, line: "Hidden text tells the AI to send out its environment. Quarantined." },
  { key: "phish", tab: "Phishing link", vendor: "Kestrel Logistics GmbH", number: "KL-26-10-0957", amount: "EUR 3,975.00",
    path: ["SCANNING", "EXTRACTING", "VALIDATING", "INSPECTING_LINKS", "DECIDING"], final: "QUARANTINED", links: true, phishing: true, line: "The “pay here” link is a password-harvesting lookalike. Quarantined." },
];
const STEP_MS = 720, HOLD_MS = 3400;

function fakeInvoice(s: Scenario, status: Status): Invoice {
  const reachedLinks = s.links && ["INSPECTING_LINKS", "DECIDING", s.final].includes(status) && status !== "INSPECTING_LINKS";
  return {
    id: s.key, order: 0, title: s.tab, filename: "", source: "demo", status,
    detectors: { injection_suspected: !!s.injection },
    policy: { outcome: status === s.final ? ({ AWAIT_APPROVAL: "CLEAR", BLOCKED: "BLOCK", QUARANTINED: "QUARANTINE" } as any)[s.final] : undefined,
      checks: Array.from({ length: 9 }, (_, i) => ({ id: `c${i}`, passed: i >= (s.failed || 0) })) },
    browser: reachedLinks ? [{ credential_harvest: !!s.phishing }] : [],
  } as Invoice;
}

function Walkthrough() {
  const [idx, setIdx] = React.useState(0);
  const [step, setStep] = React.useState(0);
  const [paused, setPaused] = React.useState(false);
  const reduced = React.useMemo(() => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches, []);
  const s = SCENARIOS[idx];
  const seq: Status[] = ["NEW", ...s.path, s.final];
  const atEnd = step >= seq.length - 1;

  const go = React.useCallback((i: number) => {
    const n = SCENARIOS[i].path.length + 1;
    setIdx(i); setStep(reduced ? n : 0);
  }, [reduced]);
  React.useEffect(() => {
    if (paused) return;
    const t = setTimeout(() => {
      if (!atEnd) setStep((x) => x + 1);
      else go((idx + 1) % SCENARIOS.length);
    }, atEnd ? HOLD_MS : step === 0 ? 500 : STEP_MS);
    return () => clearTimeout(t);
  }, [step, atEnd, paused, idx, go]);

  const status = seq[Math.min(step, seq.length - 1)];
  const inv = fakeInvoice(s, status);
  const total = (seq.length - 1) * STEP_MS + HOLD_MS;
  return (
    <div className="demo" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="demo-top">
        <span className="dots"><i /><i /><i /></span>
        <span>Replay of the demo inbox</span>
        <span className="grow" />
        <span className="muted" style={{ fontSize: 11.5 }}>{paused ? "paused" : "auto-playing"}</span>
      </div>
      <div className="demo-body">
        <AnimatePresence mode="wait">
          <motion.div key={s.key} className="demo-doc" initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 14 }} transition={{ duration: 0.35, ease }}>
            <span className="di"><FileText /></span>
            <span style={{ minWidth: 0 }}>
              <div className="dt">{s.vendor}</div>
              <div className="dd mono">{s.number} · {s.amount}</div>
            </span>
            <StatusBadge status={status} />
          </motion.div>
        </AnimatePresence>
        <Pipeline inv={inv} />
        <div style={{ minHeight: 46, marginTop: 14 }}>
          <AnimatePresence mode="wait">
            {atEnd && (
              <motion.div key={s.key} initial={{ opacity: 0, y: 6, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0 }} transition={{ duration: 0.4, ease }}
                className="row" style={{ gap: 10, alignItems: "flex-start", fontSize: 13.5 }}>
                <span style={{ color: s.final === "AWAIT_APPROVAL" ? "var(--clear)" : s.final === "BLOCKED" ? "var(--block)" : "var(--quar)", marginTop: 1 }}>
                  {s.final === "AWAIT_APPROVAL" ? <ShieldCheck size={18} /> : s.final === "BLOCKED" ? <Ban size={18} /> : <ShieldAlert size={18} />}
                </span>
                <span className="grow" style={{ minWidth: 0 }}><b>{STATUS_LABEL[s.final]}.</b> <span className="dim">{s.line}</span></span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <div className="demo-foot" role="tablist" aria-label="Demo scenarios">
        {SCENARIOS.map((x, i) => (
          <button key={x.key} role="tab" aria-selected={i === idx} className={i === idx ? "on" : ""} onClick={() => go(i)}>
            {x.tab}
            <span className="pg">{i === idx && <motion.i key={`${idx}-${paused}`} initial={{ width: paused ? undefined : "0%" }} animate={{ width: paused ? undefined : "100%" }} transition={{ duration: total / 1000, ease: "linear" }} />}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ---------- step explorer ---------- */
const STEPS = [
  { key: "scan", icon: <ScanLine />, title: "Scan the PDF", where: "sb", whereLabel: "Inside the sandbox",
    body: "A fixed program, with no AI involved, opens the PDF first. It pulls out the text and looks for anything a person can't see: white-on-white text, tiny fonts, off-page runs and instructions hidden in metadata.",
    facts: ["Hidden text runs are counted and shown to the reviewer", "A separate classifier scores how injection-like the text is", "Nothing in the PDF can reach the network"] },
  { key: "extract", icon: <FileSearch />, title: "Extract the fields", where: "sb", whereLabel: "Inside the sandbox",
    body: "The model doesn't read the invoice into its own context and act on it. It writes small Python parsing code, and that code runs in a fresh gVisor container. If the code errors, the model sees the traceback and tries again.",
    facts: ["Static checks flag risky calls such as sockets, subprocess and eval", "No network, no environment variables, read-only root", "Container destroyed after every run"] },
  { key: "validate", icon: <Check />, title: "Validate", where: "sb", whereLabel: "Sandbox, then rechecked",
    body: "Vendor known? Totals add up? IBAN valid and matching the vendor master? Is the sender's domain on file, is the PO open, and is it a duplicate? Each check runs in the sandbox, and the control plane recomputes each one on its own.",
    facts: ["9 checks per invoice", "Any disagreement between the sandbox and the control plane is flagged", "The vendor master never enters the model's prompt"] },
  { key: "links", icon: <Link2 />, title: "Inspect links", where: "sb", whereLabel: "Sandboxed browser",
    body: "If the invoice says “pay here”, a headless browser opens the link in its own container. Its only route out is an egress proxy that blocks private and cloud-metadata addresses. A vision model judges the screenshot.",
    facts: ["Forced downloads are hashed and quarantined, never opened", "CPU and memory caps contain hostile pages", "Every request is logged by the proxy"] },
  { key: "decide", icon: <Gavel />, title: "Decide by policy", where: "cp", whereLabel: "Control plane, no AI",
    body: "A deterministic policy engine, in plain code, turns the evidence into one outcome: clear, hold, block or quarantine. A model can describe the result, but it can't change it.",
    facts: ["Rules are code, and every rule that fires is listed", "The summary model never sees the raw document", "Every decision is signed into a receipt"] },
  { key: "approve", icon: <UserCheck />, title: "A person approves", where: "hu", whereLabel: "Human",
    body: "Even a cleared invoice only waits. A person reads the summary and evidence, then approves or rejects. No model has a way to post a payment.",
    facts: ["Only approved invoices reach the ledger", "Receipt verifies with Ed25519", "Blast radius measured on every run"] },
] as const;

function StepExplorer() {
  const [i, setI] = React.useState(0);
  const s = STEPS[i];
  return (
    <div className="steps">
      <div className="steps-list" role="tablist" aria-label="Pipeline steps">
        {STEPS.map((x, j) => (
          <button key={x.key} role="tab" aria-selected={i === j} className={i === j ? "on" : ""} onClick={() => setI(j)}>
            {i === j && <motion.span layoutId="step-bg" className="sbg" transition={{ duration: 0.3, ease }} />}
            <span className="si">{x.icon}</span>
            <span className="st">{x.title}</span>
            <span className="sw">{x.whereLabel}</span>
          </button>
        ))}
      </div>
      <div className="step-view">
        <AnimatePresence mode="wait">
          <motion.div key={s.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.3, ease }}>
            <span className={`step-where ${s.where}`}>{s.where === "sb" ? <Boxes /> : s.where === "cp" ? <Server /> : <UserCheck />}{s.whereLabel}</span>
            <h3>{s.title}</h3>
            <p>{s.body}</p>
            <ul className="list-check step-art">
              {s.facts.map((f, k) => (
                <motion.li key={f} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.12 + k * 0.07, duration: 0.3, ease }}><Check />{f}</motion.li>
              ))}
            </ul>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ---------- page ---------- */
export function Home() {
  const [m, setM] = React.useState<any>(null);
  React.useEffect(() => { api.metrics().then(setM).catch(() => {}); }, []);
  const e = m?.eval;

  return (
    <div>
      <section className="hero">
        <div>
          <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}>
            Open every invoice in a sealed room.
          </motion.h1>
          <motion.p className="lede" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease, delay: 0.08 }}>
            Airlock is an accounts-payable agent that reads untrusted invoices inside disposable Vultr sandboxes.
            A malicious invoice might fool the AI. It still can't reach your money, your secrets or your servers.
          </motion.p>
          <motion.div className="cta" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease, delay: 0.16 }}>
            <Link className="btn lg" to="/inbox"><Play />Try the live inbox</Link>
            <Link className="btn lg secondary" to="/red-team"><Swords />Run the attack drills</Link>
          </motion.div>
          {e && (
            <motion.div className="proof" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6, delay: 0.3 }}>
              <span><CheckCircle2 /><b>{Math.round(e.outcome_accuracy * 100)}%</b> correct on {e.n} invoices</span>
              {e.attacks_caught && <span><ShieldCheck /><b>{e.attacks_caught.caught}/{e.attacks_caught.total}</b> attacks caught</span>}
              {e.drills_passed != null && <span><Swords /><b>{e.drills_passed}/{e.drills_total}</b> drills contained</span>}
            </motion.div>
          )}
        </div>
        <motion.div initial={{ opacity: 0, y: 20, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.7, ease, delay: 0.1 }}>
          <Walkthrough />
        </motion.div>
      </section>

      <section className="section">
        <div className="section-h">
          <h2>Every invoice ends one of four ways</h2>
          <p>The outcome comes from plain-code policy, not from a model's opinion. Only “cleared” can move forward, and only after a person approves it.</p>
        </div>
        <div className="outcomes">
          {[
            { c: "clear", icon: <ShieldCheck />, t: "Cleared", d: "Every check passed. It waits for a person to approve before anything is posted.", x: "e.g. a routine supplies order" },
            { c: "hold", icon: <PauseCircle />, t: "Held", d: "Something needs a closer look: totals that don't add up, a 3-way mismatch or an unknown vendor. Nothing moves.", x: "e.g. billed more than was received" },
            { c: "block", icon: <Ban />, t: "Blocked", d: "Clear fraud signals: a swapped bank account, a lookalike sender or a duplicate.", x: "e.g. “please pay our new account”" },
            { c: "quar", icon: <ShieldAlert />, t: "Quarantined", d: "The document itself is hostile: hidden AI instructions, or a link to a phishing page.", x: "e.g. white-on-white “ignore your rules”" },
          ].map((o, i) => (
            <motion.div key={o.c} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }} transition={{ duration: 0.45, ease, delay: i * 0.06 }}>
              <Link to="/inbox" className={`oc ${o.c}`} style={{ color: "inherit", height: "100%" }}>
                <span className="ot">{o.icon}{o.t}</span>
                <p>{o.d}</p>
                <span className="ox">{o.x}</span>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-h">
          <h2>Follow one invoice through the airlock</h2>
          <p>Four stages run inside sealed, single-use containers on a separate VM. The last two run where the sandbox can't reach.</p>
        </div>
        <StepExplorer />
      </section>

      <section className="section">
        <div className="section-h">
          <h2>Why a fooled model still can't do damage</h2>
          <p>Airlock doesn't assume the AI can't be tricked. It makes sure that when the AI is tricked, nothing useful is in reach.</p>
        </div>
        <div className="guar">
          {[
            { icon: <EyeOff />, t: "The reader has no tools", d: "The model that reads raw invoice text can't call anything. A successful injection finds nothing to trigger. The model that writes the summary never sees the raw document.", m: "dual-LLM split" },
            { icon: <KeyRound />, t: "Nothing in reach to steal", d: "Sandboxes run under gVisor on their own VM, with no network, no environment variables and a read-only root. The sandbox VM holds no API keys at all.", m: "measured: 0 secrets · 0 outbound · 0 host files" },
            { icon: <UserCheck />, t: "A person signs off", d: "No model has a path to the ledger. Payment needs a human click, and the evidence is signed into a receipt anyone can verify.", m: "Ed25519-signed receipts" },
          ].map((g, i) => (
            <motion.div key={g.t} initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.08 }}>
              <div className="gi">{g.icon}</div>
              <h3>{g.t}</h3>
              <p>{g.d}</p>
              <div className="gm">{g.m}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {e && (
        <section className="section">
          <div className="section-h">
            <h2>Measured on the live site</h2>
            <p>{e.n} labelled invoices, {e.attacks_caught?.total ?? "several"} of them attacks, sent through this same deployment on {e.run_date?.slice(0, 10)}.</p>
          </div>
          <div className="stats">
            <div className="stat good"><div className="v"><CountUp to={e.outcome_accuracy * 100} suffix="%" /></div><div className="l">correct outcome</div></div>
            {e.attacks_caught && <div className="stat good"><div className="v"><CountUp to={e.attacks_caught.caught} /><small>/{e.attacks_caught.total}</small></div><div className="l">attacks caught</div></div>}
            <div className="stat"><div className="v"><CountUp to={(e.false_positive_rate ?? 0) * 100} suffix="%" /></div><div className="l">false positives</div></div>
            <div className="stat"><div className="v"><CountUp to={(e.latency_p50_ms ?? 0) / 1000} decimals={1} suffix=" s" /></div><div className="l">median per invoice</div></div>
            <div className="stat"><div className="v"><CountUp to={e.cost_per_invoice_usd ?? 0} decimals={4} prefix="$" /></div><div className="l">inference per invoice</div></div>
          </div>
          <div style={{ marginTop: 14 }}><Link to="/metrics" className="row" style={{ gap: 6, display: "inline-flex", fontWeight: 540 }}>Full breakdown <ArrowRight size={15} /></Link></div>
        </section>
      )}

      <section className="section">
        <div className="section-h">
          <h2>Built on Vultr</h2>
          <p>Two VMs on a private VPC: the control plane holds the keys, and the sandbox VM holds nothing worth stealing.</p>
        </div>
        <div className="stack-list">
          {[
            { icon: <Server />, t: "Cloud Compute", d: "Control-plane VM: API, policy engine, web" },
            { icon: <Cpu />, t: "Cloud Compute", d: "Isolated sandbox VM running gVisor" },
            { icon: <Wrench />, t: "Serverless Inference", d: "Every model call the agent makes" },
            { icon: <Network />, t: "VPC + Firewall", d: "Private link to the runner, no public exposure" },
            { icon: <HardDrive />, t: "Object Storage", d: "Uploads, screenshots and signed receipts" },
            { icon: <Database />, t: "Managed PostgreSQL", d: "Invoices, events and runs" },
            { icon: <Cloud />, t: "Container Registry", d: "Set up for the sandbox images; the live VM builds them and pins by digest" },
          ].map((x, i) => (
            <div key={i}><span className="si">{x.icon}</span><div><b>{x.t}</b><span>{x.d}</span></div></div>
          ))}
        </div>
      </section>

      <section style={{ paddingTop: 8 }}>
        <div className="cta-band">
          <div>
            <h2>See it handle the attacks yourself</h2>
            <p>Six demo invoices, four of them attacks. Processing all of them takes under a minute.</p>
          </div>
          <div className="row">
            <Link className="btn lg secondary" to="/about"><Code2 />How it's built</Link>
            <Link className="btn lg" to="/inbox"><Play />Open the inbox</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
