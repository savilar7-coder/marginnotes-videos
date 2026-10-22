# Margin Notes — pre-publish SOP (every video, no exceptions)

Owner of the final yes: Sergio. Claude runs steps 1-6 and asks for step 7.

## 1. Script (before voice)
- Hook = first spoken line, aimed at the viewer, readable on frame 1. Spec `"hook_card": 1.2` puts the whole first
  sentence on screen from frame 0 until it is spoken (Oct 22). Openers: conflict, question or "you" diagnosis; never comfort.
- Every "quoted" line is word for word from a public-domain text in `texts/` (source + translator named in the caption).
  Jung, Paz, Camus, Sartre = paraphrase only, labelled "his idea, in plain words".
- Sergio's own philosophy shapes each batch: at least one of his ideas per batch (ecosystem memory
  sergio-philosopher), told through the matching thinker in third person. No first-person "Sergio says" unless he asks;
  family/faith never.
- Ends with a share/save line and a loop back into the first line. Target 60-66 s (Creator Rewards needs > 60 s).

## 2. Pictures
- Only paintings from the thinker's set (`docs/art_sets.json`); one painting per spoken line, matching the line.
- No museum frames/walls in the image. No painting held > 4.5 s.

## 3. Render
- `dfvenv/Scripts/python docs/motion.py specs/<n>.json` then `venv/Scripts/python docs/rebrand_render.py specs/<n>-motion.json out/<n>.mp4`
- Spec `"lufs": -12.5` (single-pass loudnorm lands near -14 LUFS; unset = old -18 mix).

## 4. Machine gate (must PASS)
- `venv/Scripts/python docs/prepublish.py specs/<n>-motion.json out/<n>.mp4`
- Checks: file format, audio starts at 0, voice sync (no drift), no word shown before it is spoken, quotes verified,
  art set, longest hold, hook frame (+ hook card words), brightness, safe zones, loudness. FAIL = fix and re-render.
  WARN = step 5 looks at it.

## 5. Eyes and ears (Claude)
- Open every WARN frame (layout sheet). Watch the phone copy WITH SOUND start to finish: sync, picture matches the words,
  no cut-off text, ending loops.

## 6. Upload + schedule
- Push to `v/`, wait for the URL to return 200, schedule in Metricool (brand 7432476).
- Caption: hook + quote with source/translator + hashtags. AI labels OFF (Sergio's rule; label only AI people/faces or
  cloned real voices). No shop/journal links.
- Re-read the post from Metricool: time (Metricool once saved 1 h late), media URL, caption, AI flags.

## 7. Sergio's OK
- Send the phone preview (< 30 MB). Nothing new goes public without his yes. Re-renders of an approved script may be
  swapped in with a note to him.

## 8. After posting (next morning)
- TikTok Studio: views, avg watch, % past 3 s, followers gained, US share. Log it; feed the next batch.
