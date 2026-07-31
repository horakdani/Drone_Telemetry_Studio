from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class VideoMetadata:
    path: Path
    duration_seconds: float
    width: int
    height: int
    average_fps: float
    nominal_fps: float
    codec_name: str
    pixel_format: str | None
    has_audio: bool
    audio_codec: str | None
    creation_time: datetime | None
    is_variable_frame_rate: bool

    @property
    def resolution_label(self) -> str:
        return f"{self.width} × {self.height}"

