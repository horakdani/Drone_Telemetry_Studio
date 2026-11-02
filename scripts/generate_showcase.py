"""Builds the README/website showcase media from a synthetic flight.

Writes a DJI-style SRT for a ~2.4 km flight along the Danube in Budapest, renders a
stylised background clip with FFmpeg, exports it through the real ExportPipeline
(with OpenStreetMap tiles) and produces a looping GIF/MP4 plus a still frame.

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


def write_srt(path: Path) -> None:
    curve = _catmull_rom(WAYPOINTS, 200)
    cumulative = [0.0]
    for a, b in zip(curve, curve[1:]):
        cumulative.append(cumulative[-1] + _metres(a, b))
    total = cumulative[-1]

    def progress(t: float) -> float:
        # Smooth take-off and arrival, steady cruise in between.
        u = t / DURATION_S
        return u * u * (3 - 2 * u) * 0.35 + u * 0.65

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
        lat, lon = position(progress(t) * total)
        rel_alt = 35 + 85 * (1 - math.cos(math.pi * min(1.0, t / (DURATION_S * 0.7)))) / 2
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


def write_background(ffmpeg: str, path: Path) -> None:
    """A still dusk-sky gradient with a vignette; static so the GIF stays small."""
    still = path.with_suffix(".png")
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
            "gradients=s=1920x1080:n=4:type=linear:speed=0:c0=0x0b1a2e:c1=0x23466b:"
            "c2=0xb8643e:c3=0xf0b26a:x0=960:y0=0:x1=960:y1=1080",
            "-vf", "vignette=PI/5", "-frames:v", "1", str(still),
        ],
        check=True,
        timeout=60,
    )
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", "30", "-i", str(still), "-t", f"{DURATION_S}",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "18",
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        timeout=900,
    )


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
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(exported),
            "-vf", f"setpts=PTS/{speedup},fps=15,scale=960:-2:flags=lanczos,split[a][b];"
                   "[a]palettegen=max_colors=256:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
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
