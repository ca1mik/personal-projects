# Ike Editorial Pipeline MVP

Human-in-the-loop web MVP for semi-automated YouTube script creation on macroeconomics and economics topics.

This is a pipeline editor, not a chat UI:

- 10 sequential AI steps
- upstream Topic Radar for macro news aggregation
- versioned artifacts per step
- manual editing between steps
- approval gates on critical steps
- per-step regeneration
- artifact history and diff
- file uploads for briefs, transcripts, and supporting materials
- lightweight competitor momentum signal panel

## Stack

- Next.js 16
- TypeScript
- App Router
- Tailwind CSS v4
- File-backed JSON storage for zero-config local MVP
- OpenAI SDK integration with demo fallback when `OPENAI_API_KEY` is missing or the configured gateway rejects the request

## Run locally

```bash
npm install
npm run db:seed
npm run dev
```

Open `http://localhost:3000`.

Optional AI env vars:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://your-openai-compatible-gateway.example/v1
```

## Demo data

Seeding writes the local store to `storage/store.json` and includes:

- 2 projects
- 12 artifacts
- 12 step runs
- uploaded briefs, transcripts, and metrics
- stored sources for the evidence workflow

Reset the demo store at any time:

```bash
npm run db:reset
```

## Main areas

- `app/projects/page.tsx`: projects list and creation flow
- `app/projects/[projectId]/page.tsx`: pipeline workspace
- `app/projects/[projectId]/artifacts/[stepName]/page.tsx`: artifact detail and diff
- `app/radar/page.tsx`: aggregated topic discovery and competitor signal view
- `app/actions.ts`: server actions for generation, approvals, uploads, and versioning
- `lib/steps/registry.ts`: declarative step registry, prompt metadata, schemas, and QC rules
- `lib/ai/orchestrator.ts`: step execution, validation, and artifact persistence
- `lib/server/topic-radar.ts`: curated feed parsing, signal normalization, and topic candidate scoring
- `lib/data/repository.ts`: storage-facing repository helpers
- `lib/server/store.ts`: local JSON store

## Verification

```bash
npm run smoke
npm run qa
npm run lint
npm run build
```
