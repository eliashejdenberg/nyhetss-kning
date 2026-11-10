# Tyngdlyftning i media

Daglig bevakning av olympisk tyngdlyftning i svenska och internationella redaktionella medier.
Svenska Tyngdlyftningsförbundets eget material ingår inte.

Uppdateras automatiskt varje morgon cirka 06:47.

## Adresser

| Fil | Adress | Används till |
|---|---|---|
| Hela sidan | https://eliashejdenberg.github.io/nyhetss-kning/ | iframe i Sitevision, eller länk |
| Kompakt modul | https://eliashejdenberg.github.io/nyhetss-kning/modul.html?antal=5 | iframe i Sitevision |
| RSS, alla medier | https://eliashejdenberg.github.io/nyhetss-kning/feed.xml | RSS-modulen i Sitevision |

## Så fungerar det

- `src/sida.html` är källan. Den uppdateras av den dagliga bevakningen.
- `python3 build.py` bygger `index.html`, `modul.html` och `feed.xml` från källan.
- Ändra inte de byggda filerna för hand; de skrivs över vid nästa körning.

## Inbäddning i Sitevision utan rullningslist

Iframen växer automatiskt med innehållet om sidan också laddar `inbadda.js` en gång:

```html
<iframe src="https://eliashejdenberg.github.io/nyhetss-kning/modul.html?antal=5" title="Tyngdlyftning i media" style="width:100%;height:500px;border:0"></iframe>
<script src="https://eliashejdenberg.github.io/nyhetss-kning/inbadda.js"></script>
```

Höjden i `style` gäller bara tills sidan laddat. Samma skript fungerar för hela sidan (`/nyhetss-kning/`) och för flera iframes på samma sida.
