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


def chunk(words, emphasis):
    """1-3 words per caption; break on punctuation, pauses, and before/after emphasis words."""
    out, cur = [], []
    for i, (w, s, e) in enumerate(words):
        clean = re.sub(r"[^\w']", "", w).lower()
        if cur and (clean in emphasis or len(cur) >= 3 or s - cur[-1][2] > 0.35):
            out.append(cur); cur = []
        cur.append((w, s, e))
        if re.search(r"[.,:;?!\"…]$", w) or clean in emphasis:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    caps = []
    for i, c in enumerate(out):
        start = c[0][1]
        end = out[i + 1][0][1] if i + 1 < len(out) else c[-1][2] + 0.6
        caps.append({"words": [x[0] for x in c], "t0": start, "t1": end})
    return caps


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
    # stack: each word on its own line if emphasis present, else one/two lines
    if not has_em and sum(len(l[0]) for l in lines) <= 9:
        lines = [(" ".join(l[0] for l in lines), lines[0][1], (255, 255, 255))]
    rend = []
    for txt, size, col in lines:
        f = ImageFont.truetype(FONT, size)
        while f.getbbox(txt)[2] > 770 and size > 40:
            size -= 6; f = ImageFont.truetype(FONT, size)
        bb = f.getbbox(txt)
        rend.append((txt, f, col, bb))
    hgt = sum(bb[3] - bb[1] + 34 for *_, bb in rend)
    img = Image.new("RGBA", (W, hgt + 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 40
    for txt, f, col, bb in rend:
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        d.text((x, y - bb[1]), txt, font=f, fill=col + (255,))
        y += bb[3] - bb[1] + 34
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda a: int(a * 0.85)))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (0, 6)); out.alpha_composite(img)
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
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
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
    """Frames of a pre-rendered motion clip (DepthFlow), loaded one shot at a time."""
    def __init__(self):
        self.path, self.frames = None, None
    def get(self, path, idx):
        if path != self.path:
            fw, fh = FX1 - FX0, FY1 - FY0
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={fw}:{fh}", "-r", str(FPS),
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
            self.frames = np.frombuffer(raw, np.uint8).reshape(-1, fh, fw, 3)
            self.path = path
        return self.frames[min(idx, len(self.frames) - 1)]


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
    imgs = {s["img"]: Image.open(s["img"]).convert("RGB") for s in shots}
    # auto-exposure: bring dark paintings (Rembrandt, La Tour) up to a common brightness
    gain = {k: float(np.clip(105.0 / max(1.0, np.asarray(v.convert("L"), np.float32).mean()), 0.75, 2.2))
            for k, v in imgs.items()}

    # mask for the rounded frame
    mask = Image.new("L", (FX1 - FX0, FY1 - FY0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, FX1 - FX0 - 1, FY1 - FY0 - 1), RADIUS, fill=255)
    # vignette for the painting
    yy, xx = np.mgrid[0:FY1 - FY0, 0:FX1 - FX0]
    r = np.sqrt(((xx - (FX1 - FX0) / 2) / ((FX1 - FX0) / 2)) ** 2 + ((yy - (FY1 - FY0) / 2) / ((FY1 - FY0) / 2)) ** 2)
    vign = np.clip(1.15 - 0.55 * r ** 2, 0.35, 1.0)[..., None]
    rng = np.random.default_rng(7)
    grains = [rng.normal(0, 14, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
    dust = rng.random((60, 4))  # x, y, speed, size

    layers = {}
    def layer(i, big):
        if (i, big) not in layers:
            layers[(i, big)] = text_layer(caps[i]["words"], emphasis, big)
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
                           "-filter_complex", "[1:a]volume=1.0[v];[2:a]volume=0.55[m];[v][m]amix=inputs=2:duration=longest:normalize=0[a]",
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
            a *= min(1.0, (t - s["t"]) / 0.18 + 0.15)
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
            L = layer(ci, t < hook_until)
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
