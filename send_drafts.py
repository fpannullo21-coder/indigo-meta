#!/usr/bin/env python3
"""Manda su Telegram le anteprime delle bozze in _site/, ognuna con il pulsante «Pubblica su Instagram»."""
import os
from pathlib import Path

from indigo_meta.telegram import send_preview

only = {x.strip() for x in os.getenv("SEND_ONLY", "").split(",") if x.strip()}   # es. "news,carte-hadou-seeker"
for d in sorted(p for p in Path("_site").iterdir() if p.is_dir()):
    if only and not any(d.name == x or d.name.startswith(x + "-") or d.name.split("-")[0] == x for x in only):
        continue
    if not (d / "caption.txt").exists():
        continue
    caption = (d / "caption.txt").read_text(encoding="utf-8")
    if (d / "reel.mp4").exists():                        # reel: l'anteprima è il video
        import requests
        token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
        if token and chat:
            with open(d / "reel.mp4", "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendVideo", data={"chat_id": chat,
                              "caption": f"[Reel {d.name}]"}, files={"video": f}, timeout=300)
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                          data={"chat_id": chat, "text": f"🎬 Anteprima reel «{d.name}»\n\n{caption}"})
        print("Anteprima reel inviata:", d.name)
        continue
    send_preview(sorted(d.glob("slide_*.jpg")), f"[Post {d.name}]\n\n" + caption, publish_key=d.name)
    print("Anteprima inviata:", d.name)
