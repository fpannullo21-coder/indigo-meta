#!/usr/bin/env python3
"""Diagnosi dell'accesso a Instagram: stato del token, dell'app e del limite di pubblicazione. Risultato su Telegram."""
import json
import os

import requests

from indigo_meta.instagram import API_VERSION

TOKEN, UID = os.environ["IG_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
host = "graph.instagram.com" if TOKEN.startswith("IG") else "graph.facebook.com"
base = f"https://{host}/{API_VERSION}"


def call(path, **params):
    r = requests.get(f"{base}/{path}", params={"access_token": TOKEN, **params}, timeout=30)
    try:
        return r.json()
    except ValueError:
        return {"http": r.status_code, "text": r.text[:200]}


out = {
    "account": call(UID, fields="username,media_count"),
    "limite_pubblicazione": call(f"{UID}/content_publishing_limit", fields="config,quota_usage"),
}
if host == "graph.facebook.com":
    dbg = call("debug_token", input_token=TOKEN).get("data", {})
    out["token"] = {k: dbg.get(k) for k in ("app_id", "application", "type", "is_valid", "expires_at", "scopes", "error")}
    if dbg.get("app_id"):
        out["app"] = call(dbg["app_id"], fields="name,link")
text = json.dumps(out, ensure_ascii=False, indent=1)
print(text)
if os.getenv("QUIET") == "true":                     # controllo quotidiano: scrive solo se c'è un problema
    import time
    exp = (out.get("token") or {}).get("expires_at") or 0
    days = (exp - time.time()) / 86400 if exp else 999
    blocked = "error" in out["account"]
    if not blocked and days > 7:
        raise SystemExit(0)
    text = ("⛔ Instagram rifiuta il token: rigeneralo (Tool di esplorazione → Estendi token → secret IG_ACCESS_TOKEN)."
            if blocked else
            f"⏳ Il token di Instagram scade tra {days:.0f} giorni. Rigeneralo: Tool di esplorazione API Graph → Generate Access Token → "
            "developers.facebook.com/tools/debug/accesstoken → Estendi → aggiorna il secret IG_ACCESS_TOKEN su GitHub.")
requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
              data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": "🩺 Diagnosi Instagram\n\n" + text[:3800]}, timeout=30)
