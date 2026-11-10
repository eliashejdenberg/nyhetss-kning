/*
 * Låter iframes med Tyngdlyftning i media växa med innehållet.
 * Lägg skriptet en gång på sidan i Sitevision, efter iframen/iframarna:
 *   <script src="https://eliashejdenberg.github.io/nyhetss-kning/inbadda.js"></script>
 * Fungerar för både modul.html och hela sidan, även om båda finns på samma sida.
 */
(function () {
  var URSPRUNG = "https://eliashejdenberg.github.io";

  function iframes() {
    return document.querySelectorAll('iframe[src^="' + URSPRUNG + '/nyhetss-kning/"]');
  }

  // Ingen egen rullningslist i iframen; höjden styrs av innehållet.
  function forbered() {
    var lista = iframes();
    for (var i = 0; i < lista.length; i++) {
      lista[i].setAttribute("scrolling", "no");
      lista[i].style.overflow = "hidden";
      lista[i].style.border = "0";
      lista[i].style.width = "100%";
    }
  }

  window.addEventListener("message", function (e) {
    if (e.origin !== URSPRUNG || !e.data || e.data.typ !== "tyngdlyftning-hojd") return;
    var h = parseInt(e.data.hojd, 10);
    if (!(h > 0)) return;
    var lista = iframes();
    for (var i = 0; i < lista.length; i++) {
      if (lista[i].contentWindow === e.source) lista[i].style.height = h + "px";
    }
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", forbered);
  else forbered();
})();
