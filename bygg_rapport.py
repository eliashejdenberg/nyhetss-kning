"""Bygger en rapport över alla artiklar på sidan och fynden i öppna arkiv.

Skapar:
  arkiv/tyngdlyftning_i_media.xlsx   flikar: Per år, Artiklar, Öppna arkiv, Arkiv per årtionde
  arkiv/artiklar.csv                 alla artiklar (för den som inte har Excel)

Kör: python3 -I bygg_rapport.py   (efter att src/sida.html uppdaterats)
"""
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UT = ROOT / "arkiv"
UT.mkdir(exist_ok=True)
SRC = (ROOT / "src" / "sida.html").read_text(encoding="utf-8")

ITEM = re.compile(
    r'<div class="item"><span class="src">(?P<src>.*?)</span><div class="body">'
    r'<span class="tag[^"]*">(?P<date>.*?)</span>'
    r'<a href="(?P<href>[^"]*)"[^>]*>(?P<title>.*?)</a>(?:<p>(?P<p>.*?)</p>)?</div></div>',
    re.S,
)


def ren(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


artiklar = []
for m in ITEM.finditer(SRC):
    etiketter = re.findall(r'<span class="lang">(.*?)</span>', m["src"])
    kalla = ren(re.sub(r'<span class="lang">.*?</span>', "", m["src"]))
    datum = m["date"].strip()
    artiklar.append({
        "Datum": datum,
        "År": datum[:4] if re.fullmatch(r"\d{4}-\d\d-\d\d", datum) else "okänt",
        "Källa": kalla,
        "Etiketter": ", ".join(etiketter),
        "Rubrik": ren(m["title"]),
        "Sammanfattning": ren(m["p"]),
        "Länk": html.unescape(m["href"]),
    })
artiklar.sort(key=lambda a: a["Datum"], reverse=True)

arkivfil = UT / "oppna_arkiv.json"
oppna = json.loads(arkivfil.read_text(encoding="utf-8")) if arkivfil.exists() else []

per_ar = Counter(a["År"] for a in artiklar)
ar_lista = sorted((k for k in per_ar if k != "okänt"), reverse=True) + (["okänt"] if "okänt" in per_ar else [])

with open(UT / "artiklar.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(artiklar[0].keys()) if artiklar else ["Datum"], delimiter=";")
    w.writeheader()
    w.writerows(artiklar)
print("skrev arkiv/artiklar.csv", len(artiklar))

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
except ImportError:
    print("openpyxl saknas – hoppar över xlsx")
    raise SystemExit(0)

BLA = "1D428E"
rubrikstil = Font(bold=True, color="FFFFFF")
rubrikfyll = PatternFill("solid", fgColor=BLA)
lank = Font(color=BLA, underline="single")


def rubriker(ws, namn, bredder):
    ws.append(namn)
    for i, b in enumerate(bredder, 1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill = rubrikstil, rubrikfyll
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = b
    ws.freeze_panes = "A2"


def lanka(cell, url):
    if url:
        cell.hyperlink = url
        cell.font = lank


wb = Workbook()

ws = wb.active
ws.title = "Per år"
rubriker(ws, ["År", "Antal artiklar"], [10, 16])
for ar in ar_lista:
    ws.append([int(ar) if ar.isdigit() else ar, per_ar[ar]])
ws.append([])
ws.append(["Totalt", len(artiklar)])
ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
ws.cell(row=ws.max_row, column=2).font = Font(bold=True)
ws.append([])
ws.append(["Källa: redaktionella medier via Google Nyheter (tidigast 2003), Expressen TV, Fygstermedia och Weightlifting House."])
ws.append(["Svenska Tyngdlyftningsförbundets egna nyheter och pressmeddelanden ingår inte."])

ws = wb.create_sheet("Artiklar")
kol = ["Datum", "År", "Källa", "Etiketter", "Rubrik", "Sammanfattning", "Länk"]
rubriker(ws, kol, [12, 7, 24, 18, 60, 60, 50])
for a in artiklar:
    ws.append([a[k] for k in kol])
    lanka(ws.cell(row=ws.max_row, column=7), a["Länk"])
ws.auto_filter.ref = f"A1:G{ws.max_row}"

ws = wb.create_sheet("Öppna arkiv")
kol2 = ["år", "arkiv", "typ", "källa", "titel", "beskrivning", "länk", "rättigheter"]
rubriker(ws, ["År", "Arkiv", "Typ", "Institution", "Titel", "Beskrivning", "Länk", "Rättigheter"], [8, 16, 8, 26, 60, 60, 50, 40])
for x in sorted(oppna, key=lambda x: (x.get("år") or "9999", x.get("titel", ""))):
    ws.append([x.get(k, "") for k in kol2])
    lanka(ws.cell(row=ws.max_row, column=7), x.get("länk"))
ws.auto_filter.ref = f"A1:H{ws.max_row}"

ws = wb.create_sheet("Arkiv per årtionde")
rubriker(ws, ["Årtionde", "Bilder", "Film/video", "Ljud", "Text", "Totalt"], [12, 10, 12, 8, 8, 10])
grupper = {}
for x in oppna:
    a = x.get("år") or ""
    dek = f"{a[:3]}0-tal" if a else "okänt"
    t = (x.get("typ") or "").lower()
    t = "bild" if t == "image" else "video" if t in ("video", "movies") else "ljud" if t in ("sound", "audio") else "text"
    grupper.setdefault(dek, Counter())[t] += 1
for dek in sorted(k for k in grupper if k != "okänt") + (["okänt"] if "okänt" in grupper else []):
    g = grupper[dek]
    ws.append([dek, g["bild"], g["video"], g["ljud"], g["text"], sum(g.values())])

wb.save(UT / "tyngdlyftning_i_media.xlsx")
print("skrev arkiv/tyngdlyftning_i_media.xlsx")
