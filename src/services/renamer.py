"""Filename parsing, codec detection, and target-name construction."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..models.media_file import MediaFile
from ..utils.constants import (
    CODEC_NORMALIZATION,
    MOVIE_YEAR_REGEX,
    QUALITY_PATTERNS,
    SERIES_EPISODE_REGEX,
    SOURCE_TYPES,
    TEN_BIT_TOKENS,
)
from ..utils.logger import get_logger

log = get_logger(__name__)


def _clean_title(raw: str) -> str:
    """Normalize a title fragment extracted from a filename."""
    cleaned = re.sub(r"[._]", " ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" -[](){}:.,")
    return cleaned.strip()


def _detect_quality(tokens_lower: str) -> str:
    for q in QUALITY_PATTERNS:
        if q.lower() in tokens_lower:
            return q
    if "4k" in tokens_lower or "2160" in tokens_lower:
        return "2160p"
    return ""


def _detect_source(tokens_lower: str) -> str:
    """Detect the release source/type, preserving canonical casing."""
    for src in SOURCE_TYPES:
        pattern = r"(?<![a-z0-9])" + re.escape(src.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, tokens_lower):
            return src
    return ""


def _detect_codec_name_from_filename(tokens_lower: str) -> str:
    """Detect the base codec name from the filename.

    Returns 'x265' / 'x264' / 'av1' / 'vp9' or '' if not found.
    """
    for token, normalized in CODEC_NORMALIZATION.items():
        pattern = r"(?<![a-z0-9])" + re.escape(token.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, tokens_lower):
            return normalized
    return ""


def _detect_10bit_from_filename(tokens_lower: str) -> bool:
    """Return True if a 10-bit token is present in the filename."""
    for token in TEN_BIT_TOKENS:
        if token.lower() in tokens_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# File-based codec / bit-depth detection (fallback when filename lacks info)
# ---------------------------------------------------------------------------
def detect_video_codec_from_file(media: MediaFile) -> str:
    """Detect the video codec from the mkvmerge-identified video track.

    Returns 'x265' / 'x264' / 'av1' / 'vp9' or '' if unknown.
    """
    if not media.video_tracks:
        return ""
    codec_raw = (media.video_tracks[0].codec or "").lower()
    if "hevc" in codec_raw or "h265" in codec_raw or "h.265" in codec_raw:
        return "x265"
    if "avc" in codec_raw or "h264" in codec_raw or "h.264" in codec_raw:
        return "x264"
    if "av1" in codec_raw:
        return "av1"
    if "vp9" in codec_raw:
        return "vp9"
    return ""


def detect_10bit_from_file(file_path: Path, ffprobe_path: Path | None = None) -> bool:
    """Use ffprobe to detect whether the first video stream is 10-bit or higher.

    Requires ffprobe on PATH. Returns False on any failure (never raises).
    """
    if ffprobe_path is not None:
        ffprobe = str(ffprobe_path)
    else:
        ffprobe = shutil.which("ffprobe")
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
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(f"ffprobe 10-bit detection failed for {file_path}: {exc}")
        return False

    pix_fmt = proc.stdout.strip().lower()
    # pix_fmt examples: 'yuv420p' (8-bit), 'yuv420p10le' (10-bit), 'yuv420p12le' (12-bit)
    match = re.search(r"p(\d{1,2})(?:le|be)?$", pix_fmt)
    if match:
        bit_depth = int(match.group(1))
        return bit_depth >= 10
    return False


def resolve_codec(media: MediaFile, ffprobe_path: Path | None = None) -> str:
    """Resolve the final codec string using filename first, then the actual file.

    Order:
      1. Codec name  -> filename tokens, else mkvmerge-identified video codec,
                        else 'x265' (last resort).
      2. 10-bit flag -> filename tokens, else ffprobe pixel format.
    """
    filename_lower = media.source_path.stem.lower()
    codec_name = _detect_codec_name_from_filename(filename_lower)
    is_10bit = _detect_10bit_from_filename(filename_lower)

    if not codec_name:
        codec_name = detect_video_codec_from_file(media)
        if codec_name:
            log.info(f"Codec detected from file: {codec_name}")
        else:
            codec_name = "x265"
            log.warning("Could not detect codec from filename or file; defaulting to x265.")

    if not is_10bit:
        if detect_10bit_from_file(media.source_path, ffprobe_path):
            is_10bit = True
            log.info("10-bit depth detected from file via ffprobe.")

    if is_10bit:
        return f"{codec_name} 10 Bit"
    return codec_name


def parse_filename(filename: str) -> dict:
    """Parse a filename into structured components.

    Returns a dict with keys: is_series, title, year, season, episode,
    quality, source. (Codec is resolved separately via resolve_codec().)
    """
    stem = Path(filename).stem
    lowered = stem.lower()

    # --- Series detection ---
    series_match = re.search(SERIES_EPISODE_REGEX, stem)
    is_series = series_match is not None

    if is_series:
        season = int(series_match.group(1))
        episode = int(series_match.group(2))
        year = None
        title_part = stem[: series_match.start()]
        title_part = re.sub(r"[\s._-]+$", "", title_part)
        title = _clean_title(title_part)
        rest = stem[series_match.end():]
    else:
        season = episode = None
        year_match = re.search(MOVIE_YEAR_REGEX, stem)
        if year_match:
            year = int(year_match.group(1))
            title_part = stem[: year_match.start()]
            title = _clean_title(title_part)
            rest = stem[year_match.end():]
        else:
            year = None
            split_idx = None
            for q in QUALITY_PATTERNS:
                m = re.search(r"(?<![a-z0-9])" + re.escape(q.lower()) + r"(?![a-z0-9])", lowered)
                if m:
                    split_idx = m.start()
                    break
            if split_idx:
                title = _clean_title(stem[:split_idx])
                rest = stem[split_idx:]
            else:
                title = _clean_title(stem)
                rest = ""

    rest_lower = rest.lower()
    quality = _detect_quality(lowered) or _detect_quality(rest_lower)
    source = _detect_source(lowered)

    return {
        "is_series": is_series,
        "title": title,
        "year": year,
        "season": season,
        "episode": episode,
        "quality": quality,
        "source": source,
    }


def populate_media_file_from_filename(media: MediaFile, ffprobe_path: Path | None = None) -> MediaFile:
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
    """Return a list of warnings if the parsed data looks incomplete."""
    warnings: list[str] = []
    if not media.title:
        warnings.append("Could not parse a title.")
    if media.is_series:
        if media.season is None or media.episode is None:
            warnings.append("Series detected but season/episode missing.")
    else:
        if media.year is None:
            warnings.append("Movie detected but year missing.")
    if not media.quality:
        warnings.append("Quality not detected; defaulting to 1080p.")
    if not media.source_type:
        warnings.append("Source type not detected; defaulting to WEB-DL.")
    return warnings
