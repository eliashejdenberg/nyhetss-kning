"""Bygger de publicerade filerna från src/sida.html.

src/sida.html är den enda källan (samma innehåll som bevakningssidan på claude.ai).
Skriptet skapar:
  index.html                 hela bevakningssidan
  modul.html                 kompakt lista för inbäddning (?antal=5)
  feed.xml                   RSS: alla medier (utländska märkta med språk)

Kör: python3 build.py
"""
import html
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "https://eliashejdenberg.github.io/nyhetss-kning/"
SRC = (ROOT / "src" / "sida.html").read_text(encoding="utf-8")

ITEM_RE = re.compile(
    r'<div class="item"><span class="src">(?P<src>.*?)</span><div class="body">'
    r'<span class="tag[^"]*">(?P<date>.*?)</span>'
    r'<a href="(?P<href>[^"]*)"[^>]*>(?P<title>.*?)</a>(?:<p>(?P<p>.*?)</p>)?</div></div>',
    re.S,
)


def section(html_text, start_marker, end_marker):
    i = html_text.find(start_marker)
    if i < 0:
        return ""
    j = html_text.find(end_marker, i)
    return html_text[i : j if j > 0 else None]


def items(block):
    out = []
    for m in ITEM_RE.finditer(block):
        d = m["date"].strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue  # t.ex. "Äldre" – utan datum, hoppas över i flöden
        lang = re.findall(r'<span class="lang">(.*?)</span>', m["src"])
        out.append(
            {
                "src": html.unescape(re.sub(r"<[^>]+>", "", re.sub(r'<span class="lang">.*?</span>', "", m["src"]))).strip(),
                "lang": [html.unescape(x) for x in lang],
                "date": d,
                "href": html.unescape(m["href"]),
                "title": html.unescape(re.sub(r"<[^>]+>", "", m["title"])),
                "p": html.unescape(m["p"] or ""),
            }
        )
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


alla = items(section(SRC, 'id="flode"', "</section>"))


# Loggor: logos/<domän>.png hämtas av hamta_loggor.py. Saknas en logga visas
# källans första bokstav i en liten ruta.
def doman(url):
    m = re.match(r"https?://([^/]+)", url or "")
    d = m.group(1).lower() if m else ""
    return d[4:] if d.startswith("www.") else d


def logga(url, kalla):
    d = doman(url)
    for ext in ("png", "ico", "svg", "jpg"):
        if d and (ROOT / "logos" / f"{d}.{ext}").exists():
            return f'<img class="logo" src="logos/{d}.{ext}" alt="" width="16" height="16" loading="lazy">'
    bokstav = html.escape((kalla.strip()[:1] or "?").upper())
    return f'<span class="logo logo-txt" aria-hidden="true">{bokstav}</span>'


LOGGA_CSS = """<style>
.logo{width:16px;height:16px;flex:none;border-radius:3px;vertical-align:-3px;margin-right:6px}
.logo-txt{display:inline-flex;align-items:center;justify-content:center;background:#e9edf5;color:#1d428e;font-size:10px;font-weight:700;line-height:1}
.feed .item .src::before{content:none}
.feed .item .src{display:flex;align-items:center;flex-wrap:wrap;row-gap:2px}
.feed .item .src .logo{vertical-align:0}
</style>"""


def med_loggor(text):
    def ers(m):
        blk = m.group(0)
        href = re.search(r'<a href="([^"]*)"', blk)
        kalla = re.sub(r"<[^>]+>", "", re.sub(r'<span class="lang">.*?</span>', "", m.group(1)))
        return blk.replace('<span class="src">', '<span class="src">' + logga(href.group(1) if href else "", html.unescape(kalla)), 1)
    return re.sub(r'<div class="item"><span class="src">(.*?)</span><div class="body">.*?</div></div>', ers, text, flags=re.S)

