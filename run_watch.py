#!/usr/bin/env python3
"""Watcher dei major: quando su limitlesstcg.com compare un major appena concluso
  1. prepara la «Top 8 in diretta» (copertina + top 8) e la mette in coda subito
  2. appena ci sono le liste, prepara «I mazzi dei campioni» e la mette in coda al primo 18:30 utile

  python run_watch.py --detect     # quanti major da lavorare (leggero, senza browser)
  python run_watch.py --process    # genera i post, aggiorna queue.json e data/majors_ids.json, riempie _site/
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

from indigo_meta import rubriche as R

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
IDS = ROOT / "data" / "majors_ids.json"
QUEUE = ROOT / "queue.json"
TZ = ZoneInfo("Europe/Rome")
SEASON_START = "2026-09-01"
ARCHIVE_SLOTS = {1, 2, 5}          # mar, mer, sab alle 18:30: dove spostare un post d'archivio
FRESH = {"top 8 in diretta", "campioni del major"}
OFFICIAL = re.compile(r"^(Regional|Special Event|.*International|.*World Championships?|Latin America|Europe|North America|Oceania)", re.I)


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-").replace("regional-", "").replace("special-event-", "")


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def pending() -> tuple[list[dict], list[dict]]:
    known = load_json(IDS, [])
    tids = {e["tid"] for e in known}
    new = [m for m in R.completed_majors(CACHE, max_age_h=0)
           if m["tid"] not in tids and m["format"] == "standard" and m["date"] >= SEASON_START and OFFICIAL.match(m["name"])]
    recent = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    for m in sorted(new, key=lambda m: m["date"]):
        e = {"tid": m["tid"], "name": m["name"], "date": m["date"], "cc": m["cc"], "players": m["players"]}
        if m["date"] >= recent:                      # appena giocato: va raccontato
            e.update(top8_done=False, champions_done=False)
        known.append(e)
    todo = [e for e in known if e.get("top8_done") is False or e.get("champions_done") is False]
    return known, todo


def utc(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")


def parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)


def taken(queue: list, when: dt.datetime) -> dict | None:
    return next((q for q in queue if abs((parse(q["at"]) - when).total_seconds()) < 3600), None)


def next_1830(after: dt.datetime, days: set | None = None) -> dt.datetime:
    d = after.replace(hour=18, minute=30, second=0, microsecond=0)
    while d <= after or (days is not None and d.weekday() not in days):
        d += dt.timedelta(days=1)
    return d


def put(queue: list, key: str, when: dt.datetime, nota: str) -> None:
    """Mette `key` in coda a `when`; se lo slot è occupato, sposta il post d'archivio al primo slot libero."""
    other = taken(queue, when)
    while other and other.get("nota") in FRESH:      # c'è già un post fresco: slitta il nuovo
        when = when + dt.timedelta(hours=3) if nota == "top 8 in diretta" else next_1830(when)
        other = taken(queue, when)
    if other:
        new = next_1830(when, ARCHIVE_SLOTS)
        while taken(queue, new):
            new = next_1830(new, ARCHIVE_SLOTS)
        print(f"  sposto {other['key']} → {new:%a %d %H:%M}")
        other["at"], other["nota"] = utc(new), f"{new:%a %H:%M} (spostato)"
    queue.append({"at": utc(when), "key": key, "nota": nota})
    queue.sort(key=lambda q: q["at"])


def to_site(src: Path, key: str) -> list[Path]:
    from indigo_meta.instagram import to_jpeg
    dst = ROOT / "_site" / key
    to_jpeg(sorted(src.glob("slide_*.png")), dst)
    shutil.copy(src / "caption.txt", dst / "caption.txt")
    return sorted(dst.glob("slide_*.jpg"))


def run(*args) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT)


def lists_ready(tid: int) -> bool:
    from indigo_meta.champions import load
    m = load(tid, CACHE, lists=8)
    return sum(1 for p in m.top if p.decklist) >= 8


def notify(slides: list[Path], caption: str) -> None:
    try:
        from indigo_meta.telegram import send_preview
        send_preview(slides, caption, None)
    except Exception as e:
        print("Telegram:", e)


def process() -> int:
    known, todo = pending()
    queue = load_json(QUEUE, [])
    now = dt.datetime.now(TZ)
    done = 0
    for e in todo:
        s = slug(e["name"])
        if e.get("top8_done") is False:
            run("run_champions.py", "--tid", str(e["tid"]), "--cc", e.get("cc", ""), "--top8-only")
            key = f"top8-{s}"
            slides = to_site(ROOT / "output" / f"top8-{e['tid']}", key)
            at = now + dt.timedelta(minutes=10) if 8 <= now.hour < 23 else (now + dt.timedelta(days=now.hour >= 23)).replace(hour=8, minute=30)
            put(queue, key, at, "top 8 in diretta")
            e["top8_done"], e["top8_at"] = True, utc(at)
            notify(slides, f"🔴 Nuovo major: {e['name']}. Top 8 in coda alle {at:%H:%M} del {at:%d/%m}.\n\n"
                           + (ROOT / "output" / f"top8-{e['tid']}" / "caption.txt").read_text())
            done += 1
        if e.get("champions_done") is False:
            if not lists_ready(e["tid"]):
                print(f"  {e['name']}: liste non ancora pubblicate, riprovo più tardi")
                continue
            run("run_champions.py", "--tid", str(e["tid"]), "--cc", e.get("cc", ""))
            key = f"campioni-{s}"
            slides = to_site(ROOT / "output" / f"campioni-{e['tid']}", key)
            base = parse(e["top8_at"]) if e.get("top8_at") else now
            at = next_1830(base + dt.timedelta(hours=18))
            put(queue, key, at, "campioni del major")
            e["champions_done"] = True
            notify(slides[:1], f"🏆 I mazzi dei campioni di {e['name']} in coda per {at:%A %d/%m alle %H:%M}.")
            done += 1
    IDS.write_text(json.dumps(known, ensure_ascii=False, indent=1))
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1))
    print(f"Post preparati: {done}")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--process", action="store_true")
    a = ap.parse_args()
    if a.detect:
        _, todo = pending()
        print(f"Major da lavorare: {[e['name'] for e in todo]}")
        out = os.getenv("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"todo={len(todo)}\n")
    if a.process:
        process()


if __name__ == "__main__":
    main()
