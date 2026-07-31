#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x .venv/bin/python ]] || [[ ! -x .venv/bin/pyinstaller ]]; then
  echo "Hiányzik a fejlesztői .venv vagy a PyInstaller."
  echo "Telepítés: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export PYINSTALLER_CONFIG_DIR="$PROJECT_DIR/.pyinstaller"
./scripts/verify_environment.sh
.venv/bin/pytest -q
.venv/bin/pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Drone Telemetry Studio" \
  --paths "$PROJECT_DIR/src" \
  "$PROJECT_DIR/src/drone_telemetry_studio/main.py"

echo "Elkészült: $PROJECT_DIR/dist/Drone Telemetry Studio.app"
echo "Az FFmpeg licenc- és méretokból nincs az appba csomagolva; telepítsd: brew install ffmpeg"
