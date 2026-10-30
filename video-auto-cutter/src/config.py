from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml

from .utils import ensure_directories


SUPPORTED_STRATEGIES = {"aggressive", "balanced", "expert"}
SUPPORTED_MODES = {"auto", "talking", "tattoo", "timelapse", "portfolio", "all"}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


@dataclass(frozen=True)
class SubtitleStyle:
    name: str
    font: str
    font_size: int
    outline: int
    shadow: int
    max_chars_per_line: int
    max_lines: int
    margin_v: int
    uppercase_keywords: bool


@dataclass(frozen=True)
class AppConfig:
    """Resolved application configuration."""

    project_root: Path
    input_dir: Path
    downloads_dir: Path
    output_dir: Path
    processed_dir: Path
    logs_dir: Path
    target_width: int
    target_height: int
    fps: int
    max_download_files_per_run: int
    max_download_size_mb: int
    video_extensions: tuple[str, ...]
    clips_per_video: int
    shorts_duration_min: int
    shorts_duration_max: int
    ideal_duration_min: int
    ideal_duration_max: int
    timelapse_speed: int
    enable_transcription: bool
    enable_subtitles: bool
    enable_hooks: bool
    enable_cta: bool
    enable_reports: bool
    enable_yadisk_upload: bool
    language: str
    strategy: str
    mode: str
    min_total_score: int
    save_rejected: bool
    generate_variants: bool
    make_stories: bool
    subtitle_style: SubtitleStyle
    yadisk_token: str
    openai_api_key: str
    whisper_model: str
    log_level: str
    dry_run: bool
    analyze_only: bool
    download_only: bool

    @property
    def downloads_tmp_dir(self) -> Path:
        return self.downloads_dir / "tmp"

    @property
    def downloads_failed_dir(self) -> Path:
        return self.downloads_dir / "failed"

    @property
    def download_manifest_path(self) -> Path:
        return self.downloads_dir / "download_manifest.json"

    @property
    def processed_manifest_path(self) -> Path:
        return self.logs_dir / "processed_manifest.json"

    @property
    def best_dir(self) -> Path:
        return self.output_dir / "best"

    @property
    def talking_dir(self) -> Path:
        return self.output_dir / "talking"

    @property
    def tattoo_process_dir(self) -> Path:
        return self.output_dir / "tattoo_process"

    @property
    def closeups_dir(self) -> Path:
        return self.output_dir / "closeups"

    @property
    def satisfying_dir(self) -> Path:
        return self.output_dir / "satisfying"

    @property
    def before_after_dir(self) -> Path:
        return self.output_dir / "before_after"

    @property
    def portfolio_dir(self) -> Path:
        return self.output_dir / "portfolio"

    @property
    def timelapse_dir(self) -> Path:
        return self.output_dir / "timelapse"

    @property
    def stories_dir(self) -> Path:
        return self.output_dir / "stories"

    @property
    def previews_dir(self) -> Path:
        return self.output_dir / "previews"

    @property
    def thumbnails_dir(self) -> Path:
        return self.output_dir / "thumbnails"

    @property
    def transcripts_dir(self) -> Path:
        return self.output_dir / "transcripts"

    @property
    def subtitles_dir(self) -> Path:
        return self.output_dir / "subtitles"

    @property
    def captions_dir(self) -> Path:
        return self.output_dir / "captions"

    @property
    def metadata_dir(self) -> Path:
        return self.output_dir / "metadata"

    @property
    def reports_dir(self) -> Path:
        return self.output_dir / "reports"

    @property
    def rejected_dir(self) -> Path:
        return self.output_dir / "rejected"

    @property
    def shorts_dir(self) -> Path:
        return self.output_dir / "shorts"

    @property
    def reels_dir(self) -> Path:
        return self.output_dir / "reels"

    @property
    def tiktok_dir(self) -> Path:
        return self.output_dir / "tiktok"

    @property
    def required_directories(self) -> tuple[Path, ...]:
        return (
            self.input_dir,
            self.downloads_dir,
            self.downloads_tmp_dir,
            self.downloads_failed_dir,
            self.output_dir,
            self.best_dir,
            self.talking_dir,
            self.tattoo_process_dir,
            self.closeups_dir,
            self.satisfying_dir,
            self.before_after_dir,
            self.portfolio_dir,
            self.timelapse_dir,
            self.stories_dir,
            self.previews_dir,
            self.thumbnails_dir,
            self.transcripts_dir,
            self.subtitles_dir,
            self.captions_dir,
            self.metadata_dir,
            self.reports_dir,
            self.rejected_dir,
            self.shorts_dir,
            self.reels_dir,
            self.tiktok_dir,
            self.processed_dir,
            self.logs_dir,
        )

    @property
    def source_directories(self) -> tuple[Path, ...]:
        return (self.input_dir, self.downloads_dir)


