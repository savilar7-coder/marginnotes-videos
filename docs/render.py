"""Margin Notes video renderer.

Usage: python3 render.py spec.json out.mp4

spec = {
  "image": "/path/painting.jpg",       # public-domain painting
  "focus": [0.5, 0.35],                # point to zoom toward (fraction of image w/h)
  "zoom": [1.0, 1.15],                 # Ken Burns start/end scale
  "duration": 40.0,                    # seconds (ignored if audio is longer)
  "audio": "/path/voice.wav" or null,  # narration
  "black_until": 3.5,                  # seconds of black opening (0 = painting from start)
  "beats": [ {"t": 0.0, "html": "<div class='big'>...</div>"}, ... ]
}
Text classes: big, mid, q (italic quote), cap (small red caps), red, white, sub.
"""
import json, subprocess, sys, base64, pathlib, math
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
FONTS = HERE / "node_modules" / "@fontsource"
FPS = 30
W, H = 1080, 1920


def font_face(family, path, weight, style="normal"):
    data = base64.b64encode(pathlib.Path(path).read_bytes()).decode()
    return (f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2');"
            f"font-weight:{weight};font-style:{style};}}")


def build_html(spec):
    pf = FONTS / "playfair-display" / "files"
    it = FONTS / "inter" / "files"
    css_fonts = "".join([
        font_face("Playfair", pf / "playfair-display-latin-800-normal.woff2", 800),
        font_face("Playfair", pf / "playfair-display-latin-700-normal.woff2", 700),
        font_face("Playfair", pf / "playfair-display-latin-400-italic.woff2", 400, "italic"),
        font_face("Playfair", pf / "playfair-display-latin-700-italic.woff2", 700, "italic"),
        font_face("Inter", it / "inter-latin-700-normal.woff2", 700),
        font_face("Inter", it / "inter-latin-500-normal.woff2", 500),
    ])
    img = base64.b64encode(pathlib.Path(spec["_img_small"]).read_bytes()).decode()
    beats = json.dumps(spec["beats"])
    return f"""<!doctype html><html><head><meta charset=utf-8><style>{css_fonts}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;background:#000;overflow:hidden;color:#F5F1E8}}
#bgwrap{{position:absolute;inset:0;overflow:hidden}}
#bg{{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}}
#shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,.35) 35%,rgba(0,0,0,.6) 55%,rgba(0,0,0,.88) 100%)}}
#black{{position:absolute;inset:0;background:#000}}
#grain{{position:absolute;inset:-50%;opacity:.07;background-image:radial-gradient(#fff 1px,transparent 1px);background-size:3px 3px}}
#label{{position:absolute;top:250px;left:90px;font:700 26px Inter;letter-spacing:.3em;color:rgba(245,241,232,.55)}}
#text{{position:absolute;left:90px;right:200px;top:720px;height:720px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;text-shadow:0 4px 30px rgba(0,0,0,.95),0 2px 6px rgba(0,0,0,.9)}}
.big{{font:800 118px/1.02 Playfair;text-transform:uppercase;letter-spacing:-.01em}}
.mid{{font:700 82px/1.12 Playfair}}
.cc{{font:700 78px/1.14 Playfair}}
.cc .now{{color:#fff}}
.cover{{font:800 150px/0.98 Playfair;text-transform:uppercase;letter-spacing:-.01em}}
.q{{font:italic 400 72px/1.2 Playfair}}
.sub{{font:500 40px/1.35 Inter;color:rgba(245,241,232,.85);margin-top:28px}}
.cap{{font:700 30px Inter;letter-spacing:.22em;text-transform:uppercase;color:#E8323C;margin:26px 0;text-shadow:0 2px 12px #000,0 0 4px #000}}
.red{{color:#D3202A}}
.list{{font:700 66px/1.35 Playfair}}
.stamp{{display:inline-block;margin-top:40px;font:800 64px Inter;color:#D3202A;border:8px solid #D3202A;padding:10px 30px;transform:rotate(-7deg);letter-spacing:.04em}}
.ul{{border-bottom:8px solid #D3202A;padding-bottom:8px}}
</style></head><body>
<div id=bgwrap><img id=bg src="data:image/jpeg;base64,{img}"></div>
<div id=shade></div><div id=black></div><div id=grain></div>
<div id=label>MARGIN NOTES</div><div id=text></div>
<script>
const B={beats}; const IW={spec['_iw']}, IH={spec['_ih']};
const Z0={spec['zoom'][0]}, Z1={spec['zoom'][1]}, FX={spec['focus'][0]}, FY={spec['focus'][1]};
const D={spec['duration']}, BU={spec.get('black_until',0)};
const bg=document.getElementById('bg'), tx=document.getElementById('text'), bl=document.getElementById('black'), gr=document.getElementById('grain');
let cur=-1;
function ease(x){{return x<0?0:x>1?1:1-Math.pow(1-x,3)}}
window.render=function(t){{
  // Ken Burns: cover-fit then zoom toward focus point
  const cover=Math.max({W}/IW,{H}/IH);
  const p=Math.min(1,Math.max(0,(t-BU)/Math.max(1,D-BU)));
  const z=cover*(Z0+(Z1-Z0)*(p*p*(3-2*p)));
  const w=IW*z,h=IH*z;
  let x={W}/2-FX*w, y={H}*0.30-FY*h;
  x=Math.min(0,Math.max({W}-w,x)); y=Math.min(0,Math.max({H}-h,y));
  bg.style.width=IW+'px'; bg.style.transform=`translate(${{x}}px,${{y}}px) scale(${{z}})`;
  bl.style.opacity = t<BU ? 1 : Math.max(0,1-(t-BU)/0.35);
  gr.style.transform=`translate(${{(t*37)%3}}px,${{(t*53)%3}}px)`;
  let i=-1; for(let k=0;k<B.length;k++) if(B[k].t<=t) i=k;
  if(i!==cur){{ cur=i; tx.innerHTML = i>=0 ? B[i].html : ''; }}
  if(i>=0){{ const a=ease((t-B[i].t)/0.22); tx.style.opacity=a; tx.style.transform=`scale(${{1.045-0.045*a}})`; }}
}};
</script></body></html>"""


