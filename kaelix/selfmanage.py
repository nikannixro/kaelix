"""Self-management: version, update check, upgrade, uninstall.

Pure stdlib. Runs from inside the installed venv. Layout created by the
installers:

    <base>/app     git clone of the repo
    <base>/venv    private virtualenv with kaelix installed
    <base>/logs    rotating run logs
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

GITHUB_OWNER = "nikannixro"
GITHUB_REPO = "kaelix"
REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
TAGS_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/tags"

APP_DIR_ENV = "KAELIX_APP_DIR"

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

# upgrade_kaelix / check_update return codes
UP_TO_DATE = 0
UPDATED = 1
FAILED = 2
OFFLINE = 3
NOT_GIT = 4
UPDATE_AVAILABLE = 5


# --- Layout ------------------------------------------------------------------

def app_dirs(platform: str | None = None, home: Path | None = None) -> dict[str, Path]:
    """OS-appropriate install directories. `platform`/`home` are test seams."""
    if os.environ.get(APP_DIR_ENV):
        base = Path(os.environ[APP_DIR_ENV])
    else:
        platform = platform or sys.platform
        home = home or Path.home()
        if platform.startswith("win"):
            local = os.environ.get("LOCALAPPDATA")
            base = (Path(local) if local else home / "AppData" / "Local") / "kaelix"
        elif platform == "darwin":
            base = home / "Library" / "Application Support" / "kaelix"
        else:
            base = home / ".local" / "share" / "kaelix"
    return {
        "base": base,
        "app": base / "app",
        "venv": base / "venv",
        "logs": base / "logs",
    }


def venv_python(dirs: dict[str, Path]) -> Path:
    if sys.platform.startswith("win"):
        return dirs["venv"] / "Scripts" / "python.exe"
    return dirs["venv"] / "bin" / "python"


def resolve_app_root() -> Path:
    """Directory holding pyproject.toml: the install's app clone, else this repo."""
    app = app_dirs()["app"]
    if (app / "pyproject.toml").is_file():
        return app
    return Path(__file__).resolve().parent.parent


# --- Version -----------------------------------------------------------------

def derive_version(app_root: Path | None = None) -> str | None:
    """Version string, or None if it cannot be determined.

    With `app_root`, reads that checkout's pyproject.toml - the version the
    files on disk declare, which is what an update comparison must use.
    Without it, prefers installed package metadata and falls back to the
    resolved app root.
    """
    if app_root is None:
        try:
            from importlib.metadata import version

            return version("kaelix")
        except Exception:
            app_root = resolve_app_root()
    try:
        import tomllib

        with open(Path(app_root) / "pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except (OSError, KeyError, ValueError):
        return None


def version_sort_key(tag: str) -> tuple[int, int, int]:
    """Numeric sort key for a vX.Y.Z tag, so 0.10.0 sorts above 0.3.0."""
    m = _TAG_RE.match(tag.strip())
    if m is None:
        raise ValueError(f"not a version tag: {tag!r}")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_github_tags(raw: list[str]) -> list[str]:
    """Keep only vX.Y.Z tags, ascending by version."""
    return sorted((t for t in raw if _TAG_RE.match(t.strip())), key=version_sort_key)


def latest_tag() -> str | None:
    """Newest release tag from the GitHub API. None when unreachable."""
    req = urllib.request.Request(TAGS_API_URL, headers={"User-Agent": "kaelix"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    tags = parse_github_tags([t.get("name", "") for t in data])
    return tags[-1] if tags else None


# --- Update ------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 600):
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, timeout=timeout,
    )


def _git(*args: str, cwd: Path):
    return _run(["git", *args], cwd=cwd)


def check_update(dirs: dict[str, Path]) -> tuple[int, str | None, str | None]:
    """Compare installed version to the newest tag.

    Returns (code, current, latest) where code is UP_TO_DATE,
    UPDATE_AVAILABLE, or OFFLINE.
    """
    current = derive_version(dirs["app"])
    remote = latest_tag()
    if remote is None:
        return OFFLINE, current, None
    if current is not None and version_sort_key(remote) <= version_sort_key(current):
        return UP_TO_DATE, current, remote
    return UPDATE_AVAILABLE, current, remote


def upgrade_kaelix(dirs: dict[str, Path]) -> int:
    """Check out the newest tag and reinstall it, rolling back on failure."""
    app = dirs["app"]
    if not (app / ".git").is_dir():
        return NOT_GIT

    code, current, remote = check_update(dirs)
    if code != UPDATE_AVAILABLE:
        return code

    print(f"Updating {current or 'unknown'} -> {remote} ...")
    if _git("fetch", "--tags", "--force", "--quiet", cwd=app).returncode != 0:
        return FAILED

    previous = _git("rev-parse", "HEAD", cwd=app).stdout.strip() or None
    if _git("checkout", "--force", remote, cwd=app).returncode != 0:
        return FAILED

    if _reinstall(dirs) != 0:
        print("Install of the new version failed - rolling back.")
        if previous:
            _git("checkout", "--force", previous, cwd=app)
            _reinstall(dirs)
        return FAILED

    print(f"Updated to {remote}.")
    return UPDATED


def _reinstall(dirs: dict[str, Path]) -> int:
    """pip install the app clone into the private venv."""
    py = venv_python(dirs)
    if not py.is_file():
        return 1
    return _run(
        [str(py), "-m", "pip", "install", "--quiet", "--upgrade", str(dirs["app"])]
    ).returncode


# --- Uninstall ---------------------------------------------------------------

def _wrapper_paths() -> list[Path]:
    """Launcher locations the installers write to.

    Must stay in sync with install.sh's BIN_DIR and install.ps1's $BinDir.
    """
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return [base / "Programs" / "kaelix" / "bin" / "kaelix.cmd"]
    return [Path.home() / ".local" / "bin" / "kaelix"]


def _force_remove(path: Path) -> None:
    """rmtree that also clears read-only bits (git object files on Windows)."""
    def on_error(func, target, _exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=on_error)


def uninstall_kaelix(dirs: dict[str, Path]) -> int:
    """Remove the launcher and the whole install directory."""
    for wrapper in _wrapper_paths():
        if wrapper.is_file() or wrapper.is_symlink():
            try:
                wrapper.unlink()
                print(f"Removed {wrapper}")
            except OSError as exc:
                print(f"Could not remove {wrapper}: {exc}")

    base = dirs["base"]
    if not base.exists():
        print("Nothing else to remove.")
        return 0

    _force_remove(base)
    if base.exists():
        # On Windows this process runs from base/venv, so the live interpreter's
        # own files stay locked until it exits.
        # ponytail: report the leftover path instead of scheduling a detached
        # deleter; add one if manual cleanup proves annoying.
        print(f"Kaelix uninstalled. Delete this folder to finish: {base}")
    else:
        print(f"Removed {base}")
    return 0
