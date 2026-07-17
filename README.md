<div align="center">

# Kaelix

**Automated MKV metadata editing, track renaming, and batch renaming tool.**

Built on top of **MKVToolNix** command-line tools (`mkvmerge`, `mkvpropedit`),
it edits track names, languages, default/forced flags, swaps external subtitle
tracks, and renames files to a consistent release-style naming convention.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## Features

- **Non-destructive metadata edits** via `mkvpropedit` (no remuxing, no
  re-encoding, no quality loss) for track names, languages, and flags.
- **Subtitle replacement / removal** via `mkvmerge` only when the track
  structure must change.
- **Automatic filename parsing** into movie/series, year, season/episode,
  quality, source type, and codec.
- **Consistent renaming** to your templates:
  - Movie: `MOVIE NAME (YEAR) [QUALITY] [TYPE] [CODEC].mkv`
  - Series: `SERIES NAME - S00E00 [QUALITY] [TYPE] [CODEC].mkv`
- **External subtitle matching** by exact target name
  (`<TARGET> - [Subtitle].srt/.ass`).
- **Hybrid interactivity**: batch defaults applied automatically, with per-file
  prompts only when multiple audio/subtitle tracks are detected.
- **Original files are never touched** — output goes to a separate folder while
  preserving the source folder tree.
- **Dry-run mode** for safe previewing.
- **Detailed rotating logs** for every run.

---

## Quick Start

### Linux / WSL / macOS

```bash
bash <(curl -Ls https://raw.githubusercontent.com/nikannixro/kaelix/main/start.sh)
```

### Windows

Open **PowerShell** and run:

```powershell
irm https://raw.githubusercontent.com/nikannixro/kaelix/main/start.ps1 | iex
```

This installs all dependencies, sets up the repository, and launches the application automatically.

---

## Supported Platforms

| Platform | Package Manager | Status |
|----------|----------------|--------|
| Ubuntu | apt | Supported |
| Debian | apt | Supported |
| Linux Mint | apt | Supported |
| Arch Linux | pacman | Supported |
| WSL | Same as underlying distro | Supported |
| macOS | Homebrew | Supported |
| Windows | winget | Supported |

---

## Metadata Rules Applied

| Track | Name | Language | Default | Forced |
|-------|------|----------|---------|--------|
| Video | `Video` | `en` | yes | no |
| Audio | `Audio` | (asked) | yes | no |
| Subtitle (Persian/Farsi) | `Subtitle` | `fa` | yes | yes |
| Subtitle (English, SDH) | `English [SDH]` | `en` | no | no |
| Subtitle (English, non-SDH) | `English` | `en` | no | no |

---

## Subtitle Replacement

You can provide **two** optional external subtitle directories:
one for Persian/Farsi and one for English.

**Persian / generic subtitle files:**
- Movies: `MOVIE NAME (YEAR) [Subtitle].srt`
- Series: `SERIES NAME - S00E00 [Subtitle].srt`

**English subtitle files:**
- Movies (non-SDH): `MOVIE NAME (YEAR) [Subtitle] [english].srt`
- Movies (SDH): `MOVIE NAME (YEAR) [Subtitle] [english] [SDH].srt`
- Series (non-SDH): `SERIES NAME - S00E00 [Subtitle] [english].srt`
- Series (SDH): `SERIES NAME - S00E00 [Subtitle] [english] [SDH].srt`

---

## Project Structure

```
kaelix/
├── start.sh          # Unix/macOS installer and launcher
├── start.ps1         # Windows installer and launcher
├── src/
│   ├── main.py       # Entry point
│   ├── cli.py        # CLI argument parsing + interactive prompts
│   ├── config.py     # Run configuration dataclass
│   ├── models/       # Track, MediaFile data models
│   ├── services/     # identifier, metadata_editor, remuxer,
│   │                 # renamer, subtitle_matcher, orchestrator
│   ├── prompts/      # Interactive question helpers
│   └── utils/        # Constants, logger, validators
├── logs/             # Rotating log files
├── pyproject.toml    # Project metadata
└── requirements.txt
```

---

## License

[MIT](LICENSE)