def _apply_strategy(config: AppConfig) -> AppConfig:
    if config.strategy == "aggressive":
        return replace(
            config,
            clips_per_video=max(config.clips_per_video, 12),
            shorts_duration_min=min(config.shorts_duration_min, 14),
            shorts_duration_max=min(config.shorts_duration_max, 48),
            ideal_duration_min=min(config.ideal_duration_min, 20),
            ideal_duration_max=min(config.ideal_duration_max, 36),
            min_total_score=min(config.min_total_score, 55),
        )
    if config.strategy == "expert":
        return replace(
            config,
            clips_per_video=min(config.clips_per_video, 6),
            shorts_duration_min=max(config.shorts_duration_min, 22),
            shorts_duration_max=max(min(config.shorts_duration_max, 52), 36),
            ideal_duration_min=max(config.ideal_duration_min, 26),
            ideal_duration_max=max(config.ideal_duration_max, 38),
            min_total_score=max(config.min_total_score, 68),
        )
    return config


def load_config(config_path: Path, overrides: dict[str, Any] | None = None) -> AppConfig:
    """Load YAML config and apply runtime overrides."""
    overrides = overrides or {}
    project_root = config_path.resolve().parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    def get_value(key: str, default: Any) -> Any:
        value = overrides.get(key)
        if value is not None:
            return value
        return raw.get(key, default)

    def resolve_dir(value: str | Path, default_name: str) -> Path:
        path = Path(str(value or default_name))
        return path if path.is_absolute() else project_root / path

    subtitle_raw = raw.get("subtitle_style", {}) or {}
    strategy = str(get_value("strategy", "balanced")).strip().lower() or "balanced"
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"Unsupported strategy: {strategy}")
    mode = str(get_value("mode", "auto")).strip().lower() or "auto"
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")

    config = AppConfig(
        project_root=project_root,
        input_dir=resolve_dir(get_value("input_dir", "input"), "input"),
        downloads_dir=resolve_dir(get_value("downloads_dir", "downloads"), "downloads"),
        output_dir=resolve_dir(get_value("output_dir", "output"), "output"),
        processed_dir=resolve_dir(get_value("processed_dir", "processed"), "processed"),
        logs_dir=resolve_dir(get_value("logs_dir", "logs"), "logs"),
        target_width=max(int(get_value("target_width", 1080)), 320),
        target_height=max(int(get_value("target_height", 1920)), 320),
        fps=max(int(get_value("fps", 30)), 1),
        max_download_files_per_run=max(int(get_value("max_download_files_per_run", 4)), 1),
        max_download_size_mb=max(int(get_value("max_download_size_mb", 30)), 1),
        video_extensions=tuple(str(ext).lower() for ext in get_value("video_extensions", [".mp4", ".mov", ".mkv", ".avi", ".webm"])),
        clips_per_video=max(int(get_value("clips_per_video", 10)), 1),
        shorts_duration_min=max(int(get_value("shorts_duration_min", 18)), 3),
        shorts_duration_max=max(int(get_value("shorts_duration_max", 58)), 5),
        ideal_duration_min=max(int(get_value("ideal_duration_min", 25)), 3),
        ideal_duration_max=max(int(get_value("ideal_duration_max", 42)), 5),
        timelapse_speed=max(int(get_value("timelapse_speed", 10)), 2),
        enable_transcription=_to_bool(get_value("enable_transcription", True), True),
        enable_subtitles=_to_bool(get_value("enable_subtitles", True), True),
        enable_hooks=_to_bool(get_value("enable_hooks", True), True),
        enable_cta=_to_bool(get_value("enable_cta", True), True),
        enable_reports=_to_bool(get_value("enable_reports", True), True),
        enable_yadisk_upload=_to_bool(get_value("enable_yadisk_upload", False), False),
        language=str(get_value("language", "ru")).strip() or "ru",
        strategy=strategy,
        mode=mode,
        min_total_score=max(int(get_value("min_total_score", 60)), 0),
        save_rejected=_to_bool(get_value("save_rejected", True), True),
        generate_variants=_to_bool(get_value("generate_variants", True), True),
        make_stories=_to_bool(get_value("make_stories", False), False),
        subtitle_style=SubtitleStyle(
            name=str(subtitle_raw.get("name", "pro")),
            font=str(subtitle_raw.get("font", "Arial")),
            font_size=max(int(subtitle_raw.get("font_size", 72)), 16),
            outline=max(int(subtitle_raw.get("outline", 6)), 0),
            shadow=max(int(subtitle_raw.get("shadow", 2)), 0),
            max_chars_per_line=max(int(subtitle_raw.get("max_chars_per_line", 24)), 8),
            max_lines=max(int(subtitle_raw.get("max_lines", 2)), 1),
            margin_v=max(int(subtitle_raw.get("margin_v", 260)), 20),
            uppercase_keywords=_to_bool(subtitle_raw.get("uppercase_keywords", True), True),
        ),
        yadisk_token=os.getenv("YADISK_TOKEN", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        whisper_model=os.getenv("WHISPER_MODEL", "tiny").strip() or "tiny",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
        dry_run=_to_bool(get_value("dry_run", False), False),
        analyze_only=_to_bool(get_value("analyze_only", False), False),
        download_only=_to_bool(get_value("download_only", False), False),
    )

    config = _apply_strategy(config)

    if config.shorts_duration_min >= config.shorts_duration_max:
        raise ValueError("shorts_duration_min must be smaller than shorts_duration_max.")
    if config.ideal_duration_min >= config.ideal_duration_max:
        raise ValueError("ideal_duration_min must be smaller than ideal_duration_max.")

    ensure_directories(config.required_directories)
    return config
