from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .utils import write_json


def build_clip_metadata(
    *,
    source_video: str,
    clip_id: str,
    start: float,
    end: float,
    duration: float,
    text: str,
    hook: str,
    cta: str,
    caption: str,
    hashtags: list[str],
    scores: dict[str, Any],
    reason: str,
    files: dict[str, str],
) -> dict[str, Any]:
    """Build metadata payload for a clip."""
    return {
        "source_video": source_video,
        "clip_id": clip_id,
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(duration, 3),
        "text": text,
        "hook": hook,
        "cta": cta,
        "caption": caption,
        "hashtags": hashtags,
        **scores,
        "reason": reason,
        "files": files,
    }


def write_metadata(path: Path, payload: dict[str, Any]) -> Path:
    """Write metadata JSON."""
    write_json(path, payload)
    return path


def copy_variant_to_bucket(source_path: Path, bucket_dir: Path, target_name: str) -> Path:
    """Copy a rendered variant into a target bucket."""
    bucket_dir.mkdir(parents=True, exist_ok=True)
    target_path = bucket_dir / target_name
    shutil.copy2(source_path, target_path)
    return target_path
