from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from drone_telemetry_studio.app.paths import AppPaths
from drone_telemetry_studio.media.ffmpeg import discover_media_tools
from drone_telemetry_studio.media.ffprobe import probe_video
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion
from drone_telemetry_studio.ui.main_window import MainWindow


def _wait_for(app: QApplication, condition, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition(), "A GUI háttérfeladata túllépte az időkorlátot."


def test_gui_preview_and_export_flow(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "gui input.mp4"
    output = tmp_path / "gui output.mp4"
    subprocess.run(
        [
            discover_media_tools().ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "0.6",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
        timeout=30,
    )
    paths = AppPaths(tmp_path, tmp_path, tmp_path)
    window = MainWindow(paths, tmp_path / "log.txt")
    window.video_path.setText(str(source))
    window.output_path.setText(str(output))
    window._video_loaded(probe_video(source))
    samples_path = Path(__file__).parents[2] / "samples/DJI_DEMO.SRT"
    result = DjiSrtParser().parse(samples_path)
    enrich_motion(result.samples)
    window._srt_loaded(result)
    window.timeline.setValue(300)
    window._request_preview()
    _wait_for(app, lambda: window._preview_worker is None)
    assert window._current_pixmap is not None
    assert not window._current_pixmap.isNull()

    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    software_index = window.codec.findData("libx264")
    assert software_index >= 0
    window.codec.setCurrentIndex(software_index)
    window.quality.setCurrentText("Gyors")
    window._start_export()
    _wait_for(app, lambda: window._export_worker is None, timeout=30)
    assert output.exists()
    assert probe_video(output).duration_seconds == 0.6
    window.close()

