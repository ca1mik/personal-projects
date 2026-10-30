from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


LOGGER_NAME = "video_auto_cutter"


def ensure_directories(paths: Iterable[Path]) -> None:
    """Create directories if they do not exist yet."""
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    """Convert a filename into a filesystem-safe folder name."""
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("._")
    return cleaned or "video"


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp."""
    milliseconds = max(int(round(seconds * 1000)), 0)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def format_ass_timestamp(seconds: float) -> str:
    """Format seconds as ASS timestamp."""
    centiseconds = max(int(round(seconds * 100)), 0)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02}:{secs:02}.{centis:02}"


def write_json(path: Path, payload: Any) -> None:
    """Write JSON using UTF-8 and human-readable indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Write plain UTF-8 text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path, default: Any) -> Any:
    """Load JSON file or return default when absent/corrupted."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def setup_logging(logs_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure application logger for console and file output."""
    ensure_directories([logs_dir])
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(logs_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def compute_file_signature(path: Path, sample_size: int = 1024 * 1024) -> str:
    """Build a stable signature from file metadata and binary samples."""
    stat = path.stat()
    digest = hashlib.sha1()
    digest.update(path.name.encode("utf-8", errors="ignore"))
    digest.update(str(stat.st_size).encode("ascii"))
    digest.update(str(stat.st_mtime_ns).encode("ascii"))

    with path.open("rb") as source:
        digest.update(source.read(sample_size))
        if stat.st_size > sample_size:
            source.seek(max(stat.st_size - sample_size, 0))
            digest.update(source.read(sample_size))
    return digest.hexdigest()


def move_to_processed(source: Path, processed_dir: Path) -> Path:
    """Move file into processed directory without overwriting existing files."""
    ensure_directories([processed_dir])
    target = processed_dir / source.name
    counter = 1
    while target.exists():
        target = processed_dir / f"{source.stem}_{counter}{source.suffix}"
        counter += 1
    shutil.move(str(source), str(target))
    return target


def copy_file(source: Path, target: Path) -> Path:
    """Copy file preserving metadata."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def relative_to_or_absolute(path: Path, base: Path) -> str:
    """Return a relative path when possible, otherwise an absolute string."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def clip_text_summary(segments: list[dict[str, Any]]) -> str:
    """Join transcript segments into plain text."""
    return "\n".join(segment.get("text", "").strip() for segment in segments if segment.get("text"))
