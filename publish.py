#!/usr/bin/env python3
"""Pubblica su Instagram le slide già generate e caricate su GitHub Pages.

Uso (dentro il workflow, dopo il deploy di Pages):
  python publish.py --dir output/2026-W45 --base-url https://<utente>.github.io/indigo-meta/2026-W45

Controlli prima di pubblicare (se uno fallisce non pubblica e avvisa su Telegram):
- da 2 a 10 slide, tutte presenti e non vuote;
- caption presente;
- token e ID Instagram validi.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

from indigo_meta.instagram import Instagram, InstagramError, wait_public


def tg(text: str) -> None:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text}, timeout=30)
    print(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="cartella con slide_XX.jpg e caption.txt")
    ap.add_argument("--base-url", required=True, help="indirizzo pubblico della stessa cartella")
    ap.add_argument("--dry-run", action="store_true", help="fa i controlli ma non pubblica")
    a = ap.parse_args()

    d = Path(a.dir)
    jpgs = sorted(d.glob("slide_*.jpg"))
    cap_file = d / "caption.txt"
    problems = []
    if not 2 <= len(jpgs) <= 10:
        problems.append(f"numero di slide non valido ({len(jpgs)})")
    if any(f.stat().st_size < 20_000 for f in jpgs):
        problems.append("una slide sembra vuota")
    caption = cap_file.read_text(encoding="utf-8").strip() if cap_file.exists() else ""
    if not caption:
        problems.append("caption mancante")
    if problems:
        tg("⛔ Indigo Meta: pubblicazione bloccata — " + "; ".join(problems) + f" ({d.name})")
        sys.exit(1)

    urls = [f"{a.base_url.rstrip('/')}/{f.name}" for f in jpgs]
    try:
        ig = Instagram()
        user = ig.check()
        if a.dry_run:
            tg(f"🧪 Prova Instagram riuscita: collegato a @{user}, {len(urls)} slide pronte ({d.name}). Nessuna pubblicazione.")
            return
        wait_public(urls)
        link = ig.publish_carousel(urls, caption)
        tg(f"✅ Pubblicato su Instagram ({d.name}): {link}")
    except InstagramError as e:
        tg(f"⛔ Indigo Meta: pubblicazione Instagram non riuscita ({d.name}) — {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
