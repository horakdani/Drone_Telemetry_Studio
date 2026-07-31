from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(slots=True)
class TileCache:
    """Feltételes HTTP-kéréseket és legalább hétnapos helyi cache-t biztosít."""

    root: Path
    minimum_ttl_seconds: int = 7 * 24 * 60 * 60
    user_agent: str = "DroneTelemetryStudio/0.1 (local macOS application)"

    def _paths(self, url: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.png", self.root / f"{digest}.json"

    def get(self, url: str, *, allow_network: bool) -> Path | None:
        if not self.root.exists():
            if not allow_network:
                return None
            self.root.mkdir(parents=True, exist_ok=True)
        image_path, metadata_path = self._paths(url)
        metadata = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                metadata = {}
        fetched_at = float(metadata.get("fetched_at", 0))
        if image_path.exists() and time.time() - fetched_at < self.minimum_ttl_seconds:
            return image_path
        if not allow_network:
            return image_path if image_path.exists() else None

        headers = {"User-Agent": self.user_agent}
        if metadata.get("etag"):
            headers["If-None-Match"] = metadata["etag"]
        if metadata.get("last_modified"):
            headers["If-Modified-Since"] = metadata["last_modified"]
        try:
            with urlopen(Request(url, headers=headers), timeout=15) as response:
                content_type = response.headers.get("Content-Type", "")
                if "image" not in content_type:
                    return image_path if image_path.exists() else None
                image_path.write_bytes(response.read())
                metadata = {
                    "fetched_at": time.time(),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                }
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        except HTTPError as exc:
            if exc.code == 304 and image_path.exists():
                metadata["fetched_at"] = time.time()
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            else:
                return image_path if image_path.exists() else None
        except OSError:
            return image_path if image_path.exists() else None
        return image_path if image_path.exists() else None

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def size_bytes(self) -> int:
        if not self.root.exists():
            return 0
        return sum(path.stat().st_size for path in self.root.glob("*") if path.is_file())
