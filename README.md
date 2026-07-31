# Drone Telemetry Studio

Ingyenes, helyben futó macOS asztali alkalmazás DJI MP4-videók és DJI SRT-fájlok
telemetria-overlayes MP4-é alakításához. A felület magyar nyelvű, az eredeti videót
soha nem írja felül, és a videó vagy telemetria nem kerül külső szerverre.

![HUD-előnézet](artifacts/demo_preview.png)

![A macOS alkalmazás főablaka](artifacts/gui_screenshot.png)

## Fő funkciók

- MP4 és DJI SRT kiválasztás, automatikus név szerinti párosítás.
- Robusztus, blokkonként dolgozó parser UTF-8/BOM-, opcionálismező- és hibásblokk-kezeléssel.
- FFprobe videómetaadat, FPS-, VFR-, időtartam- és hangsáv-ellenőrzés.
- Haversine-sebesség, simítás, irányszög, magyar égtáj, vertikális sebesség és távolság.
- Képkockaalapú videóelőnézet, azonnali ±0,01 s telemetria-időeltolás.
- Fix, teljes útvonalat befoglaló térkép: teljes/eddigi út, kezdőpont, drón és északjel.
- Alapértelmezett, cache-elt OpenStreetMap-háttér; kikapcsolható, teljesen offline filmes nézet.
- Megszakítható, fájlalapú/streaming FFmpeg-export, hangmegtartás és folyamatkijelzés.
- `libx264`, `libx265`, `h264_videotoolbox` és `hevc_videotoolbox` automatikus felismerése.

## Rendszerkövetelmények

- macOS 13 vagy újabb; Apple Silicon elsődlegesen, Intel elvileg támogatott.
- Python 3.12 vagy újabb. A fejlesztés Python 3.14.6-tal is ellenőrzött.
- FFmpeg és FFprobe. A program induláskor az elérhető kódolókat ténylegesen lekérdezi.
- Nagy videónál elegendő hely a végleges kimenethez; a teljes MP4 nem kerül memóriába.

