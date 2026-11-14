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
from indigo_meta.champions import load, flag, country
from indigo_meta.render import build_deck, render_png, num, MESI

ROOT = Path(__file__).resolve().parent
ORD = {1: "1° posto", 2: "2° posto", 3: "3°–4° posto", 4: "3°–4° posto", **{i: "5°–8° posto" for i in range(5, 9)}}


def date_it(s: str) -> str:
    m = re.match(r"(\d+)\w* (\w+) (\d{4})", s)
    if not m:
        return s
    month = dt.datetime.strptime(m.group(2), "%B").month
    return f"{m.group(1)} {MESI[month - 1]} {m.group(3)}"


def rec_dict(r: str) -> dict:
    w, l, t = (int(x) for x in (r.split("-") + ["0", "0", "0"])[:3]) if r else (0, 0, 0)
    return {"wins": w, "losses": l, "ties": t}


CATEGORY = "TCG Masters"


def build(tid: int, out_root: Path, cc: str = "", top8_only: bool = False) -> Path:
    m = load(tid, ROOT / "cache", lists=8)
    venue = {"cc": cc, "flag": flag(cc), "country": country(cc) if cc else ""}
    c = m.top[0]
    wins = sum(1 for p in c.path if p[3] == "V")
    r = rec_dict(c.record)
    swiss = f"{r['wins'] - wins}-{r['losses'] - sum(1 for p in c.path if p[3] == 'S')}-{r['ties']}" if c.record else "–"
    decks = []
    for p in ([] if top8_only else m.top[:8]):
        if not p.decklist:
            continue
        cards = resolve_decklist(p.decklist, ROOT / "cache")
        d = build_deck({"deck": p.deck, "tournament": m.name, "players": m.players, "player": p.name,
                        "record": rec_dict(p.record), "placing": p.place}, cards)
        d["kicker"] = f"{ORD[p.place]} · {m.name} · {CATEGORY}"
        d["country"], d["flag"] = p.country, p.flag
        decks.append(d)
    deck_counts = Counter(p.deck for p in m.top).most_common()
    italians = [p for p in m.top if p.cc == "IT"]
    import unicodedata
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", m.name).encode("ascii", "ignore").decode().lower()).strip("-")
    if c.opw:
        c.opw = c.opw.replace("%", "").replace(".", ",").rstrip("0").rstrip(",") + "%"
    out = out_root / (f"top8-{tid}" if top8_only else f"campioni-{tid}")
    out.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("champions.html.j2").render(
        m=m, decks=decks, deck_counts=deck_counts, italians=italians, swiss=swiss, date_it=date_it(m.date),
        num=num, brand_right=(m.name.upper()[:24] + (" " + venue["flag"] if venue["flag"] else "")), venue=venue,
        category=CATEGORY, only_top8=top8_only, n_slides=2 if top8_only else 2 + len(decks))
    (out / "champions.html").write_text(html, encoding="utf-8")
    slides = render_png(out / "champions.html", out)

    where = f" {venue['flag']} {venue['country']}" if venue["flag"] else ""
    lines = [f"🏆 I MAZZI DEI CAMPIONI · {m.name}{where} ({date_it(m.date)}) · {CATEGORY}", "",
             f"{num(m.players)} giocatori nella categoria {CATEGORY}. Ha vinto {c.name} {c.flag} con {c.deck}, record {c.record}.", ""]
    if c.path:
        verb = {"V": "battuto", "S": "perso contro", "P": "pareggio con"}
        lines += ["La strada verso il titolo:"] + [f"• {ph}: {verb[res]} {opp} {fl} ({dk})".replace("  ", " ") for ph, opp, dk, res, fl in c.path] + [""]
    lines += ["Top 8:"] + [f"{p.place}. {p.name} {p.flag} · {p.deck}" for p in m.top] + [""]
    for p in italians:
        lines.append(f"🇮🇹 Grande risultato per {p.name}: {'top 4' if p.place <= 4 else 'top 8'} con {p.deck}!")
    if italians:
        lines.append("")
    lines += ["Nelle slide le liste di tutta la top 8, carta per carta. Salvale per il prossimo torneo 📌", "",
              "Dati: Limitless TCG · RK9 · immagini carte © Pokémon / Nintendo / Creatures / GAME FREAK", "",
              "#pokemontcg #pokemontcgitalia #ptcg #regionals #decklist #tcgitalia"]
    if top8_only:
        lines = [f"🔴 RISULTATI · {m.name}{where} · {CATEGORY}", "",
                 f"È finito il {m.name}: {num(m.players)} giocatori. Ha vinto {c.name} {c.flag} con {c.deck}! 🏆", "",
                 "La top 8:"] + [f"{p.place}. {p.name} {p.flag} · {p.deck}" for p in m.top] + [""]
        lines += [f"🇮🇹 Grande risultato per {p.name}: {'top 4' if p.place <= 4 else 'top 8'} con {p.deck}!" for p in italians]
        lines += ["", "Domani le liste di tutta la top 8 nei «Mazzi dei campioni» 📌", "", "Dati: Limitless TCG · RK9", "",
                  "#pokemontcg #pokemontcgitalia #ptcg #regionals #tcgitalia"]
    (out / "caption.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Campioni: {m.name} — {len(slides)} slide in {out}")
    return out


def major_slug(name: str) -> str:
    import unicodedata
    s = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("-")
    return s.replace("regional-", "")


