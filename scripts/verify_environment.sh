#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: virtual environment not found: $PYTHON_BIN"
  exit 1
fi

"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ is required"; import PIL, PySide6; print("Python:", sys.version.split()[0], "Pillow:", PIL.__version__, "PySide6:", PySide6.__version__)'
command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg is missing (brew install ffmpeg)"; exit 1; }
command -v ffprobe >/dev/null || { echo "ERROR: ffprobe is missing (brew install ffmpeg)"; exit 1; }
ffmpeg -version | head -1
ffprobe -version | head -1
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E 'libx264|h264_videotoolbox' || true
echo "The development environment is ready."

