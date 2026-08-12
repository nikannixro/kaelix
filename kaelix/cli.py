"""Command-line interface and interactive configuration."""
from __future__ import annotations

import argparse
import difflib
import textwrap

from .config import Config
from .prompts.questions import (
    _panel,
    ask_confirm,
    prompt_audio_language,
    prompt_dry_run,
    prompt_english_subtitle_directory,
    prompt_output_directory,
    prompt_persian_subtitle_directory,
    prompt_source_directory,
)
from .selfmanage import (
    NOT_GIT,
    OFFLINE,
    UP_TO_DATE,
    UPDATE_AVAILABLE,
    UPDATED,
    app_dirs,
    check_update,
    derive_version,
    uninstall_kaelix,
    upgrade_kaelix,
)
from .services.orchestrator import BatchOrchestrator
from .utils.logger import get_logger, setup_logging
from .utils.validators import (
    ValidationError,
    validate_directory,
    validate_ffprobe_available,
    validate_language_code,
    validate_mkvtoolnix_available,
    validate_output_directory,
    validate_subtitle_directory,
)

log = get_logger(__name__)

USAGE = textwrap.dedent("""\
    Usage:
      kaelix [command] [options]

    Commands:
      run               Start Kaelix
      --help            Show this help message
      --version         Show installed version
      --upgrade         Update Kaelix to the latest GitHub version
      --check-update    Check for updates
      --uninstall       Remove Kaelix from this computer
""")

EXAMPLES = textwrap.dedent("""\
    Examples:
      kaelix
      kaelix --source ./in --output ./out --non-interactive
      kaelix --check-update
      kaelix --upgrade
""")


# --- Argument parser ---------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaelix",
        description="Batch-edit MKV track metadata, languages, flags, subtitles, and filenames.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument(
        "--source", "-s",
        help="Source directory containing .mkv files (interactive if omitted).",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory for processed files (created if missing).",
    )
    parser.add_argument(
        "--persian-subs",
        help="Directory containing external Persian/Farsi subtitle files (optional).",
    )
    parser.add_argument(
        "--english-subs",
        help="Directory containing external English subtitle files (optional).",
    )
    parser.add_argument(
        "--audio-lang",
        default="en",
        help="Default audio language code (default: en).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without writing any changes.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; rely on CLI flags only.",
    )
    parser.add_argument("--mkvmerge", help="Explicit path to the mkvmerge binary.")
    parser.add_argument("--mkvpropedit", help="Explicit path to the mkvpropedit binary.")
    parser.add_argument("--ffprobe", help="Explicit path to the ffprobe binary.")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show installed version.",
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Check for a newer version without installing it.",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Update Kaelix to the latest GitHub version.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove Kaelix from this computer.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential output.",
    )
    return parser


def _known_flags(parser: argparse.ArgumentParser) -> list[str]:
    return [opt for action in parser._actions for opt in action.option_strings]


def _reject(token: str, known: list[str]) -> int:
    """Print the unknown-command error (with a suggestion) and return exit code 2."""
    label = "option" if token.startswith("-") else "command"
    print(f"Error: Unknown {label} '{token}'")
    close = difflib.get_close_matches(token, known, n=1, cutoff=0.6)
    if close:
        print(f"Did you mean '{close[0]}'?")
    print()
    print(USAGE)
    print("Run 'kaelix --help' for more information.")
    return 2


def _screen_args(
    argv: list[str], parser: argparse.ArgumentParser
) -> tuple[list[str], int | None]:
    """Validate argv before argparse so bad input gets a friendly error.

    Returns (cleaned_argv, exit_code). A non-None exit code means stop.
    """
    known = _known_flags(parser)
    cleaned: list[str] = []
    for i, token in enumerate(argv):
        if token in ("run", "help"):
            # Bare verbs: `run` is the default action, `help` maps to --help.
            if token == "help":
                cleaned.append("--help")
            continue
        if token.startswith("-"):
            flag = token.split("=", 1)[0]
            if flag not in known:
                return cleaned, _reject(flag, known)
            cleaned.append(token)
            continue
        # A bare word is only valid as the value of the preceding option.
        if i > 0 and argv[i - 1].startswith("-") and argv[i - 1] in known:
            cleaned.append(token)
            continue
        return cleaned, _reject(token, known)
    return cleaned, None


