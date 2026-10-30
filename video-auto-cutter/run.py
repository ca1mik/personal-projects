from __future__ import annotations

import argparse
from pathlib import Path

from src.config import load_config
from src.processor import process_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Tattoo-focused automatic Reels/Shorts/TikTok generator for Yandex.Disk videos."
    )
    parser.add_argument("--config", help="Path to YAML config file")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without rendering clips")
    parser.add_argument("--install-check", action="store_true", help="Print resolved config and environment info")
    parser.add_argument("--analyze-only", action="store_true", help="Download and analyze videos without rendering clips")
    parser.add_argument("--download-only", action="store_true", help="Download videos and stop before processing")
    parser.add_argument("--yadisk-url", help="Public or private Yandex.Disk URL")
    parser.add_argument("--links", help="Path to text file with one Yandex.Disk URL per line")
    parser.add_argument("--input", help="Override input directory")
    parser.add_argument("--output", help="Override output directory")
    parser.add_argument("--downloads", help="Override downloads directory")
    parser.add_argument("--processed", help="Override processed directory")
    parser.add_argument("--clips-per-video", type=int, help="Number of clips to generate per source video")
    parser.add_argument("--strategy", choices=["aggressive", "balanced", "expert"], help="Generation strategy")
    parser.add_argument("--mode", choices=["auto", "talking", "tattoo", "timelapse", "portfolio", "all"], help="Tattoo content mode")
    parser.add_argument("--make-stories", action="store_true", help="Render additional 5-15 second story clips")
    parser.add_argument("--no-transcription", action="store_true", help="Disable Whisper transcription")
    parser.add_argument("--no-subtitles", action="store_true", help="Disable subtitle rendering")
    parser.add_argument("--no-hooks", action="store_true", help="Disable hook generation")
    parser.add_argument("--no-cta", action="store_true", help="Disable CTA generation")
    return parser


def main() -> int:
    """Run the CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    overrides = {
        "input_dir": args.input,
        "output_dir": args.output,
        "downloads_dir": args.downloads,
        "processed_dir": args.processed,
        "clips_per_video": args.clips_per_video,
        "strategy": args.strategy,
        "mode": args.mode,
        "make_stories": True if args.make_stories else None,
        "enable_transcription": False if args.no_transcription else None,
        "enable_subtitles": False if args.no_subtitles else None,
        "enable_hooks": False if args.no_hooks else None,
        "enable_cta": False if args.no_cta else None,
        "dry_run": args.dry_run,
        "analyze_only": args.analyze_only,
        "download_only": args.download_only,
    }
    config = load_config(config_path, overrides=overrides)

    if args.install_check:
        print(f"Config file: {config_path}")
        print(f"Project root: {config.project_root}")
        print(f"Input dir: {config.input_dir}")
        print(f"Downloads dir: {config.downloads_dir}")
        print(f"Output dir: {config.output_dir}")
        print(f"Processed dir: {config.processed_dir}")
        print(f"Logs dir: {config.logs_dir}")
        print(f"Strategy: {config.strategy}")
        print(f"Mode: {config.mode}")
        print(f"Clips per video: {config.clips_per_video}")
        print(f"Transcription enabled: {config.enable_transcription}")
        print(f"Subtitles enabled: {config.enable_subtitles}")
        print(f"Hooks enabled: {config.enable_hooks}")
        print(f"CTA enabled: {config.enable_cta}")
        print(f"Reports enabled: {config.enable_reports}")
        print(f"Generate variants: {config.generate_variants}")
        print(f"Make stories: {config.make_stories}")
        print(f"Max download files per run: {config.max_download_files_per_run}")
        print(f"Max download size MB: {config.max_download_size_mb}")
        print(f"YADISK token configured: {bool(config.yadisk_token)}")
        print(f"OpenAI key configured: {bool(config.openai_api_key)}")
        return 0

    summary = process_pipeline(
        config,
        yadisk_url=args.yadisk_url,
        links_file=Path(args.links).resolve() if args.links else None,
    )
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