Homebrew telepítése a [hivatalos Homebrew oldal](https://brew.sh/) szerint, majd:

```bash
brew install python ffmpeg
```

## Fejlesztői telepítés és indítás

```bash
cd "/Users/horakdaniel/Telemetry Overlay"
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
./scripts/verify_environment.sh
./scripts/run_dev.sh
```

A jelenlegi munkamappában a függőségek már a `.venv` alatt vannak, ezért most közvetlenül:

```bash
cd "/Users/horakdaniel/Telemetry Overlay" && ./scripts/run_dev.sh
```

## Használat

1. Kattints a **Videó kiválasztása…** gombra, és válaszd ki a helyi MP4-et.
2. Ha az azonos nevű `.SRT`/`.srt` mellette van, az automatikus párosítás betölti;
   különben használd a **DJI SRT kiválasztása…** gombot.
3. Ellenőrizd a fájl- és validációs információkat. A csúszkán választott időponthoz
   az FFmpeg egy proxy-képkockát olvas, majd rákerül az aktuális HUD.
4. Állítsd a mezők láthatóságát, GPS-kerekítést, térképstílust/-pozíciót és a
   telemetria időeltolását. A pozitív időeltolás későbbi SRT-mintát mutat ugyanazon
   videó-időpontnál.
5. Válassz új kimeneti nevet, kódolót és minőséget, majd **Export indítása**.
   A **Megszakítás** leállítja az FFmpeg-et és törli a részfájlt.

## DJI SRT és mozgásszámítás

A parser nem egyetlen merev reguláris kifejezésből áll: előbb SRT-blokkot és idősávot,
majd biztonságosan eltávolított HTML-tageket, bracketmezőket és kulcs-érték párokat bont.
Az érvénytelen GPS-pont figyelmeztetés, nem végzetes hiba.

A GPS sebesség legalább 0,5 másodperces időablak távolságából készül, nem minden
16–17 ms-os rekordból. A geodéziai távolság Haversine-képlettel számolódik, az
alapértelmezett 45 m/s feletti fizikai ugrások kimaradnak az útból és a kumulatív
távolságból. A kijelzési sebesség időalapú exponenciális simítást kap; a nyers érték
külön mezőben marad. Az irány csak megbízható mozgásnál frissül, álló helyzetben az
utolsó irányt tartja. Minden belső érték SI-mértékegységű.

## Térkép, hálózat és cache

Az alapértelmezett, valódi térképhátteret az OpenStreetMap csempéi adják. Csak az aktuális
fix nézethez szükséges csempéket kéri, egyedi User-Agenttel, feltételes HTTP-kérésekkel és legalább
7 napos cache-sel. Nincs terület- vagy zoomszint-előtöltés. A csempe-cache helye:
`~/Library/Caches/DroneTelemetryStudio/tiles`; a felületről törölhető. A nyilvános
OSM-szolgáltatásnak nincs SLA-ja; hálózati hiba esetén az offline háttér jelenik meg.
A **Valódi OSM-térképháttér (hálózat)** kapcsolóval a csempeletöltés kikapcsolható.
Az offline nézet Web Mercator vetületű, filmes útvonalpanelt rajzol, és a teljes repülést
fix bounding boxban tartja. Az attribúció mindig látható.

Lásd az [OSMF Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)
és az [OSM attribúciós útmutató](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)
oldalakat.

## Exportfelépítés és teljesítmény

Az FFmpeg az eredeti MP4-et fájlból streameli. A Python csak az aktuális, alapból
960×540 pixeles RGBA HUD-képet tartja memóriában, ezt 10 fps-cel közvetlen pipe-on adja
át. Az FFmpeg Lanczos-skálázással az eredeti (1080p/4K) felbontásra nagyítja és egyetlen
folyamatban kódolja a kimenetet. Nincs teljes videóproxy, képkockánkénti PNG-halmaz vagy
nagy köztes alfa-videó. VFR bemenetnél az eredeti videó timestampjei vezetik a főágat.

## Tesztek és reprodukálható artifactok

```bash
.venv/bin/pytest -q
PYTHONPATH=src .venv/bin/python scripts/generate_demo_assets.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python scripts/capture_gui_screenshot.py
PYTHONPATH=src .venv/bin/python scripts/prototype_map_backends.py
```

A generátor létrehozza:

- `artifacts/demo_preview.png` – statikus videó+HUD előnézet;
- `artifacts/demo_source.mp4` – rövid, generált, hangos forrásvideó;
- `artifacts/demo_telemetry.mp4` – a tényleges FFmpeg-export.
- `artifacts/gui_screenshot.png` – reprodukálható főablak-képernyőkép.

A repositoryban lévő `samples/DJI_DEMO.SRT` a specifikációban megadott valós első
DJI-rekordot és ugyanilyen formátumú rövid útvonalat tartalmaz. A teljes, 32 772 blokkos
`DJI_20260729153808_0006_D.SRT` nem szerepelt a kapott csatolmányok között; ha a
`samples/` mappába kerül, ugyanazzal a parserrel és artifact-generátorral feldolgozható.

## macOS `.app` készítése

```bash
./scripts/build_macos.sh
```

A script előbb ellenőrzi a környezetet és lefuttatja az összes tesztet, majd PyInstallerrel
elkészíti a `dist/Drone Telemetry Studio.app` csomagot. Az app jelenleg nincs Apple
Developer ID-val aláírva vagy notarizálva. Az FFmpeg nincs a csomagba beágyazva: külön
`brew install ffmpeg` szükséges, ami kisebb appot és egyértelműbb licenckezelést ad.

## Napló és hibaelhárítás

A technikai napló: `~/Library/Application Support/DroneTelemetryStudio/logs/`.
A felület **Napló megnyitása** gombja megnyitja. Ha nincs előnézet, ellenőrizd az
`ffmpeg -version` és `ffprobe -version` kimenetet. Hardveres kódolási hiba esetén válts
`H.264 – szoftveres` módra. Meglévő kimenetet az app szándékosan nem ír felül.

## Ismert korlátozások

- Az első stabil változatban fix útvonaltérkép van; a drónt követő kamera nincs kész.
- A HUD alapértelmezett időbeli felbontása 10 fps, a forrásvideó képkockái ettől
  függetlenül az eredeti FPS/timestamp szerint készülnek.
- Az OSM nyilvános csempeszerveréről tilos bulk/offline területletöltést végezni;
  ezért az alkalmazás ilyet nem kínál.
- A teljes, név szerint hivatkozott DJI mintafájl hiánya miatt csak a mellékelt rövid,
  reprezentatív SRT-vel fut a repository integrációs ellenőrzése.
- A PyInstaller `.app` nincs kódaláírva/notarizálva, az Intel buildet Intel gépen kell
  külön elkészíteni és tesztelni.

## Licencek és attribúciók

A saját forráskód MIT licencű. A külső komponensek részletes listája a
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) fájlban van. A fontosabb hivatalos
források: [Qt for Python](https://doc.qt.io/qtforpython-6/),
[Pillow](https://pillow.readthedocs.io/), [FFmpeg](https://ffmpeg.org/legal.html) és
[PyInstaller](https://pyinstaller.org/en/stable/license.html).
