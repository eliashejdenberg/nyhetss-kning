"""Hämtar en liten logga (favicon) för varje mediehus som finns i src/sida.html.

Loggorna sparas i logos/<domän>.png och läggs i repot, så att besökare
laddar dem från GitHub Pages och inte från någon annan tjänst.
Redan hämtade loggor hämtas inte igen.

Kör: python3 -I hamta_loggor.py   (före python3 -I build.py)
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGOS = ROOT / "logos"
SRC = (ROOT / "src" / "sida.html").read_text(encoding="utf-8")
STORLEK = 64


def doman(url):
    m = re.match(r"https?://([^/]+)", url)
    if not m:
        return None
    d = m.group(1).lower()
    return d[4:] if d.startswith("www.") else d


def ar_png(data):
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def hamta(d):
    url = (
        "https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
        f"&fallback_opts=TYPE,SIZE,URL&url=https://{d}&size={STORLEK}"
    )
    r = subprocess.run(["curl", "-sS", "--max-time", "20", "-w", "\n%{http_code}", url], capture_output=True)
    body, _, code = r.stdout.rpartition(b"\n")
    if code.strip() != b"200" or not ar_png(body):
        return None
    return body


def main():
    LOGOS.mkdir(exist_ok=True)
    domaner = sorted({doman(u) for u in re.findall(r'<div class="item">.*?<a href="([^"]+)"', SRC) if doman(u)})
    for d in domaner:
        if "news.google.com" in d:
            continue
        mal = LOGOS / f"{d}.png"
        if mal.exists():
            continue
        data = hamta(d)
        if data:
            mal.write_bytes(data)
            print("hämtade", mal.name, len(data), "byte")
        else:
            print("ingen logga för", d)


if __name__ == "__main__":
    main()
