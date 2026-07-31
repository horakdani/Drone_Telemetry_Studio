from datetime import datetime
from pathlib import Path

import pytest

from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser, parse_timecode


def test_parse_timecode() -> None:
    assert parse_timecode("00:09:06,751") == pytest.approx(546.751)
    assert parse_timecode("01:02:03.004") == pytest.approx(3723.004)
    with pytest.raises(ValueError):
        parse_timecode("00:99:00,000")


def test_concrete_dji_record(tmp_path: Path) -> None:
    path = tmp_path / "record.srt"
    path.write_text(
        "\ufeff1\n00:00:00,000 --> 00:00:00,016\n"
        '<font size="28">FrameCnt: 1, DiffTime: 16ms\n'
        "2026-07-29 15:38:08.716\n"
        "[iso: 140] [shutter: 1/640.0] [fnum: 1.8] [ev: 0] "
        "[color_md: default] [focal_len: 24.00] [latitude: 47.452536] "
        "[longitude: 19.053074] [rel_alt: 52.300 abs_alt: 96.452] "
        "[ct: 5399] </font>\n",
        encoding="utf-8",
    )
    result = DjiSrtParser().parse(path)
    assert result.validation.accepted_samples == 1
    sample = result.samples[0]
    assert sample.frame_count == 1
    assert sample.recorded_at == datetime(2026, 7, 29, 15, 38, 8, 716000)
    assert sample.latitude == pytest.approx(47.452536)
    assert sample.longitude == pytest.approx(19.053074)
    assert sample.relative_altitude_m == pytest.approx(52.3)
    assert sample.absolute_altitude_m == pytest.approx(96.452)
    assert sample.iso == 140
    assert sample.shutter == "1/640.0"
    assert sample.aperture == pytest.approx(1.8)
    assert sample.focal_length_mm == pytest.approx(24.0)


def test_bad_block_does_not_stop_parser(tmp_path: Path) -> None:
    path = tmp_path / "mixed.srt"
    path.write_text(
        "1\nnot a time\n[latitude: 999]\n\n"
        "2\n00:00:01,000 --> 00:00:01,020\n"
        "[latitude: 47.0] [longitude: 19.0]\n",
        encoding="utf-8",
    )
    result = DjiSrtParser().parse(path)
    assert len(result.samples) == 1
    assert result.validation.rejected_blocks == 1
    assert result.warnings


def test_optional_fields_and_invalid_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "optional.srt"
    path.write_text(
        "1\n00:00:00,000 --> 00:00:00,100\n"
        "FrameCnt: 9\n[latitude: -91] [longitude: 181] [rel_alt: -2.5]\n",
        encoding="utf-8",
    )
    sample = DjiSrtParser().parse(path).samples[0]
    assert sample.latitude is None
    assert sample.longitude is None
    assert sample.relative_altitude_m == pytest.approx(-2.5)
    assert sample.iso is None

