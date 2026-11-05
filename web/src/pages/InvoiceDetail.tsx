import React from "react";
import { Link, useParams } from "react-router-dom";
import { api, Invoice, Run } from "../api";
import { Chip, money } from "../components";

const EV_CLASS: Record<string, string> = {
  "policy.decision": "warn", "detector.hit": "warn", "egress.attempt": "bad",
  "sandbox.destroyed": "ok", "erp.posted": "ok", "evidence.sealed": "ok",
  "check.disagreement": "bad", "blast_radius": "ok", "browser.verdict": "warn",
};

function evLabel(e: any): { t: string; d: string } {
  const p = e.payload || {};
  switch (e.type) {
    case "state.changed": return { t: `→ ${p.to}`, d: `from ${p.from}` };
    case "llm.call": return { t: "LLM call", d: `${p.role} · ${p.model} · ${p.completion_tokens || 0} tok` };
    case "code.generated": return { t: `Model wrote code (attempt ${p.attempt})`, d: (p.static_flags || []).length ? `flags: ${p.static_flags.join(", ")}` : "no risky calls flagged" };
    case "sandbox.created": return { t: `Sandbox started`, d: `${p.container_id} · ${p.tier} · ${p.isolation?.network}` };
    case "sandbox.finished": return { t: `Sandbox finished`, d: `exit ${p.exit_code}${p.killed_reason ? ` · killed: ${p.killed_reason}` : ""} · ${p.duration_ms}ms` };
    case "sandbox.destroyed": return { t: "Sandbox destroyed", d: p.destroyed_at };
    case "sandbox.retry": return { t: `Retry after error`, d: (p.stderr_tail || "").slice(-120) };
    case "egress.attempt": return { t: "Egress attempt blocked", d: p.detail };
    case "detector.hit": return { t: "Detectors ran", d: `${p.injection_suspected ? "INJECTION SUSPECTED · " : ""}${(p.hidden_text || []).length} hidden run(s)${p.classifier_score != null ? ` · classifier ${p.classifier_score}` : ""}` };
    case "check.result": return { t: `Check: ${p.check_id}`, d: `${p.passed ? "pass" : "FAIL"} — ${p.detail}` };
    case "check.disagreement": return { t: `⚠ Sandbox/control disagreement: ${p.check_id}`, d: `sandbox=${p.sandbox} authoritative=${p.authoritative}` };
    case "browser.verdict": return { t: "Browser verdict", d: `${p.credential_harvest ? "CREDENTIAL HARVEST" : "looks ok"} · ${p.final_url}` };
    case "policy.decision": return { t: `Policy: ${p.outcome}`, d: (p.rules_fired || []).map((r: any) => r.id).join(", ") || "no rules fired" };
    case "approval.requested": return { t: "Awaiting human approval", d: `${p.currency} ${p.amount}` };
    case "approval.decided": return { t: `Human ${p.decision}d`, d: "" };
    case "erp.posted": return { t: "Posted to ERP", d: `${p.currency} ${p.amount}` };
    case "blast_radius": return { t: "Blast radius measured", d: `${p.secrets_exposed} secrets · ${p.outbound_connections} outbound · ${p.host_files_written} host files` };
    case "evidence.sealed": return { t: "Evidence sealed (signed)", d: p.manifest_sha256?.slice(0, 16) };
    default: return { t: e.type, d: JSON.stringify(p).slice(0, 120) };
  }
}

