# render.py: Dostoevsky ep01 renderer (riso look B; from Camus cut 4). Adds falling snow + cut-out figure layers (fig=1). Plates + DA3 depth -> GPU parallax, slow push, code sun, dust, paper grain,
# word-synced captions. Usage: render.py timeline.json out.mp4 [t_from t_to]   (a range renders a single-scene test)
import json, sys, math, subprocess, functools
from render_guard import validate_inputs, finish_encoder, RenderInputError
D = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
args = [a for a in sys.argv[1:] if a != "--preflight-only"]
if not 2 <= len(args) <= 4:
    raise SystemExit("Usage: render_checked.py timeline.json out.mp4 [t_from t_to] [--preflight-only]")
TL = json.load(open(args[0], encoding="utf8")); OUT = args[1]
FPS, W, H = TL.get("fps", 30), 1920, 1080
T0 = float(args[2]) if len(args) > 2 else 0.0
T1 = float(args[3]) if len(args) > 3 else TL["dur"]
try:
    checked = validate_inputs(TL, D, T0, T1)
except RenderInputError as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(2)
if "--preflight-only" in sys.argv:
    print(json.dumps({"status": "asset_preflight_passed", **checked}))
    raise SystemExit(0)
import numpy as np, torch, torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont, ImageFilter
# Explicit CPU execution is restricted to this isolated public-runner build.
# The original CUDA renderer and all its guards remain unchanged locally.
torch.set_num_threads(4)
dev = torch.device("cpu")
SUN = torch.tensor([0xF9 / 255, 0x3B / 255, 0x04 / 255], device=dev).view(3, 1, 1)
INK = (28, 24, 22); BONE = (232, 222, 208)

@functools.lru_cache(maxsize=24)
def plate(name):
    try: im = Image.open(f"{D}/plates/{name}.png").convert("RGB")
    except FileNotFoundError as exc: raise RenderInputError(f"Required plate disappeared: {name}") from exc
    a = torch.from_numpy(np.asarray(im).copy()).to(dev).permute(2, 0, 1).float() / 255
    try: d = torch.from_numpy(np.asarray(Image.open(f"{D}/depth/{name}.png").convert("L").resize(im.size)).copy()).to(dev).float()[None] / 255
    except FileNotFoundError: d = torch.full((1, im.size[1], im.size[0]), .5, device=dev)
    # smooth the depth: hard depth edges tear flat shapes (jagged streaks); a soft field makes whole layers slide
    for _ in range(3): d = F.avg_pool2d(d[None], 41, 1, 20, count_include_pad=False)[0]
    # sky mask: flat cream paper (bright, low chroma) -> where a code sun may show through
    mx, mn = a.max(0).values, a.min(0).values
    sky = ((mx > .78) & (mx - mn < .28)).float()
    sky = torch.cumprod(F.max_pool2d(1 - sky[None, None], 7, 1, 3)[0, 0].lt(.5).float(), 0)[None]   # only the open sky above the first solid shape in each column
    sky = F.avg_pool2d(sky[None], 5, 1, 2)[0]
    return a, d, sky

@functools.lru_cache(maxsize=8)
def fig_layers(name):
    # bg = plate with the figure inpainted away; fg = the figure as RGBA (layers/<name>.png from cut_layers.py)
    try:
        bg = torch.from_numpy(np.asarray(Image.open(f"{D}/plates/{name}_bg.png").convert("RGB")).copy()).to(dev).permute(2, 0, 1).float() / 255
        fg = torch.from_numpy(np.asarray(Image.open(f"{D}/layers/{name}.png").convert("RGBA")).copy()).to(dev).permute(2, 0, 1).float() / 255
        return bg, fg
    except FileNotFoundError as exc: raise RenderInputError(f"Required figure layer disappeared: {name}") from exc

