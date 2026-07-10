"""Interactive prompts for configuration and per-file decisions."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

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
except Exception:
    _HAS_RICH = False
    _console = None


def _strip_rich_tags(msg: str) -> str:
    """Remove rich markup tags so plain-text output stays clean when rich is unavailable."""
    return _RICH_TAG_RE.sub("", msg)


def _print(msg: str = "") -> None:
    if _HAS_RICH:
        _console.print(msg)
    else:
        print(_strip_rich_tags(msg))


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
    raw = input(f"{label}{suffix}: ").strip()
    return raw or default


def ask_confirm(label: str, default: bool = False) -> bool:
    if _HAS_RICH:
        return Confirm.ask(label, default=default)
    yn = "Y/n" if default else "y/N"
    raw = input(f"{label} [{yn}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


# ---------------------------------------------------------------------------
# Batch configuration prompts
# ---------------------------------------------------------------------------
def prompt_source_directory() -> Path:
    while True:
        try:
            raw = ask_string("Source directory (contains your .mkv files)")
            return validate_directory(raw, "source directory")
        except ValidationError as e:
            _print(f"[red]{e}[/red]")


def prompt_output_directory() -> Path:
    while True:
        try:
            raw = ask_string("Output directory (created if it does not exist)")
            return validate_output_directory(raw, "output directory")
        except ValidationError as e:
            _print(f"[red]{e}[/red]")


def prompt_persian_subtitle_directory() -> Optional[Path]:
    raw = ask_string(
        "External PERSIAN/FARSI subtitle directory (leave empty to skip)",
        default="",
    )
    try:
        return validate_subtitle_directory(raw if raw.strip() else None)
    except ValidationError as e:
        _print(f"[red]{e}[/red]")
        return prompt_persian_subtitle_directory()


def prompt_english_subtitle_directory() -> Optional[Path]:
    raw = ask_string(
        "External ENGLISH subtitle directory (leave empty to skip)",
        default="",
    )
    try:
        return validate_subtitle_directory(raw if raw.strip() else None)
    except ValidationError as e:
        _print(f"[red]{e}[/red]")
        return prompt_english_subtitle_directory()


def prompt_audio_language(default: str = "en") -> str:
    while True:
        try:
            raw = ask_string("Default AUDIO language code", default=default)
            return validate_language_code(raw, default)
        except ValidationError as e:
            _print(f"[red]{e}[/red]")


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
        f"Total:  {total}\n"
        f"OK:     {success}\n"
        f"Failed: {failed}\n"
        f"Skipped: {skipped}",
        title="Batch summary",
    )
