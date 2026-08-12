"""Self-management: version, upgrade, uninstall.

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
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

GITHUB_OWNER = "nikannixro"
GITHUB_REPO = "kaelix"
REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
TAGS_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/tags"

APP_DIR_ENV = "KAELIX_APP_DIR"

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

# upgrade_kaelix return codes
UP_TO_DATE = 0
UPDATED = 1
FAILED = 2
OFFLINE = 3
NOT_GIT = 4
_UPDATE_AVAILABLE = 5


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


def _check_update(dirs: dict[str, Path]) -> tuple[int, str | None, str | None]:
    """Compare the installed version to the newest tag.

    Internal: `--upgrade` is the only caller. Returns (code, current, latest)
    where code is UP_TO_DATE, _UPDATE_AVAILABLE, or OFFLINE.
    """
    current = derive_version(dirs["app"])
    remote = latest_tag()
    if remote is None:
        return OFFLINE, current, None
    if current is not None and version_sort_key(remote) <= version_sort_key(current):
        return UP_TO_DATE, current, remote
    return _UPDATE_AVAILABLE, current, remote


def upgrade_kaelix(dirs: dict[str, Path]) -> int:
    """Check out the newest tag and reinstall it, rolling back on failure."""
    app = dirs["app"]
    if not (app / ".git").is_dir():
        return NOT_GIT

    code, current, remote = _check_update(dirs)
    if code != _UPDATE_AVAILABLE:
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

def _bin_dir() -> Path:
    """Directory holding the `kaelix` launcher.

    Must stay in sync with install.sh's BIN_DIR and install.ps1's $BinDir.
    """
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "Programs" / "kaelix" / "bin"
    return Path.home() / ".local" / "bin"


def _launcher_root() -> Path:
    """Topmost launcher directory that belongs solely to Kaelix.

    On Windows that is `...\\Programs\\kaelix` (ours entirely, so it goes too).
    On Unix the launcher lives in the shared `~/.local/bin`, so only the single
    file may be removed - callers use `_launcher_path()` there instead.
    """
    return _bin_dir().parent if sys.platform.startswith("win") else _bin_dir()


def _launcher_path() -> Path:
    return _bin_dir() / ("kaelix.cmd" if sys.platform.startswith("win") else "kaelix")


def _force_remove(path: Path) -> bool:
    """rmtree that also clears read-only bits (git objects on Windows).

    Returns True when `path` is gone afterwards.
    """
    def on_error(func, target, _exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=on_error)
    return not path.exists()


def _strip_from_user_path(entry: Path) -> bool:
    """Remove `entry` from the Windows per-user PATH. True when it was there."""
    if not sys.platform.startswith("win"):
        return False
    import winreg

    target = str(entry).rstrip("\\").lower()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                return False
            parts = [p for p in str(current).split(";") if p]
            kept = [p for p in parts if p.rstrip("\\").lower() != target]
            if len(kept) == len(parts):
                return False
            winreg.SetValueEx(key, "Path", 0, kind, ";".join(kept))
    except OSError:
        return False
    return True


def _schedule_windows_cleanup(paths: list[Path]) -> None:
    """Detach a batch script that deletes `paths` once this process has exited.

    Kaelix runs from <base>/venv, so the live interpreter holds its own files
    open and the launcher .cmd is still being read by cmd.exe. Both can only be
    deleted from outside, after we are gone.
    """
    lines = ["@echo off", "> nul 2>&1 timeout /t 3 /nobreak"]
    for path in paths:
        p = str(path)
        # Retry: the interpreter may take a moment to release its files.
        lines += [
            "for /l %%i in (1,1,10) do (",
            f'  if exist "{p}" rmdir /s /q "{p}" 2> nul',
            f'  if exist "{p}" > nul 2>&1 timeout /t 1 /nobreak',
            ")",
        ]
    script = Path(tempfile.gettempdir()) / "kaelix-uninstall.cmd"
    # Deletes itself last; `start` detaches so the file is free to go.
    lines.append(f'start "" /b cmd /c "> nul timeout /t 2 & del /q ""{script}"""')
    script.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")

    creation = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    subprocess.Popen(  # noqa: S603 - fixed, self-authored script path
        ["cmd", "/c", str(script)],
        cwd=tempfile.gettempdir(),  # never a directory we are about to delete
        creationflags=creation,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def uninstall_kaelix(dirs: dict[str, Path]) -> int:
    """Remove every trace of Kaelix: launcher, PATH entry, and install directory."""
    base = dirs["base"]
    bin_dir = _bin_dir()
    launcher = _launcher_path()

    if not sys.platform.startswith("win"):
        # ~/.local/bin is shared with other programs, so only our launcher goes.
        if launcher.is_file() or launcher.is_symlink():
            try:
                launcher.unlink()
                print(f"Removed {launcher}")
            except OSError as exc:
                print(f"Could not remove {launcher}: {exc}")
        if base.exists() and not _force_remove(base):
            print(f"Could not fully remove {base}")
            return 2
        print("Kaelix has been uninstalled.")
        return 0

    # Windows: this interpreter lives in base/venv, and cmd.exe keeps the
    # launcher .cmd open for the whole run. Deleting the launcher's directory
    # now makes cmd fail to read its next line ("The batch file cannot be
    # found."), so the launcher tree is left entirely to the detached script.
    if _strip_from_user_path(bin_dir):
        print(f"Removed {bin_dir} from your PATH")

    if base.exists():
        _force_remove(base)

    # Programs\kaelix is ours alone, so the whole tree goes - not just bin\.
    pending = [p for p in (base, _launcher_root()) if p.exists()]
    if pending:
        _schedule_windows_cleanup(pending)
    print("Kaelix has been uninstalled.")
    return 0
