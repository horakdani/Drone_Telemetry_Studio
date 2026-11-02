import pytest
from PIL import Image

from drone_telemetry_studio.map.geometry import (
    bounds_for_points,
    mercator_world_pixel,
    project_to_panel,
    simplify_polyline,
)
from drone_telemetry_studio.map.tiles import RasterTileProvider


def test_bounds_and_projection() -> None:
    bounds = bounds_for_points([(47.0, 19.0), (47.1, 19.2)], padding_ratio=0)
    top_left = project_to_panel(47.1, 19.0, bounds, 1000, 500)
    bottom_right = project_to_panel(47.0, 19.2, bounds, 1000, 500)
    # In Web Mercator this route is ~1.4:1, narrower than the 2:1 panel, so it fills
    # the height and is centred horizontally.
    assert top_left[1] == pytest.approx(0, abs=1e-6)
    assert bottom_right[1] == pytest.approx(500)
    assert (top_left[0] + bottom_right[0]) / 2 == pytest.approx(500)
    assert 0 < top_left[0] < bottom_right[0] < 1000


def test_projection_keeps_aspect_ratio() -> None:
    # A tall, narrow route in a wide panel must not be stretched horizontally.
    a, b = (47.4989, 19.0442), (47.5176, 19.0515)
    bounds = bounds_for_points([a, b], padding_ratio=0)
    pa, pb = project_to_panel(*a, bounds, 400, 225), project_to_panel(*b, bounds, 400, 225)
    wa, wb = mercator_world_pixel(*a), mercator_world_pixel(*b)
    panel_ratio = abs(pb[0] - pa[0]) / abs(pb[1] - pa[1])
    world_ratio = abs(wb[0] - wa[0]) / abs(wb[1] - wa[1])
    assert panel_ratio == pytest.approx(world_ratio)
    assert (pa[0] + pb[0]) / 2 == pytest.approx(200)


def test_projection_matches_raster_tiles(tmp_path) -> None:
    """A route point must land on the same pixel as its location in the tile mosaic."""

    target = (47.5071, 19.0457)
    bounds = bounds_for_points([(47.4989, 19.0442), (47.5176, 19.0515)], padding_ratio=0.1)
    width, height = 400, 225

    class MarkerCache:
        """Serves blank tiles, with a single red pixel at the target location."""

        def get(self, url: str, *, allow_network: bool):
            z, x, y = (int(part) for part in url.split("/"))
            wx, wy = mercator_world_pixel(*target, z)
            tile = Image.new("RGB", (256, 256), (0, 0, 0))
            if int(wx // 256) == x and int(wy // 256) == y:
                tile.putpixel((int(wx % 256), int(wy % 256)), (255, 0, 0))
            path = tmp_path / f"{z}-{x}-{y}.png"
            tile.save(path)
            return path

    image = RasterTileProvider(MarkerCache(), "{z}/{x}/{y}").render(bounds, width, height, allow_network=False)
    assert image is not None
    red = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if image.getpixel((x, y))[0] > 40
    ]
    assert red, "marker pixel missing from the mosaic"
    marker_x = sum(p[0] for p in red) / len(red)
    marker_y = sum(p[1] for p in red) / len(red)
    projected = project_to_panel(*target, bounds, width, height)
    assert projected[0] == pytest.approx(marker_x, abs=2)
    assert projected[1] == pytest.approx(marker_y, abs=2)


def test_simplification_preserves_endpoints() -> None:
    points = [(0, 0), (1, 0.01), (2, -0.01), (3, 0)]
    assert simplify_polyline(points, 0.1) == [(0, 0), (3, 0)]
