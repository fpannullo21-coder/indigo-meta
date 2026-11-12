#!/usr/bin/env python3
"""Pubblicatore sempre acceso. GitHub può saltare o ritardare di ore i workflow programmati ogni pochi minuti,
quindi questo processo resta attivo ~55 minuti: ogni minuto aggiorna la coda dal repository, legge i pulsanti
Telegram e pubblica i post in scadenza. Alla fine rilancia se stesso (workflow_dispatch)."""
import datetime as dt
import json
import os
import subprocess
import time
import traceback
from zoneinfo import ZoneInfo

import requests

import publish_queue
import tg_buttons

LIFETIME = 55 * 60
TZ = ZoneInfo("Europe/Rome")
REPO, TOKEN = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
PUB = {"publish": "true"}
# (giorni: 0=lun … 6=dom, ore, minuto, workflow, input). Ora italiana: l'ora legale è gestita da sola.
PLAN = [
    ({0}, [12], 47, "weekly.yml", PUB),                                   # Meta Report
    ({1}, [12], 47, "cups.yml", PUB),                                     # League Cup
    ({2, 3, 4, 5, 6}, [12], 20, "rubriche.yml", PUB),                     # rubriche delle 12:30
    ({3, 4}, [18], 20, "rubriche.yml", PUB),                              # City League, Mazzo sotto la lente
    ({5, 6, 0}, list(range(24)), 50, "watch-majors.yml", {}),             # major appena conclusi
    ({1}, list(range(0, 24, 3)), 50, "watch-majors.yml", {}),
    (set(range(7)), list(range(24)), 0, "radar.yml", {}),                 # news
]


def dispatch(wf: str, inputs: dict) -> int:
    r = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/{wf}/dispatches",
                      headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
                      json={"ref": "main", "inputs": inputs}, timeout=30)
    print(f"Avvio {wf}: {r.status_code}", flush=True)
    return r.status_code


def scheduler() -> None:
    """Avvia i workflow del piano all'orario giusto (una volta per orario, entro 15 minuti)."""
    if not (REPO and TOKEN):
        return
    st = json.loads(tg_buttons.STATE.read_text()) if tg_buttons.STATE.exists() else {"offset": 0, "published": []}
    done = st.setdefault("dispatched", [])
    now = dt.datetime.now(TZ)
    for days, hours, minute, wf, inputs in PLAN:
        if now.weekday() not in days or now.hour not in hours:
            continue
        slot = now.replace(minute=minute, second=0, microsecond=0)
        if not (slot <= now < slot + dt.timedelta(minutes=15)):
            continue
        sid = f"{slot:%Y-%m-%dT%H:%M}|{wf}"
        if sid in done:
            continue
        if dispatch(wf, inputs) == 204:
            done.append(sid)
    st["dispatched"] = done[-300:]
    tg_buttons.STATE.parent.mkdir(parents=True, exist_ok=True)
    tg_buttons.STATE.write_text(json.dumps(st))


start = time.time()
while time.time() - start < LIFETIME:
    try:
        subprocess.run(["git", "pull", "-q", "--rebase"], check=False)   # nuove voci in coda (watcher, modifiche)
        tg_buttons.main()
        publish_queue.check()
        scheduler()
    except Exception:
        traceback.print_exc()
    time.sleep(60)

if REPO and TOKEN:
    dispatch("always-on.yml", {})
