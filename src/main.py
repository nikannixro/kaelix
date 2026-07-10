"""Entry point for Movies Metadata Organizer."""
from __future__ import annotations

import sys

from .cli import run


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
