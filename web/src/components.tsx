import React from "react";

export function Chip({ status }: { status: string }) {
  const proc = ["SCANNING", "EXTRACTING", "VALIDATING", "INSPECTING_LINKS", "DECIDING"].includes(status);
  const cls = proc ? "PROC" : status;
  const label = proc ? "Processing…" : status.replace(/_/g, " ").toLowerCase();
  return <span className={`chip ${cls}`}>{label}</span>;
}

export function money(fields: any): string {
  if (!fields) return "";
  return `${fields.currency || ""} ${fields.total ?? ""}`.trim();
}

export function Spinner() {
  return <span className="muted">loading…</span>;
}

export function useAsync<T>(fn: () => Promise<T>, deps: any[] = []): [T | null, string | null, () => void] {
  const [data, setData] = React.useState<T | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [n, setN] = React.useState(0);
  React.useEffect(() => {
    let live = true;
    fn().then((d) => live && setData(d)).catch((e) => live && setErr(String(e)));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return [data, err, () => setN((x) => x + 1)];
}
