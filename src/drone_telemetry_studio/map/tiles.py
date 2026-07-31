from __future__ import annotations

import math
from io import BytesIO

from PIL import Image

from drone_telemetry_studio.map.cache import TileCache
from drone_telemetry_studio.map.geometry import GeoBounds, mercator_world_pixel


class RasterTileProvider:
    """Csak az egyetlen aktuális fix nézet csempéit kéri le; nincs előtöltés."""

    def __init__(self, cache: TileCache, url_template: str) -> None:
        self.cache = cache
        self.url_template = url_template

    def _zoom_for(self, bounds: GeoBounds, width: int, height: int) -> int:
        for zoom in range(18, 0, -1):
            left, bottom = mercator_world_pixel(bounds.min_lat, bounds.min_lon, zoom)
            right, top = mercator_world_pixel(bounds.max_lat, bounds.max_lon, zoom)
            if abs(right - left) <= width and abs(bottom - top) <= height:
                return zoom
        return 1

    def render(self, bounds: GeoBounds, width: int, height: int, *, allow_network: bool) -> Image.Image | None:
        zoom = self._zoom_for(bounds, width, height)
        left, bottom = mercator_world_pixel(bounds.min_lat, bounds.min_lon, zoom)
        right, top = mercator_world_pixel(bounds.max_lat, bounds.max_lon, zoom)
        view_width, view_height = max(right - left, 1), max(bottom - top, 1)
        scale = min(width / view_width, height / view_height)
        center_x, center_y = (left + right) / 2, (top + bottom) / 2
        canvas_left = center_x - width / scale / 2
        canvas_top = center_y - height / scale / 2
        tile_min_x, tile_max_x = math.floor(canvas_left / 256), math.floor((canvas_left + width / scale) / 256)
        tile_min_y, tile_max_y = math.floor(canvas_top / 256), math.floor((canvas_top + height / scale) / 256)
        mosaic = Image.new("RGB", ((tile_max_x - tile_min_x + 1) * 256, (tile_max_y - tile_min_y + 1) * 256))
        found = False
        limit = 2**zoom
        for tile_y in range(tile_min_y, tile_max_y + 1):
            if tile_y < 0 or tile_y >= limit:
                continue
            for tile_x in range(tile_min_x, tile_max_x + 1):
                wrapped_x = tile_x % limit
                url = self.url_template.format(z=zoom, x=wrapped_x, y=tile_y)
                path = self.cache.get(url, allow_network=allow_network)
                if not path:
                    continue
                try:
                    with Image.open(path) as tile:
                        mosaic.paste(tile.convert("RGB"), ((tile_x - tile_min_x) * 256, (tile_y - tile_min_y) * 256))
                    found = True
                except OSError:
                    continue
        if not found:
            return None
        crop_left = (canvas_left - tile_min_x * 256) * scale
        crop_top = (canvas_top - tile_min_y * 256) * scale
        resized = mosaic.resize((round(mosaic.width * scale), round(mosaic.height * scale)), Image.Resampling.LANCZOS)
        return resized.crop((round(crop_left), round(crop_top), round(crop_left + width), round(crop_top + height))).convert("RGBA")

