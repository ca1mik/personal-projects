from __future__ import annotations

import json
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

from workers.common.errors import AdapterExecutionError
from workers.common.models import AdapterResult, GeneratedFile, JobContext


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _triangle_glb(generator_name: str) -> bytes:
    document = {
        "asset": {
            "version": "2.0",
            "generator": generator_name,
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 1, "NORMAL": 2},
                        "indices": 0,
                        "material": 0,
                    }
                ]
            }
        ],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.129, 0.737, 0.843, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.86,
                },
                "doubleSided": True,
            }
        ],
        "buffers": [{"byteLength": 80}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 6, "target": 34963},
            {"buffer": 0, "byteOffset": 8, "byteLength": 36, "target": 34962},
            {"buffer": 0, "byteOffset": 44, "byteLength": 36, "target": 34962},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5123,
                "count": 3,
                "type": "SCALAR",
                "max": [2],
                "min": [0],
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "max": [0.5, 0.5, 0.0],
                "min": [-0.5, -0.5, 0.0],
            },
            {
                "bufferView": 2,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
            },
        ],
    }
    json_bytes = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)

    indices = struct.pack("<3H", 0, 1, 2) + b"\x00\x00"
    positions = struct.pack(
        "<9f",
        -0.5,
        -0.5,
        0.0,
        0.5,
        -0.5,
        0.0,
        0.0,
        0.5,
        0.0,
    )
    normals = struct.pack("<9f", 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0)
    binary_chunk = indices + positions + normals

    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary_chunk)
    header = struct.pack("<III", 0x46546C67, 2, total_length)
    json_header = struct.pack("<II", len(json_bytes), 0x4E4F534A)
    bin_header = struct.pack("<II", len(binary_chunk), 0x004E4942)
    return header + json_header + json_bytes + bin_header + binary_chunk


def _write_text(path: Path, content: str) -> int:
    path.write_text(content, encoding="utf-8")
    return path.stat().st_size


def _generated_file(job_context: JobContext, role: str, filename: str, content_type: str) -> GeneratedFile:
    path = job_context.output_dir / filename
    return GeneratedFile(
        role=role,
        filename=filename,
        content_type=content_type,
        size=path.stat().st_size,
        relative_path=f"outputs/{job_context.job_id}/{filename}",
        created_at=utc_now(),
    )


def create_stub_outputs(job_context: JobContext, generator_name: str, delay_seconds: float) -> AdapterResult:
    job_context.output_dir.mkdir(parents=True, exist_ok=True)
    time.sleep(max(delay_seconds, 0))

    glb_path = job_context.output_dir / "model.glb"
    glb_path.write_bytes(_triangle_glb(generator_name))

    obj_size = _write_text(
        job_context.output_dir / "model.obj",
        "\n".join(
            [
                "# Enya stub OBJ output",
                "o StubMesh",
                "v -0.5 -0.5 0.0",
                "v 0.5 -0.5 0.0",
                "v 0.0 0.5 0.0",
                "vn 0.0 0.0 1.0",
                "f 1//1 2//1 3//1",
                "",
            ]
        ),
    )

    manifest = {
        "job_id": job_context.job_id,
        "generator": generator_name,
        "mode": "stub",
        "generated_at": utc_now(),
        "preview": {
            "primary": "model.glb",
            "secondary": "model.obj",
            "viewer": "model-viewer",
        },
        "notes": [
            "Stub output generated for local MVP validation.",
            "Replace this adapter mode with a real backend when available.",
        ],
        "input_roles": [file.role for file in job_context.input_files],
        "files": [
            {"role": "preview_glb", "filename": "model.glb"},
            {"role": "mesh_obj", "filename": "model.obj"},
        ],
    }
    manifest_path = job_context.output_dir / "manifest.json"
    _write_text(manifest_path, json.dumps(manifest, indent=2))

    output_files = [
        _generated_file(job_context, "preview_glb", "model.glb", "model/gltf-binary"),
        _generated_file(job_context, "mesh_obj", "model.obj", "text/plain"),
        _generated_file(job_context, "manifest", "manifest.json", "application/json"),
    ]
    return AdapterResult(
        output_files=output_files,
        manifest=manifest,
        logs=[
            f"{generator_name} stub executed.",
            f"Generated {len(output_files)} output files including a previewable GLB.",
            f"OBJ size: {obj_size} bytes.",
        ],
    )


def collect_standard_outputs(
    job_context: JobContext,
    *,
    generator_name: str,
    mode: str,
) -> AdapterResult:
    discovered: list[GeneratedFile] = []
    standard_files = [
        ("preview_glb", "model.glb", "model/gltf-binary"),
        ("mesh_obj", "model.obj", "text/plain"),
        ("rigged_glb", "rigged.glb", "model/gltf-binary"),
        ("rigged_fbx", "rigged.fbx", "application/octet-stream"),
        ("manifest", "manifest.json", "application/json"),
    ]

    for role, filename, content_type in standard_files:
        path = job_context.output_dir / filename
        if not path.exists():
            continue
        discovered.append(_generated_file(job_context, role, filename, content_type))

    if not discovered:
        raise AdapterExecutionError(
            "NO_OUTPUTS_FOUND",
            f"{generator_name} ({mode}) did not produce any files in {job_context.output_dir}.",
        )

    manifest_path = job_context.output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "job_id": job_context.job_id,
            "generator": generator_name,
            "mode": mode,
            "generated_at": utc_now(),
            "files": [{"role": file.role, "filename": file.filename} for file in discovered],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        discovered.append(_generated_file(job_context, "manifest", "manifest.json", "application/json"))

    return AdapterResult(
        output_files=discovered,
        manifest=manifest,
        logs=[f"{generator_name} {mode} execution completed."],
    )
