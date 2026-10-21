"""Margin Notes rebrand renderer (Oct 20 2026 sample).

Style: black-screen hook, 1-3 words at a time synced to the voice, moving public-domain paintings
inside a rounded frame, a new shot every 2-3 s, film grain + drifting dust, soft music bed.

    python docs/rebrand_render.py spec.json out.mp4

spec: {"audio": "audio/x.mp3", "align": "audio/x.json", "hook_until": 2.4,
       "emphasis": ["word", ...], "shots": [{"t": 0.0, "img": "assets/a.jpg", "focus": [0.5,0.4], "zoom": [1.0,1.15]}, ...]}
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


def words_from_alignment(al):
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, t0 = [], "", None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append([cur, t0, last_e]); cur = ""
            continue
        if not cur:
            t0 = s
        cur += c; last_e = e
    if cur:
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


def chunk(words, emphasis):
    """Captions of 1-4 words that never end on a small word ("the", "a", "to"...): small words move to the next
    screen with the word they belong to. A spoken quote stays one caption (kind "quote") shown whole."""
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
        if cur and not name_tail and not lone_small and (c in emphasis or (len(cur) >= 3 and not ends_short)
                                                          or s_ - cur[-1][2] > 0.35):
            flush_with_carry()
        cur.append((w, s_, e_))
        nxt = words[i + 1][0] if i + 1 < len(words) else ""
        # keep a name together ("Marcus Aurelius"): a capitalised emphasis word followed by another capitalised word
        keep_name = (c in emphasis and w[:1].isupper() and nxt[:1].isupper() and not _opens_quote(nxt)
                     and not re.search(r"[.,:;?!…]$", w))
        if name_tail or (not keep_name and (re.search(r"[.,:;?!\"…]$", w) or c in emphasis)):
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
    f = ImageFont.truetype(QFONT, 64)
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
    lh = 84
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


def text_layer(words, emphasis, big):
    """Render one caption as an RGBA image: emphasis word huge + red, others white."""
    clean = lambda w: re.sub(r"[^\w']", "", w).lower()
    disp = [re.sub(r'^[\"“]|[\"”]$', "", w).strip(".,;:") or w for w in words]
    has_em = any(clean(w) in emphasis for w in words)
    lines = []
    for w, d in zip(words, disp):
        em = clean(w) in emphasis
        size = (250 if big else 230) if em else (190 if big else 150)
        if has_em and not em:
            size = 110
        lines.append((d.upper(), size, RED if em else (255, 255, 255)))
    # pack consecutive plain words into lines of <= 9 characters; an emphasis word always gets its own line
    packed = []
    for txt, size, col in lines:
        if packed and col != RED and packed[-1][2] != RED and len(packed[-1][0]) + 1 + len(txt) <= 9:
            packed[-1] = (packed[-1][0] + " " + txt, min(packed[-1][1], size), col)
        else:
            packed.append((txt, size, col))
    lines = packed
    rend = []
    for txt, size, col in lines:
        f = ImageFont.truetype(FONT, size)
        while f.getbbox(txt)[2] > 700 and size > 40:
            size -= 6; f = ImageFont.truetype(FONT, size)
        bb = f.getbbox(txt)
        rend.append((txt, f, col, bb))
    hgt = sum(bb[3] - bb[1] + 34 for *_, bb in rend)
    pad = 120
    img = Image.new("RGBA", (W, hgt + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for txt, f, col, bb in rend:
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        d.text((x, y - bb[1]), txt, font=f, fill=col + (255,), stroke_width=5, stroke_fill=(12, 8, 8, 255))
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
    fade = np.clip(np.minimum(t / 2.0, (seconds - t) / 3.0), 0, 1)
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
    beats = np.arange(1.0, seconds - 1.0, beat)
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
    fade = np.clip(np.minimum(t / 2.0, (seconds - t) / 3.0), 0, 1)
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


def main(spec_path, out_path):
    spec = json.load(open(spec_path))
    emphasis = {e.lower() for e in spec["emphasis"]}
    words = words_from_alignment(json.load(open(spec["align"])))
    voice_delay = spec.get("voice_delay", 0.15)
    for w in words:
        w[1] += voice_delay; w[2] += voice_delay
    caps = chunk(words, emphasis)
    caps[0]["t0"] = 0.0
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

    layers = {}
    def layer(i, big, t=0.0):
        c = caps[i]
        if c["kind"] == "quote":
            k = max((j for j, (ws, we) in enumerate(c["times"]) if ws <= t), default=0)
            key = (i, "q", k)
            if key not in layers:
                layers[key] = quote_layer(c["words"], k, c.get("source"))
            return layers[key]
        if (i, big) not in layers:
            layers[(i, big)] = text_layer(c["words"], emphasis, big)
        return layers[(i, big)]

    mus = out_path + ".music.wav"
    if spec.get("bpm"):
        beats = music_beat(dur, mus, spec["bpm"])
        for sh in shots:
            if spec.get("snap", True) and sh["t"] > hook_until + 0.5:
                sh["t"] = float(beats[np.argmin(np.abs(beats - sh["t"]))])
        shots.sort(key=lambda x: x["t"])
    else:
        music_bed(dur, mus)
    clips = ClipReader()
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-itsoffset", str(voice_delay), "-i", spec["audio"], "-i", mus,
                           "-filter_complex", f"[1:a]volume=1.0[v];[2:a]volume={0.0 if spec.get('music') is False else spec.get('music_volume', 0.55)}[m];[v][m]amix=inputs=2:duration=longest:normalize=0[a]",
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
            else:
                pic = shot_frame(imgs[s["img"]], s.get("focus", [0.5, 0.5]), *s.get("zoom", [1.0, 1.12]), p,
                                 s.get("drift", [1, 0]))
            a = np.asarray(pic, np.float32) * vign * spec.get("dim", 0.62) * gain[s["img"]]
            flick = 1.0 + 0.025 * math.sin(t * 7.3) + 0.015 * math.sin(t * 13.1)
            a *= flick
            # entry flash-in for each new shot (fast fade from black)
            if si > 0:   # soft 0.1 s dip at a cut (from 80%), not a dark flash: no strobe (Fable review)
                a *= min(1.0, (t - s["t"]) / 0.10 * 0.2 + 0.8)
            pic = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
            frame.paste(pic, (FX0, FY0), mask)
            # thin frame border
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
        if t < caps[ci]["t1"] + 0.05:
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
        # brand mark
        if t >= hook_until:
            f = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
            d.text((W // 2, FY1 - 46), "MARGIN NOTES", font=f, fill=(200, 200, 200), anchor="mm")
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


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
