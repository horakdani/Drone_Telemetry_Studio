from __future__ import annotations

import math
from dataclasses import dataclass

from drone_telemetry_studio.domain.telemetry import TelemetrySample, ValidityFlag
from drone_telemetry_studio.telemetry.smoothing import ema_alpha

EARTH_RADIUS_M = 6_371_008.8


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Nagykör-távolság méterben, rövid drónutakhoz elegendő pontossággal."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Kezdő irányszög: észak 0°, kelet 90°, 0–360° tartomány."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def hungarian_compass(degrees: float | None) -> str:
    if degrees is None:
        return "–"
    labels = ("É", "ÉK", "K", "DK", "D", "DNy", "Ny", "ÉNy")
    return labels[int((degrees % 360 + 22.5) // 45) % 8]


@dataclass(slots=True)
class MotionConfig:
    speed_window_seconds: float = 0.5
    smoothing_time_constant_seconds: float = 0.65
    max_speed_mps: float = 45.0
    stationary_threshold_mps: float = 0.35
    gps_deadband_m: float = 0.15
    vertical_window_seconds: float = 0.5
    max_vertical_speed_mps: float = 15.0


def enrich_motion(
    samples: list[TelemetrySample], config: MotionConfig | None = None
) -> list[TelemetrySample]:
    """GPS/altitude értékekből sebességet, irányt és távolságot számít.

    Az inputot helyben egészíti ki, így több százezer rekordnál sem készít még egy
    teljes objektumlistát. A nyers és simított sebesség külön mezőben marad.
    """
    cfg = config or MotionConfig()
    accepted_gps: list[TelemetrySample] = []
    altitude_history: list[TelemetrySample] = []
    gps_anchor_index = 0
    altitude_anchor_index = 0
    cumulative = 0.0
    speed_state: float | None = None
    vertical_state: float | None = None
    last_heading: float | None = None
    previous_time: float | None = None
    start_gps: TelemetrySample | None = None

    for sample in samples:
        now = sample.start_time_seconds
        delta = 0.0 if previous_time is None else max(0.0, now - previous_time)
        previous_time = now

        if sample.has_valid_gps and sample.latitude is not None and sample.longitude is not None:
            accepted = True
            if accepted_gps:
                previous = accepted_gps[-1]
                dt = now - previous.start_time_seconds
                segment = haversine_distance_m(
                    previous.latitude, previous.longitude, sample.latitude, sample.longitude  # type: ignore[arg-type]
                )
                if dt <= 0 or segment / dt > cfg.max_speed_mps:
                    accepted = False
                    sample.validity_flags |= ValidityFlag.GPS_OUTLIER
                else:
                    cumulative += segment
            if accepted:
                start_gps = start_gps or sample
                target = now - cfg.speed_window_seconds
                while (
                    gps_anchor_index + 1 < len(accepted_gps)
                    and accepted_gps[gps_anchor_index + 1].start_time_seconds <= target
                ):
                    gps_anchor_index += 1
                anchor = (
                    accepted_gps[gps_anchor_index]
                    if accepted_gps and accepted_gps[gps_anchor_index].start_time_seconds <= target
                    else None
                )
                if anchor is not None:
                    dt = now - anchor.start_time_seconds
                    distance = haversine_distance_m(
                        anchor.latitude, anchor.longitude, sample.latitude, sample.longitude  # type: ignore[arg-type]
                    )
                    raw_speed = distance / dt if dt > 0 else None
                    if raw_speed is not None and raw_speed <= cfg.max_speed_mps:
                        if distance < cfg.gps_deadband_m:
                            raw_speed = 0.0
                        sample.raw_speed_mps = raw_speed
                        if raw_speed >= cfg.stationary_threshold_mps:
                            last_heading = bearing_deg(
                                anchor.latitude, anchor.longitude, sample.latitude, sample.longitude  # type: ignore[arg-type]
                            )
                accepted_gps.append(sample)
            sample.cumulative_distance_m = cumulative
            if start_gps is not None:
                sample.distance_from_start_m = haversine_distance_m(
                    start_gps.latitude, start_gps.longitude, sample.latitude, sample.longitude  # type: ignore[arg-type]
                )
        else:
            sample.cumulative_distance_m = cumulative

        if sample.raw_speed_mps is not None:
            alpha = ema_alpha(delta or cfg.speed_window_seconds, cfg.smoothing_time_constant_seconds)
            speed_state = (
                sample.raw_speed_mps
                if speed_state is None
                else speed_state + alpha * (sample.raw_speed_mps - speed_state)
            )
        if speed_state is not None:
            sample.calculated_speed_mps = speed_state
            sample.calculated_speed_kmh = speed_state * 3.6
            sample.validity_flags |= ValidityFlag.DERIVED_SPEED
        if last_heading is not None:
            sample.calculated_heading_deg = last_heading
            sample.validity_flags |= ValidityFlag.DERIVED_HEADING

        if sample.relative_altitude_m is not None:
            target = now - cfg.vertical_window_seconds
            while (
                altitude_anchor_index + 1 < len(altitude_history)
                and altitude_history[altitude_anchor_index + 1].start_time_seconds <= target
            ):
                altitude_anchor_index += 1
            anchor = (
                altitude_history[altitude_anchor_index]
                if altitude_history and altitude_history[altitude_anchor_index].start_time_seconds <= target
                else None
            )
            altitude_history.append(sample)
            if anchor is not None and anchor.relative_altitude_m is not None:
                dt = now - anchor.start_time_seconds
                raw_vertical = (sample.relative_altitude_m - anchor.relative_altitude_m) / dt
                if dt > 0 and abs(raw_vertical) <= cfg.max_vertical_speed_mps:
                    alpha = ema_alpha(delta or cfg.vertical_window_seconds, cfg.smoothing_time_constant_seconds)
                    vertical_state = (
                        raw_vertical
                        if vertical_state is None
                        else vertical_state + alpha * (raw_vertical - vertical_state)
                    )
        sample.calculated_vertical_speed_mps = vertical_state

    return samples