HEAD = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
"""


# Skickar sidans höjd till den inbäddande sidan (Sitevision), så att iframen
# kan växa med innehållet i stället för att få en egen rullningslist.
# Mottagaren är inbadda.js.
HOJD_JS = """<script>
(function(){
  var senast = 0;
  function skicka(){
    var h = Math.ceil(document.documentElement.getBoundingClientRect().height);
    if (h === senast) return;
    senast = h;
    try { parent.postMessage({typ: "tyngdlyftning-hojd", hojd: h}, "*"); } catch (e) {}
  }
  window.addEventListener("load", skicka);
  window.addEventListener("resize", skicka);
  if (window.ResizeObserver) new ResizeObserver(skicka).observe(document.documentElement);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(skicka);
  skicka();
})();
</script>"""


# Sidbläddring för hela sidan: visar PER_SIDA artiklar åt gången
# (ändras med ?per=…). Sidnumret står i adressen som #sida-2.
PAGINERING = """<style>
.pager{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:6px;margin-top:4px}
.pager[hidden],.feed > .item[hidden]{display:none}
.pager button{font:inherit;font-size:14px;font-weight:600;min-width:40px;padding:8px 12px;border:1px solid var(--line);background:var(--surface);color:var(--blue);cursor:pointer}
.pager button:hover{border-color:var(--blue)}
.pager button:focus-visible{outline:2px solid var(--yellow);outline-offset:2px}
.pager button[aria-current="page"]{background:var(--blue);border-color:var(--blue);color:#fff}
.pager button:disabled{color:var(--line);border-color:#e6e6e6;cursor:default}
.pager .gap{padding:0 4px;color:var(--muted)}
.pager .info{flex-basis:100%;text-align:center;font-size:13px;color:var(--muted);margin-top:4px}
</style>
<script>
(function(){
  var PER = parseInt(new URLSearchParams(location.search).get("per") || "50", 10) || 50;
  var feed = document.querySelector('section[aria-labelledby="flode"] .feed');
  if (!feed) return;
  var items = Array.prototype.slice.call(feed.querySelectorAll(":scope > .item"));
  var antalSidor = Math.max(1, Math.ceil(items.length / PER));
  var nav = document.createElement("nav");
  nav.className = "pager";
  nav.setAttribute("aria-label", "Sidor");
  feed.parentNode.insertBefore(nav, feed.nextSibling);

  function knapp(text, sida, etikett, aktuell, av){
    var b = document.createElement("button");
    b.type = "button"; b.textContent = text;
    if (etikett) b.setAttribute("aria-label", etikett);
    if (aktuell) b.setAttribute("aria-current", "page");
    if (av) b.disabled = true; else b.addEventListener("click", function(){ visa(sida, true); });
    return b;
  }
  function sidnummer(s){
    // 1 … s-1 s s+1 … sista
    var lista = [], i;
    for (i = 1; i <= antalSidor; i++) {
      if (i === 1 || i === antalSidor || Math.abs(i - s) <= 1) lista.push(i);
      else if (lista[lista.length - 1] !== "…") lista.push("…");
    }
    return lista;
  }
  function visa(s, avAnvandare){
    s = Math.min(Math.max(1, s), antalSidor);
    items.forEach(function(el, i){ el.hidden = Math.floor(i / PER) + 1 !== s; });
    nav.innerHTML = "";
    nav.hidden = antalSidor < 2;
    if (antalSidor > 1) {
      nav.appendChild(knapp("← Föregående", s - 1, "Föregående sida", false, s === 1));
      sidnummer(s).forEach(function(n){
        if (n === "…") { var g = document.createElement("span"); g.className = "gap"; g.textContent = "…"; nav.appendChild(g); }
        else nav.appendChild(knapp(String(n), n, "Sida " + n, n === s, false));
      });
      nav.appendChild(knapp("Nästa →", s + 1, "Nästa sida", false, s === antalSidor));
      var info = document.createElement("span");
      info.className = "info";
      var fran = (s - 1) * PER + 1, till = Math.min(s * PER, items.length);
      info.textContent = "Visar " + fran + "–" + till + " av " + items.length + " artiklar";
      nav.appendChild(info);
    }
    if (avAnvandare) {
      try { history.replaceState(null, "", s > 1 ? "#sida-" + s : location.pathname + location.search); } catch (e) {}
      document.getElementById("flode").scrollIntoView();
      // be den inbäddande sidan rulla upp till modulens början
      try { parent.postMessage({typ: "tyngdlyftning-topp"}, "*"); } catch (e) {}
    }
  }
  var m = /^#sida-(\\d+)$/.exec(location.hash);
  visa(m ? parseInt(m[1], 10) : 1, false);
})();
</script>"""


def write(name, text):
    (ROOT / name).write_text(text, encoding="utf-8")
    print("skrev", name)


# index.html – hela sidan
write("index.html", HEAD + LOGGA_CSS + "\n</head>\n<body>\n" + med_loggor(SRC) + "\n" + PAGINERING + "\n" + HOJD_JS + "\n</body>\n</html>\n")


# RSS-flöden
def rss(name, title, desc, rows):
    now = format_datetime(datetime.now(timezone.utc))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{html.escape(title)}</title>",
        f"<link>{BASE}</link>",
        f'<atom:link href="{BASE}{name}" rel="self" type="application/rss+xml"/>',
        f"<description>{html.escape(desc)}</description>",
        "<language>sv</language>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]
    for r in rows[:30]:
        dt = datetime.strptime(r["date"], "%Y-%m-%d").replace(hour=6, tzinfo=timezone.utc)
        kalla = r["src"] + (f" ({', '.join(r['lang'])})" if r["lang"] else "")
        description = kalla + (" – " + r["p"] if r["p"] else "")
        parts += [
            "<item>",
            f"<title>{html.escape(r['title'])}</title>",
            f"<link>{html.escape(r['href'])}</link>",
            f'<guid isPermaLink="false">{html.escape(r["src"] + "|" + r["title"])}</guid>',
            f"<pubDate>{format_datetime(dt)}</pubDate>",
            f"<source url=\"{BASE}\">{html.escape(kalla)}</source>",
            f"<description>{html.escape(description)}</description>",
            "</item>",
        ]
    parts += ["</channel>", "</rss>", ""]
    write(name, "\n".join(parts))


rss("feed.xml", "Tyngdlyftning i media",
    "Daglig bevakning av svensk tyngdlyftning i svenska och utländska redaktionella medier.", alla)

# modul.html – kompakt lista
li = "\n".join(
    f'<li><span class="d">{r["date"]}</span><span class="s">{logga(r["href"], r["src"])}{html.escape(r["src"])}'
    + "".join(f'<span class="lg">{html.escape(x)}</span>' for x in r["lang"]) + '</span>'
    f'<a href="{html.escape(r["href"])}" target="_blank" rel="noopener">{html.escape(r["title"])}</a></li>'
    for r in alla[:20]
)
updated = re.search(r"Senast uppdaterad <b>(.*?)</b>", SRC)
updated = updated[1] if updated else ""
write("modul.html", HEAD + f"""<title>Tyngdlyftning i media</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>
:root{{--fg:#404040;--muted:#666;--line:#e6e6e6;--blue:#1d428e;--yellow:#f6ca30;
  --font:"Clear Sans","Open Sans",system-ui,-apple-system,"Segoe UI",sans-serif}}
html,body{{margin:0;background:#fff;color:var(--fg);font-family:var(--font);font-size:15px;line-height:1.45}}
.m{{padding:4px 2px}}
h2{{margin:0 0 6px;font-size:1.25rem;font-weight:700;text-transform:uppercase;color:var(--blue);padding-bottom:8px;border-bottom:1px solid #ccc}}
ul{{list-style:none;margin:0;padding:0}}
li{{display:grid;grid-template-columns:auto 1fr;column-gap:8px;padding:10px 0;border-bottom:1px solid var(--line)}}
li[hidden]{{display:none}}
.d{{font-variant-numeric:tabular-nums;color:#000;font-size:14px}}
.s{{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);align-self:center}}
.s{{display:inline-flex;align-items:center;flex-wrap:wrap;gap:0}}
.logo{{width:16px;height:16px;flex:none;border-radius:3px;margin-right:6px}}
.logo-txt{{display:inline-flex;align-items:center;justify-content:center;background:#e9edf5;color:#1d428e;font-size:10px;font-weight:700;line-height:1}}
.lg{{display:inline-block;margin-left:6px;padding:1px 6px;background:var(--yellow);color:#000;font-size:10px;font-weight:700;letter-spacing:.06em}}
a{{grid-column:1/-1;color:var(--blue);font-weight:700;text-decoration:none}}
a:hover,a:focus-visible{{text-decoration:underline}}
a:focus-visible{{outline:2px solid var(--yellow);outline-offset:2px}}
.f{{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-top:10px;font-size:13px;color:var(--muted)}}
.f a{{grid-column:auto;font-weight:600}}
</style>
</head>
<body>
<div class="m">
<h2>Tyngdlyftning i media</h2>
<ul id="l">
{li}
</ul>
<div class="f"><span>Uppdaterad {html.escape(updated)}</span><a href="https://www.tyngdlyftning.com/forbundet/tyngdlyftning-i-media" target="_top">Alla nyheter →</a></div>
</div>
<script>
// ?antal=5 styr hur många rubriker som visas (standard 5)
(function(){{
  var n = parseInt(new URLSearchParams(location.search).get("antal") || "5", 10);
  var li = document.querySelectorAll("#l li");
  for (var i = n; i < li.length; i++) li[i].hidden = true;
}})();
</script>
""" + HOJD_JS + """
</body>
</html>
""")
