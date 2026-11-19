"""Söker efter tyngdlyftning i utvalda P4-program genom att skriva ut ljudet.

Körs av GitHub Actions (.github/workflows/radio.yml) i tre steg:

  python radio.py lista [--avsnitt ID,ID]   skriver matris.json med nya avsnitt att skriva ut
  python radio.py skriv AVSNITT.json UT.json laddar ner ljudet, skriver ut talet, söker träffar
  python radio.py sammanstall MAPP           samlar träffarna, mejlar dem och uppdaterar state/

Programmen står i radio.json. Sökorden är namnen i sokord.json (lyftare och
förbund) plus tyngdlyftningsord. Träffarna läggs INTE in på sidan automatiskt
– de mejlas som "möjliga radioinslag" så att någon kan lyssna och avgöra.
"""
import difflib
import html
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KONFIG = ROOT / "radio.json"
SOKORD = ROOT / "sokord.json"
KOLLADE = ROOT / "state" / "radio_kollade.json"
TRAFFAR = ROOT / "state" / "radio_traffar.json"
API = "https://api.sr.se/api/v2"

# Ord som alltid räknas som träff
NYCKELORD = [
    r"tyngdlyft\w*", r"ryck och stöt", r"\blyftar\w*", r"elitmiljö\w*",
    r"\bryck\w* \d+", r"\bstöt\w* \d+",
]
# Vanliga efternamn som inte räcker ensamma – kräver förnamnet i närheten
VANLIGA = {"lind", "ferm", "lang", "roos", "rönn", "öhman", "ågren", "kraft", "nilsson", "johansson",
           "pettersson", "berglund", "lindqvist", "andersson", "arvidsson", "henriksson", "ottosson"}


def hamta_json(url, forsok=4):
    for i in range(forsok):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            print("fel", url, e)
            time.sleep(5 * (i + 1))
    raise SystemExit(f"Kunde inte hämta {url}")


def sr_tid(s):
    m = re.search(r"\d+", s or "")
    return datetime.fromtimestamp(int(m.group()) / 1000, tz=timezone.utc) if m else None


def las(p, standard):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else standard


def skriv_json(p, data):
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def avsnitt_info(e, program):
    filer = (e.get("broadcast") or {}).get("broadcastfiles") or []
    if not filer:
        return None
    t = sr_tid(e.get("publishdateutc"))
    return {
        "id": e["id"], "program": program["namn"], "kanal": program["kanal"],
        "datum": t.astimezone(timezone(timedelta(hours=1))).strftime("%Y-%m-%d") if t else "",
        "lank": e.get("url") or f"https://www.sverigesradio.se/avsnitt/{e['id']}",
        "ljud": filer[0]["url"], "langd": filer[0].get("duration"),
    }


# ---------- lista ----------
def lista(args):
    konf = json.loads(KONFIG.read_text(encoding="utf-8"))
    kollade = set(las(KOLLADE, []))
    valda = []
    if "--avsnitt" in args:
        ids = [x.strip() for x in args[args.index("--avsnitt") + 1].split(",") if x.strip()]
        program = {p["id"]: p for p in konf["program"]}
        for i in ids:
            e = hamta_json(f"{API}/episodes/get?id={i}&format=json")["episode"]
            p = program.get(e["program"]["id"], {"namn": e["program"]["name"], "kanal": "", "id": e["program"]["id"]})
            info = avsnitt_info(e, p)
            if info:
                valda.append(info)
    else:
        idag = datetime.now(timezone.utc).date()
        fran = idag - timedelta(days=konf.get("dagar_bakat", 2))
        for p in konf["program"]:
            d = hamta_json(f"{API}/episodes/index?programid={p['id']}&fromdate={fran}&todate={idag}"
                           f"&format=json&pagination=false")
            for e in d.get("episodes", []):
                if e["id"] in kollade:
                    continue
                info = avsnitt_info(e, p)
                if info:
                    valda.append(info)
    print(f"{len(valda)} avsnitt att skriva ut")
    for v in valda:
        print(" ", v["datum"], v["program"], v["id"])
    Path("matris.json").write_text(json.dumps({"include": valda}, ensure_ascii=False), encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"matris={json.dumps({'include': valda}, ensure_ascii=False)}\n")
            f.write(f"antal={len(valda)}\n")


# ---------- sökning ----------
def norm(s):
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^\wåäöéü ]+", " ", s)


def personer():
    d = las(SOKORD, {})
    namn = list(d.get("lyftare", [])) + [p["namn"] for p in d.get("forbund", [])]
    ut = []
    for n in namn:
        delar = norm(n).split()
        if len(delar) >= 2:
            ut.append({"namn": n, "for": delar[0], "efter": delar[-1], "hela": " ".join(delar)})
    return ut


