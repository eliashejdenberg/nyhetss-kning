/*
 * Låter iframes med Tyngdlyftning i media växa med innehållet.
 * Lägg skriptet en gång på sidan i Sitevision, efter iframen/iframarna:
 *   <script src="https://eliashejdenberg.github.io/nyhetss-kning/inbadda.js"></script>
 * Fungerar för både modul.html och hela sidan, även om båda finns på samma sida.
 * Rullningen i iframen stängs av först när rätt höjd har satts, så att
 * innehållet aldrig klipps av om något går fel.
 */
(function () {
  var URSPRUNG = "https://eliashejdenberg.github.io";

  window.addEventListener("message", function (e) {
    if (e.origin !== URSPRUNG || !e.data) return;
    if (e.data.typ === "tyngdlyftning-topp") {
      // Byte av sida i listan: rulla upp till modulens början.
      var alla = document.getElementsByTagName("iframe");
      for (var j = 0; j < alla.length; j++) {
        if (alla[j].contentWindow === e.source) alla[j].scrollIntoView({ behavior: "smooth", block: "start" });
      }
      return;
    }
    if (e.data.typ !== "tyngdlyftning-hojd") return;
    var h = parseInt(e.data.hojd, 10);
    if (!(h > 0)) return;
    var lista = document.getElementsByTagName("iframe");
    for (var i = 0; i < lista.length; i++) {
      var f = lista[i];
      if (f.contentWindow !== e.source) continue;
      f.style.height = h + "px";
      f.style.border = "0";
      f.style.width = "100%";
      f.style.overflow = "hidden";
      f.setAttribute("scrolling", "no");
    }
  });
})();
