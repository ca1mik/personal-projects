from __future__ import annotations

from pathlib import Path
from typing import Any

from .ffmpeg_utils import burn_subtitles as ffmpeg_burn_subtitles
from .utils import format_ass_timestamp, format_srt_timestamp, write_text


STYLE_PRESETS = {
    "pro": {"font_size": 72, "outline": 6, "shadow": 2, "margin_v": 260, "bold": -1},
    "clean": {"font_size": 64, "outline": 4, "shadow": 1, "margin_v": 240, "bold": 0},
    "bold": {"font_size": 78, "outline": 7, "shadow": 2, "margin_v": 260, "bold": -1},
    "minimal": {"font_size": 58, "outline": 3, "shadow": 0, "margin_v": 220, "bold": 0},
}


def split_text_for_reels(text: str, max_chars: int = 24, max_lines: int = 2) -> list[str]:
    """Split text into short subtitle chunks suitable for reels."""
    words = [word for word in text.strip().split() if word]
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    max_words = max_lines * 5

    for word in words:
        projected = current_length + len(word) + (1 if current else 0)
        if current and (projected > max_chars or len(current) >= max_words):
            chunks.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length = projected

    if current:
        chunks.append(" ".join(current))
    return chunks


def segments_to_caption_chunks(
    segments: list[dict[str, Any]],
    start_offset: float,
    end_limit: float | None,
) -> list[tuple[float, float, str]]:
    """Convert transcript segments into chunk-level caption events."""
    events: list[tuple[float, float, str]] = []
    for segment in segments:
        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        if end <= start:
            continue
        if end_limit is not None and start >= end_limit:
            continue
        chunk_start = max(0.0, start - start_offset)
        chunk_end = end - start_offset
        if end_limit is not None:
            chunk_end = min(chunk_end, end_limit - start_offset)
        if chunk_end <= chunk_start:
            continue
        text = str(segment.get("text", "")).strip()
        chunks = split_text_for_reels(text)
        if not chunks:
            continue
        per_chunk = max((chunk_end - chunk_start) / len(chunks), 0.15)
        for index, chunk in enumerate(chunks):
            event_start = chunk_start + per_chunk * index
            event_end = min(chunk_end, event_start + per_chunk)
            events.append((round(event_start, 3), round(event_end, 3), chunk))
    return events


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def write_srt(
    segments: list[dict[str, Any]],
    output_path: Path,
    start_offset: float = 0,
    end_limit: float | None = None,
) -> Path:
    """Write subtitle chunks as SRT."""
    events = segments_to_caption_chunks(segments, start_offset, end_limit)
    lines: list[str] = []
    for index, (start, end, text) in enumerate(events, start=1):
        lines.append(
            f"{index}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{text}\n"
        )
    write_text(output_path, "\n".join(lines))
    return output_path


def write_ass(
    segments: list[dict[str, Any]],
    output_path: Path,
    start_offset: float = 0,
    end_limit: float | None = None,
    hook_text: str | None = None,
    cta_text: str | None = None,
    style: str = "pro",
) -> Path:
    """Write ASS subtitles with reel-oriented styling."""
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["pro"])
    events = segments_to_caption_chunks(segments, start_offset, end_limit)
    clip_duration = max((end_limit or 0) - start_offset, max((event[1] for event in events), default=4.0))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{preset['font_size']},&H00FFFFFF,&H000000FF,&H00000000,&H78000000,{preset['bold']},0,0,0,100,100,0,0,1,{preset['outline']},{preset['shadow']},2,70,70,{preset['margin_v']},1
Style: Hook,Arial,{preset['font_size'] + 10},&H00FFFFFF,&H000000FF,&H00000000,&H7A000000,-1,0,0,0,100,100,0,0,1,{preset['outline'] + 1},{preset['shadow'] + 1},2,70,70,{max(120, preset['margin_v'] + 180)},1
Style: CTA,Arial,{max(56, preset['font_size'] - 4)},&H00FFFFFF,&H000000FF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,{preset['outline']},{preset['shadow']},2,70,70,{max(160, preset['margin_v'] - 40)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    if hook_text:
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_timestamp(0.0)},{format_ass_timestamp(min(2.8, clip_duration))},Hook,,0,0,0,,{_ass_escape(hook_text)}"
        )
    for start, end, text in events:
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_timestamp(start)},{format_ass_timestamp(end)},Default,,0,0,0,,{_ass_escape(text)}"
        )
    if cta_text:
        cta_start = max(0.0, clip_duration - 2.6)
        lines.append(
            "Dialogue: 0,"
            f"{format_ass_timestamp(cta_start)},{format_ass_timestamp(clip_duration)},CTA,,0,0,0,,{_ass_escape(cta_text)}"
        )
    write_text(output_path, "\n".join(lines))
    return output_path


def burn_subtitles(video_path: Path, subtitle_path: Path, output_path: Path) -> Path:
    """Burn an ASS subtitle file into a video."""
    return ffmpeg_burn_subtitles(video_path, subtitle_path, output_path)
