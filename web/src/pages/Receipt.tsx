import React from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Download, FileSignature, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { api, errMsg } from "../api";
import { Callout, CopyButton, Sk, ease } from "../ui";

export function Receipt() {
  const { id } = useParams();
  const [data, setData] = React.useState<any>(null);
  const [verify, setVerify] = React.useState<any>(null);
  const [verifying, setVerifying] = React.useState(true);
  const [err, setErr] = React.useState<string | null>(null);

  const runVerify = React.useCallback(() => {
    if (!id) return;
    setVerifying(true);
    // A short beat so the check reads as an action, not a static label.
    Promise.all([api.verify(id), new Promise((r) => setTimeout(r, 650))]).then(([v]) => setVerify(v)).catch(() => setVerify(null)).finally(() => setVerifying(false));
  }, [id]);

  React.useEffect(() => {
    if (!id) return;
    api.receipt(id).then(setData).catch((e) => setErr(errMsg(e)));
    runVerify();
  }, [id, runVerify]);

  const back = <Link to={`/invoices/${id}`} className="crumb"><ArrowLeft />Invoice</Link>;
  if (err) return <div>{back}<Callout kind="warn">There's no receipt yet. A receipt is sealed once the invoice finishes processing.</Callout></div>;
  if (!data) return <div>{back}<Sk w={260} h={28} /><div style={{ height: 16 }} /><div className="panel" style={{ padding: 24 }}><Sk h={60} /></div></div>;
  const ok = verify?.sha256_ok && verify?.signature_ok;
  const manifest = pretty(data.manifest);

  return (
    <div>
      {back}
      <div className="ph">
        <div className="ph-text">
          <h1>Signed evidence receipt</h1>
          <p>Everything that happened to this invoice, hashed and signed with Ed25519. Change one byte and the check below fails.</p>
        </div>
        <div className="ph-actions">
          <button className="btn secondary" onClick={runVerify} disabled={verifying}>{verifying ? <Loader2 className="spin" /> : <ShieldCheck />}Verify again</button>
          <a className="btn" download={`airlock-receipt-${id}.json`} href={`data:application/json,${encodeURIComponent(data.manifest)}`}><Download />Download</a>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="seal">
          <motion.div key={verifying ? "w" : ok ? "ok" : "bad"} className={`seal-ic ${verifying ? "wait" : ok ? "ok" : "bad"}`}
            initial={{ scale: 0.7, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.4, ease }}>
            {verifying ? <Loader2 className="spin" /> : ok ? <ShieldCheck /> : <ShieldAlert />}
          </motion.div>
          <div style={{ minWidth: 0 }}>
            <h2 style={{ fontSize: 18 }}>{verifying ? "Verifying signature…" : ok ? "Signature valid" : "Not verified"}</h2>
            <div className="row" style={{ gap: 6, marginTop: 6 }}>
              {verify && <span className={`tag ${verify.sha256_ok ? "ok" : "bad"}`}>sha256 {verify.sha256_ok ? "matches" : "mismatch"}</span>}
              {verify && <span className={`tag ${verify.signature_ok ? "ok" : "bad"}`}>Ed25519 {verify.signature_ok ? "valid" : "invalid"}</span>}
            </div>
          </div>
        </div>
        <div style={{ borderTop: "1px solid var(--line)", padding: "14px 22px", display: "grid", gap: 10 }}>
          <div><div className="muted" style={{ fontSize: 12, marginBottom: 3 }}>Manifest sha256</div><div className="hash">{data.manifest_sha256}</div></div>
          <div><div className="muted" style={{ fontSize: 12, marginBottom: 3 }}>Public key</div><div className="hash">{data.public_key}</div></div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-h"><FileSignature size={16} /><h2>Manifest</h2><span className="right"><CopyButton text={manifest} /></span></div>
        <div className="panel-b"><pre className="code" style={{ maxHeight: 560 }}>{manifest}</pre></div>
      </div>
    </div>
  );
}

function pretty(s: string) { try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; } }
