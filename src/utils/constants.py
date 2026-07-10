"""Project-wide constants."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# External binaries (expected on PATH, or overridable via CLI flags)
# ---------------------------------------------------------------------------
MKVMERGE_BIN = "mkvmerge"
MKVPROPEDIT_BIN = "mkvpropedit"
FFPROBE_BIN = "ffprobe"

# ---------------------------------------------------------------------------
# Track type names as reported by mkvmerge JSON identification
# ---------------------------------------------------------------------------
TRACK_TYPE_VIDEO = "video"
TRACK_TYPE_AUDIO = "audio"
TRACK_TYPE_SUBTITLE = "subtitles"

# Short selector letters used by mkvpropedit (track:v1, track:a1, track:s1)
TRACK_TYPE_SELECTOR = {
    TRACK_TYPE_VIDEO: "v",
    TRACK_TYPE_AUDIO: "a",
    TRACK_TYPE_SUBTITLE: "s",
}

# ---------------------------------------------------------------------------
# Default metadata values (overridable via config/defaults.yaml)
# ---------------------------------------------------------------------------
DEFAULT_VIDEO_NAME = "Video"
DEFAULT_VIDEO_LANGUAGE = "en"
DEFAULT_AUDIO_NAME = "Audio"
DEFAULT_SUBTITLE_NAME = "Subtitle"
DEFAULT_SUBTITLE_LANGUAGE_FA = "fa"
DEFAULT_SUBTITLE_LANGUAGE_EN = "en"

# Languages that are commonly tagged as "Persian/Farsi"
PERSIAN_LANGUAGE_CODES = {"fa", "fas", "per", "pes"}

# Languages that are commonly tagged as "English"
ENGLISH_LANGUAGE_CODES = {"en", "eng"}

# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------
QUALITY_PATTERNS = [
    "2160p",
    "1080p",
    "720p",
    "480p",
    "4320p",
    "1440p",
]

# Source / release type tokens (case-insensitive)
SOURCE_TYPES = [
    "WEB-DL",
    "WEBRip",
    "WEB",
    "BluRay",
    "BDRip",
    "BR-Rip",
    "HDRip",
    "HDTV",
    "DVDRip",
    "DVDScr",
    "DVD",
    "CAM",
    "HDCAM",
    "TS",
    "HDTS",
    "TC",
    "REMUX",
]

# Codec tokens and how they should be normalized in the output filename.
CODEC_NORMALIZATION = {
    "x265": "x265",
    "h265": "x265",
    "hevc": "x265",
    "x264": "x264",
    "h264": "x264",
    "avc": "x264",
    "av1": "av1",
    "vp9": "vp9",
}

TEN_BIT_TOKENS = ["10bit", "10-bit", "10 bit", "hi10p"]

# Series episode regex (case-insensitive)
SERIES_EPISODE_REGEX = r"[Ss](\d{1,2})[Ee](\d{1,3})"
# Movie year regex
MOVIE_YEAR_REGEX = r"(?:^|[\s.\(_-])((?:19|20)\d{2})(?:[\s.\)_-]|$)"

# ---------------------------------------------------------------------------
# File naming templates
# ---------------------------------------------------------------------------
MOVIE_NAME_TEMPLATE = "{title} ({year}) [{quality}] [{source}] [{codec}]"
SERIES_NAME_TEMPLATE = "{title} - S{season:02d}E{episode:02d} [{quality}] [{source}] [{codec}]"

# Segment (container) title embedded in metadata:
#   Movies -> "MOVIE NAME (YEAR)"
#   Series -> "SERIES NAME - S00E00"
MOVIE_SEGMENT_TITLE_TEMPLATE = "{title} ({year})"
SERIES_SEGMENT_TITLE_TEMPLATE = "{title} - S{season:02d}E{episode:02d}"

MOVIE_SUBTITLE_SUFFIX = " [Subtitle]"
SERIES_SUBTITLE_SUFFIX = " [Subtitle]"
ENGLISH_SUBTITLE_TAG = "[english]"
SDH_SUBTITLE_TAG = "[SDH]"

SUBTITLE_EXTENSIONS = (".srt", ".ass", ".ssa", ".sub", ".vtt")

# MIME type prefix used to detect image/cover attachments that should be removed.
IMAGE_MIME_PREFIX = "image/"

# Log directory (relative to project root)
LOG_DIR_NAME = "logs"
