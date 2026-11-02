# Third-party components and licenses

| Component | Used for | License / notes |
|---|---|---|
| Python | Runtime | PSF License |
| PySide6 / Qt 6 | Native-looking GUI, threading | LGPLv3/GPLv3 or commercial; this project relies on the LGPLv3 terms and does not modify Qt |
| Pillow | RGBA HUD and map rendering | HPND (historical permission notice) |
| FFmpeg / FFprobe | Metadata, preview frames and MP4 export | LGPLv2.1+ by default; depends on the build flags (e.g. GPL with libx264); installed separately |
| libx264 / libx265 | Optional software encoders | Per your FFmpeg build; typically requires GPL-compatible use |
| Apple VideoToolbox | Hardware encoders | macOS system component |
| PyInstaller | `.app` packaging | GPLv2-or-later with a bootloader exception that permits distributing the generated app |
| pytest | Development tests only | MIT |
| OpenStreetMap data/tiles | Optional map background | Data under ODbL; © OpenStreetMap contributors; the public tile service has its own usage policy, which must be followed |

The application bundle does not ship the FFmpeg binaries or any OSM tiles. Before
redistributing a build, check the `configuration:` line of `ffmpeg -version` for your
FFmpeg build and confirm LGPL/GPL compliance separately.
