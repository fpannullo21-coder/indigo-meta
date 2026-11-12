"""Radar news: controlla le fonti e segnala su Telegram solo le notizie nuove sul Pokémon TCG.

Fonti:
- pokemon-card.com/info/  → news ufficiali giapponesi (nuovi set, carte rivelate, eventi)
- pocketmonsters.net/rss  → news internazionali, filtrate sul TCG
Lo stato (notizie già viste) è in cache/radar_seen.json. Alla prima esecuzione segna tutto come
già visto senza inviare nulla, per non riempirti Telegram di notizie vecchie.
"""
from __future__ import annotations

import html
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import requests

UA = {"User-Agent": "IndigoMeta-Radar/0.1 (Italian Pokémon TCG news alerts)"}
JP_URL = "https://www.pokemon-card.com/info/"
PM_URL = "https://www.pocketmonsters.net/rss"
JP_LABELS = {"商品": "🛍 Prodotti", "キャンペーン": "🎁 Campagne", "イベント": "🏆 Eventi", "コラム": "📝 Rubriche"}
TCG_WORDS = re.compile(r"\b(TCG|Trading Card|Card Game|Pokémon Card|Booster|Elite Trainer|Expansion|Promo card|"
                       r"Play! Pokémon|League Cup|Regional|World Championships?|Championship Series)\b", re.I)
SKIP_WORDS = re.compile(r"TCG Pocket|Pokémon GO|Pokémon Sleep|Pokémon UNITE|Champions\b", re.I)


@dataclass
class Item:
    id: str
    source: str
    title: str
    url: str
    tag: str = ""
    date: str = ""


def fetch_japan() -> list[Item]:
    r = requests.get(JP_URL, headers=UA, timeout=30)
    r.raise_for_status()
    page = r.content.decode("utf-8", "replace")
    start = page.find('id="newsTab_all"')
    page = page[start:] if start >= 0 else page
    end = page.find('id="newsTab_', 20)
    page = page[:end] if end > 0 else page
    out = []
    for m in re.finditer(r'<a class="List_item_inner" href="([^"]+)".*?</a>', page, re.S):
        block, href = m.group(0), m.group(1)
        label = re.search(r'Calendar_Label[^"]*">([^<]+)<', block)
        label = label.group(1).strip() if label else ""
        if label not in JP_LABELS:                      # "その他" = avvisi vari, li saltiamo
            continue
        body = re.search(r'Calendar_Label[^>]*>[^<]*</div>(.*?)<span', block, re.S)
        title = html.unescape(re.sub(r"<[^>]+>", "", body.group(1))).strip() if body else ""
        date = re.search(r"(\d{4}\.\d{1,2}\.\d{1,2})", block)
        url = requests.compat.urljoin(JP_URL, href)
        if title:
            out.append(Item(f"jp:{url}:{title[:40]}", "Pokémon Card Game (JP, ufficiale)", title, url,
                            JP_LABELS[label], date.group(1) if date else ""))
    return out


# Feed RSS: (nome, url, etichetta, categorie che contano, categorie da escludere).
# Se il feed non ha categorie, si filtra sul titolo con TCG_WORDS.
FEEDS = [
    ("PocketMonsters.net", "https://www.pocketmonsters.net/rss", "🌍 Internazionale", None, None),
    ("Pokémon Millennium", "https://www.pokemonmillennium.net/feed/", "🇮🇹 Italia",
     {"GCC Pokémon", "Carte Pokémon", "espansioni", "espansione giapponese", "Carte", "Carte promozionali"},
     {"GCC Pokémon Pocket"}),
    ("Pokémon Blog", "https://pokemonblog.com/feed/", "🇬🇧 Inglese",
     {"Pokemon TCG", "TCG", "Pokemon Trading Card Game"}, {"Pokémon TCG Pocket", "TCG Pocket"}),
]


