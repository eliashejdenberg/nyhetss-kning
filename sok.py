"""Morgonens nyhetssökning – körs av GitHub Actions (.github/workflows/sok.yml).

Gör det mekaniska arbetet som tidigare gjordes av Claude-körningen:
  * alla sökningar i Google Nyheter (svenska + engelska/norska/danska/finska)
  * Expressens sportvideoflöde, Fygstermedia och Weightlifting House
  * översätter Google-länkar till artikelns riktiga adress
  * öppnar artikeln och letar efter tyngdlyftningsord, video och ljud
  * datumkontroll (återpublicerade gamla artiklar)
  * tar bort det som redan finns på sidan och förbundets eget material

Resultatet skrivs till state/kandidater.json. Claude-körningen kl. 06:47
läser bara den filen och gör bedömningen (sammanhang, sammanfattning,
publicering).

Kör: python3 sok.py            (alla sökningar, när:3d)
     python3 sok.py --snabb    (bara allmänna sökningar, för test)
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIDA = ROOT / "src" / "sida.html"
SOKORD = ROOT / "sokord.json"
UT = ROOT / "state" / "kandidater.json"
SVT = timezone(timedelta(hours=1))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
IDAG = datetime.now(SVT).date()

UTESLUT_DOMAN = ("tyngdlyftning.com", "via.tt.se", "mynewsdesk.com", "sok.se", "facebook.com", "instagram.com",
                 "tv.nu", "svenskalag.se", "idrottonline.se", "laget.se", "vietnam.vn", "tvtid", "tablå")
UTESLUT_KALLA = ("svenska tyngdlyftningsförbundet", "mynewsdesk", "via tt", "sveriges olympiska kommitté",
                 "tv.nu", "svenskalag", "vietnam.vn")
SPRAK = {"sv": "", "en": "ENGELSKA", "no": "NORSKA", "da": "DANSKA", "fi": "FINSKA"}
REGION = {"sv": "hl=sv&gl=SE&ceid=SE:sv", "en": "hl=en-US&gl=US&ceid=US:en", "en-gb": "hl=en-GB&gl=GB&ceid=GB:en",
          "no": "hl=no&gl=NO&ceid=NO:no", "da": "hl=da&gl=DK&ceid=DK:da", "fi": "hl=fi&gl=FI&ceid=FI:fi"}
# ord som visar att texten handlar om tyngdlyftning (alla språk)
SPORTORD = re.compile(r"tyngdlyft\w*|ryck och stöt|\bryck\b|\bstöt\b|weightlift\w*|snatch|clean (?:and|&) jerk|"
                      r"vektløft\w*|vægtløft\w*|painonnost\w*|\blyftar\w*|\bIWF\b", re.I)
ANNAN_SPORT = re.compile(r"styrkelyft\w*|bänkpress\w*|marklyft\w*|powerlift\w*|strongman|crossfit|knäböj", re.I)

fel = []
statistik = {"sokningar": 0, "misslyckade": 0, "i_rad": 0}
START = time.time()
BUDGET = 35 * 60  # sekunder för Google-sökningarna


def logg(*a):
    print(f"[{int(time.time() - START):4d}s]", *a, flush=True)


def hamta(url, data=None, headers=None, tid=25, max_bytes=2_000_000):
    h = {"User-Agent": UA, "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=tid) as r:
        return r.read(max_bytes).decode(r.headers.get_content_charset() or "utf-8", "replace"), r.geturl()


# ---------- Google Nyheter ----------
def google(q, region="sv", nar="3d"):
    """Returnerar lista av poster. Försöker igen om Google begränsar, inom tidsbudgeten."""
    if time.time() - START > BUDGET:
        statistik["misslyckade"] += 1
        fel.append(f"Hann inte (tidsgräns): {q} ({region})")
        return []
    qq = q + (f" when:{nar}" if nar else "")
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(qq)}&{REGION[region]}"
    statistik["sokningar"] += 1
    sista = None
    for forsok in range(3):
        try:
            text, _ = hamta(url)
            if not text.lstrip().startswith("<?xml"):
                raise ValueError("inte RSS – Google begränsar")
            text = re.sub(r"<title>[^<]*</title>", "", text, count=1)
            root = ET.fromstring(text)
            ut = []
            for it in root.findall(".//item"):
                kalla = it.findtext("source") or ""
                rubrik = re.sub(r"\s+-\s+" + re.escape(kalla) + r"\s*$", "", it.findtext("title") or "").strip()
                try:
                    d = parsedate_to_datetime(it.findtext("pubDate")).astimezone(SVT).date()
                except Exception:  # noqa: BLE001
                    d = None
                ut.append({"kalla": kalla, "rubrik": html.unescape(rubrik), "datum": d,
                           "google": it.findtext("link") or "", "kalla_url": (it.find("source").get("url") if it.find("source") is not None else "")})
            statistik["i_rad"] = 0
            time.sleep(1.5)
            return ut
        except Exception as e:  # noqa: BLE001
            sista = e
            statistik["i_rad"] += 1
            vanta = min(90, 10 * statistik["i_rad"])
            logg(f"  fel ({e}), väntar {vanta} s: {q[:60]}")
            time.sleep(vanta)
    statistik["misslyckade"] += 1
    fel.append(f"Google Nyheter: {q} ({region}) – {sista}")
    return []


def riktig_adress(google_lank):
    try:
        aid = re.search(r"/articles/([^?]+)", google_lank).group(1)
        sida, _ = hamta(f"https://news.google.com/rss/articles/{aid}")
        sg = re.search(r'data-n-a-sg="([^"]+)"', sida).group(1)
        ts = re.search(r'data-n-a-ts="([^"]+)"', sida).group(1)
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                 "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts), sg]
        freq = json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])
        svar, _ = hamta("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                        data=("f.req=" + urllib.parse.quote(freq)).encode(),
                        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        m = re.search(r'\[\\"garturlres\\",\\"(.*?)\\"', svar)
        time.sleep(0.8)
        if not m:
            return None
        u = m.group(1)
        for _ in range(3):  # svaret är dubbelt kodat (\\u003d = "=")
            u = re.sub(r"\\+u([0-9a-fA-F]{4})", lambda x: chr(int(x.group(1), 16)), u).replace("\\/", "/")
        return u
    except Exception:  # noqa: BLE001
        return None


# ---------- artikelsidan ----------
def las_artikel(url):
    """Öppnar artikeln. Returnerar text, ingress och video/ljud-markörer."""
    info = {"las": False, "ingress": "", "text": "", "media": []}
    lag = url.lower()
    if any(x in lag for x in ("tv4.se/klipp/", "tv4play.se", "expressen.se/tv/", "aftonbladet.se/tv", "svtplay.se", "youtube.com", "youtu.be")):
        info["media"].append("VIDEO")
    if any(x in lag for x in ("sverigesradio.se/avsnitt/", "sverigesradio.se/ljud/", "podcast", "/podd")):
        info["media"].append("LJUD")
    try:
        sida, _ = hamta(url, tid=20)
    except Exception:  # noqa: BLE001
        return info
    info["las"] = True
    m = re.search(r'<meta[^>]+(?:property|name)="(?:og:description|description)"[^>]+content="([^"]*)"', sida, re.I)
    info["ingress"] = html.unescape(m.group(1)).strip()[:400] if m else ""
    ren = re.sub(r"<(script|style|nav|header|footer|aside|noscript)\b.*?</\1>", " ", sida, flags=re.S | re.I)
    ren = html.unescape(re.sub(r"<[^>]+>", " ", ren))
    info["text"] = re.sub(r"\s+", " ", ren)
    if "VIDEO" not in info["media"] and re.search(
            r"<video\b|og:video|youtube\.com/embed|player\.vimeo|svtplay|tv4play|videoplayer|data-video-id|jwplayer", sida, re.I):
        info["media"].append("VIDEO")
    if "LJUD" not in info["media"] and re.search(r"<audio\b|sverigesradio\.se/(?:embed|ljud)|podcast-player|og:audio", sida, re.I):
        info["media"].append("LJUD")
    return info


def utdrag(text, monster, bredd=180):
    m = monster.search(text)
    if not m:
        return ""
    a, b = max(0, m.start() - bredd), min(len(text), m.end() + bredd)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


# ---------- redan på sidan ----------
def norm(s):
    return re.sub(r"[^\wåäöéü]+", " ", (s or "").lower()).strip()


def befintliga():
    src = SIDA.read_text(encoding="utf-8")
    lankar = {html.unescape(x).rstrip("/") for x in re.findall(r'<a href="([^"]+)"', src)}
    rubriker = {norm(html.unescape(re.sub(r"<[^>]+>", "", x))) for x in re.findall(r'<a href="[^"]*"[^>]*>(.*?)</a>', src, re.S)}
    return lankar, rubriker


def uteslut(lank, kalla):
    return any(d in (lank or "").lower() for d in UTESLUT_DOMAN) or any(k in (kalla or "").lower() for k in UTESLUT_KALLA)


# ---------- sökningar ----------
def bitar(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


def sokningar(snabb=False):
    d = json.loads(SOKORD.read_text(encoding="utf-8"))
    lyftare = d.get("lyftare", [])
    forbund = [p["namn"] for p in d.get("forbund", [])]
    efternamn = sorted({n.split()[-1] for n in lyftare})
    s = [("sv", 'tyngdlyftning OR tyngdlyftare OR tyngdlyftaren OR tyngdlyftningen OR tyngdlyftningsförbundet OR "ryck och stöt"', "allmän")]
    if snabb:
        return s
    for m in ("NM tyngdlyftning", "Lag-SM tyngdlyftning", "Junior-SM tyngdlyftning", "SM tyngdlyftning",
              "EM tyngdlyftning", "VM tyngdlyftning", "OS tyngdlyftning"):
        s.append(("sv", m, "mästerskap"))
    for b in bitar(lyftare, 6):
        namn = " OR ".join(f'"{n}"' for n in b)
        s.append(("sv", f"({namn}) (tyngdlyftning OR tyngdlyftare OR tyngdlyftaren)", "lyftare"))
        s.append(("sv", f"({namn})", "lyftare (bara namn)"))
    for b in bitar(forbund, 6):
        namn = " OR ".join(f'"{n}"' for n in b)
        s.append(("sv", f"({namn}) (tyngdlyftning OR tyngdlyftare OR tyngdlyftningsförbundet OR landslaget)", "förbund"))
    for o in ("tyngdlyftning", "tyngdlyftare", "lyftare"):
        s.append(("sv", f"site:sverigesradio.se {o}", "Sveriges Radio"))
    for b in bitar(efternamn, 8):
        s.append(("sv", "site:sverigesradio.se (" + " OR ".join(f'"{e}"' for e in b) + ")", "Sveriges Radio (efternamn)"))
    for o in ("site:hallandsposten.se tyngdlyftning", "site:hallandsposten.se lyftare", "site:hn.se tyngdlyftning"):
        s.append(("sv", o, "Halland"))
    for b in bitar(efternamn, 8):
        s.append(("sv", "site:hallandsposten.se (" + " OR ".join(f'"{e}"' for e in b) + ")", "Halland (efternamn)"))
    # utländska
    for reg in ("en", "en-gb"):
        for q in ('"Swedish weightlifter"', '"Swedish Weightlifting Federation"', "Sweden weightlifting"):
            s.append((reg, q, "utländsk"))
    namnbitar = list(bitar(lyftare, 6))
    for b in namnbitar:
        namn = " OR ".join(f'"{n}"' for n in b)
        s.append(("en", f"({namn}) weightlifting", "utländsk (namn)"))
        s.append(("no", f"({namn}) vektløfting", "utländsk (namn)"))
        s.append(("da", f"({namn}) vægtløftning", "utländsk (namn)"))
        s.append(("fi", f"({namn}) painonnosto", "utländsk (namn)"))
    s += [("no", '"svensk vektløfter"', "utländsk"), ("da", "svensk vægtløfter", "utländsk"),
          ("fi", "ruotsalainen painonnostaja", "utländsk")]
    return s


# ---------- specialkällor ----------
SVENSK = re.compile(r"\(SWE\)|Swedish|Sverige|Sweden'?s?\b|Swede\b|Vikings+on|Sj[oö]blom", re.I)


def specialkallor(lankar):
    ut = []
    d = json.loads(SOKORD.read_text(encoding="utf-8"))
    namn = d.get("lyftare", []) + [p["namn"] for p in d.get("forbund", [])]
    namnmonster = re.compile("|".join(re.escape(n.split()[-1]) for n in namn if len(n.split()[-1]) > 4), re.I)

    def granska(kalla, rubrik, lank, datum, text):
        if lank.rstrip("/") in lankar or not datum or (IDAG - datum).days > 14:
            return
        svensk = SVENSK.search(text) or namnmonster.search(text)
        if svensk:
            ut.append({"kalla": kalla, "rubrik": rubrik, "lank": lank, "datum": datum.isoformat(), "sprak": "ENGELSKA",
                       "hittad_via": "specialkälla", "utdrag": utdrag(text, re.compile(re.escape(svensk.group(0))), 300),
                       "las": True, "media": [], "hint": "kontrollera – nämner svenskar"})
    # Weightlifting House (Atom)
    try:
        text, _ = hamta("https://eustore.weightliftinghouse.com/blogs/news.atom")
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in ET.fromstring(text).findall("a:entry", ns):
            lank = e.find("a:link", ns).get("href")
            d0 = datetime.fromisoformat(e.findtext("a:published", namespaces=ns).replace("Z", "+00:00")).astimezone(SVT).date()
            innehall = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", e.findtext("a:content", "", ns))))
            granska("Weightlifting House", e.findtext("a:title", "", ns), lank, d0, innehall)
    except Exception as ex:  # noqa: BLE001
        fel.append(f"Weightlifting House: {ex}")
    # Fygstermedia (ingen RSS)
    try:
        start, _ = hamta("https://www.fygstermedia.com/")
        poster = sorted(set(re.findall(r'href="(?:https://www\.fygstermedia\.com)?/(\d{6,}_[^"#?]+)"', start)),
                        key=lambda x: int(x.split("_")[0]), reverse=True)[:12]
        for p in poster:
            lank = f"https://www.fygstermedia.com/{p}"
            if lank in lankar:
                continue
            sida, _ = hamta(lank)
            m = re.search(r"Published\W+([A-Z][a-z]+ \d{1,2}, \d{4})", re.sub(r"<[^>]+>", " ", sida))
            d0 = datetime.strptime(m.group(1), "%B %d, %Y").date() if m else None
            t = re.search(r"<title>(.*?)</title>", sida, re.S)
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", sida, flags=re.S))))
            granska("Fygstermedia", html.unescape(t.group(1)).split("|")[0].strip() if t else p, lank, d0, text)
            time.sleep(0.5)
    except Exception as ex:  # noqa: BLE001
        fel.append(f"Fygstermedia: {ex}")
    return ut


def expressen_video(lankar):
    ut = []
    try:
        text, _ = hamta("https://feeds.expressen.se/tv/sport/")
        for it in ET.fromstring(text).findall(".//item"):
            lank = (it.findtext("link") or "").strip()
            if lank.rstrip("/") in lankar:
                continue
            rubrik = html.unescape(it.findtext("title") or "")
            besk = html.unescape(re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))
            try:
                d0 = parsedate_to_datetime(it.findtext("pubDate")).astimezone(SVT).date()
            except Exception:  # noqa: BLE001
                d0 = IDAG
            sport = bool(SPORTORD.search(rubrik + " " + besk))
            if (IDAG - d0).days > 3:
                continue
            post = {"rubrik": rubrik, "lank": lank, "datum": d0.isoformat(), "nämner_tyngdlyftning": sport}
            if sport:
                post["beskrivning"] = besk[:250]
            ut.append(post)
    except Exception as ex:  # noqa: BLE001
        fel.append(f"Expressen TV: {ex}")
    return ut


# ---------- huvudprogram ----------
def main():
    snabb = "--snabb" in sys.argv
    lankar, rubriker = befintliga()
    fynd = {}
    lista = sokningar(snabb)
    logg(f"{len(lista)} sökningar att köra")
    for nr, (region, q, varfor) in enumerate(lista, 1):
        if nr % 20 == 0:
            logg(f"sökning {nr}/{len(lista)}, {len(fynd)} träffar hittills, {statistik['misslyckade']} misslyckade")
        for p in google(q, region):
            if not p["datum"] or (IDAG - p["datum"]).days > 3:
                continue
            nyckel = (norm(p["rubrik"]), norm(p["kalla"]))
            if nyckel[0] in rubriker or uteslut(p["kalla_url"], p["kalla"]):
                continue
            post = fynd.setdefault(nyckel, {**p, "sprak": SPRAK.get(region[:2], ""), "hittad_via": []})
            if varfor not in post["hittad_via"]:
                post["hittad_via"].append(varfor)
    logg(f"{statistik['sokningar']} sökningar, {len(fynd)} nya träffar efter dubblettrensning")
    allanamn = [*json.loads(SOKORD.read_text(encoding="utf-8")).get("lyftare", []),
                *[p["namn"] for p in json.loads(SOKORD.read_text(encoding="utf-8")).get("forbund", [])]]

    kandidater, bort = [], []
    for nr, post in enumerate(fynd.values(), 1):
        if nr % 10 == 0:
            logg(f"artikel {nr}/{len(fynd)}")
        lank = riktig_adress(post["google"]) or post["google"]
        if lank.rstrip("/") in lankar or uteslut(lank, post["kalla"]):
            continue
        art = las_artikel(lank) if "news.google.com" not in lank else {"las": False, "ingress": "", "text": "", "media": []}
        text = art["text"]
        namn_i = [n for n in allanamn if n.lower() in (post["rubrik"] + " " + text).lower()]
        i_rubrik = bool(SPORTORD.search(post["rubrik"]))
        i_text = SPORTORD.findall(text)
        annan = ANNAN_SPORT.findall(post["rubrik"] + " " + text)
        # datumkontroll: finns samma rubrik tidigare? (bara för troliga kandidater)
        tidigast = post["datum"]
        if i_rubrik or i_text:
            for p in google(f'"{post["rubrik"]}"', "sv" if not post["sprak"] else "en", nar=None)[:10]:
                if p["datum"] and norm(p["rubrik"]) == norm(post["rubrik"]) and p["datum"] < tidigast:
                    tidigast = p["datum"]
        k = {"kalla": post["kalla"], "rubrik": post["rubrik"], "lank": lank, "datum": post["datum"].isoformat(),
             "hittad_via": post["hittad_via"], "sprak": post["sprak"], "las": art["las"], "media": art["media"]}
        if namn_i:
            k["namn"] = namn_i
        if tidigast < post["datum"]:
            k["tidigaste_datum"] = tidigast.isoformat()
            k["aterpublicerad"] = (IDAG - tidigast).days > 14
        if art["ingress"]:
            k["ingress"] = art["ingress"]
        if i_text:
            k["utdrag"] = utdrag(text, SPORTORD)
            k["sportord_i_texten"] = len(i_text)
        if annan:
            k["annan_sport"] = sorted({a.lower() for a in annan})[:5]
        # förhandsbedömning – Claude avgör
        if i_rubrik or (i_text and len(i_text) >= 2 and len(i_text) >= len(annan)):
            k["hint"] = "trolig"
        elif not art["las"]:
            k["hint"] = "kunde inte läsa artikeln"
        elif i_text:
            k["hint"] = "osäker – nämner tyngdlyftning lite"
        else:
            k["hint"] = "troligen inte – inget tyngdlyftningsord i artikeln"
        (bort if k["hint"].startswith("troligen inte") else kandidater).append(k)

    special = specialkallor(lankar)
    video = expressen_video(lankar)
    UT.parent.mkdir(exist_ok=True)
    UT.write_text(json.dumps({
        "skapad": datetime.now(SVT).isoformat(timespec="minutes"),
        "sokningar": statistik["sokningar"], "misslyckade_sokningar": statistik["misslyckade"],
        "kandidater": sorted(kandidater, key=lambda x: x["datum"], reverse=True),
        "specialkallor": special,
        "expressen_video": video,
        "troligen_inte": [{k: v for k, v in x.items() if k in ("kalla", "rubrik", "lank", "datum", "hittad_via", "annan_sport")} for x in bort],
        "fel": fel,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    logg(f"{len(kandidater)} kandidater, {len(bort)} troligen inte, {len(special)} från specialkällor, "
          f"{len(video)} Expressen-klipp, {len(fel)} fel")


if __name__ == "__main__":
    main()
