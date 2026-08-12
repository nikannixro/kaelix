"""Track data model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils.constants import (
    ENGLISH_LANGUAGE_CODES,
    PERSIAN_LANGUAGE_CODES,
    TRACK_TYPE_AUDIO,
    TRACK_TYPE_SUBTITLE,
    TRACK_TYPE_VIDEO,
    UNKNOWN_LANGUAGE,
)


@dataclass
class Track:
    """One track inside an MKV file, as reported by mkvmerge."""

    id: int
    type: str
    codec: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def raw_name(self) -> str:
        return self.properties.get("track_name", "") or ""

    @property
    def language(self) -> str:
        """Effective language code, preferring IETF over the legacy field."""
        return (
            self.properties.get("language_ietf")
            or self.properties.get("language")
            or UNKNOWN_LANGUAGE
        )

    @property
    def is_default(self) -> bool:
        return bool(self.properties.get("default_track", False))

    @property
    def is_forced(self) -> bool:
        return bool(self.properties.get("forced_track", False))

    @property
    def is_video(self) -> bool:
        return self.type == TRACK_TYPE_VIDEO

    @property
    def is_audio(self) -> bool:
        return self.type == TRACK_TYPE_AUDIO

    @property
    def is_subtitle(self) -> bool:
        return self.type == TRACK_TYPE_SUBTITLE

    @property
    def is_english(self) -> bool:
        lang = self.language.lower()
        return lang in ENGLISH_LANGUAGE_CODES or lang.startswith("en")

    @property
    def is_persian(self) -> bool:
        lang = self.language.lower()
        return lang in PERSIAN_LANGUAGE_CODES or lang.startswith("fa")
