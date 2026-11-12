#!/usr/bin/env python3
"""Indigo Meta — City League Report: i tornei giapponesi dell'ultima settimana completa (lun–dom)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.cityleague import summarize, week_tournaments
from indigo_meta.render import MESI, num, pct, render_png
from indigo_meta.telegram import send_preview

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="lunedì della settimana (YYYY-MM-DD); di default l'ultima completa")
    ap.add_argument("--handle", default="@indigo.meta")
    ap.add_argument("--no-telegram", action="store_true")
    a = ap.parse_args()
    today = dt.date.today()
    monday = dt.date.fromisoformat(a.start) if a.start else today - dt.timedelta(days=today.weekday() + 7)
    sunday = monday + dt.timedelta(days=6)
    ts = week_tournaments(monday, sunday, ROOT / "cache")
    if len(ts) < 5:
        print(f"Solo {len(ts)} City League in settimana: niente report.")
        return
    s = summarize(ts)
    week = monday.isocalendar()[1]
    dates = (f"{monday.day}–{sunday.day} {MESI[sunday.month - 1]}" if monday.month == sunday.month
             else f"{monday.day} {MESI[monday.month - 1][:3]} – {sunday.day} {MESI[sunday.month - 1][:3]}")

    # confronto con il meta online della stessa settimana, se il Meta Report è già stato calcolato
    cmp, rep = [], ROOT / "output" / f"{monday.year}-W{week:02d}" / "report.json"
    if rep.exists():
        online = {d["name"]: d["share"] for d in json.loads(rep.read_text())["decks"]}
        for name, n in s["top16"][:8]:
            cmp.append((name, n / s["slots16"], online.get(name, 0)))
    out = ROOT / "output" / f"{monday.year}-W{week:02d}-cityleague"
    out.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("cityleague_report.html.j2").render(
        s=s, top4=dict(s["top4"]), cmp=cmp, cmp_max=max([max(j, e) for _, j, e in cmp] or [1]) * 1.05,
        dates=dates, week=week, handle=a.handle, pct=pct, num=num, n_slides=5 if cmp else 4)
    (out / "report.html").write_text(html, encoding="utf-8")
    slides = render_png(out / "report.html", out)
    w0 = s["wins"][0]
    caption = "\n".join(
        [f"🇯🇵 CITY LEAGUE REPORT · {dates}", "",
         f"{s['n']} City League giocate in {s['prefectures']} prefetture giapponesi.", "",
         f"🏆 Il mazzo che vince di più: {w0[0]} ({w0[1]} vittorie)",
         f"📊 Il più presente in top 16: {s['top16'][0][0]} ({pct(s['top16'][0][1] / s['slots16'])} dei posti)", ""]
        + (["Nella quarta slide il confronto con il meta dei tornei online: dove il Giappone è diverso, c'è da guardare 👀", ""] if cmp else [])
        + ["Ricorda: le City League sono partite secche al meglio di una, e in Giappone alcune carte escono prima. "
           "Guarda le tendenze, non il singolo torneo.", "",
           "Dati: Limitless TCG", "", "#pokemontcg #pokemontcgitalia #ptcg #cityleague #metagame #tcgitalia"])
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"City League Report: {s['n']} tornei, {len(slides)} slide in {out}")
    if not a.no_telegram:
        send_preview(slides, caption, publish_key=out.name)


if __name__ == "__main__":
    main()
