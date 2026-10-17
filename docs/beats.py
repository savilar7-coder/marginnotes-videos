"""Build render.py beats from a word-timed transcript.

old/<name>.json (from the fetch-old workflow, faster-whisper) = {"text":..., "words":[{"w","s","e"}]}
beats = [("anchor words", "<html>"), ...]  -> each beat starts when its anchor phrase starts being spoken.
The first beat (the cover) always starts at t=0. Times include the renderer's 0.3 s voice delay.
"""
import json, re

def _norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))

def build(words_json, beats, delay=0.3, lead=0.05, min_cover=1.2):
    words = json.load(open(words_json))["words"]
    toks = [_norm(x["w"]) for x in words]
    out, pos = [], 0
    for k, (anchor, html) in enumerate(beats):
        if k == 0:
            out.append({"t": 0.0, "html": html}); continue
        a = [_norm(x) for x in anchor.split()]
        for i in range(pos, len(toks) - len(a) + 1):
            if toks[i:i + len(a)] == a:
                out.append({"t": round(max(0.0, words[i]["s"] + delay - lead), 2), "html": html}); pos = i + len(a); break
        else:
            raise SystemExit(f"anchor not found after word {pos}: {anchor!r}")
    if len(out) > 1 and out[1]["t"] < min_cover:   # the cover must stay readable on the first swipe
        out[1]["t"] = min_cover
    return out
