# Contributing to Kaelix

Thanks for considering a contribution. Kaelix is a small, focused CLI, and that
is deliberate — the bar for new features is "does this make normalising a media
library measurably easier", not "is this technically possible".

Bug reports, documentation fixes, and **tests** are the most valuable
contributions right now. The project has no automated test suite yet; adding one
is the single highest-leverage change available.

New to the codebase? Read [CATALOG.md](CATALOG.md) first — it maps every module
in about five minutes of reading.

---

## Ground rules

- Be respectful. Assume the other person is competent and acting in good faith.
- Open an issue before starting anything large. A rejected PR costs you more than a rejected idea.
- Small, focused pull requests get reviewed and merged; sweeping refactors stall.
- Don't commit unrelated reformatting. It buries the actual change in noise.

---

## Development environment setup

**Requirements:** Python 3.12+, git, and MKVToolNix (`mkvmerge`,
`mkvpropedit`). `ffmpeg` (`ffprobe`) is optional — only 10-bit detection uses
it. See the README's [Requirements](README.md#requirements) section for install
commands.

```bash
git clone https://github.com/nikannixro/kaelix.git
cd kaelix

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"          # runtime deps + pytest + ruff
```

Verify:

```bash
python -m src --help
python -m src --version
```

Both invocations work in a checkout:

| | |
|---|---|
| `python -m src …` | Runs directly from the working tree — what you want while developing |
| `kaelix …` | The console script created by `pip install -e .` |

