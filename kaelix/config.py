"""Run configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .utils.constants import (
    DEFAULT_AUDIO_NAME,
    DEFAULT_SUBTITLE_NAME,
)


@dataclass
class Config:
    """Resolved configuration for a single batch run."""

    source_dir: Path
    output_dir: Path
    persian_subtitle_dir: Path | None = None
    english_subtitle_dir: Path | None = None
    audio_language: str = "en"
    dry_run: bool = False
    non_interactive: bool = False

    # Binary paths, resolved during validation.
    mkvmerge_path: Path | None = None
    mkvpropedit_path: Path | None = None
    ffprobe_path: Path | None = None

    # Metadata rules.
    audio_name: str = DEFAULT_AUDIO_NAME
    audio_default: bool = True
    audio_forced: bool = False

    subtitle_name: str = DEFAULT_SUBTITLE_NAME
    subtitle_default: bool = True   # Persian subtitle
    subtitle_forced: bool = True    # Persian subtitle
    english_subtitle_default: bool = False
    english_subtitle_forced: bool = False
    english_subtitle_name_sdh: str = "English [SDH]"
    english_subtitle_name_non_sdh: str = "English"

    def describe(self) -> str:
        rows = [
            ("source", self.source_dir),
            ("output", self.output_dir),
            ("persian subs", self.persian_subtitle_dir),
            ("english subs", self.english_subtitle_dir),
            ("audio lang", self.audio_language),
            ("dry-run", self.dry_run),
            ("non-interactive", self.non_interactive),
            ("mkvmerge", self.mkvmerge_path),
            ("mkvpropedit", self.mkvpropedit_path),
            ("ffprobe", self.ffprobe_path),
            (
                "audio",
                f"name={self.audio_name!r} lang={self.audio_language} "
                f"default={self.audio_default} forced={self.audio_forced}",
            ),
            (
                "persian sub",
                f"name={self.subtitle_name!r} lang=fa "
                f"default={self.subtitle_default} forced={self.subtitle_forced}",
            ),
            (
                "english sub",
                f"name={self.english_subtitle_name_sdh!r}/"
                f"{self.english_subtitle_name_non_sdh!r} lang=en "
                f"default={self.english_subtitle_default} "
                f"forced={self.english_subtitle_forced}",
            ),
        ]
        return "\n".join(f"{label:<16}= {value}" for label, value in rows)
