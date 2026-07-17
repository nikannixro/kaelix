"""MediaFile data model."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .track import Track


@dataclass
class MediaFile:
    """Represents one MKV file being processed."""

    source_path: Path
    output_path: Path
    relative_path: Path
    tracks: list[Track] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Parsed filename information
    is_series: bool = False
    title: str = ""
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    quality: str = ""
    source_type: str = ""
    codec: str = ""

    # Per-file audio decision (resolved by prompts)
    selected_audio_language: str = ""

    # ------------------------------------------------------------------
    # Track grouping helpers
    # ------------------------------------------------------------------
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
        from ..utils.constants import IMAGE_MIME_PREFIX

        return [
            a for a in self.attachments
            if str(a.get("content_type", "")).lower().startswith(IMAGE_MIME_PREFIX)
        ]

    # ------------------------------------------------------------------
    # Name builders
    # ------------------------------------------------------------------
    @property
    def segment_title(self) -> str:
        """The MKV container title (no quality/source/codec tags)."""
        from ..utils.constants import (
            MOVIE_SEGMENT_TITLE_TEMPLATE,
            SERIES_SEGMENT_TITLE_TEMPLATE,
        )

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
        from ..utils.constants import MOVIE_NAME_TEMPLATE, SERIES_NAME_TEMPLATE

        if self.is_series:
            return SERIES_NAME_TEMPLATE.format(
                title=self.title.strip(),
                season=self.season if self.season is not None else 1,
                episode=self.episode if self.episode is not None else 1,
                quality=self.quality or "1080p",
                source=self.source_type or "WEB-DL",
                codec=self.codec or "x265",
            )
        return MOVIE_NAME_TEMPLATE.format(
            title=self.title.strip(),
            year=self.year if self.year is not None else 0,
            quality=self.quality or "1080p",
            source=self.source_type or "WEB-DL",
            codec=self.codec or "x265",
        )

    @property
    def target_filename(self) -> str:
        return self.target_name + ".mkv"

    def describe(self) -> str:
        kind = "SERIES" if self.is_series else "MOVIE"
        return (
            f"[{kind}] {self.source_path.name}  ->  {self.target_filename}  "
            f"({len(self.video_tracks)}V/{len(self.audio_tracks)}A/"
            f"{len(self.subtitle_tracks)}S)"
        )
