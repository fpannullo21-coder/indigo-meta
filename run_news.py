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
    if im.get("src"):
        im["src"] = (A / im["src"]).as_uri()
out = ROOT / "output" / n["key"]
out.mkdir(parents=True, exist_ok=True)
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
(out / "news.html").write_text(env.get_template("news.html.j2").render(n=n), encoding="utf-8")
slides = render_png(out / "news.html", out)
(out / "caption.txt").write_text(n["caption"], encoding="utf-8")
print(f"{len(slides)} slide in {out}")
