from __future__ import annotations

import logging
import threading
import traceback
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from drone_telemetry_studio.domain.overlay import ExportConfig, OverlayConfig
from drone_telemetry_studio.domain.telemetry import TelemetrySample
from drone_telemetry_studio.domain.video import VideoMetadata
from drone_telemetry_studio.media.export_pipeline import ExportPipeline, ExportProgress

LOGGER = logging.getLogger(__name__)


class FunctionWorker(QThread):
    """Egyszeri függvényt futtat, eredményt Qt-jellel visz vissza a fő szálra."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, function: Callable[[], object], parent=None) -> None:
        super().__init__(parent)
        self.function = function

    def run(self) -> None:
        try:
            self.succeeded.emit(self.function())
        except Exception as exc:  # a technikai részlet naplóba, nem párbeszédablakba kerül
            LOGGER.error("Háttérfeladat sikertelen:\n%s", traceback.format_exc())
            self.failed.emit(str(exc) or exc.__class__.__name__)


class ExportWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(object)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        metadata: VideoMetadata,
        samples: list[TelemetrySample],
        overlay_config: OverlayConfig,
        export_config: ExportConfig,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.metadata = metadata
        self.samples = samples
        self.overlay_config = overlay_config
        self.export_config = export_config
        self.cancel_event = threading.Event()
        self.pipeline: ExportPipeline | None = None

    def run(self) -> None:
        try:
            self.pipeline = ExportPipeline()
            result = self.pipeline.export(
                self.input_path,
                self.output_path,
                self.metadata,
                self.samples,
                self.overlay_config,
                self.export_config,
                cancel_event=self.cancel_event,
                progress_callback=self.progress.emit,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            LOGGER.error("Export sikertelen:\n%s", traceback.format_exc())
            self.failed.emit(str(exc) or exc.__class__.__name__)
        finally:
            self.pipeline = None

    def cancel(self) -> None:
        self.cancel_event.set()
        if self.pipeline:
            self.pipeline.cancel()

