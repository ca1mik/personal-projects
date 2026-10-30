from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse

from apps.api.app.services.jobs import (
    create_multi_view_job,
    create_single_image_job,
    delete_job,
    get_job,
    get_job_files,
    list_all_jobs,
    rerun_job,
)
from apps.api.app.storage import asset_path_for, load_job


router = APIRouter(prefix="/api")


@router.post("/jobs/single-image")
async def create_single_image(
    image: UploadFile = File(...),
    execution_mode: str = Form("auto"),
) -> dict[str, object]:
    job = await create_single_image_job(image, execution_mode)
    return {"ok": True, "data": jsonable_encoder(job)}


@router.post("/jobs/multi-view")
async def create_multi_view(
    front: UploadFile = File(...),
    left: UploadFile = File(...),
    back: UploadFile = File(...),
    right: UploadFile | None = File(default=None),
    body_extras: list[UploadFile] | None = File(default=None),
    face_references: list[UploadFile] | None = File(default=None),
    execution_mode: str = Form("auto"),
) -> dict[str, object]:
    job = await create_multi_view_job(front, left, back, right, body_extras, face_references, execution_mode)
    return {"ok": True, "data": jsonable_encoder(job)}


@router.get("/jobs")
def list_jobs() -> dict[str, object]:
    jobs = list_all_jobs()
    return {"ok": True, "data": {"items": jsonable_encoder(jobs)}}


@router.get("/jobs/{job_id}")
def get_job_detail(job_id: str) -> dict[str, object]:
    job = get_job(job_id)
    return {"ok": True, "data": jsonable_encoder(job)}


@router.get("/jobs/{job_id}/files")
def get_files(job_id: str) -> dict[str, object]:
    payload = get_job_files(job_id)
    return {"ok": True, "data": jsonable_encoder(payload)}


@router.get("/assets/{job_id}/{filename}")
def get_asset(job_id: str, filename: str) -> FileResponse:
    job = load_job(job_id)
    path = asset_path_for(job, filename)
    media_type = mimetypes.guess_type(Path(filename).name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=Path(filename).name)


@router.post("/jobs/{job_id}/rerun")
def rerun(job_id: str) -> dict[str, object]:
    job = rerun_job(job_id)
    return {"ok": True, "data": jsonable_encoder(job)}


@router.delete("/jobs/{job_id}")
def delete(job_id: str) -> dict[str, object]:
    job = delete_job(job_id)
    return {"ok": True, "data": {"id": job.id, "status": job.status}}
