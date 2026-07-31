from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from drone_telemetry_studio.domain.overlay import MapConfig, MapStyle
from drone_telemetry_studio.domain.telemetry import TelemetrySample, ValidityFlag
from drone_telemetry_studio.map.cache import TileCache
from drone_telemetry_studio.map.geometry import GeoBounds, bounds_for_points, project_to_panel
from drone_telemetry_studio.map.tiles import RasterTileProvider


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=max(8, size))
    return ImageFont.load_default()


_PALETTES = {
    MapStyle.DARK: ((15, 23, 35, 255), (38, 54, 72, 255), (85, 104, 126, 180), (36, 220, 178, 255)),
    MapStyle.LIGHT: ((230, 234, 237, 255), (206, 214, 220, 255), (90, 105, 115, 160), (0, 118, 132, 255)),
    MapStyle.CINEMATIC: ((30, 27, 26, 255), (67, 57, 49, 255), (145, 126, 103, 150), (240, 174, 75, 255)),
}


@dataclass(slots=True)
class _PreparedMap:
    key: tuple
    base: Image.Image
    usable: list[TelemetrySample]
    sample_times: list[float]
    route_times: list[float]
    route_points: list[tuple[float, float]]
    bounds: GeoBounds | None
    done_color: tuple[int, int, int, int]
    line_width: int


