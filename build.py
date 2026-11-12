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


# Filter (år, källa, svenska/internationella, typ, fritext, sortering) och
# sidbläddring för hela sidan.
PAGINERING = """<style>
.filter{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px 12px;margin:0 0 14px;padding:14px;background:var(--soft);border:1px solid #e6e6e6}
.filter label{display:flex;flex-direction:column;gap:4px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.filter .sok{grid-column:1/-1}
.filter input,.filter select{font:inherit;font-size:15px;text-transform:none;letter-spacing:0;font-weight:400;color:var(--fg);background:#fff;border:1px solid var(--line);border-radius:0;padding:8px 10px;min-height:40px;box-sizing:border-box;width:100%}
.filter input:focus-visible,.filter select:focus-visible,.filter button:focus-visible{outline:2px solid var(--yellow);outline-offset:1px;border-color:var(--blue)}
.filter .rad{grid-column:1/-1;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;font-size:14px;color:var(--fg)}
.filter .antal{font-weight:600}
.filter button{font:inherit;font-size:14px;font-weight:600;padding:6px 12px;border:1px solid var(--blue);background:#fff;color:var(--blue);cursor:pointer}
.filter button:hover{background:var(--blue);color:#fff}
.filter button[hidden]{display:none}
.tomt{padding:24px 0;text-align:center;color:var(--muted)}
.tomt[hidden]{display:none}
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
// Filter och sidbläddring för hela sidan.
// ?per=50 styr antal per sida. Valda filter och sida sparas i adressen,
// t.ex. #ar=2024&media=intl&sida=2, så att en filtrerad vy kan delas som länk.
(function(){
  var PER = parseInt(new URLSearchParams(location.search).get("per") || "50", 10) || 50;
  var SPRAK = ["ENGELSKA", "NORSKA", "DANSKA", "FINSKA"];
  var feed = document.querySelector('section[aria-labelledby="flode"] .feed');
  if (!feed) return;
  var alla = Array.prototype.slice.call(feed.querySelectorAll(":scope > .item")).map(function(el, i){
    var src = el.querySelector(".src"), tag = el.querySelector(".tag"), a = el.querySelector(".body a");
    var etiketter = Array.prototype.map.call(src.querySelectorAll(".lang"), function(s){ return s.textContent.trim().toUpperCase(); });
    var kalla = Array.prototype.filter.call(src.childNodes, function(n){ return n.nodeType === 3; })
      .map(function(n){ return n.textContent; }).join("").trim();
    var datum = (tag && tag.textContent.trim()) || "";
    return {
      el: el, i: i, kalla: kalla, datum: datum,
      ar: /^\\d{4}-/.test(datum) ? datum.slice(0, 4) : "aldre",
      intl: etiketter.some(function(e){ return SPRAK.indexOf(e) >= 0; }),
      video: etiketter.indexOf("VIDEO") >= 0, ljud: etiketter.indexOf("LJUD") >= 0,
      text: (el.textContent || "").toLowerCase()
    };
  });

  // --- filterpanel ---
  function el(tagg, attr, barn){
    var e = document.createElement(tagg);
    for (var k in attr || {}) { if (k === "text") e.textContent = attr[k]; else e.setAttribute(k, attr[k]); }
    (barn || []).forEach(function(b){ e.appendChild(b); });
    return e;
  }
  function lista(namn, etikett, val){
    var s = el("select", {name: namn});
    val.forEach(function(v){ s.appendChild(el("option", {value: v[0], text: v[1]})); });
    return {lbl: el("label", {}, [document.createTextNode(etikett), s]), sel: s};
  }
  function rakna(f){ var c = {}; alla.forEach(function(x){ var k = f(x); c[k] = (c[k] || 0) + 1; }); return c; }
  var perAr = rakna(function(x){ return x.ar; });
  var arVal = [["", "Alla år"]].concat(Object.keys(perAr).filter(function(a){ return a !== "aldre"; }).sort().reverse()
    .map(function(a){ return [a, a + " (" + perAr[a] + ")"]; }));
  if (perAr.aldre) arVal.push(["aldre", "Utan datum (" + perAr.aldre + ")"]);
  var perKalla = rakna(function(x){ return x.kalla; });
  var kallVal = [["", "Alla källor"]].concat(Object.keys(perKalla).sort(function(a, b){ return a.localeCompare(b, "sv"); })
    .map(function(k){ return [k, k + " (" + perKalla[k] + ")"]; }));
  var antIntl = alla.filter(function(x){ return x.intl; }).length;

  var sok = el("input", {type: "search", name: "q", placeholder: "Sök på rubrik, namn, källa …", autocomplete: "off"});
  var f = {
    q: sok,
    ar: lista("ar", "År", arVal),
    kalla: lista("kalla", "Källa", kallVal),
    media: lista("media", "Medier", [["", "Alla medier"], ["sv", "Svenska medier (" + (alla.length - antIntl) + ")"], ["intl", "Internationella medier (" + antIntl + ")"]]),
    typ: lista("typ", "Typ", [["", "Alla typer"], ["video", "Video"], ["ljud", "Ljud"], ["text", "Endast text"]]),
    sort: lista("sort", "Sortera", [["", "Nyast först"], ["aldst", "Äldst först"], ["kalla", "Källa A–Ö"]])
  };
  var antal = el("span", {"class": "antal", "aria-live": "polite"});
  var rensa = el("button", {type: "button", text: "Rensa filter"});
  var panel = el("form", {"class": "filter", role: "search", "aria-label": "Filtrera artiklar"}, [
    el("label", {"class": "sok"}, [document.createTextNode("Sök"), sok]),
    f.ar.lbl, f.kalla.lbl, f.media.lbl, f.typ.lbl, f.sort.lbl,
    el("div", {"class": "rad"}, [antal, rensa])
  ]);
  panel.addEventListener("submit", function(e){ e.preventDefault(); });
  feed.parentNode.insertBefore(panel, feed);
  var tomt = el("p", {"class": "tomt", text: "Inga artiklar matchar filtret."});
  feed.parentNode.insertBefore(tomt, feed.nextSibling);
  var nav = el("nav", {"class": "pager", "aria-label": "Sidor"});
  feed.parentNode.insertBefore(nav, tomt.nextSibling);

  function varde(k){ return k === "q" ? sok.value.trim() : f[k].sel.value; }
  function satt(k, v){ if (k === "q") sok.value = v; else { f[k].sel.value = v; if (f[k].sel.value !== v) f[k].sel.value = ""; } }
  var NYCKLAR = ["q", "ar", "kalla", "media", "typ", "sort"];

  var urval = alla;
  function filtrera(){
    var q = varde("q").toLowerCase(), ar = varde("ar"), kalla = varde("kalla"), media = varde("media"), typ = varde("typ"), sort = varde("sort");
    var ord = q.split(/\\s+/).filter(Boolean);
    urval = alla.filter(function(x){
      if (ar && x.ar !== ar) return false;
      if (kalla && x.kalla !== kalla) return false;
      if (media === "sv" && x.intl) return false;
      if (media === "intl" && !x.intl) return false;
      if (typ === "video" && !x.video) return false;
      if (typ === "ljud" && !x.ljud) return false;
      if (typ === "text" && (x.video || x.ljud)) return false;
      for (var i = 0; i < ord.length; i++) if (x.text.indexOf(ord[i]) < 0) return false;
      return true;
    });
    var nyckel = function(x){ return x.ar === "aldre" ? "0000" : x.datum; };
    urval.sort(function(a, b){
      if (sort === "kalla") return a.kalla.localeCompare(b.kalla, "sv") || (nyckel(b) < nyckel(a) ? -1 : nyckel(b) > nyckel(a) ? 1 : a.i - b.i);
      if (sort === "aldst") return nyckel(a) < nyckel(b) ? -1 : nyckel(a) > nyckel(b) ? 1 : b.i - a.i;
      return a.i - b.i;  // sidan är redan sorterad med nyaste först
    });
    var aktiv = NYCKLAR.some(function(k){ return varde(k); });
    rensa.hidden = !aktiv;
    antal.textContent = (aktiv ? urval.length + " av " + alla.length : alla.length) + " artiklar";
    tomt.hidden = urval.length > 0;
    // lägg artiklarna i vald ordning
    var frag = document.createDocumentFragment();
    alla.forEach(function(x){ x.el.hidden = true; });
    urval.forEach(function(x){ frag.appendChild(x.el); });
    alla.forEach(function(x){ if (urval.indexOf(x) < 0) frag.appendChild(x.el); });
    feed.appendChild(frag);
  }

  var sida = 1;
  function antalSidor(){ return Math.max(1, Math.ceil(urval.length / PER)); }
  function knapp(text, s, etikett, aktuell, av){
    var b = el("button", {type: "button", text: text});
    if (etikett) b.setAttribute("aria-label", etikett);
    if (aktuell) b.setAttribute("aria-current", "page");
    if (av) b.disabled = true; else b.addEventListener("click", function(){ visa(s, true); });
    return b;
  }
  function sidnummer(s, n){
    var ut = [], i;
    for (i = 1; i <= n; i++) {
      if (i === 1 || i === n || Math.abs(i - s) <= 1) ut.push(i);
      else if (ut[ut.length - 1] !== "…") ut.push("…");
    }
    return ut;
  }
  function spara(){
    var p = new URLSearchParams();
    NYCKLAR.forEach(function(k){ if (varde(k)) p.set(k, varde(k)); });
    if (sida > 1) p.set("sida", sida);
    var h = p.toString();
    try { history.replaceState(null, "", h ? "#" + h : location.pathname + location.search); } catch (e) {}
  }
  function visa(s, avAnvandare){
    var n = antalSidor();
    sida = Math.min(Math.max(1, s), n);
    urval.forEach(function(x, i){ x.el.hidden = Math.floor(i / PER) + 1 !== sida; });
    nav.innerHTML = "";
    nav.hidden = n < 2;
    if (n > 1) {
      nav.appendChild(knapp("← Föregående", sida - 1, "Föregående sida", false, sida === 1));
      sidnummer(sida, n).forEach(function(k){
        if (k === "…") nav.appendChild(el("span", {"class": "gap", text: "…"}));
        else nav.appendChild(knapp(String(k), k, "Sida " + k, k === sida, false));
      });
      nav.appendChild(knapp("Nästa →", sida + 1, "Nästa sida", false, sida === n));
      var fran = (sida - 1) * PER + 1, till = Math.min(sida * PER, urval.length);
      nav.appendChild(el("span", {"class": "info", text: "Visar " + fran + "–" + till + " av " + urval.length + " artiklar"}));
    }
    spara();
    if (avAnvandare) {
      document.getElementById("flode").scrollIntoView();
      // be den inbäddande sidan rulla upp till modulens början
      try { parent.postMessage({typ: "tyngdlyftning-topp"}, "*"); } catch (e) {}
    }
  }

  var vantar;
  function andrat(){ filtrera(); visa(1, false); }
  sok.addEventListener("input", function(){ clearTimeout(vantar); vantar = setTimeout(andrat, 200); });
  ["ar", "kalla", "media", "typ", "sort"].forEach(function(k){ f[k].sel.addEventListener("change", andrat); });
  rensa.addEventListener("click", function(){ NYCKLAR.forEach(function(k){ satt(k, ""); }); andrat(); sok.focus(); });

  // läs filter och sida från adressen (#ar=2024&sida=2, eller äldre #sida-2)
  var h = location.hash.replace(/^#/, ""), start = 1, gammal = /^sida-(\\d+)$/.exec(h);
  if (gammal) start = parseInt(gammal[1], 10);
  else if (h) {
    var p = new URLSearchParams(h);
    NYCKLAR.forEach(function(k){ if (p.get(k)) satt(k, p.get(k)); });
    start = parseInt(p.get("sida") || "1", 10) || 1;
  }
  filtrera();
  visa(start, false);
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


# rullande.html – nyhetsrulle i TV-stil med de senaste artiklarna
def rull_post(r):
    tag = "".join(f'<span class="lg">{html.escape(x)}</span>' for x in r["lang"])
    return (f'<a class="p" href="{html.escape(r["href"])}" target="_blank" rel="noopener">'
            f'<span class="s">{logga(r["href"], r["src"])}{html.escape(r["src"])}{tag}</span>'
            f'<span class="t">{html.escape(r["title"])}</span></a>')


rull = "".join(rull_post(r) for r in alla[:10])
write("rullande.html", HEAD + f"""<title>Tyngdlyftning i media – nyhetsrulle</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>
:root{{--blue:#1d428e;--blue2:#16336f;--yellow:#f6ca30;
  --font:"Clear Sans","Open Sans",system-ui,-apple-system,"Segoe UI",sans-serif}}
