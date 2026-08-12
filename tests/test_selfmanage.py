"""Minimal self-check for src/selfmanage.py. Run: python tests/test_selfmanage.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from selfmanage import parse_github_tags, version_sort_key, derive_version, app_dirs, GITHUB_OWNER


def test_parse_tags():
    tags = ["v0.2.0", "v0.10.0", "v0.3.0"]
    assert parse_github_tags(tags) == ["v0.2.0", "v0.3.0", "v0.10.0"]


def test_version_sort():
    assert sorted(["v0.2.0", "v0.10.0"], key=version_sort_key, reverse=True)[0] == "v0.10.0"


def test_derive_version():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "project"
        (root).mkdir()
        (root / "pyproject.toml").write_text('[project]\nversion = "0.3.0"\n')
        assert derive_version(root) == "0.3.0"


def test_app_dirs_linux():
    # fake platform name linux → HOME-based
    d = app_dirs("linux", Path("/home/u"))
    assert d["app"].parent == Path("/home/u/.local/share/kaelix")


def test_github_owner():
    assert GITHUB_OWNER == "nikannixro"