class StaticMapRenderer:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache = TileCache(cache_dir or Path.home() / "Library/Caches/DroneTelemetryStudio/tiles")
        self._prepared: _PreparedMap | None = None

    def render(
        self,
        samples: list[TelemetrySample],
        current_time: float,
        config: MapConfig,
        width: int,
        height: int,
        *,
        allow_tile_network: bool = False,
    ) -> Image.Image:
        key = (
            id(samples), len(samples), width, height, config.style, config.padding_ratio,
            config.route_width, config.show_full_route, config.show_start, config.show_attribution,
            config.use_raster_tiles, config.tile_url, config.tile_attribution,
            config.hide_start_seconds, config.hide_end_seconds, allow_tile_network,
        )
        if self._prepared is None or self._prepared.key != key:
            self._prepared = self._prepare(
                key, samples, config, width, height, allow_tile_network=allow_tile_network
            )
        prepared = self._prepared
        panel = prepared.base.copy()
        if not prepared.usable or prepared.bounds is None:
            return self._rounded(panel, config)

        draw = ImageDraw.Draw(panel, "RGBA")
        route_index = min(
            max(0, bisect_right(prepared.route_times, current_time)), len(prepared.route_points)
        )
        if route_index >= 2:
            draw.line(
                prepared.route_points[:route_index],
                fill=prepared.done_color,
                width=prepared.line_width + max(1, prepared.line_width // 2),
                joint="curve",
            )
        current_index = min(
            max(0, bisect_right(prepared.sample_times, current_time) - 1), len(prepared.usable) - 1
        )
        current = prepared.usable[current_index]
        if config.show_drone:
            x, y = project_to_panel(
                current.latitude, current.longitude, prepared.bounds, width, height  # type: ignore[arg-type]
            )
            marker_size = max(6, width // 40)
            self._draw_arrow(
                draw, x, y, current.calculated_heading_deg or 0.0,
                marker_size * 1.6, prepared.done_color,
            )
        return self._rounded(panel, config)

    def _prepare(
        self,
        key: tuple,
        samples: list[TelemetrySample],
        config: MapConfig,
        width: int,
        height: int,
        *,
        allow_tile_network: bool,
    ) -> _PreparedMap:
        usable = [
            sample
            for sample in samples
            if sample.has_valid_gps
            and not sample.validity_flags & ValidityFlag.GPS_OUTLIER
            and sample.latitude is not None
            and sample.longitude is not None
        ]
        if config.hide_start_seconds:
            usable = [s for s in usable if s.start_time_seconds >= config.hide_start_seconds]
        if config.hide_end_seconds and usable:
            last_time = usable[-1].start_time_seconds
            usable = [s for s in usable if s.start_time_seconds <= last_time - config.hide_end_seconds]
        background, grid, future_color, done_color = _PALETTES[config.style]
        panel = Image.new("RGBA", (max(1, width), max(1, height)), background)
        draw = ImageDraw.Draw(panel, "RGBA")
        if not usable:
            draw.text((width / 2, height / 2), "Nincs érvényes GPS-adat", fill=(255, 255, 255, 210), font=_font(width // 24), anchor="mm")
            return _PreparedMap(key, panel, [], [], [], [], None, done_color, 2)

        points = [(sample.latitude, sample.longitude) for sample in usable]  # type: ignore[misc]
        bounds = bounds_for_points(points, config.padding_ratio)
        if config.use_raster_tiles:
            tiles = RasterTileProvider(self.cache, config.tile_url).render(
                bounds, width, height, allow_network=allow_tile_network
            )
            if tiles is not None:
                panel = tiles
                draw = ImageDraw.Draw(panel, "RGBA")
        else:
            for fraction in (0.25, 0.5, 0.75):
                draw.line((width * fraction, 0, width * fraction, height), fill=grid, width=1)
                draw.line((0, height * fraction, width, height * fraction), fill=grid, width=1)

        # A fix háttérhez legfeljebb néhány panelpixelnyi pont kell; a teljes
        # pontosságú telemetria változatlanul az adatmodellben marad.
        maximum_route_points = max(500, width * 3)
        step = max(1, math.ceil(len(usable) / maximum_route_points))
        route_samples = usable[::step]
        if route_samples[-1] is not usable[-1]:
            route_samples.append(usable[-1])
        projected = [
            project_to_panel(sample.latitude, sample.longitude, bounds, width, height)  # type: ignore[arg-type]
            for sample in route_samples
        ]
        line_width = max(2, round(config.route_width * width / 500))
        if config.show_full_route and len(projected) >= 2:
            draw.line(projected, fill=future_color, width=line_width, joint="curve")

        marker_size = max(6, width // 40)
        if config.show_start:
            start_x, start_y = project_to_panel(*points[0], bounds, width, height)
            draw.ellipse(
                (start_x - marker_size, start_y - marker_size, start_x + marker_size, start_y + marker_size),
                fill=(255, 255, 255, 255), outline=(20, 24, 28, 230), width=max(2, marker_size // 3),
            )
        draw.text((width - marker_size, marker_size), "É", fill=(255, 255, 255, 235), font=_font(max(11, width // 28)), anchor="ma", stroke_width=1, stroke_fill=(0, 0, 0, 180))
        draw.line((width - marker_size, marker_size * 1.4, width - marker_size, marker_size * 2.5), fill=(255, 255, 255, 230), width=2)
        if config.show_attribution:
            attribution = config.tile_attribution if config.use_raster_tiles else "Offline útvonal • helyi adatok"
            draw.text((width - 6, height - 5), attribution, fill=(255, 255, 255, 190), font=_font(max(8, width // 48)), anchor="rs", stroke_width=1, stroke_fill=(0, 0, 0, 150))
        return _PreparedMap(
            key,
            panel,
            usable,
            [sample.start_time_seconds for sample in usable],
            [sample.start_time_seconds for sample in route_samples],
            projected,
            bounds,
            done_color,
            line_width,
        )

    @staticmethod
    def _draw_arrow(draw: ImageDraw.ImageDraw, x: float, y: float, heading: float, size: float, color) -> None:
        import math

        points = []
        for angle_offset, radius in ((0, size), (145, size * 0.75), (180, size * 0.32), (215, size * 0.75)):
            angle = math.radians(heading + angle_offset - 90)
            points.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
        draw.polygon(points, fill=color, outline=(255, 255, 255, 245))

    @staticmethod
    def _rounded(panel: Image.Image, config: MapConfig) -> Image.Image:
        mask = Image.new("L", panel.size, 0)
        radius = max(1, round(min(panel.size) * config.corner_radius_ratio))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=radius, fill=config.opacity)
        panel.putalpha(mask)
        return panel
