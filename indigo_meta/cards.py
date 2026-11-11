"""Carte di una lista → nomi e immagini ufficiali, in italiano quando possibile.

Ordine delle fonti per l'immagine:
  1. TCGdex in italiano            (assets.tcgdex.net)
  2. Limitless in italiano         (scansioni ufficiali; coprono anche le espansioni appena uscite
  3. Limitless in inglese           e le energie base)
  4. TCGdex in inglese
  5. riquadro con il nome (solo se la carta non esiste in nessuna fonte)
Le immagini vengono scaricate in cache/cards/ e usate in locale per il rendering.
Prezzo indicativo: trend Cardmarket fornito da TCGdex.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.tcgdex.net/v2"
LIMITLESS_IMG = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpci/{set}/{set}_{num:0>3}_R_{lang}_LG.png"
SETMAP = json.loads((ROOT / "data" / "tcgdex_setmap.json").read_text())

ENERGY_COLORS = {  # colore del riquadro di riserva per le energie base
    "Fire": "#E8623A", "Water": "#3B8FE0", "Grass": "#4CAF50", "Lightning": "#F2C230",
    "Psychic": "#A35BD6", "Fighting": "#B5652E", "Darkness": "#3A4150", "Metal": "#8C99A6",
}


@dataclass
class DeckCard:
    count: int
    name_en: str
    name: str            # nome italiano (o inglese se manca)
    section: str         # pokemon / trainer / energy
    set_code: str
    number: str
    remote: str | None   # URL immagine
    local: str | None    # file in cache
    price: float | None  # trend Cardmarket, EUR
    energy_color: str | None = None


class TCGdex:
    def __init__(self, cache_dir: Path, lang: str = "it"):
        self.lang = lang
        self.cache = Path(cache_dir)
        (self.cache / "tcgdex").mkdir(parents=True, exist_ok=True)
        (self.cache / "cards").mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "IndigoMeta/0.1"
        self._sets: dict = {}

    def _json(self, url: str, cache_name: str | None = None, max_age_h: float = 24 * 7):
        f = self.cache / "tcgdex" / cache_name if cache_name else None
        if f and f.exists() and time.time() - f.stat().st_mtime < max_age_h * 3600:
            return json.loads(f.read_text())
        for attempt in range(3):
            try:
                r = self.s.get(url, timeout=20)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                data = r.json()
                if f:
                    f.write_text(json.dumps(data))
                return data
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
        return None

    def _set(self, lang: str, set_id: str):
        key = (lang, set_id)
        if key not in self._sets:
            self._sets[key] = self._json(f"{API}/{lang}/sets/{set_id}", f"set_{lang}_{set_id}.json", 24)
        return self._sets[key]

    def _find(self, lang: str, set_id: str, number: str):
        s = self._set(lang, set_id)
        if not s:
            return None
        try:
            n = int(number)
        except ValueError:
            return next((c for c in s.get("cards", []) if c["localId"] == number), None)
        return next((c for c in s.get("cards", []) if c["localId"].isdigit() and int(c["localId"]) == n), None)

    def _download(self, url: str, name: str) -> str | None:
        """`url` è l'indirizzo completo dell'immagine; restituisce il file locale o None."""
        ext = url.rsplit(".", 1)[-1] if url.rsplit("/", 1)[-1].count(".") else "img"
        f = self.cache / "cards" / f"{name}.{ext}"
        if f.exists() and f.stat().st_size > 1000:
            return str(f)
        for attempt in range(3):
            try:
                r = self.s.get(url, timeout=30)
                if r.ok and len(r.content) > 1000:
                    f.write_bytes(r.content)
                    return str(f)
                if r.status_code == 404:
                    return None
            except requests.RequestException:
                pass
            time.sleep(1.5 * (attempt + 1))
        return None

    def resolve(self, c: dict, section: str, download: bool = True) -> DeckCard:
        set_id = SETMAP.get(c.get("set", ""))
        name_en = c["name"]
        name, remote, local, price, ecolor = name_en, None, None, None, None
        if section == "energy":
            for t, col in ENERGY_COLORS.items():
                if t.lower() in name_en.lower():
                    ecolor = col
        if set_id:
            card = self._find(self.lang, set_id, c.get("number", ""))
            if card:
                name = card.get("name") or name_en
                if card.get("image"):
                    remote = card["image"] + "/high.webp"
                det = self._json(f"{API}/{self.lang}/cards/{card['id']}", f"card_{self.lang}_{card['id']}.json")
                try:
                    price = det["variants_detailed"][0]["pricing"]["cardmarket"]["trend"]
                except (TypeError, KeyError, IndexError):
                    price = None
        candidates = [remote] if remote else []
        code, num = c.get("set", ""), c.get("number", "")
        if code and num.isdigit():
            candidates += [LIMITLESS_IMG.format(set=code, num=num, lang=self.lang.upper()),
                           LIMITLESS_IMG.format(set=code, num=num, lang="EN")]
        if set_id and self.lang != "en":
            en = self._find("en", set_id, num)
            if en and en.get("image"):
                candidates.append(en["image"] + "/high.webp")
        remote = None
        for url in candidates:
            if not download:
                remote = url
                break
            key = url.split("://", 1)[-1].replace("/", "_").rsplit(".", 1)[0]
            local = self._download(url, key)
            if local:
                remote = url
                break
        return DeckCard(c["count"], name_en, name, section, c.get("set", ""), c.get("number", ""),
                        remote, local, price, ecolor)


def resolve_decklist(decklist: dict, cache_dir: Path, download: bool = True) -> list[DeckCard]:
    """Unisce le stampe diverse della stessa carta (stesso nome) e risolve immagini e nomi."""
    tc = TCGdex(cache_dir)
    out: list[DeckCard] = []
    for section in ("pokemon", "trainer", "energy"):
        merged: dict[str, dict] = {}
        for c in decklist.get(section, []):
            if c["name"] in merged:
                merged[c["name"]]["count"] += c["count"]
            else:
                merged[c["name"]] = dict(c)
        for c in merged.values():
            out.append(tc.resolve(c, section, download))
    return out


def deck_price(cards: list[DeckCard]) -> tuple[float | None, float]:
    """Prezzo indicativo del mazzo e quota di carte (sul totale di 60) con prezzo noto."""
    total = sum(c.count for c in cards)
    priced = [c for c in cards if c.price is not None]
    cov = sum(c.count for c in priced) / total if total else 0
    return (sum(c.count * c.price for c in priced) if priced else None, cov)


def as_dicts(cards: list[DeckCard]) -> list[dict]:
    return [asdict(c) for c in cards]
