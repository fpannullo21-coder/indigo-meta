#!/usr/bin/env python3
"""Guida «Come iniziare a giocare a Pokémon TCG» (10 slide, evergreen)."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.render import render_png
from run_rubrica import card_images

ROOT = Path(__file__).resolve().parent
KEY = "guida-come-iniziare"
cards = card_images([
    {"section": "pokemon", "name": "Pikachu ex", "set": "SSP", "number": "57"},
    {"section": "trainer", "name": "Ultra Ball", "set": "MEG", "number": "131"},
    {"section": "energy", "name": "Lightning Energy", "set": "MEE", "number": "12"},
])
pk, tr, en = cards
types = [
    dict(pk, title="Pokémon", text="Combattono per te. I <b>Base</b> vanno in campo subito, le <b>evoluzioni</b> (Fase 1 e Fase 2) si mettono sopra il Pokémon da cui si evolvono."),
    dict(tr, title="Allenatore", text="Ti aiutano: pescare, cercare carte, curare. Ci sono <b>Oggetti</b>, <b>Strumenti</b>, <b>Aiuto</b> e <b>Stadi</b>."),
    dict(en, title="Energia", text="Serve ai Pokémon per attaccare. Ce ne sono di vari tipi: <b>Fuoco</b>, <b>Acqua</b>, <b>Lampo</b>… e alcune speciali."),
]
out = ROOT / "output" / KEY
out.mkdir(parents=True, exist_ok=True)
for old in out.glob("slide_*.png"):
    old.unlink()
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
(out / "guide.html").write_text(env.get_template("guide.html.j2").render(g={"cover": cards, "types": types, "handle": "@indigo.meta"}), encoding="utf-8")
slides = render_png(out / "guide.html", out)
(out / "caption.txt").write_text("""🎴 COME INIZIARE A GIOCARE A POKÉMON TCG · guida per principianti

Hai sempre voluto provare ma non sai da dove partire? In 10 slide ti spieghiamo tutto, in modo semplice:

✅ cosa serve per giocare
✅ i tre tipi di carte
✅ come si prepara il campo
✅ cosa fai nel tuo turno
✅ come si vince
✅ i primi passi per iniziare davvero

📌 Salvalo per la tua prima partita e mandalo all'amico che vuoi far iniziare!

Hai dubbi sulle regole? Scrivili nei commenti, rispondiamo a tutti 👇

Regole semplificate per chi inizia: il regolamento completo è su pokemon.com
Immagini carte © Pokémon / Nintendo / Creatures / GAME FREAK

#pokemontcg #pokemontcgitalia #ptcg #comegiocare #pokemoncards #tcgitalia #gccpokemon""", encoding="utf-8")
print(f"{len(slides)} slide in {out}")
