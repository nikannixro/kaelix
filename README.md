<div align="center">

# Kaelix

**Batch MKV metadata editing, subtitle swapping, and release-style renaming.**

Built on [MKVToolNix](https://mkvtoolnix.download/) (`mkvmerge`, `mkvpropedit`).
Track names, languages, and default/forced flags are edited in place without
re-encoding; a remux happens only when the track layout actually has to change.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## Install

**Linux / macOS / WSL**

```bash
bash <(curl -Ls https://raw.githubusercontent.com/nikannixro/kaelix/main/install.sh)
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/nikannixro/kaelix/main/install.ps1 | iex
```

No administrator rights are needed. Kaelix installs into a private per-user
directory with its own virtual environment and adds a `kaelix` command to your
PATH. Re-running the installer updates an existing install.

Open a new terminal afterwards so the PATH change takes effect.

### Requirements

| Tool | Required | Notes |
|------|----------|-------|
| Python 3.12+ | yes | The installer finds it, or installs it via winget on Windows |
| git | yes | Used for install and `--upgrade` |
| MKVToolNix | yes, at runtime | `mkvmerge`, `mkvpropedit` |
| ffmpeg | optional | `ffprobe`, used only for 10-bit detection |

Missing runtime tools produce a warning, not a failed install. You can also
point Kaelix at them explicitly with `--mkvmerge`, `--mkvpropedit`, `--ffprobe`.

---

## Usage

```bash
kaelix
```

Prompts for the source folder, output folder, optional subtitle folders, audio
language, and whether to dry-run.

```bash
# Non-interactive
kaelix --source ./in --output ./out --non-interactive

# Preview without writing anything
kaelix --source ./in --output ./out --non-interactive --dry-run

# With external subtitles
kaelix --source ./in --output ./out \
       --persian-subs ./subs/fa --english-subs ./subs/en \
       --non-interactive
```

### Commands

| Command | Description | Exit code |
|---------|-------------|-----------|
| `kaelix` | Run (interactive, or with flags) | 0 ok, 1 some files failed, 2 bad input |
| `kaelix --help` | Full option list | 0 |
| `kaelix --version` | Installed version | 0 |
| `kaelix --check-update` | Check GitHub for a newer release | 0 current, 1 update available, 2 offline |
| `kaelix --upgrade` | Install the latest release | 0 ok, 2 failed |
| `kaelix --uninstall` | Remove Kaelix (asks first) | 0 |

`--check-update`'s exit codes make it usable from a script or cron job; add
`--quiet` to suppress the "up to date" line.

---

## What it does to a file

Originals are never modified. Each source file is copied to the output folder
(preserving the subfolder structure) and the copy is edited.

**Metadata applied**

| Track | Name | Language | Default | Forced |
|-------|------|----------|---------|--------|
| Video | `Video` | `en` | yes | no |
| Audio | `Audio` | chosen per run, or per file when several exist | yes | no |
| Subtitle, Persian | `Subtitle` | `fa` | yes | yes |
| Subtitle, English (SDH) | `English [SDH]` | `en` | no | no |
| Subtitle, English | `English` | `en` | no | no |
| Subtitle, other | `Subtitle` | unchanged | no | no |

Image/cover attachments are removed. The container title is set to the parsed
name without release tags.

**Renaming**

```
Movie:  MOVIE NAME (YEAR) [QUALITY] [SOURCE] [CODEC].mkv
Series: SERIES NAME - S00E00 [QUALITY] [SOURCE] [CODEC].mkv
```

Quality, source, and codec are read from the filename; the codec falls back to
the video track, and 10-bit is detected via `ffprobe` when the filename does not
say. Undetected fields default to `1080p`, `WEB-DL`, `x265` and are logged as
warnings.

A file whose target already exists in the output folder is skipped, so an
interrupted batch can be resumed by re-running the same command.

---

## External subtitles

Subtitle files are matched by exact stem against the container title.
`.srt`, `.ass`, `.ssa`, `.sub`, and `.vtt` are recognised.

| Kind | Filename |
|------|----------|
| Persian / generic | `MOVIE NAME (YEAR) [Subtitle].srt` |
| English | `MOVIE NAME (YEAR) [Subtitle] [english].srt` |
| English SDH | `MOVIE NAME (YEAR) [Subtitle] [english] [SDH].srt` |
| Series | `SERIES NAME - S00E00 [Subtitle].srt` |

When an external Persian or English subtitle is found, the matching embedded
track is replaced; subtitles in other languages are kept. If no external
subtitle matches, nothing is remuxed and existing tracks are only relabelled.

---

## Where things live

Nothing is written into the project directory.

| | Linux | macOS | Windows |
|---|---|---|---|
| App + venv + logs | `~/.local/share/kaelix/` | `~/Library/Application Support/kaelix/` | `%LOCALAPPDATA%\kaelix\` |
| `kaelix` command | `~/.local/bin/` | `~/.local/bin/` | `%LOCALAPPDATA%\Programs\kaelix\bin\` |

Each install owns a virtual environment at `<app dir>/venv`, so the system
Python is never touched. Run logs rotate under `<app dir>/logs`.

Set `KAELIX_APP_DIR` before installing or running to relocate all of it.

`--upgrade` fetches release tags, checks out the newest `vX.Y.Z`, and reinstalls
into the existing venv. If the new version fails to install, the previous commit
is restored and reinstalled.

---

## Development

```bash
git clone https://github.com/nikannixro/kaelix.git
cd kaelix
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ruff check kaelix/
python -m kaelix --help
```

`--upgrade` refuses to run on a development checkout; use git there.

---

## License

[MIT](LICENSE)
