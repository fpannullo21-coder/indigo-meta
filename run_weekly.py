#!/usr/bin/env python3
"""Indigo Meta — report settimanale del meta Pokémon TCG.

Uso:
  python run_weekly.py                 # ultima settimana ISO completa
  python run_weekly.py --week 45 --year 2026
  python run_weekly.py --min-players 64 --handle @indigo.meta

Output in output/<anno>-W<settimana>/: report.json, carousel.html, slide_XX.png, caption.txt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from indigo_meta.limitless import Limitless
from indigo_meta.metrics import build_report, last_completed_week
from indigo_meta.render import build_view, build_deck, render_html, render_png
from indigo_meta.cards import resolve_decklist
from indigo_meta.caption import template_caption, polish_with_claude
from indigo_meta.telegram import send_preview

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--min-players", type=int, default=32)
    ap.add_argument("--handle", default="@indigo.meta")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--no-deck", action="store_true", help="salta la slide con la lista della settimana")
    a = ap.parse_args()

    y, w = last_completed_week()
    year, week = a.year or y, a.week or w
    out = ROOT / "output" / f"{year}-W{week:02d}"
    out.mkdir(parents=True, exist_ok=True)

    api = Limitless(ROOT / "cache")
    report = build_report(api, year, week, min_players=a.min_players)
    (out / "report.json").write_text(json.dumps(report.to_dict(), indent=1, ensure_ascii=False))
    print(f"Dati: {report.tournaments} tornei, {report.players} liste ({api.calls} chiamate API)")

    deck = None
    if not a.no_deck:
        lists = [w for w in report.winners if w.get("decklist")]
        if lists:
            featured = max(lists, key=lambda w: w["players"])   # vincitore del torneo più grande
            try:
                cards = resolve_decklist(featured["decklist"], ROOT / "cache")
                found = sum(1 for c in cards if c.local)
                print(f"Lista della settimana: {featured['deck']} — immagini trovate {found}/{len(cards)}")
                deck = build_deck(featured, cards)
            except Exception as e:  # la lista non deve mai bloccare il report
                print(f"  Lista della settimana saltata: {e}")

    view = build_view(report, handle=a.handle, deck=deck)
    html = render_html(view, out / "carousel.html")
    slides = render_png(html, out)
    print(f"Slide: {len(slides)} PNG in {out}")

    caption = polish_with_claude(template_caption(view))
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    print("Caption salvata.")

    if not a.no_telegram:
        send_preview(slides, caption)


if __name__ == "__main__":
    main()
