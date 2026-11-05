import React from "react";
import { api } from "../api";

export function Metrics() {
  const [m, setM] = React.useState<any>(null);
  React.useEffect(() => { api.metrics().then(setM).catch(() => {}); }, []);
  if (!m) return <div className="muted">loading…</div>;
  const e = m.eval;

  return (
    <div>
      <h1>Metrics</h1>
      <div className="muted" style={{ marginBottom: 16 }}>Live counters from this workspace, plus the latest evaluation: labelled invoices sent through this live site.</div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Live</h2>
        <div className="tiles">
          <Tile n={m.live.llm_calls} l="LLM calls" />
          <Tile n={`$${(m.live.llm_cost_usd ?? 0).toFixed(4)}`} l="inference cost" />
          <Tile n={m.live.invoices_posted} l="invoices posted" />
        </div>
      </div>
      {e ? (
        <div className="card">
          <h2>Evaluation <span className="muted" style={{ fontSize: 12 }}>run {e.run_date || e.date || ""}{e.n ? ` · ${e.n} invoices` : ""}</span></h2>
          <div className="tiles" style={{ marginBottom: 16 }}>
            <Tile n={pct(e.outcome_accuracy)} l="outcome accuracy" />
            <Tile n={pct(e.false_positive_rate)} l="false positives (clean)" />
            {e.attacks_caught && <Tile n={`${e.attacks_caught.caught}/${e.attacks_caught.total}`} l="attacks caught" />}
            <Tile n={secs(e.latency_p50_ms)} l="latency p50" />
            <Tile n={secs(e.latency_p95_ms)} l="latency p95" />
            <Tile n={e.cost_per_invoice_usd != null ? `$${e.cost_per_invoice_usd}` : "—"} l="cost / invoice" />
            <Tile n={e.drills_passed != null ? `${e.drills_passed}/${e.drills_total}` : "—"} l="drills passed" />
          </div>
          {e.per_class && (
            <table>
              <thead><tr><th>Class</th><th>Recall</th><th>Precision</th><th>N</th></tr></thead>
              <tbody>
                {Object.entries(e.per_class).map(([k, v]: any) => (
                  <tr key={k}><td>{k}</td><td>{pct(v.recall)}</td><td>{pct(v.precision)}</td><td className="mono">{v.n}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className="card muted">No evaluation run yet. Run <span className="mono">python eval/run.py</span> to populate this.</div>
      )}
    </div>
  );
}

const Tile = ({ n, l }: { n: any; l: string }) => <div className="tile card" style={{ padding: 14 }}><div className="n">{n}</div><div className="l">{l}</div></div>;
const secs = (ms: any) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)} s`);
const pct = (x: any) => (x == null ? "—" : `${Math.round(x * 100)}%`);
