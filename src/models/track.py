"""Track data model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..utils.constants import (
    ENGLISH_LANGUAGE_CODES,
    PERSIAN_LANGUAGE_CODES,
    TRACK_TYPE_AUDIO,
    TRACK_TYPE_SUBTITLE,
    TRACK_TYPE_VIDEO,
)


@dataclass
class Track:
    """Represents a single track inside an MKV file."""

    id: int
    type: str
    codec: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Raw property accessors
    # ------------------------------------------------------------------
    @property
    def raw_name(self) -> str:
        return self.properties.get("track_name", "") or ""

    @property
    def raw_language_ietf(self) -> str:
        return self.properties.get("language_ietf", "") or ""

    @property
    def raw_language_legacy(self) -> str:
        return self.properties.get("language", "") or ""

    @property
    def language(self) -> str:
        """Effective language code, preferring IETF over legacy."""
        return self.raw_language_ietf or self.raw_language_legacy or "und"

    @property
    def is_default(self) -> bool:
        return bool(self.properties.get("default_track", False))

    @property
    def is_forced(self) -> bool:
        return bool(self.properties.get("forced_track", False))

    @property
    def uid(self) -> Optional[int]:
        return self.properties.get("uid")

    @property
    def audio_channels(self) -> Optional[int]:
        return self.properties.get("audio_channels")

    @property
    def audio_sampling_frequency(self) -> Optional[int]:
        return self.properties.get("audio_sampling_frequency")

    @property
    def pixel_dimensions(self) -> Optional[str]:
        return self.properties.get("pixel_dimensions")

    @property
    def display_dimensions(self) -> Optional[str]:
        return self.properties.get("display_dimensions")

    # ------------------------------------------------------------------
    # Type checks
    # ------------------------------------------------------------------
    @property
    def is_video(self) -> bool:
        return self.type == TRACK_TYPE_VIDEO

    @property
    def is_audio(self) -> bool:
        return self.type == TRACK_TYPE_AUDIO

    @property
    def is_subtitle(self) -> bool:
        return self.type == TRACK_TYPE_SUBTITLE

    # ------------------------------------------------------------------
    # Language helpers
    # ------------------------------------------------------------------
    @property
    def is_english(self) -> bool:
        lang = self.language.lower()
        return lang in ENGLISH_LANGUAGE_CODES or lang.startswith("en")

    @property
    def is_persian(self) -> bool:
        lang = self.language.lower()
        return lang in PERSIAN_LANGUAGE_CODES or lang.startswith("fa")

    def describe(self) -> str:
        """Human-readable one-line description."""
        bits = [f"#{self.id}", self.type]
        if self.codec:
            bits.append(self.codec)
        if self.language:
            bits.append(f"lang={self.language}")
        if self.raw_name:
            bits.append(f"name={self.raw_name!r}")
        flags = []
        if self.is_default:
            flags.append("default")
        if self.is_forced:
            flags.append("forced")
        if flags:
            bits.append("[" + ",".join(flags) + "]")
        return " ".join(bits)
