from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = ROOT / "site"
ASSETS_ROOT = ROOT / "assets" / "portfolio"
DATA_ROOT = SITE_ROOT / "data"
LIBRARY_PATH = DATA_ROOT / "portfolio-library.json"
IMAGES_ROOT = SITE_ROOT / "images"
PORTFOLIO_ROOT = IMAGES_ROOT / "portfolio"
ORIGINALS_ROOT = PORTFOLIO_ROOT / "originals"
THUMBNAILS_ROOT = PORTFOLIO_ROOT / "thumbs"
PROCESS_ROOT = IMAGES_ROOT / "process"
MASTER_ROOT = IMAGES_ROOT / "master"
STUDIO_ROOT = IMAGES_ROOT / "studio"
REVIEWS_ROOT = IMAGES_ROOT / "reviews"
MANIFEST_PATH = DATA_ROOT / "portfolio.json"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_SUFFIXES = {".mov", ".mp4", ".m4v", ".webm"}
DEFAULT_SOURCES = (
    Path(r"F:\Yandex.Disk\ppdstr"),
    Path(r"C:\Users\koall\Yandex.Disk\ppdstr"),
    Path(r"C:\Users\koall\Яндекс Диск\ppdstr"),
)

FFMPEG_CANDIDATES = (
    os.getenv("FFMPEG_PATH", "").strip(),
    shutil.which("ffmpeg") or "",
    r"C:\Users\koall\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
)


def source_key(path: Path, source_root: Path) -> str:
    return path.relative_to(source_root).as_posix()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync local portfolio images into the public site and bot catalog."
    )
    parser.add_argument("--source", help="Folder with source images. Defaults to Yandex Disk path.")
    return parser.parse_args()


def resolve_source_path(raw_source: str | None) -> Path:
    if raw_source:
        path = Path(raw_source).expanduser()
        if path.exists():
            return path

    env_source = os.getenv("YANDEX_DISK_LOCAL_PATH", "").strip()
    if env_source:
        path = Path(env_source).expanduser()
        if path.exists():
            return path

    for candidate in DEFAULT_SOURCES:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("Portfolio source folder not found. Set --source or YANDEX_DISK_LOCAL_PATH.")

def ensure_dirs() -> None:
    portfolio_categories = (
        PORTFOLIO_ROOT / "lettering",
        PORTFOLIO_ROOT / "minimal",
        PORTFOLIO_ROOT / "graphic",
        PORTFOLIO_ROOT / "color",
        PORTFOLIO_ROOT / "characters",
        PORTFOLIO_ROOT / "healed",
        PORTFOLIO_ROOT / "sketches",
    )
    for folder in (
        DATA_ROOT,
        ORIGINALS_ROOT,
        THUMBNAILS_ROOT,
        PROCESS_ROOT,
        MASTER_ROOT,
        STUDIO_ROOT,
        REVIEWS_ROOT,
        ASSETS_ROOT / "fresh",
        ASSETS_ROOT / "graphic",
        ASSETS_ROOT / "lettering",
        ASSETS_ROOT / "minimal",
        ASSETS_ROOT / "color",
        ASSETS_ROOT / "characters",
        ASSETS_ROOT / "healed",
        *portfolio_categories,
    ):
        folder.mkdir(parents=True, exist_ok=True)


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def resolve_ffmpeg() -> str | None:
    for candidate in FFMPEG_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def load_library() -> dict[str, Any]:
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def save_library(library: dict[str, Any]) -> None:
    LIBRARY_PATH.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_output_dirs() -> None:
    managed_dirs = (
        ORIGINALS_ROOT,
        THUMBNAILS_ROOT,
        PORTFOLIO_ROOT / "lettering",
        PORTFOLIO_ROOT / "minimal",
        PORTFOLIO_ROOT / "graphic",
        PORTFOLIO_ROOT / "color",
        PORTFOLIO_ROOT / "characters",
        PORTFOLIO_ROOT / "healed",
        PORTFOLIO_ROOT / "sketches",
        PROCESS_ROOT,
        MASTER_ROOT,
        STUDIO_ROOT,
        ASSETS_ROOT / "fresh",
        ASSETS_ROOT / "graphic",
        ASSETS_ROOT / "lettering",
        ASSETS_ROOT / "minimal",
        ASSETS_ROOT / "color",
        ASSETS_ROOT / "characters",
        ASSETS_ROOT / "healed",
    )
    for folder in managed_dirs:
        if not folder.exists():
            continue
        for child in folder.iterdir():
            if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES:
                child.unlink()


