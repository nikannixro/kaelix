"""Run configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .utils.constants import (
    DEFAULT_AUDIO_NAME,
    DEFAULT_SUBTITLE_NAME,
    DEFAULT_VIDEO_LANGUAGE,
    DEFAULT_VIDEO_NAME,
)


@dataclass
class Config:
    """Resolved configuration for a single batch run."""

    source_dir: Path
    output_dir: Path
    persian_subtitle_dir: Optional[Path] = None
    english_subtitle_dir: Optional[Path] = None
    audio_language: str = "en"
    dry_run: bool = False
    non_interactive: bool = False

    # Optional explicit binary paths (resolved during validation)
    mkvmerge_path: Optional[Path] = None
    mkvpropedit_path: Optional[Path] = None
    ffprobe_path: Optional[Path] = None

    # Metadata rules (defaults)
    video_name: str = DEFAULT_VIDEO_NAME
    video_language: str = DEFAULT_VIDEO_LANGUAGE
    video_default: bool = True
    video_forced: bool = False

    audio_name: str = DEFAULT_AUDIO_NAME
    audio_default: bool = True
    audio_forced: bool = False

    subtitle_name: str = DEFAULT_SUBTITLE_NAME
    subtitle_default: bool = True   # Persian subtitle default
    subtitle_forced: bool = True    # Persian subtitle forced
    english_subtitle_default: bool = False
    english_subtitle_forced: bool = False
    english_subtitle_name_sdh: str = "English [SDH]"
    english_subtitle_name_non_sdh: str = "English"

    def describe(self) -> str:
        return (
            f"source          = {self.source_dir}\n"
            f"output          = {self.output_dir}\n"
            f"persian subs    = {self.persian_subtitle_dir}\n"
            f"english subs    = {self.english_subtitle_dir}\n"
            f"audio lang      = {self.audio_language}\n"
            f"dry-run         = {self.dry_run}\n"
            f"non-interactive = {self.non_interactive}\n"
            f"mkvmerge        = {self.mkvmerge_path}\n"
            f"mkvpropedit     = {self.mkvpropedit_path}\n"
            f"ffprobe         = {self.ffprobe_path}\n"
            f"video           = name={self.video_name!r} lang={self.video_language} "
            f"default={self.video_default} forced={self.video_forced}\n"
            f"audio           = name={self.audio_name!r} lang={self.audio_language} "
            f"default={self.audio_default} forced={self.audio_forced}\n"
            f"persian sub     = name={self.subtitle_name!r} lang=fa "
            f"default={self.subtitle_default} forced={self.subtitle_forced}\n"
            f"english sub     = name={self.english_subtitle_name_sdh!r}/"
            f"{self.english_subtitle_name_non_sdh!r} lang=en "
            f"default={self.english_subtitle_default} forced={self.english_subtitle_forced}"
        )
