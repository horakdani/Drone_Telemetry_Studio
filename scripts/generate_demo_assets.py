from __future__ import annotations

import subprocess
from pathlib import Path

from drone_telemetry_studio.domain.overlay import ExportConfig, OverlayConfig
from drone_telemetry_studio.media.export_pipeline import ExportPipeline
from drone_telemetry_studio.media.ffmpeg import discover_media_tools, extract_preview_frame
from drone_telemetry_studio.media.ffprobe import probe_video
from drone_telemetry_studio.overlay.renderer import HudRenderer
from drone_telemetry_studio.parsers.dji_srt_parser import DjiSrtParser
from drone_telemetry_studio.telemetry.geo import enrich_motion
from drone_telemetry_studio.telemetry.interpolation import sample_at


def main() -> None:
    root = Path(__file__).parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    source = artifacts / "demo_source.mp4"
    output = artifacts / "demo_telemetry.mp4"
    preview = artifacts / "demo_preview.png"
    tools = discover_media_tools()

    if not source.exists():
        subprocess.run(
            [
                tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=0x162432:s=1280x720:r=30",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                "-t", "3.05", "-vf", "drawgrid=w=80:h=80:t=1:c=0x35516a",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", str(source),
            ],
            check=True,
            timeout=90,
        )

    samples = DjiSrtParser().parse(root / "samples/DJI_DEMO.SRT").samples
    enrich_motion(samples)
    metadata = probe_video(source)
    frame = extract_preview_frame(source, 1.5)
    current = sample_at(samples, 1.5)
    hud = HudRenderer().render(current, samples, OverlayConfig(), frame.width, frame.height)
    composite = frame.convert("RGBA")
    composite.alpha_composite(hud)
    composite.convert("RGB").save(preview, quality=95)

    if output.exists():
        output.unlink()
    ExportPipeline().export(
        source,
        output,
        metadata,
        samples,
        OverlayConfig(),
        ExportConfig(codec="libx264", quality="Fast", overlay_fps=10, overlay_width=640, overlay_height=360),
    )
    print(preview)
    print(output)


if __name__ == "__main__":
    main()
