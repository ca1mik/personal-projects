from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from bridge_utils import (
    input_path,
    input_paths_by_prefix,
    load_job_context,
    log,
    optional_export_obj,
    project_root,
    utc_now,
    write_manifest,
)


def _load_image(path: Path):
    from PIL import Image

    return Image.open(path).convert("RGBA")


def _reframe_subject(image, *, canvas_size: int, fill_ratio: float, bottom_margin_ratio: float):
    from PIL import Image

    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
    if bbox is None:
        return image

    subject = image.crop(bbox)
    subject_width, subject_height = subject.size
    if subject_width <= 0 or subject_height <= 0:
        return image

    target_side = max(1, int(round(canvas_size * fill_ratio)))
    scale = min(target_side / max(subject_width, subject_height), 4.0)
    resized = subject.resize(
        (
            max(1, int(round(subject_width * scale))),
            max(1, int(round(subject_height * scale))),
        ),
        Image.Resampling.LANCZOS,
    )

    frame = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    paste_x = max(0, (canvas_size - resized.size[0]) // 2)
    bottom_margin = max(0, int(round(canvas_size * bottom_margin_ratio)))
    paste_y = canvas_size - bottom_margin - resized.size[1]
    paste_y = max(0, min(canvas_size - resized.size[1], paste_y))
    frame.paste(resized, (paste_x, paste_y), resized)
    return frame


def _prepare_view(image, *, canvas_size: int, fill_ratio: float, bottom_margin_ratio: float):
    return _reframe_subject(
        image,
        canvas_size=canvas_size,
        fill_ratio=fill_ratio,
        bottom_margin_ratio=bottom_margin_ratio,
    )


def _prepare_texture_reference(image, *, remove_background: bool, canvas_size: int, fill_ratio: float, bottom_margin_ratio: float):
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    return _prepare_view(
        image,
        canvas_size=canvas_size,
        fill_ratio=fill_ratio,
        bottom_margin_ratio=bottom_margin_ratio,
    )


def _apply_projection_vertex_colors(mesh, view_images: dict[str, object]) -> tuple[object, int]:
    import numpy as np
    import trimesh

    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError("Projection texture fallback requires a trimesh mesh.")

    if len(mesh.vertices) == 0:
        raise RuntimeError("Projection texture fallback requires a non-empty mesh.")

    bounds = mesh.bounds.astype(np.float32)
    mins = bounds[0]
    maxs = bounds[1]
    spans = np.maximum(maxs - mins, 1e-6)
    vertices = mesh.vertices.astype(np.float32)
    normals = mesh.vertex_normals.astype(np.float32)

    xn = (vertices[:, 0] - mins[0]) / spans[0]
    yn = (vertices[:, 1] - mins[1]) / spans[1]
    zn = (vertices[:, 2] - mins[2]) / spans[2]
    v_coord = 1.0 - yn

    color_accum = np.zeros((len(vertices), 3), dtype=np.float32)
    weight_accum = np.zeros((len(vertices), 1), dtype=np.float32)
    used_views = 0

    view_specs = {
        "front": (xn, v_coord, np.clip(normals[:, 2], 0.0, None)),
        "back": (1.0 - xn, v_coord, np.clip(-normals[:, 2], 0.0, None)),
        "left": (1.0 - zn, v_coord, np.clip(-normals[:, 0], 0.0, None)),
        "right": (zn, v_coord, np.clip(normals[:, 0], 0.0, None)),
    }

    for role, image in view_images.items():
        spec = view_specs.get(role)
        if spec is None:
            continue

        u, v, weights = spec
        rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
        height, width = rgba.shape[:2]
        px = np.clip(np.round(u * (width - 1)).astype(np.int32), 0, width - 1)
        py = np.clip(np.round(v * (height - 1)).astype(np.int32), 0, height - 1)
        samples = rgba[py, px]
        alpha = samples[:, 3:4]
        effective_weight = weights[:, None] * alpha
        color_accum += samples[:, :3] * effective_weight
        weight_accum += effective_weight
        used_views += 1

    if used_views == 0:
        raise RuntimeError("Projection texture fallback requires at least one canonical view image.")

    neutral = np.array([[0.84, 0.84, 0.86]], dtype=np.float32)
    rgb = np.divide(
        color_accum,
        np.maximum(weight_accum, 1e-6),
        out=np.zeros_like(color_accum),
        where=weight_accum > 0,
    )
    seeded = weight_accum[:, 0] > 1e-6
    rgb = np.where(weight_accum > 0, rgb, neutral)

    if not seeded.all():
        edges = mesh.edges_unique
        valid = seeded.copy()

        for _ in range(96):
            if valid.all():
                break

            neighbor_color_sum = np.zeros_like(rgb)
            neighbor_valid_count = np.zeros((len(vertices), 1), dtype=np.float32)
            left = edges[:, 0]
            right = edges[:, 1]
            right_valid = valid[right]
            left_valid = valid[left]

            if right_valid.any():
                np.add.at(neighbor_color_sum, left[right_valid], rgb[right[right_valid]])
                np.add.at(neighbor_valid_count, left[right_valid], 1.0)
            if left_valid.any():
                np.add.at(neighbor_color_sum, right[left_valid], rgb[left[left_valid]])
                np.add.at(neighbor_valid_count, right[left_valid], 1.0)

            new_valid = (~valid) & (neighbor_valid_count[:, 0] > 0)
            if not new_valid.any():
                break

            rgb[new_valid] = neighbor_color_sum[new_valid] / np.maximum(neighbor_valid_count[new_valid], 1e-6)
            valid[new_valid] = True

        remaining = ~valid
        if remaining.any():
            seeded_mean = rgb[seeded].mean(axis=0) if seeded.any() else neutral[0]
            rgb[remaining] = seeded_mean

        for _ in range(6):
            neighbor_color_sum = np.zeros_like(rgb)
            neighbor_count = np.zeros((len(vertices), 1), dtype=np.float32)
            left = edges[:, 0]
            right = edges[:, 1]
            np.add.at(neighbor_color_sum, left, rgb[right])
            np.add.at(neighbor_color_sum, right, rgb[left])
            np.add.at(neighbor_count, left, 1.0)
            np.add.at(neighbor_count, right, 1.0)
            neighbor_avg = neighbor_color_sum / np.maximum(neighbor_count, 1.0)

            rgb[seeded] = rgb[seeded] * 0.82 + neighbor_avg[seeded] * 0.18
            rgb[~seeded] = rgb[~seeded] * 0.58 + neighbor_avg[~seeded] * 0.42

    vertex_colors = np.concatenate(
        [(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8), np.full((len(vertices), 1), 255, dtype=np.uint8)],
        axis=1,
    )

    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=vertex_colors)
    return mesh, used_views


