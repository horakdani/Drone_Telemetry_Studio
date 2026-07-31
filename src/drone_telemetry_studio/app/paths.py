from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    support: Path
    cache: Path
    logs: Path

    @classmethod
    def macos_default(cls) -> "AppPaths":
        override = os.environ.get("DRONE_TELEMETRY_DATA_DIR")
        if override:
            support = Path(override)
            return cls(support, support / "cache", support / "logs")
        home = Path.home()
        support = home / "Library/Application Support/DroneTelemetryStudio"
        cache = home / "Library/Caches/DroneTelemetryStudio"
        return cls(support, cache, support / "logs")
