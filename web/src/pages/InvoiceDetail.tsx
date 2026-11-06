import React from "react";
import { Link, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowLeft, ArrowRight, Ban, Box, Check, CheckCircle2, Code2, Cpu, Download, EyeOff, FileSignature, Gavel, Globe,
  KeyRound, Loader2, MessageSquare, PauseCircle, Play, RefreshCw, ScanLine, ServerOff, ShieldAlert, ShieldCheck,
  Sparkles, Trash2, UserCheck, X, XCircle,
} from "lucide-react";
import { api, errMsg, Invoice, Run } from "../api";
import { isProcessing, toneOf } from "../pipeline";
import { Callout, CopyButton, Drawer, Pipeline, Seg, Sk, StatusBadge, TONE_TITLE, ease, money, useToast } from "../ui";
import { Ring, RunTimeline } from "../viz";

type Ev = { id: number; type: string; ts: string; payload: any };

function evView(e: Ev): { t: string; d?: string; icon: React.ReactNode; tone?: string } {
  const p = e.payload || {};
  switch (e.type) {
    case "state.changed": return { t: STATE_NAME[p.to] || `→ ${p.to}`, icon: <ArrowRight />, tone: p.to === "QUARANTINED" ? "quar" : p.to === "BLOCKED" || p.to === "REJECTED" ? "bad" : p.to === "POSTED" ? "ok" : p.to === "HELD" ? "warn" : undefined };
    case "llm.call": return { t: `Model call · ${p.role}`, d: `${p.model} · ${p.completion_tokens || 0} tokens`, icon: <MessageSquare /> };
    case "code.generated": return { t: `The model wrote parsing code (attempt ${p.attempt})`, d: (p.static_flags || []).length ? `Flagged: ${p.static_flags.join(", ")}` : "No risky calls flagged by static checks", icon: <Code2 />, tone: (p.static_flags || []).length ? "warn" : undefined };
    case "sandbox.created": return { t: "Sandbox started", d: `${p.container_id} · ${p.tier} · network ${p.isolation?.network ?? "none"}`, icon: <Box />, tone: "proc" };
    case "sandbox.finished": return { t: "Sandbox finished", d: `exit ${p.exit_code}${p.killed_reason ? ` · killed: ${p.killed_reason}` : ""} · ${p.duration_ms} ms`, icon: <Check /> };
    case "sandbox.destroyed": return { t: "Sandbox destroyed", d: "Container and its files deleted", icon: <Trash2 />, tone: "ok" };
    case "sandbox.retry": return { t: "Retrying after an error", d: String(p.stderr_tail || "").trim().split("\n").filter(Boolean).pop()?.slice(-160), icon: <RefreshCw />, tone: "warn" };
    case "egress.attempt": return { t: "Outbound connection blocked", d: p.detail, icon: <ServerOff />, tone: "bad" };
    case "detector.hit": return { t: p.injection_suspected ? "Hidden instructions detected" : "Injection detectors ran", d: `${(p.hidden_text || []).length} hidden text run(s)${p.classifier_score != null ? ` · classifier ${Number(p.classifier_score).toFixed(2)}` : ""}`, icon: <EyeOff />, tone: p.injection_suspected ? "quar" : undefined };
    case "check.result": return { t: `${CHECK_NAME[p.check_id] || p.check_id}`, d: p.detail, icon: p.passed ? <Check /> : <X />, tone: p.passed ? "ok" : "bad" };
    case "check.disagreement": return { t: `Sandbox and control plane disagree: ${p.check_id}`, d: `sandbox=${p.sandbox}, authoritative=${p.authoritative}`, icon: <ShieldAlert />, tone: "bad" };
    case "browser.verdict": return { t: p.credential_harvest ? "Phishing page detected" : "Linked page inspected", d: p.final_url, icon: <Globe />, tone: p.credential_harvest ? "quar" : "ok" };
    case "policy.decision": return { t: `Policy decided: ${String(p.outcome).toLowerCase()}`, d: (p.rules_fired || []).map((r: any) => `${r.id} ${r.message || ""}`.trim()).join(" · ") || "No rules fired", icon: <Gavel />, tone: p.outcome === "CLEAR" ? "ok" : p.outcome === "QUARANTINE" ? "quar" : p.outcome === "HOLD" ? "warn" : "bad" };
    case "approval.requested": return { t: "Waiting for a human to approve", d: `${p.currency} ${p.amount}`, icon: <UserCheck />, tone: "proc" };
    case "approval.decided": return { t: `Reviewer ${p.decision === "approve" ? "approved" : "rejected"} the payment`, icon: <UserCheck />, tone: p.decision === "approve" ? "ok" : "bad" };
    case "erp.posted": return { t: "Posted to the ERP", d: `${p.currency} ${p.amount}`, icon: <CheckCircle2 />, tone: "ok" };
    case "blast_radius": return { t: "Blast radius measured", d: `${p.secrets_exposed} secrets · ${p.outbound_connections} outbound · ${p.host_files_written} host files`, icon: <ShieldCheck />, tone: "ok" };
    case "evidence.sealed": return { t: "Evidence signed and sealed", d: `sha256 ${p.manifest_sha256?.slice(0, 16)}…`, icon: <FileSignature />, tone: "ok" };
    case "checks.summary": return p.failed.length
      ? { t: `${p.failed.length} of ${p.n} checks failed`, d: p.failed.map((c: string) => CHECK_NAME[c] || c).join(", "), icon: <X />, tone: "bad" }
      : { t: `All ${p.n} checks passed`, d: "Details in the Checks panel", icon: <Check />, tone: "ok" };
    default: return { t: e.type, d: JSON.stringify(p).slice(0, 120), icon: <Sparkles /> };
  }
}
const STATE_NAME: Record<string, string> = {
  SCANNING: "Scanning the PDF", EXTRACTING: "Extracting fields", VALIDATING: "Validating against vendor master",
  INSPECTING_LINKS: "Opening links in a sandboxed browser", DECIDING: "Policy engine deciding", AWAIT_APPROVAL: "Cleared, awaiting approval",
  POSTED: "Posted", REJECTED: "Rejected", BLOCKED: "Blocked", HELD: "Held for review", QUARANTINED: "Quarantined", ERROR: "Error, held",
};
const CHECK_NAME: Record<string, string> = {
  vendor_known: "Vendor is known", arith: "Totals add up", iban_valid: "IBAN is valid", bank_matches_master: "Bank matches vendor master",
  sender_domain: "Sender domain on file", duplicate: "Not a duplicate", po_exists: "PO exists", three_way_qty: "3-way match (quantity)",
  three_way_price: "3-way match (price)", currency: "Currency matches PO",
};

