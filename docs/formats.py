"""Margin Notes video formats A/B/C/D, built from a narration's word timings.

Usage: python3 formats.py spec.json out.mp4
spec = {
  "style": "A" | "B" | "C" | "D",
  "audio": "/abs/marginnotes-videos/audio/<name>",      # without extension (.mp3 + .json)
  "keywords": ["never", "seneca"],                     # words shown in red / slammed (lowercase, no punctuation)
  "cite": "SENECA · LETTER 13 · TR. GUMMERE (1917)",
  "images": [{"file": "friedrich_wanderer.jpg", "wide": [.5,.42,1.05], "close": [.5,.3,2.0]}],   # A, C (D uses the first as backdrop)
  "title": "Seneca lines with the most aura",          # C only
  "page": {"file": "gummere_p99.jpg", "header": [960,170],
           "lines": [[990,1062,1600,1058],[312,1125,1000,1121]],   # underline segments in page px, in reading order
           "note": "↑ the real line, 1917 edition",
           "tag": "LETTERS TO LUCILIUS · XIII · TR. R. M. GUMMERE, 1917"}   # B only
}
Narration rules: voice starts at 0.0; the quoted passage must be in straight double quotes in the script.
Transitions: crossfades and smooth camera moves only (no flash, no shake).
"""
import base64, io, json, pathlib, subprocess, sys
from PIL import Image, ImageOps
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from align import words

ASSETS = pathlib.Path('/home/claude/marginnotes-videos/assets')
F = HERE / 'node_modules/@fontsource'
END = ('.', ',', '?', '!', ':', ';')


def b64font(fam, path, wt, st='normal'):
    return (f"@font-face{{font-family:'{fam}';src:url(data:font/woff2;base64,{base64.b64encode(path.read_bytes()).decode()})"
            f" format('woff2');font-weight:{wt};font-style:{st}}}")


def fonts():
    return "".join([
        b64font('Playfair', F/'playfair-display/files/playfair-display-latin-800-normal.woff2', 800),
        b64font('Playfair', F/'playfair-display/files/playfair-display-latin-400-italic.woff2', 400, 'italic'),
        b64font('Playfair', F/'playfair-display/files/playfair-display-latin-700-italic.woff2', 700, 'italic'),
        b64font('Inter', F/'inter/files/inter-latin-900-normal.woff2', 900),
        b64font('Inter', F/'inter/files/inter-latin-700-normal.woff2', 700),
        b64font('Caveat', F/'caveat/files/caveat-latin-700-normal.woff2', 700)])


def img(name, maxw=2000, gray=False):
    im = Image.open(ASSETS / name).convert('RGB'); im.thumbnail((maxw, 4000))
    if gray: im = ImageOps.grayscale(im).convert('RGB')
    b = io.BytesIO(); im.save(b, 'JPEG', quality=88)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), im.size


