"""«I mazzi dei campioni»: top 8 di un major (Regional, Special, Internazionale) con profilo del campione
e liste dei primi quattro. Fonti: limitlesstcg.com (classifica, mazzi, liste) e labs.limitlesstcg.com
(record, OPW%, percorso nella top cut). Solo divisione Masters (giocatori adulti).
"""
from __future__ import annotations

import html as H
import re
from dataclasses import dataclass, field
from pathlib import Path

from .web import get

BASE = "https://limitlesstcg.com"
LABS = "https://labs.limitlesstcg.com"

COUNTRIES = {
    "IT": "Italia", "US": "Stati Uniti", "CA": "Canada", "MX": "Messico", "BR": "Brasile", "AR": "Argentina",
    "CL": "Cile", "PE": "Perù", "CO": "Colombia", "GB": "Regno Unito", "DE": "Germania", "FR": "Francia",
    "ES": "Spagna", "PT": "Portogallo", "NL": "Paesi Bassi", "BE": "Belgio", "CH": "Svizzera", "AT": "Austria",
    "PL": "Polonia", "CZ": "Rep. Ceca", "SK": "Slovacchia", "HU": "Ungheria", "SE": "Svezia", "NO": "Norvegia",
    "FI": "Finlandia", "DK": "Danimarca", "IE": "Irlanda", "JP": "Giappone", "KR": "Corea del Sud",
    "AU": "Australia", "NZ": "Nuova Zelanda", "SG": "Singapore", "MY": "Malesia", "PH": "Filippine",
    "ID": "Indonesia", "TW": "Taiwan", "HK": "Hong Kong", "CN": "Cina", "TH": "Thailandia", "UA": "Ucraina",
    "RO": "Romania", "GR": "Grecia", "HR": "Croazia", "SI": "Slovenia", "RS": "Serbia", "TR": "Turchia",
    "LT": "Lituania", "LV": "Lettonia", "EE": "Estonia", "IS": "Islanda", "SV": "El Salvador", "CR": "Costa Rica",
    "GT": "Guatemala", "PA": "Panama", "PR": "Porto Rico", "EC": "Ecuador", "UY": "Uruguay", "VE": "Venezuela",
    "ZA": "Sudafrica", "MT": "Malta", "CY": "Cipro", "LU": "Lussemburgo", "BG": "Bulgaria", "BY": "Bielorussia", "IL": "Israele", "AE": "Emirati Arabi",
}
ROUND_NAMES = {1: "Finale", 2: "Semifinale", 3: "Quarti", 4: "Ottavi"}


def flag(cc: str) -> str:
    """Codice ISO a 2 lettere → bandiera emoji (🇮🇹). Vuoto se il codice non è valido."""
    cc = (cc or "").upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc)


def country(code: str) -> str:
    return COUNTRIES.get(code, code)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


@dataclass
class Player:
    place: int
    name: str
    cc: str
    deck: str
    record: str = ""
    points: str = ""
    opw: str = ""
    labs_url: str = ""
    decklist: dict | None = None
    price_eur: str = ""
    path: list = field(default_factory=list)   # top cut: [(fase, avversario, mazzo avversario, esito)]

    @property
    def country(self) -> str:
        return country(self.cc)

    @property
    def flag(self) -> str:
        return flag(self.cc)


@dataclass
class Major:
    tid: int
    name: str
    date: str
    players: int
    labs: str
    top: list[Player]


