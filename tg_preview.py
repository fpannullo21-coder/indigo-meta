#!/usr/bin/env python3
"""Anteprima su Telegram di una cartella di _site/: python tg_preview.py _site/<chiave> [--button]"""
import sys
from pathlib import Path

from indigo_meta.telegram import send_preview

d = Path(sys.argv[1])
caption = (d / "caption.txt").read_text(encoding="utf-8")
send_preview(sorted(d.glob("slide_*.jpg")), f"[Post {d.name}]\n\n" + caption,
             publish_key=d.name if "--button" in sys.argv else None)
