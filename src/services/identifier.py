"""Wrapper around `mkvmerge --identification-format json --identify`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..models.media_file import MediaFile
from ..models.track import Track
from ..utils.logger import get_logger
from ..utils.validators import ValidationError

log = get_logger(__name__)


def identify_file(
    file_path: Path | str,
    mkvmerge_path: Path,
    timeout: int = 60,
) -> dict[str, Any]:
    """Run mkvmerge identification on a single file and return parsed JSON."""
    path = Path(file_path)
    if not path.exists():
        raise ValidationError(f"File not found: {path}")
    if path.suffix.lower() != ".mkv":
        raise ValidationError(f"Not an MKV file: {path}")

    cmd = [
        str(mkvmerge_path),
        "--identification-format", "json",
        "--identify",
        str(path),
    ]
    log.debug(f"Running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        log.error(f"mkvmerge failed for {path}: {exc.stderr}")
        raise ValidationError(f"mkvmerge identify failed: {exc.stderr}")
    except FileNotFoundError as exc:
        raise ValidationError(
            f"mkvmerge binary not found: {mkvmerge_path}"
        ) from exc

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Could not parse mkvmerge output for {path}: {exc}") from exc


def build_media_file(file_path: Path, mkvmerge_path: Path) -> MediaFile:
    """Create a MediaFile object populated with identified tracks and attachments."""
    data = identify_file(file_path, mkvmerge_path)
    track_data = data.get("tracks", [])
    attachments = data.get("attachments", []) or []
    tracks = [_build_track(t) for t in track_data]

    media = MediaFile(
        source_path=file_path.resolve(),
        output_path=file_path.resolve(),  # overwritten later
        relative_path=Path("."),
        tracks=tracks,
        attachments=attachments,
    )
    return media


def _build_track(data: dict[str, Any]) -> Track:
    """Convert mkvmerge JSON track entry into a Track instance."""
    return Track(
        id=data["id"],
        type=data.get("type", "unknown"),
        codec=data.get("codec", ""),
        properties=data.get("properties", {}) or {},
    )
