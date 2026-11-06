# Airlock demo video

The submission video, built with [Remotion](https://www.remotion.dev) (free licence: teams of up to 3) from real footage of the
live site, https://app.beyonders.duckdns.org.

| Step | Command (run in `video/`) |
|---|---|
| Install | `npm install` (once: `npx remotion browser ensure`) |
| Record the footage from the live site | `uv run --with playwright python scripts/record_footage.py` (Chrome; about 8 minutes; writes `public/clips/`) |
| Preview | `npm run dev` |
| Render (silent) | `npx remotion render AirlockDemo out/airlock-demo-silent.mp4 --codec=h264 --crf=18` |
| Voice-over script | `python scripts/voiceover.py > ../docs/submission/voiceover-script.md` |
| Add the voice-over | `npx remotion ffmpeg -i out/airlock-demo-silent.mp4 -i voiceover.m4a -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k out/airlock-demo.mp4` |

The edit lives in `src/timeline.json`: every scene, its source trims and speed changes, and the captions (which are also the
voice-over lines). Graphic scenes are in `src/scenes.tsx`; the footage scenes and transitions are in `src/AirlockDemo.tsx`.
