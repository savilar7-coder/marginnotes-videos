import json,os
A=os.path.abspath('audio').replace(os.sep,'/')
FIX={"munch_melancholy":{"wide":[0.72,0.45,1.0],"close":[0.8,0.38,1.6]},"ninth_wave":{"wide":[0.5,0.72,1.0],"close":[0.3,0.78,1.6]}}
def W(f): return {"file":f+".jpg",**FIX.get(f,{"wide":[0.5,0.5,1.05],"close":[0.5,0.4,1.7]})}
S={
"2026-10-19-w-2am5":("2 AM PHILOSOPHY · #5","Follow for #6",["positive","love","week."],"NIETZSCHE · THE JOYFUL WISDOM 276 · TR. COMMON",["friedrich_woman_sun","friedrich_abbey"]),
"2026-10-19-w-shadow4":("SHADOW WORK · #4","Follow for #5",["alone.","loneliness","hears"],"",["munch_melancholy","friedrich_monk_sea"]),
"2026-10-19-w-2am6":("2 AM PHILOSOPHY · #6","Follow for #7",["off?","awake.","anyway."],"DOSTOEVSKY · NOTES FROM UNDERGROUND · TR. GARNETT",["rembrandt_philosopher","starry_night"]),
"2026-10-20-w-stoic6":("STOIC RESET · #6","Follow for #7",["carry.","pile.","rest."],"EPICTETUS · ENCHIRIDION 1 · TR. HIGGINSON",["ribera_philosopher","friedrich_wanderer"]),
"2026-10-20-w-shadow5":("SHADOW WORK · #5","Follow for #6",["dream","random.","letters"],"",["starry_night","caravaggio_narcissus"]),
"2026-10-20-w-stoic7":("STOIC RESET · #7","Follow for #8",["fighting","move."],"EPICTETUS · ENCHIRIDION 8 · TR. HIGGINSON",["death_socrates","rembrandt_old_man_red"]),
"2026-10-20-w-2am7":("2 AM PHILOSOPHY · #7","Follow for #8",["chaos","material."],"NIETZSCHE · THUS SPAKE ZARATHUSTRA · TR. COMMON",["starry_night","ninth_wave"]),
"2026-10-20-w-stoic8":("STOIC RESET · #8","Follow for #9",["notice","size.","sleep."],"SENECA · LETTER 13 · TR. GUMMERE (1917)",["friedrich_monk_sea","friedrich_wanderer"]),
}
for n,(ser,end,kw,cite,ims) in S.items():
    json.dump({"style":"W","audio":f"{A}/{n}","keywords":kw,"cite":cite,"series":ser,"endcard":end,"images":[W(i) for i in ims]},open(f"out/{n}.json","w",encoding="utf-8"),ensure_ascii=False)
print(" ".join(S))
