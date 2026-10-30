from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Any, Iterable

import requests

from .utils import ensure_directories, load_json, slugify, write_json


PUBLIC_RESOURCE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"
PUBLIC_DOWNLOAD_URL = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
IGNORE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp"}
URL_PATTERN = re.compile(r"(?:disk\.yandex\.ru|yadi\.sk)/[di]/", re.IGNORECASE)
COPY_SUFFIX_PATTERN = re.compile(r" \(\d+\)$")


@dataclass(frozen=True)
class DownloadedResource:
    """Normalized downloaded Yandex.Disk resource."""

    public_url: str
    resource_path: str
    local_path: Path
    size_bytes: int
    mime_type: str | None


def is_yadisk_url(url: str) -> bool:
    """Return True when the string looks like a Yandex.Disk link."""
    return bool(URL_PATTERN.search(url.strip()))


def load_download_manifest(path: Path) -> dict[str, Any]:
    """Load the download manifest JSON."""
    return load_json(path, {})


def save_download_manifest(path: Path, data: dict[str, Any]) -> None:
    """Persist the download manifest JSON."""
    write_json(path, data)


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"OAuth {token}"
    return headers


def _request_json(endpoint: str, params: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    response = requests.get(endpoint, params=params, headers=_headers(token), timeout=60)
    if response.ok:
        return response.json()

    try:
        payload = response.json()
        message = payload.get("message") or payload.get("description") or response.text
    except ValueError:
        message = response.text

    if response.status_code in {401, 403}:
        raise RuntimeError(
            "Yandex.Disk link is not publicly accessible. "
            "Set YADISK_TOKEN in .env if you want to retry with authorization. "
            f"Details: {message}"
        )
    raise RuntimeError(f"Yandex.Disk API error {response.status_code}: {message}")


def get_public_resource_info(
    url: str,
    *,
    path: str | None = None,
    token: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Fetch metadata for a public Yandex.Disk resource."""
    params: dict[str, Any] = {"public_key": url, "limit": limit, "offset": offset}
    if path:
        params["path"] = path
    return _request_json(PUBLIC_RESOURCE_URL, params=params, token=token)


def get_public_download_url(url: str, *, path: str | None = None, token: str | None = None) -> str:
    """Resolve a direct download URL for a public resource."""
    params: dict[str, Any] = {"public_key": url}
    if path:
        params["path"] = path
    payload = _request_json(PUBLIC_DOWNLOAD_URL, params=params, token=token)
    href = str(payload.get("href", "")).strip()
    if not href:
        raise RuntimeError(f"Could not resolve download URL for {url} {path or ''}".strip())
    return href


def _normalized_key(path_value: str) -> str:
    path = Path(path_value)
    normalized_stem = COPY_SUFFIX_PATTERN.sub("", path.stem)
    return str(Path(path.parent.as_posix()) / f"{normalized_stem}{path.suffix.lower()}")


def _preferred_resource(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    existing_name = str(existing.get("name", ""))
    candidate_name = str(candidate.get("name", ""))
    if " (" in existing_name and " (" not in candidate_name:
        return candidate
    if int(candidate.get("size", 0) or 0) > int(existing.get("size", 0) or 0):
        return candidate
    if len(candidate_name) < len(existing_name):
        return candidate
    return existing


def _walk_public_folder(url: str, *, token: str | None = None) -> list[dict[str, Any]]:
    queue = ["/"]
    files: list[dict[str, Any]] = []
    seen_dirs: set[str] = set()

    while queue:
        current_path = queue.pop(0)
        if current_path in seen_dirs:
            continue
        seen_dirs.add(current_path)

        offset = 0
        while True:
            resource = get_public_resource_info(url, path=current_path, token=token, limit=200, offset=offset)
            resource_type = str(resource.get("type", ""))
            if resource_type == "file":
                files.append(resource)
                break

            embedded = resource.get("_embedded", {}) or {}
            items = embedded.get("items", []) or []
            for item in items:
                item_type = str(item.get("type", ""))
                if item_type == "dir":
                    queue.append(str(item.get("path", "")))
                elif item_type == "file":
                    files.append(item)

            offset += len(items)
            total = int(embedded.get("total", len(items)) or len(items))
            if offset >= total or not items:
                break

    deduped: dict[str, dict[str, Any]] = {}
    for item in files:
        ext = Path(str(item.get("name", ""))).suffix.lower()
        if ext in IGNORE_EXTENSIONS or ext not in SUPPORTED_EXTENSIONS:
            continue
        key = _normalized_key(str(item.get("path", "")))
        existing = deduped.get(key)
        deduped[key] = item if existing is None else _preferred_resource(existing, item)
    return sorted(deduped.values(), key=lambda item: str(item.get("path", "")))


def _filter_items(
    items: list[dict[str, Any]],
    *,
    max_files: int | None = None,
    max_size_bytes: int | None = None,
) -> list[dict[str, Any]]:
    filtered = items
    if max_size_bytes is not None:
        filtered = [item for item in filtered if int(item.get("size", 0) or 0) <= max_size_bytes]
    filtered = sorted(filtered, key=lambda item: (int(item.get("size", 0) or 0), str(item.get("name", "")).lower()))
    if max_files is not None:
        filtered = filtered[:max_files]
    return filtered


def _target_path(output_dir: Path, resource_path: str) -> Path:
    relative_parts = [slugify(part) for part in Path(resource_path).parts if part not in {"/", "\\"}]
    if not relative_parts:
        raise RuntimeError(f"Invalid resource path: {resource_path}")
    return output_dir.joinpath(*relative_parts)


def _download_stream(
    href: str,
    target_path: Path,
    tmp_dir: Path,
    failed_dir: Path,
) -> None:
    ensure_directories([target_path.parent, tmp_dir, failed_dir])
    tmp_path = tmp_dir / f"{target_path.name}.part"
    response = requests.get(href, stream=True, timeout=120)
    response.raise_for_status()
    try:
        with tmp_path.open("wb") as destination:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    destination.write(chunk)
        tmp_path.replace(target_path)
    except Exception:
        if tmp_path.exists():
            failed_path = failed_dir / tmp_path.name
            tmp_path.replace(failed_path)
        raise


def _should_skip_download(
    manifest: dict[str, Any],
    manifest_key: str,
    target_path: Path,
    size_bytes: int,
) -> bool:
    record = manifest.get(manifest_key, {})
    if not target_path.exists():
        archived_path = Path(str(record.get("archived_path", ""))) if record.get("archived_path") else None
        if archived_path and archived_path.exists() and int(record.get("size_bytes", 0) or 0) == size_bytes:
            return True
        return False
    if int(record.get("size_bytes", 0) or 0) != size_bytes:
        return False
    return int(target_path.stat().st_size) == size_bytes


def download_public_yadisk_file(
    url: str,
    output_dir: Path,
    *,
    token: str | None = None,
    manifest_path: Path | None = None,
    tmp_dir: Path | None = None,
    failed_dir: Path | None = None,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
    max_files: int | None = None,
    max_size_bytes: int | None = None,
) -> list[DownloadedResource]:
    """Download one public Yandex.Disk file."""
    info = get_public_resource_info(url, token=token)
    if str(info.get("type", "")) != "file":
        raise RuntimeError(f"Resource is not a single file: {url}")
    items = _filter_items([info], max_files=max_files, max_size_bytes=max_size_bytes)
    return _download_items(
        url,
        items,
        output_dir,
        token=token,
        manifest_path=manifest_path,
        tmp_dir=tmp_dir,
        failed_dir=failed_dir,
        dry_run=dry_run,
        logger=logger,
    )


def _download_items(
    url: str,
    items: list[dict[str, Any]],
    output_dir: Path,
    *,
    token: str | None = None,
    manifest_path: Path | None = None,
    tmp_dir: Path | None = None,
    failed_dir: Path | None = None,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> list[DownloadedResource]:
    manifest_path = manifest_path or (output_dir.parent / "download_manifest.json")
    tmp_dir = tmp_dir or (output_dir / "tmp")
    failed_dir = failed_dir or (output_dir / "failed")
    manifest = load_download_manifest(manifest_path)
    results: list[DownloadedResource] = []

    for item in items:
        resource_path = str(item.get("path", ""))
        size_bytes = int(item.get("size", 0) or 0)
        target_path = _target_path(output_dir, resource_path)
        manifest_key = f"{url}::{resource_path}"
        mime_type = item.get("mime_type")

        if _should_skip_download(manifest, manifest_key, target_path, size_bytes):
            if logger is not None:
                logger.info("Skipping already downloaded resource %s", resource_path)
            results.append(
                DownloadedResource(
                    public_url=url,
                    resource_path=resource_path,
                    local_path=target_path,
                    size_bytes=size_bytes,
                    mime_type=str(mime_type) if mime_type else None,
                )
            )
            continue

        if dry_run:
            if logger is not None:
                logger.info("Dry-run download candidate: %s", resource_path)
            continue

        href = get_public_download_url(url, path=resource_path, token=token)
        if logger is not None:
            logger.info("Downloading Yandex resource %s -> %s", resource_path, target_path)
        _download_stream(href, target_path, tmp_dir, failed_dir)
        manifest[manifest_key] = {
            "public_url": url,
            "resource_path": resource_path,
            "local_path": str(target_path),
            "size_bytes": size_bytes,
            "mime_type": mime_type,
            "status": "downloaded",
        }
        results.append(
            DownloadedResource(
                public_url=url,
                resource_path=resource_path,
                local_path=target_path,
                size_bytes=size_bytes,
                mime_type=str(mime_type) if mime_type else None,
            )
        )

    if not dry_run:
        save_download_manifest(manifest_path, manifest)
    return results


def mark_download_as_processed(manifest_path: Path, original_path: Path, processed_path: Path) -> None:
    """Update download manifest when a downloaded source has been archived."""
    manifest = load_download_manifest(manifest_path)
    updated = False
    for record in manifest.values():
        if Path(str(record.get("local_path", ""))) == original_path:
            record["archived_path"] = str(processed_path)
            record["local_path"] = str(processed_path)
            record["status"] = "processed"
            updated = True
    if updated:
        save_download_manifest(manifest_path, manifest)


def download_public_yadisk_folder(
    url: str,
    output_dir: Path,
    *,
    token: str | None = None,
    manifest_path: Path | None = None,
    tmp_dir: Path | None = None,
    failed_dir: Path | None = None,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
    max_files: int | None = None,
    max_size_bytes: int | None = None,
) -> list[DownloadedResource]:
    """Download all supported video files from a public Yandex.Disk folder."""
    items = _filter_items(_walk_public_folder(url, token=token), max_files=max_files, max_size_bytes=max_size_bytes)
    return _download_items(
        url,
        items,
        output_dir,
        token=token,
        manifest_path=manifest_path,
        tmp_dir=tmp_dir,
        failed_dir=failed_dir,
        dry_run=dry_run,
        logger=logger,
    )


def download_from_links_file(
    path: Path,
    output_dir: Path,
    *,
    token: str | None = None,
    manifest_path: Path | None = None,
    tmp_dir: Path | None = None,
    failed_dir: Path | None = None,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
    max_files: int | None = None,
    max_size_bytes: int | None = None,
) -> list[DownloadedResource]:
    """Download all resources listed in a text file."""
    if not path.exists():
        raise FileNotFoundError(path)

    urls = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results: list[DownloadedResource] = []
    for url in urls:
        if not is_yadisk_url(url):
            if logger is not None:
                logger.warning("Skipping non-Yandex link from links file: %s", url)
            continue
        info = get_public_resource_info(url, token=token)
        if str(info.get("type", "")) == "file":
            results.extend(
                download_public_yadisk_file(
                    url,
                    output_dir,
                    token=token,
                    manifest_path=manifest_path,
                    tmp_dir=tmp_dir,
                    failed_dir=failed_dir,
                    dry_run=dry_run,
                    logger=logger,
                    max_files=max_files,
                    max_size_bytes=max_size_bytes,
                )
            )
        else:
            results.extend(
                download_public_yadisk_folder(
                    url,
                    output_dir,
                    token=token,
                    manifest_path=manifest_path,
                    tmp_dir=tmp_dir,
                    failed_dir=failed_dir,
                    dry_run=dry_run,
                    logger=logger,
                    max_files=max_files,
                    max_size_bytes=max_size_bytes,
                )
            )
    return results
