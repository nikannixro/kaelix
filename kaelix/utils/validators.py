"""Input validation helpers."""
from __future__ import annotations

import shutil
from pathlib import Path

from .constants import (
    FFPROBE_BIN,
    MKVMERGE_BIN,
    MKVPROPEDIT_BIN,
)
from .logger import get_logger

log = get_logger(__name__)


class ValidationError(Exception):
    """Raised when user-supplied input is invalid."""


def resolve_binary(name: str, explicit_path: str | Path | None = None) -> Path:
    """Resolve a binary: an explicit path if given, else a PATH lookup."""
    if explicit_path is not None:
        p = Path(explicit_path).expanduser().resolve()
        if not p.is_file():
            raise ValidationError(f"Binary not found: {p}")
        return p
    found = shutil.which(name)
    if found:
        return Path(found)
    raise ValidationError(
        f"'{name}' not found on PATH. "
        f"Install it or pass an explicit path (e.g. --{name} '/path/to/{name}')."
    )


def validate_directory(path: str | Path, label: str = "directory") -> Path:
    """Ensure the given path is an existing directory."""
    p = Path(path).expanduser()
    if not p.exists():
        raise ValidationError(f"{label} does not exist: {p}")
    if not p.is_dir():
        raise ValidationError(f"{label} is not a directory: {p}")
    return p.resolve()


def validate_output_directory(path: str | Path, label: str = "output directory") -> Path:
    """Validate or create an output directory."""
    p = Path(path).expanduser()
    if p.exists():
        if not p.is_dir():
            raise ValidationError(f"{label} exists but is not a directory: {p}")
        return p.resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValidationError(f"Could not create {label} {p}: {exc}") from exc
    log.info(f"Created {label}: {p}")
    return p.resolve()


def validate_subtitle_directory(path: str | Path | None) -> Path | None:
    """Validate an optional subtitle folder. Empty input means 'skip'."""
    if path is None or not str(path).strip():
        return None
    return validate_directory(path, "subtitle directory")


def validate_language_code(code: str, default: str = "en") -> str:
    """Normalize a 2- or 3-letter language code."""
    code = (code or "").strip().lower()
    if not code:
        return default
    if not code.isalpha():
        raise ValidationError(f"Invalid language code (letters only): {code!r}")
    if not 2 <= len(code) <= 3:
        raise ValidationError(f"Language code must be 2 or 3 letters: {code!r}")
    return code


def validate_mkvtoolnix_available(
    mkvmerge_path: str | Path | None = None,
    mkvpropedit_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Resolve both MKVToolNix binaries. Returns (mkvmerge, mkvpropedit)."""
    return (
        resolve_binary(MKVMERGE_BIN, mkvmerge_path),
        resolve_binary(MKVPROPEDIT_BIN, mkvpropedit_path),
    )


def validate_ffprobe_available(ffprobe_path: str | Path | None = None) -> Path:
    """Resolve ffprobe."""
    return resolve_binary(FFPROBE_BIN, ffprobe_path)
