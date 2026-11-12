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


CITY_CAPTION = """🇯🇵 COSA SONO LE CITY LEAGUE?

Sono i tornei ufficiali giapponesi del Pokémon TCG, giocati nei negozi. Li seguiamo perché in Giappone le espansioni escono mesi prima: le liste che vincono lì spesso arrivano da noi con il set successivo.

Come funzionano:
• Partite al meglio di una (BO1), da 25 minuti
• Turni svizzeri e poi top 8 a eliminazione diretta
• Ogni anno ci sono più stagioni di City League, e in ognuna ogni giocatore può fare un solo torneo
• Le iscrizioni sono a sorteggio: con un torneo a testa i posti vanno a più giocatori, e nessuno accumula punti giocandone tanti
• Chi vince ottiene la priorità per i Japan Championships

Come leggerle: il BO1 premia i mazzi veloci e lascia più spazio alla fortuna. Per questo guardiamo i trend su tante City League, non il singolo risultato.

Presto qui: i mazzi che vincono in Giappone, spiegati in italiano. Seguici per non perderli 👀

Fonte: regolamento ufficiale Pokémon Card Game (Giappone)

#pokemontcg #pokemontcgitalia #ptcg #cityleague #pokemoncardgame #tcgitalia"""


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
    (cl / "c.html").write_text(env.get_template("cityleague.html.j2").render(handle=HANDLE), encoding="utf-8")
    render_png(cl / "c.html", cl)
    (cl / "caption.txt").write_text(CITY_CAPTION, encoding="utf-8")
    # 3. League Cup (settimana in corso)
    run("run_cups.py", "--no-telegram")
    cup = newest("*-cup")

    site = ROOT / "_site"
    posts = [(w, "benvenuto"), (meta, f"meta-{meta.name}"), (cup, f"cup-{cup.name.replace('-cup', '')}"),
             (lente, f"lente-{lente.name.replace('-lente', '')}"), (cal, "calendario-2027"), (cl, "city-league")]
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
    except subprocess.CalledProcessError as e:
        print("Mazzi dei campioni saltati:", e)
    import json as _json
    for e in reversed(_json.loads((ROOT / "data" / "majors_ids.json").read_text())):
        import unicodedata, re as _re
        slug = _re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", e["name"]).encode("ascii", "ignore").decode().lower()).strip("-")
        d = out / f"campioni-{e['tid']}"
        if list(d.glob("slide_*.png")):
            posts.append((d, f"campioni-{slug.replace('regional-', '')}"))
    # News e «carte da tenere d'occhio» preparate a mano (data/news, data/watch)
    for f in sorted((ROOT / "data" / "news").glob("*.json")):
        try:
            run("run_news.py", str(f))
            k = json.loads(f.read_text())["key"]
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
    try:                             # guide senza scadenza
        run("run_guide.py")
        posts.append((out / "guida-come-iniziare", "guida-come-iniziare"))
    except subprocess.CalledProcessError as e:
        print("Guida saltata:", e)
    for src, name in posts:          # chiavi stabili (niente numeri): la coda non si sposta mai
        dst = site / name
        to_jpeg(sorted(src.glob("slide_*.png")), dst)
        shutil.copy(src / "caption.txt", dst / "caption.txt")
        print(f"Bozza pronta: {dst.name} ({len(list(dst.glob('*.jpg')))} slide)")
    (site / "index.html").write_text("<!doctype html><title>Indigo Meta</title><p>Indigo Meta</p>")


if __name__ == "__main__":
    main()
