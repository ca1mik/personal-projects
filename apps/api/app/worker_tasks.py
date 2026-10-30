from __future__ import annotations

import traceback

from apps.api.app.schemas import FileCategory, JobRecord, JobStatus, StoredFile
from apps.api.app.storage import append_log, input_dir, load_job, output_dir, set_job_error, write_job
from workers.common.errors import AdapterExecutionError
from workers.common.models import GeneratedFile, JobContext, JobInput
from workers.hunyuan_mv.adapter import generate_multiview_to_3d
from workers.sf3d.adapter import generate_single_image_to_3d


def _build_context(job: JobRecord) -> JobContext:
    inputs = [
        JobInput(
            role=file.role,
            filename=file.filename,
            original_name=file.original_name,
            content_type=file.content_type,
            size=file.size,
            relative_path=file.relative_path,
        )
        for file in job.input_files
    ]
    return JobContext(
        job_id=job.id,
        job_type=job.type,
        backend=job.backend,
        params=job.params,
        input_files=inputs,
        input_dir=input_dir(job.id),
        output_dir=output_dir(job.id),
    )


def _to_stored_file(generated: GeneratedFile) -> StoredFile:
    return StoredFile(
        role=generated.role,
        category=FileCategory.OUTPUT,
        filename=generated.filename,
        relative_path=generated.relative_path,
        content_type=generated.content_type,
        original_name=generated.filename,
        size=generated.size,
        created_at=generated.created_at,
    )


def process_job(job_id: str) -> dict[str, object]:
    job = load_job(job_id)
    if job.status == JobStatus.DELETED:
        raise AdapterExecutionError("JOB_DELETED", "Deleted jobs cannot be processed.")

    job.status = JobStatus.PROCESSING
    job.error = None
    job = append_log(job, f"Worker started processing with backend '{job.backend}'.")
    write_job(job)

    try:
        context = _build_context(job)
        if job.type == "single-image":
            result = generate_single_image_to_3d(context)
        else:
            result = generate_multiview_to_3d(context)

        completed = load_job(job_id)
        completed.status = JobStatus.DONE
        completed.error = None
        completed.output_files = [_to_stored_file(file) for file in result.output_files]
        for line in result.logs:
            completed = append_log(completed, line)
        completed = append_log(completed, "Job completed successfully.")
        write_job(completed)
        return result.manifest
    except AdapterExecutionError as exc:
        failed = set_job_error(load_job(job_id), exc.code, exc.message)
        write_job(failed)
        raise
    except Exception as exc:
        failed = set_job_error(load_job(job_id), "UNHANDLED_WORKER_ERROR", str(exc))
        failed = append_log(failed, traceback.format_exc(), level="error")
        write_job(failed)
        raise

