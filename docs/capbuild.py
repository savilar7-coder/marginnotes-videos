import json,sys
sys.path.insert(0,'/home/claude/render')
from align import caption_beats
A='/home/claude/marginnotes-videos/audio/'; I='/home/claude/marginnotes-videos/assets/'
def build(name,img,focus,cover,cit,end,out,dur=None):
    qh=lambda t:"<div class='q'>“"+t+"”</div><div class='cap'>"+cit+"</div>"
    b=caption_beats(A+name+'.json',cover,end,qh)
    a=json.load(open(A+name+'.json')); last=a["character_end_times_seconds"][-1]
    json.dump({"image":I+img,"focus":focus,"zoom":[1.0,1.16],"duration":dur or round(last+3.3,1),"audio":A+name+'.mp3',"black_until":0,"beats":b},open(out,'w'),indent=1)
    return b
if __name__=="__main__":
    CIT="Seneca · Letters to Lucilius 13 · tr. R. M. Gummere (1917)"
    b=build('2026-10-17-seneca-imagination','friedrich_wanderer.jpg',[0.5,0.35],
      "<div class='cover'>It <span class='red'>never</span> happened</div>",CIT,
      "<div class='list'>1. Name the worry.<br>2. Ask: what's my proof?<br>3. No proof → let it wait.</div><div class='cap'>"+CIT+"</div><div class='sub'>Save this for tonight</div>",
      sys.argv[1], float(sys.argv[2]) if len(sys.argv)>2 else None)
    for x in b: print(x['t'], x['html'][:90])
