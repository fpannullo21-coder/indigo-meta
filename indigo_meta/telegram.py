"""Invio dell'anteprima su Telegram per l'approvazione manuale.

Serve un bot (crealo con @BotFather) e la tua chat id.
Variabili: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Se mancano, il passaggio viene saltato.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests


def send_preview(slides: list[Path], caption: str) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("  Telegram non configurato: salto l'anteprima.")
        return False
    api = f"https://api.telegram.org/bot{token}"
    media, files = [], {}
    for i, p in enumerate(slides[:10]):
        files[f"f{i}"] = open(p, "rb")
        media.append({"type": "photo", "media": f"attach://f{i}"})
    r = requests.post(f"{api}/sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)},
                      files=files, timeout=120)
    for f in files.values():
        f.close()
    r.raise_for_status()
    # La caption va a parte: Telegram limita le didascalie a 1024 caratteri
    requests.post(f"{api}/sendMessage", timeout=30, data={
        "chat_id": chat,
        "text": "✅ Anteprima Indigo Meta pronta. Controlla le slide e pubblica.\n\n" + caption,
    }).raise_for_status()
    return True
