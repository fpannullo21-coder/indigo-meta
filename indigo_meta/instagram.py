"""Pubblicazione di un carosello su Instagram (API ufficiale Graph).

Flusso: per ogni immagine un contenitore "carousel item" → un contenitore CAROUSEL con la caption
→ attesa che Meta finisca di elaborarlo → media_publish.
Le immagini devono essere JPEG raggiungibili da un indirizzo pubblico (qui: GitHub Pages).

Variabili: IG_ACCESS_TOKEN, IG_USER_ID.
Token che iniziano con "IGAA" usano graph.instagram.com, gli altri (es. "EAA") graph.facebook.com.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import requests

API_VERSION = "v23.0"


class InstagramError(RuntimeError):
    pass


def to_jpeg(pngs: list[Path], out_dir: Path) -> list[Path]:
    from PIL import Image
    out_dir.mkdir(parents=True, exist_ok=True)
    res = []
    for p in pngs:
        f = out_dir / (p.stem + ".jpg")
        Image.open(p).convert("RGB").save(f, "JPEG", quality=92, optimize=True, progressive=False)
        res.append(f)
    return res


def check_caption(caption: str) -> str:
    """Instagram: massimo 2.200 caratteri e 30 hashtag."""
    tags = re.findall(r"#\w+", caption)
    if len(tags) > 30:
        for t in tags[30:]:
            caption = caption.replace(t, "", 1)
    return caption[:2200].rstrip()


def wait_public(urls: list[str], timeout: int = 300) -> None:
    """Aspetta che GitHub Pages serva davvero le immagini prima di chiamare Instagram."""
    deadline = time.time() + timeout
    pending = list(urls)
    while pending and time.time() < deadline:
        pending = [u for u in pending if requests.head(u, timeout=20).status_code != 200]
        if pending:
            time.sleep(10)
    if pending:
        raise InstagramError(f"Immagini non ancora pubbliche: {pending[0]}")


class Instagram:
    def __init__(self, token: str | None = None, user_id: str | None = None):
        self.token = token or os.getenv("IG_ACCESS_TOKEN")
        self.user = user_id or os.getenv("IG_USER_ID")
        if not (self.token and self.user):
            raise InstagramError("IG_ACCESS_TOKEN o IG_USER_ID mancanti")
        host = "graph.instagram.com" if self.token.startswith("IG") else "graph.facebook.com"
        self.base = f"https://{host}/{API_VERSION}"

    def _call(self, method: str, path: str, **params):
        params["access_token"] = self.token
        r = requests.request(method, f"{self.base}/{path}", data=params if method == "POST" else None,
                             params=params if method == "GET" else None, timeout=60)
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramError(f"{err.get('message', r.text)} (codice {err.get('code')})")
        return data

    def _wait_ready(self, container_id: str, timeout: int = 300) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self._call("GET", container_id, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Contenitore {container_id} in stato {st}")
            time.sleep(5)
        raise InstagramError(f"Contenitore {container_id} non pronto dopo {timeout}s")

    def check(self) -> str:
        """Verifica che token e ID funzionino; restituisce lo username."""
        return self._call("GET", self.user, fields="username").get("username", "?")

    def publish_carousel(self, image_urls: list[str], caption: str) -> str:
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"Un carosello vuole da 2 a 10 immagini, qui {len(image_urls)}")
        children = []
        for url in image_urls:
            c = self._call("POST", f"{self.user}/media", image_url=url, is_carousel_item="true")["id"]
            children.append(c)
        for c in children:
            self._wait_ready(c)
        parent = self._call("POST", f"{self.user}/media", media_type="CAROUSEL",
                            children=",".join(children), caption=check_caption(caption))["id"]
        self._wait_ready(parent)
        media_id = self._call("POST", f"{self.user}/media_publish", creation_id=parent)["id"]
        link = self._call("GET", media_id, fields="permalink").get("permalink", "")
        return link
