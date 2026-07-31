from __future__ import annotations

import logging
import math
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from drone_telemetry_studio.domain.overlay import ExportConfig, OverlayConfig
from drone_telemetry_studio.domain.telemetry import TelemetrySample
from drone_telemetry_studio.domain.video import VideoMetadata
from drone_telemetry_studio.media.ffmpeg import discover_media_tools
from drone_telemetry_studio.overlay.renderer import HudRenderer
from drone_telemetry_studio.telemetry.interpolation import TelemetryTimeline

LOGGER = logging.getLogger(__name__)


class ExportCancelled(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExportProgress:
    fraction: float
    elapsed_seconds: float
    remaining_seconds: float | None


@dataclass(frozen=True, slots=True)
class ExportResult:
    output_path: Path
    elapsed_seconds: float
    rendered_overlay_frames: int


def _quality_arguments(codec: str, quality: str) -> list[str]:
    if codec in {"h264_videotoolbox", "hevc_videotoolbox"}:
        bitrate = {"Gyors": "10M", "Kiegyensúlyozott": "18M", "Kiváló": "30M"}[quality]
        return ["-b:v", bitrate, "-allow_sw", "1"]
    crf = {"Gyors": "25", "Kiegyensúlyozott": "21", "Kiváló": "18"}[quality]
    preset = {"Gyors": "veryfast", "Kiegyensúlyozott": "medium", "Kiváló": "slow"}[quality]
    return ["-crf", crf, "-preset", preset]


def build_export_command(
    ffmpeg_path: str,
    input_path: Path,
    temporary_output: Path,
    metadata: VideoMetadata,
    config: ExportConfig,
) -> list[str]:
    """Argumentumlista; sem shell, sem felhasználói útvonal-interpoláció nincs."""
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{config.overlay_width}x{config.overlay_height}",
        "-framerate",
        f"{config.overlay_fps:g}",
        "-i",
        "pipe:0",
        "-filter_complex",
        f"[1:v]scale={metadata.width}:{metadata.height}:flags=lanczos,format=rgba[hud];"
        "[0:v][hud]overlay=0:0:format=auto:shortest=1[v]",
        "-map",
        "[v]",
    ]
    if config.keep_audio and metadata.has_audio:
        command += ["-map", "0:a?", "-c:a", "copy"]
    else:
        command += ["-an"]
    command += ["-c:v", config.codec, *_quality_arguments(config.codec, config.quality)]
    if config.codec in {"libx264", "h264_videotoolbox"}:
        command += ["-pix_fmt", "yuv420p"]
    command += [
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:2",
        "-nostats",
        str(temporary_output),
    ]
    return command


class ExportPipeline:
    def __init__(self, renderer: HudRenderer | None = None, ffmpeg_path: str | None = None) -> None:
        self.renderer = renderer or HudRenderer()
        self.ffmpeg_path = ffmpeg_path or discover_media_tools().ffmpeg
        self._process: subprocess.Popen | None = None

    def cancel(self) -> None:
        process = self._process
        if process and process.poll() is None:
            process.terminate()

    def export(
        self,
        input_path: str | Path,
        output_path: str | Path,
        metadata: VideoMetadata,
        samples: list[TelemetrySample],
        overlay_config: OverlayConfig,
        export_config: ExportConfig,
        *,
        cancel_event: threading.Event | None = None,
        progress_callback: Callable[[ExportProgress], None] | None = None,
    ) -> ExportResult:
        source, output = Path(input_path).resolve(), Path(output_path).resolve()
        if source == output:
            raise ValueError("Az eredeti videó nem írható felül.")
        if output.exists():
            raise FileExistsError("A kimeneti fájl már létezik; válassz új nevet.")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.part.mp4")
        command = build_export_command(self.ffmpeg_path, source, temporary, metadata, export_config)
        LOGGER.info("Export indul: input=%s output=%s codec=%s", source.name, output.name, export_config.codec)
        started = time.monotonic()
        stderr_tail: list[str] = []
        latest_media_time = [0.0]
        stop_reader = threading.Event()

        def read_progress(process: subprocess.Popen) -> None:
            assert process.stderr is not None
            for raw in iter(process.stderr.readline, b""):
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    stderr_tail.append(line)
                    del stderr_tail[:-100]
                if line.startswith("out_time_us="):
                    try:
                        latest_media_time[0] = int(line.split("=", 1)[1]) / 1_000_000
                    except ValueError:
                        pass
                if progress_callback and metadata.duration_seconds > 0:
                    elapsed = time.monotonic() - started
                    fraction = min(1.0, latest_media_time[0] / metadata.duration_seconds)
                    remaining = elapsed * (1 - fraction) / fraction if fraction > 0.001 else None
                    progress_callback(ExportProgress(fraction, elapsed, remaining))
                if stop_reader.is_set():
                    break

        rendered = 0
        timeline = TelemetryTimeline(samples)
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            reader = threading.Thread(target=read_progress, args=(self._process,), daemon=True)
            reader.start()
            assert self._process.stdin is not None
            frame_count = max(1, math.ceil(metadata.duration_seconds * export_config.overlay_fps) + 1)
            for frame_index in range(frame_count):
                if (cancel_event and cancel_event.is_set()) or self._process.poll() is not None:
                    break
                time_seconds = min(metadata.duration_seconds, frame_index / export_config.overlay_fps)
                current = timeline.at(
                    time_seconds,
                    offset_seconds=overlay_config.time_offset_seconds,
                )
                overlay = self.renderer.render(
                    current,
                    samples,
                    overlay_config,
                    export_config.overlay_width,
                    export_config.overlay_height,
                )
                try:
                    self._process.stdin.write(overlay.tobytes())
                except BrokenPipeError:
                    break
                rendered += 1
            try:
                self._process.stdin.close()
            except BrokenPipeError:
                pass
            if cancel_event and cancel_event.is_set():
                self._process.terminate()
            return_code = self._process.wait(timeout=120)
            stop_reader.set()
            reader.join(timeout=2)
            if cancel_event and cancel_event.is_set():
                raise ExportCancelled("Az exportot a felhasználó megszakította.")
            if return_code != 0:
                detail = "\n".join(stderr_tail[-20:])
                raise RuntimeError(f"Az FFmpeg export sikertelen.\n{detail}")
            if not temporary.exists() or temporary.stat().st_size == 0:
                raise RuntimeError("Az FFmpeg nem hozott létre lejátszható kimenetet.")
            os.replace(temporary, output)
            elapsed = time.monotonic() - started
            if progress_callback:
                progress_callback(ExportProgress(1.0, elapsed, 0.0))
            LOGGER.info("Export kész: %s, %.2f s", output.name, elapsed)
            return ExportResult(output, elapsed, rendered)
        finally:
            stop_reader.set()
            process = self._process
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            self._process = None
            if temporary.exists():
                temporary.unlink()
