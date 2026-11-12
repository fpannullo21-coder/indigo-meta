#!/usr/bin/env python3
"""Indigo Meta — League Cup TCG della settimana in Italia, per regione.

Uso:
  python run_cups.py                      # settimana in corso (lun–dom), scarica da pokedata.ovh
  python run_cups.py --csv export.csv     # usa un CSV già scaricato
  python run_cups.py --start 2026-11-09   # settimana che inizia in quella data
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.cups import download_csv, parse, group, paginate, area_of
from indigo_meta.render import render_png, MESI
from indigo_meta.telegram import send_preview

ROOT = Path(__file__).resolve().parent


def dates_it(a: dt.date, b: dt.date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {MESI[b.month - 1]}"
    return f"{a.day} {MESI[a.month - 1]} – {b.day} {MESI[b.month - 1]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--start", help="lunedì della settimana (YYYY-MM-DD)")
    ap.add_argument("--no-telegram", action="store_true")
    a = ap.parse_args()

    today = dt.date.today()
    monday = dt.date.fromisoformat(a.start) if a.start else today - dt.timedelta(days=today.weekday())
    sunday = monday + dt.timedelta(days=6)
    first = max(monday, today) if not a.start else monday   # niente Cup già passate
    text = Path(a.csv).read_text(encoding="utf-8-sig") if a.csv else download_csv()
    cups = parse(text, first, sunday)
    if not cups:
        print("Nessuna League Cup trovata in questa settimana: nessuna slide.")
        return

    groups = group(cups)
    pages = []
    for page in paginate(groups):
        pages.append([(name, items, area_of(name)) for name, items in page])
    week = monday.isocalendar()[1]
    out = ROOT / "output" / f"{monday.year}-W{week:02d}-cup"
    out.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("cups.html.j2").render(
        week=week, dates=dates_it(first, sunday), total=len(cups), groups=groups,
        areas=[(area, [(r, items) for r, items in groups if area_of(r) == area])
               for area in dict.fromkeys(area_of(r) for r, _ in groups)],
        pages=pages, n_slides=len(pages) + 1)
    (out / "cups.html").write_text(html, encoding="utf-8")
    slides = render_png(out / "cups.html", out)

    caption = "\n".join(
        [f"🏆 LEAGUE CUP DELLA SETTIMANA · {dates_it(first, sunday)}", "",
         f"{len(cups)} League Cup del Pokémon TCG in Italia, regione per regione.", ""]
        + [f"📍 {name}: {len(items)}" for name, items in groups]
        + ["", "Orari e iscrizioni: verifica sempre con il negozio. Scorri e trova la tua 👉", "",
           "Dati: Event Locator Play! Pokémon (via pokedata.ovh)", "",
           "#pokemontcg #pokemontcgitalia #leaguecup #ptcg #tcgitalia"])
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"Cup: {len(cups)} in {len(groups)} zone, {len(slides)} slide in {out}")
    if not a.no_telegram:
        send_preview(slides, caption, publish_key=out.name)


if __name__ == "__main__":
    main()
