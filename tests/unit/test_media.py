from pathlib import Path

from drone_telemetry_studio.domain.overlay import ExportConfig
from drone_telemetry_studio.domain.video import VideoMetadata
from drone_telemetry_studio.media.export_pipeline import build_export_command


def metadata(path: Path) -> VideoMetadata:
    return VideoMetadata(path, 2.0, 1920, 1080, 30, 30, "h264", "yuv420p", True, "aac", None, False)


def test_export_command_is_argument_list_and_preserves_audio(tmp_path: Path) -> None:
    source = tmp_path / "DJI video ; special.mp4"
    output = tmp_path / "result file.mp4"
    command = build_export_command("ffmpeg", source, output, metadata(source), ExportConfig())
    assert command[command.index("-i") + 1] == str(source)
    assert "0:a?" in command
    assert "shell=True" not in command
    assert command[-1] == str(output)


def test_hardware_quality_does_not_use_crf(tmp_path: Path) -> None:
    source = tmp_path / "a.mp4"
    command = build_export_command(
        "ffmpeg", source, tmp_path / "b.mp4", metadata(source),
        ExportConfig(codec="h264_videotoolbox", quality="High"),
    )
    assert "-b:v" in command
    assert "-crf" not in command