def parse_decklists(page: str, n: int) -> list[tuple[str, dict, str]]:
    """Prime n liste della pagina /decklists: (titolo «1st Nome», decklist, prezzo €)."""
    out = []
    for block in page.split('<div class="tournament-decklist">')[1:n + 1]:
        title = clean(re.search(r'data-toggle[^>]*>(.*?)</div>', block, re.S).group(1))
        price = re.search(r'card-price eur[^>]*>([^<]+)<', block)
        dl = {"pokemon": [], "trainer": [], "energy": []}
        main = block.split('data-text-decklist', 1)[-1]
        for col in main.split('decklist-column-heading')[1:]:
            head = clean(col[:80].split("</div>")[0].split(">", 1)[-1]).lower()
            sec = "pokemon" if head.startswith("pok") else "trainer" if head.startswith("trainer") else "energy"
            for c in re.finditer(r'data-set="([^"]*)" data-number="([^"]*)".*?card-count">(\d+)<.*?card-name">([^<]+)<',
                                 col, re.S):
                dl[sec].append({"set": c.group(1), "number": c.group(2), "count": int(c.group(3)),
                                "name": H.unescape(c.group(4)).strip()})
        out.append((title, dl, clean(price.group(1)) if price else ""))
    return out


def load(tid: int, cache: Path, top_n: int = 8, lists: int = 4) -> Major:
    page = get(f"{BASE}/tournaments/{tid}", cache)
    name = clean(re.search(r"<title>(.*?)(?:–|\|)", page, re.S).group(1))
    name = re.sub(r",\s*[A-Z]{2}$", "", name)          # «Regional Louisville, KY» → «Regional Louisville»
    info = clean(re.search(r'class="infobox-line">(.*?)</div>', page, re.S).group(1)) if 'infobox-line' in page else ""
    date = re.search(r"\d{1,2}(?:st|nd|rd|th) \w+ \d{4}", info)
    players = re.search(r"(\d[\d,]*) Players", info)
    labs = re.search(r'labs\.limitlesstcg\.com/(\d{4})', page)
    rows = re.findall(r'<tr data-rank="(\d+)" data-name="([^"]*)" data-country="([^"]*)" data-deck="([^"]*)"', page)
    top = [Player(int(r), H.unescape(n), c, H.unescape(d)) for r, n, c, d in rows[:top_n]]

    # record, punti, OPW e link al giocatore da Limitless Labs
    if labs:
        lp = re.sub(r"<!--.*?-->", "", get(f"{LABS}/{labs.group(1)}/standings", cache), flags=re.S)
        for m in re.finditer(r'<td>(\d+)</td><td><a href="(/\d{4}/player/\d+)">([^<]+)</a>.*?</td><td>(\d+)</td>'
                             r'<td class="whitespace-nowrap">([\d\s-]+)', lp, re.S):
            place = int(m.group(1))
            for p in top:
                if p.place == place:
                    p.labs_url, p.points, p.record = LABS + m.group(2), m.group(4), re.sub(r"\s+", "", m.group(5))
                    opw = re.search(r"([\d.]+)%", lp[m.end():m.end() + 200])
                    p.opw = opw.group(1) + "%" if opw else ""
    # liste dei primi `lists`
    dpage = get(f"{BASE}/tournaments/{tid}/decklists", cache)
    for (title, dl, price), p in zip(parse_decklists(dpage, lists), top):
        p.decklist, p.price_eur = dl, price
    # percorso del campione nella top cut
    if top and top[0].labs_url:
        rp = re.sub(r"<!--.*?-->", "", get(top[0].labs_url, cache), flags=re.S)
        rounds = re.findall(r'<td[^>]*>(\d+)</td><td[^>]*>(Win|Loss|Tie)</td><td[^>]*><a[^>]*>([^<]+)</a>', rp)
        cut = {1: 1, 2: 2, 4: 3, 8: 3, 16: 4}.get(top_n, 3)
        names = {p.name.lower(): p for p in top}
        for i, (rnd, res, opp) in enumerate(rounds[:cut]):          # la pagina elenca dal turno più recente
            o = names.get(opp.strip().lower())
            top[0].path.append((ROUND_NAMES.get(i + 1, f"Turno {rnd}"), opp.strip(), o.deck if o else "",
                                {"Win": "V", "Loss": "S", "Tie": "P"}[res], flag(o.cc) if o else ""))
        top[0].path.reverse()
    return Major(tid, name, date.group(0) if date else "", int(players.group(1).replace(",", "")) if players else 0,
                 labs.group(1) if labs else "", top)
