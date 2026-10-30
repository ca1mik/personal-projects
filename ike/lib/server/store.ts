import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { nanoid } from "nanoid";
import { createSourceRef } from "@/lib/citations";
import type { AppStore, ArtifactProvenanceMode } from "@/lib/domain/pipeline";
import { createSeedStore } from "@/lib/server/seed-data";

const storageDir = path.join(process.cwd(), "storage");
const storagePath = path.join(storageDir, "store.json");

async function ensureStorageFile() {
  await mkdir(storageDir, { recursive: true });

  try {
    await readFile(storagePath, "utf8");
  } catch {
    const seeded = createSeedStore();
    await writeFile(storagePath, JSON.stringify(seeded, null, 2), "utf8");
  }
}

export async function readStore() {
  await ensureStorageFile();
  const raw = await readFile(storagePath, "utf8");
  const parsed = JSON.parse(raw) as Partial<AppStore>;
  const seed = createSeedStore();

  return {
    ...seed,
    ...parsed,
    users: parsed.users ?? seed.users,
    activeUserId: parsed.activeUserId ?? seed.activeUserId,
    projects: parsed.projects ?? seed.projects,
    stepRuns: (parsed.stepRuns ?? seed.stepRuns).map((run) => ({
      ...run,
      executionMode: "executionMode" in run ? run.executionMode : "live_model",
      tokenEstimate: "tokenEstimate" in run ? run.tokenEstimate : null,
      costEstimateUsd: "costEstimateUsd" in run ? run.costEstimateUsd : null,
    })),
    artifacts: (parsed.artifacts ?? seed.artifacts).map((artifact) => {
      const legacyArtifact = artifact as AppStore["artifacts"][number] & {
        provenance?: AppStore["artifacts"][number]["provenance"];
        inputArtifactIds?: string[];
      };

      return {
        ...legacyArtifact,
        inputArtifactIds: legacyArtifact.inputArtifactIds ?? [],
        provenance:
          legacyArtifact.provenance ??
          {
            mode: (legacyArtifact.origin === "human_edited" ? "human_edit" : "live_model") as ArtifactProvenanceMode,
            modelName: legacyArtifact.origin === "human_edited" ? "manual_edit" : "seeded-import",
            note: null,
          },
      };
    }),
    sources: (parsed.sources ?? seed.sources).map((source) => ({
      ...source,
      sourceRef: "sourceRef" in source && typeof source.sourceRef === "string" ? source.sourceRef : createSourceRef(source.title),
      supportedClaims:
        "supportedClaims" in source && Array.isArray(source.supportedClaims)
          ? source.supportedClaims.filter((item): item is string => typeof item === "string")
          : [],
    })),
    uploads: parsed.uploads ?? seed.uploads,
    radarSources: parsed.radarSources ?? seed.radarSources,
    newsSignals: parsed.newsSignals ?? seed.newsSignals,
    topicCandidates: parsed.topicCandidates ?? seed.topicCandidates,
    competitorSignals: parsed.competitorSignals ?? seed.competitorSignals,
    auditEvents: parsed.auditEvents ?? seed.auditEvents,
  };
}

export async function writeStore(store: AppStore) {
  await ensureStorageFile();
  const tempPath = `${storagePath}.tmp`;
  await writeFile(tempPath, JSON.stringify(store, null, 2), "utf8");
  await rename(tempPath, storagePath);
}

export async function mutateStore<T>(mutator: (store: AppStore) => T | Promise<T>) {
  const store = await readStore();
  const result = await mutator(store);
  await writeStore(store);
  return result;
}

export async function resetStore() {
  const seeded = createSeedStore();
  await writeStore(seeded);
  return seeded;
}

export function createId(prefix: string) {
  return `${prefix}_${nanoid(10)}`;
}

export function nowIso() {
  return new Date().toISOString();
}
