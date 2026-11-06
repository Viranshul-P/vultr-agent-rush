import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, mono, sans } from "./theme";

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Fades and lifts its children in, starting `delay` seconds into the parent sequence. */
export const Rise: React.FC<{ delay?: number; dur?: number; y?: number; style?: React.CSSProperties; children: React.ReactNode }> = ({
  delay = 0, dur = 0.7, y = 24, style, children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [delay * fps, (delay + dur) * fps], [0, 1], { ...clamp, easing: ease });
  return <div style={{ opacity: p, translate: `0px ${(1 - p) * y}px`, ...style }}>{children}</div>;
};

/** The Airlock mark: two sealed doors with a chamber between. Doors close in, then the core pulses. */
export const Mark: React.FC<{ size: number; delay?: number }> = ({ size, delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const close = interpolate(frame, [delay * fps, (delay + 1.1) * fps], [1, 0], { ...clamp, easing: ease });
  const core = interpolate(frame, [(delay + 0.8) * fps, (delay + 1.4) * fps], [0, 1], { ...clamp, easing: ease });
  const ring = ((frame - (delay + 1.4) * fps) / fps) % 2.2;
  const ringP = frame > (delay + 1.4) * fps ? ring / 2.2 : 0;
  return (
    <svg width={size} height={size * 1.25} viewBox="0 0 560 700">
      <rect x="20" y="20" width="520" height="660" rx="56" fill={C.ink2} stroke={C.inkLine} strokeWidth="2" />
      <rect x={110 - close * 70} y="120" width="96" height="460" rx="34" fill={C.text} />
      <rect x={354 + close * 70} y="120" width="96" height="460" rx="34" fill={C.text} />
      <circle cx="280" cy="350" r={34 * core} fill={C.accent} />
      {ringP > 0 && <circle cx="280" cy="350" r={40 + ringP * 110} fill="none" stroke={C.accent} strokeOpacity={0.5 * (1 - ringP)} strokeWidth="3" />}
    </svg>
  );
};

/** Burned-in caption for the voice-over line, bottom-centre. Times in seconds relative to the scene. */
export type Line = { from: number; to: number; text: string };
export const Captions: React.FC<{ lines: Line[]; dark?: boolean }> = ({ lines, dark = true }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cur = lines.find((l) => t >= l.from && t < l.to);
  if (!cur) return null;
  const inP = interpolate(t, [cur.from, cur.from + 0.25], [0, 1], clamp);
  const outP = interpolate(t, [cur.to - 0.25, cur.to], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 56, pointerEvents: "none" }}>
      <div style={{
        opacity: Math.min(inP, outP), maxWidth: 1500, textAlign: "center", fontFamily: sans, fontSize: 40, fontWeight: 500, lineHeight: 1.3,
        color: dark ? C.text : C.text, background: "rgba(13,20,32,.86)", padding: "16px 30px", borderRadius: 16,
        boxShadow: "0 10px 40px rgba(0,0,0,.25)",
      }}>{cur.text}</div>
    </AbsoluteFill>
  );
};

/** Chapter tag shown top-left over footage, e.g. "Containment moment 1 of 2". */
export const Chapter: React.FC<{ label: string; tone?: string; durationSec: number }> = ({ label, tone = C.accent, durationSec }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [0.3 * fps, 0.9 * fps, (durationSec - 0.6) * fps, durationSec * fps], [0, 1, 1, 0], { ...clamp, easing: ease });
  return (
    <div style={{ position: "absolute", left: 40, top: 14, opacity: p, translate: `${(1 - p) * -20}px 0px`,
      display: "flex", alignItems: "center", gap: 14, background: "rgba(13,20,32,.9)", color: C.text, fontFamily: sans,
      fontSize: 30, fontWeight: 600, padding: "14px 24px", borderRadius: 999, boxShadow: "0 10px 30px rgba(0,0,0,.25)" }}>
      <span style={{ width: 14, height: 14, borderRadius: 4, background: tone }} />
      {label}
    </div>
  );
};

/** Highlight box drawn over footage to point at something, in footage pixel coordinates (1920x1080). */
export const Spotlight: React.FC<{ x: number; y: number; w: number; h: number; from: number; to: number; color?: string }> = ({
  x, y, w, h, from, to, color = C.accent,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [from * fps, (from + 0.4) * fps, (to - 0.3) * fps, to * fps], [0, 1, 1, 0], { ...clamp, easing: ease });
  if (p <= 0) return null;
  return <div style={{ position: "absolute", left: x - 8, top: y - 8, width: w + 16, height: h + 16, borderRadius: 18,
    border: `4px solid ${color}`, boxShadow: `0 0 0 9999px rgba(13,20,32,${0.35 * p})`, opacity: p, scale: `${0.98 + 0.02 * p}` }} />;
};

export const Eyebrow: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.accentLight }) => (
  <div style={{ fontFamily: sans, fontSize: 30, fontWeight: 600, letterSpacing: 5, textTransform: "uppercase", color }}>{children}</div>
);

export const Mono: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <span style={{ fontFamily: mono, ...style }}>{children}</span>
);
