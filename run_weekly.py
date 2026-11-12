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
    ap.add_argument("--spotlight", action="store_true", help="genera anche il post «Mazzo sotto la lente»")
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
        send_preview(slides, caption, publish_key=out.name)

    if a.spotlight and deck:
        render_spotlight(view, deck, ROOT / "output" / f"{year}-W{week:02d}-lente", a.handle)


def render_spotlight(view: dict, deck: dict, out: Path, handle: str) -> None:
    """Post «Mazzo sotto la lente»: il mazzo vincitore del torneo più grande, numeri + lista."""
    from jinja2 import Environment, FileSystemLoader
    from indigo_meta.render import pct, pp
    r = view["r"]
    sp = next((d for d in r.decks if d.name == deck["name"]), None)
    if not sp:
        print("  Mazzo sotto la lente saltato: mazzo non trovato nei dati")
        return
    avg = view["avg_conv"]
    if sp.conversion >= avg * 1.2:
        verdict = "Converte <b>sopra la media</b>: porta risultati più di quanto si gioca. Da tenere d'occhio."
    elif sp.delta is not None and sp.delta >= 2:
        verdict = ("<b>In forte crescita</b>, ma converte ancora sotto la media: lo stanno provando in tanti. "
                   "I risultati arriveranno?")
    else:
        verdict = "Ha vinto il torneo più grande, ma nel resto della settimana i numeri sono nella media."
    out.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("spotlight.html.j2").render(
        **{**view, "sp": sp, "verdict": verdict, "deck": deck, "deck_page": 2, "n_slides": 2})
    (out / "spotlight.html").write_text(html, encoding="utf-8")
    slides = render_png(out / "spotlight.html", out)
    caption = "\n".join([
        f"🔎 MAZZO SOTTO LA LENTE · {sp.name}", "",
        f"1° posto al torneo più grande della settimana: {deck['players']} giocatori ({deck['tournament']}).", "",
        f"📊 Meta share: {pct(sp.share)}" + (f" ({pp(sp.delta)} vs settimana prima)" if sp.delta is not None else ""),
        f"🎯 Top 8: {sp.top8} su {sp.entries} liste · conversion {pct(sp.conversion)} (media {pct(avg)})", "",
        "Nella seconda slide la lista vincente, carta per carta. Lo porteresti al prossimo torneo? 👇", "",
        "Dati: Limitless TCG · immagini carte © Pokémon / Nintendo / Creatures / GAME FREAK", "",
        "#pokemontcg #pokemontcgitalia #ptcg #decklist #metagame #tcgitalia"])
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"Mazzo sotto la lente: {len(slides)} slide in {out}")


if __name__ == "__main__":
    main()
