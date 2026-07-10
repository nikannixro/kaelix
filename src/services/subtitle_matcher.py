"""Match external subtitle files to their intended MKV target names.

Subtitle file naming conventions:

  Generic (Persian / any language):
    Movie:  "MOVIE NAME (YEAR) [Subtitle].srt"
    Series: "SERIES NAME - S00E00 [Subtitle].srt"

  English (with SDH flag in the filename):
    Movie non-SDH: "MOVIE NAME (YEAR) [Subtitle] [english].srt"
    Movie SDH:     "MOVIE NAME (YEAR) [Subtitle] [english] [SDH].srt"
    Series non-SDH: "SERIES NAME - S00E00 [Subtitle] [english].srt"
    Series SDH:     "SERIES NAME - S00E00 [Subtitle] [english] [SDH].srt"
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models.media_file import MediaFile
from ..utils.constants import (
    ENGLISH_SUBTITLE_TAG,
    MOVIE_SUBTITLE_SUFFIX,
    SDH_SUBTITLE_TAG,
    SERIES_SUBTITLE_SUFFIX,
    SUBTITLE_EXTENSIONS,
)
from ..utils.logger import get_logger

log = get_logger(__name__)


def _base_subtitle_stem(media: MediaFile) -> str:
    """The generic subtitle filename stem: '{segment_title} [Subtitle]'."""
    suffix = SERIES_SUBTITLE_SUFFIX if media.is_series else MOVIE_SUBTITLE_SUFFIX
    return f"{media.segment_title}{suffix}"


def find_persian_subtitle_match(
    media: MediaFile, directory: Path
) -> Optional[Path]:
    """Search the Persian subtitle directory for '{segment_title} [Subtitle].srt/.ass'.

    Only the generic pattern is matched (no [english]/[SDH] tags).
    Returns the matched file path, or None.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return None

    expected = _base_subtitle_stem(media)
    for candidate in sorted(directory.iterdir()):
        if candidate.suffix.lower() not in SUBTITLE_EXTENSIONS:
            continue
        if candidate.stem == expected:
            return candidate
    return None


def find_english_subtitle_match(
    media: MediaFile, directory: Path
) -> Optional[tuple[Path, bool]]:
    """Search the English subtitle directory.

    Returns (file_path, is_sdh) or None.

    Matching priority (case-insensitive on the tag tokens):
      1. '{segment_title} [Subtitle] [english] [SDH]'  -> is_sdh = True
      2. '{segment_title} [Subtitle] [english]'         -> is_sdh = False
      3. '{segment_title} [Subtitle]' (generic fallback) -> is_sdh = False
    """
    directory = Path(directory)
    if not directory.is_dir():
        return None

    base = _base_subtitle_stem(media)
    sdh_stem = f"{base} {ENGLISH_SUBTITLE_TAG} {SDH_SUBTITLE_TAG}"
    eng_stem = f"{base} {ENGLISH_SUBTITLE_TAG}"

    # Build a case-insensitive lookup of subtitle stems.
    candidates: dict[str, Path] = {}
    for candidate in sorted(directory.iterdir()):
        if candidate.suffix.lower() not in SUBTITLE_EXTENSIONS:
            continue
        candidates[candidate.stem.lower()] = candidate

    if sdh_stem.lower() in candidates:
        return candidates[sdh_stem.lower()], True
    if eng_stem.lower() in candidates:
        return candidates[eng_stem.lower()], False
    if base.lower() in candidates:
        return candidates[base.lower()], False
    return None
