from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def log(message: str) -> None:
    print(f"[enya-bridge] {message}")


def env_path(name: str, default: str | Path | None = None) -> Path:
    raw = os.getenv(name)
    if raw:
        return Path(raw).expanduser().resolve()
    if default is None:
        raise SystemExit(f"Environment variable {name} is required.")
    return Path(default).expanduser().resolve()


def env_json(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Environment variable {name} must contain valid JSON.") from exc


def load_job_context() -> dict[str, Any]:
    job_id = os.getenv("ENYA_JOB_ID")
    if not job_id:
        raise SystemExit("ENYA_JOB_ID is required.")

    input_dir = env_path("ENYA_INPUT_DIR")
    output_dir = env_path("ENYA_OUTPUT_DIR")
    output_dir.mkdir(parents=True, exist_ok=True)

    return {
        "job_id": job_id,
        "job_type": os.getenv("ENYA_JOB_TYPE", ""),
        "backend": os.getenv("ENYA_BACKEND", ""),
        "input_dir": input_dir,
        "output_dir": output_dir,
        "input_files": env_json("ENYA_INPUT_FILES_JSON", []),
        "params": env_json("ENYA_JOB_PARAMS_JSON", {}),
    }


def input_path(job: dict[str, Any], role: str) -> Path | None:
    for item in job["input_files"]:
        if item.get("role") != role:
            continue
        filename = item.get("filename")
        if not filename:
            continue
        path = job["input_dir"] / filename
        if path.exists():
            return path
    return None


def input_paths_by_prefix(job: dict[str, Any], prefix: str) -> list[Path]:
    discovered: list[tuple[str, Path]] = []
    for item in job["input_files"]:
        role = str(item.get("role", ""))
        filename = item.get("filename")
        if not role.startswith(prefix) or not filename:
            continue
        path = job["input_dir"] / filename
        if path.exists():
            discovered.append((role, path))
    discovered.sort(key=lambda item: item[0])
    return [path for _, path in discovered]


def write_manifest(output_dir: Path, payload: dict[str, Any]) -> Path:
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def optional_export_obj(glb_path: Path, obj_path: Path) -> str | None:
    try:
        import trimesh
    except Exception as exc:
        return f"Skipping OBJ export because trimesh is unavailable: {exc}"

    try:
        mesh = trimesh.load(glb_path, force="mesh")
        mesh.export(obj_path)
    except Exception as exc:
        return f"Skipping OBJ export because GLB->OBJ conversion failed: {exc}"
    return None

