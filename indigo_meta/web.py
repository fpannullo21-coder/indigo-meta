"""Download educato di pagine pubbliche (Limitless, Limitless Labs) con cache su disco.

Una richiesta al secondo al massimo, user agent che si identifica, cache di 7 giorni:
i risultati dei tornei conclusi non cambiano, quindi ogni pagina si scarica una volta sola.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

UA = {"User-Agent": "IndigoMeta/0.1 (Italian Pokémon TCG coverage; credits Limitless TCG)"}
_last = [0.0]


def get(url: str, cache_dir: Path, max_age_h: float = 24 * 7) -> str:
    cache_dir = Path(cache_dir) / "web"
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if f.exists() and time.time() - f.stat().st_mtime < max_age_h * 3600:
        return f.read_text(encoding="utf-8")
    wait = 1.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=40)
            _last[0] = time.time()
            r.raise_for_status()
            text = r.content.decode("utf-8", "replace")   # questi siti sono in UTF-8 anche senza dichiararlo
            f.write_text(text, encoding="utf-8")
            return text
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(url)
