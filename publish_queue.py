#!/usr/bin/env python3
"""Coda di pubblicazione: pubblica su Instagram i post di queue.json quando arriva il loro orario.

Ogni voce: {"at": "<ora UTC ISO>", "key": "<cartella su GitHub Pages>"}. Condivide lo stato con i pulsanti
Telegram (cache/tg_state.json), quindi un post non esce mai due volte, comunque venga pubblicato.
"""
import datetime as dt
import json
from pathlib import Path

from indigo_meta.instagram import InstagramError
from tg_buttons import STATE, publish, say

state = json.loads(STATE.read_text()) if STATE.exists() else {"offset": 0, "published": []}
now = dt.datetime.now(dt.timezone.utc)
for item in json.loads(Path("queue.json").read_text()):
    when = dt.datetime.fromisoformat(item["at"].replace("Z", "+00:00"))
    key = item["key"]
    if when > now or key in state["published"]:
        continue
    if now - when > dt.timedelta(days=2):              # troppo vecchio: le slide potrebbero non esserci più
        print(f"Saltato (scaduto): {key}")
        continue
    say(f"⏰ Dalla coda: pubblico «{key}»…")
    state["published"].append(key)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))
    try:
        publish(key)
    except InstagramError:
        state["published"].remove(key)
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text(json.dumps(state))
print("Coda controllata.")
