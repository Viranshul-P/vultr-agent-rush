import React from "react";
import { api } from "../api";

export function Erp() {
  const [postings, setPostings] = React.useState<any[]>([]);
  const [vendors, setVendors] = React.useState<any[]>([]);
  React.useEffect(() => {
    api.erp().then((d) => setPostings(d.postings)).catch(() => {});
    fetch("/api/vendors").then((r) => r.json()).then((d) => setVendors(d.vendors)).catch(() => {});
  }, []);
  return (
    <div>
      <h1>Mock ERP</h1>
      <div className="muted" style={{ marginBottom: 16 }}>Only human-approved invoices reach this ledger. No model can write here.</div>
      <div className="card" style={{ padding: 0, marginBottom: 20 }}>
        <table>
          <thead><tr><th>Posted</th><th>Invoice #</th><th>Amount</th></tr></thead>
          <tbody>
            {postings.map((p) => (
              <tr key={p.id}><td className="mono muted">{p.ts?.slice(0, 19).replace("T", " ")}</td><td className="mono">{p.invoice_number}</td><td className="mono">{p.currency} {p.amount}</td></tr>
            ))}
            {postings.length === 0 && <tr><td colSpan={3} className="muted" style={{ padding: 20 }}>Nothing posted yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <h2>Vendor master</h2>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>Vendor</th><th>Domains</th><th>Bank on file</th><th>Phone</th></tr></thead>
          <tbody>
            {vendors.map((v) => (
              <tr key={v.id}><td>{v.name}</td><td className="mono muted">{(v.email_domains || []).join(", ")}</td>
                <td className="mono">{v.bank?.iban || v.bank?.account_number || "—"}</td><td className="mono">{v.phone}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
