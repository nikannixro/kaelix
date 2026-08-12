"""Apply metadata changes without remuxing using mkvpropedit."""
from __future__ import annotations

import subprocess
from typing import Any

from ..config import Config
from ..models.media_file import MediaFile
from ..models.track import Track
from ..utils.constants import (
    DEFAULT_SUBTITLE_LANGUAGE_EN,
    DEFAULT_SUBTITLE_LANGUAGE_FA,
    DEFAULT_VIDEO_LANGUAGE,
    DEFAULT_VIDEO_NAME,
    SDH_MARKER,
    TRACK_TYPE_SELECTOR,
)
from ..utils.logger import get_logger
from ..utils.validators import ValidationError

log = get_logger(__name__)


def _resolve_track_rules(track: Track, media: MediaFile, config: Config) -> dict[str, Any] | None:
    """Desired name/language/default/forced for one track, per config.

    Returns None for a track that will not be in the output at all: only
    English and Persian subtitles are kept, and the orchestrator remuxes the
    rest away before this runs.
    """
    if track.is_video:
        return {
            "name": DEFAULT_VIDEO_NAME,
            "language": DEFAULT_VIDEO_LANGUAGE,
            "default": True,
            "forced": False,
        }
    if track.is_audio:
        return {
            "name": config.audio_name,
            "language": (
                media.selected_audio_language
                or config.audio_language
                or track.language
            ),
            "default": config.audio_default,
            "forced": config.audio_forced,
        }
    if track.is_subtitle:
        if track.is_english:
            sdh = SDH_MARKER in track.raw_name.lower()
            return {
                "name": (
                    config.english_subtitle_name_sdh
                    if sdh
                    else config.english_subtitle_name_non_sdh
                ),
                "language": DEFAULT_SUBTITLE_LANGUAGE_EN,
                "default": config.english_subtitle_default,
                "forced": config.english_subtitle_forced,
            }
        if track.is_persian:
            return {
                "name": config.subtitle_name,
                "language": DEFAULT_SUBTITLE_LANGUAGE_FA,
                "default": config.subtitle_default,
                "forced": config.subtitle_forced,
            }
        return None
    # Unknown track type: leave everything as-is.
    return {
        "name": track.raw_name,
        "language": track.language,
        "default": track.is_default,
        "forced": track.is_forced,
    }


def compute_track_updates(media: MediaFile, config: Config) -> list[dict[str, Any]]:
    """Return one update dict per track that survives into the output.

    Each entry carries `index`, the 1-based per-type position mkvpropedit uses
    (`track:s2`). The counter advances for every track in the file, including
    skipped ones, so a skip can never shift a later track's selector.
    """
    updates = []
    counters: dict[str, int] = {}
    for track in media.tracks:
        counters[track.type] = counters.get(track.type, 0) + 1
        rules = _resolve_track_rules(track, media, config)
        if rules is None:
            continue
        updates.append({
            "type": track.type,
            "id": track.id,
            "index": counters[track.type],
            **rules,
        })
    return updates


def apply_metadata_to_tracks(
    media: MediaFile, config: Config, dry_run: bool = False
) -> None:
    """Apply track names/languages/flags and the segment title via mkvpropedit."""
    updates = compute_track_updates(media, config)

    if dry_run:
        log.info(f"[DRY-RUN] Would update metadata: {media.output_path}")
        log.info(f"[DRY-RUN]   title: {media.segment_title!r}")
        for u in updates:
            log.info(
                f"[DRY-RUN]   {u['type']}: name={u['name']!r} "
                f"lang={u['language']} default={u['default']} forced={u['forced']}"
            )
        return

    args: list[str] = [
        str(config.mkvpropedit_path), str(media.output_path),
        "--edit", "info",
        "--set", f"title={media.segment_title}",
    ]

    for u in updates:
        sel = TRACK_TYPE_SELECTOR.get(u["type"])
        if sel is None:
            log.warning(f"Skipping unknown track type: {u['type']}")
            continue
        args += [
            "--edit", f"track:{sel}{u['index']}",
            "--set", f"name={u['name']}",
            "--set", f"language={u['language']}",
            "--set", f"flag-default={'yes' if u['default'] else 'no'}",
            "--set", f"flag-forced={'yes' if u['forced'] else 'no'}",
        ]

    _run_mkvpropedit(args)
    log.info(f"Updated metadata (title + tracks): {media.output_path}")


def remove_image_attachments(
    media: MediaFile, config: Config, dry_run: bool = False
) -> None:
    """Delete every image/cover attachment from the MKV via mkvpropedit."""
    image_atts = [a for a in media.image_attachments if a.get("id") is not None]
    if not image_atts:
        return

    if dry_run:
        for att in image_atts:
            log.info(
                f"[DRY-RUN] Would delete attachment id={att['id']} "
                f"({att.get('content_type')})"
            )
        return

    args: list[str] = [str(config.mkvpropedit_path), str(media.output_path)]
    for att in image_atts:
        args += ["--delete-attachment", str(att["id"])]

    _run_mkvpropedit(args)
    log.info(f"Removed {len(image_atts)} image attachment(s): {media.output_path}")


def _run_mkvpropedit(args: list[str]) -> None:
    log.debug(f"Running: {' '.join(args)}")
    try:
        subprocess.run(
            args, check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        log.error(f"mkvpropedit failed: {exc.stderr}")
        raise ValidationError(f"mkvpropedit failed: {exc.stderr}") from exc
    except FileNotFoundError as exc:
        raise ValidationError(f"mkvpropedit binary not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(f"mkvpropedit timed out after {exc.timeout}s") from exc
