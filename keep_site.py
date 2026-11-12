#!/usr/bin/env python3
"""Ogni pubblicazione su GitHub Pages sostituisce l'intero sito. Prima di caricarlo, questo script
riporta in _site/ i post che servono ancora, scaricandoli dal sito attuale:
  • i post in queue.json non ancora usciti (o in ritardo da meno di 2 giorni)
  • i post caricati negli ultimi 10 giorni (anteprime Telegram con il pulsante «Pubblica»)
Poi scrive _site/manifest.json con l'elenco dei file e la data di arrivo di ogni post."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests

BASE = os.getenv("PAGES_BASE", "https://fpannullo21-coder.github.io/indigo-meta/").rstrip("/") + "/"
SITE = Path("_site")
KEEP_DAYS = 10
now = dt.datetime.now(dt.timezone.utc)


def fetch(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=30)
        return r.content if r.status_code == 200 else None
    except requests.RequestException as e:
        print(f"  rete: {e}")
        return None


def guess_files(key: str) -> list[str]:
    """Se il vecchio sito non ha il manifest, prova slide_01.jpg, slide_02.jpg… finché esistono."""
    files = ["caption.txt"]
    for i in range(1, 21):
        name = f"slide_{i:02d}.jpg"
        try:
            if requests.head(BASE + f"{key}/{name}", timeout=30).status_code != 200:
                break
        except requests.RequestException:
            break
        files.append(name)
    return files if len(files) > 1 else []


def main():
    SITE.mkdir(exist_ok=True)
    raw = fetch(BASE + "manifest.json")
    old = json.loads(raw) if raw else {}
    keep = {}
    for e in json.loads(Path("queue.json").read_text()) if Path("queue.json").exists() else []:
        if dt.datetime.fromisoformat(e["at"].replace("Z", "+00:00")) >= now - dt.timedelta(days=2):
            keep[e["key"]] = "in coda"
    for key, info in old.items():
        if dt.datetime.fromisoformat(info["added"]) >= now - dt.timedelta(days=KEEP_DAYS):
            keep.setdefault(key, "recente")

    for key, why in keep.items():
        if (SITE / key).is_dir():
            continue                       # rigenerato in questo giro: vale la versione nuova
        files = old.get(key, {}).get("files") or guess_files(key)
        if not files:
            print(f"  ⚠️ {key} ({why}) non trovato sul sito attuale")
            continue
        got = 0
        for name in files:
            data = fetch(BASE + f"{key}/{name}")
            if data is not None:
                (SITE / key).mkdir(parents=True, exist_ok=True)
                (SITE / key / name).write_bytes(data)
                got += 1
        print(f"  conservato {key} ({why}, {got} file)")

    manifest = {}
    for d in sorted(p for p in SITE.iterdir() if p.is_dir()):
        manifest[d.name] = {"files": sorted(f.name for f in d.iterdir() if f.is_file()),
                            "added": old.get(d.name, {}).get("added") or now.isoformat(timespec="seconds")}
    (SITE / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"Sito: {len(manifest)} post")


if __name__ == "__main__":
    main()
