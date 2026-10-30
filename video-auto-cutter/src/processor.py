from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Callable

from tqdm import tqdm

from .audio_utils import build_audio_output_path, estimate_speech_density
from .captions import generate_caption, generate_hashtags
from .clip_selector import ClipCandidate, select_clips_from_transcript
from .config import AppConfig
from .content_detector import detect_content_type
from .cta import choose_cta, generate_cta
from .ffmpeg_utils import (
    burn_subtitles,
    check_ffmpeg,
    extract_audio,
    get_video_info,
    make_preview,
    make_thumbnail,
    make_timelapse,
    make_vertical_clip,
)
from .hooks import choose_best_hook, generate_hooks
from .metadata import copy_variant_to_bucket, write_metadata
from .reports import write_summary_reports, write_video_report
from .scanner import VideoFile, discover_videos
from .scoring import ClipScores, score_clip
from .subtitles import write_ass, write_srt
from .tattoo_editor import (
    make_before_after_reel,
    make_closeup_clip,
    make_portfolio_clip,
    make_satisfying_clip,
    make_tattoo_process_reel,
)
from .tattoo_selector import (
    select_before_process_after,
    select_closeup_clips,
    select_portfolio_clips,
    select_satisfying_clips,
    select_tattoo_process_clips,
)
from .tattoo_texts import generate_tattoo_caption, generate_tattoo_hashtags, generate_tattoo_overlay
from .transcribe import save_transcript_json, save_transcript_txt, transcribe_audio
from .transcript_cleaner import clean_transcript_segments
from .utils import (
    clip_text_summary,
    copy_file,
    ensure_directories,
    load_json,
    move_to_processed,
    relative_to_or_absolute,
    setup_logging,
    slugify,
    write_json,
    write_text,
)
from .visual_scoring import analyze_segment_visuals
from .yadisk_downloader import (
    download_from_links_file,
    download_public_yadisk_file,
    download_public_yadisk_folder,
    get_public_resource_info,
    is_yadisk_url,
    mark_download_as_processed,
)


PIPELINE_VERSION = "tattoo_v2"


@dataclass(frozen=True)
class ProcessingSummary:
    downloaded: int
    discovered: int
    processed: int
    skipped: int
    failed: int


def _source_dirs(config: AppConfig, source_video: Path) -> dict[str, Path]:
    slug = slugify(source_video.stem)
    return {
        "transcripts": config.transcripts_dir / slug,
        "subtitles": config.subtitles_dir / slug,
        "captions": config.captions_dir / slug,
        "previews": config.previews_dir / slug,
        "thumbnails": config.thumbnails_dir / slug,
    }


