# Hunyuan3D-2mv Adapter

This adapter powers the multi-view job flow.

Supported modes:

- `stub`: default, generates deterministic local placeholder GLB/OBJ output.
- `http`: calls a local HTTP backend and expects it to write outputs into the provided `output_dir`.
- `subprocess`: runs a local CLI/script and expects it to write outputs into the provided `output_dir`.

Environment variables:

- `HUNYUAN_MV_MODE=stub|http|subprocess`
- `HUNYUAN_MV_HTTP_URL=http://localhost:9002/generate`
- `HUNYUAN_MV_HTTP_TIMEOUT_SECONDS=600`
- `HUNYUAN_MV_SUBPROCESS_COMMAND_JSON=["python","scripts/run_hunyuan_mv_bridge.py"]`
- `HUNYUAN_MV_REPO_PATH=third_party/Hunyuan3D-2-official`
- `HUNYUAN_MV_MODEL_PATH=tencent/Hunyuan3D-2mv`
- `HUNYUAN_MV_SHAPE_SUBFOLDER=hunyuan3d-dit-v2-mv-turbo`
- `HUNYUAN_MV_ENABLE_TEXTURE=0|1`
- `HUNYUAN_TEX_MODEL_PATH=tencent/Hunyuan3D-2`
- `HUNYUAN_TEX_SUBFOLDER=hunyuan3d-paint-v2-0-turbo`

Expected integration contract:

1. Read front/left/back/right views from `ENYA_INPUT_DIR` or the HTTP payload.
2. Write outputs into `ENYA_OUTPUT_DIR` or the HTTP payload `output_dir`.
3. Emit at least one of:
   - `model.glb`
   - `model.obj`
   - `manifest.json`

Included bridge:

- `scripts/run_hunyuan_mv_bridge.py`

That bridge follows the official Hunyuan multiview examples and currently:

- uses canonical body views for shape generation
- can include the optional right view
- can enable texture generation when the official texture stack is available
- preserves extra body and face references in job metadata for later refinement

Official references:

- https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- https://huggingface.co/tencent/Hunyuan3D-2mv
- https://huggingface.co/tencent/Hunyuan3D-2
