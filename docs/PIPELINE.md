# UPDATE Oct 17, 2026 (12:30) — wins over everything below

Sergio approved after the TikTok audit (Ecosystem repo research/tiktok-audit/AUDIT.md):
* **Style W is the default** (`"style":"W"` in formats.py): bright full-colour paintings, short white captions, series tag
  on top (`"series":"STOIC RESET · #6"`), end card (`"endcard":"Follow for #7"`). 12–20 s scripts, ~25–40 words,
  one verified quote (karaoke + cite) or a clearly labelled paraphrase (Jung, Camus).
* **Series, numbered, never one-offs:** Stoic Reset (Seneca/Epictetus/Marcus), Shadow Work (Jung, paraphrase only),
  2 AM Philosophy (Nietzsche, Dostoevsky, Camus-paraphrase, late-night emotional). Keep numbering continuous.
* **5 TikToks a day:** 09:00, 13:00, 16:30, 19:30, 21:30 (America/Hermosillo). Instagram + YouTube only 1–2 a day
  (the 09:00 and 19:30 posts); the rest TikTok-only. English only.
* Captions: "<Series> #N: <hook>. <Author>, <work> (tr. <translator>): "<quote>". <one line>. Follow for #N+1." + 5 tags.
* After 72 h, the weakest videos go private (never delete).
* Local render (Sergio's PC): `PW_CHANNEL=msedge python docs/formats.py /abs/spec.json /abs/out.mp4`.
* Next numbers after Oct 19: Stoic Reset #6, Shadow Work #4, 2 AM Philosophy #5.

# Margin Notes video pipeline (from Oct 16, 2026)

No HeyGen. Free render + ElevenLabs voice clone + GitHub hosting + Metricool.

1. Paintings: add `name url` lines to `images.txt` (Wikimedia public-domain), push → workflow `fetch-images` saves to `assets/`.
2. Narration: add `scripts/<date>-<slug>.txt`, push → workflow `tts` calls ElevenLabs (default voice "Daniel", stock, id onwK4e9ZLuTAKqWW03F9, chosen Oct 16; Sergio's clone bCVtrce9vY4IQKrTHVnM is kept but not used; start a script with "#voice: <id>" to override; model eleven_multilingual_v2) with secret ELEVENLABS_API_KEY → `audio/<name>.mp3` + `.json` (character timestamps).
3. Timing: `python3 docs/align.py audio/<name>.json "anchor 1" "anchor 2" ...` → beat start times (add 0.3s; renderer delays voice 300ms).
4. Render: `python3 docs/render.py spec.json out.mp4` (needs `npm i @fontsource/playfair-display @fontsource/inter` and Python Playwright). Spec: image, focus, zoom, audio, black_until, beats[{t, html}]. Classes: big, mid, q, sub, cap, red, list, stamp, ul. ~4-5 min per 35 s video.
5. Publish: copy MP4 to `v/`, push; served at https://savilar7-coder.github.io/marginnotes-videos/v/<file>.mp4 (video/mp4).
6. Schedule: Metricool createScheduledPost with that URL (TikTok + Instagram Reel + YouTube Short, AI labels on — cloned voice).

Accounts: Metricool Starter $25/mo (brand 7432476). ElevenLabs Starter (40k credits/mo, ~600-700 chars per script). HeyGen Creator renews Nov 14 — cancel/downgrade before then.

## Layout rules for EVERY video (Sergio, Oct 17 2026 — after TikTok cropped the Nietzsche abyss video on an iPhone)

TikTok crops the sides of 9:16 videos on tall phones and covers the right edge (buttons) and the bottom (caption, username).

1. **Width:** all text between **10% and 85%** of the width (x 108–918 px of 1080). The right side holds TikTok's buttons.
2. **Height:** all text between **12% and 72%** of the height (y 230–1382 px of 1920). The bottom 25% is the caption.
3. **Contrast:** white (or near-white) text on the darkened painting. **No dark red on black** — red words use `#FF5C61` (`.red`); brand red `#D3202A` is only for lines and borders (margin line, underline, stamp).
4. **Hook:** max **2 lines** on the cover/first beat, huge words, readable on frame 1 (no fade-in on the first beat, no black opening behind it).
5. **Check before scheduling:** open the contact sheet (1 frame every 2 s, safe zone drawn in green) and confirm every frame. Don't schedule a video whose sheet you haven't looked at.

Both renderers enforce this automatically — `docs/formats.py` (styles A/B/C/D, through `docs/render2.py`) and `docs/render.py` (single painting):
every 0.5 s they measure every visible word and exit with **"SAFE-ZONE CHECK FAILED"** (exit code 2) if text leaves the zone or the frame-1 hook has more than 2 big lines; `render.py` also auto-shrinks long lines and flags text it had to shrink below 55% (= too many words: cut them).
Both write `<out>.sheet.jpg` (1 frame every 2 s, safe zone in green) next to the MP4.
Don't schedule anything rendered before Oct 17 2026 midday without checking it against these rules — the older animated format had none of them.
