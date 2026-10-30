from __future__ import annotations

from pathlib import Path

from .ffmpeg_utils import make_thumbnail


def choose_thumbnail_title(hook: str, fallback_text: str) -> str:
    """Choose a short thumbnail title."""
    base = hook or fallback_text or "Short clip"
    words = base.strip().split()
    return " ".join(words[:6]).strip()


def render_thumbnail(video_path: Path, output_path: Path, timestamp: float, hook: str, fallback_text: str) -> Path:
    """Render a thumbnail with a short title overlay."""
    return make_thumbnail(video_path, output_path, timestamp, title_text=choose_thumbnail_title(hook, fallback_text))
