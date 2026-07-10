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
    TRACK_TYPE_SELECTOR,
)
from ..utils.logger import get_logger
from ..utils.validators import ValidationError

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-track resolution helpers
# ---------------------------------------------------------------------------
def _resolve_language(track: Track) -> str:
    """Pick the desired language code for a track."""
    if track.is_video:
        return "en"
    if track.is_audio:
        return None  # handled by caller (audio_language)
    if track.is_subtitle:
        if track.is_english:
            return DEFAULT_SUBTITLE_LANGUAGE_EN
        if track.is_persian:
            return DEFAULT_SUBTITLE_LANGUAGE_FA
        return track.language  # keep unknown languages as-is
    return track.language


def _resolve_name(track: Track) -> str:
    """Pick the desired track name."""
    if track.is_video:
        return "Video"
    if track.is_audio:
        return "Audio"
    if track.is_subtitle:
        if track.is_english:
            # SDH is detected from the existing/already-set track name.
            if "sdh" in track.raw_name.lower():
                return "English [SDH]"
            return "English"
        return "Subtitle"  # Persian and any other subtitle
    return track.raw_name


def _resolve_default_flag(track: Track) -> bool:
    """Pick the desired Default flag."""
    if track.is_video:
        return True
    if track.is_audio:
        return True
    if track.is_subtitle:
        if track.is_english:
            return False
        if track.is_persian:
            return True
        return False  # other subtitle: not default
    return track.is_default


def _resolve_forced_flag(track: Track) -> bool:
    """Pick the desired Forced flag."""
    if track.is_video:
        return False
    if track.is_audio:
        return False
    if track.is_subtitle:
        if track.is_english:
            return False
        if track.is_persian:
            return True
        return False  # other subtitle: not forced
    return track.is_forced


def compute_track_updates(media: MediaFile, config: Config) -> list[dict[str, Any]]:
    """Return a list of update dictionaries, one per track."""
    updates = []
    for track in media.tracks:
        lang = _resolve_language(track)
        if track.is_audio:
            # Per-file selection (if any) takes priority over the batch default.
            lang = (
                media.selected_audio_language
                or config.audio_language
                or track.language
                or "und"
            )
        updates.append({
            "type": track.type,
            "id": track.id,
            "name": _resolve_name(track),
            "language": lang,
            "default": _resolve_default_flag(track),
            "forced": _resolve_forced_flag(track),
        })
    return updates


def apply_metadata_to_tracks(
    media: MediaFile, config: Config, dry_run: bool = False
) -> None:
    """Apply computed metadata (track names/langs/flags + segment title) via mkvpropedit."""
    if dry_run:
        log.info(f"[DRY-RUN] Would update metadata: {media.output_path}")
        log.info(f"[DRY-RUN]   title: {media.segment_title!r}")
        for u in compute_track_updates(media, config):
            log.info(
                f"[DRY-RUN]   {u['type']}: name={u['name']!r} "
                f"lang={u['language']} default={u['default']} forced={u['forced']}"
            )
        return

    type_counters: dict[str, int] = {}
    updates = compute_track_updates(media, config)

    args: list[str] = [str(config.mkvpropedit_path), str(media.output_path)]

    # Segment (container) title
    args.append("--edit")
    args.append("info")
    args.append("--set")
    args.append(f"title={media.segment_title}")

    # Per-track edits
    for u in updates:
        ttype = u["type"]
        sel = TRACK_TYPE_SELECTOR.get(ttype)
        if sel is None:
            log.warning(f"Skipping unknown track type: {ttype}")
            continue
        type_counters[ttype] = type_counters.get(ttype, 0) + 1
        index = type_counters[ttype]
        args.append("--edit")
        args.append(f"track:{sel}{index}")
        args.append("--set")
        args.append(f"name={u['name']}")
        args.append("--set")
        args.append(f"language={u['language']}")
        args.append("--set")
        args.append(f"flag-default={'yes' if u['default'] else 'no'}")
        args.append("--set")
        args.append(f"flag-forced={'yes' if u['forced'] else 'no'}")

    _run_mkvpropedit(args, media.output_path)
    log.info(f"Updated metadata (title + tracks): {media.output_path}")


def remove_image_attachments(
    media: MediaFile, config: Config, dry_run: bool = False
) -> None:
    """Delete every image/cover attachment from the MKV via mkvpropedit."""
    image_atts = media.image_attachments
    if not image_atts:
        return

    if dry_run:
        for att in image_atts:
            log.info(
                f"[DRY-RUN] Would delete attachment id={att.get('id')} "
                f"({att.get('content_type')})"
            )
        return

    args: list[str] = [str(config.mkvpropedit_path), str(media.output_path)]
    for att in image_atts:
        att_id = att.get("id")
        if att_id is None:
            continue
        args.append("--delete-attachment")
        args.append(str(att_id))

    _run_mkvpropedit(args, media.output_path)
    log.info(f"Removed {len(image_atts)} image attachment(s): {media.output_path}")


def _run_mkvpropedit(args: list[str], target: Path) -> None:
    log.debug(f"Running: {' '.join(args)}")
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        log.error(f"mkvpropedit failed: {exc.stderr}")
        raise ValidationError(f"mkvpropedit failed: {exc.stderr}")
    except FileNotFoundError as exc:
        raise ValidationError(
            f"mkvpropedit binary not found: {args[0]}"
        ) from exc
