# Külső függőségek és licencek

| Összetevő | Felhasználás | Licenc / megjegyzés |
|---|---|---|
| Python | futtatókörnyezet | PSF License |
| PySide6 / Qt 6 | natív jellegű GUI, szálak | LGPLv3/GPLv3 vagy kereskedelmi; ez a projekt az LGPLv3 feltételeivel számol, nincs Qt-módosítás |
| Pillow | RGBA HUD és térképrender | HPND történeti licenc |
| FFmpeg / FFprobe | metaadat, képkocka és MP4 export | LGPLv2.1+ alapesetben; az adott build kapcsolóitól (például GPL libx264) függ, külön telepítendő |
| libx264 / libx265 | opcionális szoftveres encoder | FFmpeg build/licenc szerint, jellemzően GPL-kompatibilis használatot igényel |
| Apple VideoToolbox | hardveres encoder | macOS rendszerkomponens |
| PyInstaller | `.app` csomagolás | GPLv2-or-later külön kivétellel, amely engedi a generált app terjesztését |
| pytest | csak fejlesztői teszt | MIT |
| OpenStreetMap adatok/csempék | opcionális háttér | adatok ODbL; © OpenStreetMap contributors; a nyilvános tile szolgáltatás külön használati szabályzata kötelező |

Az alkalmazás saját csomagja nem tartalmazza az FFmpeg binárist vagy OSM-csempéket.
Terjesztés előtt az adott FFmpeg build `ffmpeg -version` konfigurációs sorát és az
LGPL/GPL megfelelést külön ellenőrizni kell.

