"""Logging setup: rich console output plus a rotating file handler."""
from __future__ import annotations

import logging
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
    """Logs live next to the install (or the repo, for a dev checkout)."""
    from ..selfmanage import app_dirs

    return app_dirs()["logs"]


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


def setup_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> Path:
    """Configure root logging once and return the active log file path."""
    global _CONFIGURED, _LOG_PATH
    if _CONFIGURED and _LOG_PATH is not None:
        return _LOG_PATH

    handlers: list[logging.Handler] = []
    if console:
        if _HAS_RICH:
            handlers.append(RichHandler(rich_tracebacks=True, show_path=False))
        else:
            stream = logging.StreamHandler()
            stream.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            handlers.append(stream)

    file_handler, log_path = _file_handler(log_dir or _default_log_dir())
    handlers.append(file_handler)

    logging.basicConfig(
        level=level,
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
