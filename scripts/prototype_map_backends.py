from __future__ import annotations

import importlib.util
import json
import shutil
import time
from pathlib import Path

from drone_telemetry_studio.domain.overlay import MapConfig
from drone_telemetry_studio.map.renderer import StaticMapRenderer
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion


def main() -> None:
    root = Path(__file__).parents[1]
    samples = enrich_motion(DjiSrtParser().parse(root / "samples/DJI_DEMO.SRT").samples)
    renderer = StaticMapRenderer(root / ".prototype-tile-cache")
    started = time.perf_counter()
    for index in range(50):
        renderer.render(samples, index / 20, MapConfig(), 520, 300)
    pillow_seconds = time.perf_counter() - started
    playwright_available = importlib.util.find_spec("playwright") is not None
    chromium_available = any(shutil.which(name) for name in ("chromium", "chromium-browser", "Google Chrome"))
    report = {
        "pillow_static_50_frames_seconds": round(pillow_seconds, 4),
        "pillow_external_runtime": False,
        "maplibre_playwright_installed": playwright_available,
        "headless_chromium_on_path": chromium_available,
        "decision": "Pillow static renderer",
        "reason": "no browser runtime, smaller bundle, deterministic offline route view",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

