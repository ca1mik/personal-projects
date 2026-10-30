from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _to_path(value: str, *, base: Path = PROJECT_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    project_root: Path
    storage_root: Path
    api_host: str
    api_port: int
    web_host: str
    web_port: int
    web_origins: list[str]
    queue_mode: str
    redis_url: str
    queue_name: str
    max_upload_size_bytes: int
    worker_job_timeout_seconds: int
    stub_single_delay_seconds: float
    stub_multi_delay_seconds: float

    @property
    def jobs_dir(self) -> Path:
        return self.storage_root / "jobs"

    @property
    def inputs_dir(self) -> Path:
        return self.storage_root / "inputs"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_root / "outputs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    queue_mode = os.getenv("QUEUE_MODE", "redis").strip().lower()
    if queue_mode not in {"redis", "inline"}:
        queue_mode = "redis"
    return Settings(
        project_root=PROJECT_ROOT,
        storage_root=_to_path(os.getenv("STORAGE_DIR", "storage")),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        web_host=os.getenv("WEB_HOST", "0.0.0.0"),
        web_port=int(os.getenv("WEB_PORT", "3000")),
        web_origins=_csv(
            os.getenv(
                "WEB_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            )
        ),
        queue_mode=queue_mode,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        queue_name=os.getenv("RQ_QUEUE_NAME", "enya-jobs"),
        max_upload_size_bytes=max_upload_size_mb * 1024 * 1024,
        worker_job_timeout_seconds=int(os.getenv("WORKER_JOB_TIMEOUT_SECONDS", "1800")),
        stub_single_delay_seconds=float(os.getenv("STUB_SINGLE_DELAY_SECONDS", "2.0")),
        stub_multi_delay_seconds=float(os.getenv("STUB_MULTI_DELAY_SECONDS", "4.0")),
    )