def main(spec_path, out):
    spec = json.loads(pathlib.Path(spec_path).read_text())
    from PIL import Image
    im = Image.open(spec["image"]).convert("RGB")
    im.thumbnail((2400, 3200))
    small = pathlib.Path(out).with_suffix(".bg.jpg")
    im.save(small, quality=90)
    spec["_img_small"], spec["_iw"], spec["_ih"] = str(small), im.size[0], im.size[1]
    if spec.get("audio"):
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                             "-of", "csv=p=0", spec["audio"]]).decode().strip())
        spec["duration"] = max(spec.get("duration", 0), dur + 1.2)
    D = spec["duration"]
    html = pathlib.Path(out).with_suffix(".html")
    html.write_text(build_html(spec))
    silent = pathlib.Path(out).with_suffix(".silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
                           "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(html.as_uri()); pg.wait_for_timeout(500)
        n = int(math.ceil(D * FPS))
        for f in range(n):
            pg.evaluate(f"render({f / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
        b.close()
    ff.stdin.close(); ff.wait()
    # Audio: narration + quiet low drone pad
    drone = (f"aevalsrc='0.5*sin(2*PI*55*t)+0.3*sin(2*PI*82.4*t)+0.2*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.1*t))':d={D}:s=48000,"
             "lowpass=f=400,volume=0.06,afade=t=in:d=2,afade=t=out:st=" + str(max(0, D - 2)) + ":d=2")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-f", "lavfi", "-i", drone]
    if spec.get("audio"):
        cmd += ["-i", spec["audio"], "-filter_complex",
                "[2:a]highpass=f=70,adelay=300|300,loudnorm=I=-16:TP=-1.5:LRA=11[v];[1:a][v]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
    subprocess.check_call(cmd)
    print("wrote", out, f"{D:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
