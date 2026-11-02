"""Builds the README/website showcase media from a synthetic flight.

Writes a DJI-style SRT for a ~2.4 km flight along the Danube in Budapest, renders a
procedural dusk flyover clip that moves and climbs with that telemetry
(scripts/showcase_scene.py), exports it through the real ExportPipeline (with
OpenStreetMap tiles) and produces a looping GIF/MP4 plus a still frame.

    PYTHONPATH=src .venv/bin/python scripts/generate_showcase.py

Pass --video/--srt to build the showcase from a real DJI flight instead.
"""

from __future__ import annotations

import argparse
import math
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from drone_telemetry_studio.domain.overlay import ExportConfig, OverlayConfig
from drone_telemetry_studio.map.renderer import StaticMapRenderer
from drone_telemetry_studio.media.export_pipeline import ExportPipeline
from drone_telemetry_studio.media.ffmpeg import discover_media_tools
from drone_telemetry_studio.media.ffprobe import probe_video
from drone_telemetry_studio.overlay.renderer import HudRenderer
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion
from drone_telemetry_studio.telemetry.interpolation import sample_at

ROOT = Path(__file__).parents[1]
# Chain Bridge → Parliament → Margaret Bridge → over Margaret Island.
WAYPOINTS = [
    (47.49890, 19.04330),
    (47.50300, 19.04180),
    (47.50720, 19.04230),
    (47.51130, 19.04480),
    (47.51450, 19.04740),
    (47.51760, 19.05050),
]
DURATION_S = 150.0
SAMPLE_HZ = 10


def _catmull_rom(points: list[tuple[float, float]], steps: int) -> list[tuple[float, float]]:
    padded = [points[0], *points, points[-1]]
    curve = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for s in range(steps):
            t = s / steps
            curve.append(tuple(
                0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t**2
                       + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t**3)
                for k in range(2)
            ))
    curve.append(points[-1])
    return curve


def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((b[0] - a[0]) * 111_320, (b[1] - a[1]) * 111_320 * math.cos(lat))


def _progress(t: float) -> float:
    """Fraction of the route covered at time t: smooth take-off, steady cruise."""
    u = t / DURATION_S
    return u * u * (3 - 2 * u) * 0.35 + u * 0.65


def _altitude(t: float) -> float:
    return 35 + 85 * (1 - math.cos(math.pi * min(1.0, t / (DURATION_S * 0.7)))) / 2


def _route() -> tuple[list[tuple[float, float]], list[float]]:
    curve = _catmull_rom(WAYPOINTS, 200)
    cumulative = [0.0]
    for a, b in zip(curve, curve[1:]):
        cumulative.append(cumulative[-1] + _metres(a, b))
    return curve, cumulative


def write_srt(path: Path) -> None:
    curve, cumulative = _route()
    total = cumulative[-1]

    def position(d: float) -> tuple[float, float]:
        for i in range(1, len(cumulative)):
            if cumulative[i] >= d:
                f = (d - cumulative[i - 1]) / max(1e-9, cumulative[i] - cumulative[i - 1])
                a, b = curve[i - 1], curve[i]
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        return curve[-1]

    start = datetime(2026, 7, 29, 19, 42, 5)
    blocks = []
    n = int(DURATION_S * SAMPLE_HZ)
    for i in range(n + 1):
        t = i / SAMPLE_HZ
        lat, lon = position(_progress(t) * total)
        rel_alt = _altitude(t)
        stamp = start + timedelta(seconds=t)
        end = t + 1 / SAMPLE_HZ
        blocks.append(
            f"{i + 1}\n"
            f"{_tc(t)} --> {_tc(end)}\n"
            f'<font size="28">FrameCnt: {i * 3 + 1}, DiffTime: 100ms\n'
            f"{stamp:%Y-%m-%d %H:%M:%S}.{stamp.microsecond // 1000:03d}\n"
            f"[iso: 100] [shutter: 1/500.0] [fnum: 1.7] [ev: 0] [color_md: default] [focal_len: 24.00] "
            f"[latitude: {lat:.6f}] [longitude: {lon:.6f}] [rel_alt: {rel_alt:.3f} abs_alt: {rel_alt + 105:.3f}] "
            f"[ct: 5600] </font>\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")


