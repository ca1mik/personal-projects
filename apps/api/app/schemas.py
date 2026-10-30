from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JobType(str, Enum):
    SINGLE_IMAGE = "single-image"
    MULTI_VIEW = "multi-view"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    DELETED = "deleted"


class FileCategory(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class StoredFile(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    role: str
    category: FileCategory
    filename: str
    relative_path: str
    content_type: str | None = None
    original_name: str | None = None
    size: int = 0
    created_at: str
    url: str | None = None


class JobLogEntry(BaseModel):
    timestamp: str
    level: Literal["info", "warning", "error"] = "info"
    message: str


class JobErrorPayload(BaseModel):
    code: str
    message: str


class JobRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    type: JobType
    status: JobStatus
    backend: str
    created_at: str
    updated_at: str
    input_files: list[StoredFile] = Field(default_factory=list)
    output_files: list[StoredFile] = Field(default_factory=list)
    error: JobErrorPayload | None = None
    logs: list[JobLogEntry] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    deleted_at: str | None = None
    rq_job_id: str | None = None


class FilesPayload(BaseModel):
    input_files: list[StoredFile]
    output_files: list[StoredFile]

