from __future__ import annotations

import json
import subprocess
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from drone_telemetry_studio.domain.video import VideoMetadata
from drone_telemetry_studio.media.ffmpeg import discover_media_tools


def _rate(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def _datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def probe_video(path: str | Path, ffprobe_path: str | None = None) -> VideoMetadata:
    source = Path(path)
    executable = ffprobe_path or discover_media_tools().ffprobe
    command = [
        executable,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(source),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
    if completed.returncode != 0:
        raise RuntimeError(f"Could not read the video metadata. {completed.stderr.strip()[-800:]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFprobe returned an invalid response.") from exc
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("The selected file contains no video stream.")
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    format_data = payload.get("format", {})
    duration = float(video.get("duration") or format_data.get("duration") or 0)
    average_fps = _rate(video.get("avg_frame_rate"))
    nominal_fps = _rate(video.get("r_frame_rate"))
    creation_time = (video.get("tags") or {}).get("creation_time") or (format_data.get("tags") or {}).get("creation_time")
    vfr = bool(average_fps and nominal_fps and abs(average_fps - nominal_fps) / nominal_fps > 0.005)
    return VideoMetadata(
        path=source,
        duration_seconds=duration,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        average_fps=average_fps,
        nominal_fps=nominal_fps,
        codec_name=str(video.get("codec_name") or "unknown"),
        pixel_format=video.get("pix_fmt"),
        has_audio=audio is not None,
        audio_codec=audio.get("codec_name") if audio else None,
        creation_time=_datetime(creation_time),
        is_variable_frame_rate=vfr,
    )

