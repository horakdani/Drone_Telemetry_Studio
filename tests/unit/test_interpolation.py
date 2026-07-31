from datetime import datetime, timedelta

import pytest

from drone_telemetry_studio.domain.telemetry import TelemetrySample, ValidityFlag
from drone_telemetry_studio.telemetry.interpolation import TelemetryTimeline, sample_at


def test_linear_and_circular_interpolation() -> None:
    start = datetime(2026, 1, 1)
    left = TelemetrySample(
        1, 0.0, 0.1, recorded_at=start, latitude=47.0, longitude=19.0,
        calculated_speed_kmh=10.0, calculated_heading_deg=350.0,
        validity_flags=ValidityFlag.TIME | ValidityFlag.GPS,
    )
    right = TelemetrySample(
        2, 1.0, 1.1, recorded_at=start + timedelta(seconds=1), latitude=48.0,
        longitude=20.0, calculated_speed_kmh=20.0, calculated_heading_deg=10.0,
        validity_flags=ValidityFlag.TIME | ValidityFlag.GPS,
    )
    result = sample_at([left, right], 0.5)
    assert result is not None
    assert result.latitude == pytest.approx(47.5)
    assert result.calculated_speed_kmh == pytest.approx(15.0)
    assert result.calculated_heading_deg == pytest.approx(0.0)
    assert result.recorded_at == start + timedelta(seconds=0.5)


def test_long_gap_can_invalidate_gps() -> None:
    left = TelemetrySample(1, 0, 0.1, latitude=47, longitude=19, validity_flags=ValidityFlag.GPS)
    right = TelemetrySample(2, 10, 10.1, latitude=48, longitude=20, validity_flags=ValidityFlag.GPS)
    result = sample_at([left, right], 5, max_interpolation_gap_seconds=2, hold_last_on_gap=False)
    assert result is not None
    assert result.latitude is None
    assert not result.has_valid_gps


def test_reusable_timeline_index() -> None:
    samples = [TelemetrySample(index, float(index), float(index) + 0.1) for index in range(10)]
    timeline = TelemetryTimeline(samples)
    assert timeline.at(5.5).start_time_seconds == pytest.approx(5.5)
    assert timeline.at(7.25).start_time_seconds == pytest.approx(7.25)
