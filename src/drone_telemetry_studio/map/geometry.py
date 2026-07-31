from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class GeoBounds:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


def mercator_world_pixel(lat: float, lon: float, zoom: int = 0) -> tuple[float, float]:
    """Web Mercator világpixel; a szélesség zoom 0-n 256 pixel."""
    lat = max(-85.05112878, min(85.05112878, lat))
    scale = 256.0 * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def bounds_for_points(points: Sequence[tuple[float, float]], padding_ratio: float = 0.1) -> GeoBounds:
    if not points:
        raise ValueError("Legalább egy GPS-pont szükséges a térképhatárhoz.")
    lats = [point[0] for point in points]
    lons = [point[1] for point in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    # Álló drónnál is értelmes, kb. néhány tíz méteres nézetet adunk.
    lat_span = max(max_lat - min_lat, 0.0002)
    lon_span = max(max_lon - min_lon, 0.0002)
    return GeoBounds(
        min_lat - lat_span * padding_ratio,
        min_lon - lon_span * padding_ratio,
        max_lat + lat_span * padding_ratio,
        max_lon + lon_span * padding_ratio,
    )


def project_to_panel(lat: float, lon: float, bounds: GeoBounds, width: int, height: int) -> tuple[float, float]:
    left_x, bottom_y = mercator_world_pixel(bounds.min_lat, bounds.min_lon)
    right_x, top_y = mercator_world_pixel(bounds.max_lat, bounds.max_lon)
    point_x, point_y = mercator_world_pixel(lat, lon)
    x_span = max(abs(right_x - left_x), 1e-12)
    y_span = max(abs(bottom_y - top_y), 1e-12)
    return (
        (point_x - left_x) / x_span * width,
        (point_y - top_y) / y_span * height,
    )


def _point_line_distance(point, start, end) -> float:
    if start == end:
        return math.dist(point, start)
    dx, dy = end[0] - start[0], end[1] - start[1]
    factor = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
    factor = max(0.0, min(1.0, factor))
    projection = (start[0] + factor * dx, start[1] + factor * dy)
    return math.dist(point, projection)


def simplify_polyline(points: Sequence[tuple[float, float]], tolerance: float = 1.0) -> list[tuple[float, float]]:
    """Iteratív Ramer–Douglas–Peucker egyszerűsítés panelpixelekben."""
    if len(points) <= 2:
        return list(points)
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        max_distance = 0.0
        max_index = None
        for index in range(start + 1, end):
            distance = _point_line_distance(points[index], points[start], points[end])
            if distance > max_distance:
                max_distance, max_index = distance, index
        if max_index is not None and max_distance > tolerance:
            keep.add(max_index)
            stack.extend(((start, max_index), (max_index, end)))
    return [points[index] for index in sorted(keep)]

