# Tyngdlyftning i media

Daglig bevakning av olympisk tyngdlyftning i svenska och internationella redaktionella medier.
Svenska Tyngdlyftningsförbundets eget material ingår inte.

Uppdateras automatiskt varje morgon cirka 06:47.

## Adresser

| Fil | Adress | Används till |
|---|---|---|
| Hela sidan | https://eliashejdenberg.github.io/nyhetss-kning/ | iframe i Sitevision, eller länk |
| Kompakt modul | https://eliashejdenberg.github.io/nyhetss-kning/modul.html?antal=5 | iframe i Sitevision |
| Excel: antal per år + alla länkar | https://eliashejdenberg.github.io/nyhetss-kning/arkiv/tyngdlyftning_i_media.xlsx | ladda ner |
| CSV: alla artiklar | https://eliashejdenberg.github.io/nyhetss-kning/arkiv/artiklar.csv | ladda ner |
| Nyhetsrulle (TV-stil) | https://eliashejdenberg.github.io/nyhetss-kning/rullande.html | iframe i Sitevision, höjd 48 px |
| RSS, alla medier | https://eliashejdenberg.github.io/nyhetss-kning/feed.xml | RSS-modulen i Sitevision |

## Så fungerar det

- `src/sida.html` är källan. Den uppdateras av den dagliga bevakningen.
- `python3 hamta_loggor.py` hämtar loggor (favicons) för nya mediehus till `logos/`. Källor utan logga visas med sin första bokstav.
- `python3 build.py` bygger `index.html`, `modul.html`, `rullande.html` och `feed.xml` från källan.
- `python3 bygg_rapport.py` bygger `arkiv/tyngdlyftning_i_media.xlsx` (antal per år, alla artiklar, fynd i öppna arkiv) och `arkiv/artiklar.csv`.
- `arkiv/oppna_arkiv.json` innehåller bilder, film och ljud från öppna arkiv (Europeana, Internet Archive, Filmarkivet.se, Sveriges Radio).
- Ändra inte de byggda filerna för hand; de skrivs över vid nästa körning.

## Inbäddning i Sitevision utan rullningslist

Iframen växer automatiskt med innehållet om sidan också laddar `inbadda.js` en gång:

```html
<iframe src="https://eliashejdenberg.github.io/nyhetss-kning/modul.html?antal=5" title="Tyngdlyftning i media" style="width:100%;height:500px;border:0"></iframe>
<script src="https://eliashejdenberg.github.io/nyhetss-kning/inbadda.js"></script>
```

Höjden i `style` gäller bara tills sidan laddat. När man byter sida i listan rullar Sitevision-sidan upp till modulens början. Samma skript fungerar för hela sidan (`/nyhetss-kning/`) och för flera iframes på samma sida.

## Nyhetsrulle

`rullande.html` är ett rullande band med de 10 senaste artiklarna, som nyhetsrullen längst ner i TV-nyheter. Det stannar när man håller muspekaren över det och har en pausknapp. Den som har valt minskade animationer i sin dator får en lista som man själv bläddrar i sidled. `?antal=` ändrar antalet artiklar och `?hastighet=` farten i pixlar per sekund (standard 70). `?tema=ljus` ger vit bakgrund med blå text och blå etikett: `rullande.html?tema=ljus`.

```html
<iframe src="https://eliashejdenberg.github.io/nyhetss-kning/rullande.html" title="Tyngdlyftning i media – senaste artiklarna" style="width:100%;height:48px;border:0;display:block" scrolling="no"></iframe>
```

## Filter

Överst på hela sidan finns fritextsök och filter för år, källa, svenska/internationella medier och typ (video, ljud, endast text), plus sortering (nyast, äldst, källa A–Ö). Valen sparas i adressen, så en filtrerad vy kan delas som länk, t.ex. `https://eliashejdenberg.github.io/nyhetss-kning/#ar=2024&media=sv`.

## Sidbläddring

Hela sidan visar 50 artiklar per sida med knappar för att bläddra. Antalet ändras med `?per=`, t.ex. `https://eliashejdenberg.github.io/nyhetss-kning/?per=25`. Bläddringen visas bara när det finns fler artiklar än så. Den dagliga bevakningen tar inte bort gamla artiklar, så listan fungerar som arkiv.

## Sökord

`sokord.json` innehåller namnen som den dagliga bevakningen söker på:

- `lyftare` – svenska tyngdlyftare (underhålls av bevakningen och för hand).
- `forbund` – förbundsstyrelse, personal, landslagsstaber, ETH och medicinskt team. Uppdateras varje kvartal av `hamta_namn.py`, som läser tyngdlyftning.com. Bara namn och roll sparas.

## Mejlutskick (GitHub Actions)

När morgonkörningen pushar en uppdaterad `src/sida.html` startar `.github/workflows/morgonmejl.yml`, som mejlar artiklar som inte skickats tidigare (`state/skickade.json`) till mottagarna i `MAIL_TO`. Samma upplägg som i story-generator.

Secrets (Settings → Secrets and variables → Actions):
- `SMTP_SERVER`, `SMTP_USERNAME`, `SMTP_PASSWORD` – samma som i story-generator
- `SMTP_PORT` (valfri, standard 587) och `MAIL_FROM` (valfri)
- `MAIL_TO` – mottagare, kommaseparerade. Ligger som secret eftersom repot är publikt.

Inga nya artiklar ger inget mejl. Morgonkörningens sammanfattning (t.ex. bortsorterade artiklar) skrivs till `state/sammanfattning.txt` och tas med i mejlet.
Testa: Actions → Mejla nya artiklar → Run workflow.