html,body{{margin:0;background:var(--blue);font-family:var(--font)}}
.r{{display:flex;align-items:stretch;height:48px;background:var(--blue);color:#fff;overflow:hidden}}
.etikett{{flex:none;display:flex;align-items:center;gap:8px;padding:0 14px;background:var(--yellow);color:#000;
  font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;text-decoration:none;white-space:nowrap}}
.etikett:hover,.etikett:focus-visible{{text-decoration:underline}}
.kort{{display:none}}
.fonster{{flex:1;min-width:0;overflow:hidden;position:relative;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 24px,#000 calc(100% - 24px),transparent);
  mask-image:linear-gradient(90deg,transparent,#000 24px,#000 calc(100% - 24px),transparent)}}
.band{{display:flex;width:max-content;height:100%;animation:rulla var(--tid,80s) linear infinite}}
.grupp{{display:flex;align-items:center;flex:none}}
.r:hover .band,.r:focus-within .band,.r.paus .band{{animation-play-state:paused}}
@keyframes rulla{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.p{{display:inline-flex;align-items:center;gap:10px;padding:0 22px;height:100%;color:#fff;text-decoration:none;white-space:nowrap;font-size:15px}}
.p::after{{content:"";width:6px;height:6px;background:var(--yellow);margin-left:22px;transform:rotate(45deg)}}
.p:hover .t,.p:focus-visible .t{{text-decoration:underline}}
.p:focus-visible{{outline:2px solid var(--yellow);outline-offset:-4px}}
.s{{display:inline-flex;align-items:center;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#c9d4ec}}
.t{{font-weight:600}}
.logo{{width:16px;height:16px;flex:none;border-radius:3px;margin-right:6px;background:#fff}}
.logo-txt{{display:inline-flex;align-items:center;justify-content:center;background:#e9edf5;color:#1d428e;font-size:10px;font-weight:700;line-height:1}}
.lg{{display:inline-block;margin-left:6px;padding:1px 6px;background:var(--yellow);color:#000;font-size:10px;font-weight:700;letter-spacing:.06em}}
.knapp{{flex:none;width:44px;border:0;background:var(--blue2);color:#fff;font-size:15px;cursor:pointer;font-family:inherit}}
.knapp:hover{{background:#0f2552}}
.knapp:focus-visible{{outline:2px solid var(--yellow);outline-offset:-3px}}
/* ?tema=ljus – vit bakgrund, blå text, blå etikett */
html.ljus,html.ljus body{{background:#fff}}
.ljus .r{{background:#fff;color:var(--blue);box-shadow:inset 0 1px 0 #e6e6e6,inset 0 -1px 0 #e6e6e6}}
.ljus .etikett{{background:var(--blue);color:#fff}}
.ljus .p{{color:var(--blue)}}
.ljus .p::after{{background:var(--blue)}}
.ljus .s{{color:#5a6b8c}}
.ljus .logo-txt{{background:#e9edf5}}
.ljus .p:focus-visible{{outline-color:var(--blue)}}
.ljus .knapp{{background:#e9edf5;color:var(--blue)}}
.ljus .knapp:hover{{background:#d5ddec}}
.ljus .knapp:focus-visible{{outline-color:var(--blue)}}
@media (max-width:560px){{.etikett .lang{{display:none}}.etikett .kort{{display:inline}}.etikett{{padding:0 10px}}.p{{font-size:14px}}}}
@media (prefers-reduced-motion:reduce){{
  .band{{animation:none}} .grupp+.grupp{{display:none}}
  .fonster{{overflow-x:auto;-webkit-mask-image:none;mask-image:none}} .knapp{{display:none}}
}}
</style>
</head>
<body>
<div class="r" id="r" role="region" aria-label="Tyngdlyftning i media – senaste artiklarna">
<a class="etikett" href="https://www.tyngdlyftning.com/forbundet/tyngdlyftning-i-media" target="_top"><span class="lang">Tyngdlyftning i media</span><span class="kort" aria-hidden="true">I media</span><span aria-hidden="true">›</span></a>
<div class="fonster"><div class="band" id="band"><div class="grupp">{rull}</div><div class="grupp" aria-hidden="true">{rull}</div></div></div>
<button class="knapp" id="knapp" type="button" aria-label="Pausa nyhetsrullen" aria-pressed="false">❚❚</button>
</div>
<script>
// ?antal=10 (antal artiklar), ?hastighet=70 (pixlar per sekund), ?tema=ljus (vit bakgrund)
(function(){{
  var q = new URLSearchParams(location.search);
  if (q.get("tema") === "ljus") document.documentElement.classList.add("ljus");
  var n = parseInt(q.get("antal") || "10", 10), v = parseFloat(q.get("hastighet") || "70");
  document.querySelectorAll(".grupp").forEach(function(g, gi){{
    g.querySelectorAll(".p").forEach(function(p, i){{
      if (i >= n) p.remove(); else if (gi) p.tabIndex = -1;
    }});
  }});
  function tid(){{
    var g = document.querySelector(".grupp");
    document.getElementById("band").style.setProperty("--tid", Math.max(10, g.offsetWidth / v) + "s");
  }}
  tid(); addEventListener("resize", tid);
  if (document.fonts) document.fonts.ready.then(tid);
  var r = document.getElementById("r"), k = document.getElementById("knapp");
  k.addEventListener("click", function(){{
    var p = r.classList.toggle("paus");
    k.textContent = p ? "▶" : "❚❚";
    k.setAttribute("aria-pressed", p ? "true" : "false");
    k.setAttribute("aria-label", p ? "Starta nyhetsrullen" : "Pausa nyhetsrullen");
  }});
}})();
</script>
""" + HOJD_JS + """
</body>
</html>
""")
