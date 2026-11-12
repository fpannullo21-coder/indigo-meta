#!/usr/bin/env python3
"""Ascolta i pulsanti del bot Telegram (ogni 5 minuti, da GitHub Actions).

"📤 Pubblica su Instagram" sotto un'anteprima → pubblica quelle slide, prese da GitHub Pages.
Accetta solo i tocchi che arrivano dalla tua chat (TELEGRAM_CHAT_ID) e non pubblica mai due volte
la stessa anteprima. Stato in cache/tg_state.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from indigo_meta.instagram import Instagram, InstagramError

STATE = Path("cache/tg_state.json")
TOKEN, CHAT = os.environ["TELEGRAM_BOT_TOKEN"], str(os.environ["TELEGRAM_CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"
PAGES = os.environ["PAGES_URL"].rstrip("/")


def say(text: str) -> None:
    print(text)                                     # resta anche nel log di GitHub
    requests.post(f"{API}/sendMessage", data={"chat_id": CHAT, "text": text}, timeout=30)


def ack(cb_id: str, text: str) -> None:
    try:
        requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cb_id, "text": text}, timeout=15)
    except requests.RequestException:
        pass   # tocco troppo vecchio per una risposta: pazienza, mandiamo comunque il messaggio


def slides_online(key: str) -> list[str]:
    urls = []
    for i in range(1, 11):
        u = f"{PAGES}/{key}/slide_{i:02d}.jpg"
        if requests.head(u, timeout=20).status_code != 200:
            break
        urls.append(u)
    return urls


def publish(key: str) -> None:
    urls = slides_online(key)
    cap = requests.get(f"{PAGES}/{key}/caption.txt", timeout=20)
    if len(urls) < 2 or cap.status_code != 200:
        say(f"⛔ Le slide di «{key}» non sono più online (nel frattempo è uscito un altro contenuto). "
            f"Rilancia il workflow da GitHub con «Pubblica davvero su Instagram».")
        return
    try:
        link = Instagram().publish_carousel(urls, cap.content.decode("utf-8"))
        say(f"✅ Pubblicato su Instagram ({key}): {link}")
    except InstagramError as e:
        say(f"⛔ Pubblicazione non riuscita ({key}) — {e}")
        raise


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {"offset": 0, "published": []}
    updates = requests.get(f"{API}/getUpdates", params={"offset": state["offset"] + 1 if state["offset"] else None,
                                                        "timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
                           timeout=30).json().get("result", [])
    for u in updates:
        state["offset"] = max(state["offset"], u["update_id"])
        cb = u.get("callback_query")
        if not cb or str(cb.get("from", {}).get("id")) != CHAT:
            continue
        data = cb.get("data", "")
        if not data.startswith("pub:"):
            continue
        key = data[4:]
        if key in state["published"]:
            ack(cb["id"], "Già pubblicato")
            continue
        ack(cb["id"], "Pubblicazione avviata…")
        say(f"⏳ Pubblico «{key}» su Instagram…")
        state["published"].append(key)              # segnato subito: niente doppioni anche se fallisce a metà
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state))
        try:
            publish(key)
        except InstagramError:
            state["published"].remove(key)          # fallito: si può riprovare
    state["published"] = state["published"][-200:]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))
    print(f"{len(updates)} aggiornamenti letti")


if __name__ == "__main__":
    main()
