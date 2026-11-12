#!/usr/bin/env python3
"""Il regista: a ogni slot del piano editoriale genera la rubrica giusta e la mette in _site/<chiave>/
pronta per GitHub Pages e Instagram. Stampa la chiave (vuota se lo slot è libero o occupato dalla coda).

Piano (ora italiana):
  mer 12:30 Le carte più giocate        gio 12:30 Matchup della settimana    gio 18:30 City League Report
  ven 12:30 Anteprima del major         ven 18:30 Mazzo sotto la lente       sab 12:30 Italiani nei major / Stagione
  dom 12:30 Mazzo sotto la lente n. 2
  (lun e mar 12:47 Meta Report e League Cup hanno i loro workflow; i 18:30 di lun/mar/mer/sab sono della coda)

  python run_slot.py                 # decide dall'ora attuale
  python run_slot.py --slot gio-18   # forza uno slot (prove)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Rome")
DAYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
PLAN = {("mer", 12): "carte", ("gio", 12): "matchup", ("gio", 18): "cityleague", ("ven", 12): "anteprima",
        ("ven", 18): "lente", ("sab", 12): "italiani-stagione", ("dom", 12): "lente2"}


def py(*args, ok=(0,)) -> subprocess.CompletedProcess:
    print("$", " ".join(args), flush=True)
    r = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)
    print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
    if r.returncode not in ok:
        raise SystemExit(f"Comando fallito: {' '.join(args)}")
    return r


def queue_busy(slot_time: dt.datetime) -> str | None:
    q = json.loads((ROOT / "queue.json").read_text()) if (ROOT / "queue.json").exists() else []
    for item in q:
        at = dt.datetime.fromisoformat(item["at"].replace("Z", "+00:00")).astimezone(TZ)
        if abs((at - slot_time).total_seconds()) < 90 * 60:
            return item["key"]
    return None


def make(kind: str, today: dt.date) -> tuple[str, Path] | None:
    from indigo_meta.metrics import last_completed_week
    y, w = last_completed_week(today)
    if kind in ("carte", "matchup", "anteprima", "italiani", "stagione"):
        if kind == "anteprima":          # serve il Meta Report per i «mazzi da battere»
            py("run_weekly.py", "--no-telegram", "--no-deck", "--year", str(y), "--week", str(w))
        args = ["run_rubrica.py", kind] + (["--date", today.isoformat()] if kind == "anteprima" else ["--week", f"{y}-W{w:02d}"] if kind in ("carte", "matchup") else [])
        r = py(*args, ok=(0, 3))
        key = r.stdout.strip().splitlines()[-1] if r.returncode == 0 else ""
        return (key, ROOT / "output" / key) if key else None
    if kind == "cityleague":
        py("run_weekly.py", "--no-telegram", "--year", str(y), "--week", str(w))
        monday = dt.date.fromisocalendar(y, w, 1)
        py("run_cityleague.py", "--no-telegram", "--start", monday.isoformat())
        src = ROOT / "output" / f"{y}-W{w:02d}-cityleague"
        return (f"cityleague-{y}-W{w:02d}", src) if list(src.glob("slide_*.png")) else None
    if kind in ("lente", "lente2"):
        py("run_weekly.py", "--no-telegram", "--spotlight", "--year", str(y), "--week", str(w))
        src = ROOT / "output" / f"{y}-W{w:02d}-{kind}"
        return (f"{kind}-{y}-W{w:02d}", src) if list(src.glob("slide_*.png")) else None
    raise ValueError(kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", help="es. gio-18")
    ap.add_argument("--ignore-queue", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now(TZ)
    if a.slot:
        day, hour = a.slot.split("-")
        hour = int(hour)
    else:
        day = DAYS[now.weekday()]
        hour = 12 if 10 <= now.hour < 15 else 18 if 16 <= now.hour < 21 else -1
    kind = PLAN.get((day, hour))
    key = ""
    if not kind:
        print(f"Nessuna rubrica per {day} {hour}")
    else:
        slot_time = now.replace(hour=hour, minute=30, second=0, microsecond=0)
        busy = None if a.ignore_queue else queue_busy(slot_time)
        if busy:
            print(f"Slot {day} {hour}:30 già occupato dalla coda ({busy}): non genero nulla")
        else:
            if kind == "italiani-stagione":       # a settimane alterne
                kind = "italiani" if now.isocalendar()[1] % 2 == 0 else "stagione"
            made = make(kind, now.date())
            if made:
                key, src = made
                from indigo_meta.instagram import to_jpeg
                dst = ROOT / "_site" / key
                to_jpeg(sorted(src.glob("slide_*.png")), dst)
                shutil.copy(src / "caption.txt", dst / "caption.txt")
                (ROOT / "_site" / "index.html").write_text("<!doctype html><title>Indigo Meta</title><p>Indigo Meta</p>")
                print(f"Pronto: {key} ({len(list(dst.glob('*.jpg')))} slide)")
            else:
                print(f"{kind}: niente da pubblicare questa settimana")
    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"key={key}\n")


if __name__ == "__main__":
    main()
