#!/usr/bin/env python3
"""«Carte da tenere d'occhio» di un nuovo set: python run_cards_watch.py data/watch/hadou-seeker.json"""
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.render import render_png

ROOT = Path(__file__).resolve().parent
w = json.loads(Path(sys.argv[1]).read_text())
A = (ROOT / w["assets"]).resolve()
uri = lambda f: (A / f).as_uri()
w["cover"] = [uri(f) for f in w["cover"]]
for c in w["singles"] + w.get("pair", []):
    c["img"] = uri(c["img"])
out = ROOT / "output" / w["key"]
out.mkdir(parents=True, exist_ok=True)
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
(out / "watch.html").write_text(env.get_template("cards_watch.html.j2").render(w=w), encoding="utf-8")
slides = render_png(out / "watch.html", out)
caption = "\n".join([
    "🇯🇵 HADOU SEEKER · Le carte che possono cambiare il meta", "",
    "Il nuovo set giapponese esce il 27 novembre. Le carte che interessano a chi gioca i tornei:", "",
    *[f"{i}. {c['name']} – {c['tag']}" for i, c in enumerate(w["singles"], 1)],
    *[f"• {c['name']}" for c in w.get("pair", [])], "",
    "Le vedremo nelle City League giapponesi da fine novembre: ne parliamo nel City League Report del 3 dicembre.", "",
    "Quale carta ti incuriosisce di più? Scrivilo nei commenti 👇", "",
    "Nomi e testi: traduzione non ufficiale, il set non è ancora annunciato in Italia. Fonte: pokemon-card.com",
    "Carte © Pokémon / Nintendo / Creatures / GAME FREAK", "",
    "#pokemontcg #pokemontcgitalia #ptcg #hadouseeker #tcgitalia"])
(out / "caption.txt").write_text(caption, encoding="utf-8")
print(f"{len(slides)} slide in {out}")
