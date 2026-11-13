"""«Mazzo sotto la lente» esteso: carte chiave con il loro ruolo e piano di gioco.

Fonti, in ordine:
  1. data/spotlight/<slug-del-mazzo>.json   testo scritto a mano (vince sempre)
  2. Claude (ANTHROPIC_API_KEY)             analisi dai testi ufficiali delle carte (TCGdex, in italiano)
  3. niente                                 il post esce nel formato corto (copertina + lista):
                                            meglio nessuna analisi che un'analisi inventata.

Formato JSON (lo stesso per il file a mano e per la risposta di Claude):
{
  "carte":  [{"carta": "<nome inglese come in lista>", "ruolo": "ATTACCANTE", "perche": "..."}],  # 2–4
  "piano":  [{"fase": "Primi turni", "testo": "..."}, ...],                                       # 3
  "forza":  ["...", "..."],                                                                       # 2
  "occhio": ["...", "..."]                                                                        # 2
}
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RUOLI = ["ATTACCANTE", "MOTORE", "CARTA CHIAVE", "ASSO TATTICO", "ENERGIA", "SUPPORTO", "TECH"]
LIMITI = {"perche": 190, "testo": 170, "punto": 90}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _card_text(tc, set_code: str, number: str) -> str:
    """Testo ufficiale della carta (abilità, attacchi, effetto) da TCGdex, in italiano se c'è."""
    from .cards import SETMAP, API
    set_id = SETMAP.get(set_code)
    if not set_id:
        return ""
    for lang in ("it", "en"):
        card = tc._find(lang, set_id, number)
        if not card:
            continue
        det = tc._json(f"{API}/{lang}/cards/{card['id']}", f"card_{lang}_{card['id']}.json") or {}
        parts = []
        if det.get("hp"):
            parts.append(f"{det.get('stage', '')} PS {det['hp']}".strip())
        for ab in det.get("abilities") or []:
            parts.append(f"Abilità «{ab.get('name')}»: {ab.get('effect', '')}")
        for at in det.get("attacks") or []:
            cost = "".join((x or "?")[0] for x in at.get("cost") or [])
            parts.append(f"Attacco «{at.get('name')}» [{cost}] {at.get('damage', '')}: {at.get('effect', '') or ''}".strip())
        if det.get("effect"):
            parts.append(det["effect"])
        if det.get("trainerType"):
            parts.insert(0, det["trainerType"])
        return " | ".join(p for p in parts if p)
    return ""


def _ask_claude(deck: dict, raw_cards: list, sp, avg_conv: float) -> dict | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or os.getenv("INDIGO_OFFLINE"):
        return None
    from .cards import TCGdex
    tc = TCGdex(ROOT / "cache")
    righe = []
    for c in raw_cards:
        txt = _card_text(tc, c.set_code, c.number)
        righe.append(f"- {c.count}x {c.name} (inglese: {c.name_en}; {c.section})" + (f" — {txt}" if txt else ""))
    numeri = (f"Meta share {sp.share:.1%}, {sp.top8} top 8 su {sp.entries} liste, "
              f"conversion {sp.conversion:.1%} (media {avg_conv:.1%}).") if sp else ""
    prompt = f"""Sei l'analista di Indigo Meta, pagina italiana sul Pokémon TCG competitivo (formato Standard).
Mazzo: {deck['name']} — lista {deck['place']}° su {deck['players']} giocatori ({deck['tournament']}). {numeri}

Lista con i testi ufficiali delle carte:
{chr(10).join(righe)}

Scrivi l'analisi del mazzo per un carosello Instagram. Regole:
- Usa SOLO quello che dicono i testi delle carte e la lista: non inventare effetti, danni o interazioni.
- Non citare matchup specifici né percentuali: non hai i dati.
- Nomi delle carte in italiano come nella lista. Frasi brevi, tono diretto, niente emoji, niente maiuscolo.
- "carte": 4 carte, le più importanti per capire il mazzo, in ordine di importanza. "carta" è il nome INGLESE.
  "ruolo" è uno di: {", ".join(RUOLI)}. "perche": max {LIMITI['perche']} caratteri, cosa fa nel mazzo.
- "piano": 3 fasi ("Primi turni", "Metà partita", "Chiusura"), "testo" max {LIMITI['testo']} caratteri.
- "forza" e "occhio": 2 punti ciascuno, max {LIMITI['punto']} caratteri (punti di forza / cosa lo mette in difficoltà).
Rispondi solo con il JSON:
{{"carte":[{{"carta":"","ruolo":"","perche":""}}],"piano":[{{"fase":"","testo":""}}],"forza":["",""],"occhio":["",""]}}"""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=90,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception as e:
        print(f"  (analisi Claude non disponibile: {e})")
        return None


def _clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def _validate(data: dict, deck: dict, raw_cards: list) -> dict | None:
    """Tiene solo carte presenti nella lista e testi entro i limiti; None se resta troppo poco."""
    by_en = {c.name_en.lower(): c for c in raw_cards}
    by_it = {c.name.lower(): c for c in raw_cards}
    imgs = {c["name"]: c for c in deck["cards"]}
    carte = []
    for k in data.get("carte") or []:
        nome = str(k.get("carta", "")).lower()
        rc = by_en.get(nome) or by_it.get(nome)
        if not rc or any(x["name"] == rc.name for x in carte):
            continue
        ruolo = str(k.get("ruolo", "")).upper().strip()
        carte.append(dict(name=rc.name, count=rc.count, role=ruolo if ruolo in RUOLI else "CARTA CHIAVE",
                          why=_clip(k.get("perche"), LIMITI["perche"]), src=imgs.get(rc.name, {}).get("src"),
                          section=imgs.get(rc.name, {}).get("section", "")))
    piano = [dict(fase=_clip(p.get("fase"), 24), testo=_clip(p.get("testo"), LIMITI["testo"]))
             for p in (data.get("piano") or [])[:3] if p.get("testo")]
    forza = [_clip(x, LIMITI["punto"]) for x in (data.get("forza") or [])[:2] if x]
    occhio = [_clip(x, LIMITI["punto"]) for x in (data.get("occhio") or [])[:2] if x]
    if len(carte) < 2:
        return None
    carte = carte[:4]
    return dict(pages=[carte[i:i + 2] for i in range(0, len(carte), 2)],
                piano=piano if len(piano) == 3 else [], forza=forza, occhio=occhio)


def analysis(deck: dict, raw_cards: list, sp=None, avg_conv: float = 0) -> dict | None:
    manual = ROOT / "data" / "spotlight" / f"{slug(deck['name'])}.json"
    data = None
    if manual.exists():
        data = json.loads(manual.read_text(encoding="utf-8"))
        print(f"  Analisi a mano: {manual.name}")
    else:
        data = _ask_claude(deck, raw_cards, sp, avg_conv)
    return _validate(data, deck, raw_cards) if data else None
