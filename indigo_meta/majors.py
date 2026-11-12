"""Post «Calendario dei major» dalla lista in data/majors_2027.json."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .render import MESI, render_png

ROOT = Path(__file__).resolve().parent.parent
EUROPE = {"Germania", "Regno Unito", "Portogallo", "Rep. Ceca", "Paesi Bassi", "Italia", "Francia", "Polonia", "Spagna"}
LABEL = {"REG": "REG", "SPE": "SPE", "IC": "IC", "WC": "MONDIALI"}


def span(a: dt.date, b: dt.date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {MESI[a.month - 1][:3]}"
    return f"{a.day} {MESI[a.month - 1][:3]} – {b.day} {MESI[b.month - 1][:3]}"


def build(out: Path, handle: str, today: dt.date | None = None) -> tuple[list[Path], str]:
    today = today or dt.date.today()
    data = json.loads((ROOT / "data" / "majors_2027.json").read_text())
    evs = []
    for e in data["events"]:
        a, b = dt.date.fromisoformat(e["start"]), dt.date.fromisoformat(e["end"])
        if b < today:
            continue
        evs.append({**e, "a": a, "when": span(a, b), "label": LABEL[e["type"]],
                    "cls": ("it " if e["country"] == "Italia" else "") + ("eu" if e["country"] in EUROPE else "")})
    months: dict[str, list] = {}
    for e in evs:
        months.setdefault(f"{MESI[e['a'].month - 1].capitalize()} {e['a'].year}", []).append(e)
    pages, cur, used = [], [], 0
    for m, items in months.items():
        h = 64 + 54 * len(items)
        if cur and used + h > 1100:
            pages.append(cur); cur, used = [], 0
        cur.append((m, items)); used += h
    if cur:
        pages.append(cur)
    pick = lambda pred: next(e for e in evs if pred(e))
    view = dict(pages=pages, n_slides=len(pages) + 1, handle=handle, nxt=evs[0],
                italy=pick(lambda e: e["country"] == "Italia"), euic=pick(lambda e: e["name"].startswith("EUIC")))
    out.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    (out / "majors.html").write_text(env.get_template("majors.html.j2").render(**view), encoding="utf-8")
    slides = render_png(out / "majors.html", out)
    caption = "\n".join(
        ["🗓 CALENDARIO DEI MAJOR · stagione 2027", "",
         "Tutti i grandi tornei del Pokémon TCG fino ai Mondiali di agosto.", "",
         f"⏭ Il prossimo: {view['nxt']['name']} ({view['nxt']['when']})",
         f"🇪🇺 Europa: EUIC Londra ({view['euic']['when']})",
         f"🇮🇹 In Italia: Special Event di Bologna ({view['italy']['when']})", "",
         "Seguiamo risultati e mazzi vincenti di ogni major, qui su Indigo Meta. Salva il post per avere le date sempre a portata 📌", "",
         "Fonte: calendario ufficiale Play! Pokémon · date soggette a variazioni", "",
         "#pokemontcg #pokemontcgitalia #ptcg #regionals #euic #tcgitalia"])
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    return slides, caption