export function InvoiceDetail() {
  const { id } = useParams();
  const [inv, setInv] = React.useState<Invoice | null>(null);
  const [runs, setRuns] = React.useState<Run[]>([]);
  const [events, setEvents] = React.useState<any[]>([]);
  const [openRun, setOpenRun] = React.useState<Run | null>(null);
  const [busy, setBusy] = React.useState(false);

  const refresh = React.useCallback(() => {
    if (!id) return;
    api.invoice(id).then((d) => { setInv(d.invoice); setRuns(d.runs); setEvents(d.events); }).catch(() => {});
  }, [id]);

  React.useEffect(() => {
    refresh();
    const es = new EventSource(`/api/invoices/${id}/events`);
    const onAny = () => refresh();
    ["state.changed", "sandbox.finished", "policy.decision", "approval.requested", "erp.posted",
     "evidence.sealed", "blast_radius", "detector.hit", "browser.verdict"].forEach((t) => es.addEventListener(t, onAny));
    es.onerror = () => {};
    return () => es.close();
  }, [id, refresh]);

  if (!inv) return <div className="muted">loading…</div>;
  const f = inv.fields;
  const pol = inv.policy;
  const contained = ["QUARANTINED", "BLOCKED"].includes(inv.status);
  const process = async () => { setBusy(true); await api.process(inv.id).catch(() => {}); setTimeout(() => setBusy(false), 800); };
  const decide = async (d: "approve" | "reject") => { setBusy(true); await api.decide(inv.id, d).catch((e) => alert(e)); refresh(); setBusy(false); };

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <Link to="/" className="muted">← Inbox</Link>
        <span className="spacer" />
        {inv.status === "NEW" && <button className="btn" onClick={process} disabled={busy}>Process invoice</button>}
      </div>
      <div className="row" style={{ marginBottom: 16 }}>
        <div>
          <h1>{f?.vendor_name || inv.title}</h1>
          <div className="muted mono">{f?.invoice_number} · {money(f)} {inv.source === "seed" && inv.expected && <span className="muted"> · demo-expected: {inv.expected}</span>}</div>
        </div>
        <span className="spacer" />
        <Chip status={inv.status} />
      </div>

      {inv.summary && (
        <div className={`banner ${contained ? (inv.status === "QUARANTINED" ? "quar" : "block") : "clear"}`}>
          <h2>{contained ? "⛔ CONTAINED" : inv.status === "POSTED" ? "✓ Posted" : inv.summary.headline}</h2>
          <div>{inv.summary.headline}</div>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {(inv.summary.reasons || []).map((r: string, i: number) => <li key={i}>{r}</li>)}
          </ul>
          {inv.summary.recommended_action && <div style={{ marginTop: 8 }} className="muted">→ {inv.summary.recommended_action}</div>}
          {inv.blast_radius && (
            <div className="blast">
              {[["secrets_exposed", "secrets exposed"], ["outbound_connections", "outbound connections"], ["host_files_written", "host files written"]].map(([k, l]) => (
                <div key={k}><div className={`n ${inv.blast_radius[k] === 0 ? "z" : ""}`}>{inv.blast_radius[k]}</div><div className="muted">{l}</div></div>
              ))}
              {inv.blast_radius.blocked_egress_attempts > 0 && <div><div className="n" style={{ color: "var(--warn)" }}>{inv.blast_radius.blocked_egress_attempts}</div><div className="muted">blocked egress attempts</div></div>}
            </div>
          )}
        </div>
      )}

      {inv.status === "AWAIT_APPROVAL" && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Human approval required</h2>
          <div className="muted">No model can post this payment. A person must approve.</div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn ok" onClick={() => decide("approve")} disabled={busy}>Approve &amp; post {money(f)}</button>
            <button className="btn bad" onClick={() => decide("reject")} disabled={busy}>Reject</button>
          </div>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1.2fr 1fr" }}>
        <div className="card">
          <h2>Pipeline timeline</h2>
          <div className="timeline">
            {events.map((e) => {
              const { t, d } = evLabel(e);
              return (
                <div key={e.id} className={`ev ${EV_CLASS[e.type] || ""}`}>
                  <div className="t">{t}</div>
                  {d && <div className="d">{d}</div>}
                  {e.type === "code.generated" && <RunLink runs={runs} kind="extract" attempt={e.payload.attempt} onOpen={setOpenRun} />}
                </div>
              );
            })}
            {events.length === 0 && <div className="muted">Not processed yet.</div>}
          </div>
        </div>

        <div className="grid">
          {f && (
            <div className="card">
              <h2>Extracted fields</h2>
              <div className="kv">
                <div className="k">Vendor</div><div>{f.vendor_name}</div>
                <div className="k">Sender</div><div className="mono">{f.sender_email}</div>
                <div className="k">PO</div><div className="mono">{f.po_number || "—"}</div>
                <div className="k">Bank</div><div className="mono">{f.bank?.iban || f.bank?.account_number || "—"}</div>
                <div className="k">Total</div><div className="mono">{money(f)}</div>
                {f.links?.length > 0 && <><div className="k">Links</div><div className="mono" style={{ wordBreak: "break-all" }}>{f.links.join(", ")}</div></>}
              </div>
            </div>
          )}
          {pol?.checks && (
            <div className="card">
              <h2>Checks (recomputed in the control plane)</h2>
              {pol.checks.map((c: any) => (
                <div key={c.id} className={`check ${c.passed ? "pass" : "fail"}`}>
                  <span className="mark">{c.passed ? "✓" : "✗"}</span>
                  <span><b className="mono">{c.id}</b> — {c.detail}</span>
                </div>
              ))}
            </div>
          )}
          {inv.browser && inv.browser.length > 0 && <BrowserEvidence browser={inv.browser} runs={runs} onOpen={setOpenRun} />}
          <div className="card">
            <h2>Sandbox runs</h2>
            {runs.map((r) => (
              <div key={r.id} className="check" style={{ cursor: "pointer" }} onClick={() => api.run(r.id).then(setOpenRun)}>
                <span className="mono">{r.kind}#{r.attempt}</span>
                <span className="muted mono">{r.container_id} · {r.tier} · {r.duration_ms}ms{r.killed_reason ? ` · ${r.killed_reason}` : ""}</span>
              </div>
            ))}
            {runs.length === 0 && <div className="muted">none yet</div>}
          </div>
          {["QUARANTINED", "BLOCKED", "POSTED", "HELD", "REJECTED"].includes(inv.status) && (
            <Link className="btn ghost" to={`/receipts/${inv.id}`} style={{ textAlign: "center" }}>View signed receipt →</Link>
          )}
        </div>
      </div>

      {openRun && <RunDrawer run={openRun} onClose={() => setOpenRun(null)} />}
    </div>
  );
}

