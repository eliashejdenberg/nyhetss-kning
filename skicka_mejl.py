"""Mejlar nya artiklar i bevakningen till mottagarna i MAIL_TO.

Körs av GitHub Actions (.github/workflows/morgonmejl.yml) när src/sida.html
ändras, dvs. efter att morgonkörningen har pushat. Jämför med
state/skickade.json och mejlar bara artiklar som inte skickats tidigare.

Miljövariabler (GitHub-secrets, samma upplägg som i story-generator):
  SMTP_SERVER, SMTP_PORT (valfri, 587), SMTP_USERNAME, SMTP_PASSWORD,
  MAIL_FROM (valfri), MAIL_TO (en eller flera adresser, kommaseparerade)

Kör:  python3 skicka_mejl.py            skicka nya artiklar
      python3 skicka_mejl.py --init     markera alla nuvarande artiklar som skickade
      python3 skicka_mejl.py --prov     skriv ut mejlet utan att skicka
      python3 skicka_mejl.py --test     skicka ett testmejl med de 3 senaste artiklarna
                                        (märkt TEST, ändrar inte state/skickade.json)
"""
import html
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "sida.html"
STATE = ROOT / "state" / "skickade.json"
SAMMANFATTNING = ROOT / "state" / "sammanfattning.txt"
SIDA = "https://eliashejdenberg.github.io/nyhetss-kning/"
RAPPORT = SIDA + "arkiv/tyngdlyftning_i_media.xlsx"
BLA, GUL = "#1d428e", "#f6ca30"

ITEM = re.compile(
    r'<div class="item"><span class="src">(?P<src>.*?)</span><div class="body">'
    r'<span class="tag[^"]*">(?P<date>.*?)</span>'
    r'<a href="(?P<href>[^"]*)"[^>]*>(?P<title>.*?)</a>(?:<p>(?P<p>.*?)</p>)?</div></div>',
    re.S,
)


