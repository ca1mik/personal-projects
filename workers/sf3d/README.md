# Stable Fast 3D Adapter

This adapter powers the single-image job flow.

Supported modes:

- `stub`: default, generates deterministic local placeholder GLB/OBJ output.
- `http`: calls a local HTTP backend and expects it to write outputs into the provided `output_dir`.
- `subprocess`: runs a local CLI/script and expects it to write outputs into the provided `output_dir`.

Environment variables:

- `SF3D_MODE=stub|http|subprocess`
- `SF3D_HTTP_URL=http://localhost:9001/generate`
- `SF3D_HTTP_TIMEOUT_SECONDS=300`
- `SF3D_SUBPROCESS_COMMAND_JSON=["python","scripts/run_sf3d_bridge.py"]`
- `SF3D_REPO_PATH=third_party/stable-fast-3d`
- `SF3D_PYTHON_BIN=python`
- `SF3D_PRETRAINED_MODEL=stabilityai/stable-fast-3d`
- `SF3D_DEVICE=cuda`

Expected integration contract:

1. Read input files from `ENYA_INPUT_DIR` or the HTTP payload.
2. Write outputs into `ENYA_OUTPUT_DIR` or the HTTP payload `output_dir`.
3. Emit at least one of:
   - `model.glb`
   - `model.obj`
   - `manifest.json`

Included bridge:

- `scripts/run_sf3d_bridge.py`

That bridge shells out to the official `stable-fast-3d/run.py`, then normalizes the result into:

- `model.glb`
- optional `model.obj`
- `manifest.json`

Official references:

- https://github.com/Stability-AI/stable-fast-3d
- https://huggingface.co/stabilityai/stable-fast-3d
