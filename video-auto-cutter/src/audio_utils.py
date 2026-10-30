from __future__ import annotations

from pathlib import Path
from typing import Any


def build_audio_output_path(video_path: Path, target_dir: Path) -> Path:
    """Return a stable WAV path for extracted audio."""
    return target_dir / f"{video_path.stem}_audio.wav"


def estimate_speech_density(segments: list[dict[str, Any]], duration: float) -> float:
    """Estimate transcript density as words per second."""
    if duration <= 0:
        return 0.0
    words = sum(len(str(segment.get("text", "")).split()) for segment in segments)
    return round(words / duration, 3)
