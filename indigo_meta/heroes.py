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


def deck_heroes(names: list[str], n: int = 3) -> list[dict]:
    """Carte simbolo dei primi mazzi della lista, senza ripetere la stessa carta: [{src, name, deck}]."""
    ms = _mascots(names[: n * 3])
    out, seen = [], set()
    for name in names:
        c = ms.get(name)
        if not c or c.get("name") in seen:
            continue
        seen.add(c.get("name"))
        out.append({"src": c.get("src"), "name": c.get("name", name), "deck": name})
        if len(out) == n:
            break
    return out


def deck_hero(name: str) -> dict | None:
    h = deck_heroes([name], 1)
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
