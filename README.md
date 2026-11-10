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
