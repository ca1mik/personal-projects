from __future__ import annotations

from importlib.util import find_spec
import logging
from pathlib import Path
from typing import Any

from .utils import write_json, write_text


def transcribe_audio(
    audio_path: Path,
    language: str = "ru",
    model_name: str = "tiny",
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """Transcribe audio with local Whisper when available."""
    if find_spec("whisper") is None:
        if logger is not None:
            logger.warning("Whisper is not installed. Falling back to interval-based clipping.")
        return None

    try:
        import whisper  # type: ignore[import-not-found]
    except Exception as error:  # noqa: BLE001
        if logger is not None:
            logger.warning("Whisper import failed: %s", error)
        return None

    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(str(audio_path), language=language, fp16=False, verbose=False)
    except Exception as error:  # noqa: BLE001
        if logger is not None:
            logger.warning("Whisper transcription failed: %s", error)
        return None

    segments = [
        {
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "text": str(segment["text"]).strip(),
        }
        for segment in result.get("segments", [])
        if str(segment.get("text", "")).strip()
    ]
    return {
        "engine": "whisper",
        "model": model_name,
        "language": result.get("language", language),
        "text": str(result.get("text", "")).strip(),
        "segments": segments,
    }


def save_transcript_json(transcript: dict[str, Any], path: Path) -> Path:
    """Save transcript payload to JSON."""
    write_json(path, transcript)
    return path


def save_transcript_txt(transcript: dict[str, Any], path: Path) -> Path:
    """Save transcript text to plain UTF-8 text."""
    write_text(path, str(transcript.get("text", "")).strip())
    return path
