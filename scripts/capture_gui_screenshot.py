from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from drone_telemetry_studio.app.paths import AppPaths
from drone_telemetry_studio.app.application import STYLE
from drone_telemetry_studio.media.ffprobe import probe_video
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion
from drone_telemetry_studio.ui.main_window import MainWindow


def main() -> None:
    root = Path(__file__).parents[1]
    artifacts = root / "artifacts"
    parser = argparse.ArgumentParser(description="Save a reproducible screenshot of the main window.")
    parser.add_argument("--video", type=Path, default=artifacts / "demo_source.mp4")
    parser.add_argument("--srt", type=Path, default=root / "samples/DJI_DEMO.SRT")
    parser.add_argument("--preview", type=Path, default=artifacts / "demo_preview.png")
    parser.add_argument("--time", type=float, default=1.5, help="Timeline position in seconds")
    parser.add_argument("--output", type=Path, default=artifacts / "gui_screenshot.png")
    parser.add_argument("--all-fields", action="store_true", help="Tick every HUD field")
    parser.add_argument("--display-dir", help="Folder shown in the path fields instead of the real one")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    paths = AppPaths(artifacts / ".state", artifacts / ".state/cache", artifacts / ".state/logs")
    window = MainWindow(paths, artifacts / ".state/logs/demo.log")
    result = DjiSrtParser().parse(args.srt)
    enrich_motion(result.samples)

    def shown(path: Path) -> str:
        return f"{args.display_dir}/{path.name}" if args.display_dir else str(path)

    window.video_path.setText(shown(args.video))
    window.srt_path.setText(shown(args.srt))
    window.output_path.setText(shown(args.video.with_name(f"{args.video.stem}_telemetry.mp4")))
    window._video_loaded(probe_video(args.video))
    window._srt_loaded(result)
    if args.all_fields:
        for checkbox in window.display_checks.values():
            checkbox.setChecked(True)
    window.timeline.setValue(round(args.time * 1000))
    window.preview.set_pixmap(QPixmap(str(args.preview)))
    window.resize(1460, 900)
    window.show()
    app.processEvents()
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output), "PNG"):
        raise RuntimeError("Failed to save the GUI screenshot.")
    window.close()
    print(output)


if __name__ == "__main__":
    main()
