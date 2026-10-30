from __future__ import annotations

import re


STOP_WORDS = {
    "это",
    "что",
    "как",
    "для",
    "если",
    "или",
    "потому",
    "когда",
    "просто",
    "очень",
    "только",
}


def generate_hashtags(clip_text: str, language: str = "ru", max_tags: int = 12) -> list[str]:
    """Generate relevant hashtags from clip text."""
    del language
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]{4,}", clip_text.lower())
    unique: list[str] = []
    for token in tokens:
        if token in STOP_WORDS or token.isdigit():
            continue
        tag = f"#{token}"
        if tag not in unique:
            unique.append(tag)
        if len(unique) >= max_tags:
            break
    if not unique:
        unique = ["#shorts", "#reels", "#tattoo"]
    return unique


def generate_caption(clip_text: str, hook: str, cta: str, language: str = "ru") -> str:
    """Generate a publication caption."""
    del language
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", clip_text.strip()) if item.strip()]
    heading = hook or (sentences[0] if sentences else "Короткий разбор")
    body = "\n".join(sentences[:2]) if sentences else "Сильный фрагмент из длинного видео."
    hashtags = " ".join(generate_hashtags(clip_text))
    return f"{heading}\n\n{body}\n\n{cta}\n\n{hashtags}".strip()
