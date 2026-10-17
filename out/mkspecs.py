import json,os
A=os.path.abspath('audio').replace(os.sep,'/')
W=lambda f:{"file":f+".jpg","wide":[0.5,0.5,1.05],"close":[0.5,0.4,1.7]}
S={
"2026-10-18-w-shadow2":("SHADOW WORK · #2","Follow for #3",["fate","pattern","repeating"],"",["ninth_wave","munch_melancholy"]),
"2026-10-18-w-2am1":("2 AM PHILOSOPHY · #1","Follow for #2",["deeply","flaw","clearly"],"DOSTOEVSKY · CRIME AND PUNISHMENT · TR. GARNETT",["munch_melancholy","rembrandt_philosopher"]),
"2026-10-18-w-stoic3":("STOIC RESET · #3","Follow for #4",["worry","tricks","tonight"],"SENECA · LETTER 13 · TR. GUMMERE (1917)",["friedrich_monk_sea","friedrich_wanderer"]),
"2026-10-18-w-2am2":("2 AM PHILOSOPHY · #2","Follow for #3",["worst","story","chapter"],"NIETZSCHE · TWILIGHT OF THE IDOLS · TR. LUDOVICI",["ninth_wave","starry_night"]),
"2026-10-19-w-stoic4":("STOIC RESET · #4","Follow for #5",["changing","opinion","day."],"MARCUS AURELIUS · MEDITATIONS IV · TR. CASAUBON",["rembrandt_old_man_red","friedrich_woman_sun"]),
"2026-10-19-w-shadow3":("SHADOW WORK · #3","Follow for #4",["mask","persona","underneath"],"",["rembrandt_philosopher","friedrich_abbey"]),
"2026-10-19-w-2am3":("2 AM PHILOSOPHY · #3","Follow for #4",["rock","escape","enough"],"",["titian_sisyphus","friedrich_abbey"]),
"2026-10-19-w-stoic5":("STOIC RESET · #5","Follow for #6",["behind","quietly"],"EPICTETUS · ENCHIRIDION 13 · TR. HIGGINSON",["ribera_philosopher2","death_socrates"]),
"2026-10-19-w-2am4":("2 AM PHILOSOPHY · #4","Follow for #5",["blaming","scale","no"],"EPICTETUS · ENCHIRIDION 5 · TR. HIGGINSON",["starry_night","friedrich_monk_sea"]),
}
for n,(ser,end,kw,cite,ims) in S.items():
    json.dump({"style":"W","audio":f"{A}/{n}","keywords":kw,"cite":cite,"series":ser,"endcard":end,"images":[W(i) for i in ims]},open(f"out/{n}.json","w",encoding="utf-8"),ensure_ascii=False)
print(len(S))