def _segments_for_range(segments: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for segment in segments:
        seg_start = float(segment.get("start", 0))
        seg_end = float(segment.get("end", 0))
        if seg_end <= start or seg_start >= end:
            continue
        result.append(
            {
                "start": max(seg_start, start),
                "end": min(seg_end, end),
                "text": str(segment.get("text", "")).strip(),
            }
        )
    return result


def _overlay_segments(clip_start: float, duration: float, *texts: str) -> list[dict[str, Any]]:
    parts = [text.strip() for text in texts if text and text.strip()]
    if not parts:
        return []
    result = [{"start": clip_start, "end": clip_start + min(2.8, duration), "text": parts[0]}]
    if len(parts) > 1 and duration > 2.8:
        result.append(
            {
                "start": clip_start + max(0.0, duration - 2.6),
                "end": clip_start + duration,
                "text": parts[-1],
            }
        )
    return result


def _save_transcript_artifacts(transcript_dir: Path, raw_payload: dict[str, Any], cleaned_segments: list[dict[str, Any]]) -> None:
    save_transcript_json(raw_payload, transcript_dir / "transcript_raw.json")
    save_transcript_txt(raw_payload, transcript_dir / "transcript_raw.txt")
    cleaned_payload = {
        "engine": raw_payload.get("engine"),
        "model": raw_payload.get("model"),
        "language": raw_payload.get("language"),
        "text": clip_text_summary(cleaned_segments),
        "segments": cleaned_segments,
    }
    save_transcript_json(cleaned_payload, transcript_dir / "transcript_clean.json")
    save_transcript_txt(cleaned_payload, transcript_dir / "transcript_clean.txt")


def _load_manifests(config: AppConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    stored = load_json(config.processed_manifest_path, {})
    active = {
        signature: payload
        for signature, payload in stored.items()
        if isinstance(payload, dict) and payload.get("pipeline_version") == PIPELINE_VERSION
    }
    return stored, active


def _download_requested_sources(config: AppConfig, yadisk_url: str | None, links_file: Path | None, logger: logging.Logger) -> int:
    downloaded_count = 0
    max_size_bytes = config.max_download_size_mb * 1024 * 1024
    common = {
        "token": config.yadisk_token or None,
        "manifest_path": config.download_manifest_path,
        "tmp_dir": config.downloads_tmp_dir,
        "failed_dir": config.downloads_failed_dir,
        "dry_run": config.dry_run,
        "logger": logger,
        "max_files": config.max_download_files_per_run,
        "max_size_bytes": max_size_bytes,
    }
    if yadisk_url:
        if not is_yadisk_url(yadisk_url):
            raise RuntimeError(f"Not a Yandex.Disk URL: {yadisk_url}")
        info = get_public_resource_info(yadisk_url, token=config.yadisk_token or None)
        if str(info.get("type", "")) == "file":
            downloaded = download_public_yadisk_file(yadisk_url, config.downloads_dir, **common)
        else:
            downloaded = download_public_yadisk_folder(yadisk_url, config.downloads_dir, **common)
        downloaded_count += len(downloaded)
    if links_file is not None:
        downloaded_count += len(download_from_links_file(links_file, config.downloads_dir, **common))
    return downloaded_count


def _resolve_modes(config: AppConfig, detection: dict[str, Any], duration: float) -> list[str]:
    if config.mode == "all":
        return ["talking", "tattoo", "portfolio", "timelapse"]
    if config.mode == "auto":
        modes = list(detection.get("recommended_modes", []))
        if duration > 180 and "timelapse" not in modes:
            modes.append("timelapse")
        if detection.get("is_tattoo_process") and "tattoo" not in modes:
            modes.append("tattoo")
        if detection.get("is_portfolio_shot") and "portfolio" not in modes:
            modes.append("portfolio")
        return modes or ["tattoo"]
    return [config.mode]


def _timelapse_target_duration(duration: float) -> float:
    if duration <= 600:
        return 30.0
    if duration <= 1800:
        return 42.0
    return 52.0


def _store_clip_result(
    *,
    config: AppConfig,
    source_video: Path,
    clip_id: str,
    clip_type: str,
    start: float,
    duration: float,
    text: str,
    hook: str,
    cta: str,
    caption: str,
    hashtags: list[str],
    overlay_text: str,
    scores: ClipScores,
    visuals: dict[str, Any],
    files: dict[str, Path],
    summary_rows: list[dict[str, Any]],
) -> Path | None:
    primary = files["primary"]
    slug = slugify(source_video.stem)
    best_path: Path | None = None
    if scores.total_score >= config.min_total_score:
        best_name = f"{slug}_score_{scores.total_score}_{clip_type}_{clip_id}.mp4"
        best_path = copy_variant_to_bucket(primary, config.best_dir, best_name)
        best_flag = True
        main_output = best_path
    else:
        best_flag = False
        main_output = primary
        if config.save_rejected:
            copy_variant_to_bucket(primary, config.rejected_dir, f"{slug}_{clip_type}_{clip_id}.mp4")
    metadata = {
        "source_video": source_video.name,
        "clip_id": clip_id,
        "clip_type": clip_type,
        "start": round(start, 3),
        "end": round(start + duration, 3),
        "duration": round(duration, 3),
        "text": text,
        "hook": hook,
        "cta": cta,
        "caption": caption,
        "hashtags": hashtags,
        "overlay_text": overlay_text,
        **scores.to_dict(),
        "motion_score": round(float(visuals.get("motion_score", 0) or 0), 2),
        "brightness_score": round(float(visuals.get("brightness_score", 0) or 0), 2),
        "sharpness_score": round(float(visuals.get("sharpness_score", 0) or 0), 2),
        "visual_reason": str(visuals.get("reason", "")),
        "output_file": relative_to_or_absolute(main_output, config.project_root),
        "files": {key: relative_to_or_absolute(path, config.project_root) for key, path in files.items()},
    }
    write_metadata(config.metadata_dir / f"{slug}_{clip_id}.json", metadata)
    summary_rows.append(
        {
            "source_video": source_video.name,
            "clip_id": clip_id,
            "clip_type": clip_type,
            "start": round(start, 3),
            "end": round(start + duration, 3),
            "duration": round(duration, 3),
            "text": text,
            "hook": hook,
            "cta": cta,
            "caption": caption,
            "viral_score": scores.viral_score,
            "conversion_score": scores.conversion_score,
            "retention_score": scores.retention_score,
            "tattoo_visual_score": scores.tattoo_visual_score,
            "motion_score": round(float(visuals.get("motion_score", 0) or 0), 2),
            "brightness_score": round(float(visuals.get("brightness_score", 0) or 0), 2),
            "total_score": scores.total_score,
            "reason": scores.reason,
            "best": best_flag,
            "output_file": relative_to_or_absolute(main_output, config.project_root),
            "files": ", ".join(relative_to_or_absolute(path, config.project_root) for path in files.values()),
        }
    )
    return best_path


def _render_talking_variants(
    source_video: Path,
    source_slug: str,
    candidate: ClipCandidate,
    subtitle_segments: list[dict[str, Any]],
    hook: str,
    cta: str,
    config: AppConfig,
    directories: dict[str, Path],
    logger: logging.Logger,
    index: int,
) -> dict[str, Path]:
    base = f"{source_slug}_talking_{index:02d}"
    clean_path = config.talking_dir / f"{base}_v1_clean.mp4"
    subtitles_path = config.talking_dir / f"{base}_v2_subtitles.mp4"
    hook_path = config.talking_dir / f"{base}_v3_hook_subtitles.mp4"
    full_path = config.talking_dir / f"{base}_v4_hook_subtitles_cta.mp4"
    srt_path = directories["subtitles"] / f"{base}.srt"
    ass_clean = directories["subtitles"] / f"{base}_clean.ass"
    ass_hook = directories["subtitles"] / f"{base}_hook.ass"
    ass_full = directories["subtitles"] / f"{base}_full.ass"
    preview_path = directories["previews"] / f"{base}.jpg"
    thumbnail_path = directories["thumbnails"] / f"{base}.jpg"

    write_srt(subtitle_segments, srt_path, start_offset=candidate.start, end_limit=candidate.end)
    write_ass(subtitle_segments, ass_clean, start_offset=candidate.start, end_limit=candidate.end, style=config.subtitle_style.name)
    write_ass(
        subtitle_segments,
        ass_hook,
        start_offset=candidate.start,
        end_limit=candidate.end,
        hook_text=hook,
        style=config.subtitle_style.name,
    )
    write_ass(
        subtitle_segments,
        ass_full,
        start_offset=candidate.start,
        end_limit=candidate.end,
        hook_text=hook,
        cta_text=cta,
        style=config.subtitle_style.name,
    )
    make_vertical_clip(source_video, clean_path, candidate.start, candidate.duration, config.target_width, config.target_height, logger=logger)
    if config.enable_subtitles:
        make_vertical_clip(
            source_video,
            subtitles_path,
            candidate.start,
            candidate.duration,
            config.target_width,
            config.target_height,
            subtitle_path=ass_clean,
            logger=logger,
        )
    else:
        copy_file(clean_path, subtitles_path)
    if config.enable_hooks:
        make_vertical_clip(
            source_video,
            hook_path,
            candidate.start,
            candidate.duration,
            config.target_width,
            config.target_height,
            subtitle_path=ass_hook,
            logger=logger,
        )
    else:
        copy_file(subtitles_path, hook_path)
    if config.enable_subtitles or config.enable_hooks or config.enable_cta:
        make_vertical_clip(
            source_video,
            full_path,
            candidate.start,
            candidate.duration,
            config.target_width,
            config.target_height,
            subtitle_path=ass_full,
            logger=logger,
        )
    else:
        copy_file(hook_path, full_path)
    ts = candidate.start + min(max(candidate.duration * 0.4, 0.8), max(candidate.duration - 0.2, 0.2))
    make_preview(source_video, preview_path, ts, logger=logger)
    make_thumbnail(source_video, thumbnail_path, ts, title_text=hook, logger=logger)
    return {
        "primary": full_path,
        "clean": clean_path,
        "subtitles": subtitles_path,
        "hook_subtitles": hook_path,
        "hook_subtitles_cta": full_path,
        "preview": preview_path,
        "thumbnail": thumbnail_path,
        "srt": srt_path,
        "ass_clean": ass_clean,
        "ass_hook": ass_hook,
        "ass_full": ass_full,
    }


def _render_visual_clip(
    *,
    source_video: Path,
    source_slug: str,
    video_duration: float,
    clip_type: str,
    index: int,
    start: float,
    duration: float,
    output_dir: Path,
    overlay_text: str,
    caption: str,
    cta: str,
    hashtags: list[str],
    config: AppConfig,
    directories: dict[str, Path],
    logger: logging.Logger,
    summary_rows: list[dict[str, Any]],
    render_fn: Callable[[Path, Path, float, float, AppConfig], Path],
) -> Path | None:
    clip_id = f"{clip_type}_{index:02d}"
    output_path = output_dir / f"{source_slug}_{clip_id}.mp4"
    preview_path = directories["previews"] / f"{source_slug}_{clip_id}.jpg"
    thumbnail_path = directories["thumbnails"] / f"{source_slug}_{clip_id}.jpg"
    visuals = analyze_segment_visuals(source_video, start, duration)
    scores = score_clip(
        f"{overlay_text}. {caption}",
        duration,
        strategy=config.strategy,
        tattoo_visual_score=float(visuals.get("visual_score", 60) or 60),
    )
    render_fn(source_video, output_path, start, duration, config)
    preview_ts = min(start + max(duration / 2, 0.1), max(video_duration - 0.05, 0.0))
    make_preview(source_video, preview_path, preview_ts, logger=logger)
    make_thumbnail(source_video, thumbnail_path, preview_ts, title_text=overlay_text, logger=logger)
    write_text(directories["captions"] / f"{source_slug}_{clip_id}.txt", caption)
    return _store_clip_result(
        config=config,
        source_video=source_video,
        clip_id=clip_id,
        clip_type=clip_type,
        start=start,
        duration=duration,
        text=caption,
        hook=overlay_text,
        cta=cta,
        caption=caption,
        hashtags=hashtags,
        overlay_text=overlay_text,
        scores=scores,
        visuals=visuals,
        files={"primary": output_path, "preview": preview_path, "thumbnail": thumbnail_path},
        summary_rows=summary_rows,
    )


def _process_single_video(
    item: VideoFile,
    config: AppConfig,
    logger: logging.Logger,
    stored_manifest: dict[str, Any],
    summary_rows: list[dict[str, Any]],
) -> None:
    source_video = item.path
    source_slug = slugify(source_video.stem)
    directories = _source_dirs(config, source_video)
    ensure_directories(directories.values())
    info = get_video_info(source_video)
    duration = float(info["duration"])
    logger.info("Processing %s (%.2fs, %sx%s, audio=%s)", source_video.name, duration, info["width"], info["height"], info["has_audio"])

    transcript_payload: dict[str, Any] = {
        "engine": None,
        "model": None,
        "language": config.language,
        "text": "",
        "segments": [],
        "status": "disabled" if not config.enable_transcription else "pending",
    }
    cleaned_segments: list[dict[str, Any]] = []
    if config.enable_transcription and info["has_audio"]:
        audio_path = build_audio_output_path(source_video, directories["transcripts"])
        extract_audio(source_video, audio_path, logger=logger)
        payload = transcribe_audio(audio_path, language=config.language, model_name=config.whisper_model, logger=logger)
        if payload is None:
            transcript_payload["status"] = "fallback_no_transcription"
        else:
            transcript_payload.update(payload)
            transcript_payload["status"] = "ok"
            cleaned_segments = clean_transcript_segments(payload.get("segments", []))
    else:
        transcript_payload["status"] = "fallback_no_transcription"
    _save_transcript_artifacts(directories["transcripts"], transcript_payload, cleaned_segments)

    detection = detect_content_type(source_video, transcript_payload, info)
    modes = _resolve_modes(config, detection, duration)
    include_portfolio = "portfolio" in modes or config.mode == "all"
    include_stories = config.make_stories or config.mode == "all"
    render_enabled = not config.analyze_only
    write_json(directories["transcripts"] / "content_detection.json", detection)

    best_paths: list[Path] = []
    if render_enabled and "talking" in modes and cleaned_segments:
        talking_candidates = select_clips_from_transcript(cleaned_segments, duration, config)[: (5 if config.strategy == "aggressive" else 3)]
        for index, candidate in enumerate(talking_candidates, start=1):
            clip_text = candidate.text or candidate.reason
            scores = score_clip(clip_text, candidate.duration, strategy=config.strategy, tattoo_visual_score=50)
            hook = choose_best_hook(generate_hooks(clip_text, strategy=config.strategy), clip_text, strategy=config.strategy) if config.enable_hooks else ""
            cta = choose_cta(clip_text, scores, strategy=config.strategy) if config.enable_cta else ""
            caption = generate_caption(clip_text, hook, cta)
            hashtags = generate_hashtags(clip_text)
            write_text(directories["captions"] / f"{source_slug}_talking_{index:02d}.txt", caption)
            subtitle_segments = _segments_for_range(cleaned_segments, candidate.start, candidate.end) or _overlay_segments(candidate.start, candidate.duration, hook, cta)
            files = _render_talking_variants(source_video, source_slug, candidate, subtitle_segments, hook, cta, config, directories, logger, index)
            best = _store_clip_result(
                config=config,
                source_video=source_video,
                clip_id=f"talking_{index:02d}",
                clip_type="talking",
                start=candidate.start,
                duration=candidate.duration,
                text=clip_text,
                hook=hook,
                cta=cta,
                caption=caption,
                hashtags=hashtags,
                overlay_text=hook,
                scores=scores,
                visuals={"motion_score": 50, "brightness_score": 55, "sharpness_score": 55, "reason": "speech-first clip"},
                files=files,
                summary_rows=summary_rows,
            )
            if best is not None:
                best_paths.append(best)

    if render_enabled and ("tattoo" in modes or include_portfolio):
        tattoo_cta = generate_cta("tattoo", clip_type="tattoo", strategy=config.strategy)[0]
        tags = generate_tattoo_hashtags()
        group_specs = [
            ("tattoo_process", config.tattoo_process_dir, select_tattoo_process_clips(source_video, duration, config)[:3], generate_tattoo_overlay("process", config.strategy), generate_tattoo_caption("tattoo_process", source_video.stem, config.strategy), tattoo_cta, lambda inp, out, start, clip_duration, app: make_tattoo_process_reel(inp, out, [{"start": start, "duration": clip_duration}], app, title_text=generate_tattoo_overlay("process", config.strategy))),
            ("closeup", config.closeups_dir, select_closeup_clips(source_video, duration, config)[:3], generate_tattoo_overlay("closeup", config.strategy), generate_tattoo_caption("closeup", source_video.stem, config.strategy), tattoo_cta, make_closeup_clip),
            ("satisfying", config.satisfying_dir, select_satisfying_clips(source_video, duration, config)[:2], generate_tattoo_overlay("shading", config.strategy), generate_tattoo_caption("satisfying", source_video.stem, config.strategy), "Сохрани идею для будущей тату", make_satisfying_clip),
        ]
        if include_portfolio:
            group_specs.append(("portfolio", config.portfolio_dir, select_portfolio_clips(source_video, duration, config)[:2], generate_tattoo_overlay("portfolio", config.strategy), generate_tattoo_caption("portfolio", source_video.stem, config.strategy), "Больше работ — в профиле", make_portfolio_clip))
        for clip_type, output_dir, clips, overlay_text, caption, cta, render_fn in group_specs:
            for index, clip in enumerate(clips, start=1):
                best = _render_visual_clip(
                    source_video=source_video,
                    source_slug=source_slug,
                    video_duration=duration,
                    clip_type=clip_type,
                    index=index,
                    start=float(clip["start"]),
                    duration=float(clip["duration"]),
                    output_dir=output_dir,
                    overlay_text=overlay_text,
                    caption=caption,
                    cta=cta,
                    hashtags=tags,
                    config=config,
                    directories=directories,
                    logger=logger,
                    summary_rows=summary_rows,
                    render_fn=render_fn,
                )
                if best is not None:
                    best_paths.append(best)
        montage = select_before_process_after(source_video, duration, config)
        before_after_path = config.before_after_dir / f"{source_slug}_before_after_01.mp4"
        make_before_after_reel(source_video, before_after_path, montage, config)
        montage_visuals = analyze_segment_visuals(source_video, float(montage["process"]["start"]), float(montage["process"]["duration"]))
        montage_duration = sum(float(montage[key]["duration"]) for key in ("before", "process", "after"))
        montage_caption = generate_tattoo_caption("before_after", source_video.stem, config.strategy)
        montage_scores = score_clip(montage_caption, montage_duration, strategy=config.strategy, tattoo_visual_score=float(montage_visuals.get("visual_score", 60) or 60))
        before_preview = directories["previews"] / f"{source_slug}_before_after_01.jpg"
        before_thumb = directories["thumbnails"] / f"{source_slug}_before_after_01.jpg"
        make_preview(source_video, before_preview, max(duration * 0.82, 0.1), logger=logger)
        make_thumbnail(source_video, before_thumb, max(duration * 0.82, 0.1), title_text="BEFORE / AFTER", logger=logger)
        best = _store_clip_result(
            config=config,
            source_video=source_video,
            clip_id="before_after_01",
            clip_type="before_after",
            start=float(montage["before"]["start"]),
            duration=montage_duration,
            text=montage_caption,
            hook=generate_tattoo_overlay("before", config.strategy),
            cta="Больше работ — в профиле",
            caption=montage_caption,
            hashtags=tags,
            overlay_text="BEFORE / PROCESS / AFTER",
            scores=montage_scores,
            visuals=montage_visuals,
            files={"primary": before_after_path, "preview": before_preview, "thumbnail": before_thumb},
            summary_rows=summary_rows,
        )
        if best is not None:
            best_paths.append(best)
        if include_stories:
            story_pool = select_closeup_clips(source_video, duration, config)[:2] or select_tattoo_process_clips(source_video, duration, config)[:2]
            for index, clip in enumerate(story_pool, start=1):
                story_overlay = generate_tattoo_overlay("story", config.strategy)
                story_duration = min(max(5.0, float(clip["duration"])), 12.0)
                best = _render_visual_clip(
                    source_video=source_video,
                    source_slug=source_slug,
                    video_duration=duration,
                    clip_type="story",
                    index=index,
                    start=float(clip["start"]),
                    duration=story_duration,
                    output_dir=config.stories_dir,
                    overlay_text=story_overlay,
                    caption=generate_tattoo_caption("story", source_video.stem, config.strategy),
                    cta="Запись открыта",
                    hashtags=tags,
                    config=config,
                    directories=directories,
                    logger=logger,
                    summary_rows=summary_rows,
                    render_fn=lambda inp, out, start, clip_duration, app: make_tattoo_process_reel(inp, out, [{"start": start, "duration": clip_duration}], app, title_text=story_overlay),
                )
                if best is not None:
                    best_paths.append(best)

    if render_enabled and ("timelapse" in modes or config.mode == "all" or duration > 180):
        target = _timelapse_target_duration(duration)
        speed = max(2, int(round(duration / target))) if duration > 0 else config.timelapse_speed
        clean_path = config.timelapse_dir / f"{source_slug}_timelapse_clean.mp4"
        overlay_path = config.timelapse_dir / f"{source_slug}_timelapse_overlay.mp4"
        ass_path = directories["subtitles"] / f"{source_slug}_timelapse.ass"
        preview_path = directories["previews"] / f"{source_slug}_timelapse.jpg"
        thumb_path = directories["thumbnails"] / f"{source_slug}_timelapse.jpg"
        make_timelapse(source_video, clean_path, speed, config.target_width, config.target_height, logger=logger)
        actual_duration = max(duration / max(speed, 1), 1.0)
        write_ass([], ass_path, start_offset=0, end_limit=actual_duration, hook_text="TATTOO TIMELAPSE", style=config.subtitle_style.name)
        burn_subtitles(clean_path, ass_path, overlay_path, logger=logger)
        make_preview(source_video, preview_path, min(duration / 2, max(duration - 0.1, 0.1)), logger=logger)
        make_thumbnail(source_video, thumb_path, min(duration / 2, max(duration - 0.1, 0.1)), title_text="TIMELAPSE", logger=logger)
        visuals = analyze_segment_visuals(source_video, max(duration * 0.35, 0.0), min(duration * 0.2, 12.0))
        caption = f"Таймлапс с тату-сеанса.\n\nИсточник: {source_video.stem}\nБольше работ — в профиле."
        scores = score_clip(caption, actual_duration, strategy=config.strategy, tattoo_visual_score=float(visuals.get('visual_score', 60) or 60))
        best = _store_clip_result(
            config=config,
            source_video=source_video,
            clip_id="timelapse_01",
            clip_type="timelapse",
            start=0.0,
            duration=actual_duration,
            text=caption,
            hook="TATTOO TIMELAPSE",
            cta="Больше работ — в профиле",
            caption=caption,
            hashtags=generate_tattoo_hashtags(),
            overlay_text="TATTOO TIMELAPSE",
            scores=scores,
            visuals=visuals,
            files={"primary": overlay_path, "clean": clean_path, "overlay": overlay_path, "subtitle_overlay": ass_path, "preview": preview_path, "thumbnail": thumb_path},
            summary_rows=summary_rows,
        )
        if best is not None:
            best_paths.append(best)

    report_path = config.reports_dir / f"{source_slug}.json"
    write_video_report(
        report_path,
        {
            "pipeline_version": PIPELINE_VERSION,
            "source_video": source_video.name,
            "duration": round(duration, 3),
            "speech_density": estimate_speech_density(cleaned_segments, duration),
            "transcription_status": transcript_payload["status"],
            "content_detection": detection,
            "modes": modes,
            "best_variants": [relative_to_or_absolute(path, config.project_root) for path in best_paths],
            "rows": [row for row in summary_rows if row.get("source_video") == source_video.name],
        },
    )
    if not config.analyze_only:
        processed_target = move_to_processed(source_video, config.processed_dir)
        stored_manifest[item.signature] = {
            "pipeline_version": PIPELINE_VERSION,
            "source_name": source_video.name,
            "processed_copy": processed_target.name,
            "report_path": relative_to_or_absolute(report_path, config.project_root),
            "best_variants": [relative_to_or_absolute(path, config.project_root) for path in best_paths],
        }
        if item.source_root.resolve() == config.downloads_dir.resolve():
            mark_download_as_processed(config.download_manifest_path, source_video, processed_target)


def process_pipeline(config: AppConfig, *, yadisk_url: str | None = None, links_file: Path | None = None) -> ProcessingSummary:
    ensure_directories(config.required_directories)
    logger = setup_logging(config.logs_dir, config.log_level)
    downloaded = _download_requested_sources(config, yadisk_url, links_file, logger)
    if config.download_only:
        logger.info("Download-only mode finished. downloaded=%s", downloaded)
        return ProcessingSummary(downloaded=downloaded, discovered=0, processed=0, skipped=0, failed=0)
    ffmpeg_ready = check_ffmpeg()
    if not ffmpeg_ready and not config.dry_run:
        raise RuntimeError("FFmpeg/ffprobe were not found in PATH. Install FFmpeg first, for example: winget install Gyan.FFmpeg")
    if not ffmpeg_ready and config.dry_run:
        logger.warning("FFmpeg/ffprobe are not available. Dry-run will only list candidate files.")
    stored_manifest, active_manifest = _load_manifests(config)
    videos = discover_videos(config.source_directories, config.video_extensions, config.processed_dir, active_manifest, logger, excluded_dirs=(config.downloads_tmp_dir, config.downloads_failed_dir))
    if not videos:
        logger.info("No new videos found in input/downloads.")
        return ProcessingSummary(downloaded=downloaded, discovered=0, processed=0, skipped=0, failed=0)

    summary_rows: list[dict[str, Any]] = []
    processed_count = 0
    skipped_count = 0
    failed_count = 0
    progress = tqdm(videos, desc="Processing videos", unit="video")
    for item in progress:
        progress.set_postfix(file=item.path.name)
        if config.dry_run:
            if ffmpeg_ready:
                info = get_video_info(item.path)
                detection = detect_content_type(item.path, transcript=None, video_info=info)
                logger.info("Dry-run: %s -> %.2fs, %sx%s, modes=%s", item.path.name, info["duration"], info["width"], info["height"], ",".join(_resolve_modes(config, detection, float(info["duration"]))))
            else:
                logger.info("Dry-run: found %s (FFmpeg not installed, so media probe is skipped)", item.path.name)
            skipped_count += 1
            continue
        try:
            _process_single_video(item, config, logger, stored_manifest, summary_rows)
            processed_count += 1
            if not config.analyze_only:
                write_json(config.processed_manifest_path, stored_manifest)
        except Exception as error:  # noqa: BLE001
            failed_count += 1
            logger.exception("Failed to process %s: %s", item.path, error)

    if summary_rows and config.enable_reports:
        write_summary_reports(summary_rows, config.reports_dir)
    logger.info("Finished. downloaded=%s discovered=%s processed=%s skipped=%s failed=%s", downloaded, len(videos), processed_count, skipped_count, failed_count)
    return ProcessingSummary(downloaded=downloaded, discovered=len(videos), processed=processed_count, skipped=skipped_count, failed=failed_count)
