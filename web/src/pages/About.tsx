import React from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowRight, Cpu, EyeOff, FileLock2, Gavel, KeyRound, Lock, Play, ServerOff, Trash2, UserX } from "lucide-react";
import { PageHeader, ease } from "../ui";
import { DualLlmDiagram, PrecedenceLadder } from "../viz";

const RULES: [string, "QUARANTINE" | "BLOCK" | "HOLD", string][] = [
  ["R1", "QUARANTINE", "Invoice contains instructions aimed at AI systems"],
  ["R2", "QUARANTINE", "Linked page is a credential-harvesting lookalike"],
  ["R3", "BLOCK", "Bank details changed. Verify by phone using the number on file"],
  ["R4", "BLOCK", "Sender domain imitates the vendor"],
  ["R5", "BLOCK", "Likely duplicate invoice"],
  ["R6", "BLOCK", "Invalid bank account number"],
  ["R7", "HOLD", "Totals don't add up"],
  ["R8", "HOLD", "3-way match failed"],
  ["R9", "HOLD", "Vendor not in master data"],
  ["R10", "HOLD", "Sender address not on file for this vendor"],
  ["R11", "HOLD", "No bank account on the invoice"],
  ["R12", "HOLD", "A payment link could not be safely inspected"],
];
const TONE = { QUARANTINE: "quar", BLOCK: "block", HOLD: "hold" } as const;

const CONTAIN: [React.ReactNode, string, string][] = [
  [<Cpu key="i" />, "gVisor, separate VM", "User-space kernel (runsc) on a VM that holds no keys"],
  [<ServerOff key="i" />, "No network", "Code sandboxes have none; the browser only reaches a logging egress proxy"],
  [<KeyRound key="i" />, "No secrets", "Zero env vars passed; the sandbox VM has no API keys"],
  [<UserX key="i" />, "No privileges", "Non-root, read-only root, every capability dropped"],
  [<Gavel key="i" />, "Hard caps", "CPU, memory, process count and wall-clock limits"],
  [<Trash2 key="i" />, "Single use", "One container per task, destroyed after; orphans swept"],
  [<FileLock2 key="i" />, "Signed evidence", "Every run sealed into an Ed25519 receipt"],
];

function ArchDiagram() {
  return (
    <svg className="arch" viewBox="0 0 980 430" role="img" aria-label="Architecture: untrusted PDFs reach the control plane, which sends work over a private VPC to a sandbox VM with no secrets. Only a human can post to the ledger.">
      <defs>
        <marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--text-3)" /></marker>
        <marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--accent)" /></marker>
      </defs>

      {/* untrusted input */}
      <rect className="box" x="16" y="86" width="150" height="70" rx="12" />
      <text className="lbl" x="91" y="116" textAnchor="middle">Invoice PDF</text>
      <text className="sub" x="91" y="136" textAnchor="middle">untrusted, from email</text>

      {/* control plane */}
      <rect className="zone" x="210" y="40" width="330" height="370" rx="16" />
      <text className="ztitle" x="230" y="66">CONTROL PLANE VM · HOLDS THE KEYS</text>
      <rect className="box" x="235" y="86" width="280" height="70" rx="12" />
      <text className="lbl" x="375" y="116" textAnchor="middle">API + orchestrator</text>
      <text className="sub" x="375" y="136" textAnchor="middle">routes work, never runs invoice code</text>
      <rect className="box" x="235" y="176" width="280" height="70" rx="12" />
      <text className="lbl" x="375" y="206" textAnchor="middle">Policy engine (plain code)</text>
      <text className="sub" x="375" y="226" textAnchor="middle">rechecks every result, decides</text>
      <rect className="box" x="235" y="266" width="130" height="58" rx="12" />
      <text className="lbl" x="300" y="292" textAnchor="middle">PostgreSQL</text>
      <text className="sub" x="300" y="310" textAnchor="middle">Managed</text>
      <rect className="box" x="385" y="266" width="130" height="58" rx="12" />
      <text className="lbl" x="450" y="292" textAnchor="middle">Object Storage</text>
      <text className="sub" x="450" y="310" textAnchor="middle">evidence, receipts</text>
      <rect className="box" x="235" y="340" width="280" height="52" rx="12" style={{ stroke: "var(--clear)" }} />
      <text className="lbl" x="375" y="371" textAnchor="middle">Human approval → Ledger</text>

      {/* sandbox VM */}
      <rect className="zone sb" x="600" y="40" width="364" height="290" rx="16" />
      <text className="ztitle" x="620" y="66">SANDBOX VM · gVISOR · NO SECRETS</text>
      {[0, 1, 2].map((i) => (
        <g key={i}>
          <rect className="box" x={625 + i * 8} y={86 + i * 8} width="200" height="64" rx="12" />
        </g>
      ))}
      <text className="lbl" x="741" y="124" textAnchor="middle">Code sandboxes</text>
      <text className="sub" x="741" y="143" textAnchor="middle">network none · read-only · single use</text>
      <rect className="box" x="625" y="196" width="160" height="62" rx="12" />
      <text className="lbl" x="705" y="223" textAnchor="middle">Browser sandbox</text>
      <text className="sub" x="705" y="242" textAnchor="middle">opens “pay here” links</text>
      <rect className="box" x="798" y="196" width="156" height="62" rx="12" />
      <text className="lbl" x="876" y="223" textAnchor="middle">Egress proxy</text>
      <text className="sub" x="876" y="242" textAnchor="middle">blocks private + metadata</text>

      {/* internet + secrets */}
      <rect className="box" x="810" y="356" width="134" height="52" rx="12" />
      <text className="lbl" x="877" y="387" textAnchor="middle">Public web</text>
      <rect className="box" x="600" y="356" width="170" height="52" rx="12" style={{ strokeDasharray: "4 4" }} />
      <text className="lbl" x="685" y="380" textAnchor="middle">API keys · DB · ledger</text>
      <text className="sub" x="685" y="398" textAnchor="middle">unreachable from sandbox</text>

      {/* wires */}
      <path className="wire flow" d="M166 121 H235" markerEnd="url(#ahb)" />
      <path className="wire" d="M375 156 V176" markerEnd="url(#ah)" />
      <path className="wire flow" d="M515 121 H625" markerEnd="url(#ahb)" />
      <text className="sub" x="570" y="112" textAnchor="middle">VPC</text>
      <path className="wire" d="M625 150 C580 170 560 200 515 211" markerEnd="url(#ah)" />
      <text className="sub" x="552" y="182" textAnchor="middle">results</text>
      <path className="wire" d="M375 246 V266" />
      <path className="wire" d="M375 324 V340" markerEnd="url(#ah)" />
      <path className="wire" d="M785 227 H798" markerEnd="url(#ah)" />
      <path className="wire flow" d="M876 258 V356" markerEnd="url(#ahb)" />
      <path className="wire no" d="M705 258 V356" />
      <g transform="translate(705 306)"><circle r="11" fill="var(--block-bg)" stroke="var(--block)" /><path d="M-4 -4 L4 4 M4 -4 L-4 4" stroke="var(--block)" strokeWidth="2" /></g>
    </svg>
  );
}

