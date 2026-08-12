"""Match external subtitle files to their intended MKV target names.

Naming conventions (stem = the MKV's segment title):

  Persian / generic:  "<stem> [Subtitle].srt"
  English non-SDH:    "<stem> [Subtitle] [english].srt"
  English SDH:        "<stem> [Subtitle] [english] [SDH].srt"
"""
from __future__ import annotations

from pathlib import Path

from ..models.media_file import MediaFile
from ..utils.constants import (
    ENGLISH_SUBTITLE_TAG,
    SDH_SUBTITLE_TAG,
    SUBTITLE_EXTENSIONS,
    SUBTITLE_SUFFIX,
)
from ..utils.logger import get_logger

log = get_logger(__name__)


def _subtitle_index(directory: Path) -> dict[str, Path]:
    """Map lowercased stem -> path for every subtitle file in `directory`."""
    directory = Path(directory)
    if not directory.is_dir():
        return {}
    return {
        c.stem.lower(): c
        for c in sorted(directory.iterdir())
        if c.suffix.lower() in SUBTITLE_EXTENSIONS
    }


def _base_stem(media: MediaFile) -> str:
    return f"{media.segment_title}{SUBTITLE_SUFFIX}"


def find_persian_subtitle_match(media: MediaFile, directory: Path) -> Path | None:
    """Find '<segment title> [Subtitle].<ext>' in the Persian subtitle directory."""
    return _subtitle_index(directory).get(_base_stem(media).lower())


def find_english_subtitle_match(
    media: MediaFile, directory: Path
) -> tuple[Path, bool] | None:
    """Find the English subtitle for `media`, returning (path, is_sdh).

    Priority: '[english] [SDH]', then '[english]', then the generic stem.
    """
    index = _subtitle_index(directory)
    base = _base_stem(media)
    for stem, is_sdh in (
        (f"{base} {ENGLISH_SUBTITLE_TAG} {SDH_SUBTITLE_TAG}", True),
        (f"{base} {ENGLISH_SUBTITLE_TAG}", False),
        (base, False),
    ):
        match = index.get(stem.lower())
        if match is not None:
            return match, is_sdh
    return None
