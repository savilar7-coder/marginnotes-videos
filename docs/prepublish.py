"""Margin Notes pre-publish gate: every video must PASS this before it is scheduled.

    python docs/prepublish.py specs/<name>-motion.json out/<name>.mp4

Machine checks (FAIL blocks publishing, WARN needs a human look):
  1 file      1080x1920, 30 fps, 20-75 s (WARN under 60), < 60 MB, audio starts at 0 (no edit-list shift)
  2 sync      voice in the video sits at voice_delay +-0.05 s, no drift (start vs end)
  3 captions  no caption word shown before it is spoken (word-by-word reveal); a hook card (whole first
              sentence, frame 0, held until spoken) is allowed for the first sentence only, max 12 words
  9 loudness  integrated loudness -15.5 to -12.5 LUFS (TikTok ~-14)
  4 quotes    every "quoted" sentence in the script is word for word in texts/ (public-domain sources)
  5 art       every painting belongs to the thinker's set (docs/art_sets.json); no painting held > 4.5 s;
              no painting more than twice in a video, none from this thinker's previous video
  6 hook      frame at 0.1 s is not dark and shows text
  7 light     painting area not muddy (mean brightness >= 60 of 255)
  8 layout    scripts/video_qa.py safe zones (text under TikTok buttons/caption); flagged seconds -> look at the sheet
Exit code 0 = PASS (WARNs printed), 1 = FAIL.
"""
import glob, json, os, re, subprocess, sys
from collections import Counter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rebrand_render as rr  # noqa: E402

THINKER_KEYS = {"epictetus": "epictetus", "seneca": "seneca", "marcus": "marcus", "jung": "jung",
                "dostoevsky": "dostoevsky"}
results = []


def res(level, check, msg):
    results.append((level, check, msg))


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration,size:stream=codec_type,width,height,r_frame_rate,start_time",
                          "-of", "json", path], capture_output=True, text=True).stdout
    return json.loads(out)