def ljud(w):
    """Förenklar stavning som låter likadant: Wikingsson=Vikingsson, Sund=Sundh, Viktor=Victor."""
    for a, b in (("ph", "f"), ("ck", "k"), ("dh", "d"), ("th", "t"), ("w", "v"), ("c", "k"), ("z", "s"),
                 ("é", "e"), ("ü", "y"), ("qu", "kv"), ("q", "k"), ("x", "ks")):
        w = w.replace(a, b)
    w = re.sub(r"(.)\1+", r"\1", w)  # dubbelbokstäver
    return w[:-1] if len(w) > 4 and w.endswith("h") else w


def liknar(a, b, grans=0.88):
    """a = ord i utskriften, b = namn. Lika ljud räcker bara om stavningen också är nära
    (annars blir t.ex. Lithén = "liten")."""
    ra = difflib.SequenceMatcher(None, a, b).ratio()
    if a == b:
        return True
    if ljud(a) == ljud(b):
        return ra >= 0.8
    return len(b) >= 6 and a[:1] == b[:1] and ra >= grans


def traffar_i(segment, folk):
    """segment: lista av {start, slut, text}. Returnerar träffar grupperade (inom 90 s)."""
    texter = [norm(x["text"]) for x in segment]

    def nara(i, sek=30):
        return [j for j in range(max(0, i - 8), min(len(segment), i + 9))
                if abs(segment[j]["start"] - segment[i]["start"]) <= sek]

    def nyckel(i):
        return {re.search(m, texter[i]).group(0) for m in NYCKELORD if re.search(m, texter[i])}

    rader = []
    for i in range(len(segment)):
        omrade = nara(i)
        fonster = " ".join(texter[j] for j in omrade)
        ord_ = texter[i].split()
        traff = nyckel(i)
        sport = bool(traff) or any(nyckel(j) for j in omrade)
        namn = {}
        for p in folk:
            if not any(liknar(w, p["efter"]) for w in ord_):
                continue
            exakt = p["efter"] in ord_
            hela = any(liknar(w, p["for"]) for w in fonster.split())
            distinkt = p["efter"] not in VANLIGA and not p["efter"].endswith("sson") and len(p["efter"]) >= 5
            # vanliga namn kräver förnamn + tyngdlyftningsord i närheten; ovanliga räcker med efternamnet
            if hela and (distinkt or sport):
                niva = 3
            elif distinkt and sport:
                niva = 2
            elif distinkt and exakt:
                niva = 1
            else:
                continue
            namn[p["namn"]] = (niva, ljud(p["efter"]))
        # samma efternamn (t.ex. Victor och Henrik Sundh): behåll bara den som passar bäst
        basta = {}
        for n, (niva, efter) in namn.items():
            basta[efter] = max(basta.get(efter, 0), niva)
        namn = {n for n, (niva, efter) in namn.items() if niva == basta[efter]}
        traff |= namn
        if traff:
            rader.append((i, traff))
    grupper = []
    for i, traff in rader:
        if grupper and segment[i]["start"] - grupper[-1]["slut"] < 90:
            g = grupper[-1]
            g["slut"], g["sist"] = segment[i]["slut"], i
            g["ord"] |= traff
        else:
            grupper.append({"start": segment[i]["start"], "slut": segment[i]["slut"], "forst": i, "sist": i, "ord": set(traff)})
    ut = []
    for g in grupper:
        delar = [x["text"].strip() for x in segment
                 if g["start"] - 20 <= x["start"] <= g["slut"] + 20]
        ut.append({"start": round(g["start"]), "ord": sorted(g["ord"]), "utdrag": " ".join(delar)[:700]})
    return ut


