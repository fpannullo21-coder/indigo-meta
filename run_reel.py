#!/usr/bin/env python3
"""Reel verticale 1080x1920 da una pagina animata con seek(t).

python run_reel.py templates/reel_binder_gengar.html output/reel-binder-gengar/reel.mp4
python run_reel.py templates/reel_binder_gengar.html output/reel-binder-gengar --stills 2.9 6.2 8.8
Ogni scena (.scene con data-start/data-end) diventa un mp4; poi si uniscono senza ricodificare.
"""
import argparse
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

FPS = 30
ENC = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def open_page(p, html: Path):
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
    page.goto(html.resolve().as_uri())
    page.evaluate("document.fonts.ready")
    page.wait_for_function("[...document.images].every(i => i.complete && i.naturalWidth > 0)", timeout=30000)
    return browser, page


def shot(page, t: float) -> bytes:
    page.evaluate(f"seek({t:.4f})")
    return page.screenshot(type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": 1080, "height": 1920})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("out")
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--only", type=int, help="rifà solo questa scena (1, 2, …) e riunisce le altre già fatte")
    a = ap.parse_args()
    html, out = Path(a.html), Path(a.out)
    with sync_playwright() as p:
        browser, page = open_page(p, html)
        if a.stills:
            out.mkdir(parents=True, exist_ok=True)
            for t in a.stills:
                (out / f"still_{t:05.2f}.jpg").write_bytes(shot(page, t))
            print(f"{len(a.stills)} fotogrammi in {out}")
            return
        out.parent.mkdir(parents=True, exist_ok=True)
        parts = []
        for i, (s, e) in enumerate(page.evaluate("scenes()")):
            part = out.parent / f"scene_{i + 1:02d}.mp4"
            tmp = out.parent / f"scene_{i + 1:02d}.tmp.mp4"
            if a.only and a.only != i + 1 and part.exists():
                parts.append(part)
                continue
            ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                                   "-c:v", "mjpeg", "-i", "-", *ENC, str(tmp)], stdin=subprocess.PIPE)
            for f in range(round(s * FPS), round(e * FPS)):
                ff.stdin.write(shot(page, f / FPS))
            ff.stdin.close()
            if ff.wait() != 0:
                raise SystemExit(f"ffmpeg non riuscito sulla scena {i + 1}")
            tmp.rename(part)
            parts.append(part)
            print(f"scena {i + 1}: {e - s:.1f} s")
        browser.close()
    lst = out.parent / "scenes.txt"
    lst.write_text("".join(f"file '{q.name}'\n" for q in parts))
    tmp = out.with_suffix(".tmp.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.rename(out)
    print(f"Reel pronto: {out}")


if __name__ == "__main__":
    main()
