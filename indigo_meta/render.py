"""Dal report settimanale alle slide PNG (1080x1350, formato 4:5 Instagram/TikTok)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .metrics import WeekReport, DeckStats, OTHER_IDS, TIER_CUTS

ROOT = Path(__file__).resolve().parent.parent
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


# ---------- formattazione italiana ----------
def pct(x: float | None, nd: int = 1) -> str:
    if x is None:
        return "–"
    return f"{x * 100:.{nd}f}%".replace(".", ",")


def pp(x: float | None) -> str:
    if x is None:
        return "nuovo"
    sign = "+" if x > 0 else ("−" if x < 0 else "±")
    return f"{sign}{abs(x):.1f} pt".replace(".", ",")


def num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def dates_it(start: str, end: str) -> str:
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if a.month == b.month:
        return f"{a.day}–{b.day} {MESI[b.month - 1]} {b.year}"
    return f"{a.day} {MESI[a.month - 1]} – {b.day} {MESI[b.month - 1]} {b.year}"


def delta_html(d: float | None) -> Markup:
    if d is None:
        return Markup('<span class="delta flat">–</span>')
    if abs(d) < 0.05:
        return Markup('<span class="delta flat"><span class="ar">●</span>0,0 pt</span>')
    cls, ar = ("up", "▲") if d > 0 else ("down", "▼")
    return Markup(f'<span class="delta {cls}"><span class="ar">{ar}</span>{pp(d)}</span>')


# ---------- dati per le slide ----------
def build_view(r: WeekReport, handle: str = "@indigo.meta", min_entries: int = 20,
               conv_min: int = 40, tier_cuts: dict | None = None, deck: dict | None = None) -> dict:
    tier_cuts = tier_cuts or TIER_CUTS
    real = [d for d in r.decks if d.id not in OTHER_IDS]
    share_top = sorted(real, key=lambda d: d.share, reverse=True)[:10]

    tiers = {t: sorted([d for d in real if d.tier == t], key=lambda d: d.top8_share, reverse=True)
             for t in ("1", "2", "3")}

    movers = [d for d in real if d.delta is not None and
              (d.entries >= min_entries or (d.prev_share or 0) * r.prev_players >= min_entries)]
    risers = sorted([d for d in movers if d.delta > 0], key=lambda d: d.delta, reverse=True)[:3]
    fallers = sorted([d for d in movers if d.delta < 0], key=lambda d: d.delta)[:3]

    conv_pool = [d for d in real if d.entries >= conv_min]
    conv_top = sorted(conv_pool, key=lambda d: d.conversion, reverse=True)[:8]
    avg_conv = r.top8_slots / r.players if r.players else 0

    win_top = sorted([d for d in r.decks if d.wins], key=lambda d: (d.wins, d.top8), reverse=True)[:8]
    winning_decks = len({w["deck"] for w in r.winners})

    it_top = sorted([d for d in real if d.it_entries], key=lambda d: d.it_entries, reverse=True)[:8]
    show_it = r.it_players >= 50 and len(it_top) >= 5

    # numerazione: 1-6 fisse, poi lista (facoltativa), meta Italia (facoltativa), chiusura
    page = 6
    deck_page = it_page = None
    if deck:
        page += 1; deck_page = page
    if show_it:
        page += 1; it_page = page
    n_slides = page + 1

    return dict(
        r=r, handle=handle, min_entries=min_entries, conv_min=conv_min,
        tier_cut={k: str(v).replace(".0", "").replace(".", ",") for k, v in tier_cuts.items()},
        dates_it=dates_it(r.start, r.end),
        top=share_top[0], biggest_up=risers[0] if risers else None,
        share_top=share_top, share_max=max(d.share for d in share_top),
        tiers=tiers, risers=risers, fallers=fallers,
        conv_top=conv_top, avg_conv=avg_conv,
        conv_max=max([d.conversion for d in conv_top] + [avg_conv]) * 1.05,
        win_top=win_top, winning_decks=winning_decks,
        it_top=it_top, it_max=max([d.it_share for d in it_top] or [1]), show_it=show_it,
        n_slides=n_slides, deck=deck, deck_page=deck_page, it_page=it_page,
        pct=pct, pp=pp, num=num, delta_html=delta_html,
    )


def render_html(view: dict, out_html: Path) -> Path:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    html = env.get_template("carousel.html.j2").render(**view)
    out_html.write_text(html, encoding="utf-8")
    return out_html


def render_png(html_path: Path, out_dir: Path) -> list[Path]:
    """Screenshot di ogni <section class="slide"> con Chromium headless."""
    from playwright.sync_api import sync_playwright

    # Il template usa percorsi relativi per i font: lo rendiamo dalla cartella templates/
    tmp = ROOT / "templates" / "_render.html"
    tmp.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.goto(tmp.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        for i, el in enumerate(page.query_selector_all("section.slide"), 1):
            f = out_dir / f"slide_{i:02d}.png"
            el.screenshot(path=str(f))
            paths.append(f)
        browser.close()
    tmp.unlink(missing_ok=True)
    return paths


SECTION_IT = {"pokemon": "Pokémon", "trainer": "Allenatore", "energy": "Energia"}
GRID_W, GRID_H, GAP = 912, 840, 10   # area utile della griglia nella slide


def _grid(n: int, extra: int) -> tuple[int, int]:
    """Sceglie le colonne (6–8) con meno celle vuote che stanno nell'altezza; a parità, carte più grandi.
    `extra` = celle minime per il riquadro riepilogo. Restituisce (colonne, celle libere per il riepilogo)."""
    import math
    best = None
    for cols in (6, 7, 8):
        w = (GRID_W - (cols - 1) * GAP) / cols
        rows = math.ceil((n + extra) / cols)
        if rows * w * 88 / 63 + (rows - 1) * GAP > GRID_H:
            continue
        free = rows * cols - n
        key = (free, cols)
        if best is None or key < best[0]:
            best = (key, cols, free)
    if best is None:
        return 8, 0
    return best[1], best[2]


def build_deck(winner: dict, cards: list, remote: bool = False) -> dict:
    """Dati della slide «Lista della settimana». remote=True usa gli URL (anteprima nel browser)."""
    from .cards import deck_price
    rec = winner.get("record") or {}
    price, cov = deck_price(cards)
    items = []
    for c in cards:
        src = None
        if remote and c.remote:
            src = c.remote
        elif c.local:
            src = Path(c.local).resolve().as_uri()
        items.append(dict(name=c.name, count=c.count, src=src, set_code=c.set_code,
                          number=c.number, section=SECTION_IT.get(c.section, ""),
                          energy_color=c.energy_color,
                          energy_ink="#FFFFFF" if c.energy_color in ("#3A4150", "#A35BD6") else "#15122E"))
    counts = {k: sum(c.count for c in cards if c.section == k) for k in ("pokemon", "trainer", "energy")}
    total = sum(counts.values())
    cols, free = _grid(len(items), 1)
    return dict(
        name=winner["deck"], tournament=winner["tournament"], players=winner["players"],
        player=winner.get("player") or "",
        record=f"{rec.get('wins', 0)}-{rec.get('losses', 0)}-{rec.get('ties', 0)}",
        price=(f"{price:.0f} €" if price is not None and cov >= 0.95 else None),
        cards=items, cols=cols, summary_span=free, total=total, unique=len(items),
        counts=[("Pokémon", counts["pokemon"]), ("Allenatori", counts["trainer"]), ("Energie", counts["energy"])],
    )