def snow(t, seed, n=140):
    # riso snow: soft paper-coloured flakes in 3 depths, drifting down and sideways; near ones bigger + faster
    rng = np.random.default_rng(seed); b = rng.random((n, 5)); out = torch.zeros((1, H, W), device=dev)
    for i in range(n):
        dep = .4 + 1.2 * b[i, 2]
        y = ((b[i, 1] + t * .045 * dep) % 1.1) - .05; x = (b[i, 0] + .02 * math.sin(t * .7 * dep + 6 * b[i, 3]) + t * .006 * dep) % 1
        r = 3.0 + 7.0 * dep * b[i, 4] ** 2; cx_, cy_ = int(x * W), int(y * H); R = int(r * 2.5) + 2
        y0, y1, x0, x1 = max(0, cy_ - R), min(H, cy_ + R), max(0, cx_ - R), min(W, cx_ + R)
        if y1 <= y0 or x1 <= x0: continue
        gy, gx = torch.meshgrid(torch.arange(y0, y1, device=dev) - cy_, torch.arange(x0, x1, device=dev) - cx_, indexing="ij")
        out[0, y0:y1, x0:x1] = torch.maximum(out[0, y0:y1, x0:x1], (.75 + .25 * b[i, 3]) * torch.exp(-(gx ** 2 + gy ** 2) / (r * r)).float())
    return out

