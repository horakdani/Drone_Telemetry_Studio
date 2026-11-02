from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True, slots=True)
class MediaTools:
    ffmpeg: str
    ffprobe: str


def discover_media_tools() -> MediaTools:
    def locate(name: str) -> str | None:
        found = shutil.which(name)
        if found:
            return found
        # An .app launched from Finder does not inherit the Homebrew shell PATH.
        for directory in (Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/usr/bin")):
            candidate = directory / name
            if candidate.is_file() and candidate.stat().st_mode & 0o111:
                return str(candidate)
        return None

    ffmpeg = locate("ffmpeg")
    ffprobe = locate("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(
            "FFmpeg or FFprobe was not found. Install on macOS with: brew install ffmpeg"
        )
    return MediaTools(ffmpeg, ffprobe)


def available_video_encoders(ffmpeg_path: str | None = None) -> set[str]:
    executable = ffmpeg_path or discover_media_tools().ffmpeg
    completed = subprocess.run(
        [executable, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    encoders: set[str] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


def extract_preview_frame(
    video_path: str | Path,
    time_seconds: float,
    *,
    max_width: int = 1280,
    ffmpeg_path: str | None = None,
) -> Image.Image:
    """Requests a single proxy frame from FFmpeg; the video is never loaded into memory."""
    executable = ffmpeg_path or discover_media_tools().ffmpeg
    command = [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, time_seconds):.6f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale='min({max_width},iw)':-2",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]
    completed = subprocess.run(command, capture_output=True, check=False, timeout=45)
    if completed.returncode != 0 or not completed.stdout:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Could not read the preview frame. {detail[-600:]}")
    from io import BytesIO

    with Image.open(BytesIO(completed.stdout)) as image:
        return image.convert("RGB").copy()
