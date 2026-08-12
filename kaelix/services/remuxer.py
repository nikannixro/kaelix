"""Remuxing helper for subtitle replacement/addition using mkvmerge."""
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
) -> None:
    """Remux `input_mkv` into `output_mkv`, rebuilding its subtitle tracks.

    Keeps only `keep_subtitle_ids` from the source, appends each file in
    `external_subs` (keys: file, name, language, default, forced), and strips
    all attachments.
    """
    output_mkv.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [str(mkvmerge_path), "-o", str(output_mkv)]

    # These options apply to the next input file: the source MKV.
    if keep_subtitle_ids:
        cmd += ["--subtitle-tracks", ",".join(str(i) for i in keep_subtitle_ids)]
    else:
        cmd.append("--no-subtitles")
    cmd += ["--no-attachments", str(input_mkv)]

    # Each external subtitle carries its own metadata (track 0 of that file).
    for ext in external_subs:
        cmd += [
            "--language", f"0:{ext['language']}",
            "--track-name", f"0:{ext['name']}",
            "--default-track-flag", f"0:{'yes' if ext['default'] else 'no'}",
            "--forced-display-flag", f"0:{'yes' if ext['forced'] else 'no'}",
            str(ext["file"]),
        ]

    log.debug(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(
            cmd, check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=3600,
        )
    except subprocess.CalledProcessError as exc:
        log.error(f"mkvmerge failed: {exc.stderr}")
        raise ValidationError(f"mkvmerge failed: {exc.stderr}") from exc
    except FileNotFoundError as exc:
        raise ValidationError(f"mkvmerge binary not found: {mkvmerge_path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(f"mkvmerge timed out after {exc.timeout}s") from exc

    log.info(f"Remuxed subtitles: {output_mkv}")