def list_source_files(source_root: Path, suffixes: set[str]) -> list[Path]:
    return sorted(
        [path for path in source_root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes],
        key=lambda path: (path.stat().st_mtime, str(path).lower()),
        reverse=True,
    )


def list_source_images(source_root: Path) -> list[Path]:
    return list_source_files(source_root, IMAGE_SUFFIXES)


def build_source_lookup(source_root: Path, suffixes: set[str] | None = None) -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for source in list_source_files(source_root, suffixes or IMAGE_SUFFIXES):
        lookup[source_key(source, source_root)] = source
        lookup.setdefault(source.name, source)
    return lookup


def resolve_source_file(source_lookup: dict[str, Path], source_name: str) -> Path | None:
    return source_lookup.get(source_name) or source_lookup.get(source_name.replace("\\", "/"))


def sync_support_videos(library: dict[str, Any], source_root: Path) -> None:
    media_sync = library.get("media_sync", {})
    video_entries = media_sync.get("process_videos", [])
    if not isinstance(video_entries, list) or not video_entries:
        return

    video_lookup = build_source_lookup(source_root, VIDEO_SUFFIXES)
    for entry in video_entries:
        if not isinstance(entry, dict):
            continue
        source_name = str(entry.get("source_name", "")).strip()
        target_rel = str(entry.get("target", "")).strip().replace("\\", "/")
        if not source_name or not target_rel:
            continue
        source = resolve_source_file(video_lookup, source_name)
        if not source:
            continue
        target = SITE_ROOT / Path(target_rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "work"


def make_unique_id(base: str, used_ids: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used_ids:
        candidate = f"{base}-{index}"
        index += 1
    used_ids.add(candidate)
    return candidate


def auto_title_for_source(source: Path, default_title: str) -> str:
    digits = "".join(ch for ch in source.stem if ch.isdigit())
    if digits:
        return f"{default_title} {digits[-4:]}"
    return default_title


def should_auto_add_source(source: Path, source_root: Path, sync_settings: dict[str, Any]) -> bool:
    rel_key = source_key(source, source_root)
    auto_settings = sync_settings.get("auto_add", {})
    ignored_sources = {
        str(item).strip().replace("\\", "/").lower()
        for item in auto_settings.get("ignored_sources", [])
        if str(item).strip()
    }
    if rel_key.lower() in ignored_sources or source.name.lower() in ignored_sources:
        return False

    if source.parent != source_root:
        return True

    skip_prefixes = [str(item).strip().lower() for item in auto_settings.get("skip_prefixes", ["img_"])]
    return not any(source.name.lower().startswith(prefix) for prefix in skip_prefixes if prefix)


def sync_auto_entries(library: dict[str, Any], source_root: Path, source_lookup: dict[str, Path]) -> tuple[dict[str, Any], int]:
    sync_settings = library.setdefault("sync", {})
    auto_settings = sync_settings.setdefault("auto_add", {})
    if auto_settings.get("enabled", True) is False:
        return library, 0

    items = library.setdefault("items", [])
    used_sources = {
        str(entry.get("source_name", "")).strip().replace("\\", "/")
        for entry in items
        if isinstance(entry, dict) and str(entry.get("source_name", "")).strip()
    }
    used_ids = {
        str(entry.get("id", "")).strip()
        for entry in items
        if isinstance(entry, dict) and str(entry.get("id", "")).strip()
    }
    pinned_sources = [
        str(item).strip().replace("\\", "/")
        for item in auto_settings.get("pinned_sources", [])
        if str(item).strip()
    ]
    featured_sources = {
        str(item).strip().replace("\\", "/")
        for item in auto_settings.get("featured_sources", [])
        if str(item).strip()
    }

    default_category = str(auto_settings.get("default_category", "graphic")).strip() or "graphic"
    default_collection = str(auto_settings.get("default_collection", "portfolio")).strip() or "portfolio"
    default_title = str(auto_settings.get("default_title", "Свежая работа")).strip() or "Свежая работа"
    default_size = str(auto_settings.get("default_size", "размер уточняется")).strip() or "размер уточняется"
    default_place = str(auto_settings.get("default_place", "место уточняется")).strip() or "место уточняется"
    default_price = str(auto_settings.get("default_price", "по запросу")).strip() or "по запросу"
    default_description = str(
        auto_settings.get(
            "default_description",
            "Новая работа автоматически добавлена из локальной папки. Точный размер, место и стоимость уточним в переписке.",
        )
    ).strip()
    default_sessions = str(auto_settings.get("default_sessions", "1 сеанс")).strip() or "1 сеанс"
    default_tags = [str(tag).strip() for tag in auto_settings.get("default_tags", ["новая работа", "нужно подписать"]) if str(tag).strip()]

    candidates = [
        source
        for source in source_lookup.values()
        if source_key(source, source_root) not in used_sources
        and should_auto_add_source(source, source_root, sync_settings)
    ]
    seen_candidates: set[str] = set()
    deduped_candidates: list[Path] = []
    for source in candidates:
        rel_key = source_key(source, source_root)
        if rel_key in seen_candidates:
            continue
        seen_candidates.add(rel_key)
        deduped_candidates.append(source)

    pinned_index = {name: index for index, name in enumerate(pinned_sources)}
    deduped_candidates.sort(
        key=lambda source: (
            pinned_index.get(source_key(source, source_root), 10_000),
            -source.stat().st_mtime,
            source.name.lower(),
        )
    )

    inserted: list[dict[str, Any]] = []
    appended: list[dict[str, Any]] = []

    for source in deduped_candidates:
        rel_key = source_key(source, source_root)
        base_id = f"{default_category}-{slugify(source.stem)}"
        item_id = make_unique_id(base_id, used_ids)
        entry = {
            "id": item_id,
            "source_name": rel_key,
            "collection": default_collection,
            "category": default_category,
            "title": auto_title_for_source(source, default_title),
            "size": default_size,
            "place": default_place,
            "price": default_price,
            "sessions": default_sessions,
            "description": default_description,
            "tags": default_tags,
            "featured": rel_key in featured_sources,
            "alt": f"{default_title} PPDSTR",
            "auto_generated": True,
        }
        if rel_key in pinned_index:
            inserted.append(entry)
        else:
            appended.append(entry)

    if inserted:
        library["items"] = inserted + items + appended
    elif appended:
        library["items"] = items + appended
    else:
        library["items"] = items

    return library, len(inserted) + len(appended)


def destination_root(collection: str, category: str) -> Path:
    if collection == "portfolio":
        return PORTFOLIO_ROOT / category
    if collection == "process":
        return PROCESS_ROOT
    if collection == "studio":
        return STUDIO_ROOT
    if collection == "master":
        return MASTER_ROOT
    raise ValueError(f"Unsupported collection: {collection}")


def asset_root(category: str) -> Path:
    if category == "graphic":
        return ASSETS_ROOT / "graphic"
    if category == "lettering":
        return ASSETS_ROOT / "lettering"
    if category == "minimal":
        return ASSETS_ROOT / "minimal"
    if category == "color":
        return ASSETS_ROOT / "color"
    if category == "characters":
        return ASSETS_ROOT / "characters"
    if category == "healed":
        return ASSETS_ROOT / "healed"
    return ASSETS_ROOT / "fresh"


def maybe_resize(source: Path, optimized_target: Path, thumb_target: Path) -> None:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError:
        shutil.copy2(source, optimized_target)
        shutil.copy2(source, thumb_target)
        return

    temp_source: Path | None = None
    image_source = source

    try:
        try:
            with Image.open(source) as probe:
                probe.verify()
        except Exception:
            ffmpeg = resolve_ffmpeg()
            if not ffmpeg:
                raise
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                temp_source = Path(tmp.name)
            subprocess.run(
                [ffmpeg, "-y", "-i", str(source), "-frames:v", "1", "-update", "1", str(temp_source)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            image_source = temp_source

        with Image.open(image_source) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            optimized = image.copy()
            optimized.thumbnail((1800, 1800))
            optimized.save(optimized_target, format="WEBP", quality=84, method=6)

            thumb = image.copy()
            thumb.thumbnail((900, 900))
            thumb.save(thumb_target, format="JPEG", quality=82, optimize=True)
    finally:
        if temp_source and temp_source.exists():
            temp_source.unlink()


def build_item(
    entry: dict[str, Any],
    source: Path,
    category_labels: dict[str, str],
) -> dict[str, Any]:
    item_id = str(entry["id"]).strip()
    category = str(entry.get("category", "graphic")).strip()
    collection = str(entry.get("collection", "portfolio")).strip()
    image_dir = destination_root(collection, category)
    image_dir.mkdir(parents=True, exist_ok=True)

    original_target = ORIGINALS_ROOT / f"{item_id}{source.suffix.lower()}"
    optimized_target = image_dir / f"{item_id}.webp"
    thumb_target = THUMBNAILS_ROOT / f"{item_id}.jpg"
    asset_target = asset_root(category) / f"{item_id}{source.suffix.lower()}"

    shutil.copy2(source, original_target)
    try:
        shutil.copy2(source, asset_target)
    except PermissionError:
        pass
    maybe_resize(source, optimized_target, thumb_target)

    return {
        "id": item_id,
        "title": entry.get("title", item_id),
        "category": category,
        "category_label": category_labels.get(category, category.title()),
        "collection": collection,
        "image": "/" + optimized_target.relative_to(SITE_ROOT).as_posix(),
        "thumb": "/" + thumb_target.relative_to(SITE_ROOT).as_posix(),
        "original": "/" + original_target.relative_to(SITE_ROOT).as_posix(),
        "size": entry.get("size", ""),
        "place": entry.get("place", ""),
        "price": entry.get("price", ""),
        "sessions": entry.get("sessions", "1 сеанс"),
        "description": entry.get("description", ""),
        "tags": entry.get("tags", []),
        "featured": bool(entry.get("featured", False)),
        "alt": entry.get("alt") or entry.get("title", item_id),
        "source_name": str(entry.get("source_name", "")).strip(),
        "auto_generated": bool(entry.get("auto_generated", False)),
    }


def build_manifest(source_root: Path) -> dict[str, Any]:
    ensure_dirs()
    clean_output_dirs()

    source_lookup = build_source_lookup(source_root)
    library = load_library()
    library, auto_added = sync_auto_entries(library, source_root, source_lookup)
    if auto_added:
        save_library(library)
    sync_support_videos(library, source_root)

    categories = library.get("categories", [])
    category_labels = {
        item["key"]: item["label"]
        for item in categories
        if isinstance(item, dict) and item.get("key") and item.get("label")
    }
    items: list[dict[str, Any]] = []

    by_id: dict[str, dict[str, Any]] = {}

    for entry in library.get("items", []):
        if not isinstance(entry, dict):
            continue

        source_name = str(entry.get("source_name", "")).strip().replace("\\", "/")
        if not source_name:
            continue
        source = resolve_source_file(source_lookup, source_name)
        if source is None or not source.exists():
            raise FileNotFoundError(f"Missing portfolio source file: {source_root / source_name}")

        item = build_item(entry, source, category_labels)
        items.append(item)
        by_id[item["id"]] = item

    manifest = {
        "version": str(library.get("version", "2026-06-05")),
        "updated_at": timestamp(),
        "source": "local-yandex-library",
        "categories": categories,
        "items": items,
        "supporting": {
            "hero": [by_id[item_id] for item_id in library.get("supporting", {}).get("hero", []) if item_id in by_id],
            "master": by_id.get(str(library.get("supporting", {}).get("master", ""))),
            "studio": by_id.get(str(library.get("supporting", {}).get("studio", ""))),
            "process": [
                by_id[item_id]
                for item_id in library.get("supporting", {}).get("process", [])
                if item_id in by_id
            ],
        },
    }
    return manifest


def main() -> int:
    args = parse_args()
    source_root = resolve_source_path(args.source)
    manifest = build_manifest(source_root)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Portfolio source: {source_root}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Items: {len(manifest['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
