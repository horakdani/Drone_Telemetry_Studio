from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from drone_telemetry_studio.domain.overlay import ExportConfig, OverlayConfig
from drone_telemetry_studio.media.export_pipeline import ExportCancelled, ExportPipeline
from drone_telemetry_studio.media.ffmpeg import discover_media_tools
from drone_telemetry_studio.media.ffprobe import probe_video
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion


def create_test_video(path: Path, duration: float = 2.0) -> None:
    ffmpeg = discover_media_tools().ffmpeg
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
        timeout=60,
    )


def demo_samples() -> list:
    root = Path(__file__).parents[2]
    samples = DjiSrtParser().parse(root / "samples/DJI_DEMO.SRT").samples
    return enrich_motion(samples)


def test_probe_and_overlay_export_preserves_audio(tmp_path: Path) -> None:
    source = tmp_path / "input with space.mp4"
    output = tmp_path / "export.mp4"
    create_test_video(source)
    metadata = probe_video(source)
    assert metadata.width == 640
    assert metadata.height == 360
    assert metadata.has_audio
    progress = []
    result = ExportPipeline().export(
        source,
        output,
        metadata,
        demo_samples(),
        OverlayConfig(),
        ExportConfig(overlay_fps=5, overlay_width=320, overlay_height=180, quality="Gyors"),
        progress_callback=progress.append,
    )
    exported = probe_video(result.output_path)
    assert output.stat().st_size > 20_000
    assert exported.has_audio
    assert exported.duration_seconds == pytest.approx(2.0, abs=0.15)
    assert progress[-1].fraction == 1.0


def test_cancelled_export_cleans_temporary_file(tmp_path: Path) -> None:
    source = tmp_path / "input.mp4"
    output = tmp_path / "cancelled.mp4"
    create_test_video(source, duration=1.0)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ExportCancelled):
        ExportPipeline().export(
            source,
            output,
            probe_video(source),
            demo_samples(),
            OverlayConfig(),
            ExportConfig(overlay_fps=2, overlay_width=160, overlay_height=90, quality="Gyors"),
            cancel_event=cancel,
        )
    assert not output.exists()
    assert not list(tmp_path.glob("*.part.mp4"))
