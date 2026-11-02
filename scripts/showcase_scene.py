"""Procedural dusk "drone footage" for the showcase: a city on a river seen in flight.

Nothing here comes from real imagery. A top-down texture (blocks, lit streets, a river
with bridges) is drawn once, then every frame projects it onto a ground plane under a
dusk sky, so the camera visibly flies forward and climbs with the telemetry.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

TEXTURE = 4096  # square, tileable along the flight direction (y)
METRES_PER_PIXEL = 0.35


def _river_x(y: float) -> float:
    return TEXTURE / 2 + 260 * math.sin(2 * math.pi * y / TEXTURE) + 90 * math.sin(6 * math.pi * y / TEXTURE)


def build_texture(seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    base = Image.new("RGB", (TEXTURE, TEXTURE), (24, 27, 34))
    lights = Image.new("RGB", (TEXTURE, TEXTURE), (0, 0, 0))
    draw, glow = ImageDraw.Draw(base), ImageDraw.Draw(lights)
    river_half = 330

    # City blocks with buildings, a few parks and lit windows.
    block, street = 230, 34
    for by in range(0, TEXTURE, block):
        for bx in range(0, TEXTURE, block):
            x0, y0 = bx + street // 2, by + street // 2
            x1, y1 = bx + block - street // 2, by + block - street // 2
            if abs((x0 + x1) / 2 - _river_x((y0 + y1) / 2)) < river_half + block * 0.55:
                continue
            if rng.random() < 0.09:
                draw.rectangle((x0, y0, x1, y1), fill=(26, 40, 30))
                for _ in range(40):
                    tx, ty = rng.uniform(x0, x1), rng.uniform(y0, y1)
                    r = rng.uniform(5, 13)
                    draw.ellipse((tx - r, ty - r, tx + r, ty + r), fill=(20, 48, 32))
                continue
            draw.rectangle((x0, y0, x1, y1), fill=(34, 36, 44))
            for _ in range(rng.randint(3, 7)):
                w, h = rng.uniform(40, 110), rng.uniform(40, 110)
                rx, ry = rng.uniform(x0, x1 - w), rng.uniform(y0, y1 - h)
                shade = rng.randint(40, 72)
                draw.rectangle((rx, ry, rx + w, ry + h), fill=(shade, shade - 2, shade + 6))
                for _ in range(rng.randint(2, 12)):
                    wx, wy = rng.uniform(rx, rx + w), rng.uniform(ry, ry + h)
                    color = rng.choice(((255, 196, 120), (255, 226, 170), (180, 210, 255)))
                    glow.rectangle((wx, wy, wx + 3, wy + 3), fill=color)

    # Street lights along the grid.
    for coord in range(0, TEXTURE, block):
        for t in range(0, TEXTURE, 46):
            for x, y in ((coord, t), (t, coord)):
                if abs(x - _river_x(y)) > river_half + 70:
                    glow.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 170, 80))

    # River with a dusk reflection, embankment roads and lit bridges.
    for y in range(TEXTURE):
        cx = _river_x(y)
        draw.line((cx - river_half, y, cx + river_half, y), fill=(18, 34, 58))
        draw.line((cx - river_half - 40, y, cx - river_half, y), fill=(52, 50, 54))
        draw.line((cx + river_half, y, cx + river_half + 40, y), fill=(52, 50, 54))
        if y % 22 == 0:
            for side in (-1, 1):
                ex = cx + side * (river_half + 20)
                glow.ellipse((ex - 4, y - 4, ex + 4, y + 4), fill=(255, 190, 110))
    for _ in range(900):
        y = rng.uniform(0, TEXTURE)
        cx = _river_x(y) + rng.uniform(-river_half * 0.9, river_half * 0.9)
        length = rng.uniform(20, 90)
        glow.line((cx - length / 2, y, cx + length / 2, y), fill=(120, 80, 50), width=2)
    for k in range(3):
        y = (k + 0.5) * TEXTURE / 3
        cx = _river_x(y)
        x0, x1 = cx - river_half - 60, cx + river_half + 60
        draw.rectangle((x0, y - 22, x1, y + 22), fill=(58, 58, 64))
        for x in range(int(x0), int(x1), 18):
            for edge in (-22, 22):
                glow.ellipse((x - 4, y + edge - 4, x + 4, y + edge + 4), fill=(255, 236, 200))

    halo = lights.filter(ImageFilter.GaussianBlur(9))
    texture = ImageChops.add(ImageChops.add(base, halo), lights)
    return texture


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    rows = [row[:] + [value] for row, value in zip(matrix, vector)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(n):
            if r != col:
                factor = rows[r][col] / rows[col][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][n] / rows[i][i] for i in range(n)]


def _perspective(output: list[tuple[float, float]], source: list[tuple[float, float]]) -> list[float]:
    """Coefficients mapping output pixels to source pixels for Image.transform."""
    matrix, vector = [], []
    for (x, y), (u, v) in zip(output, source):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); vector.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y]); vector.append(v)
    return _solve(matrix, vector)


class AerialScene:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        texture = build_texture()
        # Stack two copies so any forward offset stays inside the image.
        self.texture = Image.new("RGB", (TEXTURE, TEXTURE * 2))
        self.texture.paste(texture, (0, 0))
        self.texture.paste(texture, (0, TEXTURE))
        self.horizon = round(height * 0.34)
        self.sky = self._sky()
        self.fog = self._fog()

    def _sky(self) -> Image.Image:
        w, h = self.width, self.horizon + 40
        sky = Image.new("RGB", (w, h))
        stops = ((0.0, (10, 20, 40)), (0.45, (36, 64, 100)), (0.8, (196, 104, 62)), (1.0, (246, 178, 104)))
        draw = ImageDraw.Draw(sky)
        for y in range(h):
            f = y / (h - 1)
            for (f0, c0), (f1, c1) in zip(stops, stops[1:]):
                if f0 <= f <= f1:
                    k = (f - f0) / (f1 - f0)
                    draw.line((0, y, w, y), fill=tuple(round(a + (b - a) * k) for a, b in zip(c0, c1)))
                    break
        sun = Image.new("L", (w, h), 0)
        sx, sy, r = w * 0.68, h - 10, h * 0.55
        ImageDraw.Draw(sun).ellipse((sx - r, sy - r, sx + r, sy + r), fill=150)
        sun = sun.filter(ImageFilter.GaussianBlur(h * 0.25))
        return Image.composite(Image.new("RGB", (w, h), (255, 200, 130)), sky, sun)

    def _fog(self) -> Image.Image:
        ground = self.height - self.horizon
        mask = Image.new("L", (1, ground))
        for y in range(ground):
            mask.putpixel((0, y), round(255 * (1 - y / ground) ** 3.2))
        return mask.resize((self.width, ground))

    def render(self, distance_m: float, altitude_m: float, sway: float = 0.0) -> Image.Image:
        w, h, hz = self.width, self.height, self.horizon
        ground_h = h - hz
        forward = (distance_m / METRES_PER_PIXEL) % TEXTURE
        near_y = TEXTURE * 2 - 200 - forward
        far_y = near_y - 3300
        near_w = 520 + altitude_m * 9
        far_w = 3900
        cx = _river_x(near_y) * 0.35 + TEXTURE / 2 * 0.65 + sway * 40
        coefficients = _perspective(
            [(0, 0), (w, 0), (0, ground_h), (w, ground_h)],
            [(cx - far_w / 2, far_y), (cx + far_w / 2, far_y), (cx - near_w / 2, near_y), (cx + near_w / 2, near_y)],
        )
        ground = self.texture.transform(
            (w, ground_h), Image.Transform.PERSPECTIVE, coefficients,
            Image.Resampling.BILINEAR, fillcolor=(24, 27, 34),
        )
        haze = Image.new("RGB", (w, ground_h), (214, 150, 104))
        ground = Image.composite(haze, ground, self.fog)
        frame = Image.new("RGB", (w, h))
        frame.paste(self.sky.crop((0, 0, w, hz)), (0, 0))
        frame.paste(ground, (0, hz))
        if sway:
            frame = frame.rotate(sway * 1.2, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(10, 20, 40))
            frame = frame.resize((round(w * 1.03), round(h * 1.03))).crop(
                (round(w * 0.015), round(h * 0.015), round(w * 0.015) + w, round(h * 0.015) + h)
            )
        return frame
