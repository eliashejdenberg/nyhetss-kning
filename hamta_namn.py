"""Hämtar aktuella namn på förbundsstyrelse, personal och landslagsstaber från
tyngdlyftning.com och uppdaterar avsnittet "forbund" i sokord.json.

Avsnittet "lyftare" i sokord.json ändras inte av skriptet (det underhålls av
den dagliga bevakningen och för hand).

Bara namn och roll sparas – inga telefonnummer eller e-postadresser.

Kör: python3 -I hamta_namn.py        (skriver ut vilka namn som tillkommit/försvunnit)
"""
import html
import json
import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIL = ROOT / "sokord.json"
BAS = "https://www.tyngdlyftning.com"
SIDOR = {
    "/forbundet/kontakt/forbundsstyrelsen": "Förbundsstyrelsen",
    "/forbundet/kontakt/personal": "Personal",
    "/landslaget/seniorer": "Landslagsstab senior",
    "/landslaget/ungdom--junior": "Landslagsstab ungdom/junior",
    "/landslaget/elitmiljo-eth": "Elitmiljö (ETH)",
    "/landslaget/medicinskt-team": "Medicinskt team",
}
NAMN = r"[A-ZÅÄÖÉ][a-zåäöéüA-Z]+(?:-[A-ZÅÄÖ][a-zåäö]+)?(?: [A-ZÅÄÖÉ][a-zåäöéü]+(?:-[A-ZÅÄÖ][a-zåäö]+)?){1,2}"


def text(path):
    r = subprocess.run(["curl", "-sSL", "--max-time", "25", BAS + path], capture_output=True)
    t = r.stdout.decode("utf-8", "ignore")
    t = re.sub(r"<(script|style|nav|header|footer).*?</\1>", "", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " | ", t))
    t = re.sub(r"\s+", " ", t)
    i, j = t.find("Hall of Fame"), t.find("Dela på Facebook")
    return t[i if i > 0 else 0 : j if j > 0 else None]


def personer(sida, t):
    ut = []
    # "Namn, roll, telefon" (styrelse, personal)
    for m in re.finditer(rf"\| ({NAMN}), ([^,|]+?)(?:,|\|)", t):
        ut.append((m.group(1), m.group(2).strip()))
    # "Namn - roll" (landslagsstaber, medicinskt team)
    for m in re.finditer(rf"\| ({NAMN}) - ([^|]+?) \|", t):
        ut.append((m.group(1), m.group(2).strip()))
    # löptext: "leds av Patric Bettembourg som huvudtränare och Tom Söderholm som assisterande tränare"
    for m in re.finditer(rf"({NAMN}) som ([a-zåäö ]+?tränare)", t):
        ut.append((m.group(1), m.group(2).strip()))
    return ut


def main():
    data = json.loads(FIL.read_text(encoding="utf-8")) if FIL.exists() else {"lyftare": [], "forbund": []}
    gamla = {p["namn"] for p in data.get("forbund", [])}
    nya = {}
    for path, sida in SIDOR.items():
        t = text(path)
        if not t.strip():
            print("kunde inte läsa", path)
            continue
        for namn, roll in personer(sida, t):
            if namn.split()[0] in {"Coacher", "Svenska", "Elitmiljö", "Medicinskt", "Ansvarar"}:
                continue
            post = nya.setdefault(namn, {"namn": namn, "roller": [], "kalla": BAS + path})
            r = f"{sida}: {roll}"
            if r not in post["roller"]:
                post["roller"].append(r)
    if not nya:
        print("Inga namn hittades – sidorna kan ha bytt utseende. sokord.json lämnas orörd.")
        return
    data["forbund"] = sorted(nya.values(), key=lambda p: p["namn"])
    data["forbund_uppdaterad"] = date.today().isoformat()
    FIL.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tillkom = sorted(set(nya) - gamla)
    forsvann = sorted(gamla - set(nya))
    print(f"{len(nya)} personer i förbundet.")
    print("TILLKOMNA:", ", ".join(tillkom) or "inga")
    print("BORTTAGNA:", ", ".join(forsvann) or "inga")


if __name__ == "__main__":
    main()
