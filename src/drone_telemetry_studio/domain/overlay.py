from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Corner(StrEnum):
    TOP_LEFT = "Top left"
    TOP_RIGHT = "Top right"
    BOTTOM_LEFT = "Bottom left"
    BOTTOM_RIGHT = "Bottom right"


class MapStyle(StrEnum):
    DARK = "Dark"
    LIGHT = "Light"
    CINEMATIC = "Cinematic"


@dataclass(slots=True)
class MapConfig:
    visible: bool = True
    position: Corner = Corner.BOTTOM_RIGHT
    width_ratio: float = 0.24
    height_ratio: float = 0.25
    margin_ratio: float = 0.02
    opacity: int = 225
    corner_radius_ratio: float = 0.035
    padding_ratio: float = 0.10
    route_width: int = 4
    style: MapStyle = MapStyle.DARK
    show_full_route: bool = True
    show_start: bool = True
    show_drone: bool = True
    show_attribution: bool = True
    use_raster_tiles: bool = True
    tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    tile_attribution: str = "© OpenStreetMap contributors"
    hide_start_seconds: float = 0.0
    hide_end_seconds: float = 0.0


@dataclass(slots=True)
class OverlayConfig:
    show_speed: bool = True
    show_altitude: bool = True
    show_gps: bool = True
    show_date: bool = True
    show_time: bool = True
    show_heading: bool = True
    show_vertical_speed: bool = False
    show_distance: bool = False
    gps_decimals: int = 6
    global_opacity: float = 1.0
    time_offset_seconds: float = 0.0
    map: MapConfig = field(default_factory=MapConfig)


@dataclass(slots=True)
class ExportConfig:
    codec: str = "libx264"
    quality: str = "Balanced"
    keep_audio: bool = True
    overlay_fps: float = 10.0
    overlay_width: int = 960
    overlay_height: int = 540