yy, xx = torch.meshgrid(torch.linspace(-1, 1, H, device=dev), torch.linspace(-1, 1, W, device=dev), indexing="ij")
vign = (1 - .16 * ((xx ** 2 + yy ** 2) / 2) ** 1.4).clamp(0, 1)[None]
g = torch.Generator(device="cpu").manual_seed(7)
GRAIN = [(torch.rand((1, H // 2, W // 2), generator=g) - .5).to(dev) for _ in range(4)]
GRAIN = [F.interpolate(x[None], size=(H, W), mode="bilinear", align_corners=False)[0] for x in GRAIN]
ease = lambda u: u * u * (3 - 2 * u)

@functools.lru_cache(maxsize=1)
def clip_frames(path):
    path = str(__import__("pathlib").Path(D) / path) if not __import__("os").path.isabs(path) else path
    # cut 4: a Codex acting clip as the shot's picture (uint8 frames kept on the GPU; one clip at a time)
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(pr[0]), int(pr[1])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-r", str(FPS), "-"], capture_output=True, check=True).stdout
    fr = torch.frombuffer(bytearray(raw), dtype=torch.uint8).view(-1, h, w, 3).to(dev)
    return fr
def frame_shot(s, t):
    if s.get("clip"):
        fr = clip_frames(s["clip"]); i = int((t - s["t0"] + s.get("clip_off", 0)) * FPS); i = min(max(i, 0), fr.shape[0] - 1)
        a = fr[i].permute(2, 0, 1).float() / 255
        d = torch.full((1, a.shape[1], a.shape[2]), .5, device=dev); sky = torch.zeros_like(d)
    else:
        a, d, sky = plate(s["plate"])
        if s.get("fig"):
            L = fig_layers(s["plate"])
            if L: a = L[0]
    u = (t - s["t0"]) / max(.01, s["t1"] - s["t0"]); u = min(max(u, 0), 1)
    cx, cy, z0, z1 = s.get("cam", [.5, .5, 1.06, 1.12])
    z = z0 + (z1 - z0) * ease(u)
    ph, Hp, Wp = a.shape[1] / a.shape[2], a.shape[1], a.shape[2]
    # output pixel -> plate normalized coords. Plate aspect ~16:9 like the output
    if s.get("shake"):   # the rock rolling: a low rumble shake that dies away
        k = s["shake"] * max(0, 1 - u * 1.5) / W * 2
        cx += k * (math.sin(t * 37) + .6 * math.sin(t * 23.3)); cy += k * .7 * math.sin(t * 29.1)
    gx = (cx * 2 - 1) + xx / z; gy = (cy * 2 - 1) + yy / z
    gx = gx.clamp(-1 + 1 / z - 1, 1);
    amp = min(s.get("par", 7), 9) / W * 2
    w = 2 * math.pi * t / s.get("per", 9.0)
    dd = F.grid_sample(d[None], torch.stack([gx, gy], -1)[None], align_corners=False)[0, 0] - .5
    gx2 = gx + amp * dd * math.sin(w); gy2 = gy + .35 * amp * dd * math.cos(w * .7)
    grid = torch.stack([gx2, gy2], -1)[None]
    img = F.grid_sample(a[None], grid, padding_mode="border", align_corners=False)[0]
    if s.get("fig") and not s.get("clip") and fig_layers(s["plate"]):
        fg = fig_layers(s["plate"])[1]
        # the figure: no depth smear, its own life: slow breath (scale about its feet), a small sway, a counter-drift vs the set
        ys, xs = torch.nonzero(fg[3] > .5, as_tuple=True)
        fx = (xs.float().mean() / fg.shape[2] * 2 - 1).item() if len(xs) else 0; fy = (ys.max().float() / fg.shape[1] * 2 - 1).item() if len(ys) else 1
        br = 1 + .010 * math.sin(2 * math.pi * t / 4.2); sw = .0035 * math.sin(2 * math.pi * t / 6.3 + 1)
        dx = -amp * .9 * math.sin(w)
        gfx = fx + (gx - fx) / br + sw * (fy - gy) - dx; gfy = fy + (gy - fy) / br
        acting = s.get("acting")
        if acting and acting.get("kind") == "myshkin_answer":
            # A single, motivated gesture ends before the silence. The seated
            # lower body stays anchored; a soft neck transition avoids a cut seam.
            local_t = t - s["t0"]
            begin, finish = acting.get("interval", [4.4, 5.9])
            progress = min(1.0, max(0.0, (local_t - begin) / (finish - begin)))
            settle = progress ** 3 * (progress * (progress * 6 - 15) + 10)
            angle = math.radians(acting.get("angle_degrees", 9.0)) * settle
            px = (gx + 1) * fg.shape[2] / 2
            py = (gy + 1) * fg.shape[1] / 2
            pivot_x, pivot_y = acting.get("pivot", [235, 390])
            head_top, neck_bottom = acting.get("neck_blend", [350, 455])
            head = ((neck_bottom - py) / (neck_bottom - head_top)).clamp(0, 1)
            head = head * head * (3 - 2 * head)
            c, sn = math.cos(angle), math.sin(angle)
            rx = pivot_x + c * (px - pivot_x) + sn * (py - pivot_y)
            ry = pivot_y - sn * (px - pivot_x) + c * (py - pivot_y)
            upper_body = ((820 - py) / 430).clamp(0, 1)
            sx = px + (rx - px) * head
            sy = py + (ry - py) * head - 3.0 * settle * upper_body
            gfx, gfy = sx / fg.shape[2] * 2 - 1, sy / fg.shape[1] * 2 - 1
        elif acting and acting.get("kind") == "phone_lift":
            # Hand and phone travel as one rigid object. The outer sleeve stays
            # anchored at the frame edge through a soft forearm transition.
            begin, finish = acting.get("interval", [0.8, 2.4])
            if finish <= begin:
                raise RenderInputError("phone_lift interval must have positive duration")
            progress = min(1.0, max(0.0, (t - s["t0"] - begin) / (finish - begin)))
            settle = progress ** 3 * (progress * (progress * 6 - 15) + 10)
            angle = math.radians(acting.get("angle_degrees", 16.0)) * settle
            px = (gx + 1) * fg.shape[2] / 2
            py = (gy + 1) * fg.shape[1] / 2
            pivot_x, pivot_y = acting.get("pivot", [1672, 560])
            free_x, fixed_x = acting.get("forearm_blend", [1450, 1672])
            if fixed_x <= free_x:
                raise RenderInputError("phone_lift forearm blend must have positive width")
            weight = ((fixed_x - px) / (fixed_x - free_x)).clamp(0, 1)
            weight = weight * weight * (3 - 2 * weight)
            c, sn = math.cos(angle), math.sin(angle)
            rx = pivot_x + c * (px - pivot_x) + sn * (py - pivot_y)
            ry = pivot_y - sn * (px - pivot_x) + c * (py - pivot_y)
            gfx = (px + (rx - px) * weight) / fg.shape[2] * 2 - 1
            gfy = (py + (ry - py) * weight) / fg.shape[1] * 2 - 1
        elif acting and acting.get("kind") == "seated_lean":
            # The upper body approaches the listener once, then waits. Lap and
            # skirt remain seated; no looping sway is added to the gesture.
            begin, finish = acting["interval"]
            progress = min(1.0, max(0.0, (t - s["t0"] - begin) / (finish - begin)))
            settle = progress ** 3 * (progress * (progress * 6 - 15) + 10)
            angle = math.radians(acting["angle_degrees"]) * settle
            px = (gx + 1) * fg.shape[2] / 2
            py = (gy + 1) * fg.shape[1] / 2
            pivot_x, pivot_y = acting["pivot"]
            free_y, fixed_y = acting["seat_blend"]
            weight = ((fixed_y - py) / (fixed_y - free_y)).clamp(0, 1)
            weight = weight * weight * (3 - 2 * weight)
            c, sn = math.cos(angle), math.sin(angle)
            rx = pivot_x + c * (px - pivot_x) + sn * (py - pivot_y)
            ry = pivot_y - sn * (px - pivot_x) + c * (py - pivot_y)
            gfx = (px + (rx - px) * weight) / fg.shape[2] * 2 - 1
            gfy = (py + (ry - py) * weight) / fg.shape[1] * 2 - 1
        # Premultiply before filtering to avoid dark fringes at alpha edges.
        premultiplied = torch.cat((fg[:3] * fg[3:4], fg[3:4]), dim=0)
        f_ = F.grid_sample(premultiplied[None], torch.stack([gfx, gfy], -1)[None], padding_mode="zeros", align_corners=False)[0]
        img = img * (1 - f_[3:4]) + f_[:3]
    # code sun (rise/set/pulse) behind the plate's paper sky
    sun = s.get("sun")
    if sun:
        skym = F.grid_sample(sky[None], grid, padding_mode="border", align_corners=False)[0]
        sx, sy0, sy1, r = sun   # plate-normalized x, y start, y end, radius (fraction of height)
        sy = sy0 + (sy1 - sy0) * ease(u)
        px = (xx - ((sx * 2 - 1) - (cx * 2 - 1)) * z); py = (yy - ((sy * 2 - 1) - (cy * 2 - 1)) * z)
        disk = ((px * W / H) ** 2 + py ** 2).sqrt() < r * 2 * z
        m = (disk.float()[None] * skym)
        img = img * (1 - m) + SUN * m
    if s.get("glow"):   # a breathing warm pulse on lit things (sun / exit / window)
        gx_, gy_, gr = s["glow"]
        px = (xx - ((gx_ * 2 - 1) - (cx * 2 - 1)) * z); py = (yy - ((gy_ * 2 - 1) - (cy * 2 - 1)) * z)
        k = torch.exp(-((px * W / H) ** 2 + py ** 2) / (gr * gr)) * (.06 + .04 * math.sin(t * 1.3))
        img = img + k[None] * torch.tensor([1, .75, .45], device=dev).view(3, 1, 1)
    if s.get("snow"):
        k = snow(t, int(s["t0"] * 10) % 9)
        img = img * (1 - k) + torch.tensor((250, 247, 240), device=dev).view(3, 1, 1) / 255 * k
    if s.get("dust", True) and not s.get("snow"):
        n = 14; rng = np.random.default_rng(int(s["t0"] * 10))
        base = rng.random((n, 4))
        for i in range(n):
            x = ((base[i, 0] + t * (.004 + .006 * base[i, 2])) % 1) * 2 - 1
            y = ((base[i, 1] - t * (.003 + .004 * base[i, 3])) % 1) * 2 - 1
            r = (1.2 + 1.8 * base[i, 2]) / H * 2
            k = torch.exp(-(((xx - x) * W / H) ** 2 + (yy - y) ** 2) / (r * r))
            img = img + .10 * k[None] * (0.6 + .4 * math.sin(t * 2 + i))
    return img

@functools.lru_cache(maxsize=48)
def text_layer(key):
    # cut 2: each caption lives in its own small region (full-frame buffers per word ran the PC out of RAM)
    spec = json.loads(key); size = spec["size"]
    font = ImageFont.truetype(spec.get("font", "C:/Windows/Fonts/georgia.ttf"), size)
    words = [w for w, _ in spec["words"]]
    dr = ImageDraw.Draw(Image.new("L", (8, 8)))
    maxw = spec.get("maxw", 1300); lines, cur = [], []
    for i, w in enumerate(words):
        test = " ".join(words[j] for j in cur + [i])
        if cur and dr.textlength(test, font=font) > maxw: lines.append(cur); cur = [i]
        else: cur.append(i)
    lines.append(cur)
    lh = int(size * 1.22); x0, y0 = spec["pos"]; ytop = y0 - lh * len(lines) / 2
    bb = font.getbbox("Hgjy'"); px, py = int(size * .45), int(size * .3)
    place, rects = [], []
    for li, ln in enumerate(lines):
        s_ = " ".join(words[j] for j in ln); lw = dr.textlength(s_, font=font)
        x = x0 - lw / 2 if spec.get("align", "c") == "c" else x0; y = ytop + li * lh
        for k, j in enumerate(ln):
            ww = dr.textlength(words[j], font=font); sp = dr.textlength(" ", font=font)
            rects.append((j, int(x - (px if k == 0 else sp + 1)), int(y + bb[1] - py), int(x + ww + px), int(y + bb[3] + py)))
            place.append((j, x, y)); x += dr.textlength(words[j] + " ", font=font)
    pad = int(size * .6)
    RX0 = max(0, min(r[1] for r in rects) - pad); RY0 = max(0, min(r[2] for r in rects) - pad)
    RX1 = min(W, max(r[3] for r in rects) + pad); RY1 = min(H, max(r[4] for r in rects) + pad)
    rw, rh = RX1 - RX0, RY1 - RY0; place.sort(); rects.sort()
    ms = []
    for j, x, y in place:
        m = Image.new("L", (rw, rh), 0); ImageDraw.Draw(m).text((x - RX0, y - RY0), words[j], font=font, fill=255); ms.append(np.asarray(m))
    tens = torch.from_numpy(np.stack(ms)).to(dev).float() / 255
    shadow = torch.from_numpy(np.asarray(Image.fromarray(np.max(np.stack(ms), 0)).filter(ImageFilter.GaussianBlur(size / 5))).copy()).to(dev).float() / 255
    strips = torch.zeros((len(rects), rh, rw), device=dev)
    for n, (_, a_, b_, c_, d_) in enumerate(rects): strips[n, max(0, b_ - RY0):max(0, d_ - RY0), max(0, a_ - RX0):max(0, c_ - RX0)] = 1
    return tens, shadow, strips, (RY0, RY1, RX0, RX1)

def draw_texts(img, t):
    for tx in TL["texts"]:
        if not (tx["t0"] - .05 <= t <= tx["t1"] + .35): continue
        key = json.dumps({k: tx[k] for k in ("size", "words", "pos", "maxw", "align", "font") if k in tx}, sort_keys=True)
        tens, shadow, strip, (y0, y1, x0, x1) = text_layer(key)
        reg = img[:, y0:y1, x0:x1]
        out = 1 if t <= tx["t1"] else max(0, 1 - (t - tx["t1"]) / .3)
        al = torch.tensor([min(1, max(0, (t - wt) / .1)) for _, wt in tx["words"]], device=dev).view(-1, 1, 1)
        a = (tens * al).max(0).values * out
        col = tx.get("color", "ink")
        c = torch.tensor(INK if col == "ink" else BONE if col == "bone" else (0xF9, 0x3B, 0x04), device=dev).view(3, 1, 1) / 255
        sh = torch.tensor(BONE if col == "ink" else INK, device=dev).view(3, 1, 1) / 255
        if tx.get("strip", True):
            sal = torch.tensor([min(1, max(0, (t - wt + .06) / .07)) for _, wt in tx["words"]], device=dev).view(-1, 1, 1)
            sm = (strip * sal).max(0).values * out * .94
            reg = reg * (1 - sm) + torch.tensor(BONE, device=dev).view(3, 1, 1) / 255 * sm
            c = torch.tensor(INK, device=dev).view(3, 1, 1) / 255
        elif tx.get("halo", True): reg = reg * (1 - .55 * shadow * out * al.max()) + sh * .55 * shadow * out * al.max()
        reg = reg * (1 - a) + c * a
        img = img.clone(); img[:, y0:y1, x0:x1] = reg
    return img

def render():
    shots = TL["shots"]
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-threads", "4", "-crf", "17", "-pix_fmt", "yuv420p", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(round(T0 * FPS)), int(round(T1 * FPS)); si = 0
    for n in range(n0, n1):
        t = n / FPS
        while si < len(shots) - 1 and t >= shots[si + 1]["t0"]: si += 1
        while si > 0 and t < shots[si]["t0"]: si -= 1
        s = shots[si]
        img = frame_shot(s, t)
        xf = s.get("xfade", 0)
        if xf and si > 0 and t < s["t0"] + xf:
            k = (t - s["t0"]) / xf; img = frame_shot(shots[si - 1], t) * (1 - k) + img * k
        img = img * (1 + TL.get("grain_strength", .07) * GRAIN[(n // 2) % 4]) * vign
        img = draw_texts(img, t)
        fo = TL.get("fade_out", 0)
        if fo and t > TL["dur"] - fo: img = img * max(0, (TL["dur"] - t) / fo)
        if t < .4 and TL.get("fade_in"): img = img * (t / .4)
        p.stdin.write((img.clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous().cpu().numpy().tobytes())
        if n % 300 == 0: print(f"{t:7.1f} s", flush=True)
    finish_encoder(p, OUT); print("done", OUT)

if __name__ == "__main__":
    with torch.no_grad(): render()
