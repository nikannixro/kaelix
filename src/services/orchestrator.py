"""Batch processing loop that ties all services together."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from ..config import Config
from ..models.media_file import MediaFile
from ..prompts.questions import (
    confirm_continue_after_error,
    prompt_audio_language_for_file,
    show_summary,
)
from ..utils.logger import get_logger
from .identifier import build_media_file
from .metadata_editor import apply_metadata_to_tracks, remove_image_attachments
from .remuxer import remux_subtitles
from .renamer import populate_media_file_from_filename, validate_parse
from .subtitle_matcher import find_english_subtitle_match, find_persian_subtitle_match

log = get_logger(__name__)


class BatchOrchestrator:
    """Coordinates the per-file processing of an entire library."""

    def __init__(self, config: Config):
        self.config = config
        self.stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self) -> dict:
        """Walk the source directory and process every .mkv file."""
        files = sorted(self.config.source_dir.rglob("*.mkv"))
        self.stats["total"] = len(files)
        log.info(f"Found {len(files)} MKV file(s) under {self.config.source_dir}")

        for src in files:
            try:
                result = self._process_one(src)
                if result == "skipped":
                    self.stats["skipped"] += 1
                else:
                    self.stats["success"] += 1
            except KeyboardInterrupt:
                log.warning("Interrupted by user.")
                raise
            except Exception as exc:  # noqa: BLE001
                log.error(f"Failed to process {src}: {exc}")
                self.stats["failed"] += 1
                if self.config.non_interactive:
                    continue
                if not confirm_continue_after_error(src.name, str(exc)):
                    log.warning("Aborting batch by user request.")
                    break

        show_summary(
            self.stats["total"],
            self.stats["success"],
            self.stats["failed"],
            self.stats["skipped"],
        )
        return self.stats

    # ------------------------------------------------------------------
    # Per-file processing
    # ------------------------------------------------------------------
    def _process_one(self, src: Path) -> str:
        """Process a single file. Returns 'ok' or 'skipped'."""
        log.info(f"--- Processing: {src}")

        # 1. Identify tracks + attachments
        media = build_media_file(src, self.config.mkvmerge_path)

        # 2. Parse filename
        populate_media_file_from_filename(media, self.config.ffprobe_path)
        for w in validate_parse(media):
            log.warning(f"{src.name}: {w}")

        # 3. Compute output path (preserving relative folder structure)
        rel = src.relative_to(self.config.source_dir)
        out_dir = self.config.output_dir / rel.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        media.output_path = out_dir / media.target_filename
        media.relative_path = rel

        # Skip if output already exists
        if media.output_path.exists():
            log.warning(f"Output exists, skipping: {media.output_path}")
            return "skipped"

        log.info(f"Target: {media.target_filename}")
        log.info(f"  title: {media.segment_title!r}")
        log.info(
            f"  tracks: {len(media.video_tracks)}V/{len(media.audio_tracks)}A/"
            f"{len(media.subtitle_tracks)}S  attachments: {len(media.attachments)}"
        )

        # 4. Resolve per-file audio language (only prompt if multiple audio tracks)
        self._resolve_audio(media)

        # 5. Plan subtitle remux (deterministic, based on external dirs)
        remux_plan = self._plan_subtitles(media)

        if self.config.dry_run:
            log.info("[DRY-RUN] Simulating operations only.")
            apply_metadata_to_tracks(media, self.config, dry_run=True)
            remove_image_attachments(media, self.config, dry_run=True)
            self._log_remux_plan(remux_plan)
            return "ok"

        # 6. Copy source to output (originals are never touched)
        log.info(f"Copying to {media.output_path}")
        shutil.copy2(src, media.output_path)

        try:
            # 7. Subtitle replacement/addition via remux (operates on the copy)
            if remux_plan is not None:
                self._perform_remux(media, remux_plan)

            # 8. Apply metadata (title + track names/langs/flags) via mkvpropedit
            apply_metadata_to_tracks(media, self.config, dry_run=False)

            # 9. Remove image/cover attachments via mkvpropedit
            remove_image_attachments(media, self.config, dry_run=False)
        except Exception:
            # Clean up partial output on failure (never mask the original error).
            try:
                if media.output_path.exists():
                    media.output_path.unlink()
            except OSError as cleanup_err:
                log.warning(f"Could not remove partial output {media.output_path}: {cleanup_err}")
            raise

        log.info(f"Done: {media.output_path}")
        return "ok"

    # ------------------------------------------------------------------
    # Audio decision (hybrid)
    # ------------------------------------------------------------------
    def _resolve_audio(self, media: MediaFile) -> None:
        config = self.config
        if len(media.audio_tracks) > 1 and not config.non_interactive:
            media.selected_audio_language = prompt_audio_language_for_file(
                media.source_path.name, config.audio_language
            )
        else:
            media.selected_audio_language = config.audio_language

    # ------------------------------------------------------------------
    # Subtitle planning (deterministic)
    # ------------------------------------------------------------------
    def _plan_subtitles(self, media: MediaFile) -> Optional[dict]:
        """Decide whether a remux is required for subtitle changes.

        Returns a remux plan dict, or None if no remux is needed.
        """
        config = self.config

        # Look up external subtitle files by the configured naming patterns.
        persian_ext = None
        english_ext = None
        english_is_sdh = False
        if config.persian_subtitle_dir is not None:
            persian_ext = find_persian_subtitle_match(media, config.persian_subtitle_dir)
        if config.english_subtitle_dir is not None:
            eng_result = find_english_subtitle_match(media, config.english_subtitle_dir)
            if eng_result is not None:
                english_ext, english_is_sdh = eng_result

        # If no external subtitle is provided at all, no remux is needed:
        # existing subtitles are simply renamed via mkvpropedit.
        if persian_ext is None and english_ext is None:
            return None

        # Determine which existing subtitle track IDs to KEEP.
        #   - Drop existing Persian if an external Persian is provided.
        #   - Drop existing English if an external English is provided.
        #   - Always keep subtitles in other languages.
        keep_ids: list[int] = []
        for t in media.subtitle_tracks:
            if t.is_persian and persian_ext is not None:
                continue  # will be replaced
            if t.is_english and english_ext is not None:
                continue  # will be replaced
            keep_ids.append(t.id)

        external_subs: list[dict] = []
        if persian_ext is not None:
            external_subs.append({
                "file": persian_ext,
                "name": config.subtitle_name,          # "Subtitle"
                "language": "fa",
                "default": config.subtitle_default,    # True
                "forced": config.subtitle_forced,      # True
            })
        if english_ext is not None:
            english_name = (
                config.english_subtitle_name_sdh
                if english_is_sdh
                else config.english_subtitle_name_non_sdh
            )
            external_subs.append({
                "file": english_ext,
                "name": english_name,
                "language": "en",
                "default": config.english_subtitle_default,  # False
                "forced": config.english_subtitle_forced,    # False
            })

        return {
            "keep_ids": keep_ids,
            "external_subs": external_subs,
            "persian_ext": persian_ext,
            "english_ext": english_ext,
            "english_is_sdh": english_is_sdh,
        }

    def _log_remux_plan(self, plan: Optional[dict]) -> None:
        if plan is None:
            return
        log.info(f"[DRY-RUN] Would remux: keep_ids={plan['keep_ids']}")
        for ext in plan["external_subs"]:
            log.info(
                f"[DRY-RUN]   add external sub: {ext['file'].name} "
                f"(name={ext['name']!r}, lang={ext['language']})"
            )

    # ------------------------------------------------------------------
    # Remux execution
    # ------------------------------------------------------------------
    def _perform_remux(self, media: MediaFile, plan: dict) -> None:
        tmp = media.output_path.with_suffix(".remux.tmp.mkv")
        remux_subtitles(
            input_mkv=media.output_path,
            output_mkv=tmp,
            keep_subtitle_ids=plan["keep_ids"],
            external_subs=plan["external_subs"],
            mkvmerge_path=self.config.mkvmerge_path,
            dry_run=self.config.dry_run,
        )
        tmp.replace(media.output_path)
        # Re-identify tracks + attachments because the file changed.
        refreshed = build_media_file(media.output_path, self.config.mkvmerge_path)
        media.tracks = refreshed.tracks
        media.attachments = refreshed.attachments
