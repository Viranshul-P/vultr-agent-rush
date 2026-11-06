"""Write the voice-over script, with each line's start and end time in the final video, from src/timeline.json.

Run from the video/ folder:  python scripts/voiceover.py > ../docs/submission/voiceover-script.md
"""
import json, os

here = os.path.dirname(os.path.abspath(__file__))
t = json.load(open(os.path.join(here, "..", "src", "timeline.json"), encoding="utf-8"))
fps, tr = t["fps"], round(t["transitionSec"] * t["fps"])

def mmss(sec):
    return f"{int(sec // 60)}:{sec % 60:04.1f}"

names = {"intro": "Intro (title, no speech)", "problem": "The problem", "overview": "How it works", "inbox": "The live inbox",
         "clean": "A clean invoice", "injection": "Containment moment 1: prompt injection", "phishing": "Containment moment 2: phishing link",
         "blocked": "Fraud signals", "receipt": "Signed receipt", "redteam": "Red Team drills", "results": "Results",
         "business": "Business", "roadmap": "Roadmap", "outro": "Close"}

out = ["# Voice-over script: Airlock demo video", "",
       "Read each line while the video plays; the times are where it appears in the final cut. The same text is burned in as captions,",
       "so small timing differences are fine. Leave a breath between lines rather than rushing to fill the gaps.", ""]
start = 0
for s in t["scenes"]:
    dur = sum((b - a) / r for a, b, r in s["parts"]) if s["kind"] == "clip" else s["dur"]
    n = round(dur * fps)
    t0 = start / fps
    out.append(f"## {mmss(t0)} · {names.get(s['id'], s['id'])}")
    if not s["captions"]:
        out.append("_(no narration)_")
    for c in s["captions"]:
        out.append(f"- **{mmss(t0 + c['from'])} to {mmss(t0 + c['to'])}**: {c['text']}")
    out.append("")
    start += n - tr
total = (start + tr) / fps
out.append(f"Total length: **{mmss(total)}**.")
print("\n".join(out))
