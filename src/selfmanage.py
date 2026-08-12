"""Self-management: version, update check, upgrade, uninstall.

Pure stdlib (urllib) so the app has no new dependencies. Runs inside the
installed venv; wires itself to the app dir via `APP_DIR` env var set by the
installer. Falls back to <repo_dir>/pyproject.toml for dev installs.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

GITHUB_OWNER = "nikannixro"
GITHUB_REPO = "kaelix"
REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/tags"

APP_DIR_ENV = "KAELIX_APP_DIR"


def app_dirs(platform: str | None = None, home: Path | None = None) -> dict[str, Path]:
    """OS-appropriate app directories. Home override is for tests."""
    platform = platform or sys.platform
    home = home or Path.home()
    if platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "kaelix"
    elif platform == "darwin":
        base = home / "Library" / "Application Support" / "kaelix"
    else:
        base = home / ".local" / "share" / "kaelix"
    # Env override lets the installer (or a test) relocate the app dir.
    if os.environ.get(APP_DIR_ENV):
        base = Path(os.environ[APP_DIR_ENV])
    return {
        "base": base,
        "app": base / "app",
        "venv": base / "venv",
        "logs": base / "logs",
        "downloads": base / "downloads",
    }


def derive_version(app_root: Path) -> str | None:
    """Read version from pyproject.toml under the app root."""
    pp = Path(app_root) / "pyproject.toml"
    try:
        import tomllib

        with open(pp, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return None


def venv_python(dirs: dict[str, Path]) -> Path:
    if sys.platform.startswith("win"):
        return dirs["venv"] / "Scripts" / "python.exe"
    return dirs["venv"] / "bin" / "python"


def bin_dir(dirs: dict[str, Path]) -> Path:
    if sys.platform.startswith("win"):
        return dirs["venv"] / "Scripts"
    return dirs["venv"] / "bin"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd=str(cwd))


def latest_tag() -> str | None:
    """Newest vX.Y.Z tag from the GitHub API. None when offline."""
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "kaelix"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        tags = [t["name"] for t in data if re.fullmatch(r"v?\d+\.\d+\.\d+", t["name"])]
        if not tags:
            return None
        return max(tags, key=version_sort_key)
    except Exception:
        return None


def version_sort_key(tag: str) -> tuple[int, ...]:
    """Sort vX.Y.Z tags numerically (0.10.0 > 0.3.0)."""
    return tuple(int(p) for p in re.search(r"(\d+)\.(\d+)\.(\d+)", tag).groups())


def parse_github_tags(raw: list[str]) -> list[str]:
    """Test seam: raw tag names -> sorted numeric list."""
    return sorted((t for t in raw if re.fullmatch(r"v?\d+\.\d+\.\d+", t)), key=version_sort_key)


def resolve_app_root() -> Path:
    """Locate the app dir: KAELIX_APP_DIR > install-time marker > cwd fallback."""
    if os.environ.get(APP_DIR_ENV):
        return Path(os.environ[APP_DIR_ENV]) / "app"
    marker = Path(__file__).resolve().parent.parent / ".kaelix-app"
    if marker.is_file():
        return Path(marker.read_text().strip())
    # Dev fallback: repo layout (src/ is one level below pyproject.toml)
    return Path(__file__).resolve().parent.parent


# --- Upgrade ----------------------------------------------------------------

def _marker_write(dirs: dict[str, Path], version: str) -> None:
    """Write the installed-version marker."""
    (dirs["base"] / "installed-version").write_text(version + "\n")


def upgrade_kaelix(dirs: dict[str, Path], check_only: bool = False) -> int:
    """Upgrade the app to the newest GitHub tag.

    Returns: 0 = up-to-date/success, 1 = updated, 2 = failed, 3 = offline,
             4 = not a git install.
    """
    app = dirs["app"]
    if not (app / ".git").is_dir():
        return 4
    current = derive_version(app)
    remote = latest_tag()
    if remote is None:
        return 3
    if current is not None and current == remote.lstrip("v"):
        return 0
    if check_only:
        print(f"Update available: {current or 'unknown'} -> {remote}")
        return 0
    # Fetch + pin the target tag
    print(f"Updating to {remote} ...")
    if git("fetch", "--tags", "--quiet", cwd=app).returncode != 0:
        return 2
    # Rollback anchor: tag/commit of the CURRENT tree (may be prerelease)
    prev_anchor = None
    if current is not None:
        r = git("describe", "--tags", "--exact-match", "HEAD", cwd=app)
        if r.returncode == 0:
            prev_anchor = r.stdout.strip()
    if git("checkout", "-B", "update", remote, cwd=app).returncode != 0:
        return 2
    if _reinstall(dirs) != 0:
        print("Update failed — rolling back.")
        if prev_anchor:
            git("checkout", "-B", "update", prev_anchor, cwd=app)
        else:
            git("checkout", "-B", "update", "HEAD~1", cwd=app)
        _reinstall(dirs)
        return 2
    new_version = derive_version(app)
    print(f"Updated to {new_version}.")
    return 1


def _reinstall(dirs: dict[str, Path]) -> int:
    """pip install the app into the venv, then write the version marker."""
    py = venv_python(dirs)
    r = run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", str(dirs["app"])], timeout=300)
    if r.returncode != 0:
        return r.returncode
    v = derive_version(dirs["app"])
    _marker_write(dirs, v or "unknown")
    return 0


# --- Uninstall --------------------------------------------------------------

def uninstall_kaelix(dirs: dict[str, Path]) -> int:
    """Remove wrapper, venv, downloads, logs, and app clone. Keeps nothing."""
    app = dirs["app"]
    # Wrapper: prefer KAELIX_APP_DIR marker; else remove from PATH dirs.
    wrapper = Path(os.environ.get("KAELIX_BIN", "")) / ("kaelix.cmd" if sys.platform.startswith("win") else "kaelix")
    if wrapper.exists():
        try:
            wrapper.unlink()
        except OSError:
            pass
    try:
        shutil.rmtree(dirs["base"], ignore_errors=True)
    except OSError:
        pass
    return 0