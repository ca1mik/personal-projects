from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from shlex import quote
from typing import Any


def _log_command(command: list[str], logger: logging.Logger | None = None) -> None:
    if logger is None:
        return
    logger.info("FFmpeg command: %s", " ".join(quote(part) for part in command))


def _run_command(command: list[str], logger: logging.Logger | None = None, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    _log_command(command, logger)
    return subprocess.run(command, check=check, capture_output=True, text=True, encoding="utf-8")


def safe_ass_filter_path(path: Path) -> str:
    """Escape ASS path for FFmpeg filter arguments on Windows and Unix."""
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _binary_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _candidate_ffmpeg_dirs() -> list[Path]:
    local_app_data = os.getenv("LOCALAPPDATA", "")
    candidates: list[Path] = []
    if local_app_data:
        winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.exists():
            for path in winget_packages.rglob("bin"):
                if (path / "ffmpeg.exe").exists() and (path / "ffprobe.exe").exists():
                    candidates.append(path)
    return candidates


def ensure_ffmpeg_in_path() -> bool:
    """Try to auto-register FFmpeg from common install locations."""
    if _binary_available():
        return True
    for candidate in _candidate_ffmpeg_dirs():
        os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"
        if _binary_available():
            return True
    return False


def check_ffmpeg() -> bool:
    """Return True when ffmpeg and ffprobe are available."""
    return ensure_ffmpeg_in_path()


def get_video_info(path: Path) -> dict[str, Any]:
    """Return normalized video metadata from ffprobe."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,width,height,r_frame_rate:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = _run_command(command)
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video_stream is None:
        raise RuntimeError(f"Could not read video stream metadata from {path}")
    frame_rate = str(video_stream.get("r_frame_rate", "0/1"))
    numerator, _, denominator = frame_rate.partition("/")
    fps = float(numerator) / float(denominator or "1") if numerator not in {"", "0"} else 0.0
    return {
        "duration": float(payload.get("format", {}).get("duration", 0) or 0.0),
        "width": int(video_stream.get("width", 0) or 0),
        "height": int(video_stream.get("height", 0) or 0),
        "fps": round(fps, 3),
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
    }


def get_video_duration(path: Path) -> float:
    """Return video duration in seconds."""
    return float(get_video_info(path)["duration"])


def get_video_resolution(path: Path) -> tuple[int, int]:
    """Return width and height."""
    info = get_video_info(path)
    return int(info["width"]), int(info["height"])


def has_audio_stream(path: Path) -> bool:
    """Return True when the media contains an audio stream."""
    return bool(get_video_info(path)["has_audio"])


def extract_audio(video_path: Path, audio_path: Path, logger: logging.Logger | None = None) -> Path:
    """Extract mono WAV audio for transcription."""
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]
    _run_command(command, logger)
    return audio_path


def _build_vertical_filter(
    input_path: Path,
    width: int,
    height: int,
    subtitle_path: Path | None = None,
) -> tuple[str, bool]:
    source_width, source_height = get_video_resolution(input_path)

    if source_width == source_height:
        filter_graph = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=24:2[bg];"
            f"[0:v]scale={width}:{width}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        uses_filter_complex = True
    elif source_width > source_height:
        filter_graph = f"scale=-2:{height},crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
        uses_filter_complex = False
    else:
        filter_graph = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )
        uses_filter_complex = False

    if subtitle_path is not None and subtitle_path.exists():
        ass_filter = f"ass='{safe_ass_filter_path(subtitle_path)}'"
        if uses_filter_complex:
            filter_graph = f"{filter_graph}[base];[base]{ass_filter}"
        else:
            filter_graph = f"{filter_graph},{ass_filter}"
    return filter_graph, uses_filter_complex


def make_vertical_clip(
    input_path: Path,
    output_path: Path,
    start: float,
    duration: float,
    width: int,
    height: int,
    subtitle_path: Path | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Render a vertical social clip with optional burned subtitles."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_graph, use_complex = _build_vertical_filter(input_path, width, height, subtitle_path)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{max(start, 0):.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{max(duration, 0.5):.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
    ]
    if use_complex:
        command.extend(["-filter_complex", filter_graph])
    else:
        command.extend(["-vf", filter_graph])
    command.extend(
        [
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    _run_command(command, logger)
    return output_path


def make_timelapse(
    input_path: Path,
    output_path: Path,
    speed: int,
    width: int,
    height: int,
    logger: logging.Logger | None = None,
) -> Path:
    """Create a vertical silent timelapse capped to social-friendly playback."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = get_video_duration(input_path)
    effective_speed = max(speed, math.ceil(duration / 60) if duration > 60 else speed)
    filter_graph, use_complex = _build_vertical_filter(input_path, width, height)
    command = ["ffmpeg", "-y", "-i", str(input_path), "-map", "0:v:0"]
    if use_complex:
        command.extend(["-filter_complex", f"{filter_graph},setpts=PTS/{effective_speed}"])
    else:
        command.extend(["-vf", f"{filter_graph},setpts=PTS/{effective_speed}"])
    command.extend(
        [
            "-an",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    _run_command(command, logger)
    return output_path


def make_preview(
    input_path: Path,
    output_path: Path,
    timestamp: float,
    logger: logging.Logger | None = None,
) -> Path:
    """Render a preview frame as JPEG."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{max(timestamp, 0):.3f}",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    _run_command(command, logger)
    return output_path


def make_thumbnail(
    input_path: Path,
    output_path: Path,
    timestamp: float,
    title_text: str | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Render a vertical thumbnail frame, optionally with text overlay."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_graph, use_complex = _build_vertical_filter(input_path, 1080, 1920)
    fallback_graph = filter_graph
    if title_text:
        safe_text = title_text.replace(":", r"\:").replace("'", r"\'")
        drawtext = (
            "drawtext=font=Arial:fontcolor=white:fontsize=72:"
            "box=1:boxcolor=black@0.45:boxborderw=20:"
            "x=(w-text_w)/2:y=120:"
            f"text='{safe_text}'"
        )
        if use_complex:
            filter_graph = f"{filter_graph}[thumb];[thumb]{drawtext}"
        else:
            filter_graph = f"{filter_graph},{drawtext}"
    command = ["ffmpeg", "-y", "-ss", f"{max(timestamp, 0):.3f}", "-i", str(input_path), "-frames:v", "1"]
    if use_complex:
        command.extend(["-filter_complex", filter_graph])
    else:
        command.extend(["-vf", filter_graph])
    command.extend(["-q:v", "2", str(output_path)])
    try:
        _run_command(command, logger)
    except subprocess.CalledProcessError:
        fallback_command = ["ffmpeg", "-y", "-ss", f"{max(timestamp, 0):.3f}", "-i", str(input_path), "-frames:v", "1"]
        if use_complex:
            fallback_command.extend(["-filter_complex", fallback_graph])
        else:
            fallback_command.extend(["-vf", fallback_graph])
        fallback_command.extend(["-q:v", "2", str(output_path)])
        if logger is not None and title_text:
            logger.warning("Thumbnail text overlay failed for %s. Falling back to plain thumbnail.", input_path.name)
        _run_command(fallback_command, logger)
    return output_path


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    logger: logging.Logger | None = None,
) -> Path:
    """Burn subtitles into an existing video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"ass='{safe_ass_filter_path(subtitle_path)}'",
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_command(command, logger)
    return output_path


def normalize_for_social(
    input_path: Path,
    output_path: Path,
    logger: logging.Logger | None = None,
) -> Path:
    """Re-encode a video with settings compatible with major short-form platforms."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_command(command, logger)
    return output_path


def detect_scene_changes(
    input_path: Path,
    threshold: float = 0.35,
    limit: int = 200,
    logger: logging.Logger | None = None,
) -> list[float]:
    """Return scene change timestamps extracted from FFmpeg showinfo output."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-filter:v",
        f"select='gt(scene,{threshold})',showinfo",
        "-vsync",
        "0",
        "-an",
        "-f",
        "null",
        "-",
    ]
    _log_command(command, logger)
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    timestamps = [float(match.group(1)) for match in re.finditer(r"pts_time:(\d+(?:\.\d+)?)", result.stderr or "")]
    return timestamps[:limit]
