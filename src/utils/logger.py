"""Logging setup: rich console output plus a rotating file handler."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from rich.logging import RichHandler
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

_CONFIGURED = False
_LOG_PATH: Path | None = None


def _default_log_dir() -> Path:
    """OS-appropriate log directory, mirroring selfmanage.app_dirs without importing it."""
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / "kaelix" / "logs"


def _log_file_path(log_dir: Path) -> Path:
    return Path(log_dir) / f"kaelix-{datetime.now():%Y-%m-%d-%H%M}.log"


def _file_handler(log_dir: Path) -> tuple[RotatingFileHandler, Path]:
    """Rotating handler in `log_dir`, falling back to ~/.kaelix/logs."""
    for candidate in (Path(log_dir), Path.home() / ".kaelix" / "logs"):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            path = _log_file_path(candidate)
            handler = RotatingFileHandler(
                path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
            )
        except OSError:
            continue
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        return handler, path
    raise OSError("Could not open any log file location.")


def setup_logging() -> Path:
    """Configure root logging once (INFO, console + rotating file) and return the log path."""
    global _CONFIGURED, _LOG_PATH
    if _CONFIGURED and _LOG_PATH is not None:
        return _LOG_PATH

    handlers: list[logging.Handler] = []
    if _HAS_RICH:
        handlers.append(RichHandler(rich_tracebacks=True, show_path=False))
    else:
        stream = logging.StreamHandler()
        stream.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        handlers.append(stream)

    file_handler, log_path = _file_handler(_default_log_dir())
    handlers.append(file_handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )
    _CONFIGURED = True
    _LOG_PATH = log_path
    return log_path


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "kaelix")
