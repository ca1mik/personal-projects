from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from apps.api.app.config import get_settings
from apps.api.app.errors import AppError, NotFoundError
from apps.api.app.schemas import (
    FileCategory,
    JobErrorPayload,
    JobLogEntry,
    JobRecord,
    JobStatus,
    JobType,
    StoredFile,
)


ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
CONTENT_TYPE_TO_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def ensure_storage_dirs() -> None:
    settings = get_settings()
    for path in (
        settings.storage_root,
        settings.jobs_dir,
        settings.inputs_dir,
        settings.outputs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def job_metadata_path(job_id: str) -> Path:
    return get_settings().jobs_dir / f"{job_id}.json"


def input_dir(job_id: str) -> Path:
    return get_settings().inputs_dir / job_id


def output_dir(job_id: str) -> Path:
    return get_settings().outputs_dir / job_id


def normalize_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-.").lower()
    return cleaned or "file"


def extension_for_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in ALLOWED_IMAGE_SUFFIXES:
        return suffix
    mapped = CONTENT_TYPE_TO_SUFFIX.get((upload.content_type or "").lower())
    if mapped:
        return mapped
    raise AppError(
        400,
        "INVALID_FILE_TYPE",
        "Only PNG, JPG, JPEG, and WEBP images are supported.",
    )


def _relative(path: Path) -> str:
    storage_root = get_settings().storage_root
    return path.relative_to(storage_root).as_posix()


def create_job_record(job_type: JobType, backend: str, params: dict[str, object]) -> JobRecord:
    ensure_storage_dirs()
    job_id = uuid4().hex
    now = utc_now()
    job = JobRecord(
        id=job_id,
        type=job_type,
        status=JobStatus.QUEUED,
        backend=backend,
        created_at=now,
        updated_at=now,
        params=params,
    )
    input_dir(job_id).mkdir(parents=True, exist_ok=True)
    output_dir(job_id).mkdir(parents=True, exist_ok=True)
    return append_log(job, "Job created.")


def append_log(job: JobRecord, message: str, level: str = "info") -> JobRecord:
    updated = job.model_copy(deep=True)
    updated.logs.append(JobLogEntry(timestamp=utc_now(), level=level, message=message))
    updated.updated_at = utc_now()
    return updated


def write_job(job: JobRecord) -> None:
    ensure_storage_dirs()
    target = job_metadata_path(job.id)
    payload = json.dumps(job.model_dump(mode="json"), indent=2)
    temp_path = target.with_suffix(".tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(target)


def _read_job_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_job(job_id: str) -> JobRecord:
    path = job_metadata_path(job_id)
    if not path.exists():
        raise NotFoundError(f"Job '{job_id}' was not found.")
    return JobRecord.model_validate_json(_read_job_text(path))


def list_jobs(*, include_deleted: bool = False) -> list[JobRecord]:
    ensure_storage_dirs()
    jobs: list[JobRecord] = []
    for path in sorted(get_settings().jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            job = JobRecord.model_validate_json(_read_job_text(path))
        except Exception:
            continue
        if not include_deleted and job.status == JobStatus.DELETED:
            continue
        jobs.append(job)
    return jobs


async def save_upload_file(job_id: str, upload: UploadFile, role: str) -> StoredFile:
    settings = get_settings()
    suffix = extension_for_upload(upload)
    base_name = normalize_filename(role)
    filename = f"{base_name}{suffix}"
    target_dir = input_dir(job_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    counter = 1
    while target_path.exists():
        filename = f"{base_name}-{counter}{suffix}"
        target_path = target_dir / filename
        counter += 1

    size = 0
    try:
        with target_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise AppError(
                        413,
                        "FILE_TOO_LARGE",
                        f"Files larger than {settings.max_upload_size_bytes // (1024 * 1024)}MB are not allowed.",
                    )
                handle.write(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return StoredFile(
        role=role,
        category=FileCategory.INPUT,
        filename=filename,
        relative_path=_relative(target_path),
        content_type=upload.content_type,
        original_name=normalize_filename(upload.filename or filename),
        size=size,
        created_at=utc_now(),
    )


def reset_job_for_rerun(job: JobRecord) -> JobRecord:
    updated = job.model_copy(deep=True)
    shutil.rmtree(output_dir(job.id), ignore_errors=True)
    output_dir(job.id).mkdir(parents=True, exist_ok=True)
    updated.status = JobStatus.QUEUED
    updated.error = None
    updated.output_files = []
    updated.deleted_at = None
    updated = append_log(updated, "Job reset for rerun.")
    return updated


def soft_delete_job(job: JobRecord) -> JobRecord:
    updated = job.model_copy(deep=True)
    updated.status = JobStatus.DELETED
    updated.deleted_at = utc_now()
    updated = append_log(updated, "Job soft-deleted.", level="warning")
    return updated


def asset_path_for(job: JobRecord, filename: str) -> Path:
    for file in [*job.input_files, *job.output_files]:
        if file.filename != filename:
            continue
        path = get_settings().storage_root / file.relative_path
        try:
            path.resolve().relative_to(get_settings().storage_root.resolve())
        except ValueError as exc:
            raise AppError(400, "INVALID_ASSET_PATH", "Resolved asset path escaped storage root.") from exc
        if not path.exists():
            raise NotFoundError(f"Asset '{filename}' for job '{job.id}' was not found.")
        return path
    raise NotFoundError(f"Asset '{filename}' for job '{job.id}' was not found.")


def set_job_error(job: JobRecord, code: str, message: str) -> JobRecord:
    updated = job.model_copy(deep=True)
    updated.status = JobStatus.FAILED
    updated.error = JobErrorPayload(code=code, message=message)
    updated = append_log(updated, message, level="error")
    return updated


def with_asset_urls(job: JobRecord) -> JobRecord:
    updated = job.model_copy(deep=True)
    for file in [*updated.input_files, *updated.output_files]:
        file.url = f"/api/assets/{updated.id}/{file.filename}"
    return updated
