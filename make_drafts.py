#!/usr/bin/env python3
"""Prepara un pacchetto di post (bozze) da pubblicare a mano con il pulsante Telegram.

1. Benvenuto       2. Meta Report      3. League Cup      4. Mazzo sotto la lente
Le slide vanno in _site/<n>-<nome>/ come JPEG con la loro caption; send_drafts.py manda le anteprime.
"""
from __future__ import annotations

import shutil
import json
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.instagram import to_jpeg
from indigo_meta.render import render_png
from indigo_meta import majors

ROOT = Path(__file__).resolve().parent
HANDLE = "@indigo.meta"
WELCOME_CAPTION = """👋 Benvenuto su Indigo Meta!

Il punto di riferimento italiano per chi gioca al Pokémon TCG competitivo, dal primo torneo al Regional.

📊 Ogni lunedì, il Meta Report: analizziamo migliaia di liste dei tornei della settimana. I mazzi più giocati, quelli che arrivano davvero in top 8, chi sale e chi scende, e la lista vincente carta per carta.

🏆 Ogni martedì, le League Cup: tutte le Cup in Italia, regione per regione, così trovi subito quella più vicina.

📰 News appena escono: nuove espansioni, carte rivelate, regole e grandi tornei, partendo dalle fonti ufficiali giapponesi, dove tutto arriva prima.

Numeri veri, spiegati in modo chiaro, in italiano. Niente sensazioni: dati.

Seguici e scrivi nei commenti cosa porti al prossimo torneo 👇

#pokemontcg #pokemontcgitalia #ptcg #metagame #tcgitalia"""


CITY_CAPTION = """🇯🇵 COSA SONO LE CITY LEAGUE? E chi sta vincendo adesso

Sono i tornei ufficiali giapponesi del Pokémon TCG, giocati nei negozi. Li seguiamo perché in Giappone le espansioni escono mesi prima: le liste che vincono lì spesso arrivano da noi con il set successivo.

📋 Come funzionano
• Partite al meglio di una (BO1), da 25 minuti
• Turni svizzeri e poi top 8 a eliminazione diretta
• Ogni anno ci sono più stagioni di City League, e in ognuna ogni giocatore può fare un solo torneo
• Iscrizioni a sorteggio; chi vince ottiene la priorità per i Japan Championships

🏆 Chi vince adesso ({n} City League, {dates}, TCG Masters)
{winners}

🧠 Cosa significa per chi gioca
• Le carte arrivano prima: Hadou Seeker esce in Giappone il 27 novembre ed è legale nelle City League dal giorno dopo. Da noi non c'è ancora una data.
• Il BO1 premia i mazzi veloci e lascia più spazio alla fortuna: da noi si gioca al meglio di tre.
• Guarda i trend su tante City League, non il singolo risultato.

Ogni settimana il City League Report completo, con tutti i mazzi e il confronto con i tornei online 👀

Fonti: regolamento ufficiale Pokémon Card Game (Giappone), pokemon-card.com · Dati: Limitless TCG (City League ufficiali giapponesi)

#pokemontcg #pokemontcgitalia #ptcg #cityleague #pokemoncardgame #tcgitalia"""


def build_city_explainer(cl: Path, env) -> None:
    """«Cosa sono le City League?» con i dati dell'ultima settimana completa e le carte dei mazzi che vincono."""
    import datetime as dt
    from indigo_meta.cityleague import summarize, week_tournaments
    from indigo_meta.heroes import deck_hero, deck_heroes
    from indigo_meta.render import MESI, pct
    today = dt.date.today()
    mon = today - dt.timedelta(days=today.weekday() + 7)
    sun = mon + dt.timedelta(days=6)
    s = summarize(week_tournaments(mon, sun, ROOT / "cache"))
    dates = (f"{mon.day}–{sun.day} {MESI[sun.month - 1]}" if mon.month == sun.month
             else f"{mon.day} {MESI[mon.month - 1][:3]} – {sun.day} {MESI[sun.month - 1][:3]}")
    top16 = dict(s["top16"])
    winners = []
    for name, n in s["wins"][:3]:
        h = deck_hero(name, jp=True) or {}
        winners.append(dict(deck=name, wins=n, src=h.get("src"), name=h.get("name", name),
                            top16=pct(top16.get(name, 0) / s["slots16"])))
    heroes = deck_heroes([w for w, _ in s["wins"]], 3, jp=True)
    (cl / "c.html").write_text(env.get_template("cityleague.html.j2").render(
        handle=HANDLE, s=s, dates=dates, winners=winners, heroes=heroes, n=4), encoding="utf-8")
    render_png(cl / "c.html", cl)
    w = "\n".join(f"• {x['deck']}: {x['wins']} City League vinte, {x['top16']} dei posti in top 16" for x in winners)
    (cl / "caption.txt").write_text(CITY_CAPTION.format(n=s["n"], dates=dates, winners=w), encoding="utf-8")


def run(*cmd: str) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run([sys.executable, *cmd], check=True, cwd=ROOT)


def newest(pattern: str) -> Path:
    dirs = [d for d in (ROOT / "output").glob(pattern) if d.is_dir() and list(d.glob("slide_*.png"))]
    return max(dirs, key=lambda d: d.stat().st_mtime)


