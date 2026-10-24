"""Margin Notes rebrand renderer (Oct 20 2026 sample).

Style: black-screen hook, 1-3 words at a time synced to the voice, moving public-domain paintings
inside a rounded frame, a new shot every 2-3 s, film grain + drifting dust, soft music bed.

    python docs/rebrand_render.py spec.json out.mp4

spec: {"audio": "audio/x.mp3", "align": "audio/x.json", "hook_until": 2.4,
       "emphasis": ["word", ...], "shots": [{"t": 0.0, "img": "assets/a.jpg", "focus": [0.5,0.4], "zoom": [1.0,1.15]}, ...]}
optional: "hook_card": 1.2  -> the whole first sentence on screen, still, from frame 0 until it has been spoken
                               (at least 1.2 s; critics, Oct 22)
          "lufs": -14       -> loudness-normalise the final mix (TikTok sits near -14; we were at -18)
          "card": [40, 250, 1040, 1650] -> painting card size (default 50, 330, 1030, 1590)
delivery test B (Oct 23, Sergio: motion, tidiness, attention beats):
          "captions": "karaoke" -> the whole 2-4 word chunk on screen at once, words light up as spoken (no lone "THE")
          "radius": 0, "border": false, "brand_y": 1480 -> full-screen painting (card [0, 0, 1080, 1920])
          "punch_words": ["shadow", ...], "punch": 0.06 -> quick zoom-in on the painting on these words only
          "hit_words": ["shadow", ...] -> low boom + short swell under these words (synthesised, no samples)
one painting, one story (Oct 23 concept upgrade): a shot may "focus_to": [x, y] (the camera travels across the same
painting from "focus" to "focus_to" while "zoom" goes z0 -> z1; no motion clip), "fit": true (the whole painting,
letterboxed over a dark blurred copy = the reveal) and "card_text": ["line 1", "line 2"] (the end card: painting + source).
ElevenLabs v3 audio tags in the script ("[pause]", "[whispers]") are not spoken and never become captions.
"""
import json, math, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FX0, FY0, FX1, FY1 = 50, 330, 1030, 1590          # rounded frame (inside TikTok safe area)
RADIUS = 70
FONT = "C:/Windows/Fonts/seguibl.ttf"              # Segoe UI Black
QFONT = "C:/Windows/Fonts/georgiai.ttf"            # quotes: Georgia Italic
SFONT = "C:/Windows/Fonts/segoeuib.ttf"            # small source line
RED = (255, 92, 97)
TEXT_Y = 860                                       # caption centre (safe zone 230-1382)
FADE_IN, FADE_OUT, BEAT0 = 2.0, 3.0, 1.0           # music fades + first beat (spec "music_start": "full" -> 0.05/0.3/0.0)
MAXW = 700                                         # widest caption line (860 for full-screen karaoke)


def words_from_alignment(al):
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, t0, in_tag = [], "", None, False
    for c, s, e in zip(chars, st, en):
        if c == "[":                     # v3 audio tag: direction for the voice, not a word
            in_tag = True; continue
        if in_tag:
            in_tag = c != "]"; continue
        if c.isspace():
            if cur and not re.search(r"\w", cur):    # a lone dash or "..." left between tags
                cur = ""; continue
            if cur:
                words.append([cur, t0, last_e]); cur = ""
            continue
        if not cur:
            t0 = s
        cur += c; last_e = e
    if cur and re.search(r"\w", cur):
        words.append([cur, t0, last_e])
    return words


FUNC = {"a", "an", "the", "to", "of", "in", "on", "at", "by", "for", "with", "from", "and", "or", "but", "if", "is",
        "are", "was", "were", "be", "his", "her", "their", "your", "you're", "my", "our", "its", "that", "this", "these",
        "those", "who", "which", "than", "not", "no", "does", "do", "did", "as", "into", "so", "when", "what", "before",
        "after", "about", "every", "some", "it's", "i", "he", "she", "they", "we",
        "one", "two", "three", "four", "five", "ten", "hundred", "thousand"}


def _clean(w):
    return re.sub(r"[^\w']", "", w).lower()


def _opens_quote(w):
    return w[:1] in ('"', "“")


def _closes_quote(w):
    return bool(re.search(r'["”][.,;:!?…]*$', w)) and not (_opens_quote(w) and len(w) <= 2)


