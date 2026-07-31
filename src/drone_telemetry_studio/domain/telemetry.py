from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntFlag, auto
from pathlib import Path


class ValidityFlag(IntFlag):
    """Az egyes mintaértékek érvényességét bitenként tárolja."""

    NONE = 0
    TIME = auto()
    GPS = auto()
    ALTITUDE = auto()
    CAMERA = auto()
    DERIVED_SPEED = auto()
    DERIVED_HEADING = auto()
    GPS_OUTLIER = auto()
    INTERPOLATED = auto()
    HELD = auto()


@dataclass(slots=True)
class TelemetrySample:
    index: int
    start_time_seconds: float
    end_time_seconds: float
    frame_count: int | None = None
    diff_time_ms: float | None = None
    recorded_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    relative_altitude_m: float | None = None
    absolute_altitude_m: float | None = None
    iso: int | None = None
    shutter: str | None = None
    aperture: float | None = None
    exposure_value: float | None = None
    color_mode: str | None = None
    focal_length_mm: float | None = None
    color_temperature: int | None = None
    raw_speed_mps: float | None = None
    calculated_speed_mps: float | None = None
    calculated_speed_kmh: float | None = None
    calculated_heading_deg: float | None = None
    calculated_vertical_speed_mps: float | None = None
    cumulative_distance_m: float = 0.0
    distance_from_start_m: float | None = None
    validity_flags: ValidityFlag = ValidityFlag.NONE

    @property
    def has_valid_gps(self) -> bool:
        return bool(self.validity_flags & ValidityFlag.GPS)


@dataclass(slots=True)
class ParserWarning:
    block_index: int
    message: str


@dataclass(slots=True)
class ValidationSummary:
    total_blocks: int = 0
    accepted_samples: int = 0
    rejected_blocks: int = 0
    invalid_gps_samples: int = 0
    non_monotonic_timestamps: int = 0
    missing_recorded_at: int = 0
    duration_seconds: float = 0.0

    @property
    def is_usable(self) -> bool:
        return self.accepted_samples > 0 and self.non_monotonic_timestamps == 0


@dataclass(slots=True)
class ParseResult:
    source: Path
    samples: list[TelemetrySample]
    warnings: list[ParserWarning] = field(default_factory=list)
    validation: ValidationSummary = field(default_factory=ValidationSummary)

