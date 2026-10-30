from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from typing import Any


def _neutral_scores() -> dict[str, float | str]:
    return {
        "motion_score": 60.0,
        "brightness_score": 60.0,
        "sharpness_score": 60.0,
        "visual_score": 60.0,
        "reason": "opencv unavailable, neutral visual scoring",
    }


def analyze_segment_visuals(video_path: Path, start: float, duration: float) -> dict[str, float | str]:
    """Analyze visual qualities of a segment."""
    if find_spec("cv2") is None:
        return _neutral_scores()

    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception:
        return _neutral_scores()

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return _neutral_scores()

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    start_frame = int(max(start, 0) * fps)
    end_frame = int(max(start + duration, start) * fps)
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    previous_gray = None
    motion_values: list[float] = []
    brightness_values: list[float] = []
    sharpness_values: list[float] = []
    frame_index = start_frame
    sample_step = max(1, int(fps // 2))

    while frame_index <= end_frame:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        if (frame_index - start_frame) % sample_step != 0:
            frame_index += 1
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness_values.append(float(gray.mean()))
        sharpness_values.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        if previous_gray is not None:
            motion_values.append(float(cv2.absdiff(gray, previous_gray).mean()))
        previous_gray = gray
        frame_index += 1

    capture.release()
    if not brightness_values:
        return _neutral_scores()

    motion_score = min(100.0, (sum(motion_values) / max(len(motion_values), 1)) * 2.4)
    brightness_score = min(100.0, (sum(brightness_values) / len(brightness_values)) / 2.55)
    sharpness_score = min(100.0, (sum(sharpness_values) / len(sharpness_values)) / 8.0)
    visual_score = round(motion_score * 0.4 + brightness_score * 0.3 + sharpness_score * 0.3, 2)
    reason = "good motion and acceptable brightness" if visual_score >= 65 else "neutral visual quality"
    return {
        "motion_score": round(motion_score, 2),
        "brightness_score": round(brightness_score, 2),
        "sharpness_score": round(sharpness_score, 2),
        "visual_score": visual_score,
        "reason": reason,
    }


def score_motion(video_path: Path, start: float, duration: float) -> float:
    """Return motion score only."""
    return float(analyze_segment_visuals(video_path, start, duration)["motion_score"])


def score_brightness(video_path: Path, start: float, duration: float) -> float:
    """Return brightness score only."""
    return float(analyze_segment_visuals(video_path, start, duration)["brightness_score"])


def select_segments_by_visual_score(video_path: Path, candidates: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """Sort candidates by visual score and keep the top ones."""
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        visuals = analyze_segment_visuals(video_path, float(candidate["start"]), float(candidate["duration"]))
        enriched = dict(candidate)
        enriched.update(visuals)
        scored.append(enriched)
    scored.sort(key=lambda item: (-float(item.get("visual_score", 0)), float(item.get("start", 0))))
    return scored[:top_n]
