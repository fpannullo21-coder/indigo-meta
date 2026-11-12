#!/usr/bin/env python3
"""News in formato «storia» (immagine a tutto schermo + testo): python run_story.py data/stories/hadou-seeker.json"""
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.render import render_png

ROOT = Path(__file__).resolve().parent
st = json.loads(Path(sys.argv[1]).read_text())
A = (ROOT / st.get("assets", "assets")).resolve()


def ref(x):
    """Un'immagine: file in assets/ (stringa) oppure carta ufficiale {"set": "ASC", "number": "55", "name": ...}."""
    if isinstance(x, dict):
        from run_rubrica import card_images
        return card_images([dict({"section": "pokemon"}, **x)])[0].get("src")
    return (A / x).as_uri()


for s in st["slides"]:
    if s.get("bg"):
        s["bg"] = ref(s["bg"])
    s["cards"] = [u for u in (ref(c) for c in s.get("cards", [])) if u]
out = ROOT / "output" / st["key"]
out.mkdir(parents=True, exist_ok=True)
for old in out.glob("slide_*.png"):
    old.unlink()
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
(out / "story.html").write_text(env.get_template("news_story.html.j2").render(story=st), encoding="utf-8")
slides = render_png(out / "story.html", out)
(out / "caption.txt").write_text(st["caption"], encoding="utf-8")
print(f"{len(slides)} slide in {out}")
