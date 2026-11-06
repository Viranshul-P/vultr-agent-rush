import React from "react";
import { Video } from "@remotion/media";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { AbsoluteFill, Easing, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Captions, Chapter, Line } from "./components";
import { Business, Intro, Outro, Problem, Results, Roadmap } from "./scenes";
import { C, sans } from "./theme";
import timeline from "./timeline.json";

type Part = [number, number, number]; // [source from s, source to s, playback rate]
type Scene = {
  id: string; kind: string; dur?: number; src?: string; parts?: Part[];
  chapter?: { label: string; tone: string }; captions: Line[];
};

export const scenes = timeline.scenes as Scene[];
export const sceneSeconds = (s: Scene) =>
  s.kind === "clip" ? (s.parts as Part[]).reduce((a, [f, t, r]) => a + (t - f) / r, 0) : (s.dur as number);
export const totalFrames = () => {
  const fps = timeline.fps;
  const frames = scenes.reduce((a, s) => a + Math.round(sceneSeconds(s) * fps), 0);
  return frames - (scenes.length - 1) * Math.round(timeline.transitionSec * fps);
};

const SpeedBadge: React.FC<{ rate: number; frames: number }> = ({ rate, frames }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [0, 8, frames - 8, frames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  return (
    <div style={{ position: "absolute", right: 40, top: 14, opacity: p, display: "flex", alignItems: "center", gap: 10,
      background: "rgba(13,20,32,.9)", color: C.text, fontFamily: sans, fontSize: 28, fontWeight: 600, padding: "12px 22px", borderRadius: 999 }}>
      <svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 5l8 7-8 7zM12 5l8 7-8 7z" fill={C.accentLight} /></svg>
      {rate}× speed
    </div>
  );
};

/** One recorded segment: its parts play back to back (trimmed and speed-ramped), overlays on top. */
const ClipScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const { fps } = useVideoConfig();
  let at = 0;
  const total = sceneSeconds(scene);
  return (
    <AbsoluteFill style={{ background: C.paper }}>
      {(scene.parts as Part[]).map(([from, to, rate], i) => {
        const len = Math.round(((to - from) / rate) * fps);
        const start = at; at += len;
        return (
          <Sequence key={i} name={`${scene.id} part ${i + 1}`} from={start} durationInFrames={len}>
            <Video src={staticFile(scene.src as string)} trimBefore={Math.round(from * fps)} durationInFrames={Math.round((to - from) * fps)}
              playbackRate={rate} muted style={{ width: "100%", height: "100%" }} objectFit="cover" />
            {rate >= 2 && <SpeedBadge rate={rate} frames={len} />}
          </Sequence>
        );
      })}
      {scene.chapter && <Chapter label={scene.chapter.label} tone={scene.chapter.tone} durationSec={total} />}
      <Captions lines={scene.captions} />
    </AbsoluteFill>
  );
};

const Graphic: React.FC<{ scene: Scene }> = ({ scene }) => {
  const body = { intro: <Intro />, problem: <Problem />, results: <Results />, business: <Business />, roadmap: <Roadmap />, outro: <Outro /> }[scene.kind];
  return (
    <AbsoluteFill>
      {body}
      <Captions lines={scene.captions} />
    </AbsoluteFill>
  );
};

export const AirlockDemo: React.FC = () => {
  const { fps } = useVideoConfig();
  const tr = Math.round(timeline.transitionSec * fps);
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      <TransitionSeries name="Airlock demo">
        {scenes.flatMap((scene, i) => {
          const seq = (
            <TransitionSeries.Sequence key={scene.id} name={scene.id} durationInFrames={Math.round(sceneSeconds(scene) * fps)}>
              {scene.kind === "clip" ? <ClipScene scene={scene} /> : <Graphic scene={scene} />}
            </TransitionSeries.Sequence>
          );
          return i === 0 ? [seq] : [<TransitionSeries.Transition key={`t-${scene.id}`} presentation={fade()} timing={linearTiming({ durationInFrames: tr })} />, seq];
        })}
      </TransitionSeries>
    </AbsoluteFill>
  );
};
