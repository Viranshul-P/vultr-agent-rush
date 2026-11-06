// The invoice pipeline as the UI shows it: six stages, four inside the sandbox chamber.
import type { Invoice, Status } from "./api";

export type StageKey = "scan" | "extract" | "validate" | "links" | "decide" | "approve";
export type StageState = "wait" | "active" | "done" | "stop" | "skip";
export type Tone = "clear" | "hold" | "block" | "quar" | "done" | "proc" | "new";

export const STAGES: { key: StageKey; name: string; where: "sandbox" | "control" | "human" }[] = [
  { key: "scan", name: "Scan PDF", where: "sandbox" },
  { key: "extract", name: "Extract", where: "sandbox" },
  { key: "validate", name: "Validate", where: "sandbox" },
  { key: "links", name: "Inspect links", where: "sandbox" },
  { key: "decide", name: "Policy", where: "control" },
  { key: "approve", name: "Human", where: "human" },
];

const ORDER: Partial<Record<Status, number>> = {
  NEW: -1, SCANNING: 0, EXTRACTING: 1, VALIDATING: 2, INSPECTING_LINKS: 3, DECIDING: 4, AWAIT_APPROVAL: 5,
};
export const PROCESSING: Status[] = ["SCANNING", "EXTRACTING", "VALIDATING", "INSPECTING_LINKS", "DECIDING"];

export function isProcessing(inv: Pick<Invoice, "status" | "queued">) {
  return !!inv.queued || PROCESSING.includes(inv.status);
}

export function toneOf(status: Status, queued?: boolean): Tone {
  if (queued || PROCESSING.includes(status)) return "proc";
  switch (status) {
    case "AWAIT_APPROVAL": return "clear";
    case "POSTED": return "done";
    case "HELD": case "ERROR": return "hold";
    case "BLOCKED": case "REJECTED": return "block";
    case "QUARANTINED": return "quar";
    default: return "new";
  }
}

export const STATUS_LABEL: Record<Status, string> = {
  NEW: "Not processed", SCANNING: "Scanning", EXTRACTING: "Extracting", VALIDATING: "Validating",
  INSPECTING_LINKS: "Inspecting links", DECIDING: "Deciding", AWAIT_APPROVAL: "Cleared · needs approval",
  POSTED: "Posted to ERP", REJECTED: "Rejected by reviewer", BLOCKED: "Blocked", HELD: "Held for review",
  QUARANTINED: "Quarantined", ERROR: "Error · held",
};

/** Per-stage state for an invoice. `hasLinks` marks whether the link stage really ran. */
export function stageStates(inv: Pick<Invoice, "status" | "queued" | "browser" | "fields" | "policy">): StageState[] {
  const s = inv.status;
  const ranLinks = (inv.browser?.length || 0) > 0 || s === "INSPECTING_LINKS";
  const out: StageState[] = STAGES.map(() => "wait");
  if (inv.queued || s === "NEW") return out;
  const pos = ORDER[s];
  if (pos !== undefined) {
    for (let i = 0; i < STAGES.length; i++) out[i] = i < pos ? "done" : i === pos ? "active" : "wait";
    if (pos > 3 && !ranLinks) out[3] = "skip";
    return out;
  }
  // ERROR: show where it actually stopped, instead of marking every sandbox stage as passed.
  if (s === "ERROR") {
    const at = !inv.fields ? 1 : !inv.policy?.checks?.length ? 2 : 4;
    for (let i = 0; i < STAGES.length; i++) out[i] = i < at ? "done" : i === at ? "stop" : "skip";
    if (at > 3 && !ranLinks) out[3] = "skip";
    return out;
  }
  // terminal states
  for (let i = 0; i < 5; i++) out[i] = "done";
  if (!ranLinks) out[3] = "skip";
  if (s === "POSTED") out[5] = "done";
  else if (s === "REJECTED") out[5] = "stop";
  else { out[4] = "stop"; out[5] = "skip"; }
  return out;
}

export function stageSub(key: StageKey, st: StageState, inv: Invoice): string {
  if (st === "skip") return key === "links" ? "no links" : "not needed";
  if (st === "active") return key === "approve" ? "waiting for you" : "running…";
  if (st === "wait") return "";
  if (st === "stop" && inv.status === "ERROR") return key === "decide" ? "error · held" : "failed";
  switch (key) {
    case "scan": return inv.detectors?.injection_suspected ? "hidden text found" : "fixed program";
    case "extract": return "model-written code";
    case "validate": {
      const c = inv.policy?.checks || [];
      const f = c.filter((x: any) => !x.passed).length;
      return c.length ? (f ? `${f} of ${c.length} failed` : `${c.length} checks pass`) : "checks";
    }
    case "links": return inv.browser?.some((b: any) => b.credential_harvest) ? "phishing page" : "page looked ok";
    case "decide": return inv.policy?.outcome ? inv.policy.outcome.toLowerCase() : "decided";
    case "approve": return inv.status === "POSTED" ? "approved" : inv.status === "REJECTED" ? "rejected" : "";
  }
}
