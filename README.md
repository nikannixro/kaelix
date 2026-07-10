# Movies Metadata Organizer

A professional, automated tool for batch-editing the metadata of large MKV
movie and TV-series libraries without re-encoding (no quality loss).

Built on top of **MKVToolNix** command-line tools (`mkvmerge`, `mkvpropedit`),
it edits track names, languages, default/forced flags, swaps external subtitle
tracks, and renames files to a consistent release-style naming convention.

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
bash <(curl -Ls https://raw.githubusercontent.com/nikannixro/movies-metadata-organizer/main/use.sh)
```

### Windows

Open **PowerShell as Administrator** and run:

```powershell
irm https://raw.githubusercontent.com/nikannixro/movies-metadata-organizer/main/use.bat -OutFile use.bat; .\use.bat
```

This installs all dependencies, sets up the repository, and launches the application automatically.

Alternatively, download [`use.bat`](https://github.com/nikannixro/movies-metadata-organizer/blob/main/use.bat)
directly from the repository and double-click it.

---

## Supported platforms

| Platform | Package manager | Status |
|----------|----------------|--------|
| Ubuntu | apt | Supported |
| Debian | apt | Supported |
| Linux Mint | apt | Supported |
| Arch Linux | pacman | Supported |
| WSL | Same as underlying distro | Supported |
| macOS | Homebrew | Supported |
| Windows | winget (use.bat) | Supported |

---

## Metadata rules applied

| Track        | Name              | Language | Default | Forced |
|--------------|-------------------|----------|---------|--------|
| Video        | `Video`           | `en`     | yes     | no     |
| Audio        | `Audio`           | (asked)  | yes     | no     |
| Subtitle (Persian/Farsi) | `Subtitle` | `fa` | yes | yes |
| Subtitle (English, SDH)   | `English [SDH]` | `en` | no | no |
| Subtitle (English, non-SDH) | `English`     | `en` | no | no |

The **SDH question** is only asked for English subtitles (once at the start).
Persian subtitles are never asked about SDH.

The **segment (container) title** is also set from the filename:
- Movies: `MOVIE NAME (YEAR)`
- Series: `SERIES NAME - S00E00`

**Image/cover attachments** are removed from every file.

When a file contains **multiple audio tracks**, the script pauses and asks you
to confirm the audio language for that file.

---

## Subtitle replacement

You can provide **two** optional external subtitle directories:
one for Persian/Farsi and one for English.

### Persian / generic subtitle files

- Movies: `MOVIE NAME (YEAR) [Subtitle].srt`
- Series: `SERIES NAME - S00E00 [Subtitle].srt`

(Also `.ass`.) These become a track named `Subtitle`, language `fa`,
default + forced.

### English subtitle files

The SDH flag is detected **from the filename** (no prompt needed):

- Movies (non-SDH): `MOVIE NAME (YEAR) [Subtitle] [english].srt`
- Movies (SDH): `MOVIE NAME (YEAR) [Subtitle] [english] [SDH].srt`
- Series (non-SDH): `SERIES NAME - S00E00 [Subtitle] [english].srt`
- Series (SDH): `SERIES NAME - S00E00 [Subtitle] [english] [SDH].srt`

A file containing `[SDH]` → track name `English [SDH]`; otherwise → `English`.
Language is always normalized to `en` (e.g. `en-US` becomes `en`).

### Per-language rules

- **External subtitle provided** → existing subtitle of that language is
  removed and the external file is added in its place.
- **No external subtitle** → the existing subtitle is kept and renamed
  (`Subtitle` for Persian; `English` or `English [SDH]` for English based on
  whether the original name contained "SDH").

---

## Project structure

```
movies-metadata-organizer/
├── use.sh                     # cross-platform installer and launcher
├── src/
│   ├── main.py                # entry point
│   ├── cli.py                 # argument parsing + interactive prompts
│   ├── config.py              # run configuration dataclass
│   ├── models/                # Track, MediaFile data models
│   ├── services/              # identifier, metadata_editor, remuxer,
│   │                          # renamer, subtitle_matcher, orchestrator
│   ├── prompts/               # interactive question helpers
│   └── utils/                 # constants, logger, validators
├── logs/                      # rotating log files
├── pyproject.toml             # project metadata
└── requirements.txt
```

---

## Codec detection

The codec in the output filename (e.g. `[x265 10 Bit]`) is resolved in this
order:

1. **Filename tokens** — `x265`, `x264`, `HEVC`, `AVC`, `h265`, `h264`, `av1`,
   `vp9` (case-insensitive). The 10-bit flag is read from tokens like `10bit`,
   `10-bit`, `hi10p`.
2. **Actual file** (fallback) — if the filename has no codec token, the video
   track codec reported by `mkvmerge --identify` is used (`HEVC` → `x265`,
   `AVC` → `x264`, etc.).
3. **ffprobe** (fallback) — if the filename has no 10-bit token, `ffprobe`
   reads the pixel format (`yuv420p10le` → 10-bit).
4. **Last resort** — if the codec still cannot be determined, it defaults to
   `x265` with a warning.

| Filename | Real file | Output codec |
|---|---|---|
| `Movie.2025.1080p.WEB-DL.x265.10bit.mkv` | HEVC 10-bit | `[x265 10 Bit]` (from filename) |
| `Movie.2025.2160p.BluRay.mkv` | HEVC 10-bit | `[x265 10 Bit]` (from file + ffprobe) |
| `Movie.2025.720p.Web-DL.mkv` | AVC 8-bit | `[x264]` (from file) |

---

## Performance notes

- `mkvpropedit` operates **in place** and is extremely fast (seconds for a large
  file) because it only rewrites headers — it does not touch the media streams.
- `mkvmerge` (remuxing) rewrites the whole file and is I/O-bound; it is only
  used when subtitle tracks are added/removed/replaced.
- For very large libraries, process from/to different physical disks to avoid
  I/O contention, and consider running in dry-run mode first.

---

## License

[MIT](LICENSE)