def _tc(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_background(ffmpeg: str, path: Path, fps: int = 30) -> None:
    """Renders the procedural flyover, moving and climbing with the telemetry."""
    from showcase_scene import AerialScene

    width, height = 1920, 1080
    scene = AerialScene(width, height)
    total = _route()[1][-1]
    process = subprocess.Popen(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
            "-framerate", str(fps), "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(path),
        ],
        stdin=subprocess.PIPE,
    )
    assert process.stdin is not None
    frames = round(DURATION_S * fps)
    for index in range(frames):
        t = index / fps
        sway = 0.6 * math.sin(t / 6.0) + 0.25 * math.sin(t / 2.3)
        process.stdin.write(scene.render(_progress(t) * total, _altitude(t), sway).tobytes())
        if index % (fps * 15) == 0:
            print(f"background {t:5.0f}/{DURATION_S:.0f} s", flush=True)
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("FFmpeg failed to encode the showcase background")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--video", type=Path, help="Use a real DJI MP4 instead of the synthetic clip")
    parser.add_argument("--srt", type=Path, help="SRT that belongs to --video")
    args = parser.parse_args()

    out = ROOT / "artifacts/showcase"
    out.mkdir(parents=True, exist_ok=True)
    images = ROOT / "docs/images"
    images.mkdir(parents=True, exist_ok=True)
    ffmpeg = discover_media_tools().ffmpeg

    srt = args.srt or out / "showcase.SRT"
    video = args.video or out / "showcase_source.mp4"
    if not args.srt:
        write_srt(srt)
    if not args.video and not video.exists():
        write_background(ffmpeg, video)

    samples = DjiSrtParser().parse(srt).samples
    enrich_motion(samples)
    metadata = probe_video(video)
    config = OverlayConfig(show_vertical_speed=True, show_distance=True)
    config.map.width_ratio, config.map.height_ratio = 0.30, 0.34
    map_renderer = StaticMapRenderer(out / "tiles")
    hud = HudRenderer(map_renderer)

    # Warm the tile cache once for the fixed map view; the export reads from cache.
    still_t = metadata.duration_seconds * 0.62
    hud.render(sample_at(samples, still_t), samples, config, 1920, 1080, allow_tile_network=True)

    exported = out / "showcase_export.mp4"
    exported.unlink(missing_ok=True)
    ExportPipeline(renderer=hud).export(
        video, exported, metadata, samples, config,
        ExportConfig(codec="libx264", quality="Balanced", overlay_fps=10, overlay_width=1920, overlay_height=1080),
    )

    speedup = 8
    subprocess.run(
        [
            # The whole frame moves, so the GIF is a ~12 s excerpt kept under ~8 MB for the README.
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{metadata.duration_seconds * 0.1:.1f}", "-t", f"{metadata.duration_seconds * 0.67:.1f}",
            "-i", str(exported),
            "-vf", f"setpts=PTS/{speedup},fps=10,scale=720:-2:flags=lanczos,split[a][b];"
                   "[a]palettegen=max_colors=96:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
            "-loop", "0", str(images / "demo.gif"),
        ],
        check=True,
        timeout=900,
    )
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(exported), "-an",
            "-vf", f"setpts=PTS/{speedup},fps=30,scale=1280:-2:flags=lanczos",
            "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(images / "demo.mp4"),
        ],
        check=True,
        timeout=900,
    )
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{still_t:.2f}", "-i", str(exported),
            "-frames:v", "1", "-vf", "scale=1600:-2:flags=lanczos", str(images / "hud-preview.png"),
        ],
        check=True,
        timeout=120,
    )
    for name in ("demo.gif", "demo.mp4", "hud-preview.png"):
        print(images / name)


if __name__ == "__main__":
    main()