function RunLink({ runs, kind, attempt, onOpen }: { runs: Run[]; kind: string; attempt: number; onOpen: (r: Run) => void }) {
  const r = runs.find((x) => x.kind === kind && x.attempt === attempt);
  if (!r) return null;
  return <button className="btn ghost" style={{ padding: "3px 10px", fontSize: 12, marginTop: 4 }} onClick={() => api.run(r.id).then(onOpen)}>view code &amp; output</button>;
}

function BrowserEvidence({ browser, runs, onOpen }: { browser: any[]; runs: Run[]; onOpen: (r: Run) => void }) {
  return (
    <div className="card">
      <h2>Browser evidence <span className="sim">SANDBOXED</span></h2>
      {browser.map((b, i) => {
        const run = runs.find((r) => r.id === b.run_id);
        const shots = run?.artifacts?.filter((a: any) => a.name.endsWith(".png")) || [];
        return (
          <div key={i} style={{ marginBottom: 12 }}>
            <div className={b.credential_harvest ? "fail" : "muted"}><b>{b.credential_harvest ? "Credential-harvest page" : "Page inspected"}</b> — {b.final_url}</div>
            <ul style={{ margin: "4px 0", paddingLeft: 18 }}>{(b.reasons || []).map((r: string, j: number) => <li key={j} className="muted">{r}</li>)}</ul>
            {shots.map((a: any, j: number) => a.key && <img key={j} className="shot" src={`/api/../${a.key}`} alt="screenshot" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />)}
            {run && <Containment run={run} />}
            {!run && b.downloads_seen > 0 && <div className="fail">{b.downloads_seen} download(s) quarantined (never opened)</div>}
            {run && <button className="btn ghost" style={{ padding: "3px 10px", fontSize: 12 }} onClick={() => api.run(run.id).then(onOpen)}>proxy log &amp; details</button>}
          </div>
        );
      })}
    </div>
  );
}

