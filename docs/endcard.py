"""Silent end card for Shorts whose essay pull is not spoken (Sergio, Nov 10 2026).

    python docs/endcard.py out/<name>.mp4 [seconds=1.5] ["FULL ESSAY"]   -> rewrites the file in place

The last <seconds> of the video (render with spec "tail" >= seconds + 0.4) get blurred and darkened, with the card text and a
down arrow on top: on YouTube Shorts the Related video link sits at the bottom of the player, above the channel name.
Music keeps playing; nothing is voiced.
"""
import os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rebrand_render import FONT, RED

def main(path, secs=1.5, text="FULL ESSAY"):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout)
    t0 = dur - secs
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 150); small = ImageFont.truetype(FONT, 58)
    lines = text.split(" ", 1) if len(text) > 8 else [text]
    y = 760
    for i, ln in enumerate(lines):
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=(255, 255, 255, 255) if i == 0 else RED + (255,), stroke_width=7, stroke_fill=(10, 8, 8, 255)); y += 165
    s = "LINKED ON THIS SHORT"; w = d.textlength(s, font=small)
    d.text(((W - w) / 2, y + 20), s, font=small, fill=(235, 230, 222, 255), stroke_width=4, stroke_fill=(10, 8, 8, 255))
    ax, ay = W // 2, y + 150                      # down arrow
    d.rectangle((ax - 14, ay, ax + 14, ay + 90), fill=(255, 255, 255, 255))
    d.polygon([(ax - 60, ay + 80), (ax + 60, ay + 80), (ax, ay + 160)], fill=(255, 255, 255, 255))
    card = path + ".card.png"; img.save(card)
    tmp = path + ".tmp.mp4"
    fc = (f"[0:v]split[a][b];[b]boxblur=24:3,eq=brightness=-0.22[bb];"
          f"[a][bb]overlay=enable='gte(t,{t0:.3f})'[v1];[1:v]format=rgba,fade=t=in:st={t0:.3f}:d=0.25:alpha=1[c];"
          f"[v1][c]overlay=enable='gte(t,{t0:.3f})'[v]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-loop", "1", "-t", f"{dur:.3f}", "-i", card, "-filter_complex", fc,
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "21", "-maxrate", "6M", "-bufsize", "12M", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", "-shortest", tmp], check=True)
    os.replace(tmp, path); os.remove(card)
    print("end card on", path, f"from {t0:.2f} s")

if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.5, sys.argv[3] if len(sys.argv) > 3 else "FULL ESSAY")
