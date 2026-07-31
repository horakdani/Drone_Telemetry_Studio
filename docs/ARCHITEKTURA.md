# Architektúra és technikai döntések

## Rétegek

- `domain`: GUI-tól független adatmodellek és beállítások.
- `parsers`, `telemetry`: DJI SRT, validáció, geodézia, szűrés és interpoláció.
- `map`, `overlay`: fix útvonaltérkép és skálázható RGBA HUD.
- `media`: FFprobe és egyfolyamatos FFmpeg-export.
- `ui`: Qt Widgets felület; minden hosszú művelet `QThread`-ben fut.

## Térképprototípus

A `scripts/prototype_map_backends.py` a Pillow renderert ténylegesen benchmarkolja,
és ellenőrzi a MapLibre/Playwright futtatási feltételeit. A MapLibre headless változat
Chromiumot, Playwrightot, MapLibre JS-t és stílus-/csempeforrást igényelne. A kiválasztott
Pillow renderer determinisztikus, teljesen offline alaptérképet ad, nincs böngésző-runtime,
és a fix háttér később cache-elhető. Opcionálisan rasztercsempéket is összeállít, de csak
az aktuális fix nézethez és felhasználói bekapcsolás után.

## Exportstratégiák

Az átlátszó köztes videó egyszerűen keverhető lenne, de hosszú 4K felvételnél jelentős
ideiglenes tárhelyet használna. A választott út egy 960×540-es, alapból 10 fps-es RGBA
HUD stream közvetlen pipe-olása ugyanabba az FFmpeg-folyamatba, amely az eredeti videót
dekódolja és a végleges MP4-et kódolja. A videó eredeti timestampjei és felbontása
megmaradnak; a HUD skálázását és összekeverését az FFmpeg végzi.

## Adatvédelem

Az offline útvonaltérkép semmilyen hálózati kérést nem végez. Az OSM-csempés mód külön,
egyértelmű kapcsoló; a videót/SRT-t akkor sem tölti fel. A csempe URL konfigurációban van,
azonos csempe cache-ből jön, a cache legalább hét napig érvényes, és nincs bulk prefetch.

