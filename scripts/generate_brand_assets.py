"""Draws the logo and the GitHub social preview card into docs/images.

Run after scripts/generate_showcase.py, which produces hud-preview.png:

    PYTHONPATH=src .venv/bin/python scripts/generate_brand_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from drone_telemetry_studio.overlay.renderer import _font

ROOT = Path(__file__).parents[1]
IMAGES = ROOT / "docs/images"
BG = (7, 11, 16)
ACCENT = (55, 226, 196)
AMBER = (255, 181, 71)
TEXT = (230, 238, 245)
MUTED = (141, 162, 181)


def draw_mark(size: int) -> Image.Image:
    """Crosshair reticle with an amber centre, drawn at 4x and downsampled."""
    s = size * 4
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 4.5, fill=(13, 20, 28, 255))
    c, r, w = s / 2, s * 0.32, max(4, s // 22)
    draw.ellipse((c - r, c - r, c + r, c + r), outline=ACCENT, width=w)
    tick = s * 0.13
    for x0, y0, x1, y1 in (
        (c, c - r - tick * 0.4, c, c - r + tick),
        (c, c + r - tick, c, c + r + tick * 0.4),
        (c - r - tick * 0.4, c, c - r + tick, c),
        (c + r - tick, c, c + r + tick * 0.4, c),
    ):
        draw.line((x0, y0, x1, y1), fill=ACCENT, width=w)
    dot = s * 0.07
    draw.ellipse((c - dot, c - dot, c + dot, c + dot), fill=AMBER)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def social_preview(hud: Path) -> Image.Image:
    width, height = 1280, 640
    card = Image.new("RGB", (width, height), BG)
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-300, 470, 1500, 1000), fill=(*AMBER, 34))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    card.paste(glow, (0, 0), glow)

    card.paste(draw_mark(84), (64, 70), draw_mark(84))
    draw = ImageDraw.Draw(card, "RGBA")
    draw.text((64, 186), "Drone Telemetry", font=_font(60, bold=True), fill=TEXT)
    draw.text((64, 254), "Studio", font=_font(60, bold=True), fill=ACCENT)
    body = _font(27)
    for i, line in enumerate((
        "Burn DJI flight data and a live route",
        "map onto your drone videos.",
    )):
        draw.text((64, 368 + i * 38), line, font=body, fill=MUTED)
    chip_font = _font(21, bold=True)
    x = 64
    for chip in ("Free & open source", "macOS", "100% local"):
        w = draw.textlength(chip, font=chip_font) + 32
        draw.rounded_rectangle((x, 480, x + w, 522), radius=21, outline=(31, 45, 58), width=2, fill=(13, 20, 28))
        draw.text((x + 16, 501), chip, font=chip_font, fill=TEXT, anchor="lm")
        x += w + 12

    if hud.exists():
        shot = Image.open(hud).convert("RGB")
        shot_w = 570
        shot = shot.resize((shot_w, round(shot.height * shot_w / shot.width)), Image.Resampling.LANCZOS)
        left, top = width - shot_w - 56, (height - shot.height) // 2
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (left - 6, top + 18, left + shot_w + 6, top + shot.height + 30), radius=22, fill=(0, 0, 0, 200)
        )
        card.paste(shadow.filter(ImageFilter.GaussianBlur(24)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(24)))
        mask = Image.new("L", shot.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, shot.width - 1, shot.height - 1), radius=16, fill=255)
        card.paste(shot, (left, top), mask)
        ImageDraw.Draw(card).rounded_rectangle(
            (left, top, left + shot.width - 1, top + shot.height - 1), radius=16, outline=(31, 45, 58), width=2
        )
    return card


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    draw_mark(256).save(IMAGES / "logo.png")
    social_preview(IMAGES / "hud-preview.png").save(IMAGES / "social-preview.png", optimize=True)
    for name in ("logo.png", "social-preview.png"):
        print(IMAGES / name)


if __name__ == "__main__":
    main()
