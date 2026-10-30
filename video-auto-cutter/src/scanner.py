from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Iterable

from .utils import compute_file_signature


COPY_SUFFIX_PATTERN = re.compile(r" \(\d+\)$")


@dataclass(frozen=True)
class VideoFile:
    """Discovered source video with signature and source root."""

    path: Path
    source_root: Path
    signature: str


def _normalize_name(path: Path) -> str:
    return f"{COPY_SUFFIX_PATTERN.sub('', path.stem)}{path.suffix.lower()}"


def _prefer_candidate(existing: Path, candidate: Path) -> Path:
    existing_copy = bool(COPY_SUFFIX_PATTERN.search(existing.stem))
    candidate_copy = bool(COPY_SUFFIX_PATTERN.search(candidate.stem))
    if existing_copy and not candidate_copy:
        return candidate
    if candidate_copy and not existing_copy:
        return existing
    try:
        existing_size = existing.stat().st_size
        candidate_size = candidate.stat().st_size
    except OSError:
        return existing
    if candidate_size > existing_size:
        return candidate
    if candidate_size == existing_size and len(candidate.name) < len(existing.name):
        return candidate
    return existing


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def discover_videos(
    source_dirs: Iterable[Path],
    video_extensions: Iterable[str],
    processed_dir: Path,
    processed_manifest: dict[str, object],
    logger: logging.Logger,
    excluded_dirs: Iterable[Path] = (),
) -> list[VideoFile]:
    """Find new videos across source directories, deduplicating obvious copies."""
    allowed = {extension.lower() for extension in video_extensions}
    excluded = tuple(path.resolve() for path in excluded_dirs)
    deduped: dict[str, tuple[Path, Path]] = {}

    for root in source_dirs:
        if not root.exists():
            continue
        root_resolved = root.resolve()
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in allowed:
                continue
            resolved = path.resolve()
            if any(_is_inside(resolved, blocked) for blocked in excluded):
                continue

            relative_name = str(path.relative_to(root)).replace("\\", "/")
            key = f"{root_resolved}::{_normalize_name(Path(relative_name))}"
            existing = deduped.get(key)
            deduped[key] = (root, path) if existing is None else (root, _prefer_candidate(existing[1], path))

    found: list[VideoFile] = []
    seen_signatures: set[str] = set()
    for _, (root, path) in sorted(deduped.items(), key=lambda item: item[1][1].name.lower()):
        signature = compute_file_signature(path)
        if signature in processed_manifest:
            logger.info("Skipping %s because its signature is already in the manifest.", path.name)
            continue
        if signature in seen_signatures:
            logger.info("Skipping %s because an identical file was already queued.", path.name)
            continue
        seen_signatures.add(signature)
        found.append(VideoFile(path=path, source_root=root, signature=signature))
    return found