// What the sandbox did with the page's payloads. Only states what was measured: the forced
// download's hash, the CPU limit the page ran under (with the page's own busy-loop counter,
// when it exposes one), proxy denials, and how long the container lived before destruction.
function Containment({ run }: { run: Run }) {
  const x = run.extra || {};
  const downloads: any[] = x.downloads || [];
  const denied = (x.proxy_log || []).filter((e: any) => e.decision === "deny").length;
  const burn = x.page_cpu_counter;
  const items: React.ReactNode[] = [];
  downloads.forEach((d, i) => items.push(
    <li key={`d${i}`}>Download <span className="mono">{d.name}</span> quarantined, never opened · sha256 <span className="mono">{String(d.sha256).slice(0, 8)}…{String(d.sha256).slice(-4)}</span> · {d.size} B</li>));
  if (burn != null) items.push(
    <li key="cpu">Page ran a CPU busy-loop ({Number(burn).toLocaleString()} iterations) inside a {run.limits?.cpus ?? "?"}-CPU, {run.limits?.memory_mb ?? "?"} MB sandbox</li>);
  if (denied > 0) items.push(<li key="deny">{denied} request(s) denied by the egress proxy</li>);
  if (run.destroyed_at) items.push(
    <li key="life">Container destroyed after {(run.duration_ms / 1000).toFixed(1)} s ({run.tier})</li>);
  if (!items.length) return null;
  return <ul className={downloads.length || burn != null ? "fail" : "muted"} style={{ margin: "4px 0 8px", paddingLeft: 18 }}>{items}</ul>;
}

function RunDrawer({ run, onClose }: { run: Run; onClose: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", display: "flex", justifyContent: "flex-end", zIndex: 50 }} onClick={onClose}>
      <div className="card" style={{ width: "min(680px, 100%)", height: "100%", borderRadius: 0, overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div className="row"><h2>{run.kind} #{run.attempt}</h2><span className="spacer" /><button className="btn ghost" onClick={onClose}>close</button></div>
        <div className="kv" style={{ marginBottom: 12 }}>
          <div className="k">Container</div><div className="mono">{run.container_id}</div>
          <div className="k">Tier / runtime</div><div className="mono">{run.tier} · {run.isolation?.runtime}</div>
          <div className="k">Network</div><div className="mono">{run.isolation?.network}</div>
          <div className="k">Env vars passed</div><div className="mono">{run.isolation?.env_vars_passed}</div>
          <div className="k">User / root-fs</div><div className="mono">{run.isolation?.user} · {run.isolation?.read_only_root ? "read-only" : "writable"}</div>
          <div className="k">Limits</div><div className="mono">{run.limits?.memory_mb}MB · {run.limits?.cpus}cpu · {run.limits?.pids}pids · {run.limits?.timeout_s}s</div>
          <div className="k">Lifecycle</div><div className="mono">{run.created_at?.slice(11, 23)} → {run.destroyed_at?.slice(11, 23)}</div>
          <div className="k">Exit / killed</div><div className="mono">{String(run.exit_code)}{run.killed_reason ? ` · ${run.killed_reason}` : ""}</div>
          {run.peak_mem_mb != null && <><div className="k">Peak memory</div><div className="mono">{run.peak_mem_mb} MB</div></>}
        </div>
        {run.static_flags?.length > 0 && <div style={{ marginBottom: 8 }}>{run.static_flags.map((fl) => <span key={fl} className="flag">{fl}</span>)}</div>}
        {run.code && <><div className="muted">Code the model wrote:</div><pre className="code">{run.code}</pre></>}
        {run.stdout && <><div className="muted">stdout:</div><pre className="code">{run.stdout}</pre></>}
        {run.stderr && <><div className="muted">stderr:</div><pre className="code">{run.stderr}</pre></>}
        {run.extra?.proxy_log?.length > 0 && <><div className="muted">egress proxy log:</div><pre className="code">{run.extra.proxy_log.map((e: any) => `${e.decision.toUpperCase()} ${e.host} ${e.reason || ""}`).join("\n")}</pre></>}
      </div>
    </div>
  );
}
