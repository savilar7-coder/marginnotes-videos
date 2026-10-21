"""Turn every shot of a rebrand spec into a 3D parallax clip with DepthFlow (free, local GPU).

Run with the DepthFlow venv (work/dfvenv), then render the result with rebrand_render.py as usual:

    dfvenv/Scripts/python docs/motion.py specs/<name>.json        -> specs/<name>-motion.json + motion/<name>/shotNN.mp4
    venv/Scripts/python  docs/rebrand_render.py specs/<name>-motion.json out/<name>-motion.mp4

Each shot keeps the framing chosen in the spec (img + focus + start zoom) and gets a slow push-in plus a sideways
drift; the drift direction alternates shot to shot so cuts feel alive.
"""
import json, math, os, pathlib, sys

import numpy as np
from attrs import define
from PIL import Image
from depthflow.scene import DepthScene
from depthflow.state import DepthState

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rebrand_render import split_long_shots  # noqa: E402

FW, FH = 980, 1260          # rounded-frame size in rebrand_render.py (FX1-FX0, FY1-FY0)
SUPER = 1.5                 # feed DepthFlow a sharper crop than the output
FPS = 30


@define
class Drift(DepthScene):
    direction: float = 1.0
    push: float = 0.08
    hook: bool = False

    def update(self):
        x = min(1.0, max(0.0, self.tau))
        # the hook shot moves fast at once (ease-out) so the first 2 s visibly move; the rest ease in and out
        e = 1.0 - (1.0 - x) ** 2.2 if self.hook else 0.5 - 0.5 * math.cos(math.pi * x)
        self.state.height = 0.32 if self.hook else 0.22
        self.state.steady = 0.25
        self.state.isometric = 0.55
        self.state.zoom = 1.0 - self.push * e
        self.state.offset = (self.direction * (-0.30 + 0.60 * e), 0.0)


def crop(img, focus, zoom):
    """Same framing as rebrand_render.shot_frame at progress 0, at SUPER x the output size."""
    iw, ih = img.size
    w, h = int(FW * SUPER), int(FH * SUPER)
    scale = max(w / iw, h / ih) * zoom
    cw, ch = min(w / scale, iw), min(h / scale, ih)
    cx = min(max(focus[0] * iw, cw / 2), iw - cw / 2)
    cy = min(max(focus[1] * ih, ch / 2), ih - ch / 2)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return img.resize((w, h), Image.LANCZOS, box=box)


def main(spec_path):
    spec_path = pathlib.Path(spec_path)
    spec = json.loads(spec_path.read_text())
    al = json.load(open(spec["align"]))
    dur = max(al["character_end_times_seconds"]) + spec.get("voice_delay", 0.15) + spec.get("tail", 1.6)
    shots = split_long_shots(spec["shots"], dur, spec.get("max_shot", 4.2))
    spec["shots"] = shots
    outdir = pathlib.Path("motion") / spec_path.stem
    outdir.mkdir(parents=True, exist_ok=True)
    scene = Drift(backend="headless")
    scene.ffmpeg.h264(preset="veryfast")
    for i, s in enumerate(shots):
        t_end = shots[i + 1]["t"] if i + 1 < len(shots) else dur
        length = max(0.5, t_end - s["t"]) + 0.2
        src = Image.open(s["img"]).convert("RGB")
        z0 = s.get("zoom", [1.0, 1.12])[0]
        frame = crop(src, s.get("focus", [0.5, 0.5]), z0)
        out = outdir / f"shot{i:02d}.mp4"
        scene.input(image=np.asarray(frame))
        scene.state = DepthState()
        scene.direction = 1.0 if i % 2 == 0 else -1.0
        scene.push = 0.10 if length < 4 else 0.14
        scene.hook = (i == 0)
        if i == 0:
            scene.push = 0.24
        scene.main(output=str(out), width=FW, height=FH, fps=FPS, time=length, ssaa=1.0)
        s["clip"] = str(out).replace(os.sep, "/")
        print(f"shot {i:02d} {length:4.1f}s {s['img']}", flush=True)
    out_spec = spec_path.with_name(spec_path.stem + "-motion.json")
    out_spec.write_text(json.dumps(spec, indent=1))
    print("wrote", out_spec)


if __name__ == "__main__":
    main(sys.argv[1])
