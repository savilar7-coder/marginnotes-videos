# Margin Notes — pre-publish SOP (every video, no exceptions)

Owner of the final yes: Sergio. Claude runs steps 1-6 and asks for step 7.

## 0. Panel rules (21-seat panel + 14-vote tally, Oct 23; ecosystem research/margin-notes-panel-2026-10-23/)
- **Twist by 2.5 s:** hook + twist in one breath ("You're not lazy. You're scared."); no [pause] or "..." before it;
  no gap > 0.25 s in the first 5 s (`docs/tighten.py <audio> <beat,words> <max_gap> <long_gap>`: 30 s 0.45/0.9, 55 s 0.6/0.9).
- **Frame 0 picture-first:** a face/eyes in the top half, hook card low (`hook_y` 1250), camera moving, music from frame 0.
- **Accuracy (scholar checklist):** every quote looked up in texts/; say who speaks (a character's thought = "Dostoevsky
  gave a character this thought", never "Dostoevsky said"); scene facts match the passage (read 20 lines around it);
  Jung/Camus/Paz/Sartre = "his idea, in plain words" tied to a work; our own tests/questions never after "he said";
  context when it changes meaning; no superlatives a biography wouldn't back.
- **Scene over lecture:** one real scene, one person, one problem; one open loop at 4-8 s paid after 70%; the last line
  leads INTO line 1 (never repeats it). Rotate hook formats: verdict / scene / question.
- **Voice tags:** max ~6 per 30 s, one whisper per video (never on the hook or a quote), [slowly] only on quotes.
- **Art:** literal match to the line; one subject; no printed text/frames/near-black; crop on the subject (explicit
  focus); oils by default; no near-duplicate files (art_sets.json `_duplicates`); keep nudity out of crops.
- **Edit:** hard cuts (`cut_dip` false), >= 3 picture changes in 0-5 s, boom audible on phones (160/240 Hz layer + click),
  punch 3.5%, 3 hits max; motion v2 (`docs/motion.py`: constant speed, height 0.42, wider travel, push not dolly/rise).
- **Rights:** depth model = Depth Anything V2 Small only (Large is non-commercial); max one credited sentence from
  Gummere/Jung/Camus. AI label stays OFF (Sergio, Oct 23).
- **Measure:** TikTok Studio at 48 h + 7 d (% at 0:02, 0:05, "most stopped at", avg watch); medians of >= 4 videos;
  one change per block of >= 4 videos.

## 1. Script (before voice)
- Hook = first spoken line, aimed at the viewer, readable on frame 1. Spec `"hook_card": 1.2` puts the whole first
  sentence on screen from frame 0 until it is spoken (Oct 22). Openers: conflict, question or "you" diagnosis; never comfort.
- Every "quoted" line is word for word from a public-domain text in `texts/` (source + translator named in the caption).
  Jung, Paz, Camus, Sartre = paraphrase only, labelled "his idea, in plain words".
- Sergio's own philosophy shapes each batch: at least one of his ideas per batch (ecosystem memory
  sergio-philosopher), told through the matching thinker in third person. No first-person "Sergio says" unless he asks;
  family/faith never.
- Ends with a line that leads into line 1. Length: see the length test in notes (Creator Rewards later needs > 60 s and 10K followers).
- **Delivery (style B, Sergio Oct 23 "way better"):** direct the voice with ElevenLabs v3 tags in the script:
  `[pause]` before turns, `[whispers]`/`[quietly]` on the intimate line, `[slowly]` before the quote, `[faster]` on
  lists, `...` for hesitation. Max 2-3 tags per sentence. Tags are never spoken or captioned. Expect ~130 wpm.
- Plan picks 3-5 `punch_words` (quick zoom) and 2-3 `hit_words` (low boom) on the real turns only, never more.

## 2. Pictures
- Only paintings from the thinker's set (`docs/art_sets.json`, ~30 each since Oct 22); one painting per spoken line,
  matching the line. Each painting once per video (the loop ending may return to the hook painting; Sergio Oct 23),
  none from this thinker's previous video, no two near-identical paintings in one video (gate FAILs repeats).
- New paintings: public domain, no frame/wall/round mount/watermark, no nudity TikTok could flag. Add to `images.txt`
  (cloud job fetches; Wikimedia rate-limits, so check every file opens) and eye-check a contact sheet first.
- No museum frames/walls in the image. No painting held > 4.5 s.

## 3. Render
- DepthFlow (3D motion) has ONE home: `C:\Users\Savil\tools\dfvenv` (outside every repo/worktree; tested Oct 22).
  Other Python: `C:\Ecosystem\venv`. Run from the marginnotes-videos folder:
- `C:/Users/Savil/tools/dfvenv/Scripts/python docs/motion.py specs/<n>.json` (~10 s per shot, writes motion/<n>/, git-ignored)
  then `C:/Ecosystem/venv/Scripts/python docs/rebrand_render.py specs/<n>-motion.json out/<n>.mp4`
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
