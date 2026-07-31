from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from drone_telemetry_studio.domain.overlay import Corner, OverlayConfig
from drone_telemetry_studio.domain.telemetry import TelemetrySample
from drone_telemetry_studio.map.renderer import StaticMapRenderer
from drone_telemetry_studio.telemetry.geo import hungarian_compass


def _font(size: int, bold: bool = False):
    names = (
        "/System/Library/Fonts/SFNSDisplay-Bold.otf" if bold else "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, max(8, size))
    return ImageFont.load_default()


def _number(value: float | None, digits: int = 1) -> str:
    return "–" if value is None else f"{value:.{digits}f}".replace(".", ",")


class HudRenderer:
    """A teljes videótól független, átlátszó HUD-képet készít."""

    def __init__(self, map_renderer: StaticMapRenderer | None = None) -> None:
        self.map_renderer = map_renderer or StaticMapRenderer()

    def render(
        self,
        sample: TelemetrySample | None,
        all_samples: list[TelemetrySample],
        config: OverlayConfig,
        width: int,
        height: int,
        *,
        allow_tile_network: bool = False,
    ) -> Image.Image:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        if sample is None:
            return image
        draw = ImageDraw.Draw(image, "RGBA")
        scale = min(width / 1920, height / 1080)
        margin = max(10, round(30 * scale))
        radius = max(6, round(12 * scale))
        label_font = _font(round(15 * scale))
        value_font = _font(round(34 * scale), bold=True)
        small_font = _font(round(20 * scale), bold=True)
        panel_fill = (7, 13, 20, round(190 * config.global_opacity))
        panel_gap = max(3, round(5 * scale))
        panel_padding_x = max(6, round(10 * scale))
        panel_padding_y = max(4, round(7 * scale))
        text_gap = max(1, round(2 * scale))

        y = margin
        if config.show_speed:
            speed = _number(sample.calculated_speed_kmh)
            y = self._panel(draw, margin, y, radius, panel_fill, "SEBESSÉG", f"{speed} km/h", label_font, value_font, panel_padding_x, panel_padding_y, text_gap)
        if config.show_altitude:
            y = self._panel(draw, margin, y + panel_gap, radius, panel_fill, "MAGASSÁG", f"{_number(sample.relative_altitude_m)} m", label_font, small_font, panel_padding_x, panel_padding_y, text_gap)
        if config.show_heading:
            heading = sample.calculated_heading_deg
            text = "–" if heading is None else f"{heading:03.0f}° {hungarian_compass(heading)}"
            y = self._panel(draw, margin, y + panel_gap, radius, panel_fill, "IRÁNY", text, label_font, small_font, panel_padding_x, panel_padding_y, text_gap)
        if config.show_vertical_speed:
            y = self._panel(draw, margin, y + panel_gap, radius, panel_fill, "FÜGGŐLEGES", f"{_number(sample.calculated_vertical_speed_mps)} m/s", label_font, small_font, panel_padding_x, panel_padding_y, text_gap)
        if config.show_distance:
            y = self._panel(draw, margin, y + panel_gap, radius, panel_fill, "TÁVOLSÁG", f"{_number(sample.cumulative_distance_m, 0)} m", label_font, small_font, panel_padding_x, panel_padding_y, text_gap)

        bottom_lines = []
        if config.show_gps and sample.latitude is not None and sample.longitude is not None and config.gps_decimals > 0:
            bottom_lines.append(f"{sample.latitude:.{config.gps_decimals}f}, {sample.longitude:.{config.gps_decimals}f}")
        if sample.recorded_at:
            parts = []
            if config.show_date:
                parts.append(sample.recorded_at.strftime("%Y. %m. %d."))
            if config.show_time:
                parts.append(sample.recorded_at.strftime("%H:%M:%S"))
            if parts:
                bottom_lines.append(" ".join(parts))
        if bottom_lines:
            padding_x = max(6, round(10 * scale))
            padding_y = max(5, round(8 * scale))
            line_gap = max(1, round(3 * scale))
            line_boxes = [draw.textbbox((0, 0), line, font=label_font, anchor="lt") for line in bottom_lines]
            line_widths = [box[2] - box[0] for box in line_boxes]
            line_heights = [box[3] - box[1] for box in line_boxes]
            box_width = max(line_widths) + padding_x * 2
            box_height = sum(line_heights) + line_gap * (len(bottom_lines) - 1) + padding_y * 2
            top = height - margin - box_height
            draw.rounded_rectangle((margin, top, margin + box_width, height - margin), radius=radius, fill=panel_fill)
            line_y = top + padding_y
            for line, line_height in zip(bottom_lines, line_heights, strict=True):
                draw.text((margin + padding_x, line_y), line, fill=(255, 255, 255, 245), font=label_font, anchor="lt")
                line_y += line_height + line_gap

        if config.map.visible:
            map_width = max(140, round(width * config.map.width_ratio))
            map_height = max(100, round(height * config.map.height_ratio))
            map_image = self.map_renderer.render(
                all_samples, sample.start_time_seconds, config.map, map_width, map_height,
                allow_tile_network=allow_tile_network,
            )
            map_margin = max(8, round(width * config.map.margin_ratio))
            positions = {
                Corner.TOP_LEFT: (map_margin, map_margin),
                Corner.TOP_RIGHT: (width - map_margin - map_width, map_margin),
                Corner.BOTTOM_LEFT: (map_margin, height - map_margin - map_height),
                Corner.BOTTOM_RIGHT: (width - map_margin - map_width, height - map_margin - map_height),
            }
            image.alpha_composite(map_image, positions[config.map.position])
        return image

    @staticmethod
    def _panel(
        draw,
        x,
        y,
        radius,
        fill,
        label,
        value,
        label_font,
        value_font,
        padding_x,
        padding_y,
        text_gap,
    ) -> int:
        label_box = draw.textbbox((0, 0), label, font=label_font, anchor="lt")
        value_box = draw.textbbox((0, 0), value, font=value_font, anchor="lt")
        label_width, label_height = label_box[2] - label_box[0], label_box[3] - label_box[1]
        value_width, value_height = value_box[2] - value_box[0], value_box[3] - value_box[1]
        width = max(label_width, value_width) + padding_x * 2
        height = label_height + value_height + padding_y * 2 + text_gap
        draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=fill)
        draw.text((x + padding_x, y + padding_y), label, fill=(154, 174, 192, 240), font=label_font, anchor="lt")
        draw.text((x + padding_x, y + padding_y + label_height + text_gap), value, fill=(255, 255, 255, 255), font=value_font, anchor="lt")
        return y + height
