from __future__ import annotations

import math
from collections.abc import Iterable


def ema_alpha(delta_seconds: float, time_constant_seconds: float) -> float:
    """Time-based EMA coefficient, independent of the sampling rate."""
    if time_constant_seconds <= 0:
        return 1.0
    return 1.0 - math.exp(-max(0.0, delta_seconds) / time_constant_seconds)


def exponential_moving_average(
    values: Iterable[float | None], alpha: float
) -> list[float | None]:
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1.")
    output: list[float | None] = []
    state: float | None = None
    for value in values:
        if value is not None:
            state = value if state is None else state + alpha * (value - state)
        output.append(state)
    return output

