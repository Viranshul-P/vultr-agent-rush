export function About() {
  return (
    <div>
      <h1>How Airlock works</h1>
      <div className="card" style={{ marginBottom: 16 }}>
        <p>Accounts-payable teams open hundreds of untrusted invoices from strangers every day — exactly how
          invoice fraud and prompt-injection attacks get in. <b>Airlock</b> opens every invoice inside a
          disposable sandbox on Vultr. A malicious invoice can fool the AI, but it can't reach your money,
          your secrets or your servers.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div className="card">
          <h2>The pipeline</h2>
          <ol>
            <li><b>Scan</b> — a fixed program reads the PDF in the sandbox and flags hidden text.</li>
            <li><b>Extract</b> — the model writes parsing code; it runs in the sandbox; errors retry.</li>
            <li><b>Validate</b> — totals, IBAN, 3-way match, duplicates, sender domain.</li>
            <li><b>Inspect links</b> — a sandboxed browser opens any link; a vision model judges it.</li>
            <li><b>Decide</b> — a deterministic policy engine (no AI) sets the outcome.</li>
            <li><b>Approve</b> — a human must click before anything posts to the ERP.</li>
          </ol>
        </div>
        <div className="card">
          <h2>Dual-LLM safety</h2>
          <p>The model that reads the raw invoice has <b>no tools</b> — a successful injection has nothing to
            call. The model that writes the summary <b>never sees the raw document</b>. The policy engine, in
            plain code, makes every decision, and <b>no model can trigger a payment</b>.</p>
        </div>
        <div className="card">
          <h2>Containment</h2>
          <ul>
            <li>gVisor microkernel isolation on a <b>separate VM</b></li>
            <li><b>No network</b> for code; the browser reaches the web only through an egress proxy that blocks private and cloud-metadata addresses and logs every request</li>
            <li><b>No secrets</b> ever enter the sandbox VM</li>
            <li>CPU / memory / pid / time caps; destroyed after each task</li>
            <li>Every run signed into a tamper-evident receipt</li>
          </ul>
        </div>
        <div className="card">
          <h2>Vultr services</h2>
          <ul>
            <li>Cloud Compute — control plane VM</li>
            <li>Cloud Compute — isolated sandbox VM</li>
            <li>Serverless Inference — all agent LLM calls</li>
            <li>VPC + Firewall — private runner link</li>
            <li>Object Storage — uploads, screenshots, receipts</li>
            <li>Container Registry — private registry for the sandbox images (the live deploy builds them on the sandbox VM, pinned by digest)</li>
            <li>Managed PostgreSQL — application data</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
