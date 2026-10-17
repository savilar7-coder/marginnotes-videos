import json,sys
def times(align_path, anchors):
    a=json.load(open(align_path)); chars=a["characters"]; st=a["character_start_times_seconds"]
    text="".join(chars); out=[]; pos=0
    for an in anchors:
        i=text.find(an,pos)
        if i<0: raise SystemExit("anchor not found: "+an)
        out.append(round(st[i],2)); pos=i+len(an)
    return out, a["character_end_times_seconds"][-1]
if __name__=="__main__":
    print(times(sys.argv[1], sys.argv[2:]))

def words(align_path):
    """[(word, start, end)] from ElevenLabs character alignment."""
    a=json.load(open(align_path)); ch=a["characters"]; st=a["character_start_times_seconds"]; en=a["character_end_times_seconds"]
    out=[]; cur=""; s0=None; e0=None
    for c,s,e in zip(ch,st,en):
        if c.isspace():
            if cur: out.append((cur,s0,e0)); cur=""
            continue
        if not cur: s0=s
        cur+=c; e0=e
    if cur: out.append((cur,s0,e0))
    return out

def caption_beats(align_path, cover_html, end_html, quote_html, delay=0.3, maxw=5):
    """Every spoken word on screen, in sync.
    First sentence -> cover_html + the sentence itself; quotes -> quote_html(text) shown whole while spoken;
    last sentence -> end_html; everything else -> chunks of <=maxw words split at punctuation."""
    import html as H
    W=words(align_path); beats=[]; i=0
    # first sentence
    j=0
    while j<len(W) and not W[j][0].endswith(('.','?','!')): j+=1
    first=" ".join(w for w,_,_ in W[:j+1])
    beats.append({"t":0.0,"html":cover_html+"<div class='sub'>"+H.escape(first)+"</div>"})
    # last sentence start
    k=len(W)-1
    while k>0 and not W[k-1][0].endswith(('.','?','!')): k-=1
    i=j+1
    while i<k:
        w,s,e=W[i]
        if w.startswith('"') or w.startswith('“'):
            q=[w]; m=i
            while not (q[-1].rstrip('.,;:!?').endswith('"') or q[-1].endswith('”') or q[-1].endswith('"')) and m+1<k:
                m+=1; q.append(W[m][0])
            txt=" ".join(q).strip('"“”')
            beats.append({"t":round(s+delay,2),"html":quote_html(txt)}); i=m+1; continue
        # clause = words up to punctuation (ignoring abbreviations like a.m.), then split evenly
        END=('.',',','?','!',':',';'); ABBR={'a.m.','p.m.','e.g.','i.e.','Mr.','Dr.'}
        m=i
        while m+1<k and not (W[m][0].endswith(END) and W[m][0] not in ABBR) and not W[m+1][0].startswith('"'):
            m+=1
        clause=W[i:m+1]; n=len(clause); parts=-(-n//maxw); size=-(-n//parts)
        for p0 in range(0,n,size):
            seg=clause[p0:p0+size]
            if beats and p0==0 and n<=2 and beats[-1]["html"].startswith("<div class='cc'>") and len(beats[-1]["html"].split())<=5:
                pass
            beats.append({"t":round(seg[0][1]+delay,2),"html":"<div class='cc'>"+H.escape(" ".join(x for x,_,_ in seg))+"</div>"})
        i=m+1
    beats.append({"t":round(W[k][1]+delay,2),"html":end_html})
    return beats
