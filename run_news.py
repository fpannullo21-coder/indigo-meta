#!/usr/bin/env python3
"""News in 2 slide da un file di dati: python run_news.py data/news/hadou-seeker.json"""
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from indigo_meta.render import render_png

ROOT = Path(__file__).resolve().parent
n = json.loads(Path(sys.argv[1]).read_text())
A = (ROOT / n.get("assets", "assets")).resolve()
for im in n.get("images", []):
    if isinstance(im.get("card"), dict):                 # carta ufficiale (TCGdex / Limitless)
        from run_rubrica import card_images
        im["src"] = card_images([dict({"section": "pokemon"}, **im["card"])])[0].get("src")
    elif im.get("url"):                                  # immagine ufficiale da scaricare (es. foto stampa)
        dst = A / im.get("file", im["url"].split("?")[0].rsplit("/", 1)[-1])
        if not dst.exists():
            try:
                import requests
                r = requests.get(im["url"], timeout=60, headers={"User-Agent": "Mozilla/5.0 IndigoMeta"})
                r.raise_for_status()
                A.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(r.content)
            except Exception as e:
                print(f"  immagine non scaricata ({im['url']}): {e}")
        im["src"] = dst.as_uri() if dst.exists() else None
    elif im.get("src"):
        im["src"] = (A / im["src"]).as_uri()
for f in n.get("focus", []):
    f["src"] = (A / f["img"]).as_uri()
for c in (n.get("trainers") or {}).get("cards", []):
    c["src"] = (A / c["img"]).as_uri()
for c in (n.get("gallery") or {}).get("cards", []):
    from run_rubrica import card_images
    c["src"] = card_images([dict({"section": "pokemon"}, **c["card"])])[0].get("src")
out = ROOT / "output" / n["key"]
out.mkdir(parents=True, exist_ok=True)
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
(out / "news.html").write_text(env.get_template("news.html.j2").render(n=n), encoding="utf-8")
slides = render_png(out / "news.html", out)
(out / "caption.txt").write_text(n["caption"], encoding="utf-8")
print(f"{len(slides)} slide in {out}")
