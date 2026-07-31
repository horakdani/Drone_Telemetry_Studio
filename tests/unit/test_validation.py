from pathlib import Path

from drone_telemetry_studio.domain.telemetry import ParseResult, TelemetrySample, ValidationSummary
from drone_telemetry_studio.domain.video import VideoMetadata
from drone_telemetry_studio.telemetry.validation import validate_video_telemetry


def metadata(duration: float = 2.0, fps: float = 30.0, vfr: bool = False) -> VideoMetadata:
    return VideoMetadata(Path("video.mp4"), duration, 1920, 1080, fps, fps, "h264", "yuv420p", False, None, None, vfr)


def result(duration: float = 2.0, frame_end: int = 61) -> ParseResult:
    samples = [TelemetrySample(1, 0.0, 0.01, frame_count=1), TelemetrySample(2, 2.0, 2.01, frame_count=frame_end)]
    return ParseResult(Path("flight.srt"), samples, validation=ValidationSummary(2, 2, duration_seconds=duration))


def test_consistent_video_and_srt() -> None:
    validation = validate_video_telemetry(metadata(), result())
    assert validation.is_consistent
    assert validation.inferred_telemetry_fps == 30.0


def test_duration_fps_and_vfr_warnings() -> None:
    validation = validate_video_telemetry(metadata(duration=5, fps=60, vfr=True), result(duration=2, frame_end=31))
    assert not validation.is_consistent
    assert len(validation.messages) == 3