export function About() {
  return (
    <div>
      <PageHeader
        title="How Airlock works"
        sub="AP teams open hundreds of invoices from strangers every day, which is exactly how invoice fraud and prompt injection get in. Airlock assumes a document can be hostile and builds the walls around that."
        actions={<Link className="btn" to="/inbox"><Play />Try it live</Link>}
      />

      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-h"><h2>Architecture</h2><span className="sub">two VMs, one private link, nothing secret on the side that touches invoices</span></div>
        <div className="panel-b" style={{ overflowX: "auto" }}>
          <div style={{ minWidth: 760 }}><ArchDiagram /></div>
        </div>
      </div>

      <motion.div className="panel" style={{ marginBottom: 20 }} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, ease }}>
        <div className="panel-h"><EyeOff size={16} /><h2>Dual-LLM safety</h2><span className="sub">the model that can be fooled has nothing to call</span></div>
        <div className="panel-b" style={{ overflowX: "auto" }}><div style={{ minWidth: 520 }}><DualLlmDiagram /></div></div>
      </motion.div>

      <motion.div className="panel" style={{ marginBottom: 20 }} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, ease, delay: 0.06 }}>
        <div className="panel-h"><Lock size={16} /><h2>Containment</h2><span className="sub">every sandbox run, every time</span></div>
        <div className="panel-b">
          <div className="tiles">
            {CONTAIN.map(([icon, t, d]) => <div key={t} className="tile">{icon}<b>{t}</b><span>{d}</span></div>)}
          </div>
        </div>
      </motion.div>

      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-h"><Gavel size={16} /><h2>Policy rules</h2><span className="sub">the highest-ranked rule that fires sets the outcome</span></div>
        <PrecedenceLadder counts={{ QUARANTINE: RULES.filter((r) => r[1] === "QUARANTINE").length, BLOCK: RULES.filter((r) => r[1] === "BLOCK").length, HOLD: RULES.filter((r) => r[1] === "HOLD").length }} />
        <div className="table-wrap">
          <table className="t">
            <thead><tr><th style={{ width: 70 }}>Rule</th><th style={{ width: 150 }}>Outcome</th><th>When</th></tr></thead>
            <tbody>
              {RULES.map(([id, out, msg]) => (
                <tr key={id}><td className="mono muted">{id}</td><td><span className={`badge ${TONE[out]}`}><i />{out.toLowerCase()}</span></td><td>{msg}</td></tr>
              ))}
              <tr><td className="mono muted">—</td><td><span className="badge clear"><i />clear</span></td><td>No rule fired. The invoice waits for a person to approve it.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="cta-band">
        <div>
          <h2>Watch it on real invoices</h2>
          <p>Process the demo inbox, open the injected one and read the code the model wrote.</p>
        </div>
        <div className="row">
          <Link className="btn lg secondary" to="/red-team">Run the drills</Link>
          <Link className="btn lg" to="/inbox">Open the inbox <ArrowRight /></Link>
        </div>
      </div>
    </div>
  );
}
