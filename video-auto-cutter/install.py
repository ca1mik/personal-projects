from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from src.ffmpeg_utils import check_ffmpeg


PROJECT_ROOT = Path(__file__).resolve().parent


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10+ is required.")


def ffmpeg_available() -> bool:
    return check_ffmpeg() or (shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None)


def print_ffmpeg_help() -> None:
    print("FFmpeg или ffprobe не найдены в PATH.")
    print("Установить FFmpeg можно так:")
    print("  Windows: winget install Gyan.FFmpeg")
    print("  macOS:   brew install ffmpeg")
    print("  Ubuntu:  sudo apt update && sudo apt install ffmpeg")


def install_requirements() -> None:
    command = [sys.executable, "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")]
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        return
    print("Полная установка зависимостей не удалась. Пробую fallback без Whisper/OpenCV.")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "pyyaml",
            "python-dotenv",
            "requests",
            "tqdm",
            "pandas",
            "jinja2",
        ],
        check=True,
    )
    print("Whisper/OpenCV пропущены. Проект всё равно сможет работать в fallback-режиме.")


def create_directories() -> None:
    directories = [
        PROJECT_ROOT / "input",
        PROJECT_ROOT / "downloads",
        PROJECT_ROOT / "downloads" / "tmp",
        PROJECT_ROOT / "downloads" / "failed",
        PROJECT_ROOT / "output",
        PROJECT_ROOT / "output" / "best",
        PROJECT_ROOT / "output" / "talking",
        PROJECT_ROOT / "output" / "tattoo_process",
        PROJECT_ROOT / "output" / "closeups",
        PROJECT_ROOT / "output" / "satisfying",
        PROJECT_ROOT / "output" / "before_after",
        PROJECT_ROOT / "output" / "portfolio",
        PROJECT_ROOT / "output" / "timelapse",
        PROJECT_ROOT / "output" / "stories",
        PROJECT_ROOT / "output" / "previews",
        PROJECT_ROOT / "output" / "thumbnails",
        PROJECT_ROOT / "output" / "transcripts",
        PROJECT_ROOT / "output" / "subtitles",
        PROJECT_ROOT / "output" / "captions",
        PROJECT_ROOT / "output" / "metadata",
        PROJECT_ROOT / "output" / "reports",
        PROJECT_ROOT / "output" / "rejected",
        PROJECT_ROOT / "processed",
        PROJECT_ROOT / "logs",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def ensure_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    if not env_path.exists():
        shutil.copyfile(example_path, env_path)


def main() -> int:
    check_python_version()
    if not ffmpeg_available():
        print_ffmpeg_help()
    install_requirements()
    create_directories()
    ensure_env()
    print("Установка завершена.")
    print(f"Проект: {PROJECT_ROOT}")
    print("Команды:")
    print("  python install.py")
    print("  python run.py --dry-run")
    print('  python run.py --yadisk-url "https://disk.yandex.ru/d/T-qGlSvi7Pm_uA" --mode all')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
