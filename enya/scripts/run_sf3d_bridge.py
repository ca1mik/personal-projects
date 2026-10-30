from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bridge_utils import input_path, load_job_context, log, optional_export_obj, project_root, utc_now, write_manifest


def _find_mesh_glb(root: Path) -> Path:
    direct = root / "0" / "mesh.glb"
    if direct.exists():
        return direct

    for candidate in root.rglob("mesh.glb"):
        return candidate
    raise SystemExit(f"Stable Fast 3D did not produce mesh.glb under {root}.")


def main() -> None:
    job = load_job_context()
    image_path = input_path(job, "reference")
    if image_path is None:
        raise SystemExit("Stable Fast 3D bridge requires a 'reference' input image.")

    repo_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else os.getenv("SF3D_REPO_PATH", str(project_root() / "third_party" / "stable-fast-3d"))
    ).resolve()
    if not (repo_path / "run.py").exists():
        raise SystemExit(
            f"Stable Fast 3D repo was not found at {repo_path}. "
            "Clone the official repo or set SF3D_REPO_PATH / pass the repo path as an argument."
        )

    python_bin = sys.argv[2] if len(sys.argv) > 2 else os.getenv("SF3D_PYTHON_BIN", sys.executable)
    pretrained_model = sys.argv[3] if len(sys.argv) > 3 else os.getenv("SF3D_PRETRAINED_MODEL", "stabilityai/stable-fast-3d")
    device = os.getenv("SF3D_DEVICE", "cuda")
    texture_resolution = os.getenv("SF3D_TEXTURE_RESOLUTION", "1024")
    remesh_option = os.getenv("SF3D_REMESH_OPTION", "none")
    target_vertex_count = os.getenv("SF3D_TARGET_VERTEX_COUNT", "-1")

    temp_output = Path(tempfile.mkdtemp(prefix=f"enya-sf3d-{job['job_id']}-"))
    command = [
        python_bin,
        str(repo_path / "run.py"),
        str(image_path),
        "--output-dir",
        str(temp_output),
        "--pretrained-model",
        pretrained_model,
        "--texture-resolution",
        texture_resolution,
        "--remesh_option",
        remesh_option,
        "--target_vertex_count",
        target_vertex_count,
        "--device",
        device,
    ]

    log(f"Launching Stable Fast 3D from {repo_path}.")
    completed = subprocess.run(command, cwd=repo_path, check=False, text=True, capture_output=True)
    if completed.stdout.strip():
        log(completed.stdout.strip())
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Stable Fast 3D exited with a non-zero status."
        shutil.rmtree(temp_output, ignore_errors=True)
        raise SystemExit(message)

    mesh_glb = _find_mesh_glb(temp_output)
    target_glb = job["output_dir"] / "model.glb"
    shutil.copy2(mesh_glb, target_glb)

    target_obj = job["output_dir"] / "model.obj"
    obj_note = optional_export_obj(target_glb, target_obj)
    if obj_note:
        log(obj_note)

    manifest = {
        "job_id": job["job_id"],
        "backend": "sf3d",
        "generator": "Stable Fast 3D",
        "mode": "subprocess",
        "generated_at": utc_now(),
        "input_roles": [item.get("role") for item in job["input_files"]],
        "source_image": image_path.name,
        "pretrained_model": pretrained_model,
        "device": device,
        "files": [
            {"role": "preview_glb", "filename": "model.glb"},
            {"role": "mesh_obj", "filename": "model.obj", "optional": True},
        ],
        "notes": [
            "This bridge shells out to the official Stable Fast 3D run.py entrypoint.",
            "Hugging Face access and backend dependencies must already be available in the selected Python environment.",
        ],
    }
    write_manifest(job["output_dir"], manifest)
    shutil.rmtree(temp_output, ignore_errors=True)
    log(f"Stable Fast 3D outputs are ready in {job['output_dir']}.")


if __name__ == "__main__":
    main()
