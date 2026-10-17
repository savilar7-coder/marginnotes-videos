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
# TikTok/Reels/Shorts safe zone (Sergio's rules, Oct 17 2026): all text between 10% and 85% of the
# width (action buttons on the right) and between 12% and 72% of the height (caption + username at the bottom).
SAFE = {"x0": int(W * 0.10), "x1": int(W * 0.85), "y0": int(H * 0.12), "y1": int(H * 0.72)}
TEXT_RED = "#FF5C61"   # red for WORDS on dark backgrounds (brand #D3202A is too dark for text on black)


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
#shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.62) 0%,rgba(0,0,0,.58) 12%,rgba(0,0,0,.66) 40%,rgba(0,0,0,.74) 72%,rgba(0,0,0,.9) 100%)}}
#black{{position:absolute;inset:0;background:#000}}
#grain{{position:absolute;inset:-50%;opacity:.07;background-image:radial-gradient(#fff 1px,transparent 1px);background-size:3px 3px}}
#margin{{position:absolute;left:{SAFE['x0']}px;top:{SAFE['y0']}px;height:{SAFE['y1']-SAFE['y0']}px;width:4px;background:#D3202A}}
#label{{position:absolute;top:{SAFE['y0']+6}px;left:{SAFE['x0']+34}px;font:700 26px Inter;letter-spacing:.3em;color:rgba(245,241,232,.55)}}
#fit{{display:flex;flex-direction:column;align-items:center;max-width:100%}}
#text{{position:absolute;left:{SAFE['x0']+34}px;width:{SAFE['x1']-SAFE['x0']-34}px;top:{SAFE['y0']+90}px;height:{SAFE['y1']-SAFE['y0']-90}px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;overflow-wrap:normal;word-break:normal;hyphens:none;text-shadow:0 4px 30px rgba(0,0,0,.95),0 2px 6px rgba(0,0,0,.9)}}
.big{{font:800 118px/1.02 Playfair;text-transform:uppercase;letter-spacing:-.01em}}
.mid{{font:700 82px/1.12 Playfair}}
.cc{{font:700 78px/1.14 Playfair}}
.cc .now{{color:#fff}}
.cover{{font:800 140px/0.98 Playfair;text-transform:uppercase;letter-spacing:-.01em}}
.q{{font:italic 400 72px/1.2 Playfair}}
.sub{{font:500 40px/1.35 Inter;color:rgba(245,241,232,.85);margin-top:28px}}
.cap{{font:700 30px Inter;letter-spacing:.22em;text-transform:uppercase;color:{TEXT_RED};margin:26px 0;text-shadow:0 2px 12px #000,0 0 4px #000}}
.red{{color:{TEXT_RED}}}
.list{{font:700 66px/1.35 Playfair}}
.stamp{{display:inline-block;margin-top:40px;font:800 64px Inter;color:{TEXT_RED};border:8px solid #D3202A;padding:10px 30px;transform:rotate(-7deg);letter-spacing:.04em}}
.ul{{border-bottom:8px solid #D3202A;padding-bottom:8px}}
</style></head><body>
<div id=bgwrap><img id=bg src="data:image/jpeg;base64,{img}"></div>
<div id=shade></div><div id=black></div><div id=grain></div>
<div id=margin></div><div id=label>MARGIN NOTES</div><div id=text><div id=fit></div></div>
<script>
const B={beats}; const IW={spec['_iw']}, IH={spec['_ih']};
const Z0={spec['zoom'][0]}, Z1={spec['zoom'][1]}, FX={spec['focus'][0]}, FY={spec['focus'][1]};
const D={spec['duration']}, BU={spec.get('black_until',0)};
const bg=document.getElementById('bg'), tx=document.getElementById('text'), fit=document.getElementById('fit'), bl=document.getElementById('black'), gr=document.getElementById('grain');
let cur=-1;
function ease(x){{return x<0?0:x>1?1:1-Math.pow(1-x,3)}}
function rects(el){{ const out=[]; const w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
  while(w.nextNode()){{ if(!w.currentNode.textContent.trim()) continue; const r=document.createRange(); r.selectNodeContents(w.currentNode);
    for(const q of r.getClientRects()) if(q.width>0) out.push(q); }} return out; }}
// Safe-zone audit for the current frame: text boxes (unscaled), line count, smallest font size.
window.audit=function(){{ const all=rects(document.body); const tops=new Set(rects(fit).map(q=>Math.round(q.top/20)));
  return {{x0:Math.min(...all.map(q=>q.left)), x1:Math.max(...all.map(q=>q.right)), y0:Math.min(...all.map(q=>q.top)), y1:Math.max(...all.map(q=>q.bottom)), lines:tops.size, zoom:parseFloat(fit.style.zoom)||1, beat:cur}}; }};
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
  if(i!==cur){{ cur=i; fit.style.zoom=1; fit.innerHTML = i>=0 ? B[i].html : '';
    // shrink until every glyph sits inside the safe box (with room for the 1.03 pop-in scale)
    tx.style.transform='none';
    for(let k=0;k<60;k++){{ const b=tx.getBoundingClientRect(), cx=(b.left+b.right)/2, cy=(b.top+b.bottom)/2;
      const rs=rects(fit); if(!rs.length) break;
      const ok=rs.every(q=> cx+(q.left-cx)*1.03>=b.left && cx+(q.right-cx)*1.03<=b.right && cy+(q.top-cy)*1.03>=b.top && cy+(q.bottom-cy)*1.03<=b.bottom);
      if(ok) break; fit.style.zoom=((parseFloat(fit.style.zoom)||1)*0.95).toFixed(3); }} }}
  if(i>=0){{ const a=(i===0&&B[0].t<=0)?1:ease((t-B[i].t)/0.22); tx.style.opacity=a; tx.style.transform=`scale(${{1.03-0.03*a}})`; }}
  else tx.style.opacity=0;
}};
</script></body></html>"""


def check(a, t):
    """Rules from docs/PIPELINE.md: text inside the safe zone, hook max 2 lines, nothing tiny."""
    bad = []
    if a.get("x0") is None or a["x0"] == float("inf"):
        return bad
    tol = 2
    if a["x0"] < SAFE["x0"] - tol or a["x1"] > SAFE["x1"] + tol:
        bad.append(f"beat {a['beat']}: text outside 10-85% width ({a['x0']:.0f}-{a['x1']:.0f}px)")
    if a["y0"] < SAFE["y0"] - tol or a["y1"] > SAFE["y1"] + tol:
        bad.append(f"beat {a['beat']}: text outside 12-72% height ({a['y0']:.0f}-{a['y1']:.0f}px)")
    if a["beat"] == 0 and a["lines"] > 2:
        bad.append(f"hook (beat 0) has {a['lines']} lines; max 2")
    if a["zoom"] < 0.55:
        bad.append(f"beat {a['beat']}: text had to shrink to {a['zoom']:.0%} to fit; cut words")
    return bad


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
        problems = []
        for f in range(n):
            pg.evaluate(f"render({f / FPS})")
            if f % (FPS // 2) == 0:
                problems += check(pg.evaluate("audit()"), f / FPS)
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
        b.close()
    ff.stdin.close(); ff.wait()
    # Contact sheet: 1 frame every 2 s, safe zone drawn in green. Look at it before scheduling.
    sheet = pathlib.Path(out).with_suffix(".sheet.jpg")
    tiles = max(1, math.ceil(D / 2)); cols = 6; rows = math.ceil(tiles / cols)
    subprocess.check_call(["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-vf",
        f"fps=0.5,drawbox=x={SAFE['x0']}:y={SAFE['y0']}:w={SAFE['x1']-SAFE['x0']}:h={SAFE['y1']-SAFE['y0']}:color=lime@0.9:t=6,"
        f"scale=270:-1,tile={cols}x{rows}:padding=6:color=white", "-frames:v", "1", str(sheet)])
    print("contact sheet", sheet)
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
    if problems:
        print("SAFE-ZONE CHECK FAILED:"); [print("  ", x) for x in sorted(set(problems))]
        sys.exit(2)
    print("safe-zone check passed")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
