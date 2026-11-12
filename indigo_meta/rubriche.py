"""Dati per le rubriche settimanali: carte più giocate, matchup, anteprima major, italiani nei major,
la stagione in numeri. Fonti: Limitless (API dei tornei online, limitlesstcg.com per i major)."""
from __future__ import annotations

import datetime as dt
import html as H
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .limitless import Limitless, parse_date
from .metrics import iso_week_bounds
from .web import get

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://limitlesstcg.com"
BASIC_ENERGY = re.compile(r"^(Basic )?\w+ Energy$")
SPECIAL_BASIC = {"Grass Energy", "Fire Energy", "Water Energy", "Lightning Energy", "Psychic Energy",
                 "Fighting Energy", "Darkness Energy", "Metal Energy"}
TYPE_LABEL = {"REG": "Regional", "SPE": "Special Event", "IC": "Internazionale", "WC": "Mondiali"}
COUNTRY_CC = {"Argentina": "AR", "Brasile": "BR", "Germania": "DE", "Regno Unito": "GB", "Italia": "IT",
              "Francia": "FR", "Spagna": "ES", "Stati Uniti": "US", "Messico": "MX", "Australia": "AU",
              "Nuova Zelanda": "NZ", "Perù": "PE", "Cile": "CL", "Colombia": "CO", "Polonia": "PL",
              "Rep. Ceca": "CZ", "Cechia": "CZ", "Paesi Bassi": "NL", "Belgio": "BE", "Canada": "CA",
              "Giappone": "JP", "Corea del Sud": "KR", "Singapore": "SG", "Austria": "AT", "Svezia": "SE",
              "Portogallo": "PT", "USA": "US", "Stati Uniti d'America": "US", "Brasil": "BR", "Inghilterra": "GB", "Cina": "CN", "Taiwan": "TW", "Hong Kong": "HK", "Malesia": "MY", "Indonesia": "ID", "Filippine": "PH", "Thailandia": "TH", "Danimarca": "DK", "Finlandia": "FI", "Norvegia": "NO", "Sudafrica": "ZA"}


# ---------------------------------------------------------------- tornei online della settimana
def week_top_lists(api: Limitless, year: int, week: int, min_players: int = 32, top: int = 8):
    """Liste dei primi `top` di ogni torneo online della settimana. Restituisce (liste, n_tornei)."""
    start, end = iso_week_bounds(year, week)
    now = dt.datetime.now(dt.timezone.utc)
    out, n = [], 0
    for t in api.tournaments_between(start, end):
        if t["players"] < min_players:
            continue
        st = api.standings(t["id"], cacheable=now - parse_date(t["date"]) > dt.timedelta(days=2))
        lists = [p for p in st if p.get("placing") and p["placing"] <= top and p.get("decklist") and p.get("deck")]
        if not lists:
            continue
        n += 1
        out += [dict(p, tournament=t["name"], tid=t["id"]) for p in lists]
    return out, n


def card_usage(lists: list[dict]) -> dict:
    """Per ogni carta: in quante liste compare (%) e quante copie in media. Esclude le Energie base."""
    n = len(lists)
    seen: dict[tuple, dict] = {}
    for p in lists:
        decks_with = set()
        for sec in ("pokemon", "trainer", "energy"):
            for c in p["decklist"].get(sec, []):
                if sec == "energy" and c["name"] in SPECIAL_BASIC | {f"Basic {x}" for x in SPECIAL_BASIC}:
                    continue
                key = (sec, c["name"])
                e = seen.setdefault(key, {"name": c["name"], "section": sec, "set": c.get("set", ""),
                                          "number": c.get("number", ""), "lists": 0, "copies": 0, "decks": Counter()})
                if key not in decks_with:
                    e["lists"] += 1
                    e["decks"][p["deck"]["id"]] += 1
                    decks_with.add(key)
                e["copies"] += c["count"]
    for e in seen.values():
        e["pct"] = e["lists"] / n if n else 0
        e["avg"] = e["copies"] / e["lists"] if e["lists"] else 0
        e["n_decks"] = len(e["decks"])
        e["main_share"] = max(e["decks"].values()) / e["lists"] if e["lists"] else 0   # quanto dipende da un mazzo solo
        del e["decks"]
    return {"n": n, "cards": sorted(seen.values(), key=lambda e: (-e["pct"], -e["avg"]))}


