"""Find paintings on Wikimedia Commons: first JPG >= 1000 px wide per line. Input lines: thinker|name|search words.

    python docs/find_paintings.py candidates.txt > found.tsv

Then add "name.jpg https://commons.wikimedia.org/wiki/Special:FilePath/<file>?width=2400" lines to images.txt,
let the fetch-images job download them, check every file opens (Wikimedia rate-limits), eye-check a contact sheet,
and add the keepers to docs/art_sets.json. See docs/SOP-publish.md step 2."""
import json, sys, time, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "MarginNotesBot/1.0 (savilar7@gmail.com)"}


def api(**p):
    p.update(format="json")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=30))


out = []
for line in open(sys.argv[1], encoding="utf8"):
    if not line.strip() or line.startswith("#"):
        continue
    thinker, name, q = line.strip().split("|")
    hits = api(action="query", generator="search", gsrsearch=q, gsrnamespace=6, gsrlimit=8,
               prop="imageinfo", iiprop="size|mime").get("query", {}).get("pages", {})
    best = None
    for pg in sorted(hits.values(), key=lambda x: x.get("index", 99)):
        ii = (pg.get("imageinfo") or [{}])[0]
        t = pg["title"]
        if ii.get("mime") == "image/jpeg" and ii.get("width", 0) >= 1000 and "frame" not in t.lower():
            best = (t[5:], ii["width"], ii["height"]); break
    print(thinker, name, *(best or ("NOT FOUND", 0, 0)), sep="\t", flush=True)
    time.sleep(0.3)
