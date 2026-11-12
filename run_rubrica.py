#!/usr/bin/env python3
"""Indigo Meta — rubriche settimanali. Ogni comando crea output/<chiave>/ con slide_XX.png e caption.txt
e stampa la chiave sull'ultima riga.

  python run_rubrica.py carte      [--week 2026-W45]   # Le carte più giocate (tornei online)
  python run_rubrica.py matchup    [--week 2026-W45]   # Chi batte chi
  python run_rubrica.py anteprima  [--date 2026-11-13] # Il major del weekend
  python run_rubrica.py italiani                        # Gli italiani nei major della stagione
  python run_rubrica.py stagione                        # La stagione in numeri
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta import rubriche as R
from indigo_meta.champions import country, flag
from indigo_meta.limitless import Limitless
from indigo_meta.metrics import iso_week_bounds, last_completed_week
from indigo_meta.render import MESI, num, render_png

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
HANDLE = "@indigo.meta"
TAGS = "#pokemontcg #pokemontcgitalia #ptcg #tcgitalia #pokemoncardgame"


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def it_num(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def dates_it(a: dt.date, b: dt.date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {MESI[b.month - 1]}"
    return f"{a.day} {MESI[a.month - 1]} – {b.day} {MESI[b.month - 1]}"


def week_arg(s: str | None) -> tuple[int, int]:
    if s:
        y, w = re.match(r"(\d{4})-?W(\d{1,2})", s).groups()
        return int(y), int(w)
    return last_completed_week()


def short(name: str, n: int = 14) -> str:
    return name if len(name) <= n else name.split()[0]


def card_images(cards: list[dict]) -> list[dict]:
    """Nome italiano e immagine ufficiale (TCGdex / Limitless) per una lista di carte."""
    from indigo_meta.cards import resolve_decklist
    out = []
    for c in cards:
        dl = {c["section"]: [{"count": 1, "name": c["name"], "set": c["set"], "number": c["number"]}]}
        try:
            r = resolve_decklist(dl, CACHE)[0]
            out.append(dict(c, name=r.name or c["name"], src=Path(r.local).resolve().as_uri() if r.local else None))
        except Exception as e:
            print(f"  immagine {c['name']}: {e}")
            out.append(dict(c, src=None))
    return out


def render(r: dict, key: str, caption: str) -> Path:
    out = ROOT / "output" / key
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("slide_*.png"):
        old.unlink()
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    r.setdefault("brand_right", "")
    (out / "rubrica.html").write_text(env.get_template("rubriche.html.j2").render(r=r), encoding="utf-8")
    slides = render_png(out / "rubrica.html", out)
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"{len(slides)} slide in {out}")
    return out


# ------------------------------------------------------------------ Le carte più giocate
def carte(a) -> str | None:
    y, w = week_arg(a.week)
    api = Limitless(CACHE, verbose=False)
    lists, n_t = R.week_top_lists(api, y, w)
    if len(lists) < 40:
        print("Troppe poche liste, salto"); return None
    py, pw, _ = (dt.date.fromisocalendar(y, w, 1) - dt.timedelta(days=7)).isocalendar()
    prev = R.card_usage(R.week_top_lists(api, py, pw)[0])
    use = R.card_usage(lists)
    prev_pct = {(c["section"], c["name"]): c["pct"] for c in prev["cards"]}
    deck_names = {p["deck"]["name"].lower() for p in lists}
    trainers = [c for c in use["cards"] if c["section"] == "trainer"][:10]
    pokemon = [c for c in use["cards"] if c["section"] == "pokemon" and c["n_decks"] >= 3 and c["main_share"] <= 0.5
               and not any(c["name"].split()[0].lower() in d for d in deck_names)][:8]
    moves = []
    for c in use["cards"]:
        if c["pct"] >= 0.08 or prev_pct.get((c["section"], c["name"]), 0) >= 0.08:
            moves.append((c["pct"] - prev_pct.get((c["section"], c["name"]), 0), c))
    up = [c for d, c in sorted(moves, key=lambda x: -x[0]) if d > 0.02][:3]
    down = [c for d, c in sorted(moves, key=lambda x: x[0]) if d < -0.02][:3]
    allc = card_images(trainers + pokemon + up + down)

    def view(c, i):
        v = allc[i]
        d = c["pct"] - prev_pct.get((c["section"], c["name"]), 0)
        return {"name": v["name"], "src": v["src"], "pct": pct(c["pct"]), "avg": it_num(c["avg"]),
                "n_decks": c["n_decks"], "delta": f"{abs(d) * 100:.0f} pt"}

    k = 0
    T = [view(c, k + i) for i, c in enumerate(trainers)]; k += len(trainers)
    P = [view(c, k + i) for i, c in enumerate(pokemon)]; k += len(pokemon)
    U = [view(c, k + i) for i, c in enumerate(up)]; k += len(up)
    D = [view(c, k + i) for i, c in enumerate(down)]
    start, end = iso_week_bounds(y, w)
    dates = dates_it(start.date(), (end - dt.timedelta(days=1)).date())
    r = {"kind": "carte", "category": f"settimana {w} · TCG", "brand_right": f"SETTIMANA {w}", "n_slides": 4,
         "n_lists": use["n"], "n_tournaments": n_t, "dates": dates, "podium": T[:3], "trainers": T,
         "pokemon": P, "up": U, "down": D, "prev_week": pw, "source": "Dati: Limitless TCG"}
    cap = "\n".join([
        f"🃏 LE CARTE PIÙ GIOCATE · settimana {w} ({dates})", "",
        f"Abbiamo contato le carte di {use['n']} liste arrivate in top 8 in {n_t} tornei online.", "",
        "Gli Allenatori che non mancano mai:", *[f"• {c['name']} – {c['pct']} delle liste" for c in T[:5]], "",
        *(["In crescita: " + ", ".join(c["name"] for c in U)] if U else []),
        *(["In calo: " + ", ".join(c["name"] for c in D)] if D else []), "",
        "Quale carta non toglieresti mai dal tuo mazzo? 👇", "",
        "Dati: Limitless TCG · immagini carte © Pokémon / Nintendo / Creatures / GAME FREAK", "", TAGS])
    key = f"carte-giocate-{y}-W{w:02d}"
    render(r, key, cap)
    return key


# ------------------------------------------------------------------ Matchup
def diverge(wr: float) -> str:
    """Scala divergente: grigio neutro a 50%, blu (favorevole) / rosso (sfavorevole) pieni a ±20 punti."""
    mid, blue, red = (0x38, 0x38, 0x35), (0x39, 0x87, 0xE5), (0xE6, 0x67, 0x67)
    t = max(-1.0, min(1.0, (wr - 0.5) / 0.20))
    pole = blue if t > 0 else red
    t = abs(t)
    return "#" + "".join(f"{round(m + (p - m) * t):02x}" for m, p in zip(mid, pole))


def matchup(a) -> str | None:
    y, w = week_arg(a.week)
    api = Limitless(CACHE, verbose=False)
    lists, _ = R.week_top_lists(api, y, w)
    names = {}
    for p in lists:
        names[p["deck"]["id"]] = p["deck"]["name"]
    top = [d for d, _ in Counter(p["deck"]["id"] for p in lists).most_common(6)]
    g = R.matchups(api, y, w, top, min_games=a.min_games)
    decks = [{"id": d, "name": names[d], "short": names[d]} for d in top]
    grid, games, avgs = [], 0, []
    for d in decks:
        cells, wsum, gsum = [], 0.0, 0
        for o in decks:
            if d["id"] == o["id"]:
                cells.append({"self": True}); continue
            c = g.get((d["id"], o["id"]))
            if not c:
                cells.append({"ok": False}); continue
            if c["ok"]:
                cells.append({"ok": True, "wr": pct(c["wr"]), "games": c["games"], "color": diverge(c["wr"])})
            else:
                cells.append({"ok": False})
            wsum += c["wr"] * c["games"]; gsum += c["games"]
        grid.append({"deck": d, "cells": cells})
        avgs.append((wsum / gsum if gsum else 0, d))
    games = sum(c["games"] for (x, y_), c in g.items() if x < y_)
    if games < 150:
        print("Troppe poche partite, salto"); return None
    avgs.sort(key=lambda x: -x[0])
    best = avgs[0]
    big = max(((c["wr"], k, c["games"]) for k, c in g.items() if c["games"] >= 30), default=None)
    if big:
        wr, (x, y_), n = big
        headline = f"<b>{names[x]}</b> ha battuto <b>{names[y_]}</b> nel <b>{pct(wr)}</b> delle partite ({n} partite)."
    else:
        headline = f"<b>{best[1]['name']}</b> è il mazzo con i matchup migliori della settimana."
    mx = max(v for v, _ in avgs) or 1
    start, end = iso_week_bounds(y, w)
    dates = dates_it(start.date(), (end - dt.timedelta(days=1)).date())
    r = {"kind": "matchup", "category": f"settimana {w} · TCG", "brand_right": f"SETTIMANA {w}", "n_slides": 3,
         "dates": dates, "decks": decks, "grid": grid, "games": num(games), "min_games": a.min_games,
         "headline": headline, "best": {"short": short(best[1]["name"], 10), "avg": pct(best[0])},
         "ranking": [{"name": d["name"], "avg": pct(v), "w": round(v / mx * 100)} for v, d in avgs],
         "source": "Partite dei tornei online · dati: Limitless TCG"}
    cap = "\n".join([
        f"⚔️ MATCHUP DELLA SETTIMANA · settimana {w} ({dates})", "",
        headline.replace("<b>", "").replace("</b>", ""), "",
        "Chi regge meglio il meta (media vittorie contro gli altri mazzi top):",
        *[f"{i}. {d['name']} – {pct(v)}" for i, (v, d) in enumerate(avgs, 1)], "",
        f"Analizzate {num(games)} partite tra i 6 mazzi più presenti in top 8 nei tornei online. Pareggi = mezza vittoria.", "",
        "Sei d'accordo con la tabella? Qual è il matchup che temi di più? 👇", "", "Dati: Limitless TCG", "", TAGS])
    key = f"matchup-{y}-W{w:02d}"
    render(r, key, cap)
    return key


# ------------------------------------------------------------------ Anteprima del major
def latest_report() -> dict | None:
    reps = sorted((ROOT / "output").glob("20??-W??/report.json"))
    return json.loads(reps[-1].read_text()) if reps else None


def anteprima(a) -> str | None:
    today = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    e = R.weekend_major(today)
    if not e:
        print("Nessun major questo weekend, salto"); return None
    s, en = dt.date.fromisoformat(e["start"]), dt.date.fromisoformat(e["end"])
    rep = latest_report()
    favs = []
    if rep:
        ds = sorted(rep["decks"], key=lambda d: -d["top8_share"])[:5]
        favs = [{"name": d["name"], "top8": pct(d["top8_share"]),
                 "note": f"Tier {d['tier']} · {pct(d['share'])} dei giocatori online" if d.get("tier") else f"{pct(d['share'])} dei giocatori online"}
                for d in ds]
    last = R.majors_list()[-1]
    done = {m["tid"]: m for m in R.completed_majors(CACHE, max_age_h=6)}
    lp = R.major_players(last["tid"], CACHE)
    win_cc, _, win_name = (done.get(last["tid"], {}).get("winner") or "-").partition("-")
    last_deck = lp[0]["deck"] if lp else ""
    last_line = (f"L'ultimo major, il <b>{last['name']}</b> {flag(last.get('cc', ''))}, l'ha vinto "
                 f"<b>{win_name}</b> {flag(win_cc)} con <b>{last_deck}</b>." if win_name else "")
    nxt = [dict(x, flag=flag(x["cc"]), when=dates_it(dt.date.fromisoformat(x["start"]), dt.date.fromisoformat(x["end"])))
           for x in R.next_majors(en, 3)]
    r = {"kind": "anteprima", "category": "TCG Masters", "brand_right": f"{e['name'].upper()} {flag(e['cc'])}",
         "n_slides": 3, "e": e, "flag": flag(e["cc"]), "when": dates_it(s, en), "days": (en - s).days + 1,
         "top_deck_short": short(favs[0]["name"], 11) if favs else "–", "last_winner_short": short(last_deck, 11) or "–",
         "favs": favs, "week": rep["week"] if rep else "", "last_line": last_line, "next": nxt,
         "source": "Calendario ufficiale Play! Pokémon · dati: Limitless TCG"}
    cap = "\n".join([
        f"🏟️ QUESTO WEEKEND · {e['label']} {e['name']} {flag(e['cc'])} ({dates_it(s, en)}) · TCG Masters", "",
        "I mazzi da battere secondo i tornei online della settimana:",
        *[f"{i}. {d['name']} – {d['top8']} dei posti in top 8" for i, d in enumerate(favs[:4], 1)], "",
        last_line.replace("<b>", "").replace("</b>", ""), "",
        "📅 Domenica sera: la Top 8 in diretta", "📅 Lunedì: i mazzi dei campioni, con tutte le liste", "",
        "Chi vince secondo te? Scrivi il tuo pronostico 👇", "", TAGS + " #regionals"])
    key = f"anteprima-{e['start']}"
    render(r, key, cap)
    return key


# ------------------------------------------------------------------ Italiani nei major
def italiani(a) -> str | None:
    data = R.italians(CACHE)
    if not data:
        return None
    allp, rows = [], []
    for m in reversed(data):
        b = m["best"]
        city = m["name"].replace("Regional ", "").replace("Special Event ", "")
        rows.append({"flag": flag(m.get("cc", "")), "short": city,
                     "who": b["name"] if b else "nessun italiano in classifica",
                     "detail": f"{b['deck']} · {len(m['italians'])} italiani in classifica" if b else f"{m['listed']} giocatori in classifica",
                     "place": f"{b['place']}°" if b else "–"})
        allp += [dict(p, major=city) for p in m["italians"]]
    best = {}
    for p in sorted(allp, key=lambda p: p["place"]):
        best.setdefault(p["name"], p)
    best = list(best.values())[:8]
    top = best[0] if best else None
    top8 = sum(1 for p in allp if p["place"] <= 8)
    headline = (f"Miglior risultato: <b>{top['name']}</b>, {top['place']}° al {top['major']} con {top['deck']}." if top else "")
    r = {"kind": "italiani", "category": "TCG Masters", "brand_right": "STAGIONE 2027", "n_slides": 3,
         "n_majors": len(data), "total": len(allp), "best_place": f"{top['place']}°" if top else "–",
         "top8_count": top8, "headline": headline, "majors": rows[:8], "best": best,
         "source": "Classifiche dei major · dati: Limitless TCG"}
    cap = "\n".join([
        f"🇮🇹 GLI ITALIANI NEI MAJOR · stagione 2027 · TCG Masters", "",
        f"{len(allp)} piazzamenti italiani nelle classifiche dei {len(data)} major giocati finora.",
        headline.replace("<b>", "").replace("</b>", ""), "",
        "I migliori della stagione:", *[f"{i}. {p['name']} – {p['place']}° {p['major']} ({p['deck']})" for i, p in enumerate(best[:5], 1)], "",
        "Conosci uno di loro? Taggalo nei commenti 👇", "", "Dati: Limitless TCG", "", TAGS + " #regionals"])
    key = f"italiani-{dt.date.today().isoformat()}"
    render(r, key, cap)
    return key


# ------------------------------------------------------------------ La stagione in numeri
def stagione(a) -> str | None:
    s = R.season(CACHE)
    if not s["majors"]:
        return None
    done = {m["tid"]: m for m in R.completed_majors(CACHE, max_age_h=6)}
    players = sum(done.get(m["tid"], {}).get("players", 0) for m in s["majors"])
    mw = s["wins"][0][1] if s["wins"] else 1
    mt = s["top8"][0][1] if s["top8"] else 1
    countries = [{"cc": c, "flag": flag(c), "name": country(c), "n": n} for c, n in s["countries"][:8]]
    it = dict(s["countries"]).get("IT", 0)
    italy_line = "" if any(c["cc"] == "IT" for c in countries) else (
        f"🇮🇹 L'Italia: <b>{it} posti in top 8</b> finora." if it else "🇮🇹 L'Italia non ha ancora piazzato un giocatore in top 8.")
    top_deck, top_wins = s["wins"][0]
    others = [d for d, n in s["wins"] if n == top_wins]
    headline = (f"<b>{top_deck}</b> ha vinto {top_wins} major su {len(s['majors'])}: è il mazzo della stagione finora."
                if len(others) == 1 else f"Nessun mazzo domina: <b>{', '.join(others)}</b> hanno vinto {top_wins} major a testa.")
    r = {"kind": "stagione", "category": "TCG Masters", "brand_right": "STAGIONE 2027", "n_slides": 3, "season": "2027",
         "n_majors": len(s["majors"]), "players": num(players), "top_wins": top_wins, "top_deck_short": short(top_deck, 12),
         "headline": headline,
         "wins": [{"name": d, "n": n, "w": round(n / mw * 100)} for d, n in s["wins"][:5]],
         "top8": [{"name": d, "n": n, "w": round(n / mt * 100)} for d, n in s["top8"][:6]],
         "countries": countries, "italy_line": italy_line, "source": "Major della stagione · dati: Limitless TCG"}
    cap = "\n".join([
        f"📊 LA STAGIONE IN NUMERI · {len(s['majors'])} major · TCG Masters", "",
        headline.replace("<b>", "").replace("</b>", ""), "",
        "Vittorie per mazzo:", *[f"• {d}: {n}" for d, n in s["wins"][:5]], "",
        "Nazioni con più posti in top 8: " + " ".join(f"{c['flag']} {c['n']}" for c in countries[:5]), "",
        "Quale mazzo vincerà il prossimo major? 👇", "", "Dati: Limitless TCG", "", TAGS + " #regionals"])
    key = f"stagione-{dt.date.today().isoformat()}"
    render(r, key, cap)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["carte", "matchup", "anteprima", "italiani", "stagione"])
    ap.add_argument("--week")
    ap.add_argument("--date")
    ap.add_argument("--min-games", type=int, default=15)
    a = ap.parse_args()
    key = globals()[a.kind](a)
    print(key or "")
    sys.exit(0 if key else 3)


if __name__ == "__main__":
    main()
