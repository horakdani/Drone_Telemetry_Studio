from pathlib import Path

from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser


def test_repository_sample_is_monotonic() -> None:
    path = Path(__file__).parents[2] / "samples" / "DJI_DEMO.SRT"
    result = DjiSrtParser().parse(path)
    assert len(result.samples) == 7
    assert result.validation.is_usable
    assert result.samples[0].frame_count == 1
    assert result.samples[-1].frame_count == 181
    times = [sample.start_time_seconds for sample in result.samples]
    assert times == sorted(times)

