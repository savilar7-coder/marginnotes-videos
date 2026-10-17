# Margin Notes video pipeline (from Oct 16, 2026)

No HeyGen. Free render + ElevenLabs voice clone + GitHub hosting + Metricool.

1. Paintings: add `name url` lines to `images.txt` (Wikimedia public-domain), push → workflow `fetch-images` saves to `assets/`.
2. Narration: add `scripts/<date>-<slug>.txt`, push → workflow `tts` calls ElevenLabs (default voice "Daniel", stock, id onwK4e9ZLuTAKqWW03F9, chosen Oct 16; Sergio's clone bCVtrce9vY4IQKrTHVnM is kept but not used; start a script with "#voice: <id>" to override; model eleven_multilingual_v2) with secret ELEVENLABS_API_KEY → `audio/<name>.mp3` + `.json` (character timestamps).
3. Timing: `python3 docs/align.py audio/<name>.json "anchor 1" "anchor 2" ...` → beat start times (add 0.3s; renderer delays voice 300ms).
4. Render: `python3 docs/render.py spec.json out.mp4` (needs `npm i @fontsource/playfair-display @fontsource/inter` and Python Playwright). Spec: image, focus, zoom, audio, black_until, beats[{t, html}]. Classes: big, mid, q, sub, cap, red, list, stamp, ul. ~4-5 min per 35 s video.
5. Publish: copy MP4 to `v/`, push; served at https://savilar7-coder.github.io/marginnotes-videos/v/<file>.mp4 (video/mp4).
6. Schedule: Metricool createScheduledPost with that URL (TikTok + Instagram Reel + YouTube Short, AI labels on — cloned voice).

Accounts: Metricool Starter $25/mo (brand 7432476). ElevenLabs Starter (40k credits/mo, ~600-700 chars per script). HeyGen Creator renews Nov 14 — cancel/downgrade before then.
