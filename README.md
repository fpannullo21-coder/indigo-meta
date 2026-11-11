# Indigo Meta

Report settimanale del meta Pokémon TCG Standard, in italiano, generato in automatico.

Ogni lunedì la pipeline:
1. scarica da Limitless i tornei Standard della settimana precedente con almeno 32 giocatori
   (più quelli della settimana prima, per i trend);
2. calcola meta share, presenza in top 8, conversion rate, win rate, tier list, tornei vinti
   e il meta dei giocatori italiani;
3. genera le slide PNG 1080×1350 (formato 4:5 per Instagram e TikTok) e la caption,
   compresa la **Lista della settimana**: la lista vincente del torneo più grande, con le carte
   ufficiali in italiano (TCGdex, poi Limitless; inglese solo se l'italiano non esiste);
4. ti manda l'anteprima su Telegram. Tu controlli e pubblichi.

## Avvio in locale

```bash
pip install -r requirements.txt
python -m playwright install chromium
python run_weekly.py                    # ultima settimana completa
python run_weekly.py --week 45          # una settimana precisa
python run_weekly.py --min-players 64   # solo tornei più grandi
```

L'output finisce in `output/<anno>-W<settimana>/`: `slide_01…08.png`, `caption.txt`, `report.json`, `carousel.html`.

## Automazione su GitHub (gratis)

1. Crea un repository privato e carica questa cartella.
2. In **Settings → Secrets and variables → Actions** aggiungi (sono tutti facoltativi):
   - `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` per ricevere l'anteprima: crea il bot con @BotFather,
     scrivigli un messaggio, poi leggi la chat id da `https://api.telegram.org/bot<TOKEN>/getUpdates`;
   - `LIMITLESS_API_KEY` quando Limitless approva la richiesta (servono limiti più alti, non è obbligatoria);
   - `ANTHROPIC_API_KEY` se vuoi che Claude aggiunga un'apertura alla caption.
3. Il workflow `.github/workflows/weekly.yml` parte ogni lunedì alle 07:17 italiane.
   Puoi lanciarlo a mano dal tab **Actions → Run workflow**.
   Slide e caption si scaricano anche dagli artifact della run.

## Le regole del report

| Metrica | Definizione |
|---|---|
| Meta share | liste di un archetipo / liste totali |
| Top 8 share | posti in top 8 di un archetipo / posti in top 8 totali |
| Conversion | top 8 / liste di quell'archetipo (la media è la linea tratteggiata) |
| Tier | Tier 1 ≥ 8% dei posti in top 8, Tier 2 ≥ 5%, Tier 3 ≥ 2,5% (minimo 20 liste) |
| Trend | differenza di meta share, in punti percentuali, rispetto alla settimana prima |
| Meta Italia | liste dei giocatori con bandiera IT (slide mostrata solo con almeno 50 giocatori) |

Gli archetipi sono quelli assegnati automaticamente da Limitless. I tornei senza liste vengono scartati.
Le soglie si cambiano in `indigo_meta/metrics.py` (`TIER_CUTS`) e in `run_weekly.py`.

**Limite da dichiarare:** l'API copre i tornei su Play Limitless, che sono quasi tutti online.
Il meta dei tornei dal vivo può essere diverso, ed è scritto nella slide finale.

## Struttura

```
run_weekly.py              punto di ingresso
indigo_meta/limitless.py   client API (rate limit + cache su disco)
indigo_meta/metrics.py     calcolo delle metriche
indigo_meta/render.py      HTML → PNG con Playwright
indigo_meta/cards.py       carte della lista: nomi e immagini in italiano (TCGdex), prezzo indicativo
indigo_meta/caption.py     caption italiana (con Claude facoltativo)
data/tcgdex_setmap.json    sigle dei set → id TCGdex (aggiornato in automatico a ogni esecuzione)
indigo_meta/telegram.py    anteprima per l'approvazione
templates/                 template delle slide + font (Inter, Space Grotesk – licenza OFL)
```

Per cambiare grafica modifica `templates/carousel.html.j2`: i colori sono le variabili CSS in cima al file.

**Immagini delle carte:** usale solo nella slide della lista, con la nota © già presente, e nei contenuti gratuiti.
Il costo indicativo del mazzo (trend Cardmarket via TCGdex) compare solo se è noto il prezzo di almeno il 95% delle carte.

Dati: [Limitless TCG](https://limitlesstcg.com). Citali sempre come fonte.
