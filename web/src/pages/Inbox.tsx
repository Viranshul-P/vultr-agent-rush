import React from "react";
import { useNavigate } from "react-router-dom";
import { api, Invoice } from "../api";
import { Chip, money } from "../components";

export function Inbox() {
  const nav = useNavigate();
  const [invoices, setInvoices] = React.useState<Invoice[]>([]);
  const [loaded, setLoaded] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(() => api.invoices().then((d) => { setInvoices(d.invoices); setLoaded(true); }).catch(() => {}), []);
  React.useEffect(() => {
    load();
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [load]);

  const processAll = async () => { setBusy(true); await api.processAll().catch(() => {}); setTimeout(() => setBusy(false), 1000); };
  const reset = async () => { setBusy(true); await api.reset(); await load(); setBusy(false); };
  const upload = async (f: File) => { await api.upload(f).catch((e) => alert(e)); load(); };

  return (
    <div>
      <div className="row" style={{ marginBottom: 16 }}>
        <div>
          <h1>Accounts-payable inbox</h1>
          <div className="muted">Every invoice is opened inside a disposable Vultr sandbox before any payment.</div>
        </div>
        <span className="spacer" />
        <button className="btn" onClick={processAll} disabled={busy}>Process inbox</button>
        <button className="btn ghost" onClick={() => fileRef.current?.click()}>Upload PDF</button>
        <button className="btn ghost" onClick={reset} disabled={busy}>Reset demo</button>
        <input ref={fileRef} type="file" accept="application/pdf" hidden
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>#</th><th>Vendor / title</th><th>Invoice #</th><th>Amount</th><th>Status</th><th>Outcome</th></tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id} className="clickable" onClick={() => nav(`/invoices/${inv.id}`)}>
                <td className="mono muted">{inv.order}</td>
                <td>{inv.fields?.vendor_name || inv.title}</td>
                <td className="mono">{inv.fields?.invoice_number || "—"}</td>
                <td className="mono">{money(inv.fields) || "—"}</td>
                <td><Chip status={inv.status} /></td>
                <td className="muted">{inv.summary?.headline || ""}</td>
              </tr>
            ))}
            {invoices.length === 0 && <tr><td colSpan={6} className="muted" style={{ padding: 20 }}>{loaded ? "No invoices. Click “Reset demo”." : "Loading…"}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
