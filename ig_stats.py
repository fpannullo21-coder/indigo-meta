#!/usr/bin/env python3
"""Andamento della pagina: follower, post e interazioni. Stampa un JSON nel log del workflow (dati già pubblici su Instagram)."""
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


out = {"account": call(UID, fields="username,followers_count,follows_count,media_count")}
media = call(f"{UID}/media", fields="id,caption,media_type,timestamp,like_count,comments_count,permalink", limit=40)
posts = []
for m in media.get("data", []):
    p = {k: m.get(k) for k in ("timestamp", "media_type", "like_count", "comments_count", "permalink")}
    p["titolo"] = (m.get("caption") or "").split("\n")[0][:70]
    ins = call(f"{m['id']}/insights", metric="reach,views,saved,shares,total_interactions")
    p["insights"] = {d["name"]: d["values"][0]["value"] for d in ins.get("data", [])} or ins.get("error", {}).get("message", "")[:90]
    posts.append(p)
out["post"] = posts
if "error" in media:
    out["errore_media"] = media["error"]
acc = call(f"{UID}/insights", metric="reach,follower_count", period="day")
out["account_insights"] = acc.get("data") or acc.get("error", {}).get("message", "")[:120]
print(json.dumps(out, ensure_ascii=False, indent=1))
