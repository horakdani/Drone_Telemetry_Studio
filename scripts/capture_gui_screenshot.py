from __future__ import annotations

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
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    paths = AppPaths(artifacts / ".state", artifacts / ".state/cache", artifacts / ".state/logs")
    window = MainWindow(paths, artifacts / ".state/logs/demo.log")
    source = artifacts / "demo_source.mp4"
    samples_path = root / "samples/DJI_DEMO.SRT"
    result = DjiSrtParser().parse(samples_path)
    enrich_motion(result.samples)
    window.video_path.setText(str(source))
    window.srt_path.setText(str(samples_path))
    window.output_path.setText(str(artifacts / "demo_telemetry.mp4"))
    window._video_loaded(probe_video(source))
    window._srt_loaded(result)
    window.timeline.setValue(1500)
    window.preview.set_pixmap(QPixmap(str(artifacts / "demo_preview.png")))
    window.resize(1460, 900)
    window.show()
    app.processEvents()
    output = artifacts / "gui_screenshot.png"
    if not window.grab().save(str(output), "PNG"):
        raise RuntimeError("A GUI-képernyőkép mentése sikertelen.")
    window.close()
    print(output)


if __name__ == "__main__":
    main()
