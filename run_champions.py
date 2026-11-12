#!/usr/bin/env python3
"""Indigo Meta — «I mazzi dei campioni» per un major (o per tutti quelli della stagione).

Uso:
  python run_champions.py --tid 584            # un torneo (id della pagina limitlesstcg.com/tournaments/<id>)
  python run_champions.py --season             # tutti i major della stagione in data/majors_ids.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.cards import resolve_decklist
from indigo_meta.champions import load
from indigo_meta.render import build_deck, render_png, num, MESI

ROOT = Path(__file__).resolve().parent
ORD = {1: "1° posto", 2: "2° posto", 3: "3°–4° posto", 4: "3°–4° posto"}


def date_it(s: str) -> str:
    m = re.match(r"(\d+)\w* (\w+) (\d{4})", s)
    if not m:
        return s
    month = dt.datetime.strptime(m.group(2), "%B").month
    return f"{m.group(1)} {MESI[month - 1]} {m.group(3)}"


def rec_dict(r: str) -> dict:
    w, l, t = (int(x) for x in (r.split("-") + ["0", "0", "0"])[:3]) if r else (0, 0, 0)
    return {"wins": w, "losses": l, "ties": t}


def build(tid: int, out_root: Path) -> Path:
    m = load(tid, ROOT / "cache")
    c = m.top[0]
    wins = sum(1 for p in c.path if p[3] == "V")
    r = rec_dict(c.record)
    swiss = f"{r['wins'] - wins}-{r['losses'] - sum(1 for p in c.path if p[3] == 'S')}-{r['ties']}" if c.record else "–"
    decks = []
    for p in m.top[:4]:
        if not p.decklist:
            continue
        cards = resolve_decklist(p.decklist, ROOT / "cache")
        d = build_deck({"deck": p.deck, "tournament": m.name, "players": m.players, "player": p.name,
                        "record": rec_dict(p.record), "placing": p.place}, cards)
        d["kicker"] = f"{ORD[p.place]} · {m.name}"
        d["country"] = p.country
        decks.append(d)
    deck_counts = Counter(p.deck for p in m.top).most_common()
    italians = [p for p in m.top if p.cc == "IT"]
    import unicodedata
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", m.name).encode("ascii", "ignore").decode().lower()).strip("-")
    if c.opw:
        c.opw = c.opw.replace("%", "").replace(".", ",").rstrip("0").rstrip(",") + "%"
    out = out_root / f"campioni-{tid}"
    out.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("champions.html.j2").render(
        m=m, decks=decks, deck_counts=deck_counts, italians=italians, swiss=swiss, date_it=date_it(m.date),
        num=num, brand_right=m.name.upper()[:24], n_slides=3 + len(decks))
    (out / "champions.html").write_text(html, encoding="utf-8")
    slides = render_png(out / "champions.html", out)

    lines = [f"🏆 I MAZZI DEI CAMPIONI · {m.name} ({date_it(m.date)})", "",
             f"{num(m.players)} giocatori in Masters. Ha vinto {c.name} ({c.country}) con {c.deck}, record {c.record}.", ""]
    if c.path:
        verb = {"V": "battuto", "S": "perso contro", "P": "pareggio con"}
        lines += ["La strada verso il titolo:"] + [f"• {ph}: {verb[res]} {opp} ({dk})" for ph, opp, dk, res in c.path] + [""]
    lines += ["Top 8:"] + [f"{p.place}. {p.name} ({p.country}) · {p.deck}" for p in m.top] + [""]
    for p in italians:
        lines.append(f"🇮🇹 Grande risultato per {p.name}: {'top 4' if p.place <= 4 else 'top 8'} con {p.deck}!")
    if italians:
        lines.append("")
    lines += ["Nelle slide le liste dei primi quattro, carta per carta. Salvale per il prossimo torneo 📌", "",
              "Dati: Limitless TCG · RK9 · immagini carte © Pokémon / Nintendo / Creatures / GAME FREAK", "",
              "#pokemontcg #pokemontcgitalia #ptcg #regionals #decklist #tcgitalia"]
    (out / "caption.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Campioni: {m.name} — {len(slides)} slide in {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", type=int)
    ap.add_argument("--season", action="store_true")
    a = ap.parse_args()
    ids = [a.tid] if a.tid else [e["tid"] for e in json.loads((ROOT / "data" / "majors_ids.json").read_text())]
    for tid in ids:
        try:
            build(tid, ROOT / "output")
        except Exception as e:
            print(f"  Torneo {tid} saltato: {e}")


if __name__ == "__main__":
    main()
