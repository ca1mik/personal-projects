import { generateStepArtifact } from "../lib/ai/orchestrator";
import { createProject, getProjectWorkspace, getTopicRadarSnapshot, updateArtifactState } from "../lib/data/repository";
import { refreshTopicRadar } from "../lib/server/topic-radar";
import { resetStore } from "../lib/server/store";

async function checkHttp(baseUrl: string) {
  const routes = ["/projects", "/radar", "/projects/project_fed", "/projects/project_fed/artifacts/topic_assessment"];
  const results: Array<{ route: string; status: number }> = [];

  for (const route of routes) {
    const response = await fetch(`${baseUrl}${route}`);
    results.push({ route, status: response.status });
  }

  return results;
}

async function main() {
  await resetStore();

  const seedRadar = await getTopicRadarSnapshot();
  const project = await createProject({
    title: "Smoke Test Project",
    authorName: "QA User",
    channelName: "Macro Dispatch",
    topic: "Could hidden credit stress arrive before rate cuts?",
    deadline: null,
  });

  const diagnosis = await generateStepArtifact(project.id, "channel_diagnosis");
  const refreshed = await refreshTopicRadar();

  const workspace = await getProjectWorkspace(project.id);
  const seedProject = await getProjectWorkspace("project_fed");
  const topicArtifact = seedProject?.steps.find((step) => step.id === "topic_assessment")?.latestArtifact ?? null;
  if (topicArtifact) {
    await updateArtifactState({
      artifactId: topicArtifact.id,
      status: "approved",
      approvedByHuman: true,
      approvedByUserId: "user_ira",
    });
  }

  const result: Record<string, unknown> = {
    diagnosisGenerated: diagnosis.stepName === "channel_diagnosis",
    diagnosisStatus: diagnosis.status,
    projectArtifactCount: workspace?.artifacts.length ?? 0,
    seedRadarCandidates: seedRadar.candidates.length,
    refreshedSignals: refreshed.signals.length,
    refreshedCandidates: refreshed.candidates.length,
    topRadarDecision: refreshed.candidates[0]?.decision ?? null,
  };

  if (process.env.BASE_URL) {
    result.http = await checkHttp(process.env.BASE_URL);
  }

  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