def _maybe_smooth_mesh(mesh, *, iterations: int) -> object:
    if iterations <= 0:
        return mesh

    try:
        import trimesh
    except Exception as exc:
        log(f"Skipping Taubin smoothing because trimesh is unavailable: {exc}")
        return mesh

    if not isinstance(mesh, trimesh.Trimesh):
        return mesh

    try:
        trimesh.smoothing.filter_taubin(mesh, lamb=0.45, nu=-0.5, iterations=iterations)
        log(f"Applied Taubin smoothing with {iterations} iterations.")
    except Exception as exc:
        log(f"Skipping Taubin smoothing because the mesh post-process failed: {exc}")
    return mesh


def _run_blender_autorig(source_glb: Path, *, output_dir: Path, rig_name: str) -> tuple[list[dict[str, str]], str]:
    blender_bin = Path(
        os.getenv(
            "BLENDER_BIN",
            r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        )
    ).expanduser()
    rig_script = Path(
        os.getenv("HUNYUAN_MV_RIG_SCRIPT", project_root() / "scripts" / "blender_autorig.py")
    ).expanduser()

    if not blender_bin.exists():
        raise RuntimeError(f"Blender binary was not found at {blender_bin}.")
    if not rig_script.exists():
        raise RuntimeError(f"Rig script was not found at {rig_script}.")

    output_glb = output_dir / "rigged.glb"
    output_fbx = output_dir / "rigged.fbx"
    command = [
        str(blender_bin),
        "--background",
        "--factory-startup",
        "--python",
        str(rig_script),
        "--",
        "--input",
        str(source_glb),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--rig-name",
        rig_name,
    ]

    completed = subprocess.run(
        command,
        cwd=project_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
    if completed.returncode != 0:
        raise RuntimeError(combined_output or "Blender autorig returned a non-zero exit code.")

    produced_files: list[dict[str, str]] = []
    if output_glb.exists():
        produced_files.append({"role": "rigged_glb", "filename": output_glb.name})
    if output_fbx.exists():
        produced_files.append({"role": "rigged_fbx", "filename": output_fbx.name})

    if not produced_files:
        raise RuntimeError("Blender autorig completed without producing rigged output files.")

    return produced_files, combined_output


def main() -> None:
    job = load_job_context()

    repo_path = Path(os.getenv("HUNYUAN_MV_REPO_PATH", project_root() / "third_party" / "Hunyuan3D-2-official")).resolve()
    if not (repo_path / "gradio_app.py").exists():
        raise SystemExit(
            f"Hunyuan3D-2 repo was not found at {repo_path}. "
            "Clone the official repo and set HUNYUAN_MV_REPO_PATH."
        )

    if str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))

    try:
        import torch
        from hy3dgen.rembg import BackgroundRemover
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
    except Exception as exc:
        raise SystemExit(
            "Hunyuan3D-2 dependencies are not installed in the Python environment used by this bridge. "
            "Install the official repo requirements and rerun."
        ) from exc

    model_path = os.getenv("HUNYUAN_MV_MODEL_PATH", "tencent/Hunyuan3D-2mv")
    shape_subfolder = os.getenv("HUNYUAN_MV_SHAPE_SUBFOLDER", "hunyuan3d-dit-v2-mv-turbo")
    tex_model_path = os.getenv("HUNYUAN_TEX_MODEL_PATH", "tencent/Hunyuan3D-2")
    tex_subfolder = os.getenv("HUNYUAN_TEX_SUBFOLDER", "hunyuan3d-paint-v2-0-turbo")
    device = os.getenv("HUNYUAN_MV_DEVICE", "cuda")
    remove_background = os.getenv("HUNYUAN_MV_REMOVE_BACKGROUND", "1") == "1"
    enable_texture = os.getenv("HUNYUAN_MV_ENABLE_TEXTURE", "0") == "1"
    enable_flashvdm = os.getenv("HUNYUAN_MV_ENABLE_FLASHVDM", "1") == "1"
    low_vram_mode = os.getenv("HUNYUAN_MV_LOW_VRAM_MODE", "1") == "1"
    steps = int(os.getenv("HUNYUAN_MV_NUM_STEPS", "50"))
    guidance_scale = float(os.getenv("HUNYUAN_MV_GUIDANCE_SCALE", "5.0"))
    octree_resolution = int(os.getenv("HUNYUAN_MV_OCTREE_RESOLUTION", "380"))
    num_chunks = int(os.getenv("HUNYUAN_MV_NUM_CHUNKS", "20000"))
    seed = int(os.getenv("HUNYUAN_MV_SEED", "12345"))
    canvas_size = int(os.getenv("HUNYUAN_MV_CANVAS_SIZE", "1024"))
    subject_fill = float(os.getenv("HUNYUAN_MV_SUBJECT_FILL", "0.78"))
    bottom_margin_ratio = float(os.getenv("HUNYUAN_MV_BOTTOM_MARGIN_RATIO", "0.05"))
    smooth_iterations = int(os.getenv("HUNYUAN_MV_TAUBIN_SMOOTHING_ITERATIONS", "12"))
    texture_extra_body_limit = int(os.getenv("HUNYUAN_MV_TEXTURE_MAX_BODY_REFS", "8"))
    texture_include_face_refs = os.getenv("HUNYUAN_MV_TEXTURE_INCLUDE_FACE_REFS", "0") == "1"
    texture_face_ref_limit = int(os.getenv("HUNYUAN_MV_TEXTURE_MAX_FACE_REFS", "0"))
    texture_strategy = os.getenv("HUNYUAN_MV_TEXTURE_STRATEGY", "auto").strip().lower()
    enable_rig = os.getenv("HUNYUAN_MV_ENABLE_RIG", "0") == "1"
    rig_strict = os.getenv("HUNYUAN_MV_RIG_STRICT", "0") == "1"

    view_images: dict[str, object] = {}
    for role in ("front", "left", "back", "right"):
        image_path = input_path(job, role)
        if image_path is None:
            continue
        view_images[role] = _load_image(image_path)

    if not {"front", "left", "back"}.issubset(view_images):
        raise SystemExit("Hunyuan multiview bridge requires front, left, and back canonical views.")

    if remove_background:
        remover = BackgroundRemover()
        view_images = {role: remover(image.convert("RGB")) for role, image in view_images.items()}
    else:
        view_images = {
            role: image if image.mode == "RGBA" else image.convert("RGBA")
            for role, image in view_images.items()
        }

    view_images = {
        role: _prepare_view(
            image,
            canvas_size=canvas_size,
            fill_ratio=subject_fill,
            bottom_margin_ratio=bottom_margin_ratio,
        )
        for role, image in view_images.items()
    }

    log(f"Loading Hunyuan multiview shape model from {model_path}/{shape_subfolder}.")
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        model_path,
        subfolder=shape_subfolder,
        variant="fp16",
        use_safetensors=True,
        device=device,
    )
    if enable_flashvdm:
        pipeline.enable_flashvdm()

    generator = torch.manual_seed(seed)
    mesh = pipeline(
        image=view_images,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        octree_resolution=octree_resolution,
        num_chunks=num_chunks,
        generator=generator,
        output_type="trimesh",
    )[0]
    mesh = _maybe_smooth_mesh(mesh, iterations=smooth_iterations)

    output_glb = job["output_dir"] / "model.glb"
    output_obj = job["output_dir"] / "model.obj"
    body_extras = input_paths_by_prefix(job, "body-extra-")
    face_refs = input_paths_by_prefix(job, "face-reference-")

    textured = False
    texture_prompt_count = 0
    texture_method = "disabled"
    if enable_texture:
        ordered_images = [view_images[role] for role in ("front", "left", "back", "right") if role in view_images]
        for path in body_extras[:texture_extra_body_limit]:
            ordered_images.append(
                _prepare_texture_reference(
                    _load_image(path),
                    remove_background=remove_background,
                    canvas_size=canvas_size,
                    fill_ratio=subject_fill,
                    bottom_margin_ratio=bottom_margin_ratio,
                )
            )

        if texture_include_face_refs:
            for path in face_refs[:texture_face_ref_limit]:
                ordered_images.append(
                    _prepare_texture_reference(
                        _load_image(path),
                        remove_background=remove_background,
                        canvas_size=canvas_size,
                        fill_ratio=0.86,
                        bottom_margin_ratio=0.08,
                    )
                )

        texture_prompt_count = len(ordered_images)
        log(f"Using {texture_prompt_count} texture reference images.")

        official_texture_error = None
        if texture_strategy in {"auto", "official"}:
            try:
                from hy3dgen.texgen import Hunyuan3DPaintPipeline

                log(f"Loading Hunyuan texture model from {tex_model_path}/{tex_subfolder}.")
                tex_pipeline = Hunyuan3DPaintPipeline.from_pretrained(tex_model_path, subfolder=tex_subfolder)
                if low_vram_mode and hasattr(tex_pipeline, "enable_model_cpu_offload"):
                    tex_pipeline.enable_model_cpu_offload()
                mesh = tex_pipeline(mesh, image=ordered_images)
                textured = True
                texture_method = "official_hunyuan_paint"
            except Exception as exc:
                official_texture_error = str(exc)
                if texture_strategy == "official":
                    raise
                log(f"Official texture stage failed, falling back to projection vertex colors: {exc}")

        if not textured and texture_strategy in {"auto", "projection", "projection_only"}:
            projection_views = {role: view_images[role] for role in ("front", "left", "back", "right") if role in view_images}
            mesh, projection_view_count = _apply_projection_vertex_colors(mesh, projection_views)
            textured = True
            texture_method = f"vertex_color_projection_{projection_view_count}views"
            if official_texture_error:
                log("Projection vertex-color fallback succeeded after official texture-stage failure.")

    mesh.export(output_glb)
    obj_note = optional_export_obj(output_glb, output_obj)
    if obj_note:
        log(obj_note)

    rigged_files: list[dict[str, str]] = []
    rigging_note = "Rigging disabled."
    if enable_rig:
        try:
            rigged_files, rig_output = _run_blender_autorig(
                output_glb,
                output_dir=job["output_dir"],
                rig_name=f"EnyaRig_{job['job_id'][:8]}",
            )
            rigging_note = "Blender autorig export completed."
            if rig_output:
                log(rig_output)
        except Exception as exc:
            rigging_note = f"Rigging skipped because Blender autorig failed: {exc}"
            log(rigging_note)
            if rig_strict:
                raise

    manifest = {
        "job_id": job["job_id"],
        "backend": "hunyuan_mv",
        "generator": "Hunyuan3D-2mv",
        "mode": "subprocess",
        "generated_at": utc_now(),
        "shape_model": {"path": model_path, "subfolder": shape_subfolder},
        "texture_model": {
            "path": tex_model_path,
            "subfolder": tex_subfolder,
            "enabled": textured,
            "strategy": texture_strategy,
            "method": texture_method,
        },
        "rigging": {
            "enabled": bool(rigged_files),
            "requested": enable_rig,
            "strict": rig_strict,
            "method": "blender_autorig",
            "note": rigging_note,
        },
        "canonical_views_used": list(view_images.keys()),
        "parameters": {
            "steps": steps,
            "guidance_scale": guidance_scale,
            "octree_resolution": octree_resolution,
            "num_chunks": num_chunks,
            "seed": seed,
            "canvas_size": canvas_size,
            "subject_fill": subject_fill,
            "bottom_margin_ratio": bottom_margin_ratio,
            "taubin_smoothing_iterations": smooth_iterations,
            "texture_reference_count": texture_prompt_count,
            "texture_extra_body_limit": texture_extra_body_limit,
            "texture_include_face_refs": texture_include_face_refs,
            "texture_face_ref_limit": texture_face_ref_limit,
            "texture_strategy": texture_strategy,
        },
        "stored_reference_counts": {
            "extra_body": len(body_extras),
            "face": len(face_refs),
        },
        "files": [
            {"role": "preview_glb", "filename": "model.glb"},
            {"role": "mesh_obj", "filename": "model.obj", "optional": True},
            *rigged_files,
        ],
        "notes": [
            "This bridge follows the official Hunyuan3D-2 multiview examples and uses the canonical body views for shape generation.",
            "Canonical body views are background-removed and reframed onto a square canvas before shape generation for more stable human-body alignment.",
            "Extra body references can also be passed into the texture stage for richer color placement.",
            "Face references stay attached to the job for future refinement stages and are opt-in for texturing because close-up crops can distort body-wide color transfer.",
            rigging_note,
        ],
    }
    write_manifest(job["output_dir"], manifest)
    log(f"Hunyuan multiview outputs are ready in {job['output_dir']}.")


if __name__ == "__main__":
    main()
