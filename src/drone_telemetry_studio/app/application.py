from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from drone_telemetry_studio.app.paths import AppPaths
from drone_telemetry_studio.ui.main_window import MainWindow
from drone_telemetry_studio.utils.logging import configure_logging

STYLE = """
QWidget { background: #0e151d; color: #e8eef4; font-size: 13px; }
QScrollArea, #settingsBody { background: #101923; border: none; }
QGroupBox { border: 1px solid #2a3948; border-radius: 10px; margin-top: 12px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #a9bed0; }
QPushButton { background: #243342; border: 1px solid #3b4e60; border-radius: 7px; padding: 8px 10px; }
QPushButton:hover { background: #304456; }
QPushButton:disabled { color: #667786; background: #1a242e; }
#primaryButton { background: #00a486; border-color: #18c3a3; color: white; font-weight: 700; }
#primaryButton:hover { background: #0bb597; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #0a1118; border: 1px solid #314354; border-radius: 6px; padding: 6px; }
QCheckBox { spacing: 8px; }
QProgressBar { background: #111b24; border: 1px solid #304252; border-radius: 6px; text-align: center; }
QProgressBar::chunk { background: #00a486; border-radius: 5px; }
QSlider::groove:horizontal { height: 5px; background: #2c3b48; border-radius: 2px; }
QSlider::handle:horizontal { background: #20c7a8; width: 16px; margin: -6px 0; border-radius: 8px; }
#appTitle { font-size: 24px; font-weight: 800; color: #f4f8fb; letter-spacing: 2px; padding: 4px; }
#sectionTitle { font-size: 18px; font-weight: 700; color: #a9bed0; letter-spacing: 2px; }
QStatusBar { color: #93a8ba; }
"""


def run_application(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    app.setApplicationName("Drone Telemetry Studio")
    app.setOrganizationName("DroneTelemetryStudio")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    paths = AppPaths.macos_default()
    log_path = configure_logging(paths.logs)
    window = MainWindow(paths, log_path)
    window.show()
    return app.exec()

