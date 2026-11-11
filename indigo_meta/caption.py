"""Caption italiana del post.

Di base è generata da template (deterministica: nessun numero inventato).
Se è impostata ANTHROPIC_API_KEY, Claude riscrive solo il tono dell'apertura,
con il vincolo di non aggiungere né cambiare dati.
"""
from __future__ import annotations

import os

import requests

from .render import pct, pp, num, dates_it


def template_caption(view: dict) -> str:
    r = view["r"]
    top, up = view["top"], view["biggest_up"]
    down = view["fallers"][0] if view["fallers"] else None
    best_conv = view["conv_top"][0] if view["conv_top"] else None
    t1 = ", ".join(d.name for d in view["tiers"]["1"]) or "nessuno sopra soglia"

    lines = [
        f"📊 META REPORT · Settimana {r.week} ({dates_it(r.start, r.end)})",
        "",
        f"{r.tournaments} tornei Standard, {num(r.players)} liste analizzate.",
        "",
    ]
    if down and down.id == top.id:
        lines.append(f"🥇 {top.name} resta il più giocato ({pct(top.share)}) ma perde {pp(down.delta)[1:]}")
        down = view["fallers"][1] if len(view["fallers"]) > 1 else None
    else:
        lines.append(f"🥇 Più giocato: {top.name} ({pct(top.share)})")
    if up:
        lines.append(f"📈 In crescita: {up.name} ({pp(up.delta)})")
    if down:
        lines.append(f"📉 In calo: {down.name} ({pp(down.delta)})")
    if best_conv:
        lines.append(f"🎯 Converte meglio: {best_conv.name} ({pct(best_conv.conversion)} in top 8)")
    lines += [
        f"🏆 Tier 1: {t1}",
        f"🔀 {view['winning_decks']} mazzi diversi hanno vinto almeno un torneo",
        "",
        "Tu cosa porti al prossimo torneo? Scrivilo nei commenti 👇",
        "",
        f"Dati: Limitless TCG · tornei online con almeno {r.min_players} giocatori.",
        "",
        "#pokemontcg #pokemontcgitalia #ptcg #metagame #tierlist #pokemontcglive #tcgitalia",
    ]
    return "\n".join(lines)


def polish_with_claude(caption: str) -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return caption
    prompt = (
        "Sei l'editor di Indigo Meta, pagina italiana sul Pokémon TCG competitivo. "
        "Riscrivi SOLO la prima riga di questa caption Instagram aggiungendo un gancio breve "
        "(max 12 parole) prima di essa. Non cambiare, aggiungere o togliere nessun numero, "
        "nome di mazzo o dato. Restituisci l'intera caption e nient'altro.\n\n" + caption
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 800,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        # salvaguardia: se Claude ha toccato i numeri, teniamo l'originale
        digits = lambda s: sorted(c for c in s if c.isdigit())
        return text if digits(text) == digits(caption) else caption
    except Exception as e:  # la caption non deve mai bloccare la pipeline
        print(f"  (Claude non disponibile, uso la caption base: {e})")
        return caption
