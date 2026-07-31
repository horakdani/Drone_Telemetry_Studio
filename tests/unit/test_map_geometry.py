import pytest

from drone_telemetry_studio.map.geometry import bounds_for_points, project_to_panel, simplify_polyline


def test_bounds_and_projection() -> None:
    bounds = bounds_for_points([(47.0, 19.0), (47.1, 19.2)], padding_ratio=0)
    top_left = project_to_panel(47.1, 19.0, bounds, 1000, 500)
    bottom_right = project_to_panel(47.0, 19.2, bounds, 1000, 500)
    assert top_left == pytest.approx((0, 0))
    assert bottom_right == pytest.approx((1000, 500))


def test_simplification_preserves_endpoints() -> None:
    points = [(0, 0), (1, 0.01), (2, -0.01), (3, 0)]
    assert simplify_polyline(points, 0.1) == [(0, 0), (3, 0)]

