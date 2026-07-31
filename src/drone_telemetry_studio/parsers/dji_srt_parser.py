from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, TextIO

from drone_telemetry_studio.domain.telemetry import (
    ParseResult,
    ParserWarning,
    TelemetrySample,
    ValidationSummary,
    ValidityFlag,
)

_TIMECODE_RE = re.compile(
    r"^\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_TAG_RE = re.compile(r"<[^>]{0,512}>")
_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
_KEY_VALUE_RE = re.compile(r"([A-Za-z_]+)\s*:\s*([^\s\]]+)")
_FRAME_RE = re.compile(r"FrameCnt\s*:\s*(\d+)", re.IGNORECASE)
_DIFF_RE = re.compile(r"DiffTime\s*:\s*([-+]?\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)\b")


def parse_timecode(value: str) -> float:
    """Egyetlen SRT-időkódot alakít másodperccé."""
    match = re.fullmatch(r"\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})\s*", value)
    if not match:
        raise ValueError(f"Hibás SRT-időkód: {value!r}")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Érvénytelen SRT-időkód: {value!r}")
    return hours * 3600 + minutes * 60 + seconds + millis / (10 ** len(match.group(4)))


def _blocks(stream: TextIO) -> Iterable[list[str]]:
    """Blokkonként olvas; így nagy SRT-nél sincs szükség a teljes fájl duplázására."""
    block: list[str] = []
    for raw_line in stream:
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            if block:
                yield block
                block = []
        else:
            block.append(line.lstrip("\ufeff") if not block else line)
    if block:
        yield block


def _number(values: dict[str, str], key: str, cast: type[float] | type[int] = float):
    raw = values.get(key)
    if raw is None:
        return None
    try:
        return cast(raw.replace(",", "."))
    except (ValueError, TypeError):
        return None


class DjiSrtParser:
    """Megengedő DJI SRT parser részletes, nem végzetes figyelmeztetésekkel."""

    def parse(self, path: str | Path) -> ParseResult:
        source = Path(path)
        warnings: list[ParserWarning] = []
        samples: list[TelemetrySample] = []
        summary = ValidationSummary()

        with source.open("r", encoding="utf-8-sig", errors="replace", newline=None) as stream:
            for block_no, block in enumerate(_blocks(stream), 1):
                summary.total_blocks += 1
                try:
                    sample = self._parse_block(block, block_no, warnings)
                except ValueError as exc:
                    summary.rejected_blocks += 1
                    warnings.append(ParserWarning(block_no, str(exc)))
                    continue
                if sample is None:
                    summary.rejected_blocks += 1
                    warnings.append(ParserWarning(block_no, "A blokk nem tartalmaz felismerhető idősávot."))
                    continue
                if samples and sample.start_time_seconds < samples[-1].start_time_seconds:
                    summary.non_monotonic_timestamps += 1
                    warnings.append(ParserWarning(block_no, "Az időbélyeg visszafelé lép."))
                if not sample.has_valid_gps:
                    summary.invalid_gps_samples += 1
                if sample.recorded_at is None:
                    summary.missing_recorded_at += 1
                samples.append(sample)

        summary.accepted_samples = len(samples)
        if samples:
            summary.duration_seconds = max(sample.end_time_seconds for sample in samples)
        return ParseResult(source, samples, warnings, summary)

    def _parse_block(
        self, block: list[str], block_no: int, warnings: list[ParserWarning]
    ) -> TelemetrySample | None:
        time_match = None
        for line in block:
            time_match = _TIMECODE_RE.match(line)
            if time_match:
                break
        if not time_match:
            return None

        groups = time_match.groups()
        start = parse_timecode(f"{groups[0]}:{groups[1]}:{groups[2]},{groups[3]}")
        end = parse_timecode(f"{groups[4]}:{groups[5]}:{groups[6]},{groups[7]}")
        if end < start:
            raise ValueError("Az SRT-blokk záró ideje megelőzi a kezdőidőt.")

        cleaned = "\n".join(_TAG_RE.sub("", line) for line in block)
        frame_match = _FRAME_RE.search(cleaned)
        diff_match = _DIFF_RE.search(cleaned)
        date_match = _DATE_RE.search(cleaned)
        values: dict[str, str] = {}
        for content in _BRACKET_RE.findall(cleaned):
            for key, value in _KEY_VALUE_RE.findall(content):
                values[key.lower()] = value

        recorded_at = None
        if date_match:
            normalized = date_match.group(1).replace(",", ".")
            try:
                recorded_at = datetime.fromisoformat(normalized)
            except ValueError:
                warnings.append(ParserWarning(block_no, "A rögzítési dátum nem értelmezhető."))

        latitude = _number(values, "latitude")
        longitude = _number(values, "longitude")
        gps_valid = (
            latitude is not None
            and longitude is not None
            and -90.0 <= latitude <= 90.0
            and -180.0 <= longitude <= 180.0
            and not (latitude == 0.0 and longitude == 0.0)
        )
        if not gps_valid and (latitude is not None or longitude is not None):
            warnings.append(ParserWarning(block_no, "Érvénytelen vagy nullsziget GPS-koordináta."))

        flags = ValidityFlag.TIME
        if gps_valid:
            flags |= ValidityFlag.GPS
        rel_alt = _number(values, "rel_alt")
        abs_alt = _number(values, "abs_alt")
        if rel_alt is not None or abs_alt is not None:
            flags |= ValidityFlag.ALTITUDE
        if any(key in values for key in ("iso", "shutter", "fnum", "focal_len")):
            flags |= ValidityFlag.CAMERA

        return TelemetrySample(
            index=int(block[0].strip()) if block and block[0].strip().isdigit() else block_no,
            start_time_seconds=start,
            end_time_seconds=end,
            frame_count=int(frame_match.group(1)) if frame_match else None,
            diff_time_ms=float(diff_match.group(1)) if diff_match else None,
            recorded_at=recorded_at,
            latitude=latitude if gps_valid else None,
            longitude=longitude if gps_valid else None,
            relative_altitude_m=rel_alt,
            absolute_altitude_m=abs_alt,
            iso=_number(values, "iso", int),
            shutter=values.get("shutter"),
            aperture=_number(values, "fnum"),
            exposure_value=_number(values, "ev"),
            color_mode=values.get("color_md"),
            focal_length_mm=_number(values, "focal_len"),
            color_temperature=_number(values, "ct", int),
            validity_flags=flags,
        )

