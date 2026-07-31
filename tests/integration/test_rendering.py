from dataclasses import replace
from pathlib import Path

from drone_telemetry_studio.domain.overlay import OverlayConfig
from drone_telemetry_studio.overlay.renderer import HudRenderer
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion
from drone_telemetry_studio.telemetry.interpolation import sample_at


def test_static_hud_and_map_render(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    samples = DjiSrtParser().parse(root / "samples/DJI_DEMO.SRT").samples
    enrich_motion(samples)
    current = sample_at(samples, 1.5)
    image = HudRenderer().render(current, samples, OverlayConfig(), 1920, 1080)
    output = tmp_path / "hud.png"
    image.save(output)
    assert image.size == (1920, 1080)
    assert image.getbbox() is not None
    assert output.stat().st_size > 10_000


def test_telemetry_cards_fit_their_text() -> None:
    root = Path(__file__).parents[2]
    samples = DjiSrtParser().parse(root / "samples/DJI_DEMO.SRT").samples
    current = samples[0]
    config = OverlayConfig(
        show_altitude=False,
        show_gps=False,
        show_date=False,
        show_time=False,
        show_heading=False,
    )
    config.map.visible = False

    short_card = HudRenderer().render(
        replace(current, calculated_speed_kmh=None), samples, config, 1920, 1080
    )
    long_card = HudRenderer().render(
        replace(current, calculated_speed_kmh=12_345.6), samples, config, 1920, 1080
    )

    short_box = short_card.getbbox()
    long_box = long_card.getbbox()
    assert short_box is not None and long_box is not None
    assert short_box[2] - short_box[0] < 160
    assert long_box[2] - long_box[0] > short_box[2] - short_box[0]
