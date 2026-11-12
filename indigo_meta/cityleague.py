"""Report settimanale delle City League giapponesi (fonte: limitlesstcg.com/tournaments/jp).

Per ogni torneo della settimana: mazzo vincitore e mazzi in top 16. Gli archetipi sono ricavati
dalle icone dei Pokémon che Limitless associa a ogni lista (es. dragapult + dudunsparce).
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .web import get

BASE = "https://limitlesstcg.com"


ALIASES = {"Zoroark": "N's Zoroark", "Ogerpon Hydrapple": "Ogerpon Meganium Hydrapple"}


def deck_name(icons: list[str]) -> str:
    name = _deck_name(icons)
    return ALIASES.get(name, name)


def _deck_name(icons: list[str]) -> str:
    def one(slug: str) -> str:
        parts = slug.split("-")
        mega = "mega" in parts
        parts = [p for p in parts if p != "mega"]
        name = " ".join(p.capitalize() for p in parts)
        return ("Mega " if mega else "") + name
    return " ".join(one(i) for i in icons) if icons else "Altro"


@dataclass
class CLTournament:
    url: str
    date: dt.date
    prefecture: str
    winner: str
    placings: list[tuple[int, str]]   # (posizione, archetipo)


def week_tournaments(start: dt.date, end: dt.date, cache: Path, fetch_pages: bool = True) -> list[CLTournament]:
    page = get(f"{BASE}/tournaments/jp?show=100", cache, max_age_h=6)
    out = []
    for m in re.finditer(r'<tr data-date="([^"]+)" data-city="([^"]*)" data-shop="[^"]*" data-winner="([^"]*)">'
                         r'.*?href="(https://limitlesstcg\.com/tournaments/jp/\d+)"', page, re.S):
        d = dt.date.fromisoformat(m.group(1))
        if not (start <= d <= end):
            continue
        winner = deck_name(m.group(3).split())
        placings = []
        if fetch_pages:
            tp = get(m.group(4), cache)
            for row in re.findall(r"<tr>\s*<td>(\d+)</td>(.*?)</tr>", tp, re.S):
                icons = re.findall(r'class="pokemon"[^>]*alt="([^"]+)"', row[1]) or \
                        re.findall(r'alt="([^"]+)"[^>]*class="pokemon"', row[1])
                placings.append((int(row[0]), deck_name(icons)))
        out.append(CLTournament(m.group(4), d, m.group(2), winner, placings))
    return out


def summarize(ts: list[CLTournament]) -> dict:
    wins = Counter(t.winner for t in ts)
    top16 = Counter(a for t in ts for _, a in t.placings)
    top4 = Counter(a for t in ts for p, a in t.placings if p <= 4)
    slots16 = sum(len(t.placings) for t in ts)
    return {"n": len(ts), "wins": wins.most_common(), "top16": top16.most_common(), "top4": top4.most_common(),
            "slots16": slots16, "prefectures": len({t.prefecture for t in ts})}
