<div align="center">

# Kaelix

**Batch MKV metadata editor, subtitle swapper, and release-style renamer.**

Normalise a whole media library in one pass — track names, languages, and
default/forced flags — without re-encoding a single frame.

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](#requirements)

[Install](#installation) · [Quick start](#quick-start) · [CLI reference](#cli-reference) · [Troubleshooting](#troubleshooting) · [Contributing](CONTRIBUTING.md) · [Catalog](CATALOG.md)

</div>

---

## What it does

Media files collected from different sources carry inconsistent metadata: one
file labels its audio `AAC 5.1 [Release Group]`, the next leaves it blank, a
third marks an English subtitle as *forced*. Players then pick the wrong track,
and libraries display the wrong names.

Kaelix walks a folder of `.mkv` files and, for each one:

1. **Reads** the real track layout with `mkvmerge --identify`.
2. **Parses** the filename into title, year or season/episode, quality, source, and codec.
3. **Rewrites** track names, languages, and default/forced flags to one consistent rule set.
4. **Replaces** embedded Persian or English subtitles with external `.srt`/`.ass` files when you supply them.
5. **Renames** the output to a consistent release-style filename.

Two guarantees shape the design:

- **Your originals are never touched.** Every file is copied to an output folder first; all edits happen on the copy.
- **No re-encoding.** Metadata is written with `mkvpropedit`, which edits headers in place. A remux (`mkvmerge`) happens *only* when the track layout must change — i.e. when you supply external subtitles. Video and audio streams are copied bit-for-bit either way.

---

## Features

| | |
|---|---|
| **Lossless metadata edits** | `mkvpropedit` rewrites headers in place — no quality loss, no long encode |
| **Batch, recursive** | Processes an entire tree; the output mirrors your source folder structure |
| **Filename parsing** | Title, year, season/episode, quality, source type, and codec from the filename |
| **Codec fallback** | Reads the codec from the video track when the filename omits it; detects 10-bit via `ffprobe` |
| **Subtitle replacement** | Swaps embedded Persian/English subtitles for external files |
| **Language filtering** | Subtitles that are neither English nor Persian are removed entirely |
| **SDH detection** | External `[SDH]` subtitles are named `English [SDH]` automatically |
| **Attachment cleanup** | Strips `image/*` cover attachments |
| **Hybrid prompting** | Prompts per file only when a choice is genuinely ambiguous (multiple audio tracks) |
| **Dry run** | `--dry-run` logs every planned change without writing anything |
| **Resumable** | A file whose target already exists is skipped, so an interrupted batch resumes by re-running |
| **Self-managing** | `--check-update`, `--upgrade` with automatic rollback, `--uninstall` |
| **Clean footprint** | App, virtualenv, and logs live in one per-user directory; your project folders stay clean |

---

## Requirements

| Tool | Required | Purpose |
|------|:--------:|---------|
| **Python 3.12+** | yes | Runtime. The installer locates it, or installs it via winget on Windows |
| **git** | yes | Used by the installer and by `--upgrade` |
| **MKVToolNix** | yes, at runtime | `mkvmerge` (identify, remux) and `mkvpropedit` (metadata) |
| **ffmpeg** | optional | `ffprobe`, used only to detect 10-bit video |

The single Python dependency is [`rich`](https://github.com/Textualize/rich) for
console output; everything else is standard library.

Missing runtime tools produce a warning, not a failed install. Kaelix reports
them clearly on first run, and you can always point it at a specific binary with
`--mkvmerge`, `--mkvpropedit`, or `--ffprobe`.

<details>
<summary><b>Installing MKVToolNix and ffmpeg manually</b></summary>

```bash
# Debian / Ubuntu
sudo apt-get install -y mkvtoolnix ffmpeg

# Fedora / RHEL
sudo dnf install -y mkvtoolnix ffmpeg

# Arch
sudo pacman -S --needed mkvtoolnix-cli ffmpeg

# macOS
brew install mkvtoolnix ffmpeg
```

```powershell
# Windows
winget install MoritzBunkus.MKVToolNix
winget install Gyan.FFmpeg
```

</details>

---

## Installation

### Linux / macOS / WSL

```bash
bash <(curl -Ls https://raw.githubusercontent.com/nikannixro/kaelix/main/install.sh)
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/nikannixro/kaelix/main/install.ps1 | iex
```

No administrator rights are required. The installer prints what it detects
before it changes anything:

```
==> Environment
    Operating system:  Ubuntu 24.04.1 LTS
    Architecture:      x86_64
    Shell:             /bin/bash
    Install location:  /home/you/.local/share/kaelix
    Python env:        /home/you/.local/share/kaelix/venv
```

It then clones the repo, creates a private virtualenv, installs Kaelix into it,
and writes a `kaelix` launcher onto your PATH. Re-running the installer updates
an existing install in place.

> **Open a new terminal afterwards** so the PATH change takes effect.

<details>
<summary><b>Installer options</b></summary>

```bash
# Linux / macOS
./install.sh              # install or update
./install.sh --uninstall  # remove everything
./install.sh --help
```

```powershell
# Windows
.\install.ps1                     # install or update
.\install.ps1 -SkipDependencies   # never invoke winget; warn instead
.\install.ps1 -Quiet              # no prompts, no closing pause
.\install.ps1 -Uninstall          # remove everything, restore PATH
```

</details>

### From source (development)

See [CONTRIBUTING.md](CONTRIBUTING.md#development-environment-setup). A source
checkout deliberately refuses `--upgrade`; use git there.

---

## Quick start

```bash
kaelix
```

That's it. Kaelix asks six questions, shows you the resolved configuration, and
waits for confirmation before touching anything:

```
╭─────────────────────────── Welcome ───────────────────────────╮
│ Kaelix                                                        │
╰───────────────────────────────────────────────────────────────╯
Source directory (contains your .mkv files): ~/media/inbox
Output directory (created if it does not exist): ~/media/library
External PERSIAN/FARSI subtitle directory (leave empty to skip):
External ENGLISH subtitle directory (leave empty to skip):
Default AUDIO language code [en]:
Run in DRY-RUN mode (no changes written)? [y/N]: y
```

**Try a dry run first.** It prints every planned change and writes nothing:

```bash
kaelix --source ./inbox --output ./library --non-interactive --dry-run
```

```
INFO  Found 2 MKV file(s) under /home/you/media/inbox
INFO  --- Processing: /home/you/media/inbox/Test Movie 2021 1080p WEB-DL x265 10bit.mkv
INFO  Target: Test Movie (2021) [1080p] [WEB-DL] [x265 10 Bit].mkv
INFO    title: 'Test Movie (2021)'
INFO    tracks: 1V/2A/0S  attachments: 0
INFO  [DRY-RUN] Simulating operations only.
INFO  [DRY-RUN]   video: name='Video' lang=en default=True forced=False
INFO  [DRY-RUN]   audio: name='Audio' lang=en default=True forced=False
╭──────────────────────── Batch summary ────────────────────────╮
│ Total:   2                                                    │
│ OK:      2                                                    │
│ Failed:  0                                                    │
│ Skipped: 0                                                    │
╰───────────────────────────────────────────────────────────────╯
```

Happy with the plan? Drop `--dry-run`.

---

## Usage examples

```bash
# Interactive — Kaelix asks for everything
kaelix

# Fully scripted
kaelix --source ./inbox --output ./library --non-interactive

# With external subtitles for both languages
kaelix --source ./inbox --output ./library \
       --persian-subs ./subs/fa --english-subs ./subs/en \
       --non-interactive

# Japanese audio, no prompts
kaelix --source ./anime --output ./library --audio-lang ja --non-interactive

# MKVToolNix installed somewhere unusual
kaelix --source ./in --output ./out --non-interactive \
       --mkvmerge /opt/mkvtoolnix/bin/mkvmerge \
       --mkvpropedit /opt/mkvtoolnix/bin/mkvpropedit

# Nightly update check, silent unless something is available
kaelix --check-update --quiet
```

---

## Architecture overview

```
                  ┌──────────────────────────────────────────┐
   kaelix ───────▶│ cli.py                                   │
                  │  screen argv → self-manage? → run app    │
                  └────────────┬─────────────────┬───────────┘
                               │                 │
                  ┌────────────▼──────┐   ┌──────▼──────────────┐
                  │ selfmanage.py     │   │ prompts/questions.py│
                  │ version, update,  │   │ interactive input   │
                  │ upgrade, uninstall│   └──────┬──────────────┘
                  └───────────────────┘          │ Config
                                        ┌────────▼────────────────┐
                                        │ services/orchestrator.py│
                                        │ per-file pipeline       │
                                        └────────┬────────────────┘
             ┌───────────────┬──────────────┬────┴─────────┬──────────────────┐
             ▼               ▼              ▼              ▼                  ▼
      identifier.py     renamer.py   subtitle_matcher  remuxer.py     metadata_editor.py
      mkvmerge -J    parse filename   find .srt/.ass    mkvmerge        mkvpropedit
                     + ffprobe                         (only if needed)
```

Per file, the orchestrator runs a fixed pipeline: identify → parse filename →
compute the output path → resolve the audio language → plan subtitles → copy →
remux if required → write metadata → strip image attachments. Any failure
deletes the partial output and, when interactive, asks whether to continue with
the next file.

A full module-by-module map lives in [CATALOG.md](CATALOG.md).

---

## Configuration

Kaelix has **no config file**. Everything is a CLI flag or an interactive
prompt, which keeps a run reproducible from its command line alone.

### Interactive prompts

| Prompt | Validation |
|--------|-----------|
| Source directory | Must exist and be a directory |
| Output directory | Created if missing |
| Persian/Farsi subtitle directory | Optional; must exist if given |
| English subtitle directory | Optional; must exist if given |
| Default audio language | 2- or 3-letter code, letters only (default `en`) |
| Dry run | Yes/no |

Invalid input re-prompts rather than aborting. A per-file prompt appears only
when a file has **more than one audio track** — otherwise the batch default is
used silently.

### Environment variables

| Variable | Effect |
|----------|--------|
| `KAELIX_APP_DIR` | Overrides the entire install directory (app, virtualenv, logs). Honoured by both installers, the launcher, and the CLI. Useful for portable installs and testing. |
| `NO_COLOR` | Disables colour in `install.sh` output |

```bash
# Install into a custom location
KAELIX_APP_DIR=/opt/kaelix bash install.sh
```

### Metadata rules

These are the rules Kaelix applies. They are defined in
[`src/config.py`](src/config.py) as dataclass defaults and are not yet
exposed as CLI flags — see [Limitations](#limitations-and-direction).

| Track | Name | Language | Default | Forced |
|-------|------|----------|:-------:|:------:|
| Video | `Video` | `en` | yes | no |
| Audio | `Audio` | your choice per run or per file | yes | no |
| Subtitle — Persian/Farsi | `Subtitle` | `fa` | yes | yes |
| Subtitle — English, SDH | `English [SDH]` | `en` | no | no |
| Subtitle — English | `English` | `en` | no | no |
| Subtitle — any other language | **removed from the output** | — | — | — |

Persian is detected from `fa`, `fas`, `per`, `pes` (or any `fa*`); English from
`en`, `eng` (or any `en*`). The container title is set to the parsed name
without release tags, and `image/*` attachments are deleted.

### Renaming

```
Movie:  MOVIE NAME (YEAR) [QUALITY] [SOURCE] [CODEC].mkv
Series: SERIES NAME - S00E00 [QUALITY] [SOURCE] [CODEC].mkv
```

| Field | Recognised values | Fallback |
|-------|-------------------|----------|
| Quality | `4320p` `2160p` `1440p` `1080p` `720p` `480p`, plus `4k` → `2160p` | `1080p` |
| Source | `WEB-DL` `WEBRip` `WEB` `BluRay` `BDRip` `BR-Rip` `HDRip` `HDTV` `DVDRip` `DVDScr` `DVD` `HDCAM` `CAM` `HDTS` `TS` `TC` `REMUX` | `WEB-DL` |
| Codec | `x265`/`h265`/`hevc` → `x265`; `x264`/`h264`/`avc` → `x264`; `av1`; `vp9` | video track, then `x265` |
| 10-bit | `10bit` `10-bit` `10 bit` `hi10p` in the filename, else `ffprobe` pixel format | not 10-bit |

Season/episode comes from `S00E00`; a movie year from a standalone `19xx`/`20xx`.
Every fallback is logged as a warning, so you always know what was guessed.

> Tokens must stand alone — `1080p` inside `x1080possible` will not match.

---

## External subtitles

Subtitle files are matched by **exact stem** against the container title, so
matching is predictable and never fuzzy. Recognised extensions: `.srt`, `.ass`,
`.ssa`, `.sub`, `.vtt`.

| Kind | Expected filename |
|------|-------------------|
| Persian / generic | `MOVIE NAME (YEAR) [Subtitle].srt` |
| English | `MOVIE NAME (YEAR) [Subtitle] [english].srt` |
| English SDH | `MOVIE NAME (YEAR) [Subtitle] [english] [SDH].srt` |
| Series | `SERIES NAME - S00E00 [Subtitle].srt` |

English lookup order: `[english] [SDH]` → `[english]` → the plain stem. Matching
is case-insensitive on the tag tokens.

**Example.** For `Test Movie (2021) [1080p] [WEB-DL] [x265].mkv`:

```
subs/fa/Test Movie (2021) [Subtitle].srt
subs/en/Test Movie (2021) [Subtitle] [english] [SDH].srt
```

When an external Persian or English subtitle is found, the corresponding
embedded track is dropped and the external one is added with the correct name,
language, and flags.

Subtitles in **any other language are removed** — Kaelix keeps English and
Persian only. If a file has nothing to add and nothing to drop, no remux
happens at all and the existing tracks are simply relabelled in place.

---

## CLI reference

```
kaelix [command] [options]
```

### Commands

| Command | Description | Exit codes |
|---------|-------------|------------|
| `kaelix` / `kaelix run` | Process files (interactive, or with flags) | `0` all ok · `1` some files failed · `2` bad input · `130` interrupted |
| `kaelix --help` / `kaelix help` | Full option list with examples | `0` |
| `kaelix --version` | Installed version | `0` |
| `kaelix --check-update` | Check GitHub for a newer release | `0` current · `1` update available · `2` unreachable |
| `kaelix --upgrade` | Install the latest release | `0` ok or already current · `2` failed |
| `kaelix --uninstall` | Remove Kaelix (asks first) | `0` |

`--check-update`'s exit codes are script-friendly — pair with `--quiet` to
print only when an update exists:

```bash
kaelix --check-update --quiet || notify-send "Kaelix update available"
```

### Options

| Option | Description |
|--------|-------------|
| `-s`, `--source PATH` | Source directory containing `.mkv` files |
| `-o`, `--output PATH` | Output directory (created if missing) |
| `--persian-subs PATH` | External Persian/Farsi subtitle directory |
| `--english-subs PATH` | External English subtitle directory |
| `--audio-lang CODE` | Default audio language, 2–3 letters (default `en`) |
| `--dry-run` | Simulate; write nothing |
| `--non-interactive` | Never prompt; requires `--source` and `--output` |
| `--mkvmerge PATH` | Explicit `mkvmerge` binary |
| `--mkvpropedit PATH` | Explicit `mkvpropedit` binary |
| `--ffprobe PATH` | Explicit `ffprobe` binary |
| `--quiet` | Suppress non-essential output |

Unknown input never produces a stack trace or a raw argparse dump:

```console
$ kaelix --upgarde
Error: Unknown option '--upgarde'
Did you mean '--upgrade'?

Usage:
  kaelix [command] [options]
...
Run 'kaelix --help' for more information.
```

---

## Where files live

Nothing is written into your project or media folders except the output files.

| | Linux | macOS | Windows |
|---|---|---|---|
| App, virtualenv, logs | `~/.local/share/kaelix/` | `~/Library/Application Support/kaelix/` | `%LOCALAPPDATA%\kaelix\` |
| `kaelix` launcher | `~/.local/bin/` | `~/.local/bin/` | `%LOCALAPPDATA%\Programs\kaelix\bin\` |

```
~/.local/share/kaelix/
├── app/      git clone of this repository
├── venv/     private virtualenv with Kaelix installed
└── logs/     kaelix-YYYY-MM-DD-HHMM.log (rotating, 5 MB × 5)
```

Linux honours `XDG_DATA_HOME` when set. Each install owns its virtualenv, so
your system Python is never modified. If the log directory is unwritable,
Kaelix falls back to `~/.kaelix/logs`.

### How upgrades work

`kaelix --upgrade` fetches release tags, checks out the newest `vX.Y.Z`, and
reinstalls it into the existing virtualenv. **If the new version fails to
install, the previous commit is restored and reinstalled** — a failed upgrade
leaves you on a working install, never a broken one.

Versions are compared numerically, so `0.10.0` correctly supersedes `0.3.0`.

---

## Troubleshooting

<details>
<summary><b><code>kaelix: command not found</code> after installing</b></summary>

The launcher directory is not on your PATH yet. Open a new terminal first — the
installer prints the exact line to add if it still isn't found:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc   # or ~/.zshrc
```

On Windows, a new terminal is required for the user PATH change to apply.
</details>

<details>
<summary><b><code>'mkvmerge' not found on PATH</code></b></summary>

MKVToolNix isn't installed or isn't on PATH. Install it (see
[Requirements](#requirements)), or point Kaelix at the binaries directly:

```bash
kaelix --mkvmerge /path/to/mkvmerge --mkvpropedit /path/to/mkvpropedit
```
</details>

<details>
<summary><b>Everything was skipped: <code>Output exists, skipping</code></b></summary>

Intentional. A target filename that already exists is never overwritten, which
is what makes an interrupted batch resumable. Delete the outputs you want
regenerated, or use a fresh output directory.
</details>

<details>
<summary><b>Filenames came out with the wrong quality/source/codec</b></summary>

Those fields are parsed from the filename. Run with `--dry-run` and read the
warnings — each fallback is logged (`Quality not detected; defaulting to
1080p.`). Rename the input to include the tokens listed under
[Renaming](#renaming), or accept the defaults.
</details>

<details>
<summary><b>My external subtitle wasn't picked up</b></summary>

Matching is by exact stem. Run `--dry-run` to see the target name Kaelix
computed, then name the subtitle `<that name without tags> [Subtitle].srt`. A
mismatched year or a stray release tag is the usual cause.
</details>

<details>
<summary><b>10-bit isn't detected</b></summary>

`ffprobe` is missing, so only filename tokens are consulted. Install ffmpeg or
pass `--ffprobe /path/to/ffprobe`. Bit depth affects the output filename only.
</details>

<details>
<summary><b><code>--upgrade</code> says "This is a development checkout"</b></summary>

You're running from a git clone rather than an install. Update it with
`git pull` instead.
</details>

<details>
<summary><b>Windows: uninstall left the folder behind</b></summary>

Kaelix runs from inside its own virtualenv, so Windows keeps the live
interpreter's files locked. The exact path to delete is printed; removing it
manually after the process exits completes the uninstall.
</details>

<details>
<summary><b>Where are the logs?</b></summary>

`<app dir>/logs/kaelix-YYYY-MM-DD-HHMM.log` — see
[Where files live](#where-files-live). The active path is printed at the start
of every run. Installer logs sit in the same directory as `install-*.log`.
</details>

---

## FAQ

**Does it re-encode my video?**
No. Metadata is edited in place with `mkvpropedit`. Even a subtitle swap uses
`mkvmerge` to copy streams without touching them.

**Can it damage my originals?**
Originals are opened read-only and copied. All edits happen on the copy, and a
failed file has its partial output deleted.

**Does it work on `.mp4` or `.avi`?**
No — MKV only. The tooling it wraps is Matroska-specific.

**Why Persian and English specifically?**
Those are the two languages Kaelix keeps. Subtitles in any other language —
including untagged (`und`) ones — are removed from the output, because the
point is a library with exactly two predictable subtitle options. Audio tracks
are never removed.

**Can I keep the original track names?**
Not currently. Kaelix's purpose is to normalise them.

**Does it need admin/root?**
No. Everything installs under your user account.

**Can I run it on a schedule?**
Yes — use `--non-interactive` with explicit paths. Exit codes distinguish
success from partial failure.

**How do I move an install?**
Set `KAELIX_APP_DIR` and re-run the installer; then remove the old directory.

---

## Security considerations

- **No network access at runtime.** The only outbound requests are to
  `api.github.com/repos/nikannixro/kaelix/tags` and GitHub over git, and only
  when you run `--check-update` or `--upgrade`.
- **No credentials, no telemetry.** Kaelix stores no secrets and reports
  nothing anywhere.
- **No shell interpolation.** Every external tool is invoked with an argument
  list, never a shell string, so filenames containing quotes, spaces, or
  semicolons cannot inject commands.
- **User-scoped install.** No elevation is required and nothing is written
  outside your user directories. The Windows installer only asks for elevation
  indirectly, when *winget* installs a system dependency.
- **Installation runs code from the internet.** As with any
  `curl | bash`-style installer, read
  [`install.sh`](install.sh) / [`install.ps1`](install.ps1) before running them
  if you don't trust the source.
- **Upgrades are pinned to signed-off tags** in this repository, and a failed
  upgrade rolls back to the previous commit.
- **Log contents.** Logs record the full paths of processed files. Treat them
  as you would any file listing.

Found a security issue? Please report it privately via a
[security advisory](https://github.com/nikannixro/kaelix/security/advisories/new)
rather than a public issue.

---

## Limitations and direction

Stated honestly, so you know what you're adopting:

- **No automated test suite.** Adding one is the highest-value contribution
  right now — see [CONTRIBUTING.md](CONTRIBUTING.md#testing).
- **Metadata rules aren't user-configurable.** They live as dataclass defaults
  in [`src/config.py`](src/config.py); the plumbing reads them from `Config`,
  so exposing them as flags or a config file is a contained change.
- **English and Persian are the only subtitle languages kept.** Everything else
  is removed, by design. If you need other languages preserved, this is the
  behaviour to change.
- **Files are processed one at a time.** Metadata-only files cost one copy and
  two header writes; a large remux-heavy batch would benefit from parallelism.
- **MKV only.**

---

## Contributing

Contributions are welcome — bug reports, documentation fixes, and tests
especially. Start with [CONTRIBUTING.md](CONTRIBUTING.md) for environment
setup, coding conventions, and the pull request process, and
[CATALOG.md](CATALOG.md) for a tour of the codebase.

---

## License

[MIT](LICENSE) © N I K A N

---

## Credits

Kaelix is a wrapper around excellent existing tools and would not exist without
them:

- **[MKVToolNix](https://mkvtoolnix.download/)** by Moritz Bunkus — `mkvmerge` and `mkvpropedit` do all the real Matroska work.
- **[FFmpeg](https://ffmpeg.org/)** — `ffprobe` for pixel-format inspection.
- **[Rich](https://github.com/Textualize/rich)** by Will McGugan — console output.

Installer presentation takes inspiration from
[Ollama](https://ollama.com/install.sh),
[3x-ui](https://github.com/MHSanaei/3x-ui), and
[Chris Titus Tech's Windows Utility](https://github.com/ChrisTitusTech/winutil).
