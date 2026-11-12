#!/usr/bin/env python3
"""Indigo Meta — radar news: segnala su Telegram le nuove notizie sul Pokémon TCG."""
from pathlib import Path
from indigo_meta.radar import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parent / "cache" / "radar_seen.json")