# --- Self-management --------------------------------------------------------

def _handle_selfmanage(args: argparse.Namespace) -> int | None:
    """Run a self-management action. None means 'proceed to the app'."""
    if args.version:
        print(f"kaelix {derive_version() or 'unknown'}")
        return 0

    dirs = app_dirs()

    if args.uninstall:
        if not args.quiet and not ask_confirm(
            "Remove Kaelix and its install directory?", default=False
        ):
            print("Aborted.")
            return 0
        return uninstall_kaelix(dirs)

    if args.check_update:
        code, current, remote = check_update(dirs)
        if code == UPDATE_AVAILABLE:
            print(f"Update available: {current or 'unknown'} -> {remote}")
            print("Run 'kaelix --upgrade' to install it.")
            return 1
        if code == OFFLINE:
            print("Could not reach GitHub to check for updates.")
            return 2
        if not args.quiet:
            print(f"kaelix {current or 'unknown'} is up to date.")
        return 0

    if args.upgrade:
        code = upgrade_kaelix(dirs)
        if code == UPDATED:
            return 0
        if code == UP_TO_DATE:
            if not args.quiet:
                print("Already up to date.")
            return 0
        if code == OFFLINE:
            print("Could not reach GitHub to check for updates.")
        elif code == NOT_GIT:
            print(
                "This is a development checkout, not a Kaelix install. "
                "Use git to update it."
            )
        else:
            print("Upgrade failed. Your existing install was left in place.")
        return 2

    return None


# --- App run ----------------------------------------------------------------

def _run_app(args: argparse.Namespace) -> int:
    log_path = setup_logging()

    try:
        mkvmerge_path, mkvpropedit_path = validate_mkvtoolnix_available(
            args.mkvmerge, args.mkvpropedit
        )
        ffprobe_path = validate_ffprobe_available(args.ffprobe)
        config = (
            gather_config_from_args(args)
            if args.non_interactive
            else gather_config_interactive()
        )
    except ValidationError as exc:
        log.error(str(exc))
        return 2

    config.mkvmerge_path = mkvmerge_path
    config.mkvpropedit_path = mkvpropedit_path
    config.ffprobe_path = ffprobe_path

    log.info(f"Logging to: {log_path}")
    log.info(config.describe())

    if not config.dry_run and not args.non_interactive:
        if not ask_confirm("Proceed with processing?", default=True):
            log.info("Aborted by user.")
            return 0

    try:
        stats = BatchOrchestrator(config).run()
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        return 130

    return 0 if stats["failed"] == 0 else 1


# --- Config helpers ---------------------------------------------------------

def gather_config_interactive() -> Config:
    """Prompt the user for all configuration values."""
    _panel("Kaelix", title="Welcome")
    config = Config(
        source_dir=prompt_source_directory(),
        output_dir=prompt_output_directory(),
        persian_subtitle_dir=prompt_persian_subtitle_directory(),
        english_subtitle_dir=prompt_english_subtitle_directory(),
        audio_language=prompt_audio_language(),
        dry_run=prompt_dry_run(),
    )
    _panel(config.describe(), title="Configuration summary")
    return config


def gather_config_from_args(args: argparse.Namespace) -> Config:
    """Build a Config purely from CLI arguments (non-interactive)."""
    if not args.source or not args.output:
        raise ValidationError("--source and --output are required in non-interactive mode.")
    return Config(
        source_dir=validate_directory(args.source, "source directory"),
        output_dir=validate_output_directory(args.output, "output directory"),
        persian_subtitle_dir=validate_subtitle_directory(args.persian_subs),
        english_subtitle_dir=validate_subtitle_directory(args.english_subs),
        audio_language=validate_language_code(args.audio_lang),
        dry_run=args.dry_run,
        non_interactive=True,
    )


# --- Entry point ------------------------------------------------------------

def run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    cleaned, code = _screen_args(list(argv or []), parser)
    if code is not None:
        return code
    args = parser.parse_args(cleaned)
    rc = _handle_selfmanage(args)
    return rc if rc is not None else _run_app(args)
