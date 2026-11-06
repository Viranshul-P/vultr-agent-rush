import React from "react";
import { motion } from "motion/react";
import { Check, Circle, Loader2, Play, PlayCircle, ShieldCheck, X } from "lucide-react";
import { api, errMsg } from "../api";
import { Callout, PageHeader, Sk, ease, useToast } from "../ui";

export function RedTeam() {
  const toast = useToast();
  const [cat, setCat] = React.useState<any>(null);
  const [results, setResults] = React.useState<Record<string, any>>({});
  const [busy, setBusy] = React.useState<string | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    api.drills().then((d) => { setCat(d); setResults(mapLast(d.last_results || {})); }).catch((e) => setErr(errMsg(e)));
  }, []);

  const run = async (id: string) => {
    setBusy(id);
    try {
      const r = await api.runDrill(id);
      setResults((p) => ({ ...p, [id]: { ...r, ts: new Date().toISOString() } }));
      toast(r.passed ? { kind: "ok", title: `${id} contained`, detail: r.title } : r.passed === false ? { kind: "err", title: `${id} failed`, detail: r.actual } : { kind: "info", title: `${id} skipped`, detail: r.actual });
    } catch (e) { setResults((p) => ({ ...p, [id]: { error: errMsg(e) } })); toast({ kind: "err", title: `${id} couldn't run`, detail: errMsg(e) }); }
    setBusy(null);
  };
  const runAll = async () => {
    setBusy("all");
    try {
      const all = await api.runAllDrills();
      const now = new Date().toISOString();
      const stamped: Record<string, any> = {};
      for (const k in all) stamped[k] = { ...all[k], ts: now };
      setResults(stamped);
      const p = Object.values(all).filter((r: any) => r?.passed === true).length;
      toast({ kind: p === Object.keys(all).length ? "ok" : "err", title: `${p}/${Object.keys(all).length} drills contained` });
    } catch (e) { setErr(errMsg(e)); }
    setBusy(null);
  };

  const drills: any[] = cat?.drills || [];
  const passed = drills.filter((d) => results[d.id]?.passed === true).length;
  const failed = drills.filter((d) => results[d.id]?.passed === false).length;
  const lastTs = Object.values(results).map((r: any) => r?.ts).filter(Boolean).sort().pop();

  return (
    <div>
      <PageHeader
        title="Red Team drills"
        sub="Each drill runs a real attack inside the same sandbox an invoice gets, then checks that it stayed contained. Run them yourself."
        actions={<button className="btn" onClick={runAll} disabled={!!busy || !cat}>{busy === "all" ? <Loader2 className="spin" /> : <PlayCircle />}{busy === "all" ? "Running all drills…" : "Run all drills"}</button>}
      />
      {err && <div style={{ marginBottom: 16 }}><Callout kind="bad">The sandbox runner didn't answer: {err}</Callout></div>}
      {cat?.tier?.includes("DEV") && <div style={{ marginBottom: 16 }}><Callout kind="warn"><b>Dev backend.</b> Isolation drills are skipped here; run them on the gVisor sandbox VM for real results.</Callout></div>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="score">
          <div>
            <div className="big">{cat ? passed : "–"}<small>/{drills.length || 11}</small></div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{failed ? `${failed} failed` : "contained"}</div>
          </div>
          <div className="meter" style={{ ["--n" as any]: drills.length || 11 }} aria-label={`${passed} of ${drills.length} drills passed`}>
            {(drills.length ? drills : Array.from({ length: 11 })).map((d: any, i) => {
              const r = d && results[d.id];
              const running = busy === "all" || (d && busy === d.id);
              return (
                <motion.i key={d?.id || i} title={d?.id} className={r?.passed === true ? "p" : r?.passed === false ? "f" : ""}
                  initial={false} animate={running ? { opacity: [1, 0.35, 1] } : { opacity: 1 }}
                  transition={running ? { duration: 1, repeat: Infinity, delay: i * 0.06 } : { duration: 0.3, ease, delay: i * 0.04 }} />
              );
            })}
          </div>
          <div style={{ textAlign: "right", minWidth: 120 }} className="hide-sm">
            <div className="row" style={{ justifyContent: "flex-end", gap: 6, fontWeight: 560 }}><ShieldCheck size={15} color="var(--clear)" />{cat?.tier || "…"}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>{lastTs ? `last run ${new Date(lastTs).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}` : "not run yet"}</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="drills">
          {!cat && !err && [0, 1, 2, 3].map((i) => <div key={i} className="drill"><Sk w={26} h={26} r={99} /><Sk w={30} /><div><Sk w="50%" /><div style={{ height: 8 }} /><Sk w="80%" h={11} /></div><Sk w={64} h={30} /></div>)}
          {drills.map((d, i) => {
            const r = results[d.id];
            const running = busy === "all" || busy === d.id;
            const st = running ? "run" : r?.passed === true ? "pass" : r?.passed === false ? "fail" : "none";
            return (
              <motion.div key={d.id} className="drill" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease, delay: i * 0.03 }}>
                <span className={`ic ${st}`}>{st === "run" ? <Loader2 className="spin" /> : st === "pass" ? <Check /> : st === "fail" ? <X /> : <Circle />}</span>
                <span className="id">{d.id}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="tt">{d.title}</div>
                  <dl className="ex">
                    <dt>Attack</dt><dd>{d.attempt}</dd>
                    <dt>Expect</dt><dd>{d.expected}</dd>
                    {r?.actual && <><dt>Result</dt><dd className="mono" style={{ color: r.passed ? "var(--text)" : "var(--block)" }}>{r.actual}</dd></>}
                    {r?.error && <><dt>Error</dt><dd style={{ color: "var(--block)" }}>{r.error}</dd></>}
                  </dl>
                </div>
                <button className="btn secondary sm" onClick={() => run(d.id)} disabled={!!busy}>{busy === d.id ? <Loader2 className="spin" /> : <Play />}Run</button>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function mapLast(last: Record<string, any>) {
  const out: Record<string, any> = {};
  for (const k in last) out[k] = { ...(last[k].data || last[k]), ts: last[k].ts };
  return out;
}

/** Passed / total from the last recorded drill results (null while loading or if the runner is down). */
export function useDrillScore() {
  const [v, setV] = React.useState<{ passed: number; total: number } | null>(null);
  React.useEffect(() => {
    api.drills().then((d) => {
      const last = mapLast(d.last_results || {});
      const ids: string[] = (d.drills || []).map((x: any) => x.id);
      if (!ids.length || !ids.some((i) => last[i])) return;
      setV({ passed: ids.filter((i) => last[i]?.passed === true).length, total: ids.length });
    }).catch(() => {});
  }, []);
  return v;
}
