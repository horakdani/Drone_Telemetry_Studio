from __future__ import annotations

from dataclasses import dataclass, field

from drone_telemetry_studio.domain.telemetry import ParseResult
from drone_telemetry_studio.domain.video import VideoMetadata


@dataclass(slots=True)
class SyncValidation:
    duration_difference_seconds: float
    inferred_telemetry_fps: float | None
    messages: list[str] = field(default_factory=list)

    @property
    def is_consistent(self) -> bool:
        return not self.messages


def validate_video_telemetry(metadata: VideoMetadata, result: ParseResult) -> SyncValidation:
    """Compares the SRT relative timeline and FrameCnt fields with the FFprobe data."""
    duration_difference = result.validation.duration_seconds - metadata.duration_seconds
    messages: list[str] = []
    tolerance = max(0.5, metadata.duration_seconds * 0.01)
    if abs(duration_difference) > tolerance:
        messages.append(f"Video and SRT durations differ by {duration_difference:+.2f} s.")
    samples = result.samples
    if samples and abs(samples[0].start_time_seconds) > 0.1:
        messages.append(f"The SRT does not start at 0 ({samples[0].start_time_seconds:.3f} s).")
    inferred_fps = None
    framed = [sample for sample in samples if sample.frame_count is not None]
    if len(framed) >= 2:
        delta_time = framed[-1].start_time_seconds - framed[0].start_time_seconds
        delta_frames = framed[-1].frame_count - framed[0].frame_count  # type: ignore[operator]
        if delta_time > 0 and delta_frames > 0:
            inferred_fps = delta_frames / delta_time
            if metadata.average_fps > 0 and abs(inferred_fps - metadata.average_fps) / metadata.average_fps > 0.05:
                messages.append(
                    f"FrameCnt implies {inferred_fps:.3f} fps, but the video measures {metadata.average_fps:.3f} fps."
                )
        frame_counts = [sample.frame_count for sample in framed]
        if any(right <= left for left, right in zip(frame_counts, frame_counts[1:])):  # type: ignore[operator]
            messages.append("FrameCnt values are not strictly increasing.")
    if metadata.is_variable_frame_rate:
        messages.append("The video has a variable frame rate; export is timestamp-based.")
    if result.validation.non_monotonic_timestamps:
        messages.append("The SRT relative timestamps are not monotonically increasing.")
    return SyncValidation(duration_difference, inferred_fps, messages)

