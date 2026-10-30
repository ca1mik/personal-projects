from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


BAD_START_PATTERN = re.compile(
    r"^(всем привет|привет|сегодня поговорим|ну|ээ+|эм+|короче|итак|в этом видео)\b[\s,:-]*",
    re.IGNORECASE,
)
BAD_END_PATTERN = re.compile(r"(ну вот|как бы|в общем|короче|вот так)\.?$", re.IGNORECASE)
GOOD_KEYWORDS = (
    "ошибка",
    "почему",
    "секрет",
    "результат",
    "как",
    "главное",
    "запомни",
    "до",
    "после",
    "разбор",
    "миф",
    "нельзя",
    "важно",
    "правда",
    "ошибаются",
)


@dataclass(frozen=True)
class ClipCandidate:
    """Candidate short-form clip."""

    start: float
    end: float
    duration: float
    title: str
    text: str
    reason: str
    selection_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "title": self.title,
            "text": self.text,
            "reason": self.reason,
            "selection_score": round(self.selection_score, 3),
        }


def merge_segments_into_candidates(
    segments: list[dict[str, Any]],
    min_duration: int,
    max_duration: int,
) -> list[ClipCandidate]:
    """Merge transcript segments into candidate blocks."""
    cleaned = [
        segment
        for segment in segments
        if float(segment.get("end", 0)) > float(segment.get("start", 0))
        and str(segment.get("text", "")).strip()
    ]
    candidates: list[ClipCandidate] = []
    for start_index, first_segment in enumerate(cleaned):
        block_start = float(first_segment["start"])
        block_text: list[str] = []
        for segment in cleaned[start_index:]:
            block_end = float(segment["end"])
            duration = block_end - block_start
            if duration > max_duration:
                break
            block_text.append(str(segment["text"]).strip())
            if duration >= min_duration:
                text = " ".join(block_text).strip()
                candidates.append(
                    ClipCandidate(
                        start=block_start,
                        end=block_end,
                        duration=duration,
                        title="",
                        text=text,
                        reason="merged transcript block",
                    )
                )
    return candidates


def trim_bad_start(candidate: ClipCandidate) -> ClipCandidate:
    """Trim weak greetings and filler at the beginning of a candidate."""
    text = BAD_START_PATTERN.sub("", candidate.text).strip()
    start = candidate.start
    if text != candidate.text:
        start = min(candidate.end - 1.0, candidate.start + min(1.5, candidate.duration * 0.12))
    duration = max(candidate.end - start, 0.5)
    return ClipCandidate(
        start=start,
        end=candidate.end,
        duration=duration,
        title=candidate.title,
        text=text or candidate.text,
        reason=candidate.reason,
    )


def trim_bad_end(candidate: ClipCandidate) -> ClipCandidate:
    """Trim weak filler at the end of a candidate."""
    text = BAD_END_PATTERN.sub("", candidate.text).strip()
    end = candidate.end
    if text != candidate.text:
        end = max(candidate.start + 0.5, candidate.end - min(1.0, candidate.duration * 0.1))
    duration = max(end - candidate.start, 0.5)
    return ClipCandidate(
        start=candidate.start,
        end=end,
        duration=duration,
        title=candidate.title,
        text=text or candidate.text,
        reason=candidate.reason,
    )


def _selection_score(candidate: ClipCandidate, video_duration: float) -> tuple[float, str]:
    text = candidate.text.lower()
    words = [word for word in text.split() if word]
    keyword_hits = sum(keyword in text for keyword in GOOD_KEYWORDS)
    punctuation_bonus = candidate.text.count("?") * 3 + candidate.text.count("!") * 3
    density = len(words) / max(candidate.duration, 1)
    completeness_bonus = 8 if candidate.text.endswith((".", "!", "?")) else 0
    intro_penalty = 12 if BAD_START_PATTERN.search(candidate.text.lower()) else 0
    boundary_penalty = 8 if candidate.start <= min(5, video_duration * 0.05) else 0
    score = len(words) * 0.7 + keyword_hits * 6 + punctuation_bonus + density * 3 + completeness_bonus
    score -= intro_penalty + boundary_penalty
    if keyword_hits >= 2:
        reason = "strong payoff + keyword-rich fragment"
    elif punctuation_bonus:
        reason = "emotional or attention-grabbing speech"
    else:
        reason = "dense explanatory fragment"
    return score, reason


def _has_heavy_overlap(candidate: ClipCandidate, selected: list[ClipCandidate]) -> bool:
    for existing in selected:
        overlap = max(0.0, min(candidate.end, existing.end) - max(candidate.start, existing.start))
        if overlap / min(candidate.duration, existing.duration) > 0.45:
            return True
    return False


def select_clips_from_transcript(segments: list[dict[str, Any]], video_duration: float, config: Any) -> list[ClipCandidate]:
    """Select the best transcript-driven clips."""
    raw_candidates = merge_segments_into_candidates(
        segments,
        min_duration=config.shorts_duration_min,
        max_duration=config.shorts_duration_max,
    )
    scored: list[ClipCandidate] = []
    for index, raw in enumerate(raw_candidates, start=1):
        trimmed = trim_bad_end(trim_bad_start(raw))
        score, reason = _selection_score(trimmed, video_duration)
        scored.append(
            ClipCandidate(
                start=trimmed.start,
                end=trimmed.end,
                duration=trimmed.duration,
                title=f"clip_{index:02d}",
                text=trimmed.text,
                reason=reason,
                selection_score=score,
            )
        )

    scored.sort(key=lambda item: (-item.selection_score, item.start))
    selected: list[ClipCandidate] = []
    for candidate in scored:
        if _has_heavy_overlap(candidate, selected):
            continue
        selected.append(candidate)
        if len(selected) >= config.clips_per_video:
            break

    return [
        ClipCandidate(
            start=item.start,
            end=item.end,
            duration=item.duration,
            title=f"clip_{index:02d}",
            text=item.text,
            reason=item.reason,
            selection_score=item.selection_score,
        )
        for index, item in enumerate(selected, start=1)
    ]


def select_fallback_clips(video_duration: float, config: Any) -> list[ClipCandidate]:
    """Fallback selection for videos without transcript."""
    if video_duration <= config.shorts_duration_min:
        return [
            ClipCandidate(
                start=0.0,
                end=video_duration,
                duration=video_duration,
                title="clip_01",
                text="",
                reason="full-length fallback",
                selection_score=1.0,
            )
        ]

    safe_start = video_duration * 0.05
    safe_end = video_duration * 0.95
    usable_duration = max(safe_end - safe_start, config.shorts_duration_min)
    target_duration = min(max(config.ideal_duration_min, 30), config.shorts_duration_max, usable_duration)
    clip_count = max(1, config.clips_per_video)
    last_start = max(safe_start, safe_end - target_duration)
    step = 0 if clip_count == 1 else (last_start - safe_start) / max(clip_count - 1, 1)

    clips: list[ClipCandidate] = []
    for index in range(clip_count):
        start = safe_start + step * index if clip_count > 1 else (safe_start + last_start) / 2
        end = min(video_duration, start + target_duration)
        clips.append(
            ClipCandidate(
                start=round(start, 3),
                end=round(end, 3),
                duration=round(end - start, 3),
                title=f"clip_{index + 1:02d}",
                text="",
                reason="evenly spaced fallback clip",
                selection_score=0.0,
            )
        )
    return clips
