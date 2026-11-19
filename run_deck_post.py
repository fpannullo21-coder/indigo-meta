"""Post «Mazzo sotto la lente» su un archetipo scelto a mano, con numeri da più fonti.

    python run_deck_post.py data/posts/alakazam.json

Il file di configurazione dà copertina, slide dei numeri, caption e la lista da mostrare (torneo Limitless +
piazzamento). L'analisi delle carte è in data/spotlight/<analisi>.json. Uscita: output/<key>/ (slide + caption).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from indigo_meta.cards import resolve_decklist
from indigo_meta.champions import flag, load
from indigo_meta.render import build_deck
from indigo_meta.spotlight import analysis, render_post

ROOT = Path(__file__).resolve().parent
CATEGORY = "TCG Masters"


def main(cfg_path: str) -> Path:
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    src = cfg["lista"]
    m = load(src["tid"], ROOT / "cache", top_n=max(8, src["place"]), lists=max(8, src["place"]))
    p = next(x for x in m.top if x.place == src["place"])
    cards = resolve_decklist(p.decklist, ROOT / "cache")
    rec = dict(zip(("wins", "losses", "ties"), map(int, p.record.split("-")))) if p.record else {}
    deck = build_deck({"deck": p.deck, "tournament": m.name, "players": m.players, "player": p.name,
                       "record": rec, "placing": p.place}, cards)
    deck["kicker"] = f"{p.place}° posto · {m.name} {flag(src.get('cc', ''))} · {CATEGORY}".replace("  ", " ")
    deck["country"], deck["flag"] = p.country, p.flag
    if p.price_eur:                                     # stesso prezzo della caption: il totale indicato da Limitless
        import datetime as dt
        deck["price"] = f"{float(p.price_eur.replace('€', '').strip()):.0f} €"
        deck["price_note"] = (f"Costo: totale Cardmarket indicato da Limitless TCG ({dt.date.today():%d/%m/%Y}). "
                              "Solo carte singole, spedizione esclusa.")
    an = analysis(deck, cards, key=cfg["analisi"], only_key=True)
    if not an:
        sys.exit(f"Manca l'analisi data/spotlight/{cfg['analisi']}.json")
    out = ROOT / "output" / cfg["key"]
    slides = render_post(out, cfg["cover"], deck, an, cfg.get("handle", "@indigo.meta"), cfg.get("brand_right", ""))
    (out / "caption.txt").write_text(cfg["caption"], encoding="utf-8")
    print(f"{cfg['key']}: {len(slides)} slide in {out}")
    return out


if __name__ == "__main__":
    main(sys.argv[1])
