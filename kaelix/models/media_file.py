"""MediaFile data model."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.constants import (
    DEFAULT_CODEC,
    DEFAULT_QUALITY,
    DEFAULT_SOURCE_TYPE,
    IMAGE_MIME_PREFIX,
    MOVIE_NAME_TEMPLATE,
    MOVIE_SEGMENT_TITLE_TEMPLATE,
    SERIES_NAME_TEMPLATE,
    SERIES_SEGMENT_TITLE_TEMPLATE,
)
from .track import Track


@dataclass
class MediaFile:
    """One MKV file being processed."""

    source_path: Path
    output_path: Path
    relative_path: Path
    tracks: list[Track] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Parsed filename information
    is_series: bool = False
    title: str = ""
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    quality: str = ""
    source_type: str = ""
    codec: str = ""

    # Per-file audio decision (resolved by prompts)
    selected_audio_language: str = ""

    @property
    def video_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.is_video]

    @property
    def audio_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.is_audio]

    @property
    def subtitle_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.is_subtitle]

    @property
    def image_attachments(self) -> list[dict[str, Any]]:
        """Attachments whose MIME type looks like an image/cover."""
        return [
            a for a in self.attachments
            if str(a.get("content_type", "")).lower().startswith(IMAGE_MIME_PREFIX)
        ]

    @property
    def segment_title(self) -> str:
        """The MKV container title (no quality/source/codec tags)."""
        if self.is_series:
            return SERIES_SEGMENT_TITLE_TEMPLATE.format(
                title=self.title.strip(),
                season=self.season if self.season is not None else 1,
                episode=self.episode if self.episode is not None else 1,
            )
        return MOVIE_SEGMENT_TITLE_TEMPLATE.format(
            title=self.title.strip(),
            year=self.year if self.year is not None else 0,
        )

    @property
    def target_name(self) -> str:
        """The final output filename (without extension)."""
        common = {
            "title": self.title.strip(),
            "quality": self.quality or DEFAULT_QUALITY,
            "source": self.source_type or DEFAULT_SOURCE_TYPE,
            "codec": self.codec or DEFAULT_CODEC,
        }
        if self.is_series:
            return SERIES_NAME_TEMPLATE.format(
                season=self.season if self.season is not None else 1,
                episode=self.episode if self.episode is not None else 1,
                **common,
            )
        return MOVIE_NAME_TEMPLATE.format(
            year=self.year if self.year is not None else 0,
            **common,
        )

    @property
    def target_filename(self) -> str:
        return self.target_name + ".mkv"
