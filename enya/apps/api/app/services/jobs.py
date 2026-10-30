from __future__ import annotations

import threading
from typing import Any

from fastapi import UploadFile
from redis.exceptions import RedisError

from apps.api.app.config import get_settings
from apps.api.app.errors import AppError
from apps.api.app.queue import get_queue
from apps.api.app.schemas import FilesPayload, JobRecord, JobStatus, JobType
from apps.api.app.storage import (
    append_log,
    create_job_record,
    list_jobs,
    load_job,
    reset_job_for_rerun,
    save_upload_file,
    set_job_error,
    soft_delete_job,
    with_asset_urls,
    write_job,
)
from apps.api.app.worker_tasks import process_job


VALID_EXECUTION_MODES = {"auto", "stub", "http", "subprocess"}


def _normalize_execution_mode(execution_mode: str | None) -> str:
    value = (execution_mode or "auto").lower().strip()
    if value not in VALID_EXECUTION_MODES:
        raise AppError(400, "INVALID_EXECUTION_MODE", f"Execution mode must be one of: {', '.join(sorted(VALID_EXECUTION_MODES))}.")
    return value


def _enqueue(job: JobRecord) -> JobRecord:
    settings = get_settings()

    if settings.queue_mode == "inline":
        updated = job.model_copy(deep=True)
        updated.rq_job_id = f"inline-{job.id}"
        updated = append_log(updated, "Queued for inline background processing.")
        write_job(updated)

        worker_thread = threading.Thread(target=process_job, args=(job.id,), daemon=True)
        worker_thread.start()
        return updated

    try:
        rq_job = get_queue().enqueue(process_job, job.id, result_ttl=0, failure_ttl=86400)
    except RedisError as exc:
        failed_job = set_job_error(job, "QUEUE_UNAVAILABLE", "Redis/RQ is unavailable. Start Redis and the worker first.")
        write_job(failed_job)
        raise AppError(503, "QUEUE_UNAVAILABLE", "Redis/RQ is unavailable. Start Redis and the worker first.") from exc

    updated = job.model_copy(deep=True)
    updated.rq_job_id = rq_job.id
    updated = append_log(updated, f"Queued for processing via Redis/RQ ({rq_job.id}).")
    write_job(updated)
    return updated


async def create_single_image_job(image: UploadFile, execution_mode: str | None) -> JobRecord:
    params: dict[str, Any] = {"execution_mode": _normalize_execution_mode(execution_mode)}
    job = create_job_record(JobType.SINGLE_IMAGE, "sf3d", params)
    file_record = await save_upload_file(job.id, image, "reference")
    job.input_files.append(file_record)
    job.params["input_roles"] = ["reference"]
    job = append_log(job, "Single-image input saved.")
    write_job(job)
    queued = _enqueue(job)
    return with_asset_urls(queued)


async def create_multi_view_job(
    front: UploadFile,
    left: UploadFile,
    back: UploadFile,
    right: UploadFile | None,
    body_extras: list[UploadFile] | None,
    face_references: list[UploadFile] | None,
    execution_mode: str | None,
) -> JobRecord:
    params: dict[str, Any] = {"execution_mode": _normalize_execution_mode(execution_mode)}
    job = create_job_record(JobType.MULTI_VIEW, "hunyuan_mv", params)

    uploads = [("front", front), ("left", left), ("back", back)]
    if right is not None:
        uploads.append(("right", right))

    input_roles: list[str] = []
    for role, upload in uploads:
        file_record = await save_upload_file(job.id, upload, role)
        job.input_files.append(file_record)
        input_roles.append(role)

    body_extra_count = 0
    for index, upload in enumerate(body_extras or [], start=1):
        role = f"body-extra-{index:02d}"
        file_record = await save_upload_file(job.id, upload, role)
        job.input_files.append(file_record)
        input_roles.append(role)
        body_extra_count += 1

    face_reference_count = 0
    for index, upload in enumerate(face_references or [], start=1):
        role = f"face-reference-{index:02d}"
        file_record = await save_upload_file(job.id, upload, role)
        job.input_files.append(file_record)
        input_roles.append(role)
        face_reference_count += 1

    job.params["input_roles"] = input_roles
    job.params["view_count"] = len(input_roles)
    job.params["canonical_body_view_count"] = len(uploads)
    job.params["body_reference_count"] = body_extra_count
    job.params["face_reference_count"] = face_reference_count
    job = append_log(
        job,
        "Multi-view inputs saved "
        f"({len(uploads)} canonical body views, {body_extra_count} extra body references, "
        f"{face_reference_count} face references).",
    )
    write_job(job)
    queued = _enqueue(job)
    return with_asset_urls(queued)


def list_all_jobs() -> list[JobRecord]:
    return [with_asset_urls(job) for job in list_jobs()]


def get_job(job_id: str) -> JobRecord:
    return with_asset_urls(load_job(job_id))


def get_job_files(job_id: str) -> FilesPayload:
    job = with_asset_urls(load_job(job_id))
    return FilesPayload(input_files=job.input_files, output_files=job.output_files)


def rerun_job(job_id: str) -> JobRecord:
    job = load_job(job_id)
    if job.status == JobStatus.DELETED:
        raise AppError(409, "JOB_DELETED", "Deleted jobs cannot be rerun.")
    updated = reset_job_for_rerun(job)
    write_job(updated)
    queued = _enqueue(updated)
    return with_asset_urls(queued)


def delete_job(job_id: str) -> JobRecord:
    job = load_job(job_id)
    deleted = soft_delete_job(job)
    write_job(deleted)
    return with_asset_urls(deleted)
