from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field, replace
from datetime import timedelta

from drone_telemetry_studio.domain.telemetry import TelemetrySample, ValidityFlag


def _lerp(left: float | None, right: float | None, factor: float) -> float | None:
    if left is None or right is None:
        return left if factor < 0.5 else right
    return left + (right - left) * factor


def _lerp_heading(left: float | None, right: float | None, factor: float) -> float | None:
    if left is None or right is None:
        return left if factor < 0.5 else right
    delta = ((right - left + 180.0) % 360.0) - 180.0
    return (left + delta * factor) % 360.0


@dataclass(slots=True)
class TelemetryTimeline:
    """Egyszer felépített időindex; export közben O(log n) mintakeresést ad."""

    samples: list[TelemetrySample]
    _times: list[float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._times = [sample.start_time_seconds for sample in self.samples]

    def at(
        self,
        video_time_seconds: float,
        *,
        offset_seconds: float = 0.0,
        max_interpolation_gap_seconds: float = 2.0,
        hold_last_on_gap: bool = True,
    ) -> TelemetrySample | None:
        return _sample_at_indexed(
            self.samples,
            self._times,
            video_time_seconds,
            offset_seconds=offset_seconds,
            max_interpolation_gap_seconds=max_interpolation_gap_seconds,
            hold_last_on_gap=hold_last_on_gap,
        )


def _sample_at_indexed(
    samples: list[TelemetrySample],
    times: list[float],
    video_time_seconds: float,
    *,
    offset_seconds: float = 0.0,
    max_interpolation_gap_seconds: float = 2.0,
    hold_last_on_gap: bool = True,
) -> TelemetrySample | None:
    if not samples:
        return None
    target = video_time_seconds + offset_seconds
    position = bisect_right(times, target)
    if position <= 0:
        return replace(samples[0], validity_flags=samples[0].validity_flags | ValidityFlag.HELD)
    if position >= len(samples):
        return replace(samples[-1], validity_flags=samples[-1].validity_flags | ValidityFlag.HELD)

    left, right = samples[position - 1], samples[position]
    gap = right.start_time_seconds - left.start_time_seconds
    if gap <= 0:
        return replace(left)
    if gap > max_interpolation_gap_seconds:
        if not hold_last_on_gap:
            held = replace(left, latitude=None, longitude=None)
            held.validity_flags &= ~ValidityFlag.GPS
            return held
        return replace(left, validity_flags=left.validity_flags | ValidityFlag.HELD)

    factor = (target - left.start_time_seconds) / gap
    recorded_at = None
    if left.recorded_at and right.recorded_at:
        recorded_at = left.recorded_at + timedelta(
            seconds=(right.recorded_at - left.recorded_at).total_seconds() * factor
        )
    elif left.recorded_at or right.recorded_at:
        recorded_at = left.recorded_at if factor < 0.5 else right.recorded_at

    return replace(
        left,
        index=left.index,
        start_time_seconds=target,
        end_time_seconds=target,
        frame_count=round(_lerp(float(left.frame_count), float(right.frame_count), factor))
        if left.frame_count is not None and right.frame_count is not None
        else left.frame_count,
        recorded_at=recorded_at,
        latitude=_lerp(left.latitude, right.latitude, factor),
        longitude=_lerp(left.longitude, right.longitude, factor),
        relative_altitude_m=_lerp(left.relative_altitude_m, right.relative_altitude_m, factor),
        absolute_altitude_m=_lerp(left.absolute_altitude_m, right.absolute_altitude_m, factor),
        raw_speed_mps=_lerp(left.raw_speed_mps, right.raw_speed_mps, factor),
        calculated_speed_mps=_lerp(left.calculated_speed_mps, right.calculated_speed_mps, factor),
        calculated_speed_kmh=_lerp(left.calculated_speed_kmh, right.calculated_speed_kmh, factor),
        calculated_heading_deg=_lerp_heading(
            left.calculated_heading_deg, right.calculated_heading_deg, factor
        ),
        calculated_vertical_speed_mps=_lerp(
            left.calculated_vertical_speed_mps, right.calculated_vertical_speed_mps, factor
        ),
        cumulative_distance_m=_lerp(
            left.cumulative_distance_m, right.cumulative_distance_m, factor
        )
        or 0.0,
        distance_from_start_m=_lerp(left.distance_from_start_m, right.distance_from_start_m, factor),
        validity_flags=left.validity_flags | right.validity_flags | ValidityFlag.INTERPOLATED,
    )


def sample_at(
    samples: list[TelemetrySample],
    video_time_seconds: float,
    *,
    offset_seconds: float = 0.0,
    max_interpolation_gap_seconds: float = 2.0,
    hold_last_on_gap: bool = True,
) -> TelemetrySample | None:
    """Kényelmi egyszeri lekérdezés; ismételt használathoz `TelemetryTimeline` való."""
    return TelemetryTimeline(samples).at(
        video_time_seconds,
        offset_seconds=offset_seconds,
        max_interpolation_gap_seconds=max_interpolation_gap_seconds,
        hold_last_on_gap=hold_last_on_gap,
    )
