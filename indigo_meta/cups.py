"""League Cup TCG della settimana, una sezione per regione, in ordine di macro-area
(fonte: pokedata.ovh, dati dell'Event Locator Play! Pokémon)."""
from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass

import requests

EXPORT_URL = "https://www.pokedata.ovh/events/tocsv.php"
SOLO_MIN, MERGE_MIN = 4, 3

NORM = {
    "Lombardy": "Lombardia", "Piedmont": "Piemonte", "Tuscany": "Toscana", "Sicily": "Sicilia",
    "Apulia": "Puglia", "Sardinia": "Sardegna", "Sardigna/Sardegna": "Sardegna",
    "Aosta Valley": "Valle d'Aosta", "Friuli - Venezia Giulia": "Friuli-Venezia Giulia",
    "Trentino-Alto Adige/Sudtirol": "Trentino-Alto Adige", "Trentino-South Tyrol": "Trentino-Alto Adige",
}
# macro-aree in ordine geografico (nord → sud)
AREAS = [
    ("Nord-Ovest", ["Piemonte", "Valle d'Aosta", "Liguria"]),
    ("Lombardia", ["Lombardia"]),
    ("Nord-Est", ["Veneto", "Friuli-Venezia Giulia", "Trentino-Alto Adige"]),
    ("Emilia-Romagna", ["Emilia-Romagna"]),
    ("Toscana", ["Toscana"]),
    ("Centro", ["Lazio", "Umbria", "Marche", "Abruzzo", "Molise"]),
    ("Campania", ["Campania"]),
    ("Sud", ["Puglia", "Basilicata", "Calabria"]),
    ("Sicilia", ["Sicilia"]),
    ("Sardegna", ["Sardegna"]),
]
MERGE_INTO = {"Sardegna": "Sicilia", "Sicilia": "Sud", "Sud": "Campania", "Campania": "Sud",
              "Centro": "Toscana", "Toscana": "Centro", "Emilia-Romagna": "Toscana",
              "Nord-Est": "Lombardia", "Nord-Ovest": "Lombardia", "Lombardia": "Nord-Ovest"}
GIORNI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


@dataclass
class Cup:
    when: dt.datetime
    region: str
    city: str
    shop: str
    name: str
    url: str

    @property
    def day(self) -> str:
        return f"{GIORNI[self.when.weekday()]} {self.when.day}"

    @property
    def time(self) -> str:
        return self.when.strftime("%H:%M")


def download_csv(country: str = "IT") -> str:
    data = {"past": "false", "country": country, "city": "", "shop": "", "league": "", "states": "[]",
            "postcode": "", "cups": "true", "challenges": "false", "vcups": "false", "vchallenges": "false",
            "prereleases": "false", "premier": "false", "go": "false", "gocup": "false", "mss": "false",
            "ftcg": "false", "fvg": "false", "fgo": "false", "latitude": "", "longitude": "",
            "radius": "", "unit": "km"}
    r = requests.post(EXPORT_URL, data=data, timeout=60,
                      headers={"User-Agent": "IndigoMeta/0.1 (weekly Italian Pokémon TCG cups list)"})
    r.raise_for_status()
    return r.content.decode("utf-8-sig")


def parse(text: str, start: dt.date, end: dt.date) -> list[Cup]:
    """Solo League Cup TCG con data in [start, end]. Gli export filtrano male per tipo: filtriamo qui."""
    out, seen = [], set()
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        if row.get("type") != "League Cup":
            continue
        try:
            when = dt.datetime.strptime(row["when"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
        if not (start <= when.date() <= end):
            continue
        key = row.get("guid") or (row.get("shop"), row["when"])
        if key in seen:
            continue
        seen.add(key)
        out.append(Cup(when, NORM.get(row.get("state", ""), row.get("state", "")),
                       (row.get("city") or "").split(" / ")[0].strip(),
                       (row.get("shop") or "").strip(), (row.get("name") or "").strip(),
                       row.get("pokemon_url") or ""))
    return dedupe(sorted(out, key=lambda c: c.when))


def dedupe(cups: list[Cup]) -> list[Cup]:
    """Un negozio fa al massimo una League Cup TCG al giorno: se ne compaiono due, è quasi sempre
    lo stesso torneo registrato due volte. Teniamo la prima in ordine di orario."""
    out, seen = [], {}
    for c in cups:
        key = (c.shop.upper(), c.when.date())
        if key in seen:
            print(f"  doppione scartato: {c.shop} {c.when:%d/%m %H:%M} «{c.name}» (tengo «{seen[key].name}»)")
            continue
        seen[key] = c
        out.append(c)
    return out


def area_of(region: str) -> str:
    for area, regions in AREAS:
        if region in regions:
            return area
    return "Altre"


def group(cups: list[Cup]) -> list[tuple[str, list[Cup]]]:
    """Una sezione per regione, in ordine geografico (per macro-area, da nord a sud)."""
    by_region: dict[str, list[Cup]] = {}
    for c in cups:
        by_region.setdefault(c.region, []).append(c)
    order = [r for _, regions in AREAS for r in regions if r in by_region]
    order += sorted(r for r in by_region if r not in order)          # regioni non riconosciute in fondo
    return [(r, sorted(by_region[r], key=lambda c: c.when)) for r in order]


ROW_PX, HEAD_PX, PAGE_PX = 58, 80, 1080   # altezza riga, titolo regione, spazio utile per slide


def paginate(groups: list[tuple[str, list[Cup]]]) -> list[list[tuple[str, list[Cup]]]]:
    """Riempie ogni slide finché c'è spazio, senza spezzare una regione (salvo se non entra in una slide)."""
    per_page = (PAGE_PX - HEAD_PX) // ROW_PX
    pages, cur, used = [], [], 0
    for name, items in groups:
        while len(items) > per_page:
            if cur:
                pages.append(cur); cur, used = [], 0
            pages.append([(name, items[:per_page])])
            items = items[per_page:]
        h = HEAD_PX + ROW_PX * len(items)
        if cur and used + h > PAGE_PX:
            pages.append(cur); cur, used = [], 0
        cur.append((name, items)); used += h
    if cur:
        pages.append(cur)
    return pages
