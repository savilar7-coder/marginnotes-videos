"""Build a rebrand spec from a short plan: each shot starts on the first spoken word of its anchor phrase.

    python docs/make_spec.py plans/<name>.json      -> specs/<name>.json

Plan: {"name", "thinker", "emphasis": [...], "quote_source": [...],
       "shots": [[anchor phrase, image name, focus or null], ...]}   (first shot = hook, starts at 0)
Anchors are searched in order, so a repeated phrase (the loop line) matches its next occurrence.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rebrand_render import words_from_alignment  # noqa: E402

LEAD = 0.1  # cut this long before the anchor word is heard


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def main(plan_path):
    plan = json.load(open(plan_path, encoding="utf8"))
    name = plan["name"]
    words = words_from_alignment(json.load(open(f"audio/{name}.json")))
    toks = [norm(w[0]) for w in words]
    delay = plan.get("voice_delay", 0.15)
    shots, pos = [], 0
    for i, (anchor, img, focus) in enumerate(plan["shots"]):
        a = [norm(x) for x in anchor.split()]
        if i == 0:
            t = 0.0
        else:
            j = next((j for j in range(pos, len(toks)) if toks[j:j + len(a)] == a), None)
            if j is None:
                sys.exit(f"anchor not found after word {pos}: {anchor!r}")
            t, pos = round(max(0.0, words[j][1] + delay - LEAD), 2), j + 1
        s = {"t": t, "img": f"assets/{img}.jpg", "line": anchor, "zoom": [1.0, 1.12]}
        if focus:
            s["focus"] = focus
        shots.append(s)
    spec = {"bpm": 76, "snap": False, "dim": 0.9, "tail": 0.35, "vignette": 0.5,
            "audio": f"audio/{name}.mp3", "align": f"audio/{name}.json", "hook_until": 0.0,
            "thinker": plan["thinker"], "emphasis": plan["emphasis"], "quote_source": plan["quote_source"],
            "shots": shots}
    out = f"specs/{name}.json"
    json.dump(spec, open(out, "w"), indent=1)
    print(out, f"{len(shots)} shots, voice ends {words[-1][2]:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1])
