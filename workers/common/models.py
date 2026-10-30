from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class JobInput:
    role: str
    filename: str
    original_name: str | None
    content_type: str | None
    size: int
    relative_path: str


@dataclass(slots=True)
class JobContext:
    job_id: str
    job_type: str
    backend: str
    params: dict[str, Any]
    input_files: list[JobInput]
    input_dir: Path
    output_dir: Path


@dataclass(slots=True)
class GeneratedFile:
    role: str
    filename: str
    content_type: str
    size: int
    relative_path: str
    created_at: str


@dataclass(slots=True)
class AdapterResult:
    output_files: list[GeneratedFile]
    manifest: dict[str, Any]
    logs: list[str] = field(default_factory=list)