def ren(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def artiklar():
    ut = []
    for m in ITEM.finditer(SRC.read_text(encoding="utf-8")):
        ut.append({
            "lank": html.unescape(m["href"]),
            "datum": m["date"].strip(),
            "kalla": ren(re.sub(r'<span class="lang">.*?</span>', "", m["src"])),
            "etiketter": [ren(x) for x in re.findall(r'<span class="lang">(.*?)</span>', m["src"])],
            "rubrik": ren(m["title"]),
            "text": ren(m["p"]),
        })
    return ut


def las_state():
    return set(json.loads(STATE.read_text(encoding="utf-8"))) if STATE.exists() else None


def spara_state(lankar):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(sorted(lankar), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def bygg_mejl(nya, sammanfattning):
    n = len(nya)
    rubrik = f"Tyngdlyftning i media – {n} {'ny artikel' if n == 1 else 'nya artiklar'} ({date.today().isoformat()})"
    text = [f"{rubrik}\n"]
    rader = []
    for a in nya:
        et = f" [{', '.join(a['etiketter'])}]" if a["etiketter"] else ""
        text.append(f"{a['datum']} · {a['kalla']}{et}\n{a['rubrik']}\n{a['lank']}\n" + (f"{a['text']}\n" if a["text"] else ""))
        etiketter = "".join(
            f'<span style="display:inline-block;margin-left:6px;padding:1px 6px;background:{GUL};color:#000;'
            f'font-size:11px;font-weight:bold;letter-spacing:.05em">{html.escape(e)}</span>' for e in a["etiketter"])
        rader.append(
            f'<tr><td style="padding:14px 0;border-bottom:1px solid #e6e6e6">'
            f'<div style="font-size:13px;color:#666">{html.escape(a["datum"])} · '
            f'<span style="text-transform:uppercase;letter-spacing:.04em;font-weight:bold">{html.escape(a["kalla"])}</span>{etiketter}</div>'
            f'<div style="margin-top:4px;font-size:17px;font-weight:bold"><a href="{html.escape(a["lank"])}" '
            f'style="color:{BLA};text-decoration:none">{html.escape(a["rubrik"])}</a></div>'
            + (f'<div style="margin-top:4px;font-size:14px;color:#404040">{html.escape(a["text"])}</div>' if a["text"] else "")
            + "</td></tr>")
    sam_html = ""
    if sammanfattning:
        text.append("\nFrån morgonkörningen:\n" + sammanfattning)
        sam_html = (f'<div style="margin-top:20px;padding:12px 14px;background:#fafafa;border-left:4px solid {GUL};'
                    f'font-size:13px;color:#404040;white-space:pre-wrap">{html.escape(sammanfattning)}</div>')
    text.append(f"\nAlla artiklar: {SIDA}\nRapport (Excel): {RAPPORT}")
    html_body = f"""\
<div style="font-family:'Open Sans',Arial,sans-serif;max-width:640px;color:#404040">
<h2 style="margin:0 0 8px;color:{BLA};text-transform:uppercase;font-size:20px;border-bottom:1px solid #ccc;padding-bottom:8px">Tyngdlyftning i media</h2>
<p style="margin:0 0 4px;font-size:14px">{n} {'ny artikel' if n == 1 else 'nya artiklar'} sedan förra utskicket.</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{''.join(rader)}</table>
{sam_html}
<p style="margin-top:20px;font-size:13px"><a href="{SIDA}" style="color:{BLA}">Alla artiklar</a> ·
<a href="{RAPPORT}" style="color:{BLA}">Rapport (Excel)</a></p>
</div>"""
    return rubrik, "\n".join(text), html_body


def skicka(rubrik, text, html_body):
    raw = os.environ.get("MAIL_TO") or ""
    mottagare = [a.strip() for a in raw.replace(";", ",").split(",") if a.strip()]
    if not mottagare:
        sys.exit("MAIL_TO saknas – lägg till secret MAIL_TO med en eller flera adresser.")
    user = os.environ["SMTP_USERNAME"]
    msg = EmailMessage()
    msg["Subject"] = rubrik
    msg["From"] = formataddr((os.environ.get("MAIL_FROM_NAME") or "Tyngdlyftning i media",
                              os.environ.get("MAIL_FROM") or user))
    msg["To"] = ", ".join(mottagare)
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    host = os.environ["SMTP_SERVER"]
    port = int(os.environ.get("SMTP_PORT") or 587)
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
            s.login(user, os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(user, os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    print("Skickade mejl till", len(mottagare), "mottagare")


def main():
    alla = artiklar()
    lankar = {a["lank"] for a in alla}
    if "--init" in sys.argv:
        spara_state(lankar)
        print(f"Markerade {len(lankar)} artiklar som skickade.")
        return
    if "--test" in sys.argv:
        senaste = sorted((a for a in alla if re.fullmatch(r"\d{4}-\d\d-\d\d", a["datum"])),
                         key=lambda a: a["datum"], reverse=True)[:3]
        rubrik, text, html_body = bygg_mejl(senaste, "Det här är ett testutskick med de tre senaste artiklarna i bevakningen.")
        skicka("TEST – " + rubrik, text, html_body)
        return
    skickade = las_state()
    if skickade is None:
        # första körningen: skicka inte hela arkivet
        spara_state(lankar)
        print("Ingen tidigare lista – markerade alla nuvarande artiklar som skickade, inget mejl.")
        return
    nya = [a for a in alla if a["lank"] not in skickade]
    sammanfattning = SAMMANFATTNING.read_text(encoding="utf-8").strip() if SAMMANFATTNING.exists() else ""
    if not nya:
        print("Inga nya artiklar – inget mejl.")
        return
    rubrik, text, html_body = bygg_mejl(nya, sammanfattning)
    if "--prov" in sys.argv:
        print(rubrik, "\n", text)
        return
    skicka(rubrik, text, html_body)
    spara_state(skickade | {a["lank"] for a in nya})


if __name__ == "__main__":
    main()
