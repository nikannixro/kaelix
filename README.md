<div align="center">

# Kaelix

**Automated MKV metadata editing, track renaming, and batch renaming tool.**

Built on top of **MKVToolNix** command-line tools (`mkvmerge`, `mkvpropedit`),
it edits track names, languages, default/forced flags, swaps external subtitle
tracks, and renames files to a consistent release-style naming convention.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

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

### 1. Install

**Linux / WSL / macOS:**

```bash
bash <(curl -Ls https://kaelix.pages.dev/install.sh)
```

**Windows (PowerShell):**

```powershell
irm https://kaelix.pages.dev/install.ps1 | iex
```

> **Note:** The Windows installer requires Administrator (for system
> dependencies and the global launcher). You'll be prompted to elevate.

### 2. Run

```bash
kaelix
```

The installer creates a global `kaelix` command. Open a new terminal after
installation if `kaelix` isn't found immediately.

---

## Commands

| Command | Description |
|---------|-------------|
| `kaelix` | Run normally (interactive or with CLI flags) |
| `kaelix --help` | Show help with examples |
| `kaelix --version` | Show installed version |
| `kaelix --check-update` | Check for a newer version (exit 0 = up to date, 1 = update available, 2 = error) |
| `kaelix --upgrade` | Update Kaelix to the latest GitHub release |
| `kaelix --uninstall` | Remove Kaelix completely |

### Examples

```bash
# Run interactively
kaelix

# Non-interactive batch
kaelix --source /path/to/mkvs --output /path/to/out --non-interactive

# Check for updates quietly (good for cron)
kaelix --check-update --quiet

# Update to latest
kaelix --upgrade

# Uninstall
kaelix --uninstall
```

---

## How Updates Work

- Kaelix installs into a private, per-user directory:
  - Linux/macOS: `~/.local/share/kaelix/`
  - Windows: `%LOCALAPPDATA%\kaelix\`
- Each install has its own virtual environment — no system Python pollution.
- `kaelix --upgrade` fetches the latest GitHub release tag (`vX.Y.Z`),
  checks it out, reinstalls into the existing venv, and rolls back
  automatically if anything fails.
- `kaelix --check-update` is safe for cron; combine with `--quiet` to
  only get an exit code.

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

## License

[MIT](LICENSE)