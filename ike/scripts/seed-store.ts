import { resetStore } from "../lib/server/store";

async function main() {
  const store = await resetStore();
  console.log("Seeded store:", {
    projects: store.projects.length,
    artifacts: store.artifacts.length,
    stepRuns: store.stepRuns.length,
    uploads: store.uploads.length,
    sources: store.sources.length,
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
