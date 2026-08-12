"""Subtitle policy check: only English and Persian subtitles survive.

Runnable standalone (`python tests/test_subtitle_policy.py`) or under pytest.
Pure logic — no media files, no subprocesses.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config  # noqa: E402
from src.models.media_file import MediaFile  # noqa: E402
from src.models.track import Track  # noqa: E402
from src.services.metadata_editor import compute_track_updates  # noqa: E402
from src.services.orchestrator import BatchOrchestrator  # noqa: E402


def _media(*subtitle_langs: str) -> MediaFile:
    media = MediaFile(Path("in.mkv"), Path("out.mkv"), Path("."))
    media.tracks = [Track(0, "video"), Track(1, "audio", properties={"language": "eng"})]
    for i, lang in enumerate(subtitle_langs, start=2):
        media.tracks.append(Track(i, "subtitles", properties={"language": lang}))
    media.selected_audio_language = "en"
    return media


def _orchestrator(**kw) -> BatchOrchestrator:
    return BatchOrchestrator(Config(source_dir=Path("."), output_dir=Path("."), **kw))


def test_non_english_persian_subtitles_are_dropped():
    plan = _orchestrator()._plan_subtitles(_media("eng", "fas", "spa", "jpn"))
    assert plan is not None, "a file with unwanted subtitles must be remuxed"
    assert plan["keep_ids"] == [2, 3], plan["keep_ids"]
    assert [t.id for t in plan["dropped"]] == [4, 5]


def test_untagged_subtitle_is_dropped():
    plan = _orchestrator()._plan_subtitles(_media("und"))
    assert plan is not None
    assert plan["keep_ids"] == []
    assert [t.id for t in plan["dropped"]] == [2]


def test_english_and_persian_only_needs_no_remux():
    # Nothing to add, nothing to drop: mkvpropedit relabels in place.
    assert _orchestrator()._plan_subtitles(_media("eng", "fas")) is None
    assert _orchestrator()._plan_subtitles(_media()) is None


def test_language_variants_are_recognised():
    plan = _orchestrator()._plan_subtitles(_media("en", "eng", "fa", "fas", "per", "pes"))
    assert plan is None, "every English/Persian code variant must be kept"


def test_dropped_tracks_get_no_metadata_update():
    media = _media("eng", "spa")
    config = Config(source_dir=Path("."), output_dir=Path("."))
    updates = compute_track_updates(media, config)
    types = [(u["type"], u["index"]) for u in updates]
    assert types == [("video", 1), ("audio", 1), ("subtitles", 1)], types
    assert all(u["language"] != "spa" for u in updates)


def test_selector_index_survives_a_skipped_track():
    # spa sits first, so the English track is s2 in the file. mkvpropedit must
    # be told s2, not s1, or it would rewrite the wrong track.
    media = _media("spa", "eng")
    updates = compute_track_updates(media, Config(source_dir=Path("."), output_dir=Path(".")))
    subs = [u for u in updates if u["type"] == "subtitles"]
    assert len(subs) == 1
    assert subs[0]["index"] == 2, subs[0]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok   {name}")
    print("\nALL PASS")
