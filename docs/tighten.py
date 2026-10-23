"""Trim dead air out of a narration without a new voice take (critics, Oct 23: the pause after the hook left
1.6-1.9 s of silence and an empty screen right where viewers leave; even 1.5-2 s pauses felt like waiting).

    python docs/tighten.py audio/<name> [keep,long,words] [max_gap] [long_gap]
        -> audio/<name>-t.mp3 + audio/<name>-t.json (alignment shifted to match)
Panel edit grammar (Oct 23): no gap over EARLY_GAP s in the first 5 s; 30 s cuts max_gap ~0.45, 55 s ~0.6, beats <= 0.9.

Gap after the hook sentence -> at most HOOK_GAP s; every other gap between words -> at most MAX_GAP s, except before
the words in KEEP_LONG (the real beats), which may keep up to LONG_GAP s. The cut is taken from the middle of each gap,
so breaths and word tails stay. ElevenLabs v3 tags ([pause] ...) carry no timing of their own and are untouched.
"""
import json, re, subprocess, sys

HOOK_GAP, MAX_GAP, LONG_GAP, EARLY_GAP = 0.30, 0.85, 1.25, 0.25


def main(base, keep_long=(), max_gap=MAX_GAP, long_gap=LONG_GAP):
    al = json.load(open(base + ".json"))
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    # word spans on the character list (tags skipped, like rebrand_render.words_from_alignment)
    words, cur, in_tag = [], None, False
    for i, c in enumerate(chars):
        if c == "[":
            in_tag = True; continue
        if in_tag:
            in_tag = c != "]"; continue
        if c.isspace():
            if cur and re.search(r"\w", cur["w"]):
                words.append(cur)
            cur = None; continue
        if cur is None:
            cur = {"w": "", "i0": i, "s": st[i]}
        cur["w"] += c; cur["i1"] = i; cur["e"] = en[i]
    if cur and re.search(r"\w", cur["w"]):
        words.append(cur)
    keep = {k.lower() for k in keep_long}
    hook_end = next(j for j, w in enumerate(words) if re.search(r"[.?!…]$", w["w"]))
    cuts = []                                    # (start, length) in the original timeline
    for j in range(len(words) - 1):
        gap = words[j + 1]["s"] - words[j]["e"]
        nxt = re.sub(r"[^\w']", "", words[j + 1]["w"]).lower()
        cap = HOOK_GAP if j == hook_end else (long_gap if nxt in keep else max_gap)
        if words[j]["e"] < 5.0:          # nothing to wait for in the first 5 s
            cap = min(cap, EARLY_GAP)
        if gap > cap:
            cut = gap - cap
            cuts.append((words[j]["e"] + cap / 2, cut))
    # shift every character time by the cuts before it
    def shift(t):
        return t - sum(min(c, max(0.0, t - s)) for s, c in cuts)
    al2 = dict(al)
    al2["character_start_times_seconds"] = [round(shift(t), 4) for t in st]
    al2["character_end_times_seconds"] = [round(shift(t), 4) for t in en]
    json.dump(al2, open(base + "-t.json", "w"))
    # audio: keep everything except the cut windows
    keepf, t0 = [], 0.0
    for s, c in cuts:
        keepf.append(f"between(t,{t0:.4f},{s:.4f})"); t0 = s + c
    keepf.append(f"gte(t,{t0:.4f})")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base + ".mp3", "-af",
                    f"aselect='{'+'.join(keepf)}',asetpts=N/SR/TB", "-c:a", "libmp3lame", "-b:a", "192k",
                    base + "-t.mp3"], check=True)
    print(f"{base}-t: {len(cuts)} gaps trimmed, {sum(c for _, c in cuts):.1f} s removed")


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2].split(",") if len(a) > 2 and a[2] else (), *(float(x) for x in a[3:5]))
