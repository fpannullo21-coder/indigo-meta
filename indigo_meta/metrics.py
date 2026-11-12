"""Calcolo delle metriche settimanali: meta share, top 8, conversion, win rate, tier, trend."""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field, asdict

from .limitless import Limitless, parse_date

OTHER_IDS = {"other", None}


@dataclass
class DeckStats:
    id: str
    name: str
    entries: int = 0
    top8: int = 0
    wins: int = 0            # tornei vinti
    mw: int = 0              # partite vinte
    ml: int = 0
    mt: int = 0
    it_entries: int = 0      # giocatori con bandiera IT
    share: float = 0.0
    top8_share: float = 0.0
    conversion: float = 0.0
    winrate: float = 0.0
    it_share: float = 0.0
    prev_share: float | None = None
    delta: float | None = None   # punti percentuali vs settimana precedente
    tier: str | None = None
    best_list: dict | None = None   # lista meglio piazzata della settimana


@dataclass
class WeekReport:
    week: int
    year: int
    start: str
    end: str
    tournaments: int
    players: int
    top8_slots: int
    it_players: int
    min_players: int
    decks: list[DeckStats] = field(default_factory=list)
    winners: list[dict] = field(default_factory=list)
    prev_tournaments: int = 0
    prev_players: int = 0

    def to_dict(self):
        return asdict(self)


def iso_week_bounds(year: int, week: int):
    start = dt.datetime.fromisocalendar(year, week, 1).replace(tzinfo=dt.timezone.utc)
    return start, start + dt.timedelta(days=7)


def last_completed_week(today: dt.date | None = None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    d = today - dt.timedelta(days=7)
    y, w, _ = d.isocalendar()
    return y, w


def _aggregate(api: Limitless, start, end, min_players: int):
    ts = [t for t in api.tournaments_between(start, end) if t["players"] >= min_players]
    ts.sort(key=lambda t: t["date"])
    now = dt.datetime.now(dt.timezone.utc)
    decks: dict[str, DeckStats] = {}
    players = top8_slots = it_players = used = 0
    winners = []
    for i, t in enumerate(ts, 1):
        api._log(f"  [{i}/{len(ts)}] {t['name']} ({t['players']} giocatori)")
        recent = now - parse_date(t["date"]) < dt.timedelta(days=2)
        st = api.standings(t["id"], cacheable=not recent)
        with_deck = [p for p in st if p.get("deck")]
        if len(with_deck) < 0.8 * len(st):   # torneo senza liste: inutile per il meta
            continue
        used += 1
        for p in with_deck:
            d = p["deck"]
            ds = decks.setdefault(d["id"], DeckStats(d["id"], d["name"]))
            ds.entries += 1
            players += 1
            rec = p.get("record") or {}
            ds.mw += rec.get("wins", 0)
            ds.ml += rec.get("losses", 0)
            ds.mt += rec.get("ties", 0)
            if p.get("country") == "IT":
                ds.it_entries += 1
                it_players += 1
            pl = p.get("placing")
            if pl and p.get("decklist"):
                cand = {"deck": d["name"], "placing": pl, "tournament": t["name"], "players": t["players"],
                        "player": p.get("name"), "record": p.get("record"), "decklist": p.get("decklist")}
                cur = ds.best_list
                if cur is None or (pl, -t["players"]) < (cur["placing"], -cur["players"]):
                    ds.best_list = cand
            if pl and pl <= 8:
                ds.top8 += 1
                top8_slots += 1
            if pl == 1:
                ds.wins += 1
                winners.append({"tournament": t["name"], "players": t["players"],
                                "deck": d["name"], "player": p.get("name"),
                                "record": p.get("record"), "decklist": p.get("decklist"),
                                "date": t["date"]})
    return decks, used, players, top8_slots, it_players, winners


TIER_CUTS = {"1": 8.0, "2": 5.0, "3": 2.5}   # % minima dei posti in top 8


def build_report(api: Limitless, year: int, week: int, min_players: int = 32,
                 min_entries: int = 20, tier_cuts: dict | None = None) -> WeekReport:
    tier_cuts = tier_cuts or TIER_CUTS
    start, end = iso_week_bounds(year, week)
    api._log(f"Settimana {week}/{year}: {start.date()} → {(end - dt.timedelta(days=1)).date()}")
    decks, n_t, players, slots, it_players, winners = _aggregate(api, start, end, min_players)

    py, pw, _ = (start - dt.timedelta(days=7)).isocalendar()
    ps, pe = iso_week_bounds(py, pw)
    api._log(f"Settimana precedente {pw}/{py} (per i trend)")
    prev, pn_t, pplayers, *_ = _aggregate(api, ps, pe, min_players)

    for d in decks.values():
        d.share = d.entries / players if players else 0
        d.top8_share = d.top8 / slots if slots else 0
        d.conversion = d.top8 / d.entries if d.entries else 0
        games = d.mw + d.ml + d.mt
        d.winrate = d.mw / games if games else 0
        d.it_share = d.it_entries / it_players if it_players else 0
        if d.id in prev and pplayers:
            d.prev_share = prev[d.id].entries / pplayers
            d.delta = (d.share - d.prev_share) * 100
        elif pplayers:
            d.prev_share = 0.0
            d.delta = d.share * 100
        # Tier basato sulla presenza nelle top 8 (risultati, non popolarità)
        if d.id not in OTHER_IDS and d.entries >= min_entries:
            for t in ("1", "2", "3"):
                if d.top8_share * 100 >= tier_cuts[t]:
                    d.tier = t
                    break

    ordered = sorted(decks.values(), key=lambda d: d.entries, reverse=True)
    return WeekReport(week=week, year=year, start=start.date().isoformat(),
                      end=(end - dt.timedelta(days=1)).date().isoformat(),
                      tournaments=n_t, players=players, top8_slots=slots,
                      it_players=it_players, min_players=min_players,
                      decks=ordered, winners=winners,
                      prev_tournaments=pn_t, prev_players=pplayers)
