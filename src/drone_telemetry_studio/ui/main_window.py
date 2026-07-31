from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from drone_telemetry_studio.app.paths import AppPaths
from drone_telemetry_studio.domain.overlay import Corner, ExportConfig, MapStyle, OverlayConfig
from drone_telemetry_studio.domain.telemetry import ParseResult
from drone_telemetry_studio.domain.video import VideoMetadata
from drone_telemetry_studio.media.export_pipeline import ExportProgress
from drone_telemetry_studio.media.ffmpeg import available_video_encoders, extract_preview_frame
from drone_telemetry_studio.media.ffprobe import probe_video
from drone_telemetry_studio.map.cache import TileCache
from drone_telemetry_studio.overlay.renderer import HudRenderer
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import MotionConfig, enrich_motion
from drone_telemetry_studio.telemetry.interpolation import TelemetryTimeline
from drone_telemetry_studio.telemetry.validation import validate_video_telemetry
from drone_telemetry_studio.ui.preview_widget import PreviewWidget
from drone_telemetry_studio.ui.workers import ExportWorker, FunctionWorker

LOGGER = logging.getLogger(__name__)


def _pil_to_pixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


class MainWindow(QMainWindow):
    def __init__(self, paths: AppPaths, log_path: Path) -> None:
        super().__init__()
        self.paths = paths
        self.log_path = log_path
        self.video_metadata: VideoMetadata | None = None
        self.parse_result: ParseResult | None = None
        self.samples = []
        self.timeline_index: TelemetryTimeline | None = None
        self._workers: set[FunctionWorker] = set()
        self._preview_worker: FunctionWorker | None = None
        self._preview_pending = False
        self._export_worker: ExportWorker | None = None
        self._current_pixmap: QPixmap | None = None

        self.setWindowTitle("Drone Telemetry Studio")
        self.resize(1460, 900)
        self.setMinimumSize(1050, 680)
        self._build_ui()
        self._connect_signals()
        self._detect_encoders()

        self.preview_debounce = QTimer(self)
        self.preview_debounce.setSingleShot(True)
        self.preview_debounce.setInterval(180)
        self.preview_debounce.timeout.connect(self._request_preview)
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(200)
        self.play_timer.timeout.connect(self._advance_playback)

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._settings_area())
        splitter.addWidget(self._preview_area())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 1050])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Készen áll")

    def _settings_area(self) -> QScrollArea:
        body = QWidget()
        body.setObjectName("settingsBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("DRONE TELEMETRY\nSTUDIO")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        files = QGroupBox("Fájlok")
        files_layout = QVBoxLayout(files)
        self.video_path = QLineEdit()
        self.video_path.setReadOnly(True)
        self.video_button = QPushButton("Videó kiválasztása…")
        self.srt_path = QLineEdit()
        self.srt_path.setReadOnly(True)
        self.srt_button = QPushButton("DJI SRT kiválasztása…")
        self.auto_pair = QCheckBox("Automatikus párosítás azonos fájlnévvel")
        self.auto_pair.setChecked(True)
        self.file_info = QLabel("Még nincs betöltött fájl.")
        self.file_info.setWordWrap(True)
        self.validation_info = QLabel("")
        self.validation_info.setWordWrap(True)
        for widget in (self.video_path, self.video_button, self.srt_path, self.srt_button, self.auto_pair, self.file_info, self.validation_info):
            files_layout.addWidget(widget)
        layout.addWidget(files)

        display = QGroupBox("Megjelenítés")
        display_layout = QVBoxLayout(display)
        self.display_checks = {}
        labels_defaults = (
            ("speed", "Sebesség", True), ("altitude", "Relatív magasság", True),
            ("gps", "GPS-koordináták", True), ("date", "Dátum", True),
            ("time", "Idő", True), ("heading", "Irány", True),
            ("map", "Térkép", True), ("vertical", "Függőleges sebesség", False),
            ("distance", "Megtett távolság", False),
        )
        for key, label, checked in labels_defaults:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            self.display_checks[key] = checkbox
            display_layout.addWidget(checkbox)
        self.gps_decimals = QComboBox()
        self.gps_decimals.addItems(["6 tizedes", "5 tizedes", "4 tizedes", "Rejtett"])
        display_layout.addWidget(QLabel("GPS pontossága"))
        display_layout.addWidget(self.gps_decimals)
        layout.addWidget(display)

        map_group = QGroupBox("Térkép")
        map_form = QFormLayout(map_group)
        self.map_style = QComboBox()
        self.map_style.addItems([item.value for item in MapStyle])
        self.map_position = QComboBox()
        self.map_position.addItems([item.value for item in Corner])
        self.map_position.setCurrentText(Corner.BOTTOM_RIGHT.value)
        self.map_width = QSpinBox(); self.map_width.setRange(15, 55); self.map_width.setValue(24); self.map_width.setSuffix(" %")
        self.map_height = QSpinBox(); self.map_height.setRange(15, 55); self.map_height.setValue(25); self.map_height.setSuffix(" %")
        self.map_opacity = QSpinBox(); self.map_opacity.setRange(30, 100); self.map_opacity.setValue(88); self.map_opacity.setSuffix(" %")
        self.route_width = QSpinBox(); self.route_width.setRange(2, 12); self.route_width.setValue(4); self.route_width.setSuffix(" px")
        self.tile_background = QCheckBox("Valódi OSM-térképháttér (hálózat)")
        self.tile_background.setChecked(True)
        self.tile_background.setToolTip("Csak az aktuális fix nézet csempéit tölti le, és helyben gyorsítótárazza.")
        self.hide_start = QDoubleSpinBox(); self.hide_start.setRange(0, 600); self.hide_start.setDecimals(1); self.hide_start.setSuffix(" s")
        self.hide_end = QDoubleSpinBox(); self.hide_end.setRange(0, 600); self.hide_end.setDecimals(1); self.hide_end.setSuffix(" s")
        self.cache_info = QLabel(str(self.paths.cache / "tiles"))
        self.cache_info.setWordWrap(True)
        self.clear_cache_button = QPushButton("Csempecache törlése")
        map_form.addRow("Stílus", self.map_style)
        map_form.addRow("Pozíció", self.map_position)
        map_form.addRow("Szélesség", self.map_width)
        map_form.addRow("Magasság", self.map_height)
        map_form.addRow("Átlátszatlanság", self.map_opacity)
        map_form.addRow("Útvonalvastagság", self.route_width)
        map_form.addRow("Kezdő szakasz rejtése", self.hide_start)
        map_form.addRow("Záró szakasz rejtése", self.hide_end)
        map_form.addRow(self.tile_background)
        map_form.addRow("Cache helye", self.cache_info)
        map_form.addRow(self.clear_cache_button)
        layout.addWidget(map_group)

        sync = QGroupBox("Szinkron és szűrés")
        sync_form = QFormLayout(sync)
        self.time_offset = QDoubleSpinBox(); self.time_offset.setRange(-600, 600); self.time_offset.setDecimals(2); self.time_offset.setSingleStep(0.01); self.time_offset.setSuffix(" s")
        self.smoothing = QDoubleSpinBox(); self.smoothing.setRange(0.05, 5); self.smoothing.setDecimals(2); self.smoothing.setValue(0.65); self.smoothing.setSuffix(" s")
        self.speed_limit = QDoubleSpinBox(); self.speed_limit.setRange(5, 100); self.speed_limit.setValue(45); self.speed_limit.setSuffix(" m/s")
        sync_form.addRow("Telemetria-időeltolás", self.time_offset)
        sync_form.addRow("Simítás időállandója", self.smoothing)
        sync_form.addRow("GPS-kiugrási határ", self.speed_limit)
        layout.addWidget(sync)

        export = QGroupBox("Export")
        export_layout = QVBoxLayout(export)
        self.output_path = QLineEdit()
        self.output_button = QPushButton("Kimeneti MP4…")
        self.codec = QComboBox()
        self.quality = QComboBox(); self.quality.addItems(["Gyors", "Kiegyensúlyozott", "Kiváló"]); self.quality.setCurrentText("Kiegyensúlyozott")
        self.keep_audio = QCheckBox("Hang megtartása"); self.keep_audio.setChecked(True)
        export_form = QFormLayout()
        export_form.addRow("Kimenet", self.output_path)
        export_form.addRow("Videokodek", self.codec)
        export_form.addRow("Minőség", self.quality)
        export_layout.addLayout(export_form)
        export_layout.addWidget(self.output_button)
        export_layout.addWidget(self.keep_audio)
        buttons = QHBoxLayout()
        self.export_button = QPushButton("Export indítása")
        self.export_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("Megszakítás")
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.cancel_button)
        export_layout.addLayout(buttons)
        self.export_progress = QProgressBar(); self.export_progress.setRange(0, 1000); self.export_progress.setValue(0)
        self.export_status = QLabel("Nincs folyamatban export.")
        export_layout.addWidget(self.export_progress)
        export_layout.addWidget(self.export_status)
        layout.addWidget(export)

        self.log_button = QPushButton("Napló megnyitása")
        layout.addWidget(self.log_button)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setMinimumWidth(350)
        scroll.setMaximumWidth(500)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def _preview_area(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        heading = QLabel("ELŐNÉZET")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.preview = PreviewWidget()
        layout.addWidget(self.preview, 1)
        controls = QHBoxLayout()
        self.play_button = QPushButton("▶ Lejátszás")
        self.back_button = QPushButton("−1 s")
        self.forward_button = QPushButton("+1 s")
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.time_label = QLabel("00:00,00 / 00:00,00")
        controls.addWidget(self.play_button)
        controls.addWidget(self.back_button)
        controls.addWidget(self.timeline, 1)
        controls.addWidget(self.forward_button)
        controls.addWidget(self.time_label)
        layout.addLayout(controls)
        return panel

    def _connect_signals(self) -> None:
        self.video_button.clicked.connect(self._select_video)
        self.srt_button.clicked.connect(self._select_srt)
        self.output_button.clicked.connect(self._select_output)
        self.export_button.clicked.connect(self._start_export)
        self.cancel_button.clicked.connect(self._cancel_export)
        self.log_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_path))))
        self.timeline.valueChanged.connect(self._timeline_changed)
        self.play_button.clicked.connect(self._toggle_playback)
        self.back_button.clicked.connect(lambda: self.timeline.setValue(max(0, self.timeline.value() - 1000)))
        self.forward_button.clicked.connect(lambda: self.timeline.setValue(min(self.timeline.maximum(), self.timeline.value() + 1000)))
        for checkbox in self.display_checks.values():
            checkbox.toggled.connect(self._schedule_preview)
        for combo in (self.gps_decimals, self.map_style, self.map_position):
            combo.currentIndexChanged.connect(self._schedule_preview)
        for spin in (self.map_width, self.map_height, self.map_opacity, self.route_width, self.hide_start, self.hide_end, self.time_offset):
            spin.valueChanged.connect(self._schedule_preview)
        self.tile_background.toggled.connect(self._tile_mode_changed)
        self.clear_cache_button.clicked.connect(self._clear_tile_cache)
        self.smoothing.valueChanged.connect(self._reprocess_srt)
        self.speed_limit.valueChanged.connect(self._reprocess_srt)

    def _detect_encoders(self) -> None:
        try:
            available = available_video_encoders()
        except RuntimeError as exc:
            self._error(str(exc))
            return
        options = (("H.264 – szoftveres", "libx264"), ("H.265 – szoftveres", "libx265"), ("H.264 – Apple VideoToolbox", "h264_videotoolbox"), ("H.265 – Apple VideoToolbox", "hevc_videotoolbox"))
        for label, codec in options:
            if codec in available:
                self.codec.addItem(label, codec)
        default_index = self.codec.findData("h264_videotoolbox")
        self.codec.setCurrentIndex(default_index if default_index >= 0 else 0)

    def _select_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "DJI videó kiválasztása", "", "MP4 videó (*.mp4 *.MP4);;Minden fájl (*)")
        if not path:
            return
        self.video_path.setText(path)
        source = Path(path)
        self.output_path.setText(str(source.with_name(f"{source.stem}_telemetry.mp4")))
        if self.auto_pair.isChecked():
            candidates = [source.with_suffix(".SRT"), source.with_suffix(".srt")]
            pair = next((candidate for candidate in candidates if candidate.exists()), None)
            if pair:
                self.srt_path.setText(str(pair))
                self._load_srt(pair)
        self.statusBar().showMessage("Videó elemzése…")
        self._run_worker(lambda: probe_video(path), self._video_loaded)

    def _video_loaded(self, metadata: VideoMetadata) -> None:
        self.video_metadata = metadata
        self.timeline.setRange(0, max(0, round(metadata.duration_seconds * 1000)))
        vfr = " • VFR" if metadata.is_variable_frame_rate else ""
        audio = f" • hang: {metadata.audio_codec}" if metadata.has_audio else " • nincs hang"
        self.file_info.setText(
            f"{metadata.resolution_label} • {metadata.average_fps:.3f} fps{vfr}\n"
            f"{metadata.duration_seconds:.2f} s • {metadata.codec_name}{audio}"
        )
        self.statusBar().showMessage("Videó betöltve", 4000)
        self._update_validation()
        self._schedule_preview()

    def _select_srt(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "DJI SRT kiválasztása", "", "SRT telemetria (*.srt *.SRT);;Minden fájl (*)")
        if path:
            self.srt_path.setText(path)
            self._load_srt(Path(path))

    def _load_srt(self, path: Path) -> None:
        smoothing = self.smoothing.value()
        max_speed = self.speed_limit.value()

        def work():
            result = DjiSrtParser().parse(path)
            enrich_motion(result.samples, MotionConfig(smoothing_time_constant_seconds=smoothing, max_speed_mps=max_speed))
            return result

        self.statusBar().showMessage("Telemetria feldolgozása…")
        self._run_worker(work, self._srt_loaded)

    def _srt_loaded(self, result: ParseResult) -> None:
        self.parse_result = result
        self.samples = result.samples
        self.timeline_index = TelemetryTimeline(self.samples)
        status = result.validation
        self.validation_info.setText(
            f"{status.accepted_samples} minta • {status.duration_seconds:.3f} s • "
            f"{len(result.warnings)} parserfigyelmeztetés"
        )
        if result.warnings:
            self.validation_info.setToolTip(
                "\n".join(f"#{warning.block_index}: {warning.message}" for warning in result.warnings[:30])
            )
        self._update_validation()
        self.statusBar().showMessage("Telemetria feldolgozva", 4000)
        self._schedule_preview()

    def _reprocess_srt(self) -> None:
        path = Path(self.srt_path.text())
        if path.is_file():
            self._load_srt(path)

    def _update_validation(self) -> None:
        if not self.video_metadata or not self.parse_result:
            return
        validation = validate_video_telemetry(self.video_metadata, self.parse_result)
        parser = self.parse_result.validation
        inferred = "" if validation.inferred_telemetry_fps is None else f" • SRT: {validation.inferred_telemetry_fps:.3f} fps"
        summary = (
            f"{parser.accepted_samples} minta • {parser.duration_seconds:.3f} s • "
            f"eltérés: {validation.duration_difference_seconds:+.2f} s{inferred}"
        )
        if validation.messages:
            summary += "\n⚠ " + "\n⚠ ".join(validation.messages)
        else:
            summary += "\n✓ A videó és a telemetria idővonala konzisztens."
        self.validation_info.setText(summary)

    def _select_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Kimeneti videó", self.output_path.text(), "MP4 videó (*.mp4)")
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.output_path.setText(path)

    def _timeline_changed(self, value: int) -> None:
        duration = self.video_metadata.duration_seconds if self.video_metadata else 0
        self.time_label.setText(f"{self._time(value / 1000)} / {self._time(duration)}")
        self._schedule_preview()

    @staticmethod
    def _time(seconds: float) -> str:
        minutes, remainder = divmod(max(0, seconds), 60)
        return f"{int(minutes):02d}:{remainder:05.2f}".replace(".", ",")

    def _toggle_playback(self) -> None:
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.play_button.setText("▶ Lejátszás")
        else:
            self.play_timer.start()
            self.play_button.setText("⏸ Szünet")

    def _advance_playback(self) -> None:
        value = self.timeline.value() + self.play_timer.interval()
        if value > self.timeline.maximum():
            self.play_timer.stop()
            self.play_button.setText("▶ Lejátszás")
            value = 0
        self.timeline.setValue(value)

    def _schedule_preview(self) -> None:
        if hasattr(self, "preview_debounce"):
            self.preview_debounce.start()

    def _request_preview(self) -> None:
        # A közvetlen előnézetkérés felülírja a még várakozó debounce-kérést;
        # különben ugyanarra az állapotra két egymást követő worker indulhat.
        if hasattr(self, "preview_debounce"):
            self.preview_debounce.stop()
        if not self.video_metadata or not self.samples:
            return
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_pending = True
            return
        time_seconds = self.timeline.value() / 1000
        video_path = self.video_metadata.path
        overlay_config = self._overlay_config()
        samples = self.samples
        # Rejtett/fej nélküli ablakhoz ne indítsunk felesleges hálózati kérést.
        # A ténylegesen megjelenített előnézet letölti és cache-eli a csempéket.
        allow_tiles = overlay_config.map.use_raster_tiles and self.isVisible()

        def work():
            frame = extract_preview_frame(video_path, time_seconds, max_width=1280)
            timeline = self.timeline_index or TelemetryTimeline(samples)
            current = timeline.at(time_seconds, offset_seconds=overlay_config.time_offset_seconds)
            hud = HudRenderer().render(current, samples, overlay_config, frame.width, frame.height, allow_tile_network=allow_tiles)
            composite = frame.convert("RGBA")
            composite.alpha_composite(hud)
            return composite.convert("RGB")

        self.preview.set_message("Előnézet készítése…")
        worker = FunctionWorker(work, self)
        self._preview_worker = worker
        worker.succeeded.connect(self._preview_ready)
        worker.failed.connect(self._worker_error)
        worker.finished.connect(self._preview_finished)
        worker.start()

    def _preview_ready(self, image: Image.Image) -> None:
        self._current_pixmap = _pil_to_pixmap(image)
        self.preview.set_pixmap(self._current_pixmap)

    def _preview_finished(self) -> None:
        worker = self._preview_worker
        self._preview_worker = None
        if worker:
            worker.deleteLater()
        if self._preview_pending:
            self._preview_pending = False
            self._schedule_preview()

    def _tile_mode_changed(self, enabled: bool) -> None:
        if enabled:
            QMessageBox.information(
                self,
                "Térképcsempék és adatvédelem",
                "Az aktuális térképnézet csempéi az OpenStreetMap szerveréről töltődnek le. "
                "A videó és az SRT nem kerül feltöltésre, de a csempekérésből a repülés környéke következtethető. "
                "A csempék legalább 7 napig helyi cache-ben maradnak.",
            )
        self._schedule_preview()

    def _clear_tile_cache(self) -> None:
        cache = TileCache(self.paths.cache / "tiles")
        size_mb = cache.size_bytes() / 1024 / 1024
        answer = QMessageBox.question(
            self,
            "Csempecache törlése",
            f"Törlöd a helyi térképcsempe-cache-t ({size_mb:.1f} MB)?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            cache.clear()
            self.statusBar().showMessage("A térképcsempe-cache törölve.", 4000)

    def _overlay_config(self) -> OverlayConfig:
        decimals = (6, 5, 4, 0)[self.gps_decimals.currentIndex()]
        config = OverlayConfig(
            show_speed=self.display_checks["speed"].isChecked(),
            show_altitude=self.display_checks["altitude"].isChecked(),
            show_gps=self.display_checks["gps"].isChecked(),
            show_date=self.display_checks["date"].isChecked(),
            show_time=self.display_checks["time"].isChecked(),
            show_heading=self.display_checks["heading"].isChecked(),
            show_vertical_speed=self.display_checks["vertical"].isChecked(),
            show_distance=self.display_checks["distance"].isChecked(),
            gps_decimals=decimals,
            time_offset_seconds=self.time_offset.value(),
        )
        config.map.visible = self.display_checks["map"].isChecked()
        config.map.style = MapStyle(self.map_style.currentText())
        config.map.position = Corner(self.map_position.currentText())
        config.map.width_ratio = self.map_width.value() / 100
        config.map.height_ratio = self.map_height.value() / 100
        config.map.opacity = round(self.map_opacity.value() / 100 * 255)
        config.map.route_width = self.route_width.value()
        config.map.use_raster_tiles = self.tile_background.isChecked()
        config.map.hide_start_seconds = self.hide_start.value()
        config.map.hide_end_seconds = self.hide_end.value()
        return config

    def _start_export(self) -> None:
        if not self.video_metadata or not self.samples:
            self._error("Előbb válassz videót és feldolgozott SRT-fájlt.")
            return
        output = Path(self.output_path.text())
        if not output.name:
            self._error("Válassz kimeneti MP4-fájlt.")
            return
        if output.exists():
            self._error("A kimeneti fájl már létezik. Válassz új nevet; az alkalmazás nem ír felül fájlt.")
            return
        codec = self.codec.currentData()
        if not codec:
            self._error("A kiválasztott videokodek nem érhető el ebben az FFmpeg buildben.")
            return
        export_config = ExportConfig(codec=codec, quality=self.quality.currentText(), keep_audio=self.keep_audio.isChecked())
        worker = ExportWorker(
            str(self.video_metadata.path), str(output), self.video_metadata, self.samples,
            self._overlay_config(), export_config, self,
        )
        self._export_worker = worker
        worker.progress.connect(self._export_progressed)
        worker.succeeded.connect(self._export_succeeded)
        worker.failed.connect(self._export_failed)
        worker.finished.connect(self._export_finished)
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.export_progress.setValue(0)
        self.export_status.setText("Export indítása…")
        worker.start()

    def _cancel_export(self) -> None:
        if self._export_worker:
            self.export_status.setText("Megszakítás…")
            self._export_worker.cancel()

    def _export_progressed(self, progress: ExportProgress) -> None:
        self.export_progress.setValue(round(progress.fraction * 1000))
        remaining = "számítás…" if progress.remaining_seconds is None else self._time(progress.remaining_seconds)
        self.export_status.setText(
            f"{progress.fraction * 100:.1f}% • eltelt: {self._time(progress.elapsed_seconds)} • hátra: {remaining}"
        )

    def _export_succeeded(self, result) -> None:
        self.export_status.setText(f"Kész: {result.output_path.name} ({result.elapsed_seconds:.1f} s)")
        QMessageBox.information(self, "Export kész", f"A videó elkészült:\n{result.output_path}")

    def _export_failed(self, message: str) -> None:
        self.export_status.setText("Az export megszakadt vagy hibával leállt.")
        self._error(message)

    def _export_finished(self) -> None:
        worker = self._export_worker
        self._export_worker = None
        self.export_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if worker:
            worker.deleteLater()

    def _run_worker(self, function, success) -> None:
        worker = FunctionWorker(function, self)
        self._workers.add(worker)
        worker.succeeded.connect(success)
        worker.failed.connect(self._worker_error)
        worker.finished.connect(lambda w=worker: self._worker_done(w))
        worker.start()

    def _worker_done(self, worker: FunctionWorker) -> None:
        self._workers.discard(worker)
        worker.deleteLater()

    def _worker_error(self, message: str) -> None:
        self.statusBar().showMessage("Hiba történt")
        self._error(message)

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Drone Telemetry Studio", message)

    def closeEvent(self, event) -> None:
        self.preview_debounce.stop()
        self.play_timer.stop()
        if self._export_worker and self._export_worker.isRunning():
            answer = QMessageBox.question(self, "Export folyamatban", "Megszakítod az exportot és bezárod az alkalmazást?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._export_worker.cancel()
            self._export_worker.wait(5000)
        event.accept()