def tid(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# ---------- skriv ----------
def ladda_modell():
    from faster_whisper import WhisperModel
    for namn in (os.environ.get("WHISPER_MODELL") or "KBLab/kb-whisper-small", "small"):
        try:
            m = WhisperModel(namn, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
            print("modell:", namn)
            return m, namn
        except Exception as e:  # noqa: BLE001
            print("kunde inte ladda", namn, e)
    raise SystemExit("Ingen taligenkänningsmodell gick att ladda")


def skriv(args):
    arg = args[0]
    avsnitt = json.loads(arg) if arg.lstrip().startswith("{") else json.loads(Path(arg).read_text(encoding="utf-8"))
    ut = Path(args[1])
    wav = Path("ljud.wav")
    t0 = time.time()
    subprocess.run(["curl", "-sSL", "--retry", "4", "-o", "ljud.m4a", avsnitt["ljud"]], check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", "ljud.m4a", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    print(f"ljud hämtat på {time.time() - t0:.0f} s")
    modell, modellnamn = ladda_modell()
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as w:
        ljud = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = modell.transcribe(ljud, language="sv", beam_size=1, vad_filter=True,
                                condition_on_previous_text=False)
    segment = []
    for s in segs:
        segment.append({"start": s.start, "slut": s.end, "text": s.text})
        if len(segment) % 200 == 0:
            print(f"  {tid(s.end)} utskrivet efter {time.time() - t0:.0f} s")
    folk = personer()
    traff = traffar_i(segment, folk)
    print(f"klart på {time.time() - t0:.0f} s, {len(segment)} segment, {len(traff)} träffar")
    for t in traff:
        print(" ", tid(t["start"]), t["ord"], t["utdrag"][:160])
    skriv_json(ut, {**avsnitt, "modell": modellnamn, "traffar": traff, "segment": len(segment)})


# ---------- sammanställ och mejla ----------
def sammanstall(args):
    mapp = Path(args[0])
    resultat = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(mapp.rglob("*.json"))]
    kollade = las(KOLLADE, [])
    historik = las(TRAFFAR, [])
    nya = []
    for r in resultat:
        if r["id"] not in kollade:
            kollade.append(r["id"])
        for t in r["traffar"]:
            post = {"avsnitt": r["id"], "program": r["program"], "datum": r["datum"], "lank": r["lank"], **t}
            if not any(h["avsnitt"] == post["avsnitt"] and abs(h["start"] - post["start"]) < 60 for h in historik):
                historik.append(post)
                nya.append(post)
    skriv_json(KOLLADE, kollade[-2000:])
    skriv_json(TRAFFAR, historik)
    print(f"{len(resultat)} avsnitt utskrivna, {len(nya)} nya träffar")
    if not nya or "--inget-mejl" in args:
        return
    nya.sort(key=lambda x: (x["datum"], x["program"], x["start"]))
    sys.path.insert(0, str(ROOT))
    from skicka_mejl import BLA, GUL, skicka
    rubrik = f"Möjliga radioinslag om tyngdlyftning – {len(nya)} {'träff' if len(nya) == 1 else 'träffar'} ({datetime.now().date()})"
    text, rader = [rubrik, "Automatisk utskrift av P4-program. Lyssna och avgör – svara om något ska läggas in.\n"], []
    for t in nya:
        text.append(f"{t['datum']} · {t['program']} · {tid(t['start'])} in\n{', '.join(t['ord'])}\n{t['lank']}\n”{t['utdrag']}”\n")
        rader.append(
            f'<tr><td style="padding:14px 0;border-bottom:1px solid #e6e6e6">'
            f'<div style="font-size:13px;color:#666">{html.escape(t["datum"])} · '
            f'<span style="text-transform:uppercase;font-weight:bold;letter-spacing:.04em">{html.escape(t["program"])}</span>'
            f'<span style="display:inline-block;margin-left:6px;padding:1px 6px;background:{GUL};color:#000;font-size:11px;font-weight:bold">LJUD</span></div>'
            f'<div style="margin-top:4px;font-size:17px;font-weight:bold"><a href="{html.escape(t["lank"])}" style="color:{BLA};text-decoration:none">'
            f'{tid(t["start"])} in i sändningen</a></div>'
            f'<div style="margin-top:2px;font-size:13px;color:#000">Träff på: {html.escape(", ".join(t["ord"]))}</div>'
            f'<div style="margin-top:6px;font-size:14px;color:#404040;font-style:italic">”{html.escape(t["utdrag"])}”</div></td></tr>')
    body = f"""<div style="font-family:'Open Sans',Arial,sans-serif;max-width:640px;color:#404040">
<h2 style="margin:0 0 8px;color:{BLA};text-transform:uppercase;font-size:20px;border-bottom:1px solid #ccc;padding-bottom:8px">Möjliga radioinslag</h2>
<p style="margin:0 0 4px;font-size:14px">Automatisk utskrift av P4-program. Taligenkänningen kan höra fel på namn – lyssna och avgör. Svara om något ska läggas in på sidan.</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{''.join(rader)}</table></div>"""
    skicka(rubrik, "\n".join(text), body)


if __name__ == "__main__":
    kommando, *rest = sys.argv[1:] or ["hjälp"]
    {"lista": lista, "skriv": skriv, "sammanstall": sammanstall}.get(kommando, lambda a: print(__doc__))(rest)
