"""Re-renders of the 5 broken animated videos (Oct 17 2026) in the painting format.
Narration = the original audio (old/<name>.mp3), timings from old/<name>.json.
Usage: python3 docs/reshoot_2026_10_17.py <name> [out_dir]"""
import json, sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from beats import build
R = "/home/claude/marginnotes-videos"
r = lambda s: f"<span class='red'>{s}</span>"

V = {
"camus-universe": dict(file="2026-10-18-camus-universe", image="friedrich_monk_sea.jpg", focus=[0.355, 0.86], zoom=[1.0, 1.12], anchor_y=0.86,
  beats=[
  ("", f"<div class='cover'>NO {r('ANSWER.')}</div>"),
  ("why this job", f"<div class='big'>Why this {r('job?')}</div>"),
  ("why this loss", f"<div class='big'>Why this {r('loss?')}</div>"),
  ("why any", f"<div class='big'>Why any of {r('it?')}</div>"),
  ("and the universe", f"<div class='big'>The universe says {r('nothing.')}</div>"),
  ("albert camus", f"<div class='mid'>Albert Camus called that silence</div><div class='big'>{r('the absurd')}</div><div class='cap'>Camus · The Myth of Sisyphus · 1942</div>"),
  ("we want meaning", f"<div class='mid'>We want meaning.<br>The world {r('doesn’t answer.')}</div>"),
  ("most people", f"<div class='mid'>Most people do one of {r('two things')}</div>"),
  ("they pretend", "<div class='list'>1. Pretend there’s an answer</div>"),
  ("or they give", f"<div class='list'>1. Pretend there’s an answer<br>{r('2. Give up')}</div>"),
  ("camus said", f"<div class='big'>Camus: a {r('third way')}</div>"),
  ("keep living", f"<div class='mid'>Keep living fully, knowing there’s {r('no answer.')}</div>"),
  ("like a man", "<div class='mid'>Like a man pushing a rock up a hill forever…</div>"),
  ("who decides", f"<div class='big'>…who decides the climb is {r('his.')}</div>"),
  ("you don't need", f"<div class='mid'>You don’t need the universe to {r('approve')} of your life.</div>"),
  ("you just need", f"<div class='big'>Just {r('live it.')}</div>"),
  ("what would you", f"<div class='mid'>What would you do tomorrow if you stopped {r('waiting for a sign?')}</div>"),
  ("follow for", f"<div class='mid'>Follow for {r('sourced')} philosophy.</div><div class='cap'>Camus, paraphrased · The Myth of Sisyphus</div>"),
  ]),
"jung-shadow": dict(file="2026-10-19-jung-shadow", image="caravaggio_narcissus.jpg", focus=[0.5, 0.45], zoom=[1.0, 1.12],
  beats=[
  ("", f"<div class='cover'><span style='white-space:nowrap'>WHO ANNOYS</span><br>{r('YOU?')}</div>"),
  ("is showing", f"<div class='mid'>The person who annoys you most is {r('showing you something.')}</div>"),
  ("jung's word", f"<div class='big'>Jung’s word: {r('the shadow')}</div><div class='cap'>C. G. Jung · Aion, ch. 2 · paraphrased</div>"),
  ("traits you hide", f"<div class='mid'>The parts of you that you hide, deny, or were taught were {r('unacceptable.')}</div>"),
  ("they don't disappear", f"<div class='big'>They don’t {r('disappear.')}</div>"),
  ("they go into", f"<div class='big'>They go into {r('the shadow.')}</div>"),
  ("we see it first", f"<div class='mid'>We see it first in {r('other people.')}</div>"),
  ("jung called it", f"<div class='big'>{r('Projection.')}</div>"),
  ("the arrogance", f"<div class='mid'>The arrogance you can’t stand in a coworker…</div>"),
  ("might be", f"<div class='mid'>…might be the {r('confidence')} you never let yourself have.</div>"),
  ("next time", f"<div class='mid'>Next time someone gets to you, ask {r('one question:')}</div>"),
  ("what exactly", f"<div class='mid'>What exactly bothers me — and {r('where do I do a version of it?')}</div>"),
  ("who's your mirror", f"<div class='big'>Who’s your {r('mirror?')}</div>"),
  ("follow for", f"<div class='mid'>Follow for {r('sourced')} philosophy.</div><div class='cap'>Jung, paraphrased · Aion (1951)</div>"),
  ]),
"nietzsche-amorfati": dict(file="2026-10-19-nietzsche-amorfati", image="friedrich_woman_sun.jpg", focus=[0.48, 0.45], zoom=[1.0, 1.1],
  beats=[
  ("", f"<div class='cover'>BAD {r('WEEK?')}</div>"),
  ("was two words", f"<div class='mid'>Nietzsche’s answer was {r('two words.')}</div>"),
  ("amor", f"<div class='big'>{r('Amor fati.')}</div><div class='sub'>Love of fate.</div>"),
  ("new year", f"<div class='big'>New Year, {r('1882.')}</div><div class='cap'>Nietzsche · The Gay Science §276</div>"),
  ("in the gay science", f"<div class='mid'>He wishes himself one thing for the year:</div>"),
  ("to see what", f"<div class='mid'>to see what is necessary in things {r('as beautiful.')}</div><div class='cap'>The Gay Science §276 · paraphrased</div>"),
  ("not everything", f"<div class='mid'>Not “everything happens {r('for a reason.')}”</div>"),
  ("no reason", f"<div class='big'>No reason {r('required.')}</div>"),
  ("this happened", f"<div class='mid'>This happened. It’s {r('mine.')}</div>"),
  ("and i won't", f"<div class='mid'>And I won’t spend my life {r('wishing it hadn’t.')}</div>"),
  ("take the worst", f"<div class='mid'>Take the {r('worst thing')} this week.</div>"),
  ("ask if", f"<div class='mid'>If I had to choose this again, {r('what would I do with it?')}</div>"),
  ("then do that", f"<div class='big'>Then {r('do that.')}</div>"),
  ("could you say", f"<div class='mid'>Could you say {r('amor fati')} about this week?</div>"),
  ("follow for", f"<div class='mid'>Follow for {r('sourced')} philosophy.</div><div class='cap'>Nietzsche · The Gay Science §276 (1882)</div>"),
  ]),
"dostoevsky-firstline": dict(file="2026-10-20-dostoevsky-firstline", image="rembrandt_old_man_red.jpg", focus=[0.5, 0.4], zoom=[1.0, 1.12],
  beats=[
  ("", f"<div class='cover'>I AM A {r('SICK MAN.')}</div>"),
  ("i am a sick", f"<div class='q'>“I am a sick man.... I am a spiteful man. I am an {r('unattractive man.')}”</div><div class='cap'>Notes from Underground · tr. C. Garnett, 1918</div>"),
  ("a man who", f"<div class='mid'>A man who spent forty years {r('in his own head.')}</div>"),
  ("dostoyevsky's narrator", f"<div class='mid'>He’s thought about everything and {r('done almost nothing.')}</div>"),
  ("he calls his mind", f"<div class='big'>He calls his mind a {r('disease.')}</div>"),
  ("overthinking feels", f"<div class='big'>Overthinking feels like {r('depth.')}</div>"),
  ("it's often", f"<div class='big'>It’s often just {r('hiding.')}</div>"),
  ("every plan", f"<div class='mid'>Every plan you analyze instead of starting is another night {r('in the underground.')}</div>"),
  ("pick one thing", f"<div class='mid'>Pick one thing you’ve thought about {r('for weeks.')}</div>"),
  ("do the smallest", f"<div class='mid'>Do the {r('smallest version')} tomorrow — before you can think again.</div>"),
  ("what are you", f"<div class='big'>What are you {r('overthinking?')}</div>"),
  ("follow for", f"<div class='mid'>Follow for {r('sourced')} philosophy.</div><div class='cap'>Dostoevsky · Notes from Underground (1864)</div>"),
  ]),
"marcus-zoomout": dict(file="2026-10-21-marcus-zoomout", image="friedrich_wanderer.jpg", focus=[0.5, 0.35], zoom=[1.35, 1.0],
  beats=[
  ("", f"<div class='cover'>ZOOM {r('OUT.')}</div>"),
  ("your problems", f"<div class='big'>Your problems feel {r('huge.')}</div>"),
  ("the email", "<div class='big'>The email.</div>"),
  ("the bill", "<div class='big'>The bill.</div>"),
  ("what they said", f"<div class='mid'>What they said {r('about you.')}</div>"),
  ("now zoom", f"<div class='big'>Now {r('zoom out.')}</div>"),
  ("out of the room", "<div class='mid'>Out of the room.</div>"),
  ("over the city", "<div class='mid'>Over the city.</div>"),
  ("past the clouds", "<div class='mid'>Past the clouds.</div>"),
  ("until the whole", f"<div class='mid'>Until the whole earth is {r('a blue dot')} spinning in the dark.</div>"),
  ("marcus aurelius", f"<div class='mid'>Marcus Aurelius, Emperor of Rome, did this {r('on purpose.')}</div>"),
  ("in his private", f"<div class='mid'>In his private notes: how {r('small and brief')} everything is.</div><div class='cap'>Meditations IV.3 · VI.36 · paraphrased</div>"),
  ("not to feel", f"<div class='mid'>Not to feel worthless.</div>"),
  ("to feel free", f"<div class='big'>To feel {r('free.')}</div>"),
  ("so tonight", f"<div class='mid'>Tonight, when it gets heavy: {r('zoom out.')}</div>"),
  ("save this", f"<div class='mid'>Save this for a {r('heavy day.')}</div><div class='cap'>Marcus Aurelius · Meditations</div>"),
  ]),
}

def main(name, outdir=f"{R}/v"):
    v = V[name]
    spec = {"image": f"{R}/assets/{v['image']}", "focus": v["focus"], "zoom": v["zoom"], "anchor_y": v.get("anchor_y", 0.30),
            "audio": f"{R}/old/{name}.mp3", "black_until": 0, "duration": 0,
            "beats": build(f"{R}/old/{name}.json", v["beats"])}
    sp = pathlib.Path(outdir) / f"{v['file']}.spec.json"; sp.write_text(json.dumps(spec, indent=1))
    subprocess.check_call([sys.executable, f"{R}/docs/render.py", str(sp), str(pathlib.Path(outdir) / f"{v['file']}.mp4")])

if __name__ == "__main__":
    main(*sys.argv[1:])