def chunk(words, emphasis, by_meaning=False, solo=()):
    """Captions of 1-4 words that never end on a small word ("the", "a", "to"...): small words move to the next
    screen with the word they belong to. A spoken quote stays one caption (kind "quote") shown whole.
    by_meaning (karaoke, critics Oct 23): an emphasis word does not force its own screen, so phrases stay whole
    ("AND YOU CALL IT FATE", not "IT FATE"); up to 4 words, 5 when the 5th closes the sentence."""
    out, cur = [], []

    def flush_with_carry():
        nonlocal cur
        carry = []
        while cur and _clean(cur[-1][0]) in FUNC and not re.search(r"[.,:;?!…]$", cur[-1][0]):
            carry.insert(0, cur.pop())
        if cur:
            out.append({"kind": "text", "words": cur})
        cur = carry

    i, name_tail = 0, False
    while i < len(words):
        w, s_, e_ = words[i]
        if _opens_quote(w):
            if cur:
                out.append({"kind": "text", "words": cur}); cur = []
            q, j = [words[i]], i
            while not _closes_quote(words[j][0]) and j + 1 < len(words):
                j += 1; q.append(words[j])
            out.append({"kind": "quote", "words": q})
            i = j + 1
            continue
        c = _clean(w)
        lone_small = len(cur) == 1 and c in emphasis and not re.search(r"[.,:;?!…]$", cur[0][0])
        ends_short = len(cur) == 3 and re.search(r"[.,:;?!…]$", w) and len(c) <= 6 and c not in emphasis
        if by_meaning:
            full = len(cur) >= 4 and not (len(cur) == 4 and re.search(r"[.,:;?!…]$", w))
            brk = cur and not name_tail and (full or s_ - cur[-1][2] > 0.35 or c in solo)
        else:
            brk = cur and not name_tail and not lone_small and (c in emphasis or (len(cur) >= 3 and not ends_short)
                                                                or s_ - cur[-1][2] > 0.35)
        if brk:
            flush_with_carry()
        cur.append((w, s_, e_))
        nxt = words[i + 1][0] if i + 1 < len(words) else ""
        # keep a name together ("Marcus Aurelius"): a capitalised emphasis word followed by another capitalised word
        keep_name = (c in emphasis and w[:1].isupper() and nxt[:1].isupper() and not _opens_quote(nxt)
                     and not re.search(r"[.,:;?!…]$", w))
        if name_tail or (not keep_name and (re.search(r"[.,:;?!\"…]$", w) or (c in emphasis and not by_meaning))):
            out.append({"kind": "text", "words": cur}); cur = []
        name_tail = keep_name
        i += 1
    if cur:
        out.append({"kind": "text", "words": cur})
    caps = []
    for i, c in enumerate(out):
        start = c["words"][0][1]
        end = out[i + 1]["words"][0][1] if i + 1 < len(out) else c["words"][-1][2] + 0.6
        caps.append({"kind": c["kind"], "words": [x[0] for x in c["words"]],
                     "times": [(x[1], x[2]) for x in c["words"]], "t0": start, "t1": end})
    return caps


def quote_layer(words, k, source=None):
    """A spoken quote shown whole in italic serif; words already spoken are cream, the current one red,
    upcoming ones dimmed. Optional small source line underneath."""
    qsize = 96 if len(words) <= 8 else 80 if len(words) <= 14 else 64   # short quotes big enough for a phone (Oct 22)
    f = ImageFont.truetype(QFONT, qsize)
    txt = [w for w in words]
    txt[0] = "“" + re.sub(r'^["“]', "", txt[0])
    txt[-1] = re.sub(r'["”]([.,;:!?…]*)$', r"\1", txt[-1]) + "”"
    space = f.getlength(" ")
    lines, line, wline = [], [], 0.0
    for idx, w in enumerate(txt):
        wl = f.getlength(w)
        if line and wline + space + wl > 820:
            lines.append(line); line, wline = [], 0.0
        line.append((idx, w, wl)); wline += (space if len(line) > 1 else 0) + wl
    if line:
        lines.append(line)
    lh = int(qsize * 1.31)
    sf = ImageFont.truetype(SFONT, 28) if source else None
    hgt = lh * len(lines) + (70 if source else 0)
    pad = 120
    img = Image.new("RGBA", (W, hgt + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for ln in lines:
        lw = sum(x[2] for x in ln) + space * (len(ln) - 1)
        x = (W - lw) / 2
        for idx, w, wl in ln:
            col = RED + (255,) if idx == k else ((237, 230, 218, 255) if idx < k else (237, 230, 218, 120))
            d.text((x, y), w, font=f, fill=col, stroke_width=3, stroke_fill=(10, 8, 8, 255))
            x += wl + space
        y += lh
    if source:
        st = source.upper()
        sw = sf.getlength(st) + 4 * len(st)
        x = (W - sw) / 2
        for ch in st:
            d.text((x, y + 26), ch, font=sf, fill=(201, 191, 174, 230))
            x += sf.getlength(ch) + 4
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    halo.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(44)).point(lambda a: min(255, int(a * 1.7))))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(halo); out.alpha_composite(img)
    return out


