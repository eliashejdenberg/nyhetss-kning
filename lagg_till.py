"""Lägger till en artikel på sidan på begäran ("Lägg till"-knappen i mejlet).

Körs av .github/workflows/lagg_till.yml när ägaren (eller någon med
skrivrätt) skapar ett GitHub-ärende med rubriken "Lägg till: <adress>".
Ärendets text kommer från mejlet och innehåller källa, rubrik och datum:
  - Källa – "Rubrik" (ÅÅÅÅ-MM-DD) – skäl

Skriptet öppnar artikeln (rubrik, ingress, datum, video/ljud), lägger in
posten i src/sida.html i datumordning och skriver ut vad som gjordes.

Kör:  python3 lagg_till.py "Lägg till: https://…" "ärendetext"
      python3 lagg_till.py --visa https://…      (visa bara vad som hittas)
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sok import hamta, las_artikel  # noqa: E402

ROOT = Path(__file__).resolve().parent
SIDA = ROOT / "src" / "sida.html"
SPRAK = {"en": ("ENGELSKA", "en"), "no": ("NORSKA", "no"), "nb": ("NORSKA", "no"), "da": ("DANSKA", "da"), "fi": ("FINSKA", "fi")}


def meta(sida, *namn):
    for n in namn:
        m = re.search(rf'<meta[^>]+(?:property|name|itemprop)="{re.escape(n)}"[^>]+content="([^"]*)"', sida, re.I) or \
            re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name|itemprop)="{re.escape(n)}"', sida, re.I)
        if m and m.group(1).strip():
            return html.unescape(m.group(1)).strip()
    return ""


def fran_mejl(text):
    """Källa, rubrik och datum ur raden som mejlet skickade med."""
    m = re.search(r"^\s*-?\s*(?P<kalla>[^\n–]+?)\s+–\s+[\"”“](?P<rubrik>.+?)[\"”“]\s*(?:\((?P<datum>\d{4}-\d\d-\d\d)\))?\s*(?:–|$)",
                  text or "", re.M)
    return {k: (v or "").strip() for k, v in m.groupdict().items()} if m else {}


def undersok(url, mejl=""):
    info = fran_mejl(mejl)
    ut = {"lank": url, "kalla": info.get("kalla", ""), "rubrik": info.get("rubrik", ""), "datum": info.get("datum", ""),
          "ingress": "", "media": [], "sprak": ""}
    try:
        sida, _ = hamta(url)
    except Exception as e:  # noqa: BLE001
        print("kunde inte öppna artikeln:", e)
        sida = ""
    if sida:
        ut["rubrik"] = ut["rubrik"] or meta(sida, "og:title", "twitter:title") or \
            html.unescape((re.search(r"<title>(.*?)</title>", sida, re.S) or [None, ""])[1]).strip()
        ut["kalla"] = ut["kalla"] or meta(sida, "og:site_name")
        pub = meta(sida, "article:published_time", "datePublished", "pubdate", "publish-date", "date") or \
            (re.search(r'"datePublished"\s*:\s*"([^"]+)"', sida) or [None, ""])[1]
        if not ut["datum"] and re.match(r"\d{4}-\d\d-\d\d", pub):
            ut["datum"] = pub[:10]
        ut["ingress"] = meta(sida, "og:description", "description")[:300]
        lang = (re.search(r'<html[^>]+lang="([a-z]{2})', sida, re.I) or [None, ""])[1].lower()
        if lang in SPRAK:
            ut["sprak"] = lang
    ut["media"] = las_artikel(url)["media"] if sida else []
    if not ut["kalla"]:
        ut["kalla"] = urlparse(url).netloc.removeprefix("www.")
    ut["datum"] = ut["datum"] or date.today().isoformat()
    return ut


def rad(a):
    etiketter = []
    lang_attr = ""
    if a["sprak"] in SPRAK:
        etikett, kod = SPRAK[a["sprak"]]
        etiketter.append(etikett)
        lang_attr = f' lang="{kod}"'
    etiketter += a["media"]
    src = html.escape(a["kalla"]) + "".join(f'<span class="lang">{e}</span>' for e in etiketter)
    p = f"<p>{html.escape(a['ingress'])}</p>" if a["ingress"] else ""
    return (f'      <div class="item"><span class="src">{src}</span><div class="body"><span class="tag">{a["datum"]}</span>'
            f'<a href="{html.escape(a["lank"])}" target="_blank" rel="noopener"{lang_attr}>{html.escape(a["rubrik"])}</a>{p}</div></div>\n')


def lagg_in(a):
    s = SIDA.read_text(encoding="utf-8")
    if f'href="{html.escape(a["lank"])}"' in s or f'href="{a["lank"]}"' in s:
        return False
    ny = rad(a)
    for m in re.finditer(r'      <div class="item">.*?<span class="tag[^"]*">([^<]*)</span>', s):
        d = m.group(1)
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", d) or d < a["datum"]:
            s = s[:m.start()] + ny + s[m.start():]
            break
    else:
        i = s.index("</div>\n  </section>") if "</div>\n  </section>" in s else s.rindex('<div class="item">')
        s = s[:i] + ny + s[i:]
    SIDA.write_text(s, encoding="utf-8")
    # artikeln är redan sedd i mejlet – mejla den inte igen som ny
    skickade = ROOT / "state" / "skickade.json"
    if skickade.exists():
        lista = set(json.loads(skickade.read_text(encoding="utf-8")))
        lista.add(a["lank"])
        skickade.write_text(json.dumps(sorted(lista), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    return True


def main():
    if sys.argv[1:2] == ["--visa"]:
        print(json.dumps(undersok(sys.argv[2]), ensure_ascii=False, indent=1))
        return
    titel, text = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    m = re.search(r"https?://\S+", titel) or re.search(r"https?://\S+", text)
    if not m:
        sys.exit("Ingen adress i ärendet.")
    url = m.group(0).rstrip(").,;")
    a = undersok(url, text)
    print(json.dumps(a, ensure_ascii=False, indent=1))
    if lagg_in(a):
        print(f"LAGT TILL: {a['kalla']} – {a['rubrik']} ({a['datum']})")
    else:
        print("FANNS REDAN på sidan")


if __name__ == "__main__":
    main()
