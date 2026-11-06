// Small, dependency-free SVG visuals used across pages. Colors come from the status tokens in
// styles.css (each paired with an icon or label, never color alone); every mark has a hover title.
import React from "react";
import { motion } from "motion/react";
import type { Invoice, Run } from "./api";
import { Tone, toneOf } from "./pipeline";
import { TONE_TITLE, ease } from "./ui";

const TONE_VAR: Record<Tone, string> = {
  clear: "var(--clear)", done: "var(--text-2)", hold: "var(--hold)", block: "var(--block)",
  quar: "var(--quar)", proc: "var(--proc)", new: "var(--line-strong)",
};

/* ---------- ring: passed out of total, as a segmented donut ---------- */
export function Ring({ passed, total, size = 64, label, sub }: { passed: number; total: number; size?: number; label?: React.ReactNode; sub?: string }) {
  const r = size / 2 - 5, c = 2 * Math.PI * r;
  // Few items: one segment each. Many (an eval of 40): two continuous arcs, passed and failed.
  const segs = total > 12
    ? [{ len: c * passed / total, ok: true, off: 0 }, { len: c * (total - passed) / total, ok: false, off: c * passed / total }].filter((x) => x.len > 0)
    : null;
  const n = Math.max(total, 1);
  const gap = total > 1 ? Math.min(4, c / n / 4) : 0; // 2px-ish surface gap between segments
  const seg = c / n;
  return (
    <div className="ring" style={{ width: size, height: size }} title={`${passed} of ${total} passed`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {segs && segs.map((x, i) => (
            <motion.circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={6}
              stroke={x.ok ? "var(--clear)" : "var(--block)"} strokeDasharray={`${Math.max(x.len - (segs.length > 1 ? 2 : 0), 0.5)} ${c}`} strokeDashoffset={-x.off}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, ease }}>
              <title>{x.ok ? `${passed} passed` : `${total - passed} failed`}</title>
            </motion.circle>
          ))}
          {!segs && Array.from({ length: n }, (_, i) => (
            <motion.circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={6} strokeLinecap="butt"
              stroke={total === 0 ? "var(--surface-3)" : i < passed ? "var(--clear)" : "var(--block)"}
              strokeDasharray={`${Math.max(seg - gap, 0.5)} ${c}`} strokeDashoffset={-i * seg}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3, delay: i * 0.035, ease }}>
              <title>{i < passed ? "passed" : "failed"}</title>
            </motion.circle>
          ))}
        </g>
      </svg>
      <div className="ring-c"><b style={{ fontSize: size < 56 ? 10.5 : 14 }}>{label ?? `${passed}/${total}`}</b>{sub && <span>{sub}</span>}</div>
    </div>
  );
}

/* ---------- outcome strip: where the inbox stands, at a glance ---------- */
const STRIP_ORDER: Tone[] = ["clear", "done", "hold", "block", "quar", "proc", "new"];
const STRIP_LABEL: Record<Tone, string> = { ...TONE_TITLE, clear: "Needs approval", new: "Not processed" };

export function OutcomeStrip({ invoices }: { invoices: Invoice[] }) {
  if (!invoices.length) return null;
  const counts = STRIP_ORDER.map((t) => [t, invoices.filter((i) => toneOf(i.status, i.queued) === t).length] as const).filter(([, n]) => n > 0);
  const total = invoices.length;
  return (
    <div className="strip" aria-label="Inbox outcomes">
      <div className="strip-bar" role="img" aria-label={counts.map(([t, n]) => `${n} ${STRIP_LABEL[t]}`).join(", ")}>
        {counts.map(([t, n]) => (
          <motion.i key={t} layout title={`${STRIP_LABEL[t]}: ${n} of ${total}`} className={t === "proc" ? "pulse" : ""}
            style={{ background: TONE_VAR[t], flexGrow: n }} transition={{ duration: 0.5, ease }} />
        ))}
      </div>
      <div className="strip-legend">
        {counts.map(([t, n]) => (
          <span key={t}><i style={{ background: TONE_VAR[t] }} />{STRIP_LABEL[t]}<b className="num">{n}</b></span>
        ))}
      </div>
    </div>
  );
}

/* ---------- run timeline: every sandbox container, created to destroyed ---------- */
const KIND_LABEL: Record<string, string> = { scan: "Scan", extract: "Extract", validate: "Validate", browse: "Browser", browser: "Browser" };

