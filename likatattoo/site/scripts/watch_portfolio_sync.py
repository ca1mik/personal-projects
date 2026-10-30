from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from sync_portfolio import IMAGE_SUFFIXES, VIDEO_SUFFIXES, ROOT, resolve_source_path, source_key, timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch the local portfolio folder and rebuild site assets on change.")
    parser.add_argument("--source", help="Folder with source images. Defaults to the configured Yandex Disk path.")
    parser.add_argument("--interval", type=float, default=6.0, help="Polling interval in seconds.")
    parser.add_argument(
        "--build-bundle",
        action="store_true",
        help="Also rebuild deploy/reg-ru/ppdstr.ru-upload.zip after each detected change.",
    )
    return parser.parse_args()


def snapshot(source_root: Path) -> dict[str, tuple[int, int]]:
    state: dict[str, tuple[int, int]] = {}
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (IMAGE_SUFFIXES | VIDEO_SUFFIXES):
            continue
        stat = path.stat()
        state[source_key(path, source_root)] = (int(stat.st_mtime), int(stat.st_size))
    return state


def run_step(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def main() -> int:
    args = parse_args()
    source_root = resolve_source_path(args.source)
    sync_script = ROOT / "site" / "scripts" / "sync_portfolio.py"
    bundle_script = ROOT / "site" / "scripts" / "build_reg_ru_bundle.py"

    print(f"[{timestamp()}] Watching portfolio source: {source_root}")
    previous = snapshot(source_root)

    run_step([sys.executable, str(sync_script), "--source", str(source_root)])
    if args.build_bundle:
        run_step([sys.executable, str(bundle_script)])

    while True:
        time.sleep(max(args.interval, 1.0))
        current = snapshot(source_root)
        if current == previous:
            continue
        print(f"[{timestamp()}] Change detected, rebuilding portfolio assets...")
        run_step([sys.executable, str(sync_script), "--source", str(source_root)])
        if args.build_bundle:
            run_step([sys.executable, str(bundle_script)])
        previous = current


if __name__ == "__main__":
    raise SystemExit(main())
