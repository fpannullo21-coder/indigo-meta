"""Invio dell'anteprima su Telegram per l'approvazione manuale.

Serve un bot (crealo con @BotFather) e la tua chat id.
Variabili: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Se mancano, il passaggio viene saltato.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests


def send_preview(slides: list[Path], caption: str, publish_key: str | None = None) -> bool:
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
    # La caption va a parte: Telegram limita le didascalie a 1024 caratteri.
    # Se la pubblicazione non è automatica, sotto c'è il pulsante "Pubblica su Instagram".
    auto = os.getenv("PUBLISH") == "true"
    head = ("✅ Anteprima Indigo Meta: esce in automatico su Instagram tra pochi minuti." if auto
            else "👀 Anteprima Indigo Meta pronta. Controlla le slide e, se va bene, premi Pubblica.")
    data = {"chat_id": chat, "text": head + "\n\n" + caption}
    if publish_key and not auto:
        data["reply_markup"] = json.dumps({"inline_keyboard": [[
            {"text": "📤 Pubblica su Instagram", "callback_data": f"pub:{publish_key}"}]]})
    requests.post(f"{api}/sendMessage", timeout=30, data=data).raise_for_status()
    return True
