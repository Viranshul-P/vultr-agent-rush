import React from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Building2, FileSignature, Landmark, Lock } from "lucide-react";
import { api } from "../api";
import { Empty, PageHeader, Sk, ease } from "../ui";

export function Erp() {
  const [postings, setPostings] = React.useState<any[] | null>(null);
  const [vendors, setVendors] = React.useState<any[] | null>(null);
  React.useEffect(() => {
    api.erp().then((d) => setPostings(d.postings || [])).catch(() => setPostings([]));
    fetch("/api/vendors").then((r) => r.json()).then((d) => setVendors(d.vendors || [])).catch(() => setVendors([]));
  }, []);
  const total = (postings || []).reduce((acc: Record<string, number>, p) => { acc[p.currency] = (acc[p.currency] || 0) + Number(p.amount || 0); return acc; }, {});

  return (
    <div>
      <PageHeader title="Ledger" sub="A mock ERP. Only invoices a person approved can reach it; no model has a way to write here." />

      <div className="panel" style={{ marginBottom: 24 }}>
        <div className="panel-h">
          <Landmark size={16} /><h2>Posted payments</h2>
          <span className="sub">{postings ? `${postings.length} posted` : ""}</span>
          <span className="right">{Object.entries(total).map(([c, v]) => <span key={c} className="tag ok">{c} {v.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>)}</span>
        </div>
        {postings === null ? <div className="panel-b"><Sk /><div style={{ height: 10 }} /><Sk w="60%" /></div> : postings.length === 0 ? (
          <Empty icon={<Lock />} title="Nothing posted yet" action={<Link className="btn secondary sm" to="/inbox">Go to the inbox</Link>}>
            Process the inbox, then approve a cleared invoice. It shows up here with its signed receipt.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="t">
              <thead><tr><th>Posted</th><th>Vendor</th><th>Invoice #</th><th className="r">Amount</th><th style={{ width: 110 }}>Evidence</th></tr></thead>
              <tbody>
                {postings.map((p, i) => (
                  <motion.tr key={p.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04, duration: 0.3, ease }}>
                    <td className="mono muted" title={p.ts}>{p.ts ? new Date(p.ts).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}</td>
                    <td>{(vendors || []).find((v) => v.id === p.vendor_id)?.name || <span className="mono muted">{p.vendor_id || "—"}</span>}</td>
                    <td className="mono"><Link to={`/invoices/${p.invoice_id}`}>{p.invoice_number || "—"}</Link></td>
                    <td className="r mono num">{p.currency} {Number(p.amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                    <td><Link className="btn ghost sm" to={`/receipts/${p.invoice_id}`}><FileSignature />Receipt</Link></td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-h"><Building2 size={16} /><h2>Vendor master</h2><span className="sub">what every invoice is checked against</span></div>
        <div className="table-wrap">
          <table className="t">
            <thead><tr><th>Vendor</th><th>Email domains</th><th>Bank on file</th><th>Phone</th></tr></thead>
            <tbody>
              {vendors === null && [0, 1, 2].map((i) => <tr key={i}><td><Sk w={140} /></td><td><Sk w={120} /></td><td><Sk w={180} /></td><td><Sk w={90} /></td></tr>)}
              {(vendors || []).map((v) => (
                <tr key={v.id}>
                  <td style={{ fontWeight: 540 }}>{v.name}</td>
                  <td className="mono muted" style={{ fontSize: 12.5 }}>{(v.email_domains || []).join(", ")}</td>
                  <td className="mono" style={{ fontSize: 12.5 }}>{v.bank?.iban || v.bank?.account_number || "—"}</td>
                  <td className="mono muted" style={{ fontSize: 12.5 }}>{v.phone}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
