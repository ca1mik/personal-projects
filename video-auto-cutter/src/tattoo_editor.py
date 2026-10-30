from __future__ import annotations

from pathlib import Path
import tempfile
import subprocess

from .config import AppConfig
from .ffmpeg_utils import make_vertical_clip
from .subtitles import write_ass


def _overlay_ass(path: Path, duration: float, title_text: str | None) -> Path | None:
    if not title_text:
        return None
    return write_ass([], path, start_offset=0, end_limit=duration, hook_text=title_text, style="pro")


def make_tattoo_process_reel(input_path, output_path, clips, config: AppConfig, title_text=None):
    """Make a tattoo process reel from a list of segments."""
    segment = clips[0]
    overlay_path = _overlay_ass(output_path.with_suffix(".ass"), float(segment["duration"]), title_text)
    return make_vertical_clip(
        input_path,
        output_path,
        float(segment["start"]),
        float(segment["duration"]),
        config.target_width,
        config.target_height,
        subtitle_path=overlay_path,
    )


def make_closeup_clip(input_path, output_path, start, duration, config: AppConfig):
    """Make a short close-up tattoo clip."""
    overlay_path = _overlay_ass(output_path.with_suffix(".ass"), float(duration), "DETAILS")
    return make_vertical_clip(
        input_path,
        output_path,
        float(start),
        float(duration),
        config.target_width,
        config.target_height,
        subtitle_path=overlay_path,
    )


def make_satisfying_clip(input_path, output_path, start, duration, config: AppConfig):
    """Make a satisfying motion-focused clip."""
    overlay_path = _overlay_ass(output_path.with_suffix(".ass"), float(duration), "PROCESS")
    return make_vertical_clip(
        input_path,
        output_path,
        float(start),
        float(duration),
        config.target_width,
        config.target_height,
        subtitle_path=overlay_path,
    )


def make_before_after_reel(input_path, output_path, segments, config: AppConfig):
    """Make a before / process / after montage reel."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        file_list_path = temp_dir / "concat.txt"
        rendered_parts: list[Path] = []
        for key in ("before", "process", "after"):
            segment = segments[key]
            part_path = temp_dir / f"{key}.mp4"
            overlay_path = _overlay_ass(temp_dir / f"{key}.ass", float(segment["duration"]), key.upper())
            make_vertical_clip(
                input_path,
                part_path,
                float(segment["start"]),
                float(segment["duration"]),
                config.target_width,
                config.target_height,
                subtitle_path=overlay_path,
            )
            rendered_parts.append(part_path)
        file_lines = []
        for path in rendered_parts:
            safe_path = str(path).replace("'", "''")
            file_lines.append(f"file '{safe_path}'")
        file_list_path.write_text("\n".join(file_lines), encoding="utf-8")
        from .ffmpeg_utils import _run_command  # local import to avoid circular surface

        try:
            _run_command(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(file_list_path),
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
            )
        except subprocess.CalledProcessError:
            process_segment = segments["process"]
            overlay_path = _overlay_ass(temp_dir / "fallback.ass", float(process_segment["duration"]), "PROCESS")
            make_vertical_clip(
                input_path,
                output_path,
                float(process_segment["start"]),
                float(process_segment["duration"]),
                config.target_width,
                config.target_height,
                subtitle_path=overlay_path,
            )
    return output_path


def make_portfolio_clip(input_path, output_path, start, duration, config: AppConfig):
    """Make a softer portfolio clip without aggressive text."""
    return make_vertical_clip(
        input_path,
        output_path,
        float(start),
        float(duration),
        config.target_width,
        config.target_height,
    )
