#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "HIBA: nem található a virtuális környezet: $PYTHON_BIN"
  exit 1
fi

"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ szükséges"; import PIL, PySide6; print("Python:", sys.version.split()[0], "Pillow:", PIL.__version__, "PySide6:", PySide6.__version__)'
command -v ffmpeg >/dev/null || { echo "HIBA: ffmpeg hiányzik (brew install ffmpeg)"; exit 1; }
command -v ffprobe >/dev/null || { echo "HIBA: ffprobe hiányzik (brew install ffmpeg)"; exit 1; }
ffmpeg -version | head -1
ffprobe -version | head -1
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E 'libx264|h264_videotoolbox' || true
echo "A fejlesztői környezet használható."

