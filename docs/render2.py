"""Margin Notes renderer v2: any self-contained HTML page that defines window.render(t).

Usage: python3 render2.py spec.json out.mp4
spec = {"html": "/abs/page.html", "duration": 11.0, "audio": "/abs/voice.mp3" | null,
        "voice_delay": 0.0, "sfx": [{"t": 0.0, "kind": "whoosh|thud|pen|page"}], "bed": true}
Voice starts at voice_delay (default 0). SFX are synthesised with ffmpeg (no third-party audio).
"""
import json, subprocess, sys, pathlib, math
from playwright.sync_api import sync_playwright

FPS = 30
W, H = 1080, 1920
# Safe zone (docs/PIPELINE.md, Oct 17 2026): text within 10-85% width, 12-72% height.
SAFE = {"x0": int(W * 0.10), "x1": int(W * 0.85), "y0": int(H * 0.12), "y1": int(H * 0.72)}
AUDIT_JS = """() => {
  const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const vis = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= parseFloat(cs.opacity); } return o; };
  while (w.nextNode()) { const n = w.currentNode; if (!n.textContent.trim()) continue;
    const el = n.parentElement; if (vis(el) < 0.15) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize); const r = document.createRange(); r.selectNodeContents(n);
    for (const q of r.getClientRects()) if (q.width > 0 && q.right > 0 && q.left < innerWidth && q.bottom > 0 && q.top < innerHeight)
      out.push([q.left, q.top, q.right, q.bottom, fs]); }
  return out; }"""

SFX = {
    # short filtered-noise swish
    "whoosh": "anoisesrc=d=0.45:c=pink:a=0.9,highpass=f=500,lowpass=f=6000,afade=t=in:d=0.18,afade=t=out:st=0.2:d=0.25,volume=0.55",
    # low impact for word slams
    "thud": "aevalsrc='sin(2*PI*58*t)*exp(-9*t)+0.4*sin(2*PI*116*t)*exp(-14*t)':d=0.5:s=48000,volume=0.9",
    # pen scratch on paper
    "pen": "anoisesrc=d=0.9:c=white:a=0.5,bandpass=f=3800:w=2500,tremolo=f=18:d=0.6,afade=t=in:d=0.05,afade=t=out:st=0.6:d=0.3,volume=0.35",
    # paper page turn
    "page": "anoisesrc=d=0.5:c=brown:a=0.9,highpass=f=300,lowpass=f=4000,afade=t=in:d=0.04,afade=t=out:st=0.1:d=0.4,volume=0.6",
}


def main(spec_path, out):
    spec = json.loads(pathlib.Path(spec_path).read_text())
    D = float(spec["duration"])
    silent = pathlib.Path(out).with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
                           "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch(channel=__import__("os").environ.get("PW_CHANNEL") or None)  # PW_CHANNEL=msedge on Sergio's PC
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(pathlib.Path(spec["html"]).as_uri()); pg.wait_for_timeout(800)
        problems = []
        for f in range(int(math.ceil(D * FPS))):
            pg.evaluate(f"render({f / FPS})")
            if f % (FPS // 2) == 0:
                rs = pg.evaluate(AUDIT_JS); t = f / FPS
                for x0, y0, x1, y1, fs in rs:
                    if x0 < SAFE["x0"] - 2 or x1 > SAFE["x1"] + 2 or y0 < SAFE["y0"] - 2 or y1 > SAFE["y1"] + 2:
                        problems.append(f"t={t:.1f}s text at x {x0:.0f}-{x1:.0f}, y {y0:.0f}-{y1:.0f} (font {fs:.0f}px) outside the safe zone")
                if f == 0:
                    tops = {round(y0 / 20) for x0, y0, x1, y1, fs in rs if fs >= 70}
                    if len(tops) > 2:
                        problems.append(f"hook on frame 1 has {len(tops)} lines; max 2")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=90))
        b.close()
    ff.stdin.close(); ff.wait()
    sheet = pathlib.Path(out).with_suffix(".sheet.jpg"); tiles = max(1, math.ceil(D / 2))
    subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-vf",
        f"fps=0.5,drawbox=x={SAFE['x0']}:y={SAFE['y0']}:w={SAFE['x1']-SAFE['x0']}:h={SAFE['y1']-SAFE['y0']}:color=lime@0.9:t=6,"
        f"scale=270:-1,tile=6x{math.ceil(tiles / 6)}:padding=6:color=white", "-frames:v", "1", str(sheet)])
    print("contact sheet", sheet)

    inputs = ["-i", str(silent)]
    filt = []
    mix = []
    n = 1
    if spec.get("bed", True):
        bed = (f"aevalsrc='0.5*sin(2*PI*55*t)+0.3*sin(2*PI*82.4*t)+0.2*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.1*t))':d={D}:s=48000,"
               f"lowpass=f=400,volume=0.07,afade=t=in:d=0.5,afade=t=out:st={max(0, D - 1)}:d=1")
        inputs += ["-f", "lavfi", "-i", bed]; mix.append(f"[{n}:a]"); n += 1
    if spec.get("audio"):
        inputs += ["-i", spec["audio"]]
        d = int(spec.get("voice_delay", 0) * 1000)
        filt.append(f"[{n}:a]highpass=f=70,adelay={d}|{d},loudnorm=I=-15:TP=-1.5:LRA=11[v]"); mix.append("[v]"); n += 1
    for i, s in enumerate(spec.get("sfx", [])):
        inputs += ["-f", "lavfi", "-i", SFX[s["kind"]]]
        d = int(s["t"] * 1000)
        filt.append(f"[{n}:a]aformat=channel_layouts=stereo,adelay={d}|{d}[s{i}]"); mix.append(f"[s{i}]"); n += 1
    filt.append("".join(mix) + f"amix=inputs={len(mix)}:duration=longest:normalize=0,atrim=0:{D}[a]")
    subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(filt),
                           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", out])
    print("wrote", out)
    if problems:
        print("SAFE-ZONE CHECK FAILED:"); [print("  ", x) for x in problems[:25]]
        if len(problems) > 25: print(f"   ... and {len(problems) - 25} more")
        sys.exit(2)
    print("safe-zone check passed")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
