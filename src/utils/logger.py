"""Logging setup using rich for console output and a rotating file handler."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

try:
    from rich.logging import RichHandler
    _HAS_RICH = True
except Exception:
    _HAS_RICH = False

_CONFIGURED = False


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
    console: bool = True,
) -> Path:
    """Configure root logging and return the log file path."""
    global _CONFIGURED
    if _CONFIGURED:
        return _log_file_path(log_dir)

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = _log_file_path(log_dir)

    handlers: list[logging.Handler] = []

    if console:
        if _HAS_RICH:
            handlers.append(RichHandler(rich_tracebacks=True, show_path=False))
        else:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            handlers.append(stream_handler)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )
    _CONFIGURED = True
    return log_path


def _log_file_path(log_dir: Path) -> Path:
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(log_dir) / f"movies_organizer_{stamp}.log"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name if name else "movies_metadata_organizer")
