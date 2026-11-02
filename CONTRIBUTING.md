# Contributing to Drone Telemetry Studio

Thanks for your interest! Bug reports, SRT samples from other DJI models, and pull
requests are all welcome.

## Development setup

```bash
brew install python ffmpeg
git clone https://github.com/horakdani/Drone_Telemetry_Studio.git
cd Drone_Telemetry_Studio
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
./scripts/verify_environment.sh   # checks Python, PySide6, Pillow, FFmpeg
./scripts/run_dev.sh              # launches the app
```

## Running the tests

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

The suite has unit tests (parser, geodesy, smoothing, interpolation, map geometry),
integration tests that run a real FFmpeg export on a generated clip, and offscreen GUI
tests. It needs no network and no real drone footage. CI runs the same command on
macOS for every pull request.

## Regenerating screenshots and demo media

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_demo_assets.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python scripts/capture_gui_screenshot.py
```

Outputs go to `artifacts/` (git-ignored). Copy updated images to `docs/images/` if
they belong in the README.

## Supporting another drone or SRT variant

DJI changes its SRT layout between models and firmware versions. If your file does
not parse:

1. Open an issue using the **SRT format support** template.
2. Attach the first ~20 blocks of the file. Strip or shift GPS coordinates if the
   location is private: the parser cares about the format, not the place.
3. Mention the drone model and firmware version.

## Pull request checklist

- Keep the core modules (`parsers`, `telemetry`, `map`, `overlay`, `media`) free of
  Qt imports so they stay testable headless.
- Add or update tests for behavior changes.
- Never overwrite the user's source files; keep work on the export temp-file path.
- Run `pytest` locally and add a line to `CHANGELOG.md` under *Unreleased*.
