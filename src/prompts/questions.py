"""Interactive prompts for configuration and per-file decisions."""
from __future__ import annotations

import re
from pathlib import Path

from ..utils.logger import get_logger
from ..utils.validators import (
    ValidationError,
    validate_directory,
    validate_language_code,
    validate_output_directory,
    validate_subtitle_directory,
)

log = get_logger(__name__)

_RICH_TAG_RE = re.compile(r"\[/?[a-zA-Z0-9 ]+\]")

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt

    _console = Console()
    _HAS_RICH = True
except ImportError:  # rich is a declared dependency; degrade if absent anyway
    _HAS_RICH = False
    _console = None


def _print(msg: str = "") -> None:
    if _HAS_RICH:
        _console.print(msg)
    else:
        print(_RICH_TAG_RE.sub("", msg))


def _panel(msg: str, title: str = "") -> None:
    if _HAS_RICH:
        _console.print(Panel(msg, title=title, border_style="cyan"))
    else:
        print(f"=== {title} ===" if title else "===")
        print(msg)


# ---------------------------------------------------------------------------
# Generic input helpers
# ---------------------------------------------------------------------------

def ask_string(label: str, default: str = "") -> str:
    if _HAS_RICH:
        return Prompt.ask(label, default=default)
    suffix = f" [{default}]" if default else ""
    return input(f"{label}{suffix}: ").strip() or default


def ask_confirm(label: str, default: bool = False) -> bool:
    if _HAS_RICH:
        return Confirm.ask(label, default=default)
    raw = input(f"{label} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not raw else raw in ("y", "yes")


def _ask_until_valid(label: str, validate, default: str = ""):
    """Re-prompt until `validate` accepts the input."""
    while True:
        try:
            return validate(ask_string(label, default=default))
        except ValidationError as exc:
            _print(f"[red]{exc}[/red]")


# ---------------------------------------------------------------------------
# Batch configuration prompts
# ---------------------------------------------------------------------------

def prompt_source_directory() -> Path:
    return _ask_until_valid(
        "Source directory (contains your .mkv files)",
        lambda raw: validate_directory(raw, "source directory"),
    )


def prompt_output_directory() -> Path:
    return _ask_until_valid(
        "Output directory (created if it does not exist)",
        lambda raw: validate_output_directory(raw, "output directory"),
    )


def prompt_persian_subtitle_directory() -> Path | None:
    return _ask_until_valid(
        "External PERSIAN/FARSI subtitle directory (leave empty to skip)",
        validate_subtitle_directory,
    )


def prompt_english_subtitle_directory() -> Path | None:
    return _ask_until_valid(
        "External ENGLISH subtitle directory (leave empty to skip)",
        validate_subtitle_directory,
    )


def prompt_audio_language(default: str = "en") -> str:
    return _ask_until_valid(
        "Default AUDIO language code",
        lambda raw: validate_language_code(raw, default),
        default=default,
    )


def prompt_dry_run() -> bool:
    return ask_confirm("Run in DRY-RUN mode (no changes written)?", default=False)


# ---------------------------------------------------------------------------
# Per-file prompts (hybrid mode)
# ---------------------------------------------------------------------------

def prompt_audio_language_for_file(file_name: str, default: str) -> str:
    _panel(f"File: {file_name}", title="Multiple audio tracks detected")
    return prompt_audio_language(default)


def confirm_continue_after_error(file_name: str, error: str) -> bool:
    _panel(f"FAILED: {file_name}\n{error}", title="Error processing file")
    return ask_confirm("Continue with the next file?", default=True)


def show_summary(total: int, success: int, failed: int, skipped: int) -> None:
    _panel(
        f"Total:   {total}\n"
        f"OK:      {success}\n"
        f"Failed:  {failed}\n"
        f"Skipped: {skipped}",
        title="Batch summary",
    )
