from __future__ import annotations

from pathlib import Path

SUPPORTED_MEDIA_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".ogg"}
VOICE_EXTENSIONS = {".ogg"}


def is_media_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS


def is_voice_file(path: Path) -> bool:
    return path.suffix.lower() in VOICE_EXTENSIONS
