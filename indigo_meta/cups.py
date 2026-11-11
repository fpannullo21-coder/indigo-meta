"""League Cup TCG della settimana, raggruppate per regione (fonte: pokedata.ovh, dati dell'Event Locator).

Regole di raggruppamento:
- una regione con almeno SOLO_MIN Cup ha la sua sezione;
- le altre si uniscono nella loro macro-area (es. Piemonte + Liguria = Nord-Ovest);
- una macro-area con meno di MERGE_MIN Cup si unisce alla vicina indicata in MERGE_INTO.
"""
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
    return sorted(out, key=lambda c: c.when)


def group(cups: list[Cup]) -> list[tuple[str, list[Cup]]]:
    by_region: dict[str, list[Cup]] = {}
    for c in cups:
        by_region.setdefault(c.region, []).append(c)
    groups: dict[str, list[Cup]] = {}
    order: list[str] = []
    known = {r for _, rs in AREAS for r in rs}
    for area, regions in AREAS:
        rest = []
        for reg in regions:
            items = by_region.get(reg, [])
            if len(items) >= SOLO_MIN and area != reg:
                groups[reg] = items
                order.append(reg)
            else:
                rest += items
        if rest:
            groups[area] = rest
            order.append(area)
    unknown = [c for reg, items in by_region.items() if reg not in known for c in items]
    if unknown:
        groups["Altre"] = unknown
        order.append("Altre")
    # unisci le macro-aree troppo piccole
    changed = True
    while changed:
        changed = False
        for name in list(order):
            target = MERGE_INTO.get(name)
            if len(groups[name]) < MERGE_MIN and target in groups and target != name:
                merged = f"{target} e {name}" if order.index(target) < order.index(name) else f"{name} e {target}"
                groups[merged] = groups.pop(target) + groups.pop(name)
                i = min(order.index(target), order.index(name))
                order = [o for o in order if o not in (target, name)]
                order.insert(i, merged)
                changed = True
                break
    return [(n, sorted(groups[n], key=lambda c: c.when)) for n in order]


def paginate(groups: list[tuple[str, list[Cup]]], cap: int = 15) -> list[list[tuple[str, list[Cup]]]]:
    """Distribuisce le sezioni sulle slide: `cap` = righe per slide, titoli di sezione compresi."""
    pages, cur, n = [], [], 0
    for name, items in groups:
        while len(items) + 1 > cap:                   # sezione troppo lunga: la spezziamo
            if cur:
                pages.append(cur); cur, n = [], 0
            pages.append([(name, items[:cap - 1])])
            items = items[cap - 1:]
        if cur and n + len(items) + 1 > cap:
            pages.append(cur); cur, n = [], 0
        cur.append((name, items)); n += len(items) + 1
    if cur:
        pages.append(cur)
    return pages
