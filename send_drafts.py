#!/usr/bin/env python3
"""Manda su Telegram le anteprime delle bozze in _site/, ognuna con il pulsante «Pubblica su Instagram»."""
from pathlib import Path

from indigo_meta.telegram import send_preview

for d in sorted(p for p in Path("_site").iterdir() if p.is_dir()):
    caption = (d / "caption.txt").read_text(encoding="utf-8")
    send_preview(sorted(d.glob("slide_*.jpg")), f"[Post {d.name}]\n\n" + caption, publish_key=d.name)
    print("Anteprima inviata:", d.name)
