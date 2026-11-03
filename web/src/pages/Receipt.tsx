import React from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

export function Receipt() {
  const { id } = useParams();
  const [data, setData] = React.useState<any>(null);
  const [verify, setVerify] = React.useState<any>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!id) return;
    api.receipt(id).then(setData).catch((e) => setErr(String(e)));
    api.verify(id).then(setVerify).catch(() => {});
  }, [id]);

  if (err) return <div className="banner block">{err} — the receipt is sealed once processing finishes.</div>;
  if (!data) return <div className="muted">loading…</div>;
  const ok = verify?.sha256_ok && verify?.signature_ok;

  return (
    <div>
      <div className="row"><Link to={`/invoices/${id}`} className="muted">← Invoice</Link></div>
      <h1>Signed evidence receipt</h1>
      <div className={`banner ${ok ? "clear" : "block"}`}>
        <h2>{ok ? "✓ Signature valid" : "⚠ Not verified"}</h2>
        <div className="muted mono">Ed25519 · sha256 {data.manifest_sha256?.slice(0, 32)}…</div>
        <div className="muted mono" style={{ wordBreak: "break-all", marginTop: 6 }}>public key: {data.public_key}</div>
      </div>
      <div className="card">
        <div className="row" style={{ marginBottom: 8 }}>
          <h2>Manifest</h2><span className="spacer" />
          <a className="btn ghost" download={`airlock-receipt-${id}.json`}
             href={`data:application/json,${encodeURIComponent(data.manifest)}`}>Download</a>
        </div>
        <pre className="code" style={{ maxHeight: 520 }}>{pretty(data.manifest)}</pre>
      </div>
    </div>
  );
}

function pretty(s: string) { try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; } }