def fetch_feed(name: str, url: str, tag: str, include: set | None, exclude: set | None) -> list[Item]:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        cats = {(c.text or "").strip() for c in it.findall("category")}
        if include is not None:
            if not (cats & include) or (exclude and cats & exclude) or SKIP_WORDS.search(title):
                continue
        elif not TCG_WORDS.search(title) or SKIP_WORDS.search(title):
            continue
        out.append(Item(f"{name}:{it.findtext('guid') or link}", name, title, link, tag,
                        (it.findtext("pubDate") or "")[:16]))
    return out


def fetch_pocketmonsters() -> list[Item]:
    r = requests.get(PM_URL, headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        if not TCG_WORDS.search(title) or SKIP_WORDS.search(title):
            continue
        out.append(Item(f"pm:{it.findtext('guid') or link}", "PocketMonsters.net", title, link, "🌍 Internazionale",
                        (it.findtext("pubDate") or "")[:16]))
    return out


def translate(items: list[Item]) -> dict[str, str]:
    """Titoli giapponesi/inglesi → italiano con Claude, se c'è la chiave. Altrimenti niente."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or not items:
        return {}
    numbered = "\n".join(f"{i + 1}. {it.title}" for i, it in enumerate(items))
    prompt = ("Traduci in italiano questi titoli di notizie sul Pokémon TCG. Mantieni i nomi propri e i nomi dei set "
              "come sono (se un set giapponese ha un nome in katakana, scrivilo in caratteri latini). Non aggiungere "
              "informazioni. Rispondi solo con le righe numerate, nello stesso ordine.\n\n" + numbered)
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=60,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                          json={"model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
                                "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        lines = r.json()["content"][0]["text"].strip().splitlines()
        res = {}
        for line in lines:
            m = re.match(r"\s*(\d+)\.\s*(.+)", line)
            if m and 0 < int(m.group(1)) <= len(items):
                res[items[int(m.group(1)) - 1].id] = m.group(2).strip()
        return res
    except Exception as e:
        print(f"  traduzione non disponibile: {e}")
        return {}


def send(text: str) -> None:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("Telegram non configurato. Messaggio:\n" + text)
        return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                  data={"chat_id": chat, "text": text, "disable_web_page_preview": "false"}).raise_for_status()


def run(state_file: Path) -> None:
    state = json.loads(state_file.read_text()) if state_file.exists() else None
    if isinstance(state, list):                        # formato vecchio: solo gli id
        state = {"ids": state, "sources": ["Pokémon Card Game (JP, ufficiale)", "PocketMonsters.net"]}
    first_run = state is None
    state = state or {"ids": [], "sources": []}
    seen, known_sources = set(state["ids"]), set(state["sources"])

    sources = [("Pokémon Card Game (JP, ufficiale)", fetch_japan)]
    sources += [(f[0], (lambda f=f: fetch_feed(*f))) for f in FEEDS]
    items, errors, fresh_sources = [], [], []
    for name, fn in sources:
        try:
            got = fn()
            print(f"{name}: {len(got)} notizie TCG")
            if name not in known_sources:              # fonte appena aggiunta: niente arretrati
                seen |= {i.id for i in got}
                known_sources.add(name)
                fresh_sources.append(name)
            items += got
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"  errore {name}: {e}")

    def save():
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"ids": sorted(seen | {i.id for i in items})[-3000:],
                                          "sources": sorted(known_sources)}))

    if first_run or fresh_sources:
        names = ", ".join(fresh_sources)
        send(f"📡 Radar Indigo Meta: nuove fonti attive → {names}.\nTi scrivo qui appena esce una notizia nuova "
             f"sul TCG (le notizie già pubblicate non te le mando).")
    new = [i for i in items if i.id not in seen]
    if new:
        tr = translate(new)
        for it in reversed(new):
            lines = [f"📡 {it.tag} · {it.source}", "", tr.get(it.id, it.title)]
            if it.id in tr and tr[it.id] != it.title:
                lines.append(f"({it.title})")
            lines += ["", it.url]
            send("\n".join(lines))
        print(f"Inviate {len(new)} notizie nuove.")
    else:
        print("Nessuna notizia nuova.")
    save()
    if errors and not items:
        raise SystemExit("Nessuna fonte raggiungibile: " + "; ".join(errors))
