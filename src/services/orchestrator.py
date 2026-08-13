"""Batch processing loop that ties all services together."""
from __future__ import annotations

import shutil
from importlib import import_module
from pathlib import Path

from ..config import Config
from ..models.media_file import MediaFile
from ..prompts.questions import (
    confirm_continue_after_error,
    prompt_audio_language_for_file,
    show_summary,
)
from ..utils.logger import get_logger
from .identifier import build_media_file
from .remuxer import remux_subtitles
from .renamer import populate_media_file_from_filename, validate_parse

_meta = import_module(".metadata editor", __package__)
apply_metadata_to_tracks = _meta.apply_metadata_to_tracks
remove_image_attachments = _meta.remove_image_attachments
_sub = import_module(".subtitle matcher", __package__)
find_english_subtitle_match = _sub.find_english_subtitle_match
find_persian_subtitle_match = _sub.find_persian_subtitle_match

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

        if not files:
            log.warning("No MKV files found in the source directory.")
            show_summary(**self.stats)
            return self.stats

        for src in files:
            try:
                result = self._process_one(src)
            except KeyboardInterrupt:
                log.warning("Interrupted by user.")
                raise
            except Exception as exc:  # noqa: BLE001 - one bad file must not kill the batch
                log.error(f"Failed to process {src}: {exc}")
                self.stats["failed"] += 1
                if self.config.non_interactive:
                    continue
                if not confirm_continue_after_error(src.name, str(exc)):
                    log.warning("Aborting batch by user request.")
                    break
            else:
                key = "skipped" if result == "skipped" else "success"
                self.stats[key] += 1

        show_summary(**self.stats)
        return self.stats

    # ------------------------------------------------------------------
    # Per-file processing
    # ------------------------------------------------------------------
    def _process_one(self, src: Path) -> str:
        """Process a single file. Returns 'ok' or 'skipped'."""
        log.info(f"--- Processing: {src}")

        media = build_media_file(src, self.config.mkvmerge_path)

        populate_media_file_from_filename(media, self.config.ffprobe_path)
        for w in validate_parse(media):
            log.warning(f"{src.name}: {w}")

        # Output path mirrors the source folder structure.
        rel = src.relative_to(self.config.source_dir)
        media.relative_path = rel
        media.output_path = self.config.output_dir / rel.parent / media.target_filename

        if media.output_path.exists():
            log.warning(f"Output exists, skipping: {media.output_path}")
            return "skipped"

        log.info(f"Target: {media.target_filename}")
        log.info(f"  title: {media.segment_title!r}")
        log.info(
            f"  tracks: {len(media.video_tracks)}V/{len(media.audio_tracks)}A/"
            f"{len(media.subtitle_tracks)}S  attachments: {len(media.attachments)}"
        )

        self._resolve_audio(media)
        remux_plan = self._plan_subtitles(media)

        if self.config.dry_run:
            log.info("[DRY-RUN] Simulating operations only.")
            apply_metadata_to_tracks(media, self.config, dry_run=True)
            remove_image_attachments(media, self.config, dry_run=True)
            self._log_remux_plan(remux_plan)
            return "ok"

        media.output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if remux_plan is not None:
                # mkvmerge reads the source and writes the output in one pass.
                # Copying first would move the whole file twice for no gain;
                # the source is only ever read.
                self._remux_to_output(media, remux_plan)
            else:
                # No track changes needed, so a copy plus in-place header edits
                # is far cheaper than a full remux.
                log.info(f"Copying to {media.output_path}")
                shutil.copy2(src, media.output_path)

            apply_metadata_to_tracks(media, self.config, dry_run=False)
            remove_image_attachments(media, self.config, dry_run=False)
        except BaseException:
            # Includes KeyboardInterrupt: never leave a half-written output behind.
            self._discard_partial_output(media)
            raise

        log.info(f"Done: {media.output_path}")
        return "ok"

    @staticmethod
    def _discard_partial_output(media: MediaFile) -> None:
        try:
            media.output_path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning(f"Could not remove partial output {media.output_path}: {exc}")

    # ------------------------------------------------------------------
    # Audio decision (hybrid)
    # ------------------------------------------------------------------
    def _resolve_audio(self, media: MediaFile) -> None:
        if len(media.audio_tracks) > 1 and not self.config.non_interactive:
            media.selected_audio_language = prompt_audio_language_for_file(
                media.source_path.name, self.config.audio_language
            )
        else:
            media.selected_audio_language = self.config.audio_language

    # ------------------------------------------------------------------
    # Subtitle planning (deterministic)
    # ------------------------------------------------------------------
    def _plan_subtitles(self, media: MediaFile) -> dict | None:
        """Return a remux plan, or None when the subtitle layout is already correct."""
        config = self.config

        persian_ext = None
        if config.persian_subtitle_dir is not None:
            persian_ext = find_persian_subtitle_match(media, config.persian_subtitle_dir)

        english_ext = None
        english_is_sdh = False
        if config.english_subtitle_dir is not None:
            match = find_english_subtitle_match(media, config.english_subtitle_dir)
            if match is not None:
                english_ext, english_is_sdh = match

        # Only English and Persian subtitles are kept; every other language
        # (including untagged 'und') is dropped from the output entirely.
        unwanted = [t for t in media.subtitle_tracks if not (t.is_english or t.is_persian)]

        keep_ids = [
            t.id for t in media.subtitle_tracks
            if (t.is_english or t.is_persian)
            and not (t.is_persian and persian_ext is not None)
            and not (t.is_english and english_ext is not None)
        ]

        external_subs: list[dict] = []
        if persian_ext is not None:
            external_subs.append({
                "file": persian_ext,
                "name": config.subtitle_name,
                "language": "fa",
                "default": config.subtitle_default,
                "forced": config.subtitle_forced,
            })
        if english_ext is not None:
            external_subs.append({
                "file": english_ext,
                "name": (
                    config.english_subtitle_name_sdh
                    if english_is_sdh
                    else config.english_subtitle_name_non_sdh
                ),
                "language": "en",
                "default": config.english_subtitle_default,
                "forced": config.english_subtitle_forced,
            })

        # Nothing to add and nothing to drop: mkvpropedit can relabel the
        # existing tracks in place, which is far cheaper than a remux.
        if not external_subs and not unwanted:
            return None

        if unwanted:
            log.info(
                f"  dropping {len(unwanted)} non-English/Persian subtitle(s): "
                + ", ".join(f"#{t.id} ({t.language})" for t in unwanted)
            )

        return {"keep_ids": keep_ids, "external_subs": external_subs, "dropped": unwanted}

    @staticmethod
    def _log_remux_plan(plan: dict | None) -> None:
        if plan is None:
            return
        log.info(f"[DRY-RUN] Would remux: keep subtitle ids={plan['keep_ids']}")
        for t in plan["dropped"]:
            log.info(f"[DRY-RUN]   drop subtitle #{t.id} (lang={t.language})")
        for ext in plan["external_subs"]:
            log.info(
                f"[DRY-RUN]   add external sub: {ext['file'].name} "
                f"(name={ext['name']!r}, lang={ext['language']})"
            )

    # ------------------------------------------------------------------
    # Remux execution
    # ------------------------------------------------------------------
    def _remux_to_output(self, media: MediaFile, plan: dict) -> None:
        """Remux the source straight into the output path, then re-identify."""
        remux_subtitles(
            input_mkv=media.source_path,
            output_mkv=media.output_path,
            keep_subtitle_ids=plan["keep_ids"],
            external_subs=plan["external_subs"],
            mkvmerge_path=self.config.mkvmerge_path,
        )
        # Track IDs shifted, so re-identify before editing metadata.
        refreshed = build_media_file(media.output_path, self.config.mkvmerge_path)
        media.tracks = refreshed.tracks
        media.attachments = refreshed.attachments