def matchups(api: Limitless, year: int, week: int, decks: list[str], min_players: int = 32,
             min_games: int = 15) -> dict:
    """Vittorie/sconfitte tra i mazzi indicati (id Limitless) nei tornei online della settimana."""
    start, end = iso_week_bounds(year, week)
    tally = defaultdict(lambda: [0, 0, 0])      # (a, b) -> [vinte da a, perse da a, pari]
    cache = api.cache / "pairings"
    cache.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    want = set(decks)
    for t in api.tournaments_between(start, end):
        if t["players"] < min_players:
            continue
        old = now - parse_date(t["date"]) > dt.timedelta(days=2)
        st = api.standings(t["id"], cacheable=old)
        deck_of = {p["player"]: p["deck"]["id"] for p in st if p.get("deck")}
        f = cache / f"{t['id']}.json"
        if f.exists():
            pairings = json.loads(f.read_text())
        else:
            pairings = api._get(f"/tournaments/{t['id']}/pairings")
            if old:
                f.write_text(json.dumps(pairings))
        for m in pairings:
            a, b = m.get("player1"), m.get("player2")
            if not b:
                continue
            da, db = deck_of.get(a), deck_of.get(b)
            if da not in want or db not in want or da == db:
                continue
            w = m.get("winner")
            if w == a:
                tally[(da, db)][0] += 1; tally[(db, da)][1] += 1
            elif w == b:
                tally[(da, db)][1] += 1; tally[(db, da)][0] += 1
            elif w == 0:
                tally[(da, db)][2] += 1; tally[(db, da)][2] += 1
    grid = {}
    for (a, b), (w, l, t) in tally.items():
        g = w + l + t
        grid[(a, b)] = {"games": g, "wr": (w + t / 2) / g if g else None, "ok": g >= min_games}
    return grid


# ---------------------------------------------------------------- major
def events() -> list[dict]:
    return json.loads((ROOT / "data" / "majors_2027.json").read_text())["events"]


def weekend_major(today: dt.date) -> dict | None:
    """Il major TCG che si gioca nel weekend successivo a `today` (venerdì → sabato/domenica)."""
    for e in events():
        s, en = dt.date.fromisoformat(e["start"]), dt.date.fromisoformat(e["end"])
        if today <= en and (s - today).days <= 3:
            return dict(e, cc=COUNTRY_CC.get(e["country"], ""), label=TYPE_LABEL.get(e["type"], e["type"]))
    return None


def next_majors(today: dt.date, n: int = 3) -> list[dict]:
    out = [dict(e, cc=COUNTRY_CC.get(e["country"], ""), label=TYPE_LABEL.get(e["type"], e["type"]))
           for e in events() if dt.date.fromisoformat(e["start"]) > today]
    return out[:n]


def completed_majors(cache: Path, max_age_h: float = 1) -> list[dict]:
    """Major conclusi su limitlesstcg.com/tournaments (TCG, Masters), dal più recente."""
    page = get(f"{BASE}/tournaments", cache, max_age_h=max_age_h)
    table = page[page.find("completed-tournaments"):]
    out = []
    for m in re.finditer(r'<tr data-date="([\d-]+)" data-country="(\w*)"\s+data-name="([^"]+)" data-format="(\w+)"\s+'
                         r'data-players="(\d+)" data-winner="([^"]*)">.*?href="/tournaments/(\d+)"', table, re.S):
        date, cc, name, fmt, players, winner, tid = m.groups()
        out.append({"tid": int(tid), "date": date, "cc": cc, "name": H.unescape(name), "format": fmt,
                    "players": int(players), "winner": H.unescape(winner)})
    return out


def major_players(tid: int, cache: Path) -> list[dict]:
    """Tutti i giocatori elencati nella pagina del torneo (in genere quelli del Day 2)."""
    page = get(f"{BASE}/tournaments/{tid}", cache)
    return [{"place": int(r), "name": H.unescape(n), "cc": c, "deck": H.unescape(d)}
            for r, n, c, d in re.findall(r'<tr data-rank="(\d+)" data-name="([^"]*)" data-country="(\w*)" data-deck="([^"]*)"', page)]


def majors_list() -> list[dict]:
    return json.loads((ROOT / "data" / "majors_ids.json").read_text())


def italians(cache: Path) -> list[dict]:
    """Per ogni major della stagione: italiani nella classifica pubblicata e il migliore."""
    out = []
    for e in majors_list():
        ps = major_players(e["tid"], cache)
        it = [p for p in ps if p["cc"] == "IT"]
        out.append({**e, "listed": len(ps), "italians": it, "best": it[0] if it else None})
    return out


def season(cache: Path) -> dict:
    """Vittorie e top 8 per mazzo, paesi più presenti in top 8, giocatori totali."""
    wins, top8, countries, players = Counter(), Counter(), Counter(), 0
    majors = []
    for e in majors_list():
        ps = major_players(e["tid"], cache)
        if not ps:
            continue
        majors.append(e)
        players += e.get("players", 0)
        wins[ps[0]["deck"]] += 1
        for p in ps[:8]:
            top8[p["deck"]] += 1
            countries[p["cc"]] += 1
    return {"majors": majors, "players": players, "wins": wins.most_common(), "top8": top8.most_common(),
            "countries": countries.most_common()}