def main():
    out = ROOT / "output"
    # 1. Benvenuto
    w = out / "benvenuto"
    w.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    (w / "welcome.html").write_text(env.get_template("welcome.html.j2").render(handle=HANDLE), encoding="utf-8")
    render_png(w / "welcome.html", w)
    (w / "caption.txt").write_text(WELCOME_CAPTION, encoding="utf-8")
    # 2 + 4. Meta Report e Mazzo sotto la lente (ultima settimana completa)
    run("run_weekly.py", "--no-telegram", "--spotlight")
    meta = newest("20??-W??")
    lente = newest("*-lente")
    extra = sorted((d for d in out.glob("*-lente[0-9]") if list(d.glob("slide_*.png"))), key=lambda d: d.name)
    # Calendario dei major e spiegazione delle City League
    cal = out / "calendario"
    majors.build(cal, HANDLE)
    cl = out / "cityleague"
    cl.mkdir(parents=True, exist_ok=True)
    build_city_explainer(cl, env)
    # 3. League Cup (settimana in corso)
    run("run_cups.py", "--no-telegram")
    cup = newest("*-cup")

    site = ROOT / "_site"
    posts = [(w, "benvenuto"), (meta, f"meta-{meta.name}"), (cup, f"cup-{cup.name.replace('-cup', '')}"),
             (lente, f"lente-{lente.name.replace('-lente', '')}"), (cal, "calendario-2027"), (cl, "city-league-2")]
    posts += [(d, f"lente{d.name[-1]}-{d.name.split('-lente')[0]}") for d in extra]
    # 9. City League Report (stessa settimana del Meta Report)  ·  10+. I mazzi dei campioni, dal più recente
    import datetime as _dt
    y, w = int(meta.name[:4]), int(meta.name[-2:])
    try:   # i post nuovi non devono mai bloccare quelli già in coda
        run("run_cityleague.py", "--no-telegram", "--start", _dt.date.fromisocalendar(y, w, 1).isoformat())
    except subprocess.CalledProcessError as e:
        print("City League Report saltato:", e)
    clr = out / f"{meta.name}-cityleague"
    if list(clr.glob("slide_*.png")):
        posts.append((clr, f"cityleague-{meta.name}"))
    try:
        run("run_champions.py", "--season")
        run("run_champions.py", "--season", "--analysis")      # «Il mazzo del campione», dove c'è l'analisi
    except subprocess.CalledProcessError as e:
        print("Mazzi dei campioni saltati:", e)
    import json as _json
    for e in reversed(_json.loads((ROOT / "data" / "majors_ids.json").read_text())):
        import unicodedata, re as _re
        slug = _re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", e["name"]).encode("ascii", "ignore").decode().lower()).strip("-")
        d = out / f"campioni-{e['tid']}"
        if list(d.glob("slide_*.png")):
            posts.append((d, f"campioni-{slug.replace('regional-', '')}"))
        d = out / f"analisi-{e['tid']}"
        if list(d.glob("slide_*.png")):
            posts.append((d, f"analisi-{slug.replace('regional-', '')}"))
    # News e «carte da tenere d'occhio» preparate a mano (data/news, data/watch)
    for f in sorted((ROOT / "data" / "news").glob("*.json")):
        try:
            run("run_news.py", str(f))
            meta = json.loads(f.read_text())
            k = meta["key"]
            if meta.get("manual"):                   # immagini non ufficiali: solo pubblicazione a mano
                (out / k / "MANUAL").write_text("immagini non ufficiali: pubblicare a mano\n")
            posts.append((out / k, k))
        except subprocess.CalledProcessError as e:
            print("News saltata:", f.name, e)
    for f in sorted((ROOT / "data" / "watch").glob("*.json")):
        try:
            run("run_cards_watch.py", str(f))
            k = json.loads(f.read_text())["key"]
            posts.append((out / k, k))
        except subprocess.CalledProcessError as e:
            print("Carte saltate:", f.name, e)
    for f in sorted((ROOT / "data" / "stories").glob("*.json")):
        try:
            run("run_story.py", str(f))
            k = json.loads(f.read_text())["key"]
            posts.append((out / k, k))
        except subprocess.CalledProcessError as e:
            print("Storia saltata:", f.name, e)
    try:                             # guide senza scadenza
        run("run_guide.py")
        posts.append((out / "guida-come-iniziare", "guida-come-iniziare"))
    except subprocess.CalledProcessError as e:
        print("Guida saltata:", e)
    for src, name in posts:          # chiavi stabili (niente numeri): la coda non si sposta mai
        dst = site / name
        to_jpeg(sorted(src.glob("slide_*.png")), dst)
        shutil.copy(src / "caption.txt", dst / "caption.txt")
        if (src / "MANUAL").exists():
            shutil.copy(src / "MANUAL", dst / "MANUAL")
        print(f"Bozza pronta: {dst.name} ({len(list(dst.glob('*.jpg')))} slide)")
    for d in sorted((ROOT / "assets" / "reels").glob("*")):      # reel già pronti: video, copertina e caption
        if (d / "reel.mp4").exists() and (d / "caption.txt").exists():
            shutil.copytree(d, site / d.name, dirs_exist_ok=True)
            print(f"Reel pronto: {d.name}")
    (site / "index.html").write_text("<!doctype html><title>Indigo Meta</title><p>Indigo Meta</p>")


if __name__ == "__main__":
    main()
