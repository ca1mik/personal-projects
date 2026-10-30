from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_content_type(
    video_path: Path,
    transcript: dict[str, Any] | None = None,
    video_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect likely content type for a source video."""
    transcript = transcript or {}
    video_info = video_info or {}
    duration = float(video_info.get("duration", 0) or 0)
    has_audio = bool(video_info.get("has_audio", False))
    words = len(str(transcript.get("text", "")).split())
    has_speech = has_audio and words > 50
    is_portfolio_shot = 5 <= duration <= 20 and words < 20
    is_tattoo_process = duration > 60 and not has_speech or (duration > 25 and has_audio)
    recommended_modes: list[str] = []
    reasons: list[str] = []

    if has_speech:
        recommended_modes.append("talking")
        reasons.append("speech detected")
    if is_tattoo_process:
        recommended_modes.append("tattoo")
        reasons.append("long tattoo-style process video")
    if is_portfolio_shot:
        recommended_modes.append("portfolio")
        reasons.append("short portfolio-like shot")
    if duration > 180:
        recommended_modes.append("timelapse")
        reasons.append("long enough for timelapse")
    if not recommended_modes:
        recommended_modes.append("tattoo")
        reasons.append("fallback to tattoo mode")

    return {
        "source_name": video_path.name,
        "has_speech": has_speech,
        "is_tattoo_process": is_tattoo_process,
        "is_portfolio_shot": is_portfolio_shot,
        "recommended_modes": recommended_modes,
        "reason": " + ".join(reasons),
    }