def split_long_shots(shots, dur, max_len=4.2):
    """No painting holds longer than ~max_len s: long shots become a wide view then closer views of the same art."""
    out = []
    for i, s in enumerate(shots):
        end = shots[i + 1]["t"] if i + 1 < len(shots) else dur
        n = max(1, math.ceil((end - s["t"]) / max_len)) if s["t"] > 0 or end > max_len else 1
        z0 = s.get("zoom", [1.0, 1.12])[0]
        for k in range(n):
            part = dict(s)
            part.pop("clip", None)
            part["t"] = round(s["t"] + k * (end - s["t"]) / n, 3)
            if k:
                zz = z0 * (1.0 + 0.3 * k)
                part["zoom"] = [zz, zz + 0.1]
                part["drift"] = [(-1) ** k, 0]
            out.append(part)
    return out


GHOST = None   # spec "ghost": "grey" -> unspoken karaoke words in solid grey, never faint red (art director, Oct 23)


def text_layer(words, emphasis, big, lit=None):
    """Render one caption as an RGBA image: emphasis word huge + red, others white.
    lit (karaoke captions): only the first `lit` words are bright; the rest of the chunk shows faint."""
    clean = lambda w: re.sub(r"[^\w']", "", w).lower()
    disp = [re.sub(r'^[\"“]|[\"”]$', "", w) for w in words]
    disp = [d if re.search(r"\w\.\w", d) else (d.strip(".,;:") or d) for d in disp]   # "a.m." keeps its dots
    has_em = any(clean(w) in emphasis for w in words)
    lit = len(words) if lit is None else lit
    lines = []
    for i, (w, d) in enumerate(zip(words, disp)):
        em = clean(w) in emphasis
        size = (250 if big else 230) if em else (190 if big else 150)
        if has_em and not em:
            size = 110
        lines.append(([(d.upper(), 255 if i < lit else 115)], size, RED if em else (255, 255, 255), i < lit))
    # pack consecutive plain words into lines of <= 9 characters; an emphasis word always gets its own line
    packed = []
    for ws, size, col, lit_ in lines:
        if GHOST == "grey" and not lit_:
            ws, col = [(t, 255) for t, _ in ws], (150, 146, 140)
        n = lambda ws_: len(" ".join(t for t, _ in ws_))
        if packed and col != RED and packed[-1][2] != RED and n(packed[-1][0]) + 1 + n(ws) <= 9:
            packed[-1] = (packed[-1][0] + ws, min(packed[-1][1], size), col)
        else:
            packed.append((ws, size, col))
    lines = packed
    rend = []
    for ws, size, col in lines:
        txt = " ".join(t for t, _ in ws)
        f = ImageFont.truetype(FONT, size)
        while f.getbbox(txt)[2] > MAXW and size > 40:
            size -= 6; f = ImageFont.truetype(FONT, size)
        bb = f.getbbox(txt)
        rend.append((ws, txt, f, col, bb))
    hgt = sum(bb[3] - bb[1] + 34 for *_, bb in rend)
    pad = 120
    img = Image.new("RGBA", (W, hgt + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for ws, txt, f, col, bb in rend:
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        for t_, al in ws:
            d.text((x, y - bb[1]), t_, font=f, fill=col + (al,), stroke_width=5, stroke_fill=(12, 8, 8, al))
            x += f.getlength(t_ + " ")
        y += bb[3] - bb[1] + 34
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda a: int(a * 0.85)))
    # soft dark halo so words stay readable on bright parts of a painting (Sonnet review, Oct 20)
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    halo.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(48)).point(lambda a: min(255, int(a * 1.6))))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(halo); out.alpha_composite(shadow, (0, 6)); out.alpha_composite(img)
    return out


def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, x)))


