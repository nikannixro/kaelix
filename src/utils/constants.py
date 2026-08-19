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
# Default metadata values (overridable per run via Config)
# ---------------------------------------------------------------------------
DEFAULT_VIDEO_NAME = "Video"
DEFAULT_VIDEO_LANGUAGE = "en"
DEFAULT_AUDIO_NAME = "Audio"
DEFAULT_SUBTITLE_NAME = "Subtitle"
DEFAULT_SUBTITLE_LANGUAGE_FA = "fa"
DEFAULT_SUBTITLE_LANGUAGE_EN = "en"
UNKNOWN_LANGUAGE = "und"

# Languages commonly tagged as "Persian/Farsi" and "English"
PERSIAN_LANGUAGE_CODES = {"fa", "fas", "per", "pes"}
ENGLISH_LANGUAGE_CODES = {"en", "eng"}

# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------
QUALITY_PATTERNS = [
    "4320p",
    "2160p",
    "1440p",
    "1080p",
    "720p",
    "480p",
]

# Source / release type tokens. Longest-first so "WEB-DL" wins over "WEB".
# Non-canonical spellings (WEBRip, BDRip, BR-Rip, BluRip, ...) live in
# SOURCE_NORMALIZATION below; keeping them here would shadow the canonical
# output, since this list is matched first.
SOURCE_TYPES = [
    "WEB-DL",
    "WEB",
    "BluRay",
    "HDRip",
    "HDTV",
    "DVDRip",
    "DVDScr",
    "DVD",
    "HDCAM",
    "CAM",
    "HDTS",
    "TS",
    "TC",
    "REMUX",
]

# Variant spellings -> canonical output source token. Keys are lowercase and
# matched with token-boundary regex, so glued/hyphenated/spaced variants all hit.
SOURCE_NORMALIZATION = {
    "webrip": "WEB-DL",
    "web-rip": "WEB-DL",
    "webrip-": "WEB-DL",  # trailing-hyphen artifacts like "WEBRip-720p"
    "web rip": "WEB-DL",
    "webdl": "WEB-DL",
    "web-dl": "WEB-DL",
    "bluray": "BluRay",
    "blu-ray": "BluRay",
    "blu ray": "BluRay",
    "blurip": "BluRay",
    "blu-rip": "BluRay",
    "blu rip": "BluRay",
    "bdrip": "BluRay",
    "bd-rip": "BluRay",
    "brrip": "BluRay",
    "br-rip": "BluRay",
}

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

# Fallbacks used when a filename yields nothing.
DEFAULT_QUALITY = "1080p"
DEFAULT_SOURCE_TYPE = "WEB-DL"
DEFAULT_CODEC = "x265"

# Series episode / movie year patterns
SERIES_EPISODE_REGEX = r"[Ss](\d{1,2})[Ee](\d{1,3})"
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

# External subtitle filename tags
SUBTITLE_SUFFIX = " [Subtitle]"
ENGLISH_SUBTITLE_TAG = "[english]"
SDH_SUBTITLE_TAG = "[SDH]"
SDH_MARKER = "sdh"

SUBTITLE_EXTENSIONS = (".srt", ".ass", ".ssa", ".sub", ".vtt")

# MIME type prefix used to detect image/cover attachments that should be removed.
IMAGE_MIME_PREFIX = "image/"
