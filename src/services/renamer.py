"""Filename parsing, codec detection, and target-name construction."""
from __future__ import annotations

import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

from ..models.media_file import MediaFile
from ..utils.constants import (
    CODEC_NORMALIZATION,
    DEFAULT_CODEC,
    DEFAULT_QUALITY,
    DEFAULT_SOURCE_TYPE,
    FFPROBE_BIN,
    MOVIE_YEAR_REGEX,
    QUALITY_PATTERNS,
    SERIES_EPISODE_REGEX,
    SOURCE_TYPES,
    TEN_BIT_TOKENS,
)
from ..utils.logger import get_logger

log = get_logger(__name__)

_SERIES_RE = re.compile(SERIES_EPISODE_REGEX)
_YEAR_RE = re.compile(MOVIE_YEAR_REGEX)
_PIX_FMT_DEPTH_RE = re.compile(r"p(\d{1,2})(?:le|be)?$")
_SEPARATOR_RE = re.compile(r"[._]")
_WHITESPACE_RE = re.compile(r"\s+")


@cache
def _token_re(token: str) -> re.Pattern[str]:
    """Compiled matcher for `token`, only when not glued to other alphanumerics.

    Cached: the same ~30 tokens are tested against every filename in a batch.
    """
    return re.compile(r"(?<![a-z0-9])" + re.escape(token.lower()) + r"(?![a-z0-9])")


def _clean_title(raw: str) -> str:
    """Normalize a title fragment extracted from a filename."""
    cleaned = _SEPARATOR_RE.sub(" ", raw)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip(" -[](){}:.,").strip()


def _detect_quality(text_lower: str) -> str:
    for q in QUALITY_PATTERNS:
        if _token_re(q).search(text_lower):
            return q
    if _token_re("4k").search(text_lower) or "2160" in text_lower:
        return "2160p"
    return ""


def _detect_source(text_lower: str) -> str:
    """Detect the release source/type, preserving canonical casing."""
    for src in SOURCE_TYPES:
        if _token_re(src).search(text_lower):
            return src
    return ""


def _detect_codec_name_from_filename(text_lower: str) -> str:
    """Return 'x265' / 'x264' / 'av1' / 'vp9', or '' when absent."""
    for token, normalized in CODEC_NORMALIZATION.items():
        if _token_re(token).search(text_lower):
            return normalized
    return ""


def _detect_10bit_from_filename(text_lower: str) -> bool:
    return any(token.lower() in text_lower for token in TEN_BIT_TOKENS)


# ---------------------------------------------------------------------------
# File-based codec / bit-depth detection (fallback when the filename lacks it)
# ---------------------------------------------------------------------------

def detect_video_codec_from_file(media: MediaFile) -> str:
    """Detect the codec from the mkvmerge-identified video track."""
    if not media.video_tracks:
        return ""
    codec_raw = (media.video_tracks[0].codec or "").lower()
    for needles, normalized in (
        (("hevc", "h265", "h.265"), "x265"),
        (("avc", "h264", "h.264"), "x264"),
        (("av1",), "av1"),
        (("vp9",), "vp9"),
    ):
        if any(n in codec_raw for n in needles):
            return normalized
    return ""


def detect_10bit_from_file(file_path: Path, ffprobe_path: Path | None = None) -> bool:
    """Use ffprobe to detect a 10-bit-or-deeper first video stream.

    Returns False on any failure; bit depth is cosmetic in the output name.
    """
    ffprobe = str(ffprobe_path) if ffprobe_path else shutil.which(FFPROBE_BIN)
    if not ffprobe:
        return False
    try:
        proc = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=pix_fmt",
                "-of", "csv=s=x:p=0",
                str(file_path),
            ],
            check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning(f"ffprobe 10-bit detection failed for {file_path}: {exc}")
        return False

    # pix_fmt examples: 'yuv420p' (8-bit), 'yuv420p10le' (10-bit)
    match = _PIX_FMT_DEPTH_RE.search(proc.stdout.strip().lower())
    return bool(match) and int(match.group(1)) >= 10


def resolve_codec(media: MediaFile, ffprobe_path: Path | None = None) -> str:
    """Resolve the codec string from the filename first, then the file itself."""
    filename_lower = media.source_path.stem.lower()
    codec_name = _detect_codec_name_from_filename(filename_lower)
    is_10bit = _detect_10bit_from_filename(filename_lower)

    if not codec_name:
        codec_name = detect_video_codec_from_file(media)
        if codec_name:
            log.info(f"Codec detected from file: {codec_name}")
        else:
            codec_name = DEFAULT_CODEC
            log.warning(
                f"Could not detect codec from filename or file; using {DEFAULT_CODEC}."
            )

    # Only shell out to ffprobe when the filename didn't already settle it.
    if not is_10bit and detect_10bit_from_file(media.source_path, ffprobe_path):
        is_10bit = True
        log.info("10-bit depth detected from file via ffprobe.")

    return f"{codec_name} 10 Bit" if is_10bit else codec_name


def parse_filename(filename: str) -> dict:
    """Parse a filename into is_series/title/year/season/episode/quality/source."""
    stem = Path(filename).stem
    lowered = stem.lower()

    series_match = _SERIES_RE.search(stem)
    if series_match is not None:
        season = int(series_match.group(1))
        episode = int(series_match.group(2))
        year = None
        title = _clean_title(stem[: series_match.start()])
    else:
        season = episode = None
        year_match = _YEAR_RE.search(stem)
        if year_match:
            year = int(year_match.group(1))
            title = _clean_title(stem[: year_match.start()])
        else:
            year = None
            # No year: cut the title at the first quality token if there is one.
            split_idx = None
            for q in QUALITY_PATTERNS:
                m = _token_re(q).search(lowered)
                if m:
                    split_idx = m.start()
                    break
            title = _clean_title(stem if split_idx is None else stem[:split_idx])

    return {
        "is_series": series_match is not None,
        "title": title,
        "year": year,
        "season": season,
        "episode": episode,
        "quality": _detect_quality(lowered),
        "source": _detect_source(lowered),
    }


def populate_media_file_from_filename(
    media: MediaFile, ffprobe_path: Path | None = None
) -> MediaFile:
    """Fill in parsed filename fields on a MediaFile in place."""
    parsed = parse_filename(media.source_path.name)
    media.is_series = parsed["is_series"]
    media.title = parsed["title"]
    media.year = parsed["year"]
    media.season = parsed["season"]
    media.episode = parsed["episode"]
    media.quality = parsed["quality"]
    media.source_type = parsed["source"]
    media.codec = resolve_codec(media, ffprobe_path)
    return media


def validate_parse(media: MediaFile) -> list[str]:
    """Warnings for parsed data that fell back to a default."""
    warnings: list[str] = []
    if not media.title:
        warnings.append("Could not parse a title.")
    if media.is_series:
        if media.season is None or media.episode is None:
            warnings.append("Series detected but season/episode missing.")
    elif media.year is None:
        warnings.append("Movie detected but year missing.")
    if not media.quality:
        warnings.append(f"Quality not detected; defaulting to {DEFAULT_QUALITY}.")
    if not media.source_type:
        warnings.append(f"Source type not detected; defaulting to {DEFAULT_SOURCE_TYPE}.")
    return warnings
