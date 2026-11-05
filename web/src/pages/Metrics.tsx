import React from "react";
import { motion } from "motion/react";
import { Activity, Gauge } from "lucide-react";
import { api } from "../api";
import { CountUp, PageHeader, Sk, ease, pct, secs } from "../ui";

const CLASS_NAME: Record<string, string> = {
  clean: "Clean invoices", bank_change: "Bank-detail swap", duplicate: "Duplicate invoice", injection: "Prompt injection",
  phishing_link: "Phishing link", benign_link: "Legitimate link",
};
const ROLE_NAME: Record<string, string> = {
  classifier: "Injection classifier", coder_extract: "Code writer · extract", coder_validate: "Code writer · validate",
  planner: "Planner", safety: "Safety summary", vision: "Vision (link screenshots)",
};

export function Metrics() {
  const [m, setM] = React.useState<any>(null);
  React.useEffect(() => { api.metrics().then(setM).catch(() => setM({})); }, []);
  const e = m?.eval;

  return (
    <div>
      <PageHeader title="Metrics" sub="The latest evaluation: labelled invoices, attacks included, sent through this live site. Below it are the live counters for your own demo session." />

      {!m && <div className="stats">{[0, 1, 2, 3].map((i) => <div key={i} className="stat"><Sk w={70} h={24} /><div style={{ height: 8 }} /><Sk w={100} h={11} /></div>)}</div>}

      {m && e && (
        <>
          <div className="row" style={{ marginBottom: 10, gap: 8 }}>
            <Gauge size={16} className="muted" />
            <h2>Evaluation</h2>
            <span className="muted" style={{ fontSize: 12.5 }}>run {e.run_date}{e.n ? ` · ${e.n} invoices` : ""}{e.duration_s ? ` · ${Math.round(e.duration_s / 60)} min` : ""}</span>
          </div>
          <div className="stats" style={{ marginBottom: 20 }}>
            <Stat good v={<CountUp to={(e.outcome_accuracy ?? 0) * 100} suffix="%" />} l="correct outcome" />
            {e.attacks_caught && <Stat good v={<><CountUp to={e.attacks_caught.caught} /><small>/{e.attacks_caught.total}</small></>} l="attacks caught" />}
            <Stat v={pct(e.false_positive_rate)} l="false positives on clean invoices" />
            <Stat v={secs(e.latency_p50_ms)} l="median time per invoice" />
            <Stat v={secs(e.latency_p95_ms)} l="p95 time per invoice" />
            <Stat v={e.cost_per_invoice_usd != null ? `$${Number(e.cost_per_invoice_usd).toFixed(4)}` : "—"} l="inference cost per invoice" />
            {e.drills_passed != null && <Stat good v={<><CountUp to={e.drills_passed} /><small>/{e.drills_total}</small></>} l="red-team drills passed" />}
          </div>

          <div className="split-even" style={{ marginBottom: 20 }}>
            {e.per_class && (
              <div className="panel">
                <div className="panel-h"><h2>By invoice type</h2><span className="sub">recall</span></div>
                <div className="panel-b stack" style={{ gap: 14 }}>
                  {Object.entries(e.per_class).map(([k, v]: any, i) => (
                    <div key={k}>
                      <div className="row" style={{ marginBottom: 6, fontSize: 13.5 }}>
                        <span style={{ fontWeight: 540 }}>{CLASS_NAME[k] || k}</span>
                        <span className="muted mono" style={{ fontSize: 12 }}>n={v.n}</span>
                        <span className="grow" />
                        <span className="mono num">{pct(v.recall)}</span>
                      </div>
                      <div className="bar"><motion.i initial={{ scaleX: 0 }} whileInView={{ scaleX: v.recall ?? 0 }} viewport={{ once: true }} transition={{ duration: 0.8, ease, delay: i * 0.06 }} /></div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {e.llm_latency_by_role && (
              <div className="panel">
                <div className="panel-h"><h2>Model calls by role</h2><span className="sub">median latency</span></div>
                <div className="panel-b stack" style={{ gap: 14 }}>
                  {(() => {
                    const rows = Object.entries(e.llm_latency_by_role) as [string, any][];
                    const max = Math.max(...rows.map(([, v]) => v.p50_ms || 0), 1);
                    return rows.map(([k, v], i) => (
                      <div key={k}>
                        <div className="row" style={{ marginBottom: 6, fontSize: 13.5 }}>
                          <span style={{ fontWeight: 540 }}>{ROLE_NAME[k] || k}</span>
                          <span className="muted mono" style={{ fontSize: 12 }}>{v.calls} calls{v.failed ? ` · ${v.failed} failed` : ""}</span>
                          <span className="grow" />
                          <span className="mono num">{secs(v.p50_ms)}</span>
                        </div>
                        <div className="bar"><motion.i style={{ background: "var(--accent)" }} initial={{ scaleX: 0 }} whileInView={{ scaleX: (v.p50_ms || 0) / max }} viewport={{ once: true }} transition={{ duration: 0.8, ease, delay: i * 0.06 }} /></div>
                      </div>
                    ));
                  })()}
                </div>
              </div>
            )}
          </div>

          {e.per_outcome && (
            <div className="panel" style={{ marginBottom: 20 }}>
              <div className="panel-h"><h2>By outcome</h2></div>
              <div className="table-wrap">
                <table className="t">
                  <thead><tr><th>Outcome</th><th className="r">Expected</th><th className="r">Predicted</th><th className="r">Recall</th><th className="r">Precision</th></tr></thead>
                  <tbody>
                    {Object.entries(e.per_outcome).map(([k, v]: any) => (
                      <tr key={k}><td style={{ fontWeight: 540 }}>{k}</td><td className="r mono num">{v.n_true}</td><td className="r mono num">{v.n_predicted}</td><td className="r mono num">{pct(v.recall)}</td><td className="r mono num">{pct(v.precision)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
      {m && !e && <div className="panel panel-b muted" style={{ marginBottom: 20 }}>No evaluation has been run yet. Run <span className="mono">python eval/run.py</span> to fill this page.</div>}

      {m?.live && (
        <>
          <div className="row" style={{ marginBottom: 10, gap: 8 }}><Activity size={16} className="muted" /><h2>Your session</h2><span className="muted" style={{ fontSize: 12.5 }}>live, this demo workspace only</span></div>
          <div className="stats">
            <Stat v={m.live.llm_calls ?? 0} l="model calls" />
            <Stat v={`$${(m.live.llm_cost_usd ?? 0).toFixed(4)}`} l="inference cost" />
            <Stat v={m.live.invoices_posted ?? 0} l="invoices posted" />
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ v, l, good }: { v: React.ReactNode; l: string; good?: boolean }) {
  return <div className={`stat ${good ? "good" : ""}`}><div className="v">{v}</div><div className="l">{l}</div></div>;
}
