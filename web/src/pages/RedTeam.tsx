import React from "react";
import { api } from "../api";

export function RedTeam() {
  const [cat, setCat] = React.useState<any>(null);
  const [results, setResults] = React.useState<Record<string, any>>({});
  const [busy, setBusy] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    api.drills().then((d) => { setCat(d); setResults(mapLast(d.last_results || {})); }).catch((e) => setErr(String(e)));
  }, []);

  const run = async (id: string) => {
    setBusy(id);
    try { const r = await api.runDrill(id); setResults((p) => ({ ...p, [id]: r })); }
    catch (e) { setResults((p) => ({ ...p, [id]: { error: String(e) } })); }
    setBusy(null);
  };
  const runAll = async () => {
    setBusy("all");
    try { const all = await api.runAllDrills(); setResults(all); } catch (e) { setErr(String(e)); }
    setBusy(null);
  };

  const passed = Object.values(results).filter((r: any) => r?.passed === true).length;
  const total = cat?.drills?.length || 0;

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <div><h1>Red Team drills</h1><div className="muted">Each drill runs a real attack inside the sandbox and checks it was contained.</div></div>
        <span className="spacer" />
        {cat && <span className="pill">{cat.tier}</span>}
        <button className="btn" onClick={runAll} disabled={!!busy}>{busy === "all" ? "Running…" : "Run all drills"}</button>
      </div>
      {err && <div className="banner block">Runner unreachable: {err}</div>}
      {cat?.tier?.includes("DEV") && <div className="banner block"><b>Dev backend:</b> isolation drills are skipped here. Run on the gVisor sandbox VM for real results.</div>}
      <div className="card">
        <div className="row" style={{ marginBottom: 8 }}><b>{passed}/{total} passed</b></div>
        {(cat?.drills || []).map((d: any) => {
          const r = results[d.id];
          const st = r?.passed === true ? "pass" : r?.passed === false ? "fail" : "skip";
          return (
            <div key={d.id} className="drill">
              <span className={`st ${st}`}>{r == null ? "—" : r.passed === true ? "PASS" : r.passed === false ? "FAIL" : "SKIP"}</span>
              <div style={{ flex: 1 }}>
                <b className="mono">{d.id}</b> {d.title}
                <div className="muted">{d.attempt} → expect: {d.expected}</div>
                {r?.actual && <div className="muted" style={{ fontSize: 12 }}>actual: {r.actual}</div>}
                {r?.error && <div className="fail" style={{ fontSize: 12 }}>{r.error}</div>}
              </div>
              <button className="btn ghost" onClick={() => run(d.id)} disabled={!!busy}>{busy === d.id ? "…" : "Run"}</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function mapLast(last: Record<string, any>) {
  const out: Record<string, any> = {};
  for (const k in last) out[k] = last[k].data || last[k];
  return out;
}