def build_analysis(tid: int, out_root: Path, cc: str = "", handle: str = "@indigo.meta") -> Path | None:
    """«Il mazzo del campione»: la lista che ha vinto il major spiegata carta per carta (carte chiave, piano di gioco,
    lista). Esce solo se c'è l'analisi (data/spotlight/analisi-<torneo>.json oppure Claude)."""
    from indigo_meta.spotlight import analysis, render_post
    m = load(tid, ROOT / "cache", lists=8)
    c = m.top[0]
    if not c.decklist:
        print(f"  Analisi {m.name} saltata: lista del campione non disponibile")
        return None
    key = f"analisi-{major_slug(m.name)}"
    cards = resolve_decklist(c.decklist, ROOT / "cache")
    deck = build_deck({"deck": c.deck, "tournament": m.name, "players": m.players, "player": c.name,
                       "record": rec_dict(c.record), "placing": 1}, cards)
    deck["kicker"] = f"1° posto · {m.name} · {CATEGORY}"
    deck["country"], deck["flag"] = c.country, c.flag
    an = analysis(deck, cards, key=key)
    if not an:
        print(f"  Analisi {m.name} saltata: manca data/spotlight/{key}.json (o la chiave di Claude)")
        return None
    vflag = flag(cc)
    wins = sum(1 for p in c.path if p[3] == "V")
    r = rec_dict(c.record)
    swiss = f"{r['wins'] - wins}-{r['losses'] - sum(1 for p in c.path if p[3] == 'S')}-{r['ties']}" if c.record else "–"
    same = sum(1 for p in m.top if p.deck == c.deck)
    beaten = [f"{opp} {fl} ({dk})".replace("  ", " ") for ph, opp, dk, res, fl in c.path if res == "V"]
    stats = [(c.record or "–", "record totale"), (swiss, "nei turni svizzeri"),
             (f"{same} su {len(m.top)}", f"{c.deck} in top {len(m.top)}")]
    if c.price_eur:
        price_txt = c.price_eur.replace(".", ",").replace("€", "").strip() + " €"
        stats.append((f"{float(c.price_eur.replace('€', '').strip()):.0f} €", "costo su Cardmarket"))
    elif c.opw:
        stats.append((c.opw, "forza avversari (OPW)"))
    cover = dict(
        kicker=f"Il mazzo del campione · {CATEGORY}", title=c.deck,
        why=f"Ha vinto il {m.name}{' ' + vflag if vflag else ''}: <b>1° su {num(m.players)} giocatori</b> con {c.name} {c.flag}.",
        verdict=an.get("nota") or (("<b>In top cut</b> ha battuto " + ", ".join(beaten) + ".") if beaten else ""),
        stats=stats, closing="I mazzi che vincono i major,|carta per carta.",
        source=f"Dati: major dal vivo ({date_it(m.date)}) · classifica e lista da Limitless TCG")
    out = out_root / f"analisi-{tid}"
    slides = render_post(out, cover, deck, an, handle, m.name.upper()[:24] + (" " + vflag if vflag else ""))
    where = f" {vflag} {country(cc)}" if vflag else ""
    lines = [f"🏆 IL MAZZO DEL CAMPIONE · {c.deck} · {m.name}{where} · {CATEGORY}", "",
             f"{c.name} {c.flag} ha vinto il {m.name} ({date_it(m.date)}, {num(m.players)} giocatori nella categoria {CATEGORY}) "
             f"con {c.deck}, record {c.record}.", "",
             "🃏 Le carte chiave: " + " · ".join(f"{k['name']} ({k['role'].lower()})" for pg in an["pages"] for k in pg), ""]
    if c.price_eur:
        lines += [f"💶 Costo del mazzo: {price_txt}. È il totale su Cardmarket indicato da Limitless TCG nella pagina delle liste "
                  f"del torneo (rilevato il {dt.date.today():%d/%m/%Y}): solo carte singole, spedizione esclusa. Il prezzo reale cambia "
                  "con versione, lingua e condizioni.", ""]
    lines += ["Nelle slide: carte chiave, piano di gioco e lista completa. La giocheresti così o cambieresti qualcosa? 👇", "",
              "Da dove vengono i dati: è un major dal vivo (torneo ufficiale Play! Pokémon). Classifica, record e lista sono "
              "quelli pubblicati da Limitless TCG e Limitless Labs; l'analisi è di Indigo Meta, sui testi ufficiali delle carte.", "",
              "Immagini carte © Pokémon / Nintendo / Creatures / GAME FREAK", "",
              "#pokemontcg #pokemontcgitalia #ptcg #regionals #decklist #tcgitalia"]
    (out / "caption.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Mazzo del campione: {m.name} — {len(slides)} slide in {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", type=int)
    ap.add_argument("--season", action="store_true")
    ap.add_argument("--cc", default="", help="paese della sede, se il torneo non è in majors_ids.json")
    ap.add_argument("--analysis", action="store_true", help="«Il mazzo del campione»: analisi della lista vincente")
    ap.add_argument("--top8-only", action="store_true", help="solo copertina e top 8 (risultati a caldo)")
    a = ap.parse_args()
    known = {e["tid"]: e.get("cc", "") for e in json.loads((ROOT / "data" / "majors_ids.json").read_text())}
    ids = [a.tid] if a.tid else list(known)
    for tid in ids:
        try:
            if a.analysis:
                build_analysis(tid, ROOT / "output", known.get(tid, "") or a.cc)
            else:
                build(tid, ROOT / "output", known.get(tid, "") or a.cc, top8_only=a.top8_only)
        except Exception as e:
            print(f"  Torneo {tid} saltato: {e}")


if __name__ == "__main__":
    main()
