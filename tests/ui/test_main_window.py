import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from drone_telemetry_studio.app.paths import AppPaths
from drone_telemetry_studio.ui.main_window import MainWindow


def test_main_window_constructs_and_exposes_hungarian_flow(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    paths = AppPaths(tmp_path, tmp_path, tmp_path)
    window = MainWindow(paths, tmp_path / "log.txt")
    window.show()
    app.processEvents()
    assert window.windowTitle() == "Drone Telemetry Studio"
    assert window.video_button.text() == "Videó kiválasztása…"
    assert window.export_button.text() == "Export indítása"
    assert window.codec.count() >= 1
    window.close()

