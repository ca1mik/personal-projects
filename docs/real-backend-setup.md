# Real Backend Setup

This project is ready to run in two layers:

1. Stub mode right now for end-to-end product testing.
2. Real backend mode once the official model environments are installed.

## Immediate local testing

Keep these defaults:

- `QUEUE_MODE=inline` if you want the simplest local startup without Redis
- `SF3D_MODE=stub`
- `HUNYUAN_MV_MODE=stub`

Then start the stack:

```powershell
.\.venv\Scripts\python.exe scripts\runtime_doctor.py
.\scripts\start_local_stack.ps1
```

## Real single-image generation with Stable Fast 3D

Official sources:

- https://github.com/Stability-AI/stable-fast-3d
- https://huggingface.co/stabilityai/stable-fast-3d

What the bridge expects:

1. Official `stable-fast-3d` repo available under `third_party/stable-fast-3d` or `SF3D_REPO_PATH`.
2. A Python environment that can run the official `run.py`.
3. Hugging Face access for `stabilityai/stable-fast-3d`, or a local downloaded model path.

Switch these env values:

```env
SF3D_MODE=subprocess
SF3D_SUBPROCESS_COMMAND_JSON=["python","scripts/run_sf3d_bridge.py"]
```

If the backend lives in its own Python environment, point the command to that interpreter instead:

```env
SF3D_SUBPROCESS_COMMAND_JSON=["F:/backends/sf3d/.venv/Scripts/python.exe","scripts/run_sf3d_bridge.py"]
```

## Real multi-view generation with Hunyuan3D-2mv

Official sources:

- https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- https://huggingface.co/tencent/Hunyuan3D-2mv
- https://huggingface.co/tencent/Hunyuan3D-2

What the bridge expects:

1. Official `Hunyuan3D-2` repo available under `third_party/Hunyuan3D-2-official` or `HUNYUAN_MV_REPO_PATH`.
2. A Python environment with the official Hunyuan requirements installed.
3. Access to the multiview shape model and optional texture model.

Recommended env values:

```env
HUNYUAN_MV_MODE=subprocess
HUNYUAN_MV_SUBPROCESS_COMMAND_JSON=["python","scripts/run_hunyuan_mv_bridge.py"]
HUNYUAN_MV_MODEL_PATH=tencent/Hunyuan3D-2mv
HUNYUAN_MV_SHAPE_SUBFOLDER=hunyuan3d-dit-v2-mv-turbo
HUNYUAN_MV_ENABLE_TEXTURE=0
```

When the texture stack is stable on your machine, turn it on:

```env
HUNYUAN_MV_ENABLE_TEXTURE=1
HUNYUAN_TEX_MODEL_PATH=tencent/Hunyuan3D-2
HUNYUAN_TEX_SUBFOLDER=hunyuan3d-paint-v2-0-turbo
```

## Capture guidance for the doll workflow

- Use `front`, `left`, `back`, and optional `right` as the canonical body set.
- Upload the rest of the 8 body photos under `Body reference set`.
- Upload the 8 face photos under `Face reference set`.
- Current real multiview generation uses the canonical body views for shape generation.
- Extra body and face references are preserved with the job for later texture or likeness refinement.

## Viewer

The job detail page already includes:

- drag orbit
- zoom
- preset angles
- turntable on/off
- GLB download
- OBJ download when available