export function InvoiceDetail() {
  const { id } = useParams();
  const toast = useToast();
  const [inv, setInv] = React.useState<Invoice | null>(null);
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [events, setEvents] = React.useState<Ev[]>([]);
  const [openRun, setOpenRun] = React.useState<Run | null>(null);
  const [busy, setBusy] = React.useState<"" | "process" | "approve" | "reject">("");
  const [err, setErr] = React.useState<string | null>(null);
  const [showAll, setShowAll] = React.useState(false);

  const refresh = React.useCallback(() => {
    if (!id) return;
    api.invoice(id).then((d) => { setInv(d.invoice); setRuns(d.runs); setEvents(d.events); setErr(null); }).catch((e) => setErr(errMsg(e)));
  }, [id]);

  React.useEffect(() => {
    refresh();
    const es = new EventSource(`/api/invoices/${id}/events`);
    const onAny = () => refresh();
    ["state.changed", "sandbox.created", "sandbox.finished", "sandbox.destroyed", "code.generated", "check.result", "policy.decision",
     "approval.requested", "erp.posted", "evidence.sealed", "blast_radius", "detector.hit", "browser.verdict"].forEach((t) => es.addEventListener(t, onAny));
    es.onerror = () => {};
    return () => es.close();
  }, [id, refresh]);
  // Safety net if the event stream drops while processing.
  React.useEffect(() => {
    if (!inv || !isProcessing(inv)) return;
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [inv?.status, inv?.queued, refresh]);

  const openRunById = (rid: string) => api.run(rid).then(setOpenRun).catch((e) => toast({ kind: "err", title: "Couldn't load the run", detail: errMsg(e) }));

  if (err && !inv) return <div><BackLink /><Callout kind="bad">Couldn't load this invoice. It may belong to another demo workspace, or the demo was reset.</Callout></div>;
  if (!inv) return <DetailSkeleton />;

  const f = inv.fields;
  const tone = toneOf(inv.status, inv.queued);
  const process = async () => {
    setBusy("process");
    try { await api.process(inv.id); toast({ kind: "info", title: "Processing started", detail: "Watch each stage light up below." }); refresh(); }
    catch (e) { toast({ kind: "err", title: "Couldn't start processing", detail: errMsg(e) }); }
    setTimeout(() => setBusy(""), 600);
  };
  const decide = async (d: "approve" | "reject") => {
    setBusy(d);
    try {
      await api.decide(inv.id, d);
      toast(d === "approve" ? { kind: "ok", title: `Approved: ${money(f)} posted`, detail: "The payment is in the ledger and the evidence is signed." } : { kind: "info", title: "Payment rejected", detail: "Nothing was posted." });
      refresh();
    } catch (e) { toast({ kind: "err", title: "Decision failed", detail: errMsg(e) }); }
    setBusy("");
  };
  const t0 = events.length ? +new Date(events[0].ts) : 0;
  const visibleEvents: Ev[] = showAll ? events : events.reduce((acc: Ev[], e) => {
    if (e.type === "llm.call") return acc;
    if (e.type === "check.result") {
      const last = acc[acc.length - 1];
      if (last?.type === "checks.summary") { last.payload.n++; if (!e.payload?.passed) last.payload.failed.push(e.payload?.check_id); return acc; }
      acc.push({ id: e.id, ts: e.ts, type: "checks.summary", payload: { n: 1, failed: e.payload?.passed ? [] : [e.payload?.check_id] } });
      return acc;
    }
    acc.push(e); return acc;
  }, []);
  const hidden: string[] = inv.detectors?.hidden_text || [];
  const terminal = ["QUARANTINED", "BLOCKED", "POSTED", "HELD", "REJECTED", "ERROR"].includes(inv.status);

  return (
    <div>
      <BackLink />
      <div className="ph" style={{ marginBottom: 20 }}>
        <div className="ph-text">
          <div className="row" style={{ gap: 12 }}>
            <h1>{f?.vendor_name || inv.title}</h1>
            <StatusBadge status={inv.status} queued={inv.queued} />
          </div>
          <p className="row" style={{ gap: 8 }}>
            {[
              f?.invoice_number && <span key="n" className="mono">{f.invoice_number}</span>,
              money(f) && <span key="m" className="mono num" style={{ color: "var(--text)" }}>{money(f)}</span>,
              f?.vendor_name ? <span key="t">{inv.title}</span> : <span key="t" className="mono">{inv.filename}</span>,
            ].filter(Boolean).flatMap((el, i) => (i ? [<span key={`s${i}`} className="muted">·</span>, el] : [el]))}
          </p>
        </div>
        <div className="ph-actions">
          {inv.status === "NEW" && !inv.queued && <button className="btn" onClick={process} disabled={!!busy}>{busy === "process" ? <Loader2 className="spin" /> : <Play />}Process invoice</button>}
          {terminal && <Link className="btn secondary" to={`/receipts/${inv.id}`}><FileSignature />Signed receipt</Link>}
        </div>
      </div>

      <div className="panel" style={{ padding: "26px 22px 14px", marginBottom: 16 }}>
        <Pipeline inv={inv} />
      </div>

      <AnimatePresence mode="popLayout">
        {inv.status === "NEW" && !inv.queued && (
          <motion.div key="new" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ marginBottom: 16 }}>
            <Callout kind="info">This invoice hasn't been opened yet. <b style={{ color: "var(--text)" }}>Process it</b> to scan, extract and validate it inside a fresh sandbox. The sandbox is destroyed when the run ends.</Callout>
          </motion.div>
        )}
        {inv.status === "ERROR" && (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ marginBottom: 16 }}>
            <Callout kind="warn"><b style={{ color: "var(--text)" }}>Processing stopped, so the invoice is held.</b> Nothing was posted, and the sandbox was still destroyed.
              {inv.error && <div className="err-line" style={{ marginTop: 6 }}>{String(inv.error).split("\n")[0].slice(0, 180)}</div>}</Callout>
          </motion.div>
        )}
        {inv.summary && (
          <motion.div key={`v-${inv.status}`} initial={{ opacity: 0, y: 10, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} transition={{ duration: 0.55, ease }} style={{ marginBottom: 16 }}>
            <Verdict inv={inv} tone={tone} />
          </motion.div>
        )}
        {inv.status === "AWAIT_APPROVAL" && (
          <motion.div key="approve" className="panel" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.4, ease, delay: 0.15 }} style={{ marginBottom: 16 }}>
            <div className="panel-b row" style={{ gap: 16 }}>
              <div className="stamp" style={{ ["--c" as any]: "var(--accent)", ["--bgc" as any]: "var(--accent-soft)", ["--lc" as any]: "var(--accent-line)", width: 44, height: 44, borderRadius: 12 }}><UserCheck size={20} /></div>
              <div className="grow" style={{ minWidth: 220 }}>
                <h2>Your approval is needed</h2>
                <p className="dim" style={{ marginTop: 2 }}>No model can post a payment. Approving posts <b className="mono" style={{ color: "var(--text)" }}>{money(f)}</b> to the ledger and seals the evidence.</p>
              </div>
              <button className="btn danger" onClick={() => decide("reject")} disabled={!!busy}>{busy === "reject" ? <Loader2 className="spin" /> : <XCircle />}Reject</button>
              <button className="btn success" onClick={() => decide("approve")} disabled={!!busy}>{busy === "approve" ? <Loader2 className="spin" /> : <Check />}Approve &amp; post</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="split">
        <div className="panel">
          <div className="panel-h">
            <h2>What happened</h2>
            <span className="sub">{events.length ? `${events.length} events` : ""}</span>
            <div className="right">
              {events.length > 0 && (
                <button className="btn ghost sm" onClick={() => setShowAll((s) => !s)}>{showAll ? "Compact view" : "Show every event"}</button>
              )}
            </div>
          </div>
          <div className="panel-b">
            {events.length === 0 && <p className="muted">Nothing yet. Events stream in here while the invoice is processed.</p>}
            <div className="tl">
              <AnimatePresence initial={false}>
                {visibleEvents.map((e) => {
                  const v = evView(e);
                  const run = e.type === "code.generated" ? runs.find((r) => r.kind === "extract" && r.attempt === e.payload.attempt) : undefined;
                  return (
                    <motion.div key={e.id} className={`tl-item ${v.tone || ""}`} layout="position"
                      initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, ease }}>
                      <div className="tl-ic">{v.icon}</div>
                      <div style={{ minWidth: 0 }}>
                        <div className="tl-t">{v.t}</div>
                        {v.d && <div className="tl-d">{v.d}</div>}
                        {run && <button className="btn secondary sm" style={{ marginTop: 6 }} onClick={() => openRunById(run.id)}><Code2 />View the code</button>}
                      </div>
                      <div className="tl-ts" title={e.ts}>+{((+new Date(e.ts) - t0) / 1000).toFixed(1)}s</div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className="stack">
          {hidden.length > 0 && (
            <div className="panel" style={{ borderColor: "var(--quar-line)" }}>
              <div className="panel-h"><EyeOff size={16} color="var(--quar)" /><h2>Hidden text found in the PDF</h2></div>
              <div className="panel-b">
                <p className="dim" style={{ fontSize: 13 }}>Invisible to a person reading the invoice and aimed at AI tools. Shown here as inert text.</p>
                <pre className="code" style={{ marginTop: 10, borderColor: "var(--quar-line)", background: "var(--quar-bg)", whiteSpace: "pre-wrap", maxHeight: 220 }}>{hidden.join("\n")}</pre>
              </div>
            </div>
          )}

          {f && (
            <div className="panel">
              <div className="panel-h"><h2>Extracted fields</h2><span className="sub">by code the model wrote, run in the sandbox</span></div>
              <div className="panel-b">
                <dl className="kv">
                  <dt>Vendor</dt><dd>{f.vendor_name || "—"}</dd>
                  <dt>Sender</dt><dd className="mono">{f.sender_email || "—"}</dd>
                  <dt>Invoice #</dt><dd className="mono">{f.invoice_number || "—"}</dd>
                  <dt>PO</dt><dd className="mono">{f.po_number || "—"}</dd>
                  <dt>Bank</dt><dd className="mono">{f.bank?.iban || f.bank?.account_number || "—"}</dd>
                  <dt>Total</dt><dd className="mono num">{money(f) || "—"}</dd>
                  {f.links?.length > 0 && <><dt>Links</dt><dd className="mono" style={{ fontSize: 12 }}>{f.links.join(", ")}</dd></>}
                </dl>
              </div>
            </div>
          )}

          {inv.policy?.checks && (
            <div className="panel">
              <div className="panel-h">
                <Ring size={44} passed={inv.policy.checks.filter((c: any) => c.passed).length} total={inv.policy.checks.length} />
                <div><h2>Checks</h2><span className="sub">recomputed outside the sandbox</span></div>
                <span className="right"><span className={`tag ${inv.policy.checks.every((c: any) => c.passed) ? "ok" : "bad"}`}>{inv.policy.checks.every((c: any) => c.passed) ? "all pass" : `${inv.policy.checks.filter((c: any) => !c.passed).length} failed`}</span></span>
              </div>
              <div className="panel-b" style={{ paddingTop: 6, paddingBottom: 6 }}>
                <div className="checks">
                  {inv.policy.checks.map((c: any) => (
                    <div key={c.id} className={`check ${c.passed ? "pass" : "fail"}`}>
                      {c.passed ? <CheckCircle2 /> : <XCircle />}
                      <div><b>{CHECK_NAME[c.id] || c.id}</b><div className="d">{c.detail}</div></div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {inv.browser && inv.browser.length > 0 && <BrowserEvidence browser={inv.browser} runs={runs} onOpen={openRunById} />}

          <div className="panel">
            <div className="panel-h"><h2>Sandbox runs</h2><span className="sub">each one a fresh container, destroyed after</span></div>
            {runs.length === 0 && <div className="panel-b muted">None yet.</div>}
            {runs.length > 0 && <RunTimeline runs={runs} onOpen={openRunById} />}
            {runs.map((r) => (
              <button key={r.id} className="run-row" onClick={() => openRunById(r.id)}>
                <span className="run-k"><Cpu size={14} />{r.kind}{r.attempt > 1 ? ` #${r.attempt}` : ""}</span>
                <span className="mono muted" style={{ fontSize: 12 }}>{r.container_id}</span>
                <span className="grow" />
                {r.killed_reason && <span className="tag bad">{r.killed_reason}</span>}
                <span className="mono muted num" style={{ fontSize: 12 }}>{(r.duration_ms / 1000).toFixed(1)} s</span>
                <ArrowRight size={14} className="muted" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <Drawer open={!!openRun} onClose={() => setOpenRun(null)} title={openRun ? <>Sandbox run · <span className="mono">{openRun.kind}{openRun.attempt > 1 ? ` #${openRun.attempt}` : ""}</span></> : ""}>
        {openRun && <RunDetail run={openRun} />}
      </Drawer>
    </div>
  );
}

function BackLink() {
  return <Link to="/inbox" className="crumb"><ArrowLeft />Inbox</Link>;
}

function DetailSkeleton() {
  return (
    <div>
      <BackLink />
      <Sk w={280} h={28} /><div style={{ height: 10 }} /><Sk w={220} />
      <div style={{ height: 24 }} />
      <div className="panel" style={{ padding: 24 }}><Sk h={90} /></div>
      <div style={{ height: 16 }} />
      <div className="split"><div className="panel" style={{ padding: 20 }}>{[0, 1, 2, 3, 4].map((i) => <div key={i} style={{ marginBottom: 14 }}><Sk w="70%" /></div>)}</div><div className="panel" style={{ padding: 20 }}><Sk h={120} /></div></div>
    </div>
  );
}

function Verdict({ inv, tone }: { inv: Invoice; tone: string }) {
  const s = inv.summary;
  const br = inv.blast_radius;
  const contained = tone === "quar" || tone === "block";
  const icon = tone === "quar" ? <ShieldAlert /> : tone === "block" ? <Ban /> : tone === "hold" ? <PauseCircle /> : tone === "done" ? <CheckCircle2 /> : <ShieldCheck />;
  const kicker = contained ? `Contained · ${TONE_TITLE[tone as keyof typeof TONE_TITLE]}` : tone === "done" ? "Approved and posted" : tone === "clear" ? "Cleared by policy" : TONE_TITLE[tone as keyof typeof TONE_TITLE];
  return (
    <div className={`verdict ${tone}`}>
      <div className="verdict-band" />
      <div className="verdict-in">
        <motion.div className="stamp" initial={{ scale: 1.5, opacity: 0, rotate: -8 }} animate={{ scale: 1, opacity: 1, rotate: 0 }} transition={{ duration: 0.45, ease, delay: 0.1 }}>{icon}</motion.div>
        <div style={{ minWidth: 0 }}>
          <div className="vk">{kicker}</div>
          <h2>{s.headline}</h2>
          {s.reasons?.length > 0 && <ul>{s.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>}
          {s.recommended_action && <div className="rec"><ArrowRight />{s.recommended_action}</div>}
        </div>
      </div>
      {br && (
        <>
          <div className="blast-h"><ShieldCheck />Blast radius, measured</div>
          <div className="blast">
            {([["secrets_exposed", "secrets exposed", <KeyRound key="k" />], ["outbound_connections", "outbound connections", <Globe key="g" />], ["host_files_written", "host files written", <ServerOff key="s" />]] as const).map(([k, l], i) => (
              <motion.div key={k} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 + i * 0.08, duration: 0.35, ease }}>
                <div className={`n ${br[k] === 0 ? "zero" : ""}`}>{br[k]}{br[k] === 0 && <Check />}</div>
                <div className="l">{l}</div>
              </motion.div>
            ))}
            {br.blocked_egress_attempts > 0 && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6, duration: 0.35, ease }}>
                <div className="n warn">{br.blocked_egress_attempts}</div><div className="l">egress attempts blocked</div>
              </motion.div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function BrowserEvidence({ browser, runs, onOpen }: { browser: any[]; runs: Run[]; onOpen: (id: string) => void }) {
  const [zoom, setZoom] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (!zoom) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && setZoom(null);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [zoom]);
  return (
    <div className="panel">
      <div className="panel-h"><Globe size={16} /><h2>Link inspection</h2><span className="sub">sandboxed browser behind an egress proxy</span></div>
      <div className="panel-b stack" style={{ gap: 18 }}>
        {browser.map((b, i) => {
          const run = runs.find((r) => r.id === b.run_id);
          const shots = run?.artifacts?.filter((a: any) => a.name?.endsWith(".png") && a.key) || [];
          const shotUrl = (a: any) => `/api/runs/${run!.id}/screenshots/${encodeURIComponent(a.name)}`;
          return (
            <div key={i} className="stack" style={{ gap: 10 }}>
              <div className="row" style={{ gap: 8 }}>
                <span className={`badge ${b.credential_harvest ? "quar" : "clear"}`}>{b.credential_harvest ? <ShieldAlert /> : <ShieldCheck />}{b.credential_harvest ? "Credential harvest" : "Looks legitimate"}</span>
                {b.confidence != null && <span className="muted" style={{ fontSize: 12 }}>confidence {Math.round(b.confidence * 100)}%</span>}
              </div>
              <div className="mono" style={{ fontSize: 12, overflowWrap: "anywhere", color: "var(--text-2)" }}>{b.final_url}</div>
              {(b.reasons || []).length > 0 && <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text-2)", fontSize: 13, display: "grid", gap: 3 }}>{b.reasons.map((r: string, j: number) => <li key={j}>{r}</li>)}</ul>}
              {shots.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
                  {shots.map((a: any) => (
                    <button key={a.key} className="shot-btn" onClick={() => setZoom(shotUrl(a))} aria-label={`Open screenshot ${a.name}`}>
                      <img src={shotUrl(a)} alt={`Screenshot: ${a.name}`} onError={(e) => ((e.currentTarget.parentElement as HTMLElement).style.display = "none")} />
                      <span>{a.name}</span>
                    </button>
                  ))}
                </div>
              )}
              {run && <Containment run={run} />}
              {!run && b.downloads_seen > 0 && <div className="tag bad">{b.downloads_seen} download(s) quarantined, never opened</div>}
              {run && <div><button className="btn secondary sm" onClick={() => onOpen(run.id)}><Globe />Proxy log &amp; details</button></div>}
            </div>
          );
        })}
      </div>
      <AnimatePresence>
        {zoom && (
          <motion.div className="lightbox" role="dialog" aria-modal="true" aria-label="Screenshot" onClick={() => setZoom(null)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button className="lb-close" aria-label="Close screenshot" onClick={() => setZoom(null)}><X size={18} /></button>
            <motion.img src={zoom} alt="Screenshot" initial={{ scale: 0.94 }} animate={{ scale: 1 }} transition={{ duration: 0.3, ease }} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Only states what was measured: download hash, CPU limit, proxy denials, container lifetime.
function Containment({ run }: { run: Run }) {
  const x = run.extra || {};
  const downloads: any[] = x.downloads || [];
  const denied = (x.proxy_log || []).filter((e: any) => e.decision === "deny").length;
  const burn = x.page_cpu_counter;
  const items: React.ReactNode[] = [];
  downloads.forEach((d, i) => items.push(
    <li key={`d${i}`}><Download size={14} /><span>Download <span className="mono">{d.name}</span> quarantined, never opened · sha256 <span className="mono">{String(d.sha256).slice(0, 8)}…{String(d.sha256).slice(-4)}</span> · {d.size} B</span></li>));
  if (burn != null) items.push(<li key="cpu"><Cpu size={14} /><span>Page ran a CPU busy-loop ({Number(burn).toLocaleString()} iterations) inside a {run.limits?.cpus ?? "?"}-CPU, {run.limits?.memory_mb ?? "?"} MB sandbox</span></li>);
  if (denied > 0) items.push(<li key="deny"><ServerOff size={14} /><span>{denied} request(s) denied by the egress proxy</span></li>);
  if (run.destroyed_at) items.push(<li key="life"><Trash2 size={14} /><span>Container destroyed after {(run.duration_ms / 1000).toFixed(1)} s ({run.tier})</span></li>);
  if (!items.length) return null;
  return <ul className="contain">{items}</ul>;
}

function RunDetail({ run }: { run: Run }) {
  const tabs = [
    run.code && { value: "code", label: "Code the model wrote" },
    (run.stdout || run.stderr) && { value: "out", label: "Output" },
    run.extra?.proxy_log?.length > 0 && { value: "proxy", label: "Egress log" },
  ].filter(Boolean) as { value: string; label: string }[];
  const [tab, setTab] = React.useState(tabs[0]?.value || "");
  const iso = run.isolation || {};
  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="iso-grid">
        <IsoCell ok={iso.network === "none"} label="Network" value={iso.network ?? "—"} />
        <IsoCell ok={iso.env_vars_passed === 0} label="Env vars passed" value={String(iso.env_vars_passed ?? "—")} />
        <IsoCell ok={!!iso.read_only_root} label="Root filesystem" value={iso.read_only_root ? "read-only" : "writable"} />
        <IsoCell ok={iso.runtime === "runsc"} label="Runtime" value={`${iso.runtime ?? "—"} · ${run.tier}`} />
      </div>
      <dl className="kv">
        <dt>Container</dt><dd className="mono">{run.container_id}</dd>
        <dt>Image</dt><dd className="mono" style={{ fontSize: 12 }}>{run.image_digest}</dd>
        <dt>User</dt><dd className="mono">{iso.user ?? "—"}</dd>
        <dt>Limits</dt><dd className="mono">{run.limits?.memory_mb} MB · {run.limits?.cpus} CPU · {run.limits?.pids} pids · {run.limits?.timeout_s} s</dd>
        <dt>Lifetime</dt><dd className="mono">{run.created_at?.slice(11, 23)} → {run.destroyed_at?.slice(11, 23) || "running"} ({(run.duration_ms / 1000).toFixed(2)} s)</dd>
        <dt>Exit</dt><dd className="mono">{String(run.exit_code)}{run.killed_reason ? ` · killed: ${run.killed_reason}` : ""}</dd>
        {run.peak_mem_mb != null && <><dt>Peak memory</dt><dd className="mono">{run.peak_mem_mb} MB</dd></>}
      </dl>
      {run.static_flags?.length > 0 && <div className="row" style={{ gap: 6 }}><span className="muted" style={{ fontSize: 12.5 }}>Static flags</span>{run.static_flags.map((fl) => <span key={fl} className="tag bad">{fl}</span>)}</div>}
      {tabs.length > 0 && (
        <div>
          <div className="row"><Seg id="run" value={tab} onChange={setTab} items={tabs} /><span className="grow" />
            {tab === "code" && run.code && <CopyButton text={run.code} />}
          </div>
          <div style={{ marginTop: 12 }}>
            {tab === "code" && <pre className="code" style={{ maxHeight: "none" }}>{run.code}</pre>}
            {tab === "out" && <>
              {run.stdout && <><div className="code-head">stdout</div><pre className="code">{run.stdout}</pre></>}
              {run.stderr && <><div className="code-head">stderr</div><pre className="code">{run.stderr}</pre></>}
            </>}
            {tab === "proxy" && <pre className="code">{run.extra.proxy_log.map((e: any) => `${String(e.decision).toUpperCase().padEnd(6)} ${e.host} ${e.reason || ""}`).join("\n")}</pre>}
          </div>
        </div>
      )}
    </div>
  );
}

function IsoCell({ ok, label, value }: { ok: boolean; label: string; value: string }) {
  return (
    <div className={`iso ${ok ? "ok" : ""}`}>
      <div className="l">{ok ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}{label}</div>
      <div className="v mono">{value}</div>
    </div>
  );
}
