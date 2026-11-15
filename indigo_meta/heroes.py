"""Immagini per le copertine: la carta simbolo di un mazzo, dal nome dell'archetipo (es. «Dragapult Dudunsparce»).

Usa la stessa regola delle rubriche (run_rubrica.mascots): il Pokémon che dà il nome al mazzo, preso dalle liste
dei tornei online dell'ultima settimana completa, preferendo la versione ex. Immagini ufficiali delle carte.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mascots(names: list[str]) -> dict:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from run_rubrica import mascots
        return mascots(names)
    except Exception as e:
        print(f"  (carte simbolo non disponibili: {e})")
        return {}


def jp_image(set_code: str, number: str) -> str | None:
    """Immagine della stampa giapponese della stessa carta (per i post sulle City League).
    Dalla pagina della carta su Limitless TCG prende la prima voce «JP. Prints» (la stampa normale)
    e scarica l'immagine ufficiale giapponese dal CDN di Limitless."""
    import os
    import re
    if os.getenv("INDIGO_OFFLINE") or not (set_code and number):
        return None
    try:
        import requests
        from .web import get
        page = get(f"https://limitlesstcg.com/cards/{set_code}/{number}", ROOT / "cache", max_age_h=24 * 30)
        i = page.find("JP. Prints")
        m = re.search(r'href="/cards/jp/([^/"]+)/(\d+)"', page[i:]) if i >= 0 else None
        if not m:
            return None
        js, jn = m.group(1), m.group(2)
        dst = ROOT / "cache" / "cards" / f"jp_{js}_{jn}.png"
        if not dst.exists():
            r = requests.get(f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc/{js}/{js}_{jn}_R_JP_LG.png", timeout=40)
            r.raise_for_status()
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(r.content)
        return dst.resolve().as_uri()
    except Exception as e:
        print(f"  (stampa giapponese non trovata per {set_code} {number}: {e})")
        return None


def deck_heroes(names: list[str], n: int = 3, jp: bool = False) -> list[dict]:
    """Carte simbolo dei primi mazzi della lista, senza ripetere la stessa carta: [{src, name, deck}].
    jp=True usa la stampa giapponese (se non si trova, resta quella internazionale)."""
    ms = _mascots(names[: n * 3])
    out, seen = [], set()
    for name in names:
        c = ms.get(name)
        if not c or c.get("name") in seen:
            continue
        seen.add(c.get("name"))
        src = (jp and jp_image(c.get("set", ""), c.get("number", ""))) or c.get("src")
        out.append({"src": src, "name": c.get("name", name), "deck": name})
        if len(out) == n:
            break
    return out


def deck_hero(name: str, jp: bool = False) -> dict | None:
    h = deck_heroes([name], 1, jp=jp)
    return h[0] if h else None


def meta_heroes(n: int = 3) -> list[dict]:
    """Carte simbolo dei mazzi più giocati nell'ultimo Meta Report calcolato (tornei online)."""
    import json
    for rep in sorted((ROOT / "output").glob("20??-W??/report.json"), reverse=True):
        try:
            decks = json.loads(rep.read_text(encoding="utf-8"))["decks"]
        except Exception:
            continue
        names = [d["name"] for d in sorted(decks, key=lambda d: -d.get("share", 0))]
        return deck_heroes(names, n)
    return []
