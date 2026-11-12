#!/usr/bin/env python3
"""Coda di pubblicazione: pubblica su Instagram i post di queue.json quando arriva il loro orario.

Ogni voce: {"at": "<ora UTC ISO>", "key": "<cartella su GitHub Pages>"}. Condivide lo stato con i pulsanti
Telegram (cache/tg_state.json), quindi un post non esce mai due volte, comunque venga pubblicato.
"""
import datetime as dt
import json
import os
from pathlib import Path

from indigo_meta.instagram import InstagramError
from tg_buttons import STATE, publish, say

def check() -> None:
    state = json.loads(STATE.read_text()) if STATE.exists() else {"offset": 0, "published": []}
    now = dt.datetime.now(dt.timezone.utc)
    pause = state.get("pause_until")
    if pause and dt.datetime.fromisoformat(pause) > now and os.getenv("IGNORE_PAUSE") != "true":
        return                                              # Instagram ha bloccato l'accesso: si riprova più tardi
    for item in json.loads(Path("queue.json").read_text()):
        when = dt.datetime.fromisoformat(item["at"].replace("Z", "+00:00"))
        key = item["key"]
        if when > now or key in state["published"]:
            continue
        if now - when > dt.timedelta(days=2):              # troppo vecchio: le slide potrebbero non esserci più
            continue
        say(f"⏰ Dalla coda: pubblico «{key}»…")
        state["published"].append(key)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state))
        try:
            publish(key)
            state.pop("pause_until", None)                  # l'accesso funziona di nuovo
        except InstagramError as e:
            state["published"].remove(key)
            if "blocked" in str(e).lower() or "(codice 200)" in str(e):
                state["pause_until"] = (now + dt.timedelta(hours=1)).isoformat()
                say("⏸️ Instagram ha bloccato l'accesso alle API: metto in pausa la coda e riprovo tra un'ora. "
                    "Controlla gli avvisi dell'app su developers.facebook.com.")
                break
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))


if __name__ == "__main__":
    check()
    print("Coda controllata.")
