#!/usr/bin/env python3
"""Aggiorna data/tcgdex_setmap.json (sigla ufficiale del set → id TCGdex).
Da lanciare quando esce una nuova espansione. Richiede git."""
import glob, json, os, re, subprocess, tempfile
from pathlib import Path

out = Path(__file__).resolve().parent.parent / "data" / "tcgdex_setmap.json"
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse",
                    "https://github.com/tcgdex/cards-database.git", tmp], check=True)
    subprocess.run(["git", "-C", tmp, "sparse-checkout", "set", "data"], check=True)
    m = {}
    for f in glob.glob(f"{tmp}/data/*/*.ts"):
        if os.path.basename(os.path.dirname(f)) == "Pokémon TCG Pocket":
            continue
        s = open(f, encoding="utf-8").read()
        ab = re.search(r'abbreviations:\s*{[^}]*official:\s*["\']([^"\']+)', s)
        i = re.search(r'\bid:\s*["\']([^"\']+)', s)
        if ab and i:
            m.setdefault(ab.group(1), i.group(1))
out.write_text(json.dumps(m, indent=1, sort_keys=True))
print(f"{len(m)} set salvati in {out}")