> `--upgrade` deliberately refuses to run in a source checkout ("This is a
> development checkout"). That is correct behaviour, not a bug — use git.

### Linting

Ruff is configured in `pyproject.toml` (line length 100, rules `E`, `F`, `W`,
`I`, `UP`, `B`, ignoring `E501`) and installed by the `dev` extra:

```bash
ruff check src/          # must pass with zero findings
ruff check src/ --fix    # auto-fix import order and similar
```

CI does not exist yet. **`ruff check src/` and `pytest tests/ -q` both passing
is the current bar for a green build** — run them before every push.

### Trying changes safely

Generate a throwaway MKV rather than experimenting on real media:

```bash
mkdir -p /tmp/kx/in /tmp/kx/out
ffmpeg -f lavfi -i "testsrc=size=320x180:rate=10:duration=2" \
       -f lavfi -i "sine=frequency=440:duration=2" \
       -map 0:v -map 1:a -c:v libx265 -c:a aac \
       "/tmp/kx/in/Test Movie 2021 1080p WEB-DL x265 10bit.mkv"

python -m src --source /tmp/kx/in --output /tmp/kx/out --non-interactive --dry-run
```

Inspect the result with the same tool Kaelix uses:

```bash
mkvmerge -J "/tmp/kx/out/Test Movie (2021) [1080p] [WEB-DL] [x265 10 Bit].mkv"
```

To exercise install paths without touching your real install, point
`KAELIX_APP_DIR` somewhere disposable:

```bash
KAELIX_APP_DIR=/tmp/kx/app bash install.sh
KAELIX_APP_DIR=/tmp/kx/app bash install.sh --uninstall
```

---

## Repository workflow

Kaelix uses a simple branch-and-PR flow against `main`. There is no `develop`
branch and no release branches.

```bash
git checkout main
git pull
git checkout -b fix/subtitle-stem-matching

# ... work, committing as you go ...

ruff check src/
git push -u origin fix/subtitle-stem-matching
```

Then open a pull request against `main`.

Never commit directly to `main`, and never force-push a branch someone else may
have pulled.

### Branch naming

`<type>/<short-description>`, lowercase with hyphens:

| Prefix | For |
|--------|-----|
| `fix/` | Bug fixes |
| `feat/` | New features |
| `docs/` | Documentation only |
| `refactor/` | Restructuring with no behaviour change |
| `test/` | Adding or improving tests |
| `chore/` | Tooling, dependencies, housekeeping |

Examples: `fix/windows-uninstall-lock`, `feat/config-file`, `test/renamer-parsing`.

---

## Commit message guidelines

[Conventional Commits](https://www.conventionalcommits.org/), matching the
existing history:

```
<type>: <imperative summary, lower case, no trailing period>

<body — why, not what; wrap at ~72 columns>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.

Good:

```
fix: compare release tags numerically so 0.10.0 beats 0.3.0

String comparison put v0.10.0 below v0.3.0, so --upgrade refused to
install any release after v0.9.x.
```

Bad: `update stuff`, `Fixed bug.`, `WIP`.

The body matters more than the summary for anything non-obvious. Explain what
was wrong and why the fix is correct — a future reader has the diff already,
not your reasoning.

---

## Code style guidelines

Match the surrounding code. Concretely, as it exists today:

- **`from __future__ import annotations`** at the top of every module.
- **Modern type hints**: `Path | None`, `list[str]`, `dict[str, Path]` — not `Optional`/`List`/`Dict`.
- **f-strings** for logging: `log.info(f"Found {n} file(s)")`.
- **Module-level logger**: `log = get_logger(__name__)`, from `src/utils/logger.py`. Never `print()` in library code — the CLI's user-facing output is the one exception, in `src/cli.py` and `src/selfmanage.py`.
- **Docstrings**: a one-line summary for every public function; add a short body when the *why* isn't obvious. Explain reasoning, not mechanics.
- **`pathlib.Path`** everywhere. No `os.path`.
- **Private helpers** are `_prefixed` and grouped under a `# --- Section ---` comment, following the layout in `src/cli.py`.
- **Constants** belong in `src/utils/constants.py`, never inline. If you add a
  magic string or number, it goes there with a comment.
- **Line length 100.** Ruff enforces the rest.

### Error handling

Two rules, both load-bearing:

1. **Raise `ValidationError`** (from `src/utils/validators.py`) for anything caused by user input — a missing directory, a bad language code, an absent binary. The CLI catches it, logs the message, and exits `2`. Never let a raw traceback reach the user for input errors.

2. **Catch specific exceptions.** No bare `except Exception` except in the one place it is deliberate — `BatchOrchestrator.run`, where a single unprocessable file must not kill the batch (it carries a `# noqa: BLE001` and a comment explaining why). Chain with `raise ... from exc` so the original cause survives.

Every subprocess wrapper handles `CalledProcessError`, `FileNotFoundError`, and
`TimeoutExpired`, converting each to a `ValidationError` with a useful message.
Follow that pattern — see `src/services/identifier.py`.

### Safety invariants

Do not break these. They are the project's core promises:

1. **Source files are never modified.** Read them; copy them; edit the copy.
2. **No re-encoding.** `mkvpropedit` for metadata; `mkvmerge` only when the track layout must change, always stream-copying.
3. **A failed file leaves no partial output.** See `_discard_partial_output` in the orchestrator — it also runs on `KeyboardInterrupt`.
4. **Existing outputs are never overwritten**, which is what makes a batch resumable.
5. **Only English and Persian subtitles reach the output.** Any other subtitle language is removed. Audio and video tracks are never removed.
6. **`--dry-run` writes nothing.** Every new write path needs a dry-run branch.
7. **No shell strings.** Always pass an argument list to `subprocess`, so filenames with quotes or semicolons stay inert.

A PR that violates one of these will be asked to change regardless of how well
it is written.

---

## Testing

Coverage is thin: `tests/test_subtitle_policy.py` covers the subtitle language
policy and the `mkvpropedit` selector indexing. Everything else is untested, and
PRs that only add tests are very welcome.

```bash
pip install -e ".[dev]"
pytest tests/ -q                          # or:
python tests/test_subtitle_policy.py      # runs standalone, no pytest needed
```

When adding tests:

- Use `pytest`, in the top-level `tests/` directory, files named `test_*.py`.
- Keep test-only dependencies in `[project.optional-dependencies].dev`, never in the runtime list. Kaelix's only runtime dependency is `rich`, and that should stay true.
- Model new files on `tests/test_subtitle_policy.py`: it builds `Track`/`MediaFile` objects by hand, touches no media files, and runs both under pytest and as a plain script.
- Good next targets, in rough order of value:
  - `src/services/renamer.py` — `parse_filename`, quality/source/codec detection
  - `src/services/subtitle_matcher.py` — stem matching and English/SDH precedence
  - `src/services/metadata_editor.py` — `compute_track_updates` against a hand-built `MediaFile`
  - `src/selfmanage.py` — `version_sort_key`, `parse_github_tags`, `app_dirs`
- Do not require real media files or network access. Build `Track`/`MediaFile` objects directly, and stub `latest_tag()` rather than calling GitHub.
- Add the command you used to run them to your PR description.

Because coverage is thin, every PR must still state **how it was verified** —
the exact commands you ran and what you observed. "Tested locally" is not a
verification report. For example:

```
ruff check src/                        → All checks passed
pytest tests/ -q                       → 6 passed
python -m src --version                → kaelix 0.5.0
python -m src --upgarde                → exit 2, suggests --upgrade
python -m src --source /tmp/kx/in --output /tmp/kx/out \
              --non-interactive --dry-run   → 2 files planned, 0 failed
mkvmerge -J "<output>"                 → 1V/1A/2S, spa+jpn subtitles dropped
```

If a change touches the installers, say which platform you ran them on. Both
were verified on Windows; `install.sh` has not been exercised on a native Linux
host, so real-Linux verification is genuinely useful.

---

## Reporting issues

Search [existing issues](https://github.com/nikannixro/kaelix/issues) first.

### Bugs

Include:

1. What you ran — the **full command**, with paths redacted if needed.
2. What you expected, and what happened instead.
3. `kaelix --version` output.
4. OS and version; `mkvmerge --version` output.
5. Relevant log excerpt from `<app dir>/logs/` (see [Where files live](README.md#where-files-live)).
6. For parsing or renaming bugs: the **exact input filename** and the output you expected. Attach `--dry-run` output — it shows the parse result and every fallback warning.

Please avoid attaching media files. A filename and `mkvmerge -J` output are
almost always enough.

### Security issues

Do not open a public issue. Use a
[private security advisory](https://github.com/nikannixro/kaelix/security/advisories/new).

### Feature requests

Describe the problem before the solution. "I have 900 files whose audio is
tagged `und` and I need it set per-directory" is actionable; "add a config
system" is not.

---

## Documentation contributions

Docs are code here — an inaccurate README is a bug.

Three files, three jobs. Keep them in their lanes:

| File | Audience | Contains |
|------|----------|----------|
| `README.md` | Users | What it does, install, usage, CLI reference, troubleshooting, FAQ |
| `CONTRIBUTING.md` | Contributors | Setup, workflow, conventions, testing, review |
| `CATALOG.md` | Developers | Module map, directory structure, technical reference |

Rules:

- **Verify before you document.** Run the command and paste real output. Do not describe intended behaviour.
- **Never invent a feature, flag, or config option.** If it isn't in the code, it doesn't go in the docs.
- **No duplication across files.** Cross-link instead — one fact, one home.
- **Consistent terminology.** Use these exact terms:

| Term | Meaning |
|------|---------|
| **app dir** / **install directory** | `~/.local/share/kaelix` and platform equivalents |
| **launcher** | The `kaelix` wrapper script / `kaelix.cmd` shim on PATH |
| **app clone** | The git clone at `<app dir>/app` |
| **segment title** | The MKV container title, e.g. `Test Movie (2021)` |
| **target name** | The computed output filename |
| **external subtitle** | An on-disk `.srt`/`.ass` file, as opposed to an embedded track |
| **remux** | An `mkvmerge` pass that rebuilds the track layout, stream-copying |

- **Clear English for an international audience**: short sentences, no idioms, no jokes that need cultural context.
- **Tables over paragraphs** for anything enumerable.
- **Keep code blocks runnable** — a reader should be able to copy, paste, and have it work.
- If a change alters user-visible behaviour, **update the docs in the same PR**.

---

## Pull request requirements

Before opening:

- [ ] `ruff check src/` passes with zero findings
- [ ] `pytest tests/ -q` passes
- [ ] Branch is up to date with `main`
- [ ] Commits follow Conventional Commits
- [ ] Docs updated if behaviour changed
- [ ] No unrelated files, reformatting, or caches (`__pycache__/`, `.ruff_cache/`, `build/`, `*.egg-info/` are all git-ignored — keep it that way)
- [ ] No new runtime dependency, unless the PR argues for it explicitly

In the description, include:

1. **What** changed, in one or two sentences.
2. **Why** — the problem it solves; link the issue if there is one.
3. **How it was verified** — exact commands and observed output (see [Testing](#testing)).
4. **Anything you could not verify**, and why. Honest gaps are fine; silent ones are not.

Keep the title under 70 characters and use the same style as a commit summary.

---

## Code review process

A single maintainer reviews. Expect a first response within a few days.

What review looks for, roughly in order:

1. **Does it hold the safety invariants?** (see [above](#safety-invariants))
2. **Is the verification real?** Claims of behaviour need commands and output behind them.
3. **Is it the smallest change that solves the problem?** No speculative abstractions, no config for a value that never changes.
4. **Does it fix the root cause?** A guard in the shared function beats a guard at one call site while sibling callers stay broken.
5. **Does it match the surrounding conventions?**
6. **Are the docs still accurate?**

Review comments are about the code, not you. If you disagree with one, say so
and explain why — being talked out of a review comment is a normal outcome.

Once approved, the maintainer merges. You do not need to squash; keep your
history readable and that is enough.

---

Thanks for helping make Kaelix better.
