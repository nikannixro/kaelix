"""Remuxing helpers for subtitle replacement/addition using mkvmerge."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..utils.logger import get_logger
from ..utils.validators import ValidationError

log = get_logger(__name__)


def remux_subtitles(
    input_mkv: Path,
    output_mkv: Path,
    keep_subtitle_ids: list[int],
    external_subs: list[dict],
    mkvmerge_path: Path,
    dry_run: bool = False,
) -> None:
    """
    Remux an MKV keeping only `keep_subtitle_ids` subtitle tracks from the
    source, then append the external subtitle files described in
    `external_subs` (each a dict with keys: file, name, language, default, forced).

    All attachments are stripped from the output.
    """
    if dry_run:
        log.info(f"[DRY-RUN] Would remux {input_mkv}")
        log.info(f"[DRY-RUN]   keep subtitle ids: {keep_subtitle_ids}")
        for ext in external_subs:
            log.info(
                f"[DRY-RUN]   add external: {ext['file']} "
                f"(name={ext['name']!r}, lang={ext['language']}, "
                f"default={ext['default']}, forced={ext['forced']})"
            )
        return

    output_mkv.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [str(mkvmerge_path), "-o", str(output_mkv)]

    # Subtitle selection applies to the NEXT input file (the source MKV).
    if keep_subtitle_ids:
        cmd.append("--subtitle-tracks")
        cmd.append(",".join(str(i) for i in keep_subtitle_ids))
    else:
        cmd.append("--no-subtitles")

    # Strip attachments from the source.
    cmd.append("--no-attachments")
    cmd.append(str(input_mkv))

    # Append each external subtitle file with its own metadata.
    for ext in external_subs:
        cmd.append("--language")
        cmd.append(f"0:{ext['language']}")
        cmd.append("--track-name")
        cmd.append(f"0:{ext['name']}")
        cmd.append("--default-track-flag")
        cmd.append(f"0:{'yes' if ext['default'] else 'no'}")
        cmd.append("--forced-display-flag")
        cmd.append(f"0:{'yes' if ext['forced'] else 'no'}")
        cmd.append(str(ext["file"]))

    log.debug(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        log.error(f"mkvmerge failed: {exc.stderr}")
        raise ValidationError(f"mkvmerge failed: {exc.stderr}")
    except FileNotFoundError as exc:
        raise ValidationError(
            f"mkvmerge binary not found: {mkvmerge_path}"
        ) from exc

    log.info(f"Remuxed subtitles: {output_mkv}")
