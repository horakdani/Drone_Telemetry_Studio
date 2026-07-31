from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class PreviewWidget(QWidget):
    resized = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source: QPixmap | None = None
        self.label = QLabel("Válassz egy MP4-videót és egy DJI SRT-fájlt.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumSize(640, 360)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.label.setStyleSheet(
            "QLabel { background: #080d13; border: 1px solid #273443; border-radius: 14px; color: #8fa2b5; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._fit()

    def set_message(self, message: str) -> None:
        self._source = None
        self.label.setPixmap(QPixmap())
        self.label.setText(message)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()
        self.resized.emit()

    def _fit(self) -> None:
        if self._source and not self._source.isNull():
            self.label.setPixmap(
                self._source.scaled(
                    self.label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