export function RunTimeline({ runs, onOpen }: { runs: Run[]; onOpen: (id: string) => void }) {
  const rows = runs.filter((r) => r.created_at).map((r) => {
    const start = +new Date(r.created_at!);
    const end = r.destroyed_at ? +new Date(r.destroyed_at) : start + (r.duration_ms || 0);
    return { r, start, end: Math.max(end, start + (r.duration_ms || 0)) };
  });
  if (!rows.length) return null;
  const t0 = Math.min(...rows.map((x) => x.start));
  const t1 = Math.max(...rows.map((x) => x.end));
  const span = Math.max(t1 - t0, 1000);
  const W = 100; // percent
  const ticks = niceTicks(span / 1000);
  return (
    <div className="gantt" role="list" aria-label="Sandbox container lifetimes">
      {rows.map(({ r, start, end }, i) => {
        const left = ((start - t0) / span) * W;
        const width = Math.max(((end - start) / span) * W, 1.2);
        return (
          <button key={r.id} role="listitem" className="g-row" onClick={() => onOpen(r.id)}
            title={`${KIND_LABEL[r.kind] || r.kind}${r.attempt > 1 ? ` #${r.attempt}` : ""}: ${(r.duration_ms / 1000).toFixed(1)} s, ${r.tier}${r.killed_reason ? `, killed: ${r.killed_reason}` : ""}. Click for details.`}>
            <span className="g-k">{KIND_LABEL[r.kind] || r.kind}{r.attempt > 1 ? ` #${r.attempt}` : ""}</span>
            <span className="g-track">
              <motion.i className={r.killed_reason ? "bad" : r.kind === "browse" || r.kind === "browser" ? "br" : ""}
                style={{ left: `${left}%` }} initial={{ width: 0 }} animate={{ width: `${width}%` }} transition={{ duration: 0.6, ease, delay: i * 0.05 }} />
            </span>
            <span className="g-d mono num">{(r.duration_ms / 1000).toFixed(1)} s</span>
          </button>
        );
      })}
      <div className="g-axis" aria-hidden>
        <span />
        <span className="g-ticks">{ticks.map((t) => <i key={t} style={{ left: `${(t / (span / 1000)) * 100}%` }}>{t}s</i>)}</span>
        <span />
      </div>
    </div>
  );
}
function niceTicks(max: number) {
  const step = max <= 6 ? 1 : max <= 15 ? 3 : max <= 40 ? 10 : max <= 90 ? 20 : 30;
  const out: number[] = [];
  for (let t = 0; t <= max + 1e-6; t += step) out.push(t);
  return out;
}

/* ---------- dual-LLM split, drawn ---------- */
export function DualLlmDiagram() {
  return (
    <svg className="arch dual" viewBox="0 0 640 250" role="img"
      aria-label="The raw invoice goes to a reader model that has no tools. It only writes code, which runs in the sandbox. The summary model sees only structured results. The policy engine, plain code, decides; only a human can post.">
      <defs>
        <marker id="dah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--text-3)" /></marker>
      </defs>
      {/* raw doc */}
      <rect className="box" x="10" y="30" width="110" height="56" rx="10" style={{ stroke: "var(--quar)" }} />
      <text className="lbl" x="65" y="55" textAnchor="middle">Raw invoice</text>
      <text className="sub" x="65" y="73" textAnchor="middle">may be hostile</text>

      {/* reader */}
      <rect className="box" x="160" y="22" width="150" height="72" rx="10" />
      <text className="lbl" x="235" y="48" textAnchor="middle">Reader model</text>
      <text className="sub" x="235" y="66" textAnchor="middle">sees raw text</text>
      <g transform="translate(235 82)"><rect x="-38" y="-8" width="76" height="16" rx="8" fill="var(--block-bg)" stroke="var(--block-line)" /><text x="0" y="4" textAnchor="middle" style={{ fontSize: 10, fontWeight: 650, fill: "var(--block)" }}>NO TOOLS</text></g>

      {/* sandbox */}
      <rect className="zone sb" x="350" y="14" width="140" height="88" rx="12" />
      <text className="lbl" x="420" y="50" textAnchor="middle">Its code runs</text>
      <text className="sub" x="420" y="68" textAnchor="middle">in the sandbox</text>

      {/* structured result */}
      <rect className="box" x="520" y="30" width="110" height="56" rx="10" />
      <text className="lbl" x="575" y="55" textAnchor="middle">Typed fields</text>
      <text className="sub" x="575" y="73" textAnchor="middle">+ checks</text>

      {/* summary model */}
      <rect className="box" x="430" y="150" width="200" height="66" rx="10" />
      <text className="lbl" x="530" y="176" textAnchor="middle">Summary model</text>
      <text className="sub" x="530" y="196" textAnchor="middle">never sees the raw document</text>

      {/* policy */}
      <rect className="box" x="190" y="150" width="200" height="66" rx="10" style={{ stroke: "var(--accent)" }} />
      <text className="lbl" x="290" y="176" textAnchor="middle">Policy engine</text>
      <text className="sub" x="290" y="196" textAnchor="middle">plain code, decides</text>

      {/* human */}
      <rect className="box" x="10" y="150" width="120" height="66" rx="10" style={{ stroke: "var(--clear)" }} />
      <text className="lbl" x="70" y="176" textAnchor="middle">Human</text>
      <text className="sub" x="70" y="196" textAnchor="middle">only path to ledger</text>

      <path className="wire flow" d="M120 58 H160" markerEnd="url(#dah)" />
      <path className="wire" d="M310 58 H350" markerEnd="url(#dah)" />
      <text className="sub" x="330" y="50" textAnchor="middle">code</text>
      <path className="wire" d="M490 58 H520" markerEnd="url(#dah)" />
      <path className="wire" d="M575 86 V150" markerEnd="url(#dah)" />
      <path className="wire" d="M540 86 C520 120 330 120 300 150" markerEnd="url(#dah)" />
      <path className="wire" d="M430 183 H390" markerEnd="url(#dah)" />
      <text className="sub" x="410" y="176" textAnchor="middle">words</text>
      <path className="wire" d="M190 183 H130" markerEnd="url(#dah)" />
      <text className="sub" x="160" y="176" textAnchor="middle">outcome</text>
      {/* the summary can't change the outcome */}
      <text className="sub" x="410" y="236" textAnchor="middle">describes the decision, cannot change it</text>
    </svg>
  );
}

/* ---------- policy precedence: four outcomes on one ladder ---------- */
export function PrecedenceLadder({ counts }: { counts: Record<"QUARANTINE" | "BLOCK" | "HOLD", number> }) {
  const steps = [
    { k: "QUARANTINE", t: "Quarantine", c: "var(--quar)", d: "document is hostile" },
    { k: "BLOCK", t: "Block", c: "var(--block)", d: "fraud signal" },
    { k: "HOLD", t: "Hold", c: "var(--hold)", d: "needs a look" },
    { k: "CLEAR", t: "Clear", c: "var(--clear)", d: "no rule fired, waits for a person" },
  ] as const;
  return (
    <div className="ladder" aria-label="Outcome precedence: quarantine beats block beats hold beats clear">
      {steps.map((s, i) => (
        <React.Fragment key={s.k}>
          <div className="lad" style={{ ["--c" as any]: s.c }}>
            <span className="lad-dot" />
            <b>{s.t}</b>
            <span className="muted">{s.k !== "CLEAR" ? `${(counts as any)[s.k]} rules · ` : ""}{s.d}</span>
          </div>
          {i < steps.length - 1 && <svg className="lad-arrow" viewBox="0 0 24 12" aria-hidden><path d="M2 6 H20 M15 1 L21 6 L15 11" fill="none" stroke="var(--text-3)" strokeWidth="1.5" /></svg>}
        </React.Fragment>
      ))}
    </div>
  );
}

/* ---------- paired bars: expected vs predicted per outcome ---------- */
export function PairedBars({ rows }: { rows: { k: string; a: number; b: number }[] }) {
  const max = Math.max(1, ...rows.flatMap((r) => [r.a, r.b]));
  return (
    <div className="pairs">
      <div className="pairs-legend"><span><i className="pa" />Expected</span><span><i className="pb" />Airlock decided</span></div>
      {rows.map((r, i) => (
        <div key={r.k} className="pair">
          <div className="pair-k">{r.k}</div>
          <div className="pair-bars">
            <div className="pb-row" title={`${r.k}: expected ${r.a}`}><motion.i className="pa" initial={{ width: 0 }} whileInView={{ width: `${(r.a / max) * 100}%` }} viewport={{ once: true }} transition={{ duration: 0.7, ease, delay: i * 0.06 }} /><span className="num">{r.a}</span></div>
            <div className="pb-row" title={`${r.k}: decided ${r.b}`}><motion.i className="pb" initial={{ width: 0 }} whileInView={{ width: `${(r.b / max) * 100}%` }} viewport={{ once: true }} transition={{ duration: 0.7, ease, delay: i * 0.06 + 0.05 }} /><span className="num">{r.b}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}
