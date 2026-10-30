# Enya Local 3D Studio MVP

Local-first image-to-3D generation web service built as a monorepo with Next.js, FastAPI, Redis/RQ, local filesystem storage, and clean adapter boundaries for real open-source backend integration.

## What works now

- Next.js 14 web UI with:
  - single-image and multi-view upload flows
  - canonical body views plus extra body and face reference sets
  - drag-and-drop file inputs
  - local job history
  - job detail view
  - browser GLB preview via `model-viewer`
  - preset front/left/back/right/top controls
  - turntable on/off for all-side inspection
  - download buttons for generated files
- FastAPI backend with:
  - stable JSON envelope responses
  - upload validation and filename sanitization
  - safe asset serving under known job ids
  - local job metadata JSON storage
  - rerun and soft-delete endpoints
  - `GET /healthz`
- Redis + RQ queueing
- Worker adapters for:
  - `sf3d` single-image jobs
  - `hunyuan_mv` multi-view jobs
- Stub mode end-to-end output generation:
  - deterministic placeholder `model.glb`
  - placeholder `model.obj`
  - `manifest.json`
- Real backend bridge scripts for:
  - official Stable Fast 3D repo
  - official Hunyuan3D-2 multiview repo
- Official Hunyuan repo source cloned locally under `third_party/Hunyuan3D-2-official`
- Optional `QUEUE_MODE=inline` fallback for fully local startup when Redis/Docker is unavailable

## What is still honest about the project

- Stub mode works immediately.
- Real model generation only works after the official backend repos, weights, and Python environments are installed.
- A lone checkpoint file like `F:/models/hunyuan/model.fp16.ckpt` is not enough by itself to run official Hunyuan multiview inference.

## Repo structure

```text
.
|- apps
|  |- api
|  |  |- Dockerfile
|  |  `- app
|  `- web
|- workers
|  |- hunyuan_mv
|  |- sf3d
|  `- common
|- packages
|  `- shared
|- storage
|  |- assets
|  |- inputs
|  |- jobs
|  `- outputs
|- scripts
|- docs
|- docker-compose.yml
|- .env.example
`- README.md
```

## Job schema

Every job is stored as JSON under `storage/jobs/<job_id>.json` with these core fields:

- `id`
- `type`
- `status`
- `backend`
- `created_at`
- `updated_at`
- `input_files`
- `output_files`
- `error`
- `logs`
- `params`

## API surface

- `POST /api/jobs/single-image`
- `POST /api/jobs/multi-view`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/files`
- `GET /api/assets/{job_id}/{filename}`
- `POST /api/jobs/{job_id}/rerun`
- `DELETE /api/jobs/{job_id}`
- `GET /healthz`

Success responses:

```json
{
  "ok": true,
  "data": {}
}
```

Error responses:

```json
{
  "ok": false,
  "error": {
    "code": "SOME_CODE",
    "message": "Human readable message"
  }
}
```

## Quick start

### 1. Create env files

```powershell
Copy-Item .env.example .env
Copy-Item apps/web/.env.local.example apps/web/.env.local
```

### 2. Install dependencies

Python:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

JavaScript:

```powershell
corepack pnpm install
```

### 3. Check readiness

```powershell
.\.venv\Scripts\python.exe scripts\runtime_doctor.py
```

### 4. Start locally

Fastest path on Windows:

```powershell
.\scripts\start_local_stack.ps1
```

Manual path with normal Redis/RQ queue:

```powershell
docker compose up redis -d
python scripts/dev_api.py
python scripts/run_worker.py
corepack pnpm --dir apps/web dev
```

Manual path with inline fallback:

```powershell
python scripts/dev_api.py
corepack pnpm --dir apps/web dev
```

Open:

- Web UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/healthz`

## Docker Compose

For a containerized local run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

This starts:

- `redis`
- `api`
- `worker`
- `web`

## Stub mode

By default:

- `SF3D_MODE=stub`
- `HUNYUAN_MV_MODE=stub`

So the whole pipeline works immediately without downloading model weights.

If Docker or Redis is currently broken on your machine, set:

```env
QUEUE_MODE=inline
```

That keeps the app local-first and processes jobs in the API process without Redis or a separate worker.

## Real backend hooks

### Stable Fast 3D

Default bridge command:

```env
SF3D_SUBPROCESS_COMMAND_JSON=["python","scripts/run_sf3d_bridge.py"]
```

Relevant env vars:

- `SF3D_REPO_PATH`
- `SF3D_PYTHON_BIN`
- `SF3D_PRETRAINED_MODEL`
- `SF3D_DEVICE`
- `SF3D_TEXTURE_RESOLUTION`
- `SF3D_REMESH_OPTION`
- `SF3D_TARGET_VERTEX_COUNT`

The bridge shells out to the official `stable-fast-3d/run.py` entrypoint and normalizes the result to `model.glb`, optional `model.obj`, and `manifest.json`.

### Hunyuan3D-2mv

Default bridge command:

```env
HUNYUAN_MV_SUBPROCESS_COMMAND_JSON=["python","scripts/run_hunyuan_mv_bridge.py"]
```

Relevant env vars:

- `HUNYUAN_MV_REPO_PATH`
- `HUNYUAN_MV_MODEL_PATH`
- `HUNYUAN_MV_SHAPE_SUBFOLDER`
- `HUNYUAN_MV_DEVICE`
- `HUNYUAN_MV_REMOVE_BACKGROUND`
- `HUNYUAN_MV_ENABLE_FLASHVDM`
- `HUNYUAN_MV_ENABLE_TEXTURE`
- `HUNYUAN_MV_LOW_VRAM_MODE`
- `HUNYUAN_MV_NUM_STEPS`
- `HUNYUAN_MV_GUIDANCE_SCALE`
- `HUNYUAN_MV_OCTREE_RESOLUTION`
- `HUNYUAN_MV_NUM_CHUNKS`
- `HUNYUAN_MV_SEED`
- `HUNYUAN_TEX_MODEL_PATH`
- `HUNYUAN_TEX_SUBFOLDER`

The bridge follows the official Hunyuan multiview examples and uses canonical body views for shape generation. Extra body and face references remain attached to the job for later refinement.

## Doll workflow

For your "super realistic doll from photos" pipeline:

1. Put `front`, `left`, `back`, and optional `right` into the canonical body view slots.
2. Put the remaining full-body shots into `Body reference set`.
3. Put the 8 face shots into `Face reference set`.
4. Generate the mesh.
5. Open the job detail page and inspect with presets or turntable.
6. Download GLB or OBJ when available.

## Docs

- `docs/doll-capture-workflow.md`
- `docs/real-backend-setup.md`

## Notes

- Stored inputs, metadata, and outputs remain inspectable on disk.
- Asset routes only serve files registered to a known job id.
- Filenames are sanitized and client names are never trusted as storage paths.
- Soft delete is metadata-only so generated files remain available for inspection.
