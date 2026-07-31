from drone_telemetry_studio.domain.telemetry import TelemetrySample, ValidityFlag
from drone_telemetry_studio.telemetry.geo import (
    MotionConfig,
    bearing_deg,
    enrich_motion,
    haversine_distance_m,
    hungarian_compass,
)


def sample(index: int, time: float, lat: float, lon: float, alt: float = 10.0) -> TelemetrySample:
    return TelemetrySample(
        index=index,
        start_time_seconds=time,
        end_time_seconds=time + 0.01,
        latitude=lat,
        longitude=lon,
        relative_altitude_m=alt,
        validity_flags=ValidityFlag.TIME | ValidityFlag.GPS | ValidityFlag.ALTITUDE,
    )


def test_haversine_and_bearing() -> None:
    assert 110_000 < haversine_distance_m(0, 0, 1, 0) < 112_000
    assert bearing_deg(47, 19, 47.001, 19) == 0.0
    assert 89.0 < bearing_deg(47, 19, 47, 19.001) < 91.0
    assert [hungarian_compass(value) for value in (0, 45, 90, 135, 180, 225, 270, 315)] == [
        "É", "ÉK", "K", "DK", "D", "DNy", "Ny", "ÉNy"
    ]


def test_stationary_points_have_zero_speed_and_stable_heading() -> None:
    samples = [sample(i, i * 0.5, 47.0, 19.0) for i in range(6)]
    enrich_motion(samples, MotionConfig(speed_window_seconds=0.5))
    assert all((item.calculated_speed_mps or 0.0) == 0.0 for item in samples[1:])
    assert all(item.calculated_heading_deg is None for item in samples)


def test_speed_distance_vertical_and_outlier_rejection() -> None:
    samples = [
        sample(1, 0.0, 47.0, 19.0, 10.0),
        sample(2, 1.0, 47.000009, 19.0, 11.0),
        sample(3, 2.0, 48.0, 20.0, 50.0),  # fizikailag lehetetlen kiugrás
        sample(4, 3.0, 47.000027, 19.0, 13.0),
    ]
    enrich_motion(samples, MotionConfig(speed_window_seconds=0.5, smoothing_time_constant_seconds=0.1))
    assert 0.7 < (samples[1].raw_speed_mps or 0) < 1.3
    assert samples[2].validity_flags & ValidityFlag.GPS_OUTLIER
    assert samples[3].cumulative_distance_m < 5.0
    assert 0.5 < (samples[3].calculated_vertical_speed_mps or 0) < 1.5

