// Thin client for the Airlock control-plane API. Cookies carry the workspace.

export type Outcome = "CLEAR" | "HOLD" | "BLOCK" | "QUARANTINE";
export type Status =
  | "NEW" | "SCANNING" | "EXTRACTING" | "VALIDATING" | "INSPECTING_LINKS" | "DECIDING"
  | "AWAIT_APPROVAL" | "POSTED" | "REJECTED" | "BLOCKED" | "HELD" | "QUARANTINED" | "ERROR";

export interface Invoice {
  id: string; order: number; title: string; filename: string; status: Status; queued?: boolean;
  source: string; expected?: string | null;
  fields?: any; detectors?: any; sandbox_checks?: any[]; browser?: any[];
  policy?: any; summary?: any; blast_radius?: any; error?: string | null;
}
export interface Run {
  id: string; kind: string; attempt: number; tier: string; container_id: string;
  image_digest: string; code?: string; static_flags: string[]; limits: any; isolation: any;
  exit_code?: number | null; killed_reason?: string | null; stdout?: string; stderr?: string;
  artifacts: any[]; extra: any; created_at?: string; destroyed_at?: string; duration_ms: number;
  peak_mem_mb?: number | null;
}

const J = async (r: Response) => {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
};

export const api = {
  session: () => fetch("/api/session", { method: "POST" }).then(J),
  reset: () => fetch("/api/workspace/reset", { method: "POST" }).then(J),
  invoices: (): Promise<{ invoices: Invoice[] }> => fetch("/api/invoices").then(J),
  invoice: (id: string): Promise<{ invoice: Invoice; runs: Run[]; events: any[] }> =>
    fetch(`/api/invoices/${id}`).then(J),
  process: (id: string) => fetch(`/api/invoices/${id}/process`, { method: "POST" }).then(J),
  processAll: () => fetch("/api/inbox/process-all", { method: "POST" }).then(J),
  decide: (id: string, decision: "approve" | "reject", note = "") =>
    fetch(`/api/invoices/${id}/decision`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note }),
    }).then(J),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/invoices", { method: "POST", body: fd }).then(J);
  },
  run: (id: string): Promise<Run> => fetch(`/api/runs/${id}`).then(J),
  receipt: (id: string) => fetch(`/api/receipts/${id}`).then(J),
  verify: (id: string) => fetch(`/api/receipts/${id}/verify`, { method: "POST" }).then(J),
  drills: () => fetch("/api/drills").then(J),
  runDrill: (id: string) => fetch(`/api/drills/${id}/run`, { method: "POST" }).then(J),
  runAllDrills: () => fetch("/api/drills/run-all", { method: "POST" }).then(J),
  metrics: () => fetch("/api/metrics").then(J),
  erp: () => fetch("/api/erp/postings").then(J),
  health: () => fetch("/api/health").then(J),
};

export const OUTCOME_FROM_STATUS: Record<string, Outcome | "PENDING" | "DONE"> = {
  POSTED: "DONE", AWAIT_APPROVAL: "CLEAR", BLOCKED: "BLOCK", HELD: "HOLD",
  QUARANTINED: "QUARANTINE", REJECTED: "BLOCK", ERROR: "HOLD",
};