def segment(audio, keywords):
    """Split narration into caption chunks (<=4 words, at punctuation) and quote spans."""
    W = [{"w": w, "s": round(s, 3), "e": round(e, 3)} for w, s, e in words(audio + '.json')]
    parts, i = [], 0
    while i < len(W):
        if W[i]["w"].startswith('"'):
            j = i
            while not W[j]["w"].rstrip('.,;:!?').endswith('"') and j + 1 < len(W): j += 1
            parts.append({"kind": "quote", "s": W[i]["s"], "e": W[j]["e"], "words": W[i:j + 1]}); i = j + 1; continue
        j = i
        while j + 1 < len(W) and not W[j]["w"].endswith(END) and not W[j + 1]["w"].startswith('"'): j += 1
        clause = W[i:j + 1]; n = len(clause); k = -(-n // 4); size = -(-n // k)
        for p in range(0, n, size):
            seg = clause[p:p + size]
            parts.append({"kind": "cap", "s": seg[0]["s"], "e": seg[-1]["e"], "text": " ".join(x["w"] for x in seg)})
        i = j + 1
    end = W[-1]["e"]
    return W, parts, end


BASE_CSS = """*{margin:0;padding:0;box-sizing:border-box}html,body{width:1080px;height:1920px;overflow:hidden;background:#000}
.layer{position:absolute;inset:0}
#grain{position:absolute;inset:-20px;opacity:.10;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/></filter><rect width='160' height='160' filter='url(%23n)'/></svg>");mix-blend-mode:overlay}
#vig{background:radial-gradient(ellipse at 50% 45%,rgba(0,0,0,0) 45%,rgba(0,0,0,.6) 100%)}
#label{position:absolute;top:250px;left:90px;font:700 26px Inter;letter-spacing:.3em;color:rgba(245,241,232,.6)}
.k{color:#E8323C}
#cite{position:absolute;left:90px;right:200px;text-align:center;font:700 28px Inter;letter-spacing:.2em;color:#ff4a52;text-shadow:0 2px 10px #000}
"""

BASE_JS = r"""
function cl(x){return x<0?0:x>1?1:x}
function eo(x){x=cl(x);return 1-Math.pow(1-x,3)}
function eio(x){x=cl(x);return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2}
const dust=[];for(let i=0;i<60;i++)dust.push({x:(i*137)%1080,y:(i*263)%1920,r:1+(i%3),v:8+(i*7)%25,a:.15+((i*13)%40)/100,p:i});
function drawDust(t){const c=document.getElementById('dust');if(!c)return;const g=c.getContext('2d');g.clearRect(0,0,1080,1920);
 for(const d of dust){const y=((d.y-d.v*t*6)%1920+1920)%1920,x=d.x+Math.sin(t*.8+d.p)*18;g.fillStyle='rgba(255,240,215,'+d.a*(0.6+0.4*Math.sin(t*2+d.p))+')';g.beginPath();g.arc(x,y,d.r,0,7);g.fill()}}
function grain(t){const g=document.getElementById('grain');if(g)g.style.transform='translate('+((t*997)%20-10)+'px,'+((t*631)%20-10)+'px)'}
function kw(text){return text.split(' ').map(w=>KEY.includes(w.replace(/[".,:;!?]/g,'').toLowerCase())?'<span class=k>'+w+'</span>':w).join(' ')}
function cur(t){let c=null;for(const p of P)if(p.s<=t+0.02)c=p;return c}
function karaoke(q,t){return q.words.map(w=>'<span style="opacity:'+(t>=w.s?1:.28)+'">'+w.w.replace(/"/g,'')+'</span>').join(' ')}
// shots: cover-fit image, [cx,cy,zoom] eased a->b, crossfade XF seconds into next shot, gentle push-in at shot start
const XF=.35;
function place(el,iw,ih,v,extra){const c=Math.max(1080/iw,1920/ih)*v[2]*(1+extra);const w=iw*c,h=ih*c;
 let x=540-v[0]*w,y=820-v[1]*h;x=Math.min(0,Math.max(1080-w,x));y=Math.min(0,Math.max(1920-h,y));
 el.style.width=iw+'px';el.style.transform='translate('+x+'px,'+y+'px) scale('+c+')'}
function shotAt(s,t,el){const p=eio((t-s.t0)/(s.t1-s.t0));const v=[0,1,2].map(i=>s.a[i]+(s.b[i]-s.a[i])*p);
 const push=.05*(1-eo((t-s.t0)/.7));place(el,s.iw,s.ih,v,push)}
function runShots(t,S){let k=0;for(let i=0;i<S.length;i++)if(t>=S[i].t0)k=i;
 const A=document.getElementById('shA'),B=document.getElementById('shB');
 const s=S[k];A.src=IM[s.img];shotAt(s,t,A);A.style.opacity=1;
 const n=S[k+1];if(n&&t>n.t0-XF){B.src=IM[n.img];shotAt(n,Math.max(t,n.t0-XF),B);B.style.opacity=eio((t-(n.t0-XF))/XF)}else B.style.opacity=0}
"""


def build(spec, out):
    style = spec["style"]; KEY = [k.lower() for k in spec.get("keywords", [])]
    W, P, end = segment(spec["audio"], KEY)
    D = round(end + 1.3, 2)
    quotes = [p for p in P if p["kind"] == "quote"]
    css, body, js, sfx = "", "", "", []
    ims = {}

    def shots_from(images, gray=False, closeups=True):
        # one shot per caption group; a cut at most every ~1.6 s, quote gets its own slow shot
        nonlocal ims
        for n, im in enumerate(images):
            src, sz = img(im["file"], gray=gray); ims[f"i{n}"] = (src, sz)
        cuts = [0.0]
        for p in P:
            if p["kind"] == "quote" or p["s"] - cuts[-1] >= 1.6:
                if p["s"] - cuts[-1] >= 0.9: cuts.append(p["s"])
        cuts.append(D)
        S = []
        for i in range(len(cuts) - 1):
            im = images[(i // 2) % len(images)] if closeups else images[i % len(images)]
            key = f"i{images.index(im)}"
            v = im["close"] if (closeups and i % 2 == 1) else im["wide"]
            drift = [v[0], v[1] - 0.02, v[2] * 1.08]
            S.append(dict(t0=cuts[i], t1=cuts[i + 1], img=key, iw=ims[key][1][0], ih=ims[key][1][1], a=v, b=drift))
        return S, cuts

    if style in ("A", "C"):
        S, cuts = shots_from(spec["images"], gray=(style == "C"), closeups=(style == "A"))
        sfx += [{"t": max(0, c - 0.25), "kind": "whoosh"} for c in cuts[1:-1]]
        filt = "brightness(1.12) contrast(1.15) saturate(1.08)" if style == "A" else "contrast(1.45) brightness(.92)"
        css += f".shot{{position:absolute;left:0;top:0;transform-origin:0 0;filter:{filt}}}"
        body += "<div class=layer><img class=shot id=shA><img class=shot id=shB></div>"
        if style == "A":
            css += """#shade{background:linear-gradient(180deg,rgba(0,0,0,.25) 0%,rgba(0,0,0,0) 30%,rgba(0,0,0,.2) 48%,rgba(0,0,0,.6) 74%,rgba(0,0,0,.3) 100%)}
#cap{position:absolute;left:90px;right:200px;top:1060px;text-align:center;font:900 104px/1.02 Inter;color:#fff;text-transform:uppercase;letter-spacing:-.01em;-webkit-text-stroke:14px #000;paint-order:stroke fill;text-shadow:0 8px 30px rgba(0,0,0,.6)}
#q{position:absolute;left:90px;right:200px;top:900px;text-align:center;font:italic 700 74px/1.18 Playfair;color:#fff;text-shadow:0 4px 24px #000,0 0 8px #000}
#cite{top:1360px}"""
            body += "<div class=layer id=shade></div><canvas id=dust width=1080 height=1920 class=layer></canvas>"
        else:
            css += """#title{position:absolute;left:90px;right:200px;top:430px;text-align:center;font:italic 400 58px/1.2 Playfair;color:#fff;text-shadow:0 3px 18px #000}
#cap,#q{position:absolute;left:90px;right:200px;top:1120px;text-align:center;font:italic 400 66px/1.25 Playfair;color:#fff;text-shadow:0 4px 22px #000,0 0 6px #000}
#cite{top:1470px;color:#ddd}#q .n{color:#E8323C;font-weight:800;font-style:normal}"""
            body += f"<div id=title>{spec.get('title','')}</div>"
        js += f"const S={json.dumps(S)};"
    if style == "D":
        src, sz = img(spec["images"][0]["file"], gray=True); ims["i0"] = (src, sz)
        css += """#bg{background:radial-gradient(ellipse at 50% 45%,#2a0b0d 0%,#0b0506 70%)}
#ghost{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;opacity:0;filter:contrast(1.3)}
#word{position:absolute;left:60px;right:160px;top:760px;height:400px;display:flex;align-items:center;justify-content:center;text-align:center;font:900 200px/0.95 Inter;color:#F5F1E8;text-transform:uppercase;letter-spacing:-.03em}
#word.k{color:#E8323C}
#q{position:absolute;left:90px;right:200px;top:820px;text-align:center;font:italic 700 84px/1.15 Playfair;color:#fff;text-shadow:0 4px 24px #000}
#cite{top:1420px}#bar{position:absolute;left:90px;top:1220px;height:10px;background:#E8323C}"""
        body += "<div class=layer id=bg></div><img id=ghost><div id=word></div><div id=bar></div>"
        sfx += [{"t": w["s"], "kind": "thud"} for w in W if w["w"].strip('".,:;!?').lower() in KEY]
        qspans = [(q["s"] - .01, q["e"] + .01) for q in quotes]
        free = [w for w in W if not any(a <= w["s"] <= b for a, b in qspans)]
        DB, cur_ = [], None
        for i, w in enumerate(free):
            raw = w["w"].strip('".,:;!?'); k = raw.lower() in KEY
            nxt = free[i + 1]["s"] if i + 1 < len(free) else w["e"]
            if cur_ and not k and not cur_["k"] and (w["s"] - cur_["s"] < 0.32) and len(cur_["text"].split()) < 2:
                cur_["text"] += " " + raw
            else:
                cur_ = {"text": raw, "s": w["s"] if DB else 0.0, "k": k}; DB.append(cur_)
            if w["w"].endswith(END) and not k: cur_ = {"text": "", "s": 99, "k": True}  # force break after punctuation
        DB = [b for b in DB if b["text"]]
        js += f"const DB={json.dumps(DB)};"
    if style == "B":
        pgd = spec["page"]; src, sz = img(pgd["file"], 1920); ims["page"] = (src, sz)
        pw, ph = sz
        segs = pgd["lines"]
        paths = "".join(f'<path class=u d="M{a} {b} C {a+(c-a)*.3:.0f} {b-5}, {a+(c-a)*.7:.0f} {d+6}, {c} {d}" stroke="#C8141E" stroke-width="9" fill="none" stroke-linecap="round"/>' for a, b, c, d in segs)
        xs = [v for s in segs for v in (s[0], s[2])]; ys = [v for s in segs for v in (s[1], s[3])]
        lcx, lcy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        span = max(xs) - min(xs); sc = min(0.85, 960 / max(span, 1))
        hx, hy = pgd.get("header", [pw / 2, 170])
        q0 = quotes[0] if quotes else {"s": end * .5, "e": end}
        pre = q0["s"]
        # camera keys [t, cx, cy, scale, rot]: hook on dimmed page near the lines, then header, then glide to the lines
        K = [[0, lcx, lcy + 120, .95, -3], [0.6, lcx, lcy + 60, .82, -1.2],
             [max(0.7, pre * 0.5), lcx, lcy, .86, -1], [max(0.8, pre * 0.5 + 0.7), hx, hy + 60, .95, 0],
             [max(0.9, pre - 0.4), hx, hy + 160, .88, 0], [pre + 0.5, lcx, lcy + (900 - 650) / sc, sc, 0],
             [q0["e"] + 0.2, lcx, lcy + (900 - 650) / (sc * 1.04), sc * 1.04, 0], [D, lcx, lcy + (900 - 650) / sc, sc, 0]]
        css += """#desk{background:radial-gradient(ellipse at 50% 40%,#3a2c20,#120c08 75%)}
#cam{position:absolute;left:0;top:0;transform-origin:0 0}
#paper{position:absolute;left:0;top:0;filter:sepia(.35) brightness(1.04) contrast(1.08);box-shadow:0 40px 120px rgba(0,0,0,.7)}
#ink{position:absolute;left:0;top:0;overflow:visible}
#dim{background:rgba(10,6,3,.62)}
#cap{position:absolute;left:90px;right:200px;top:1100px;text-align:center;font:800 112px/1.0 Playfair;color:#fff;text-transform:uppercase;text-shadow:0 6px 30px #000,0 0 8px #000}
#q{position:absolute;left:90px;right:200px;top:1450px;text-align:center;font:italic 700 60px/1.2 Playfair;color:#fff;background:rgba(12,8,5,.78);border-radius:18px;padding:22px 26px;opacity:0}
#tag{position:absolute;left:90px;right:200px;top:560px;text-align:center;font:700 28px Inter;letter-spacing:.2em;color:#E8323C;text-shadow:0 2px 10px rgba(0,0,0,.5)}
#note{position:absolute;left:470px;top:790px;padding:6px 22px;background:#f3ead6;font:700 54px Caveat;color:#C8141E;transform:rotate(-4deg);box-shadow:0 6px 20px rgba(0,0,0,.35);opacity:0}"""
        body += (f"<div class=layer id=desk></div><div id=cam><img id=paper style='width:{pw}px;height:{ph}px'>"
                 f"<svg id=ink width={pw} height={ph} viewBox='0 0 {pw} {ph}'>{paths}</svg></div><div class=layer id=dim></div>"
                 f"<div id=tag></div><div id=note>{pgd.get('note','')}</div>")
        seglen = [((c - a) ** 2 + (d - b) ** 2) ** .5 for a, b, c, d in segs]
        js += f"const K={json.dumps(K)};const SEG={json.dumps(seglen)};const TAG={json.dumps(pgd.get('tag',''))};"
        sfx += [{"t": 0.0, "kind": "page"}, {"t": max(0.8, pre * 0.5 + 0.7) - 0.3, "kind": "page"}]
        # pen sound while each segment is drawn
        tot = sum(seglen); t0 = q0["s"]
        for L in seglen:
            sfx.append({"t": round(t0, 2), "kind": "pen"}); t0 += (q0["e"] - q0["s"]) * L / tot

    body += ("<div id=grain></div><div class=layer id=vig></div><div id=label>MARGIN NOTES</div>"
             "<div id=cap></div><div id=q></div><div id=cite></div>")
    imjs = "const IM=" + json.dumps({k: v[0] for k, v in ims.items()}) + ";"
    js = imjs + f"const WD={json.dumps(W)};const KEY={json.dumps(KEY)};const P={json.dumps(P)};const CITE={json.dumps(spec.get('cite',''))};" + js

    render = {
        "A": r"""window.render=function(t){runShots(t,S);drawDust(t);grain(t);const p=cur(t);const cap=document.getElementById('cap'),q=document.getElementById('q'),ci=document.getElementById('cite');
 if(p&&p.kind=='cap'){cap.innerHTML=kw(p.text);const a=eo((t-p.s)/.16);cap.style.opacity=a;cap.style.transform='scale('+(0.88+0.12*a)+')';q.innerHTML='';ci.innerHTML=''}
 else if(p&&p.kind=='quote'){cap.innerHTML='';q.innerHTML=karaoke(p,t);ci.innerHTML=CITE;ci.style.opacity=eo((t-p.s-.2)/.4)}};""",
        "C": r"""window.render=function(t){runShots(t,S);grain(t);const p=cur(t);const cap=document.getElementById('cap'),q=document.getElementById('q'),ci=document.getElementById('cite');
 if(p&&p.kind=='cap'){const grp=P.filter(x=>x.kind=='cap'&&Math.abs(x.s-p.s)<3&&x.s<=p.s+2.5&&x.s>=p.s-2.5);
  cap.innerHTML=grp.map(x=>'<span style="opacity:'+(t>=x.s?1:.25)+'">'+x.text+'</span>').join(' ');q.innerHTML='';ci.innerHTML=''}
 else if(p&&p.kind=='quote'){const n=P.filter(x=>x.kind=='quote').indexOf(p)+1;cap.innerHTML='';q.innerHTML='<span class=n>'+n+'.</span> '+karaoke(p,t);ci.innerHTML=CITE}};""",
        "D": r"""document.getElementById('ghost').src=IM.i0;
window.render=function(t){grain(t);const p=cur(t);const w=document.getElementById('word'),q=document.getElementById('q'),ci=document.getElementById('cite'),g=document.getElementById('ghost'),bar=document.getElementById('bar');
 const Q=P.find(x=>x.kind=='quote');const qs=Q?Q.s:99;
 if(!p||p.kind=='cap'){q.innerHTML='';ci.innerHTML='';let cw=DB[0];for(const x of DB)if(x.s<=t+0.02&&x.s<qs)cw=x;const raw=cw.text;const k=cw.k;
  w.className=k?'k':'';w.textContent=raw;w.style.fontSize=Math.min(k?250:205,840/(Math.max(raw.length,3)*0.6))+'px';
  const d=t-cw.s;const e=eo(d/.16);w.style.transform='scale('+((k?1.3:1.12)-(k?.3:.12)*e)+') rotate('+(k?-3:0)+'deg)';w.style.opacity=cw.s==0?1:Math.min(1,.35+d/.06);
  bar.style.width=(780*cl(t/qs))+'px';g.style.opacity=Math.max(0,parseFloat(g.style.opacity||0)-.05)}
 else{w.textContent='';bar.style.width='0px';q.innerHTML=karaoke(p,t);ci.innerHTML=CITE;g.style.opacity=.22*cl((t-p.s)/.6);g.style.transform='scale('+(1.05+0.03*(t-p.s))+')'}};""",
        "B": r"""document.getElementById('paper').src=IM.page;
const U=[...document.querySelectorAll('.u')];U.forEach(u=>{const L=u.getTotalLength();u.style.strokeDasharray=L;u.style.strokeDashoffset=L;u.dataset.L=L});
const Q=P.find(x=>x.kind=='quote');const TOT=SEG.reduce((a,b)=>a+b,0);
window.render=function(t){let i=0;while(i<K.length-2&&t>=K[i+1][0])i++;const a=K[i],b=K[i+1];const p=eio((t-a[0])/(b[0]-a[0]));
 const cx=a[1]+(b[1]-a[1])*p,cy=a[2]+(b[2]-a[2])*p,s=a[3]+(b[3]-a[3])*p,r=a[4]+(b[4]-a[4])*p;const intro=1-eo(t/.6);
 document.getElementById('cam').style.transform='translate('+(540-cx*s)+'px,'+(900-cy*s+intro*260)+'px) rotate('+(r-intro*3)+'deg) scale('+s+')';
 grain(t);const P0=cur(t);const cap=document.getElementById('cap'),q=document.getElementById('q'),ci=document.getElementById('cite'),tag=document.getElementById('tag'),dim=document.getElementById('dim');
 const qs=Q?Q.s:99,qe=Q?Q.e:99;dim.style.opacity=t<qs?(.62-.2*cl((t-K[3][0])/.6)):Math.max(0,.42-(t-qs)*1.2);
 tag.innerHTML=t>=K[3][0]-.2&&t<qs+.3?TAG:'';tag.style.opacity=cl((t-K[3][0]+.2)/.4)*(1-cl((t-qs)/.3));
 if(P0&&P0.kind=='cap'){cap.innerHTML=kw(P0.text);const e=eo((t-P0.s)/.16);cap.style.opacity=e;cap.style.transform='scale('+(0.9+0.1*e)+')';q.style.opacity=0}
 else if(P0&&P0.kind=='quote'){cap.innerHTML='';q.innerHTML=karaoke(P0,t);q.style.opacity=cl((t-P0.s)/.3)}
 let acc=0;const prog=cl((t-qs)/(qe-qs))*TOT;U.forEach((u,j)=>{const L=+u.dataset.L;u.style.strokeDashoffset=L*(1-cl((prog-acc)/SEG[j]));acc+=SEG[j]});
 document.getElementById('note').style.opacity=cl((t-qe-.1)/.35)};""",
    }[style]
    js += BASE_JS + render
    html = (f"<!doctype html><html><head><meta charset=utf-8><style>{fonts()}{BASE_CSS}{css}</style></head>"
            f"<body>{body}<script>{js}</script></body></html>")
    o = pathlib.Path(out).resolve()
    hp = o.with_suffix('.html'); hp.write_text(html)
    rs = o.with_suffix('.render.json')
    json.dump({"html": str(hp), "duration": D, "audio": spec["audio"] + '.mp3', "voice_delay": 0.0, "sfx": sfx, "bed": True}, open(rs, 'w'))
    subprocess.check_call([sys.executable, str(HERE / 'render2.py'), str(rs), str(o)])


if __name__ == "__main__":
    build(json.loads(pathlib.Path(sys.argv[1]).read_text()), sys.argv[2])
