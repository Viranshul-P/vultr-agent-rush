import React from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  AlertTriangle, Ban, Check, CheckCircle2, CircleDashed, Copy, FileSearch, FileText, Gavel, Inbox as InboxIcon,
  Info, Link2, Loader2, PauseCircle, ScanLine, ShieldAlert, ShieldCheck, UserCheck, X, XCircle,
} from "lucide-react";
import type { Invoice, Status } from "./api";
import { STAGES, STATUS_LABEL, StageKey, Tone, stageStates, stageSub, toneOf } from "./pipeline";

export const ease = [0.16, 1, 0.3, 1] as const;

/* ---------- brand ---------- */
export function Logo({ size = 24 }: { size?: number }) {
  // Two sealed doors with a chamber between: the product's mechanism as a mark.
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="1.5" y="1.5" width="21" height="21" rx="6.5" fill="var(--ink)" />
      <rect x="6" y="6" width="3" height="12" rx="1.2" fill="var(--ink-text)" />
      <rect x="15" y="6" width="3" height="12" rx="1.2" fill="var(--ink-text)" />
      <circle cx="12" cy="12" r="1.8" fill="var(--accent)" />
    </svg>
  );
}

/* ---------- formatting ---------- */
export function money(fields: any): string {
  if (!fields || fields.total == null) return "";
  const n = Number(fields.total);
  const v = Number.isFinite(n) ? n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(fields.total);
  return `${fields.currency || ""} ${v}`.trim();
}
export const pct = (x: any) => (x == null ? "—" : `${Math.round(x * 100)}%`);
export const secs = (ms: any) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)} s`);
export function timeOf(ts?: string) {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(+d) ? ts.slice(11, 19) : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/* ---------- status ---------- */
const TONE_ICON: Record<Tone, React.ReactNode> = {
  clear: <ShieldCheck />, done: <CheckCircle2 />, hold: <PauseCircle />, block: <Ban />,
  quar: <ShieldAlert />, proc: <i />, new: <i />,
};
export function StatusBadge({ status, queued }: { status: Status; queued?: boolean }) {
  const tone = toneOf(status, queued);
  const label = queued ? "Queued" : STATUS_LABEL[status] || status;
  return (
    <span className={`badge ${tone}`}>
      {tone === "proc" || tone === "new" ? <i /> : TONE_ICON[tone]}
      {label}
    </span>
  );
}

export const TONE_TITLE: Record<Tone, string> = {
  clear: "Cleared", done: "Posted", hold: "Held", block: "Blocked", quar: "Quarantined", proc: "Processing", new: "New",
};

/* ---------- pipeline ---------- */
const STAGE_ICON: Record<StageKey, React.ReactNode> = {
  scan: <ScanLine />, extract: <FileSearch />, validate: <Check />, links: <Link2 />, decide: <Gavel />, approve: <UserCheck />,
};

export function Pipeline({ inv }: { inv: Invoice }) {
  const states = stageStates(inv);
  const tone = toneOf(inv.status, inv.queued);
  const stopTone = tone === "quar" ? "quar" : tone === "hold" ? "hold" : "";
  const inChamber = states.slice(0, 4).some((s) => s === "active");
  const sealed = states.slice(0, 4).every((s) => s === "done" || s === "skip");
  const doneCount = states.filter((s) => s === "done" || s === "skip").length;
  const progress = Math.max(0, Math.min(1, (doneCount - (states[5] === "done" ? 1 : 0)) / 5));
  return (
    <div className="pipe" role="list" aria-label="Pipeline">
      <div className={`pipe-chamber ${inChamber ? "live" : ""} ${sealed ? "sealed" : ""}`}>
        <span className="pipe-label"><ShieldCheck /> gVisor sandbox · no network · no secrets</span>
      </div>
      <div className="pipe-track"><motion.i initial={false} animate={{ width: `${progress * 100}%` }} transition={{ duration: 0.6, ease }} /></div>
      {STAGES.map((s, i) => (
        <React.Fragment key={s.key}>
          {i === 4 && <div className="pipe-gap" />}
          <div role="listitem" className={`stage ${states[i]} ${states[i] === "stop" ? stopTone : ""}`} style={{ ["--col" as any]: i < 4 ? i + 1 : i + 2, ["--mrow" as any]: i + 1 }}>
            <motion.div className="node" initial={false}
              animate={states[i] === "active" ? { scale: [1, 1.06, 1] } : { scale: 1 }}
              transition={states[i] === "active" ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}>
              {states[i] === "active" && s.key !== "approve" ? <Loader2 className="spin" /> : states[i] === "stop" ? (stopTone === "quar" ? <ShieldAlert /> : stopTone === "hold" ? <PauseCircle /> : <Ban />) : STAGE_ICON[s.key]}
            </motion.div>
            <div className="sn">{s.name}</div>
            <div className="ss">{stageSub(s.key, states[i], inv)}</div>
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}

export function MiniPipe({ inv }: { inv: Invoice }) {
  const states = stageStates(inv);
  const tone = toneOf(inv.status, inv.queued);
  const stopCls = tone === "quar" ? "q" : tone === "hold" ? "h" : "x";
  return (
    <span className="mini" aria-hidden>
      {states.map((s, i) => <i key={i} className={s === "done" ? "d" : s === "active" ? "a" : s === "stop" ? stopCls : ""} style={s === "skip" ? { opacity: .35 } : undefined} />)}
    </span>
  );
}

/* ---------- page header ---------- */
export function PageHeader({ title, sub, actions }: { title: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="ph">
      <div className="ph-text"><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      {actions && <div className="ph-actions">{actions}</div>}
    </div>
  );
}

/* ---------- segmented control ---------- */
export function Seg<T extends string>({ value, onChange, items, id }: {
  value: T; onChange: (v: T) => void; id: string; items: { value: T; label: React.ReactNode; count?: number }[];
}) {
  return (
    <div className="seg" role="tablist">
      {items.map((it) => (
        <button key={it.value} role="tab" aria-selected={value === it.value} className={value === it.value ? "on" : ""} onClick={() => onChange(it.value)}>
          {value === it.value && <motion.span layoutId={`seg-${id}`} className="bgp" transition={{ duration: 0.25, ease }} />}
          <span>{it.label}{it.count != null && <span className="cnt">{it.count}</span>}</span>
        </button>
      ))}
    </div>
  );
}

/* ---------- skeleton & empty ---------- */
export const Sk = ({ w = "100%", h = 14, r }: { w?: number | string; h?: number; r?: number }) =>
  <div className="sk" style={{ width: w, height: h, borderRadius: r }} />;

export function Empty({ icon = <InboxIcon />, title, children, action }: { icon?: React.ReactNode; title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="empty">
      <div className="ei">{icon}</div>
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

/* ---------- copy ---------- */
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [ok, setOk] = React.useState(false);
  return (
    <button className="btn ghost sm" onClick={() => { navigator.clipboard?.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1400); }).catch(() => {}); }}>
      {ok ? <Check /> : <Copy />}{ok ? "Copied" : label}
    </button>
  );
}

/* ---------- drawer ---------- */
export function Drawer({ open, onClose, title, children, side }: { open: boolean; onClose: () => void; title: React.ReactNode; children: React.ReactNode; side?: React.ReactNode }) {
  React.useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", k); document.body.style.overflow = prev; };
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="scrim" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} />
          <motion.aside className="drawer" role="dialog" aria-modal="true"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: 0.38, ease }}>
            <div className="drawer-h">
              <h2 style={{ fontSize: 15 }}>{title}</h2>
              <span className="grow" />
              {side}
              <button className="icon-btn" onClick={onClose} aria-label="Close"><X /></button>
            </div>
            <div className="drawer-b">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

/* ---------- toasts ---------- */
type ToastT = { id: number; kind: "ok" | "err" | "info"; title: string; detail?: string };
const ToastCtx = React.createContext<(t: Omit<ToastT, "id">) => void>(() => {});
export const useToast = () => React.useContext(ToastCtx);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastT[]>([]);
  const push = React.useCallback((t: Omit<ToastT, "id">) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), t.kind === "err" ? 7000 : 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        <AnimatePresence initial={false}>
          {items.map((t) => (
            <motion.div key={t.id} layout className={`toast ${t.kind}`}
              initial={{ opacity: 0, y: 14, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, x: 24, transition: { duration: 0.15 } }}
              transition={{ duration: 0.3, ease }}>
              {t.kind === "ok" ? <CheckCircle2 /> : t.kind === "err" ? <XCircle /> : <Info />}
              <div><div className="tt">{t.title}</div>{t.detail && <div className="td">{t.detail}</div>}</div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------- misc ---------- */
export function Callout({ kind = "info", children }: { kind?: "info" | "warn" | "bad"; children: React.ReactNode }) {
  return <div className={`callout ${kind}`}>{kind === "info" ? <Info /> : kind === "warn" ? <AlertTriangle /> : <XCircle />}<div>{children}</div></div>;
}

export function FadeIn({ children, delay = 0, y = 8, className, style }: { children: React.ReactNode; delay?: number; y?: number; className?: string; style?: React.CSSProperties }) {
  return (
    <motion.div className={className} style={style} initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay, ease }}>
      {children}
    </motion.div>
  );
}

/** Count up to a number once it scrolls into view. */
export function CountUp({ to, decimals = 0, prefix = "", suffix = "", duration = 0.9 }: { to: number; decimals?: number; prefix?: string; suffix?: string; duration?: number }) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const [v, setV] = React.useState(0);
  React.useEffect(() => {
    const el = ref.current; if (!el) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setV(to); return; }
    let raf = 0; let started = false;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting || started) return; started = true;
      const t0 = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - t0) / (duration * 1000));
        setV(to * (1 - Math.pow(1 - p, 4)));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.3 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to, duration]);
  return <span ref={ref} className="num">{prefix}{v.toFixed(decimals)}{suffix}</span>;
}

export { FileText, CircleDashed };
