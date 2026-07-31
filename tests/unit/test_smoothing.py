import pytest

from drone_telemetry_studio.telemetry.smoothing import exponential_moving_average


def test_exponential_moving_average_handles_missing_values() -> None:
    values = exponential_moving_average([0.0, 10.0, None, 10.0], 0.5)
    assert values == pytest.approx([0.0, 5.0, 5.0, 7.5])

