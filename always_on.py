#!/usr/bin/env python3
"""Pubblicatore sempre acceso. GitHub può saltare o ritardare di ore i workflow programmati ogni pochi minuti,
quindi questo processo resta attivo ~55 minuti: ogni minuto aggiorna la coda dal repository, legge i pulsanti
Telegram e pubblica i post in scadenza. Alla fine rilancia se stesso (workflow_dispatch)."""
import os
import subprocess
import time
import traceback

import requests

import publish_queue
import tg_buttons

LIFETIME = 55 * 60
start = time.time()
while time.time() - start < LIFETIME:
    try:
        subprocess.run(["git", "pull", "-q", "--rebase"], check=False)   # nuove voci in coda (watcher, modifiche)
        tg_buttons.main()
        publish_queue.check()
    except Exception:
        traceback.print_exc()
    time.sleep(60)

repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
if repo and token:
    r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/always-on.yml/dispatches",
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                      json={"ref": "main"}, timeout=30)
    print("Rilancio:", r.status_code)
