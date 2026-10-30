from __future__ import annotations

from typing import Any

from .visual_scoring import select_segments_by_visual_score


def _even_segments(
    video_duration: float,
    *,
    count: int,
    min_duration: float,
    max_duration: float,
    start_ratio: float = 0.08,
    end_ratio: float = 0.92,
) -> list[dict[str, Any]]:
    safe_start = video_duration * start_ratio
    safe_end = video_duration * end_ratio
    usable = max(safe_end - safe_start, min_duration)
    duration = min(max_duration, max(min_duration, usable / max(count, 1)))
    last_start = max(safe_start, safe_end - duration)
    step = 0 if count <= 1 else (last_start - safe_start) / max(count - 1, 1)
    items: list[dict[str, Any]] = []
    for index in range(count):
        start = safe_start + step * index if count > 1 else (safe_start + last_start) / 2
        items.append({"start": round(start, 3), "duration": round(min(duration, video_duration - start), 3)})
    return items


def select_tattoo_process_clips(video_path, video_duration, config):
    """Select longer tattoo process clips from the middle of the source."""
    candidates = _even_segments(
        video_duration,
        count=min(max(config.clips_per_video, 5), 8),
        min_duration=12,
        max_duration=min(30, max(12, config.ideal_duration_max)),
        start_ratio=0.12,
        end_ratio=0.88,
    )
    return select_segments_by_visual_score(video_path, candidates, top_n=min(len(candidates), 6))


def select_closeup_clips(video_path, video_duration, config):
    """Select short close-up style clips."""
    candidates = _even_segments(
        video_duration,
        count=min(max(config.clips_per_video, 6), 12),
        min_duration=6,
        max_duration=12,
        start_ratio=0.1,
        end_ratio=0.9,
    )
    return select_segments_by_visual_score(video_path, candidates, top_n=min(len(candidates), 8))


def select_satisfying_clips(video_path, video_duration, config):
    """Select motion-rich satisfying clips."""
    candidates = _even_segments(
        video_duration,
        count=min(max(config.clips_per_video, 6), 10),
        min_duration=8,
        max_duration=18,
        start_ratio=0.08,
        end_ratio=0.92,
    )
    return select_segments_by_visual_score(video_path, candidates, top_n=min(len(candidates), 6))


def select_before_process_after(video_path, video_duration, config):
    """Select before, process, and after segments."""
    del video_path, config
    before = {"label": "before", "start": round(max(2.0, video_duration * 0.03), 3), "duration": round(min(8.0, max(video_duration * 0.08, 5.0)), 3)}
    process = {"label": "process", "start": round(max(video_duration * 0.45, before["start"] + before["duration"]), 3), "duration": round(min(12.0, max(video_duration * 0.1, 8.0)), 3)}
    after_duration = round(min(8.0, max(video_duration * 0.08, 5.0)), 3)
    after_start = round(max(video_duration * 0.82, video_duration - after_duration - 1.0), 3)
    after = {"label": "after", "start": after_start, "duration": after_duration}
    return {"before": before, "process": process, "after": after}


def select_portfolio_clips(video_path, video_duration, config):
    """Select clean portfolio clips with softer timing."""
    candidates = _even_segments(
        video_duration,
        count=min(max(3, config.clips_per_video // 2), 6),
        min_duration=7,
        max_duration=15,
        start_ratio=0.15,
        end_ratio=0.95,
    )
    return select_segments_by_visual_score(video_path, candidates, top_n=min(len(candidates), 4))
