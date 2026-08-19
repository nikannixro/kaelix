<div align="center">

# Kaelix

**Batch MKV metadata editor, subtitle swapper, and release-style renamer.**

Normalise a whole media library in one pass — track names, languages, and
default/forced flags — without re-encoding a single frame.

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](#requirements)

</div>

---

## Features

- **Lossless** — `mkvpropedit` edits headers in place; a remux (`mkvmerge`) happens only when the track layout must change, and always stream-copies.
- **Non-destructive** — originals are read-only; every edit happens on the copy in your output directory.
- **Batch and recursive** — walks a whole tree, mirroring its structure in the output.
- **Metadata normalisation** — consistent names, languages, and default/forced flags for video, audio, and subtitles.
- **Subtitle policy** — keeps English and Persian/Farsi only; every other subtitle language is removed.
- **External subtitles** — swaps embedded Persian/English tracks for your own `.srt`/`.ass` files, with automatic `[SDH]` naming.
- **Release-style renaming** — title, year or `S00E00`, quality, source, and codec parsed from the filename, with `ffprobe` as a fallback. Source tokens are normalized to their canonical form: `WEBRip`/`WEB-Rip`/`WEBRip-` → `WEB-DL`, `BluRip`/`Blu-Ray`/`BR-Rip`/`BDRip` → `BluRay`.
- **Resumable** — files whose target already exists are skipped, so an interrupted batch resumes by re-running.
- **Self-managing** — `--upgrade` with automatic rollback, `--uninstall` that removes everything.

---

## Requirements

| Tool | Required | Purpose |
|------|:--------:|---------|
| Python 3.12+ | yes | Runtime (the installer finds it, or installs it via winget on Windows) |
| git | yes | Used by the installer and `--upgrade` |
| [MKVToolNix](https://mkvtoolnix.download/) | yes | `mkvmerge` and `mkvpropedit` |
| [FFmpeg](https://ffmpeg.org/) | optional | `ffprobe`, for 10-bit detection only |

Missing runtime tools produce a warning, not a failed install — Kaelix reports
them on first run, and `--mkvmerge` / `--mkvpropedit` / `--ffprobe` accept
explicit paths.

```bash
sudo apt-get install -y mkvtoolnix ffmpeg     # Debian/Ubuntu
brew install mkvtoolnix ffmpeg                # macOS
```

```powershell
winget install MoritzBunkus.MKVToolNix Gyan.FFmpeg   # Windows
```

---

## Installation

**Linux / macOS / WSL**

```bash
bash <(curl -Ls https://raw.githubusercontent.com/nikannixro/kaelix/main/install.sh)
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/nikannixro/kaelix/main/install.ps1 | iex
```

No admin rights needed. The installer clones the repo, creates a private
virtualenv, and puts a `kaelix` launcher on your PATH — your system Python is
never touched. Re-run it to update an existing install. **Open a new terminal
afterwards** so the PATH change applies.

<details>
<summary>Installer options and paths</summary>

```bash
./install.sh              # install or update
./install.sh --uninstall
```

```powershell
.\install.ps1                     # install or update
.\install.ps1 -SkipDependencies   # never invoke winget
.\install.ps1 -Quiet              # no prompts
.\install.ps1 -Uninstall
```

| | Linux | macOS | Windows |
|---|---|---|---|
| App, virtualenv, logs | `~/.local/share/kaelix/` | `~/Library/Application Support/kaelix/` | `%LOCALAPPDATA%\kaelix\` |
| `kaelix` launcher | `~/.local/bin/` | `~/.local/bin/` | `%LOCALAPPDATA%\Programs\kaelix\bin\` |

`KAELIX_APP_DIR` overrides the install directory. `--uninstall` removes all of
the above, including the PATH entry.

For a development checkout, see [CONTRIBUTING.md](CONTRIBUTING.md#development-environment-setup).

</details>

---

## Quick start

```bash
kaelix
```

Kaelix asks six questions — source, output, optional subtitle directories,
audio language, dry-run — shows the resolved configuration, and waits for
confirmation before touching anything.

Or skip the prompts entirely. **Try `--dry-run` first**: it logs every planned
change and writes nothing.

```bash
kaelix --source ./inbox --output ./library --non-interactive --dry-run
```

```
INFO  Found 2 MKV file(s) under /home/you/media/inbox
INFO  Target: Test Movie (2021) [1080p] [WEB-DL] [x265 10 Bit].mkv
INFO    tracks: 1V/2A/4S  attachments: 0
INFO    dropping 2 non-English/Persian subtitle(s): #5 (spa), #6 (jpn)
INFO  [DRY-RUN]   audio: name='Audio' lang=en default=True forced=False
╭──────────────── Batch summary ────────────────╮
│ Total: 2   OK: 2   Failed: 0   Skipped: 0     │
╰───────────────────────────────────────────────╯
```

Happy with the plan? Drop `--dry-run`.

---

## Usage

```bash
# Fully scripted
kaelix --source ./inbox --output ./library --non-interactive

# With your own subtitle files
kaelix --source ./inbox --output ./library \
       --persian-subs ./subs/fa --english-subs ./subs/en --non-interactive

# Japanese audio
kaelix --source ./anime --output ./library --audio-lang ja --non-interactive
```

### CLI reference

| Command | Exit codes |
|---------|------------|
| `kaelix` / `kaelix run` | `0` all ok · `1` some files failed · `2` bad input · `130` interrupted |
| `kaelix --version` | `0` |
| `kaelix --upgrade` | `0` ok or already current · `2` failed |
| `kaelix --uninstall` | `0` (asks first; `--quiet` skips the prompt) |

| Option | Description |
|--------|-------------|
| `-s`, `--source PATH` | Source directory containing `.mkv` files |
| `-o`, `--output PATH` | Output directory (created if missing) |
| `--persian-subs PATH` | External Persian/Farsi subtitle directory |
| `--english-subs PATH` | External English subtitle directory |
| `--audio-lang CODE` | Default audio language, 2–3 letters (default `en`) |
| `--dry-run` | Simulate; write nothing |
| `--non-interactive` | Never prompt; requires `--source` and `--output` |
| `--mkvmerge`, `--mkvpropedit`, `--ffprobe` | Explicit binary paths |
| `--quiet` | Suppress non-essential output |

`kaelix --help` prints the full list.

---

## What Kaelix writes

Metadata rules applied to every file:

| Track | Name | Language | Default | Forced |
|-------|------|----------|:-------:|:------:|
| Video | `Video` | `en` | yes | no |
| Audio | `Audio` | your choice | yes | no |
| Subtitle — Persian/Farsi | `Subtitle` | `fa` | yes | yes |
| Subtitle — English | `English` / `English [SDH]` | `en` | no | no |
| Subtitle — anything else | **removed** | — | — | — |

Output filenames:

```
Movie:  MOVIE NAME (YEAR) [QUALITY] [SOURCE] [CODEC].mkv
Series: SERIES NAME - S00E00 [QUALITY] [SOURCE] [CODEC].mkv
```

Quality, source, and codec are read from the input filename, falling back to
`1080p` / `WEB-DL` / the video track. Every fallback is logged as a warning.

External subtitles are matched by exact stem against the container title:

```
subs/fa/Test Movie (2021) [Subtitle].srt
subs/en/Test Movie (2021) [Subtitle] [english] [SDH].srt
```

The metadata rules live as dataclass defaults in
[`src/config.py`](src/config.py) and the parsing tables in
[`src/utils/constants.py`](src/utils/constants.py) — see
[CATALOG.md](CATALOG.md#configuration-reference) for the full set.

---

## Documentation

| | |
|---|---|
| [CATALOG.md](CATALOG.md) | Module-by-module map of the codebase, execution flow, technical reference |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, conventions, safety invariants, PR process |

Runtime logs live in `<app dir>/logs/`; the active path is printed at the start
of every run.

## Security

No telemetry, no credentials, no runtime network access — the only outbound
requests are to GitHub, and only when you run `--upgrade`. External tools are
invoked with argument lists, never shell strings. Everything installs under
your user account.

Please report security issues via a
[private advisory](https://github.com/nikannixro/kaelix/security/advisories/new)
rather than a public issue.

## License

[MIT](LICENSE) © N I K A N

Built on [MKVToolNix](https://mkvtoolnix.download/) by Moritz Bunkus,
[FFmpeg](https://ffmpeg.org/), and [Rich](https://github.com/Textualize/rich).