def shot_frame(img, focus, z0, z1, p, drift):
    """Ken Burns: crop around focus with zoom z0->z1 over progress p, slight drift."""
    fw, fh = FX1 - FX0, FY1 - FY0
    iw, ih = img.size
    base = max(fw / iw, fh / ih)
    z = z0 + (z1 - z0) * ease(p)
    scale = base * z
    cw, ch = fw / scale, fh / scale
    cx = focus[0] * iw + drift[0] * (p - 0.5) * cw * 0.08
    cy = focus[1] * ih + drift[1] * (p - 0.5) * ch * 0.08
    cx = min(max(cx, cw / 2), iw - cw / 2); cy = min(max(cy, ch / 2), ih - ch / 2)
    cw, ch = min(cw, iw), min(ch, ih)
    cx = min(max(cx, cw / 2), iw - cw / 2); cy = min(max(cy, ch / 2), ih - ch / 2)
    box = (max(0.0, cx - cw / 2), max(0.0, cy - ch / 2), min(iw, cx + cw / 2), min(ih, cy + ch / 2))
    return img.resize((fw, fh), Image.BICUBIC, box=box)


def music_bed(seconds, path, sr=44100):
    """Soft ambient pad (A minor - F - C - G), generated here: no licence issues."""
    t = np.arange(int(seconds * sr)) / sr
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    out = np.zeros_like(t)
    dur = 8.0
    for i in range(int(seconds / dur) + 1):
        ch = chords[i % 4]
        s0 = i * dur
        m = (t >= s0 - 1.5) & (t < s0 + dur + 1.5)
        tt = t[m] - s0
        env = np.clip(np.minimum((tt + 1.5) / 2.5, (dur + 1.5 - tt) / 2.5), 0, 1)
        for f in ch:
            out[m] += env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt + 0.3)) * 0.06
        out[m] += env * np.sin(2 * np.pi * ch[0] / 2 * tt) * 0.08
    out *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t)
    fade = np.clip(np.minimum(t / FADE_IN, (seconds - t) / FADE_OUT), 0, 1)
    out = np.tanh(out * fade * 1.4) * 0.5
    pcm = (np.stack([out, np.roll(out, 300)], 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def music_beat(seconds, path, bpm=76, sr=44100):
    """Pad + soft piano plucks on every beat + low pulse on each bar. Generated here: no licence issues.
    Returns the beat times so shots can cut on the beat."""
    music_bed(seconds, path, sr)
    with wave.open(path) as w:
        base = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32767
    n = base.shape[0]
    t = np.arange(n) / sr
    beat = 60.0 / bpm
    beats = np.arange(BEAT0, seconds - 1.0, beat)
    chords = [[440.0, 523.25, 659.25], [349.23, 440.0, 523.25], [392.0, 523.25, 659.25], [392.0, 493.88, 587.33]]
    out = np.zeros(n, np.float32)
    for i, b in enumerate(beats):
        ch = chords[(i // 8) % 4]
        f = ch[i % 3] if i % 4 != 3 else ch[0] * 2
        i0 = int(b * sr); L = min(n - i0, int(sr * 1.6))
        if L <= 0:
            continue
        tt = np.arange(L) / sr
        env = np.exp(-tt * 3.2) * (1 - np.exp(-tt * 400))
        tone = np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt) + 0.12 * np.sin(2 * np.pi * 3 * f * tt)
        out[i0:i0 + L] += (0.10 if i % 4 == 0 else 0.07) * env * tone
        if i % 4 == 0:  # bar pulse
            Lk = min(n - i0, int(sr * 0.35)); tk = np.arange(Lk) / sr
            out[i0:i0 + Lk] += 0.22 * np.exp(-tk * 14) * np.sin(2 * np.pi * (55 + 40 * np.exp(-tk * 30)) * tk)
    fade = np.clip(np.minimum(t / FADE_IN, (seconds - t) / FADE_OUT), 0, 1)
    mix = base + np.stack([out, np.roll(out, 180)], 1) * fade[:, None]
    pcm = (np.tanh(mix * 1.2) * 0.8 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    return beats


def ease_out_back(x):
    x = max(0.0, min(1.0, x)); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


class ClipReader:
    """Frames of a pre-rendered motion clip (docs/motion.py), streamed one shot at a time."""
    def __init__(self):
        self.path, self.proc, self.idx, self.last = None, None, -1, None
        self.fw, self.fh = FX1 - FX0, FY1 - FY0

    def get(self, path, idx):
        if path != self.path:
            if self.proc:
                self.proc.kill()
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={self.fw}:{self.fh}",
                                          "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                         stdout=subprocess.PIPE)
            self.path, self.idx, self.last = path, -1, None
        n = self.fw * self.fh * 3
        while self.idx < idx:
            buf = self.proc.stdout.read(n)
            if len(buf) < n:            # clip ended: hold the last frame
                break
            self.last = np.frombuffer(buf, np.uint8).reshape(self.fh, self.fw, 3)
            self.idx += 1
        return self.last


def fit_frame(img, p):
    """The whole painting, fitted to the frame width and placed low, over a dark blurred copy (the reveal shot)."""
    fw, fh = FX1 - FX0, FY1 - FY0
    iw, ih = img.size
    sc = max(fw / iw, fh / ih)
    bg = img.resize((int(iw * sc) + 1, int(ih * sc) + 1)).crop((0, 0, fw, fh)).filter(ImageFilter.GaussianBlur(30))
    bg = Image.eval(bg, lambda v: int(v * 0.35))
    k = 1.0 + 0.04 * ease(p)
    w = int(fw * 0.96 * k); h = int(ih * w / iw)
    fg = img.resize((w, h), Image.BICUBIC)
    bg.paste(fg, ((fw - w) // 2, int(fh * 0.65) - h // 2))
    return bg


def card_layer(lines):
    """End card text: painting title (serif italic) + source line, centred, for the reveal shot."""
    f1, f2 = ImageFont.truetype(QFONT, 46), ImageFont.truetype(SFONT, 30)
    img = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((W // 2, 60), lines[0], font=f1, fill=(240, 232, 214, 255), anchor="mm")
    if len(lines) > 1:
        d.text((W // 2, 130), lines[1].upper(), font=f2, fill=(200, 190, 175, 255), anchor="mm")
    return img


def add_hits(path, times, sr_default=44100):
    """Mix a soft low boom (with a short noise swell into it) under each time into the music wav."""
    with wave.open(path) as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32).reshape(-1, ch)
    rng = np.random.default_rng(3)
    tb = np.arange(int(0.9 * sr)) / sr
    boom = (np.sin(2 * np.pi * 52 * tb) + 0.5 * np.sin(2 * np.pi * 104 * tb)) * np.exp(-tb / 0.28) * np.minimum(1, tb / 0.006)
    # phone speakers drop everything under ~150 Hz (editor, Oct 23): add a 160/240 Hz body and a short click on top
    boom += (0.7 * np.sin(2 * np.pi * 160 * tb) + 0.35 * np.sin(2 * np.pi * 240 * tb)) * np.exp(-tb / 0.12)
    boom[:int(0.004 * sr)] += rng.normal(0, 0.6, int(0.004 * sr))
    ts = np.arange(int(0.35 * sr)) / sr
    noise = np.convolve(rng.normal(0, 1, len(ts)), np.ones(40) / 40, "same")
    swell = noise * (ts / ts[-1]) ** 2.5 * 0.5
    for t in times:
        i = int(t * sr)
        for sig, at in ((boom * 0.5, i), (swell, i - len(swell))):
            s0, s1 = max(0, at), min(len(a), at + len(sig))
            if s1 > s0:
                a[s0:s1] += (sig[s0 - at:s1 - at] * 9000)[:, None]
    with wave.open(path, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(sw); w.setframerate(sr)
        w.writeframes(np.clip(a, -32767, 32767).astype(np.int16).tobytes())


def main(spec_path, out_path):
    spec = json.load(open(spec_path))
    global FX0, FY0, FX1, FY1, RADIUS, MAXW, FADE_IN, FADE_OUT, BEAT0, GHOST
    GHOST = spec.get("ghost")
    if spec.get("card"):                 # bigger painting card (Oct 22 deliberation); old specs keep the default
        FX0, FY0, FX1, FY1 = spec["card"]
    RADIUS = spec.get("radius", RADIUS)
    if spec.get("music_start") == "full":   # music at full level on frame 0, no hole at the loop seam
        FADE_IN, FADE_OUT, BEAT0 = 0.05, 0.3, 0.0
    karaoke = spec.get("captions") == "karaoke"
    if karaoke:
        MAXW = 860
    emphasis = {e.lower() for e in spec["emphasis"]}
    words = words_from_alignment(json.load(open(spec["align"])))
    voice_delay = spec.get("voice_delay", 0.15)
    for w in words:
        w[1] += voice_delay; w[2] += voice_delay
    caps = chunk(words, emphasis, karaoke, {x.lower() for x in spec.get("solo_words", [])})
    caps[0]["t0"] = 0.0
    hook_card = spec.get("hook_card", 0.0)
    hook_words = []
    if hook_card:
        for w in words:
            hook_words.append(w)
            if re.search(r"[.?!…]$", w[0]):
                break
        hook_card = max(hook_card, hook_words[-1][2])   # hold until the sentence is spoken: no echo afterwards
    dur = words[-1][2] + spec.get("tail", 1.6)
    hook_until = spec["hook_until"]
    shots = spec["shots"]
    if not any(s.get("clip") for s in shots):        # motion specs are already split by docs/motion.py
        shots = split_long_shots(shots, dur, spec.get("max_shot", 4.2))
    imgs = {s["img"]: Image.open(s["img"]).convert("RGB") for s in shots}
    qsrc = spec.get("quote_source")
    qsrc = qsrc if isinstance(qsrc, list) else [qsrc] * 20
    qn = 0
    for c in caps:
        if c["kind"] == "quote":
            c["source"] = qsrc[qn] if qn < len(qsrc) else None; qn += 1
    # auto-exposure: bring dark paintings (Rembrandt, La Tour) up to a common brightness
    gain = {k: float(np.clip(105.0 / max(1.0, np.asarray(v.convert("L"), np.float32).mean()), 0.75, 2.2))
            for k, v in imgs.items()}

    # mask for the rounded frame
    mask = Image.new("L", (FX1 - FX0, FY1 - FY0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, FX1 - FX0 - 1, FY1 - FY0 - 1), RADIUS, fill=255)
    # vignette for the painting
    yy, xx = np.mgrid[0:FY1 - FY0, 0:FX1 - FX0]
    r = np.sqrt(((xx - (FX1 - FX0) / 2) / ((FX1 - FX0) / 2)) ** 2 + ((yy - (FY1 - FY0) / 2) / ((FY1 - FY0) / 2)) ** 2)
    k = spec.get("vignette", 1.0)
    vign = np.clip(1.0 + 0.15 * k - 0.55 * k * r ** 2, 1.0 - 0.65 * k, 1.0)[..., None]
    rng = np.random.default_rng(7)
    grains = [rng.normal(0, 14, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    dust = rng.random((60, 4))  # x, y, speed, size

    def starts(ws_):
        ws_ = {x.lower() for x in ws_}
        return [w[1] for w in words if re.sub(r"[^\w']", "", w[0]).lower() in ws_]
    punch_t, punch_amp = starts(spec.get("punch_words", [])), spec.get("punch", 0.06)
    hit_t = starts(spec.get("hit_words", []))

    def punch(t):
        """0 -> punch_amp in 0.08 s at each punch word, then eases back over ~0.5 s."""
        b = 0.0
        for h in punch_t:
            dt = t - h
            if -0.08 < dt < 1.2:
                b = max(b, punch_amp * (min(1.0, (dt + 0.08) / 0.08) if dt < 0 else math.exp(-dt / 0.35)))
        return b

    layers = {}
    def layer(i, big, t=0.0):
        c = caps[i]
        if c["kind"] == "quote":
            k = max((j for j, (ws, we) in enumerate(c["times"]) if ws <= t), default=0)
            key = (i, "q", k)
            if key not in layers:
                layers[key] = quote_layer(c["words"], k, c.get("source"))
            return layers[key]
        # build the phrase word by word: a word appears only once it is spoken (iNQ style, no text ahead of voice)
        k = max(1, sum(1 for ws, we in c["times"] if ws <= t + 0.02))
        key = (i, big, k)
        if key not in layers:   # karaoke: the whole chunk shows, unspoken words faint
            layers[key] = text_layer(c["words"], emphasis, big, k) if karaoke else text_layer(c["words"][:k], emphasis, big)
        return layers[key]

    # caption timeline for the pre-publish gate: when each word appears vs when it is spoken
    tl = []
    for c in caps:
        for j, (w, (ws, we)) in enumerate(zip(c["words"], c["times"])):
            shown = c["t0"] if (c["kind"] == "quote" or j == 0) else max(c["t0"], ws - 0.02)
            # karaoke: later words show faint ahead of the voice, but light up only when spoken
            tl.append({"word": w, "shown": round(shown, 3), "spoken": round(ws, 3), "kind": c["kind"]})
    # the hook card shows the first sentence ahead of the voice on purpose; the gate checks it separately
    tl += [{"word": w, "shown": 0.0, "spoken": round(ws, 3), "kind": "hook"} for w, ws, we in hook_words]
    json.dump(tl, open(out_path + ".captions.json", "w"))
    hook_layer = text_layer([w for w, _, _ in hook_words], emphasis, True) if hook_words else None
    # captions of the hook sentence already shown on the card are skipped afterwards (no "SIDE" echo)
    first_after = next((i for i, c in enumerate(caps) if c["times"][0][0] > hook_words[-1][1] + 0.01),
                       len(caps)) if hook_words else 0
    if karaoke and hook_words and first_after < len(caps):
        hook_card = max(hook_card, caps[first_after]["t0"])   # never an empty screen after the hook (critics Oct 23)
    mus = out_path + ".music.wav"
    if spec.get("bpm"):
        beats = music_beat(dur, mus, spec["bpm"])
        for sh in shots:
            if spec.get("snap", True) and sh["t"] > hook_until + 0.5:
                sh["t"] = float(beats[np.argmin(np.abs(beats - sh["t"]))])
        shots.sort(key=lambda x: x["t"])
    else:
        music_bed(dur, mus)
    if hit_t:
        add_hits(mus, hit_t)
    clips = ClipReader()
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", spec["audio"], "-i", mus,
                           "-filter_complex", f"[1:a]adelay={int(voice_delay * 1000)}:all=1,volume=1.0[v];[2:a]volume={0.0 if spec.get('music') is False else spec.get('music_volume', 0.55)}" + "".join(f",volume={f_}:enable='between(t,{a_},{b_})'" for a_, b_, f_ in spec.get("duck", [])) + "[m];[v][m]amix=inputs=2:duration=longest:normalize=0" + (f",loudnorm=I={spec['lufs']}:TP=-1.5:LRA=11,aresample=44100" if spec.get("lufs") else "") + "[a]",
                           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-b:v", "6M", "-maxrate", "8M", "-bufsize", "12M",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                           out_path], stdin=subprocess.PIPE)
    nframes = int(dur * FPS)
    sheet = []
    for fi in range(nframes):
        t = fi / FPS
        frame = Image.new("RGB", (W, H), (0, 0, 0))
        if t >= hook_until:
            si = max(i for i, s in enumerate(shots) if s["t"] <= t)
            s = shots[si]
            t_end = shots[si + 1]["t"] if si + 1 < len(shots) else dur
            p = (t - s["t"]) / max(0.1, t_end - s["t"])
            if s.get("clip"):
                pic = clips.get(s["clip"], int((t - s["t"]) * FPS))
            elif s.get("fit"):
                pic = fit_frame(imgs[s["img"]], p)
            else:
                f0 = s.get("focus", [0.5, 0.5]); f1 = s.get("focus_to", f0); e = ease(p)
                pic = shot_frame(imgs[s["img"]], [f0[0] + (f1[0] - f0[0]) * e, f0[1] + (f1[1] - f0[1]) * e],
                                 *s.get("zoom", [1.0, 1.12]), p, [0, 0] if "focus_to" in s else s.get("drift", [1, 0]))
            a = np.asarray(pic, np.float32) * vign * spec.get("dim", 0.62) * gain[s["img"]] * s.get("gain", 1.0)
            qi = max((i for i, c in enumerate(caps) if c["t0"] <= t), default=0)
            if caps[qi]["kind"] == "quote" and t < caps[qi]["t1"] + 0.05:
                a *= spec.get("quote_dim", 0.6)   # darker painting behind a quote so the serif text reads on a phone
            flick = 1.0 + 0.025 * math.sin(t * 7.3) + 0.015 * math.sin(t * 13.1)
            a *= flick
            # entry flash-in for each new shot (fast fade from black)
            if si > 0 and spec.get("cut_dip", True):   # soft 0.1 s dip at a cut (from 80%), not a dark flash: no strobe (Fable review)
                a *= min(1.0, (t - s["t"]) / 0.10 * 0.2 + 0.8)
            pic = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
            b = punch(t)
            if b > 0.002:            # punch-in: scale up around the centre, keep the frame size
                pw, ph = pic.size
                cw, ch = pw / (1 + b), ph / (1 + b)
                pic = pic.resize((pw, ph), Image.BILINEAR, box=((pw - cw) / 2, (ph - ch) / 2, (pw + cw) / 2, (ph + ch) / 2))
            frame.paste(pic, (FX0, FY0), mask)
            # thin frame border
            if spec.get("border", True):
                ImageDraw.Draw(frame).rounded_rectangle((FX0, FY0, FX1 - 1, FY1 - 1), RADIUS, outline=(60, 60, 60), width=2)
        # dust (everywhere, subtle)
        d = ImageDraw.Draw(frame)
        for x, y, sp, sz in dust:
            px = (x * W + 25 * math.sin(t * 0.6 + y * 9)) % W
            py = (y * H - t * (20 + 50 * sp)) % H
            c = int(90 + 80 * sz)
            rr = 1 + 2.5 * sz
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(c, c, c - 10))
        # caption
        ci = max((i for i, c in enumerate(caps) if c["t0"] <= t), default=0)
        if hook_layer is not None and t < hook_card:
            hy = spec.get("hook_y", TEXT_Y)   # low slot keeps the face on frame 0 clear (art director, Oct 23)
            frame.paste(hook_layer, ((W - hook_layer.width) // 2, hy - hook_layer.height // 2), hook_layer)
        elif ci >= first_after and t < caps[ci]["t1"] + 0.05:
            L = layer(ci, t < hook_until, t)
            p = min(1.0, (t - caps[ci]["t0"]) / 0.2) if ci > 0 else 1.0
            k = ease_out_back(p)
            sc = 0.82 + 0.18 * k
            dy = int((1 - k) * 46)
            L2 = L.resize((max(1, int(L.width * sc)), max(1, int(L.height * sc))), Image.BILINEAR) if sc < 0.999 or sc > 1.001 else L
            if p < 1.0:
                al = L2.getchannel("A").point(lambda a, m=min(1.0, p * 2.5): int(a * m))
                L2 = L2.copy(); L2.putalpha(al)
            frame.paste(L2, ((W - L2.width) // 2, TEXT_Y - L2.height // 2 + dy), L2)
        # end card on the reveal shot (painting + source)
        if t >= hook_until and shots[max(i for i, s_ in enumerate(shots) if s_["t"] <= t)].get("card_text"):
            st_ = shots[max(i for i, s_ in enumerate(shots) if s_["t"] <= t)]
            key = ("card", tuple(st_["card_text"]))
            if key not in layers:
                layers[key] = card_layer(st_["card_text"])
            cl = layers[key]
            al = min(1.0, (t - st_["t"]) / 0.4)
            if al < 1.0:
                cl = cl.copy(); cl.putalpha(cl.getchannel("A").point(lambda a, m=al: int(a * m)))
            frame.paste(cl, (0, 330), cl)
        # brand mark
        if t >= hook_until:
            f = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
            d.text((W // 2, spec.get("brand_y", FY1 - 46)), "MARGIN NOTES", font=f, fill=(200, 200, 200), anchor="mm")
        # grain
        g = np.asarray(Image.fromarray(grains[fi % 6]).resize((W, H)), np.float32)[..., None]
        a = np.clip(np.asarray(frame, np.float32) + g, 0, 255).astype(np.uint8)
        ff.stdin.write(a.tobytes())
        if fi % (FPS * 3) == 0:
            sheet.append(Image.fromarray(a).resize((216, 384)))
    ff.stdin.close(); ff.wait()
    cols = 8
    rows = math.ceil(len(sheet) / cols)
    sh = Image.new("RGB", (cols * 216, rows * 384))
    for i, im in enumerate(sheet):
        sh.paste(im, ((i % cols) * 216, (i // cols) * 384))
    sh.save(out_path + ".sheet.jpg", quality=85)
    print("done", out_path, f"{dur:.1f}s", len(caps), "captions")


def timeline_only(spec_path, out_path):
    """Write only <out>.captions.json (same caption logic as main) for a video rendered by this code version."""
    spec = json.load(open(spec_path))
    emphasis = {e.lower() for e in spec["emphasis"]}
    words = words_from_alignment(json.load(open(spec["align"])))
    d = spec.get("voice_delay", 0.15)
    for w in words:
        w[1] += d; w[2] += d
    caps = chunk(words, emphasis, spec.get("captions") == "karaoke"); caps[0]["t0"] = 0.0
    tl = [{"word": w, "spoken": round(ws, 3), "kind": c["kind"],
           "shown": round(c["t0"] if (c["kind"] == "quote" or j == 0) else max(c["t0"], ws - 0.02), 3)}
          for c in caps for j, (w, (ws, we)) in enumerate(zip(c["words"], c["times"]))]
    json.dump(tl, open(out_path + ".captions.json", "w"))


if __name__ == "__main__":
    if sys.argv[1] == "--timeline":
        timeline_only(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
