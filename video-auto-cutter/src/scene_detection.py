from __future__ import annotations

import logging
from pathlib import Path

from .ffmpeg_utils import detect_scene_changes


def detect_scene_points(
    video_path: Path,
    threshold: float = 0.35,
    limit: int = 200,
    logger: logging.Logger | None = None,
) -> list[float]:
    """Detect scene changes using FFmpeg."""
    return detect_scene_changes(video_path, threshold=threshold, limit=limit, logger=logger)


def snap_timestamp_to_scene(timestamp: float, scene_points: list[float], tolerance: float = 2.5) -> float:
    """Snap a timestamp to the nearest scene point when it is close enough."""
    if not scene_points:
        return timestamp
    nearest = min(scene_points, key=lambda point: abs(point - timestamp))
    return nearest if abs(nearest - timestamp) <= tolerance else timestamp
