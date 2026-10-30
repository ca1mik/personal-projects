# Architecture

## Monorepo layout

- `apps/web`: Next.js 14 App Router frontend.
- `apps/api`: FastAPI gateway API and queue entry points.
- `workers/sf3d`: single-image adapter for Stable Fast 3D style backends.
- `workers/hunyuan_mv`: multi-view adapter for Hunyuan3D-2mv style backends.
- `packages/shared`: shared TypeScript response and job types.
- `storage`: local-first runtime storage for uploads, job JSON, and outputs.

## Data flow

1. The web app uploads images to the FastAPI API.
2. The API writes sanitized files into `storage/inputs/<job_id>`.
3. The API writes a stable JSON metadata record into `storage/jobs/<job_id>.json`.
4. The API enqueues `process_job(job_id)` into Redis/RQ.
5. The worker loads the job, chooses the backend adapter, and writes outputs into `storage/outputs/<job_id>`.
6. The frontend polls job status and renders previews/downloads through safe asset routes.

## Output contract

Adapters are expected to write files into the job output directory and preferably expose:

- `model.glb`
- `model.obj`
- `manifest.json`

Stub mode already follows this contract. Real integrations should keep it unless there is a strong reason to change both the adapter and the UI together.