def pcm(path, ss, t, sr=8000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(ss), "-t", str(t), "-i", path, "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    return a - a.mean()


def offset(src, out, sr=8000):
    L = len(src) + len(out)
    cc = np.fft.irfft(np.fft.rfft(out, L) * np.conj(np.fft.rfft(src, L)), L)
    return np.argmax(cc[: sr * 2]) / sr


def frame(path, t, w=270):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-vf",
                          f"scale={w}:{w * 16 // 9},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(w * 16 // 9, w).astype(np.float32)


def main(spec_path, video):
    spec = json.load(open(spec_path))
    name = os.path.basename(spec["audio"]).rsplit(".", 1)[0]
    delay = spec.get("voice_delay", 0.15)

    # 1 file
    p = probe(video)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    dur, size = float(p["format"]["duration"]), int(p["format"]["size"])
    ok = v["width"] == 1080 and v["height"] == 1920 and v["r_frame_rate"] == "30/1"
    res("PASS" if ok else "FAIL", "file", f"{v['width']}x{v['height']} @ {v['r_frame_rate']}")
    # 20 s floor: the Oct 23-29 length test runs ~28 s cuts next to ~58 s ones (deliberation, Oct 22)
    res("PASS" if 20 <= dur <= 75 else "FAIL", "file", f"length {dur:.1f} s" + ("" if dur >= 60 else " (under 60 s: no Creator Rewards)"))
    if dur < 60:
        res("WARN", "file", "under 60 s")
    res("PASS" if size < 60e6 else "FAIL", "file", f"size {size / 1e6:.0f} MB")
    st = float(a.get("start_time", 0)) if a else -1
    res("PASS" if a and abs(st) < 0.01 else "FAIL", "file", f"audio starts at {st:.3f} s (must be 0, else apps shift the voice)")

    # 2 sync
    src_a, out_a = pcm(spec["audio"], 5, 10), pcm(video, 5, 12)
    src_b, out_b = pcm(spec["audio"], dur - 20, 10), pcm(video, dur - 20, 12)
    o1, o2 = offset(src_a, out_a), offset(src_b, out_b)
    good = abs(o1 - delay) <= 0.05 and abs(o2 - delay) <= 0.05
    res("PASS" if good else "FAIL", "sync", f"voice offset {o1:.3f} s / {o2:.3f} s (want {delay:.2f})")

    # 3 captions: from the renderer's caption timeline, no plain word may appear > 0.15 s before it is spoken
    tlp = video + ".captions.json"
    if not os.path.exists(tlp):
        res("FAIL", "captions", "no caption timeline: render with the current docs/rebrand_render.py")
    else:
        tl = json.load(open(tlp))
        early = [x for x in tl if x["kind"] == "text" and x["spoken"] - x["shown"] > 0.15 and x["shown"] > 0.05]
        res("PASS" if not early else "FAIL", "captions",
            "every word appears when spoken" if not early else
            f"{len(early)} words shown early, e.g. " + ", ".join(f"'{x['word']}' {x['spoken'] - x['shown']:.1f}s early" for x in early[:3]))
        hook = [x for x in tl if x["kind"] == "hook"]
        if hook:
            ok = len(hook) <= 12
            res("PASS" if ok else "FAIL", "captions", f"hook card until {max(x['spoken'] for x in hook):.1f} s, {len(hook)} words: "
                + " ".join(x["word"] for x in hook))

    # 9 loudness
    ln = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-af", "ebur128", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", ln)
    if m:
        lufs = float(m[-1])
        res("PASS" if -15.5 <= lufs <= -12.5 else "WARN", "loudness", f"{lufs:.1f} LUFS (want about -14)")

    # 4 quotes
    script = os.path.join("scripts", name + ".txt")
    text = open(script, encoding="utf8").read() if os.path.exists(script) else ""
    norm = lambda x: re.sub(r"\s+", " ", x.replace("\u200b", "").replace("\xa0", " ")
                            .replace("\u2019", "'").replace("\u2014", "-").replace("--", "-")
                            .replace("\u201c", '"').replace("\u201d", '"')).strip().lower()
    corpus = ""
    for d in ("texts", os.environ.get("MN_EXTRA_TEXTS", "")):
        if d and os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith((".txt", ".html")):
                    corpus += " " + open(os.path.join(d, f), encoding="utf8", errors="ignore").read()
    corpus = norm(re.sub(r"<[^>]+>", " ", corpus))
    quotes = re.findall(r'["\u201c]([^"\u201d]{12,})["\u201d]', text)
    if not quotes:
        res("PASS", "quotes", "no direct quotes (paraphrase script)")
    for q in quotes:
        qn = norm(q).rstrip(".,;:")
        res("PASS" if qn in corpus else "FAIL", "quotes", f'"{q[:60]}..." {"found" if qn in corpus else "NOT FOUND in texts/"}')

    # 5 art
    sets = json.load(open(os.path.join(HERE, "art_sets.json")))
    thinker = spec.get("thinker") or next((v for k, v in THINKER_KEYS.items() if k in name), None)
    if thinker and thinker in sets:
        allowed = set(sets[thinker]["images"])
        bad = sorted({os.path.basename(s["img"]).rsplit(".", 1)[0] for s in spec["shots"]} - allowed)
        res("PASS" if not bad else "WARN", "art", f"{thinker} set" + (f"; outside set: {bad}" if bad else ""))
    else:
        res("WARN", "art", "thinker unknown: add \"thinker\" to the spec")
    shots = spec["shots"]
    longest = max((shots[i + 1]["t"] if i + 1 < len(shots) else dur) - s["t"] for i, s in enumerate(shots))
    res("PASS" if longest <= 4.5 else "FAIL", "art", f"longest painting hold {longest:.1f} s")
    # no repeats (Sergio, Oct 22): a painting comes back at most twice in a video (a long shot split into closer
    # views counts once) and never reuses a painting from this thinker's previous video
    imgs = [os.path.basename(s["img"]).rsplit(".", 1)[0] for s in shots]
    runs = [im for i, im in enumerate(imgs) if i == 0 or im != imgs[i - 1]]
    over = {im: n for im, n in Counter(runs).items() if n > 2}
    res("PASS" if not over else "FAIL", "art", f"{len(set(runs))} paintings in {len(runs)} shots"
        + (f"; used more than twice: {over}" if over else ""))
    base = lambda p: re.sub(r"(-v\d+)?(-motion)?\.json$", "", os.path.basename(p))
    me = base(spec_path)
    prev = sorted(p for p in glob.glob(os.path.join(os.path.dirname(spec_path) or ".", "*-motion.json"))
                  if base(p) < me and (json.load(open(p)).get("thinker") or
                                       next((v for k, v in THINKER_KEYS.items() if k in base(p)), None)) == thinker)
    if prev:
        last = json.load(open(prev[-1]))
        again = sorted(set(runs) & {os.path.basename(s["img"]).rsplit(".", 1)[0] for s in last["shots"]})
        res("PASS" if not again else "FAIL", "art", f"vs {base(prev[-1])}: "
            + ("no painting reused" if not again else f"{len(again)} reused: {again}"))

    # 6 hook + 7 light
    f0 = frame(video, 0.1)
    box = f0[int(0.17 * len(f0)):int(0.83 * len(f0)), int(0.05 * f0.shape[1]):int(0.95 * f0.shape[1])]
    bright_text = (box > 225).mean()
    res("PASS" if box.mean() >= 45 and bright_text > 0.005 else "FAIL", "hook",
        f"0.1 s: brightness {box.mean():.0f}, text {'yes' if bright_text > 0.005 else 'NO'}")
    means = [frame(video, t)[int(0.17 * 480):int(0.83 * 480), 13:257].mean() for t in np.linspace(2, dur - 2, 8)]
    res("PASS" if np.mean(means) >= 60 else "WARN", "light", f"painting brightness avg {np.mean(means):.0f} (want >= 60)")

    # 8 layout
    qa = next((c for c in [os.path.join(HERE, "..", "..", "..", "scripts", "video_qa.py"), "C:/Ecosystem/scripts/video_qa.py"]
               if os.path.exists(c)), None)
    if qa:
        out = subprocess.run([sys.executable, "-X", "utf8", qa, os.path.abspath(video)], capture_output=True, text=True,
                             cwd=os.path.dirname(os.path.dirname(os.path.abspath(qa)))).stdout
        try:
            j = json.loads(out[out.index("{"):])
            flags = [f"{z} @{r['worst_second']}s" for z, r in j["zones"].items() if not r["pass"]]
            res("PASS" if not flags else "WARN", "layout", "safe zones ok" if not flags else
                f"check these frames by eye (bright paint can trip it): {flags}; sheet {j.get('sheet')}")
        except Exception:
            res("WARN", "layout", "video_qa output unreadable")
    else:
        res("WARN", "layout", "video_qa.py not found")

    for lvl, c, m in results:
        print(f"{lvl:4} {c:9} {m}")
    fail = any(l == "FAIL" for l, _, _ in results)
    print("\nVERDICT:", "FAIL - do not publish" if fail else "PASS - continue with the human checks in the SOP")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
