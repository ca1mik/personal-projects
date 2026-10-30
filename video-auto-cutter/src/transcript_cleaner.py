from __future__ import annotations

import re
from typing import Any


FILLER_PATTERN = re.compile(r"\b(ээ+|эм+|ну|как бы|короче|типа|в общем|ну вот)\b", re.IGNORECASE)
SPACE_PATTERN = re.compile(r"\s+")


def normalize_segment_text(text: str) -> str:
    """Normalize punctuation, spaces, and filler words carefully."""
    cleaned = FILLER_PATTERN.sub(" ", text)
    cleaned = SPACE_PATTERN.sub(" ", cleaned).strip(" ,.-")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    return cleaned.strip()


def merge_short_segments(segments: list[dict[str, Any]], min_duration: float = 1.2) -> list[dict[str, Any]]:
    """Merge very short neighboring segments to reduce choppy subtitles."""
    merged: list[dict[str, Any]] = []
    for segment in segments:
        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        text = str(segment.get("text", "")).strip()
        if not text or end <= start:
            continue
        duration = end - start
        if merged and duration < min_duration:
            merged[-1]["end"] = end
            merged[-1]["text"] = f"{merged[-1]['text']} {text}".strip()
            continue
        merged.append({"start": start, "end": end, "text": text})
    return merged


def split_long_segments(segments: list[dict[str, Any]], max_words: int = 18) -> list[dict[str, Any]]:
    """Split long transcript segments into smaller reading-friendly chunks."""
    result: list[dict[str, Any]] = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        words = text.split()
        if len(words) <= max_words:
            result.append(segment)
            continue

        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        duration = max(end - start, 0.1)
        chunk_count = max(1, len(words) // max_words + (1 if len(words) % max_words else 0))
        chunk_duration = duration / chunk_count
        for index in range(chunk_count):
            chunk_words = words[index * max_words:(index + 1) * max_words]
            chunk_start = start + chunk_duration * index
            chunk_end = min(end, chunk_start + chunk_duration)
            result.append(
                {
                    "start": round(chunk_start, 3),
                    "end": round(chunk_end, 3),
                    "text": " ".join(chunk_words).strip(),
                }
            )
    return result


def clean_transcript_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply conservative cleanup to transcript segments."""
    normalized: list[dict[str, Any]] = []
    for segment in segments:
        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        if end <= start:
            continue
        text = normalize_segment_text(str(segment.get("text", "")).strip())
        if not text:
            continue
        normalized.append({"start": start, "end": end, "text": text})
    return split_long_segments(merge_short_segments(normalized))
