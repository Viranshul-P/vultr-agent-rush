import React from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ChevronRight, FileUp, Loader2, Play, RotateCcw, Sparkles, UploadCloud } from "lucide-react";
import { api, Invoice } from "../api";
import { isProcessing, toneOf } from "../pipeline";
import { Empty, MiniPipe, PageHeader, Seg, Sk, StatusBadge, ease, money, useToast } from "../ui";

type Filter = "all" | "approval" | "contained" | "active" | "posted";

export function Inbox() {
  const nav = useNavigate();
  const toast = useToast();
  const [invoices, setInvoices] = React.useState<Invoice[]>([]);
  const [loaded, setLoaded] = React.useState(false);
  const [busy, setBusy] = React.useState<"" | "process" | "reset" | "upload">("");
  const [filter, setFilter] = React.useState<Filter>("all");
  const [dragging, setDragging] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(() => api.invoices().then((d) => { setInvoices(d.invoices); setLoaded(true); }).catch(() => setLoaded(true)), []);
  React.useEffect(() => {
    load();
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [load]);

  const processAll = async () => {
    setBusy("process");
    try {
      const r = await api.processAll();
      const n = r?.started?.length ?? 0;
      toast(n ? { kind: "info", title: `Processing ${n} invoice${n === 1 ? "" : "s"}`, detail: "Each one opens in its own disposable sandbox. Results arrive in about 20–40 s." }
        : { kind: "info", title: "Nothing new to process", detail: "Reset the demo to start over, or upload a PDF." });
    } catch (e) { toast({ kind: "err", title: "Couldn't start processing", detail: String(e) }); }
    setTimeout(() => setBusy(""), 800);
  };
  const reset = async () => {
    setBusy("reset");
    try { await api.reset(); await load(); toast({ kind: "ok", title: "Demo reset", detail: "Six fresh demo invoices are back in the inbox." }); }
    catch (e) { toast({ kind: "err", title: "Reset failed", detail: String(e) }); }
    setBusy("");
  };
  const upload = async (f: File) => {
    if (!/\.pdf$/i.test(f.name) && f.type !== "application/pdf") { toast({ kind: "err", title: "Only PDF invoices are accepted", detail: `${f.name} isn't a PDF.` }); return; }
    setBusy("upload");
    try { await api.upload(f); toast({ kind: "ok", title: "Invoice uploaded", detail: `${f.name} is in the inbox. Process it to send it through the sandbox.` }); load(); }
    catch (e) { toast({ kind: "err", title: "Upload failed", detail: String(e).slice(0, 200) }); }
    setBusy("");
  };

  // Drag a PDF anywhere on the page to upload it.
  React.useEffect(() => {
    let depth = 0;
    const has = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).includes("Files");
    const enter = (e: DragEvent) => { if (!has(e)) return; depth++; setDragging(true); };
    const leave = () => { depth = Math.max(0, depth - 1); if (!depth) setDragging(false); };
    const over = (e: DragEvent) => { if (has(e)) e.preventDefault(); };
    const drop = (e: DragEvent) => { if (!has(e)) return; e.preventDefault(); depth = 0; setDragging(false); const f = e.dataTransfer?.files?.[0]; if (f) upload(f); };
    window.addEventListener("dragenter", enter); window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over); window.addEventListener("drop", drop);
    return () => { window.removeEventListener("dragenter", enter); window.removeEventListener("dragleave", leave); window.removeEventListener("dragover", over); window.removeEventListener("drop", drop); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = {
    all: invoices.length,
    approval: invoices.filter((i) => i.status === "AWAIT_APPROVAL").length,
    contained: invoices.filter((i) => ["block", "quar", "hold"].includes(toneOf(i.status, i.queued))).length,
    active: invoices.filter(isProcessing).length,
    posted: invoices.filter((i) => i.status === "POSTED").length,
  };
  const shown = invoices.filter((i) => {
    const t = toneOf(i.status, i.queued);
    switch (filter) {
      case "approval": return i.status === "AWAIT_APPROVAL";
      case "contained": return t === "block" || t === "quar" || t === "hold";
      case "active": return isProcessing(i);
      case "posted": return i.status === "POSTED";
      default: return true;
    }
  });
  const allNew = loaded && invoices.length > 0 && invoices.every((i) => i.status === "NEW" && !i.queued);
  const anyNew = invoices.some((i) => i.status === "NEW" && !i.queued);

  return (
    <div>
      <PageHeader
        title="Accounts-payable inbox"
        sub="Every invoice opens inside a disposable Vultr sandbox before anyone can pay it. Open a row to watch what happened inside."
        actions={<>
          <button className="btn secondary" onClick={reset} disabled={!!busy}>{busy === "reset" ? <Loader2 className="spin" /> : <RotateCcw />}Reset demo</button>
          <button className="btn secondary" onClick={() => fileRef.current?.click()} disabled={!!busy}>{busy === "upload" ? <Loader2 className="spin" /> : <FileUp />}Upload PDF</button>
          <button className="btn" onClick={processAll} disabled={!!busy || !anyNew}>{busy === "process" ? <Loader2 className="spin" /> : <Play />}Process inbox</button>
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
        </>}
      />

      <AnimatePresence>
        {allNew && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3, ease }} style={{ overflow: "hidden" }}>
            <div className="callout info" style={{ marginBottom: 16, alignItems: "center" }}>
              <Sparkles />
              <div className="grow"><b style={{ color: "var(--text)" }}>{invoices.length} demo invoices are waiting.</b> Two are clean, and four are attacks: a duplicate, a bank-detail swap, a hidden prompt injection and a phishing link. Process them and see which ones get through.</div>
              <button className="btn sm" onClick={processAll} disabled={!!busy}><Play />Process all</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="row" style={{ marginBottom: 12 }}>
        <Seg id="inbox" value={filter} onChange={setFilter} items={[
          { value: "all", label: "All", count: counts.all },
          { value: "approval", label: "Needs approval", count: counts.approval },
          { value: "contained", label: "Contained", count: counts.contained },
          { value: "active", label: "Processing", count: counts.active },
          { value: "posted", label: "Posted", count: counts.posted },
        ]} />
        <span className="grow" />
        <span className="muted" style={{ fontSize: 12.5, display: "inline-flex", gap: 6, alignItems: "center" }}><UploadCloud size={14} />Drop a PDF anywhere to upload</span>
      </div>

      <div className="panel">
        <div className="table-wrap">
          <table className="t inbox-t">
            <thead>
              <tr>
                <th style={{ width: 44 }}>#</th>
                <th>Invoice</th>
                <th className="r">Amount</th>
                <th style={{ width: 130 }}>Pipeline</th>
                <th>Status</th>
                <th style={{ width: 32 }} aria-label="Open" />
              </tr>
            </thead>
            <tbody>
              {!loaded && [0, 1, 2, 3, 4, 5].map((i) => (
                <tr key={i}><td><Sk w={14} /></td><td><Sk w="60%" /><div style={{ height: 6 }} /><Sk w="35%" h={11} /></td><td><Sk w={80} /></td><td><Sk w={100} h={6} /></td><td><Sk w={110} h={22} r={99} /></td><td /></tr>
              ))}
              <AnimatePresence initial={false}>
                {shown.map((inv, idx) => (
                  <motion.tr key={inv.id} className="click" layout="position"
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    transition={{ duration: 0.3, ease, delay: Math.min(idx, 8) * 0.03 }}
                    onClick={() => nav(`/invoices/${inv.id}`)}
                    tabIndex={0} onKeyDown={(e) => e.key === "Enter" && nav(`/invoices/${inv.id}`)}>
                    <td className="mono muted c-num">{inv.order}</td>
                    <td className="c-inv">
                      <div className="cell-title">{inv.fields?.vendor_name || inv.title}</div>
                      <div className="cell-sub">
                        {inv.fields?.invoice_number ? <span className="mono">{inv.fields.invoice_number}</span> : inv.filename}
                        {inv.summary?.headline && <> · {inv.summary.headline}</>}
                        {!inv.summary?.headline && inv.fields?.vendor_name && inv.title !== inv.fields.vendor_name && <> · {inv.title}</>}
                      </div>
                    </td>
                    <td className="r mono num c-amt" style={{ whiteSpace: "nowrap" }}>{money(inv.fields) || <span className="muted">—</span>}</td>
                    <td className="c-pipe"><MiniPipe inv={inv} /></td>
                    <td className="c-st"><StatusBadge status={inv.status} queued={inv.queued} /></td>
                    <td className="c-go"><span className="row-go"><ChevronRight /></span></td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
        {loaded && invoices.length === 0 && (
          <Empty title="The inbox is empty" action={<button className="btn" onClick={reset}><RotateCcw />Load demo invoices</button>}>
            Load the six demo invoices, or drop your own PDF here.
          </Empty>
        )}
        {loaded && invoices.length > 0 && shown.length === 0 && (
          <Empty title="Nothing in this view" action={<button className="btn secondary sm" onClick={() => setFilter("all")}>Show all invoices</button>}>
            No invoices match this filter yet.
          </Empty>
        )}
      </div>

      <AnimatePresence>
        {dragging && (
          <motion.div className="drop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <motion.div className="drop-box" initial={{ scale: 0.96 }} animate={{ scale: 1 }} transition={{ duration: 0.25, ease }}>
              <UploadCloud />
              <h2>Drop the PDF to add it to the inbox</h2>
              <p className="muted">It stays unopened until a sandbox processes it.</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
