#!/usr/bin/env python3
"""Converte le slide PNG appena generate in JPEG (Instagram accetta solo JPEG) e le mette in _site/
per GitHub Pages. Stampa il nome della cartella pubblicata."""
import shutil
import sys
from pathlib import Path

from indigo_meta.instagram import to_jpeg

dirs = [d for d in Path("output").iterdir() if d.is_dir() and list(d.glob("slide_*.png"))]
if not dirs:
    sys.exit("Nessuna slide da pubblicare")
src = max(dirs, key=lambda d: d.stat().st_mtime)
dst = Path("_site") / src.name
to_jpeg(sorted(src.glob("slide_*.png")), dst)
if (src / "caption.txt").exists():
    shutil.copy(src / "caption.txt", dst / "caption.txt")
(Path("_site") / "index.html").write_text("<!doctype html><title>Indigo Meta</title><p>Indigo Meta — immagini per Instagram.</p>")
print(src.name)
