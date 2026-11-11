"""Client minimale per l'API pubblica di Limitless (play.limitlesstcg.com/api).

- Funziona senza chiave; se LIMITLESS_API_KEY è impostata la invia (limiti più alti).
- Rispetta il rate limit leggendo l'header `ratelimit` ("50-in-5min"; r=<rimaste>; t=<secondi al reset>).
- Mette in cache su disco le classifiche dei tornei conclusi: non cambiano più,
  quindi ogni settimana scarichiamo solo i tornei nuovi.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from pathlib import Path

import requests

BASE = "https://play.limitlesstcg.com/api"
UA = "IndigoMeta/0.1 (weekly Italian meta report; data: Limitless TCG)"


class Limitless:
    def __init__(self, cache_dir: str | Path = "cache", verbose: bool = True):
        self.cache = Path(cache_dir)
        (self.cache / "standings").mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        key = os.getenv("LIMITLESS_API_KEY")
        if key:
            self.s.headers["X-Access-Key"] = key
        self.verbose = verbose
        self.calls = 0

    def _log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def _get(self, path: str, params: dict | None = None):
        for attempt in range(5):
            r = self.s.get(f"{BASE}{path}", params=params, timeout=30)
            self.calls += 1
            remaining, reset = self._parse_ratelimit(r.headers.get("ratelimit", ""))
            if r.status_code == 429:
                wait = (reset or 60) + 2
                self._log(f"  rate limit raggiunto, attendo {wait}s…")
                time.sleep(wait)
                continue
            r.raise_for_status()
            if remaining is not None and remaining <= 1 and reset:
                self._log(f"  quota quasi esaurita, attendo {reset + 2}s…")
                time.sleep(reset + 2)
            return r.json()
        raise RuntimeError(f"Troppi tentativi falliti per {path}")

    @staticmethod
    def _parse_ratelimit(h: str):
        r = re.search(r"\br=(\d+)", h)
        t = re.search(r"\bt=(\d+)", h)
        return (int(r.group(1)) if r else None, int(t.group(1)) if t else None)

    def tournaments_between(self, start: dt.datetime, end: dt.datetime,
                            game: str = "PTCG", fmt: str = "STANDARD") -> list[dict]:
        """Tutti i tornei con data in [start, end). La lista è ordinata dal più recente."""
        out, page = [], 1
        while True:
            batch = self._get("/tournaments", {"game": game, "format": fmt,
                                               "limit": 100, "page": page})
            if not batch:
                break
            for t in batch:
                d = parse_date(t["date"])
                if start <= d < end:
                    out.append(t)
            if parse_date(batch[-1]["date"]) < start:
                break
            page += 1
        return out

    def standings(self, tid: str, cacheable: bool = True) -> list[dict]:
        """`cacheable=False` per tornei troppo recenti (potrebbero essere ancora in corso)."""
        f = self.cache / "standings" / f"{tid}.json"
        if f.exists():
            return json.loads(f.read_text())
        data = self._get(f"/tournaments/{tid}/standings")
        if cacheable:
            f.write_text(json.dumps(data))
        return data


def parse_date(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
