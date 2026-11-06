"""Find speech segments in a voice-over WAV (16 kHz mono) and line them up against the caption times.

Usage: python scripts/speech_segments.py audio/vo16k.wav
Prints each detected phrase (start-end) and, for each caption line, the nearest phrase start and the offset.
"""
import json, math, os, struct, sys, wave

path = sys.argv[1]
w = wave.open(path, "rb")
sr, n = w.getframerate(), w.getnframes()
raw = w.readframes(n)
samples = struct.unpack(f"<{n}h", raw)

win = int(sr * 0.05)  # 50 ms windows
rms = []
for i in range(0, n - win, win):
    chunk = samples[i:i + win]
    rms.append(math.sqrt(sum(s * s for s in chunk) / win))
srt = sorted(rms)
noise = srt[int(len(srt) * 0.15)]
peak = srt[int(len(srt) * 0.95)]
thr = noise + (peak - noise) * 0.12
print(f"noise {noise:.0f}  peak {peak:.0f}  threshold {thr:.0f}")

# speech = above threshold; merge gaps < 0.35 s, drop blips < 0.15 s
segs, cur = [], None
for i, v in enumerate(rms):
    t = i * 0.05
    if v > thr:
        if cur is None: cur = [t, t + 0.05]
        else: cur[1] = t + 0.05
    elif cur is not None and t - cur[1] > 0.35:
        segs.append(cur); cur = None
if cur: segs.append(cur)
segs = [s for s in segs if s[1] - s[0] >= 0.15]

# phrases: merge segments separated by < 0.6 s
phr = []
for s in segs:
    if phr and s[0] - phr[-1][1] < 0.6: phr[-1][1] = s[1]
    else: phr.append(list(s))
print(f"{len(phr)} phrases")
for a, b in phr: print(f"  {a:7.2f} - {b:7.2f}")

here = os.path.dirname(os.path.abspath(__file__))
t = json.load(open(os.path.join(here, "..", "src", "timeline.json"), encoding="utf-8"))
fps, tr = t["fps"], round(t["transitionSec"] * t["fps"])
start = 0
lines = []
for s in t["scenes"]:
    dur = sum((b - a) / r for a, b, r in s["parts"]) if s["kind"] == "clip" else s["dur"]
    for c in s["captions"]: lines.append((start / fps + c["from"], start / fps + c["to"], s["id"], c["text"]))
    start += round(dur * fps) - tr
json.dump({"phrases": phr, "lines": lines}, open(os.path.join(here, "..", "audio", "segments.json"), "w"), indent=1)
print("\ncaption start -> nearest phrase start (offset)")
for a, b, sid, text in lines:
    near = min(phr, key=lambda p: abs(p[0] - a))
    print(f"  {a:7.2f}  {near[0]:7.2f}  {near[0] - a:+6.2f}  [{sid}] {text[:60]}")
