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


def ace_specs(raw_cards: list) -> set[str]:
    """Nomi inglesi degli assi tattici (ACE SPEC) della lista: elenco in data/ace_spec.json più la rarità su TCGdex.
    Un mazzo ne può giocare uno solo, quindi di norma è una carta."""
    known = {n.lower() for n in json.loads((ROOT / "data" / "ace_spec.json").read_text(encoding="utf-8"))}
    out = {c.name_en for c in raw_cards if c.name_en.lower() in known}
    if not os.getenv("INDIGO_OFFLINE"):
        try:
            from .cards import TCGdex, SETMAP, API
            tc = TCGdex(ROOT / "cache")
            for c in raw_cards:
                if c.section == "pokemon" or c.name_en in out or not SETMAP.get(c.set_code):
                    continue
                card = tc._find("en", SETMAP[c.set_code], c.number)
                det = tc._json(f"{API}/en/cards/{card['id']}", f"card_en_{card['id']}.json") if card else None
                if det and "ace" in str(det.get("rarity", "")).lower():
                    out.add(c.name_en)
        except Exception as e:
            print(f"  (controllo assi tattici su TCGdex saltato: {e})")
    return out


def _ask_claude(deck: dict, raw_cards: list, sp, avg_conv: float, aces: set[str] = frozenset()) -> dict | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or os.getenv("INDIGO_OFFLINE"):
        return None
    from .cards import TCGdex
    tc = TCGdex(ROOT / "cache")
    righe = []
    for c in raw_cards:
        txt = _card_text(tc, c.set_code, c.number)
        righe.append(f"- {c.count}x {c.name} (inglese: {c.name_en}; {c.section}"
                     + ("; ASSO TATTICO / ACE SPEC" if c.name_en in aces else "") + ")" + (f" — {txt}" if txt else ""))
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
- Asso tattico (ACE SPEC): {("la lista gioca " + ", ".join(sorted(aces)) + ": deve essere una delle 4 carte, con ruolo ASSO TATTICO, e va spiegato quando conviene giocarlo") if aces else "questa lista non ne gioca"}.
  Il ruolo ASSO TATTICO vale solo per quella carta, mai per le altre.
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


def _validate(data: dict, deck: dict, raw_cards: list, aces: set[str] = frozenset()) -> dict | None:
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
        if rc.name_en in aces:
            ruolo = "ASSO TATTICO"                      # l'asso tattico si chiama sempre così…
        elif ruolo == "ASSO TATTICO":
            ruolo = "CARTA CHIAVE"                      # …e nessun'altra carta può esserlo
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
    aces = ace_specs(raw_cards)
    if manual.exists():
        data = json.loads(manual.read_text(encoding="utf-8"))
        print(f"  Analisi a mano: {manual.name}")
    else:
        data = _ask_claude(deck, raw_cards, sp, avg_conv, aces)
    an = _validate(data, deck, raw_cards, aces) if data else None
    if an and aces and not any(k["role"] == "ASSO TATTICO" for pg in an["pages"] for k in pg):
        print(f"  ⚠️ L'analisi non parla dell'asso tattico della lista ({', '.join(sorted(aces))})")
    return an
