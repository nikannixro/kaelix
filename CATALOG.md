# Kaelix Project Catalog

A technical map of the repository: every module, what it owns, and how the
pieces connect. Read this before making a non-trivial change.

For user-facing documentation see [README.md](README.md); for workflow and
conventions see [CONTRIBUTING.md](CONTRIBUTING.md).

**Version:** 0.6.0 · **Python:** 3.12+ · **Runtime dependency:** `rich` · ~2,100 lines of Python

---

## Table of contents

- [At a glance](#at-a-glance)
- [Directory structure](#directory-structure)
- [Root files](#root-files)
- [Execution flow](#execution-flow)
- [Module reference](#module-reference)
  - [Entry points](#entry-points)
  - [`src/cli.py`](#srcclipy)
  - [`src/selfmanage.py`](#srcselfmanagepy)
  - [`src/config.py`](#srcconfigpy)
  - [Data models](#data-models)
  - [Services](#services)
  - [Prompts](#prompts)
  - [Utilities](#utilities)
- [Installed layout](#installed-layout)
- [Configuration reference](#configuration-reference)
- [Commands and tools](#commands-and-tools)
- [External integrations](#external-integrations)
- [Feature list](#feature-list)
- [Technical notes](#technical-notes)
- [Extension points](#extension-points)

---

## At a glance

| | |
|---|---|
| **Purpose** | Batch-normalise MKV track metadata, swap in external subtitles, rename to a release-style scheme |
| **Type** | Single-user CLI application |
| **Distribution name** | `kaelix` (import package: `src`) |
| **Console script** | `kaelix` → `src.main:main` |
| **Runtime dependency** | `rich>=13.0.0` — everything else is standard library |
| **External binaries** | `mkvmerge`, `mkvpropedit` (required); `ffprobe` (optional) |
| **State** | None. No database, no config file, no cache. Logs only. |
| **Network** | Only on `--upgrade` (GitHub tags API + git) |
| **Lint** | `ruff check src/` — the project's only automated gate |
| **Tests** | None — see [CONTRIBUTING.md](CONTRIBUTING.md#testing) |

---

## Directory structure

```
kaelix/
├── src/                        Python package (imported as `src`)
│   ├── __init__.py             Package docstring only
│   ├── __main__.py             `python -m src` entry
│   ├── main.py                 `main()` — console-script entry point
│   ├── cli.py                  Argument parsing, dispatch, config assembly
│   ├── selfmanage.py           Version, update check, upgrade, uninstall
│   ├── config.py               `Config` dataclass — one run's resolved settings
│   │
│   ├── models/                 Plain data, no I/O
│   │   ├── track.py            One MKV track
│   │   └── media_file.py       One MKV file + parsed name + target name
│   │
│   ├── services/               All real work; each wraps one concern
│   │   ├── orchestrator.py     Per-file pipeline and batch loop
│   │   ├── identifier.py       `mkvmerge --identify` → models
│   │   ├── renamer.py          Filename parsing, codec/10-bit detection
│   │   ├── subtitle_matcher.py External subtitle lookup
│   │   ├── remuxer.py          `mkvmerge` remux (subtitle rebuild)
│   │   └── metadata_editor.py  `mkvpropedit` metadata + attachment removal
│   │
│   ├── prompts/
│   │   └── questions.py        Interactive input, panels, summary
│   │
│   └── utils/
│       ├── constants.py        Every literal: tokens, templates, defaults
│       ├── validators.py       Input validation + `ValidationError`
│       └── logger.py           Rich console + rotating file handler
│
├── install.sh                  Linux/macOS installer (bash)
├── install.ps1                 Windows installer (PowerShell 5.1+)
├── pyproject.toml              Packaging + ruff config
├── README.md                   User documentation
├── CONTRIBUTING.md             Contributor guide
├── CATALOG.md                  This file
├── LICENSE                     MIT
└── .gitignore
```

Four layers, strictly one-directional: `models` ← `services` ← `cli` ← `main`.
`utils` is used by everything; `models` import nothing but `utils`.

---

## Root files

| File | Lines | Purpose |
|------|------:|---------|
| `install.sh` | ~300 | Detects distro/arch/WSL, finds Python 3.12+, clones the repo, creates a virtualenv, writes a PATH launcher, logs to the app dir. Supports `--uninstall` and `--help`. |
| `install.ps1` | ~440 | Same for Windows. No elevation required; optionally installs dependencies via winget; writes a `.cmd` shim and updates the user PATH. Supports `-Uninstall`, `-SkipDependencies`, `-Quiet`. |
| `pyproject.toml` | 44 | setuptools build, project metadata, the `kaelix` console script, and the ruff configuration. |
| `.gitignore` | — | Python artefacts, virtualenvs, tool caches, logs, IDE and OS files, local agent output. |

---

## Execution flow

### Startup

```
kaelix --version
  └─ launcher script  (exports KAELIX_APP_DIR, execs the venv binary)
      └─ src.main:main
          └─ cli.run(argv)
              ├─ _screen_args()      reject unknown commands/options early
              ├─ parser.parse_args()
              ├─ _handle_selfmanage() --version/--upgrade/--uninstall
              └─ _run_app()          the normal path
```

`_screen_args` runs **before** argparse so bad input yields a friendly message
plus a `difflib` suggestion instead of an argparse dump. It also maps the bare
verbs `run` (no-op, the default action) and `help` (→ `--help`).

### The per-file pipeline

`BatchOrchestrator.run()` walks `source_dir.rglob("*.mkv")` sorted, then for each
file calls `_process_one`:

| Step | Module | Notes |
|-----:|--------|-------|
| 1 | `identifier.build_media_file` | `mkvmerge -J` → `MediaFile` + `Track` list |
| 2 | `renamer.populate_media_file_from_filename` | Title, year/season/episode, quality, source, codec; `validate_parse` logs each fallback |
| 3 | — | Output path = `output_dir / <relative parent> / target_filename` |
| 4 | — | **Skip** if the target already exists |
| 5 | `orchestrator._resolve_audio` | Prompt only when >1 audio track and interactive |
| 6 | `orchestrator._plan_subtitles` | Returns a remux plan, or `None` when nothing is added and nothing needs dropping |
| 7 | — | `--dry-run` stops here, logging the full plan |
| 8 | `remuxer.remux_subtitles` | **Plan exists:** `mkvmerge` writes the output directly from the source in one pass |
| 9 | — | **No plan:** `shutil.copy2` source → output. Steps 8 and 9 are mutually exclusive — the file is never written twice |
| 10 | `identifier.build_media_file` | Re-identify after a remux — track IDs shifted |
| 11 | `metadata_editor.apply_metadata_to_tracks` | One `mkvpropedit` call: title + every surviving track |
| 12 | `metadata_editor.remove_image_attachments` | Second `mkvpropedit` call, only if `image/*` attachments exist |

Failure handling: steps 8–12 are wrapped so **any** exception — including
`KeyboardInterrupt` — deletes the partial output before re-raising. The batch
loop then counts the failure and, when interactive, asks whether to continue.

Subtitle policy: only English and Persian subtitles reach the output. A file
carrying any other subtitle language is remuxed even when no external subtitle
was supplied, because dropping a track requires rebuilding the container.

---

## Module reference

### Entry points

| File | Contents |
|------|----------|
| `src/main.py` | `main() -> int` — calls `cli.run(sys.argv[1:])`. The console-script target. |
| `src/__main__.py` | Enables `python -m src`; raises `SystemExit(main())`. |
| `src/__init__.py` | Docstring only — no import side effects. |

### `src/cli.py`

Argument parsing, dispatch, and config assembly. 318 lines.

| Symbol | Role |
|--------|------|
| `USAGE`, `EXAMPLES` | Help text shown by `_reject` and as the argparse epilog |
| `build_arg_parser()` | The full `ArgumentParser`; `prog="kaelix"` |
| `_known_flags(parser)` | Every registered option string, for validation and suggestions |
| `_reject(token, known)` | Prints `Error: Unknown command/option …`, a `difflib` suggestion, usage; returns `2` |
| `_screen_args(argv, parser)` | Pre-argparse validation; returns `(cleaned_argv, exit_code or None)` |
| `_handle_selfmanage(args)` | Runs a self-management action; `None` means "continue to the app" |
| `_run_app(args)` | Resolves binaries, builds `Config`, confirms, runs the orchestrator |
| `gather_config_interactive()` | Six prompts → `Config` |
| `gather_config_from_args(args)` | Flags → `Config`, validating every path and the language code |
| `run(argv)` | Entry point: screen → parse → dispatch |

Exit codes: `0` success · `1` some files failed · `2` bad input, unknown
command, or a failed upgrade · `130` interrupted.

### `src/selfmanage.py`

Version reporting, upgrading, uninstalling. Pure standard
library (`urllib`, `subprocess`, `tomllib`, `winreg`) — the CLI gains self-management
without adding a dependency. 247 lines.

| Symbol | Role |
|--------|------|
| `GITHUB_OWNER`, `GITHUB_REPO`, `REPO_URL`, `TAGS_API_URL` | Upstream constants |
| `APP_DIR_ENV` | `"KAELIX_APP_DIR"` |
| `UP_TO_DATE=0` `UPDATED=1` `FAILED=2` `OFFLINE=3` `NOT_GIT=4` | Outcome codes shared with `cli.py` (`_UPDATE_AVAILABLE=5` is internal) |
| `app_dirs(platform, home)` | `{base, app, venv, logs}` per OS; `platform`/`home` are test seams |
| `venv_python(dirs)` | `venv/bin/python` or `venv\Scripts\python.exe` |
| `resolve_app_root()` | The app clone if it has a `pyproject.toml`, else this repo |
| `derive_version(app_root)` | With `app_root`: that checkout's declared version. Without: installed package metadata. |
| `version_sort_key(tag)` | `"v0.10.0"` → `(0, 10, 0)`; raises `ValueError` on junk |
| `parse_github_tags(raw)` | Keeps `vX.Y.Z` only, ascending — prereleases are ignored |
| `latest_tag()` | Newest tag from the GitHub API; `None` when unreachable |
| `_check_update(dirs)` | `(code, current, latest)`; internal, only `upgrade_kaelix` calls it |
| `upgrade_kaelix(dirs)` | Fetch tags → checkout → reinstall → **roll back on failure** |
| `_reinstall(dirs)` | `pip install --upgrade <app clone>` into the private venv |
| `_bin_dir()`, `_launcher_root()`, `_launcher_path()` | Launcher location — **must stay in sync with both installers** |
| `_force_remove(path)` | `rmtree` that clears read-only bits (git objects on Windows); returns whether the path is gone |
| `_strip_from_user_path(entry)` | Removes the launcher directory from the Windows per-user PATH via `winreg` |
| `_schedule_windows_cleanup(paths)` | Detached `.cmd` that deletes the locked paths after this process exits |
| `uninstall_kaelix(dirs)` | Removes the launcher, the PATH entry, and the whole install directory |

Two subtleties worth knowing:

- `derive_version(dirs["app"])` reads the **checkout's** `pyproject.toml`, not
  installed metadata — an update decision must compare what is on disk.
- Versions are compared numerically, so `0.10.0 > 0.3.0`. String comparison
  would get this wrong.

### `src/config.py`

One frozen-by-convention dataclass, `Config`, carrying a single run's settings:
directories, the audio language, `dry_run`/`non_interactive`, the three resolved
binary paths, and the metadata rule set (names, default/forced flags, SDH
names). `describe()` renders the aligned summary shown before processing.

**This is where the metadata rules live.** They are defaults on the dataclass,
consumed by `metadata_editor` and `orchestrator`, and not yet surfaced as CLI
flags — the cleanest extension point in the codebase.

### Data models

Plain dataclasses with computed properties. No I/O, no subprocess calls — which
makes them trivially unit-testable.

#### `src/models/track.py`

| Member | Meaning |
|--------|---------|
| `id`, `type`, `codec`, `properties` | Straight from `mkvmerge -J` |
| `raw_name` | `properties["track_name"]`, `""` when absent |
| `language` | `language_ietf` preferred over `language`, else `"und"` |
| `is_default`, `is_forced` | Existing flags |
| `is_video`, `is_audio`, `is_subtitle` | Type checks (`"subtitles"` is mkvmerge's spelling) |
| `is_english`, `is_persian` | Code sets plus an `en*` / `fa*` prefix check |

#### `src/models/media_file.py`

| Member | Meaning |
|--------|---------|
| `source_path`, `output_path`, `relative_path` | Paths; `output_path` is set by the orchestrator |
| `tracks`, `attachments` | Identified content |
| `is_series`, `title`, `year`, `season`, `episode`, `quality`, `source_type`, `codec` | Parsed from the filename |
| `selected_audio_language` | Resolved per file |
| `video_tracks`, `audio_tracks`, `subtitle_tracks` | Filtered views |
| `image_attachments` | Attachments whose `content_type` starts with `image/` |
| `segment_title` | Container title, e.g. `Test Movie (2021)` |
| `target_name`, `target_filename` | Output name, with fallbacks applied |

### Services

#### `src/services/orchestrator.py`

`BatchOrchestrator` — the only stateful class. Owns `stats`
(`total`/`success`/`failed`/`skipped`) and the pipeline described
[above](#the-per-file-pipeline).

| Method | Role |
|--------|------|
| `run()` | Walks the tree, loops, prints the summary, returns `stats` |
| `_process_one(src)` | The 12-step pipeline; returns `"ok"` or `"skipped"` |
| `_discard_partial_output(media)` | Deletes the partial output after any failure, including interrupt |
| `_resolve_audio(media)` | Batch default, or a prompt when >1 audio track and interactive |
| `_plan_subtitles(media)` | Which subtitle IDs to keep, which to drop (non-EN/FA), which external files to add; `None` when no remux is needed |
| `_log_remux_plan(plan)` | Dry-run rendering of the plan |
| `_remux_to_output(media, plan)` | `mkvmerge` source → output in one pass, then re-identify |

#### `src/services/identifier.py`

`identify_file()` runs `mkvmerge --identification-format json --identify` (60 s
timeout) and returns parsed JSON; `build_media_file()` converts that into a
`MediaFile`. Every failure mode — non-zero exit, missing binary, timeout,
unparseable JSON — becomes a `ValidationError`. Null `tracks`/`attachments` are
treated as empty.

#### `src/services/renamer.py`

Filename parsing and codec detection. Pure functions except for the `ffprobe`
call.

| Function | Role |
|----------|------|
| `_token_re(token)` | `@cache`d compiled regex matching a token only when not glued to other alphanumerics |
| `_clean_title(raw)` | `.`/`_` → space, collapse whitespace, strip punctuation |
| `_detect_quality`, `_detect_source`, `_detect_codec_name_from_filename`, `_detect_10bit_from_filename` | Token scans against `constants.py` |
| `detect_video_codec_from_file(media)` | Codec from the identified video track |
| `detect_10bit_from_file(path, ffprobe)` | `ffprobe` pixel format → bit depth ≥ 10; `False` on any failure |
| `resolve_codec(media, ffprobe)` | Filename → video track → `x265`; appends `" 10 Bit"` |
| `parse_filename(filename)` | The main parser; returns a seven-key dict |
| `populate_media_file_from_filename(media, ffprobe)` | Applies the parse in place |
| `validate_parse(media)` | Warnings for every field that fell back |

Parse order: an `S00E00` match makes it a series (title = everything before it).
Otherwise a standalone year makes it a movie. With neither, the title is cut at
the first quality token.

#### `src/services/subtitle_matcher.py`

Exact-stem matching against `media.segment_title`, case-insensitive on tags.

| Function | Role |
|----------|------|
| `_subtitle_index(directory)` | `@lru_cache`d single scan → `{lowercased stem: path}` for recognised extensions |
| `_base_stem(media)` | `"<segment title> [Subtitle]"` |
| `find_persian_subtitle_match(media, dir)` | The base stem only |
| `find_english_subtitle_match(media, dir)` | `[english] [SDH]` → `[english]` → base; returns `(path, is_sdh)` |

#### `src/services/remuxer.py`

`remux_subtitles()` builds one `mkvmerge` command: keep the listed subtitle IDs
(or `--no-subtitles`), `--no-attachments`, then append each external file with
its own `--language`, `--track-name`, `--default-track-flag`, and
`--forced-display-flag`. One-hour timeout. Video and audio are stream-copied.

#### `src/services/metadata_editor.py`

| Function | Role |
|----------|------|
| `_resolve_track_rules(track, media, config)` | The single source of truth for name/language/default/forced per track type and language; `None` for a track that is not in the output |
| `compute_track_updates(media, config)` | One update dict per surviving track, each carrying its 1-based per-type `index` |
| `apply_metadata_to_tracks(media, config, dry_run)` | One `mkvpropedit` call: container title + `track:v1`/`a1`/`s1`… selectors |
| `remove_image_attachments(media, config, dry_run)` | `--delete-attachment` per image attachment |
| `_run_mkvpropedit(args)` | Shared runner; 120 s timeout; every failure → `ValidationError` |

Track selectors are built from per-type counters, because `mkvpropedit` numbers
tracks per type (`s1`, `s2`) while `mkvmerge` reports global IDs. The counter
advances for **every** track including skipped ones, so skipping a track can
never shift a later track's selector.

### Prompts

`src/prompts/questions.py` — all interactive input, in one place, so the rest of
the codebase never reads stdin.

| Function | Role |
|----------|------|
| `_print`, `_panel` | Rich output, with a plain-text fallback that strips markup |
| `ask_string`, `ask_confirm` | Primitives (`rich.Prompt`/`Confirm`, else `input()`) |
| `_ask_until_valid(label, validate, default)` | Re-prompt loop shared by every prompt below |
| `prompt_source_directory`, `prompt_output_directory`, `prompt_persian_subtitle_directory`, `prompt_english_subtitle_directory`, `prompt_audio_language`, `prompt_dry_run` | The six configuration questions |
| `prompt_audio_language_for_file(name, default)` | Per-file audio prompt |
| `confirm_continue_after_error(name, error)` | Batch continuation prompt |
| `show_summary(total, success, failed, skipped)` | Closing panel |

`rich` is a declared dependency, but every call degrades gracefully if the
import fails.

### Utilities

#### `src/utils/constants.py`

Every literal the project uses: binary names, mkvmerge track-type strings,
`mkvpropedit` selector letters, default names and languages, Persian/English
code sets, quality tokens, source types (**longest-first**, so `WEB-DL` beats
`WEB`), codec normalisation, 10-bit tokens, fallbacks, the series/year regexes,
name and title templates, subtitle tags and extensions, and the image MIME
prefix.

New magic values go here, with a comment.

#### `src/utils/validators.py`

| Function | Role |
|----------|------|
| `ValidationError` | The one user-input exception; `cli.py` catches it and exits `2` |
| `resolve_binary(name, explicit)` | Explicit path, else `shutil.which` |
| `validate_directory(path, label)` | Must exist and be a directory |
| `validate_output_directory(path, label)` | Created if missing; `OSError` → `ValidationError` |
| `validate_subtitle_directory(path)` | Optional; empty/`None` → `None` |
| `validate_language_code(code, default)` | 2–3 letters, alphabetic |
| `validate_mkvtoolnix_available(...)` | Resolves both MKVToolNix binaries |
| `validate_ffprobe_available(...)` | Resolves `ffprobe` |

#### `src/utils/logger.py`

`setup_logging()` configures the root logger exactly once and returns the active
log path: a `RichHandler` for the console (plain `StreamHandler` fallback) plus a
`RotatingFileHandler` (5 MB × 5). The directory comes from
`selfmanage.app_dirs()["logs"]`, falling back to `~/.kaelix/logs` when
unwritable. `get_logger(name)` is what every module calls.

---

## Installed layout

```
<app dir>/
├── app/      git clone of this repository (what --upgrade moves)
├── venv/     private virtualenv; Kaelix installed non-editable
└── logs/     kaelix-*.log (runs) and install-*.log (installers)
```

| Platform | App dir | Launcher |
|----------|---------|----------|
| Linux | `$XDG_DATA_HOME/kaelix` or `~/.local/share/kaelix` | `~/.local/bin/kaelix` |
| macOS | `~/Library/Application Support/kaelix` | `~/.local/bin/kaelix` |
| Windows | `%LOCALAPPDATA%\kaelix` | `%LOCALAPPDATA%\Programs\kaelix\bin\kaelix.cmd` |

`KAELIX_APP_DIR` overrides the app dir everywhere: both installers, the
launcher, and `selfmanage.app_dirs()`.

The launcher is a **wrapper, not a symlink** — it exports `KAELIX_APP_DIR`
(respecting an existing value) and then execs the venv binary, so the override
survives upgrades.

> Launcher paths are duplicated in three places: `install.sh` (`BIN_DIR`),
> `install.ps1` (`$BinDir`), and `selfmanage._bin_dir()`. Changing one means
> changing all three, or `--uninstall` will leave the launcher behind.

---

## Configuration reference

There is no configuration file. Everything is a flag or a prompt.

### Environment variables

| Variable | Read by | Effect |
|----------|---------|--------|
| `KAELIX_APP_DIR` | `selfmanage.app_dirs`, both installers, the launcher | Overrides the install directory |
| `XDG_DATA_HOME` | `install.sh` | Linux app-dir base |
| `LOCALAPPDATA` | `selfmanage`, `install.ps1` | Windows app-dir and launcher base |
| `NO_COLOR` | `install.sh` | Disables coloured output |

### Metadata rules (`Config` defaults)

| Field | Default |
|-------|---------|
| `audio_name` | `"Audio"` |
| `audio_default` / `audio_forced` | `True` / `False` |
| `subtitle_name` | `"Subtitle"` |
| `subtitle_default` / `subtitle_forced` | `True` / `True` (Persian) |
| `english_subtitle_default` / `english_subtitle_forced` | `False` / `False` |
| `english_subtitle_name_sdh` | `"English [SDH]"` |
| `english_subtitle_name_non_sdh` | `"English"` |

Video is always `Video` / `en` / default / not forced, from `constants.py`.

### Parsing tables (`constants.py`)

| Table | Values |
|-------|--------|
| `QUALITY_PATTERNS` | `4320p` `2160p` `1440p` `1080p` `720p` `480p` (plus `4k` → `2160p`) |
| `SOURCE_TYPES` | `WEB-DL` `WEBRip` `WEB` `BluRay` `BDRip` `BR-Rip` `HDRip` `HDTV` `DVDRip` `DVDScr` `DVD` `HDCAM` `CAM` `HDTS` `TS` `TC` `REMUX` |
| `CODEC_NORMALIZATION` | `x265`/`h265`/`hevc` → `x265`; `x264`/`h264`/`avc` → `x264`; `av1`; `vp9` |
| `TEN_BIT_TOKENS` | `10bit` `10-bit` `10 bit` `hi10p` |
| `PERSIAN_LANGUAGE_CODES` | `fa` `fas` `per` `pes` |
| `ENGLISH_LANGUAGE_CODES` | `en` `eng` |
| `SUBTITLE_EXTENSIONS` | `.srt` `.ass` `.ssa` `.sub` `.vtt` |
| Defaults | `DEFAULT_QUALITY=1080p` `DEFAULT_SOURCE_TYPE=WEB-DL` `DEFAULT_CODEC=x265` |

---

## Commands and tools

### User commands

Full reference in the [README](README.md#cli-reference).

| Command | Handler |
|---------|---------|
| `kaelix` / `kaelix run` | `cli._run_app` → `BatchOrchestrator.run` |
| `kaelix --help` / `help` | argparse |
| `kaelix --version` | `selfmanage.derive_version` |
| `kaelix --upgrade` | `selfmanage.upgrade_kaelix` |
| `kaelix --uninstall` | `selfmanage.uninstall_kaelix` |

### Developer commands

| Task | Command |
|------|---------|
| Install for development | `pip install -e ".[dev]"` |
| Run from the tree | `python -m src …` |
| Lint | `ruff check src/` |
| Auto-fix | `ruff check src/ --fix` |
| Build | `python -m build` (setuptools) |
| Inspect an MKV | `mkvmerge -J "<file>"` |
| Install to a throwaway dir | `KAELIX_APP_DIR=/tmp/kx bash install.sh` |

### Installer flags

| Installer | Flags |
|-----------|-------|
| `install.sh` | `-u`/`--uninstall`, `-h`/`--help` |
| `install.ps1` | `-Uninstall`, `-SkipDependencies`, `-Quiet` |

---

## External integrations

| Integration | Where | Purpose |
|-------------|-------|---------|
| **mkvmerge** | `identifier.py`, `remuxer.py` | JSON identification; remux when the track layout changes |
| **mkvpropedit** | `metadata_editor.py` | In-place metadata and attachment edits |
| **ffprobe** | `renamer.py` | Pixel format → 10-bit detection (optional) |
| **GitHub tags API** | `selfmanage.latest_tag` | `api.github.com/repos/nikannixro/kaelix/tags`, 10 s timeout |
| **git** | `selfmanage`, both installers | Clone, fetch tags, checkout, rollback |
| **winget** | `install.ps1` | Optional Windows dependency installation |
| **rich** | `logger.py`, `questions.py` | Console output; degrades if unavailable |

All subprocess calls pass argument **lists**, never shell strings, and every one
has an explicit timeout: identify 60 s, `mkvpropedit` 120 s, remux 3600 s, git
600 s, `ffprobe` 30 s.

---

## Feature list

**Processing**

- Recursive `.mkv` discovery, sorted, output mirroring the source tree
- Non-destructive: originals read-only, all edits on a copy
- No re-encoding — `mkvpropedit` in place, `mkvmerge` stream-copy when remuxing
- Metadata normalisation for video, audio, and subtitle tracks
- Container title set from the parsed name
- `image/*` attachment removal
- External Persian/English subtitle replacement
- Subtitles that are neither English nor Persian are removed entirely
- Automatic SDH naming
- Existing outputs skipped, making batches resumable
- Partial outputs deleted on any failure, including interrupt
- Dry-run mode

**Parsing**

- Movie vs. series detection
- Quality, source type, and codec from the filename, with token-boundary matching
- Codec fallback to the video track; 10-bit via filename or `ffprobe`
- Every fallback logged as a warning

**Interface**

- Interactive prompts with re-prompt-on-invalid
- Fully scriptable non-interactive mode
- Per-file prompt only when >1 audio track
- Unknown commands/options get a suggestion, never a traceback
- Script-friendly exit codes
- Rich console output plus rotating file logs

**Distribution**

- One-line installers for Linux, macOS, and Windows
- User-scoped install; no admin required
- Private virtualenv; system Python untouched
- Idempotent installers that also upgrade
- `--upgrade` with rollback, and `--uninstall` that removes every trace
- `KAELIX_APP_DIR` for relocatable installs

---

## Technical notes

**Package name.** The distribution is `kaelix` but the import package is `src`
(`kaelix = "src.main:main"`, `include = ["src*"]`). Unusual, and deliberate.

**Numeric version comparison.** `version_sort_key` parses `vX.Y.Z` into a tuple
so `0.10.0 > 0.3.0`. Non-`vX.Y.Z` tags — prereleases included — are ignored by
`parse_github_tags`.

**Upgrade rollback.** `upgrade_kaelix` records `HEAD` before checking out the
new tag; if the reinstall fails, it checks that commit back out and reinstalls,
so a failed upgrade never leaves a broken install.

**Windows uninstall.** The process runs from `<app dir>/venv` and `cmd.exe`
keeps the `kaelix.cmd` launcher open for the whole command, so neither can
delete itself. `uninstall_kaelix` removes what it can, strips the PATH entry via
`winreg`, and hands the rest to `_schedule_windows_cleanup` — a detached `.cmd`
in `%TEMP%` that retries for a few seconds, then deletes itself. Deleting the
launcher's directory *before* exiting is what produced the old
`The batch file cannot be found.` message: `cmd.exe` reads the batch file line
by line, so removing it mid-run breaks the next read. The installer's shim also
ends its call line with `& exit /b` so cmd never looks for a line that is gone.

**Re-identification after remux.** A remux renumbers tracks, so
`_remux_to_output` re-runs identification before metadata is applied. Skipping
this would write metadata to the wrong tracks.

**Per-type selectors.** `mkvpropedit` addresses tracks per type (`s1`, `s2`)
while `mkvmerge` reports global IDs; `apply_metadata_to_tracks` keeps per-type
counters to bridge the two.

**Token boundaries.** `_token_re` prevents `1080p` from matching inside
`x1080possible` — filename parsing is full of these traps.

**Deliberate broad catch.** Exactly one `except Exception` exists, in
`BatchOrchestrator.run`, so one unreadable file cannot abort a 900-file batch.
It is annotated `# noqa: BLE001` with a comment.

**Idempotent logging.** `setup_logging` guards with a module-level flag and
returns the cached path on repeat calls.

---

## Extension points

Ranked by leverage, with the honest cost of each:

| Change | Where | Notes |
|--------|-------|-------|
| **Add tests** | new `tests/` | Highest value. `renamer`, `subtitle_matcher`, `metadata_editor`, `selfmanage` are pure enough to test without media files. |
| **Expose metadata rules** | `config.py` + `cli.py` | The rules already flow through `Config`; this is flags/config-file plumbing, not a redesign. |
| **New quality/source/codec tokens** | `constants.py` | Table edit. Keep `SOURCE_TYPES` longest-first. |
| **More per-language rules** | `metadata_editor._resolve_track_rules` | One function owns every rule; add a branch. |
| **New subtitle naming scheme** | `constants.py` + `subtitle_matcher.py` | Matching is exact-stem; adjust `_base_stem`. |
| **CI** | new `.github/workflows/` | Start with `ruff check src/` on push; add tests once they exist. |
| **Parallel processing** | `orchestrator.run` | The loop is sequential; per-file work is independent. Worth it only for remux-heavy batches. |
| **Other containers (`.mp4`)** | `identifier.py`, `remuxer.py`, `metadata_editor.py` | Large: MKVToolNix is Matroska-only, so this means a second backend. |
