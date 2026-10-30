import { WorkflowError, generateStepArtifact } from "../lib/ai/orchestrator";
import {
  canAdvance,
  createProject,
  getCurrentUser,
  getProjectWorkspace,
  getTopicRadarSnapshot,
  isArtifactStale,
  saveArtifactVersion,
  setCurrentUser,
  updateArtifactState,
} from "../lib/data/repository";
import type { UserRole } from "../lib/domain/pipeline";
import { getStepDefinition } from "../lib/steps/registry";
import { refreshTopicRadar } from "../lib/server/topic-radar";
import { resetStore } from "../lib/server/store";

function assert(condition: unknown, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

async function main() {
  await resetStore();

  const initialUser = await getCurrentUser();
  assert(initialUser?.role === "producer", "Seed should start with producer as current user.");

  const project = await createProject({
    title: "QA Project",
    authorName: "QA User",
    channelName: "Macro Dispatch",
    topic: "Could credit strain arrive before the first rate cut?",
    deadline: null,
  });

  const diagnosis = await generateStepArtifact(project.id, "channel_diagnosis");
  assert(
    diagnosis.provenance.mode === "live_model" || diagnosis.provenance.mode === "demo_fallback",
    "Channel diagnosis should complete through live model or controlled fallback.",
  );
  if (diagnosis.provenance.mode === "demo_fallback") {
    assert((diagnosis.provenance.note?.trim().length ?? 0) > 0, "Fallback note should explain why live generation was unavailable.");
  } else {
    assert(
      typeof diagnosis.provenance.modelName === "string" && diagnosis.provenance.modelName.length > 0,
      "Live generation should record the model name.",
    );
  }

  const audience = await generateStepArtifact(project.id, "audience_hypothesis");
  assert(
    audience.provenance.mode === "live_model" || audience.provenance.mode === "demo_fallback",
    "Audience generation should complete through live model or controlled fallback.",
  );

  await saveArtifactVersion({
    projectId: project.id,
    stepName: "brief_parsing",
    parentArtifactId: null,
    title: "Brief Parsing v1",
    contentJson: {
      step: "brief_parsing",
      status: "ok",
      confidence: 0.82,
      summary: "QA brief is normalized.",
      content: {
        requested_topic: "Credit strain before cuts",
        core_thesis: "The first cut may arrive because weakness is already visible in credit.",
        desired_outcome: "Viewer understands the signal behind the cut.",
        author_intent: "Measured and analytical",
        constraints: ["15-20 minutes"],
        must_include: ["Credit", "labor", "rates"],
        must_avoid: ["Alarmism"],
        ambiguities: ["How much market detail to include"],
      },
      qc_notes: [],
    },
    contentMarkdown: "# Brief Parsing\n\nQA brief artifact.",
    qcNotes: [],
    origin: "human_edited",
    humanEdited: true,
    provenance: {
      mode: "human_edit",
      modelName: "manual_edit",
      note: "QA setup",
    },
  });

  const topicAssessment = await generateStepArtifact(project.id, "topic_assessment");
  await updateArtifactState({
    artifactId: topicAssessment.id,
    status: "approved",
    approvedByHuman: true,
    approvedByUserId: initialUser?.id ?? "user_ira",
  });

  const evidencePack = await generateStepArtifact(project.id, "evidence_pack");
  assert(evidencePack.stepName === "evidence_pack", "Evidence pack should generate after topic approval.");
  const evidenceContent = evidencePack.contentJson.content as {
    sources?: Array<{ source_ref?: string; supported_claims?: string[] }>;
  };
  assert(
    Array.isArray(evidenceContent.sources) &&
      evidenceContent.sources.length > 0 &&
      evidenceContent.sources.every(
        (source) => typeof source.source_ref === "string" && Array.isArray(source.supported_claims),
      ),
    "Evidence pack should emit structured source references and supported claims.",
  );

  const evidenceSourceRefs = (evidenceContent.sources ?? [])
    .map((source) => source.source_ref)
    .filter((sourceRef): sourceRef is string => typeof sourceRef === "string");

  await saveArtifactVersion({
    projectId: project.id,
    stepName: "editorial_angle",
    parentArtifactId: null,
    title: "Editorial Angle v1",
    contentJson: {
      step: "editorial_angle",
      status: "ok",
      confidence: 0.85,
      summary: "Approved editorial angle for citation QA.",
      content: {
        core_question: "What does the first cut actually signal?",
        central_conflict: "Cheaper money can mean relief or weakness.",
        hook_options: ["The first cut can look bullish for the wrong reason."],
        viewer_promise: "Viewers learn how to read the first cut as a signal.",
        emotional_frame: "Curious skepticism",
        why_this_matters_now: "The signal matters more than the cut itself.",
        chosen_angle: "Decode the signal behind the cut.",
        rejected_angles: ["Generic rate-cut explainer"],
      },
      qc_notes: [],
    },
    contentMarkdown: "# Editorial Angle\n\nQA editorial angle.",
    qcNotes: [],
    origin: "human_edited",
    humanEdited: true,
    status: "approved",
    approvedByHuman: true,
    approvedByUserId: initialUser?.id ?? "user_ira",
    provenance: {
      mode: "human_edit",
      modelName: "manual_edit",
      note: "QA approved angle",
    },
  });

  await saveArtifactVersion({
    projectId: project.id,
    stepName: "script_outline",
    parentArtifactId: null,
    title: "Script Outline v1",
    contentJson: {
      step: "script_outline",
      status: "ok",
      confidence: 0.84,
      summary: "Approved outline for citation QA.",
      content: {
        hook: "Why can the same cut feel like relief and danger at once?",
        blocks: ["Hook", "Frame shift", "Evidence", "Historical comparison", "Viewer checklist"],
        transitions: ["From headline to signal", "From signal to evidence"],
        midpoint_shift: "The issue becomes why the Fed moved, not that it moved.",
        climax: "The same cut can imply opposite realities.",
        ending: "Watch labor, credit, and inflation together.",
        est_duration_min: 17,
        block_goals: ["Hook attention", "Support the paradox", "Ground in evidence", "Leave a framework"],
      },
      qc_notes: [],
    },
    contentMarkdown: "# Script Outline\n\nQA outline.",
    qcNotes: [],
    origin: "human_edited",
    humanEdited: true,
    status: "approved",
    approvedByHuman: true,
    approvedByUserId: initialUser?.id ?? "user_ira",
    provenance: {
      mode: "human_edit",
      modelName: "manual_edit",
      note: "QA approved outline",
    },
  });

  const draftWriter = await generateStepArtifact(project.id, "draft_writer");
  const draftContent = draftWriter.contentJson.content as {
    cited_claims?: Array<{ claim?: string; source_refs?: string[] }>;
  };
  assert(
    Array.isArray(draftContent.cited_claims) &&
      draftContent.cited_claims.length > 0 &&
      draftContent.cited_claims.every(
        (item) =>
          typeof item.claim === "string" &&
          Array.isArray(item.source_refs) &&
          item.source_refs.length > 0 &&
          item.source_refs.every((sourceRef) => evidenceSourceRefs.includes(sourceRef)),
      ),
    "Draft writer should emit cited claims linked to evidence-pack source refs.",
  );

  const workspaceAfterDiagnosis = await getProjectWorkspace(project.id);
  assert((workspaceAfterDiagnosis?.auditEvents.length ?? 0) >= 7, "Audit events should be recorded for project creation, generation, approvals, and citation-linked drafting.");

  await saveArtifactVersion({
    projectId: project.id,
    stepName: "channel_diagnosis",
    parentArtifactId: diagnosis.id,
    title: "Channel Diagnosis v2",
    contentJson: diagnosis.contentJson,
    contentMarkdown: diagnosis.contentMarkdown,
    qcNotes: diagnosis.qcNotes,
    origin: "human_edited",
    humanEdited: true,
    provenance: {
      mode: "human_edit",
      modelName: "manual_edit",
      note: "QA upstream refresh",
    },
  });

  const refreshedWorkspace = await getProjectWorkspace(project.id);
  const staleDiagnosis = refreshedWorkspace?.steps.find((step) => step.id === "channel_diagnosis")?.latestArtifact ?? null;
  const generatedAudience = refreshedWorkspace?.steps.find((step) => step.id === "audience_hypothesis")?.latestArtifact ?? null;
  const generatedTopicAssessment = refreshedWorkspace?.steps.find((step) => step.id === "topic_assessment")?.latestArtifact ?? null;
  const generatedEvidencePack = refreshedWorkspace?.steps.find((step) => step.id === "evidence_pack")?.latestArtifact ?? null;
  const generatedDraftWriter = refreshedWorkspace?.steps.find((step) => step.id === "draft_writer")?.latestArtifact ?? null;
  assert(
    staleDiagnosis !== null &&
      generatedAudience !== null &&
      generatedTopicAssessment !== null &&
      generatedEvidencePack !== null &&
      generatedDraftWriter !== null,
    "QA artifacts should exist.",
  );

  const stale = isArtifactStale(generatedAudience!, refreshedWorkspace?.artifacts ?? []);
  assert(stale, "Downstream artifact should become stale after upstream change.");
  assert(
    isArtifactStale(generatedTopicAssessment!, refreshedWorkspace?.artifacts ?? []),
    "Critical downstream artifact should become stale after upstream change.",
  );
  assert(
    isArtifactStale(generatedEvidencePack!, refreshedWorkspace?.artifacts ?? []),
    "Transitive downstream artifact should become stale when an approved input becomes stale.",
  );
  assert(
    isArtifactStale(generatedDraftWriter!, refreshedWorkspace?.artifacts ?? []),
    "Citation-bearing draft should also become stale after upstream changes.",
  );
  assert(
    canAdvance("audience_hypothesis", generatedAudience!, refreshedWorkspace?.artifacts ?? []) === false,
    "Stale artifact should not be advanceable.",
  );
  assert(
    canAdvance("topic_assessment", generatedTopicAssessment!, refreshedWorkspace?.artifacts ?? []) === false,
    "Stale approved artifact should require re-approval before advancing.",
  );
  assert(
    refreshedWorkspace?.controls.pendingCriticalStepLabels.includes("Topic Assessment") ?? false,
    "Critical stale artifact should be treated as pending approval again.",
  );

  let staleApprovalBlocked = false;
  try {
    await generateStepArtifact(project.id, "editorial_angle");
  } catch (error) {
    staleApprovalBlocked =
      error instanceof WorkflowError &&
      error.message.includes("Required approvals are missing for: Topic Assessment.");
  }
  assert(staleApprovalBlocked, "Stale approvals should block downstream critical generation.");

  await setCurrentUser("user_nadia");
  const writerUser = await getCurrentUser();
  assert(writerUser?.role === "writer", "Writer session switch should succeed.");
  const topicApprovalRoles = getStepDefinition("topic_assessment").approvalRoles as readonly UserRole[];
  assert(
    topicApprovalRoles.includes("writer") === false,
    "Writer should not be allowed to approve topic assessment.",
  );

  await setCurrentUser("user_ira");
  const producerUser = await getCurrentUser();
  assert(producerUser?.role === "producer", "Producer session switch should succeed.");
  assert(
    topicApprovalRoles.includes("producer"),
    "Producer should be allowed to approve topic assessment.",
  );

  const radarBefore = await getTopicRadarSnapshot();
  const refreshedRadar = await refreshTopicRadar();
  assert(refreshedRadar.signals.length > 0, "Radar refresh should return signals.");

  const finalWorkspace = await getProjectWorkspace(project.id);
  const result = {
    currentUser: producerUser?.role ?? null,
    executionMode: diagnosis.provenance.mode,
    executionNote: diagnosis.provenance.note,
    modelName: diagnosis.provenance.modelName,
    auditEvents: finalWorkspace?.auditEvents.length ?? 0,
    sourceReferenceCount: finalWorkspace?.controls.sourceReferenceCount ?? 0,
    citedClaimCount: finalWorkspace?.controls.citedClaimCount ?? 0,
    uncitedClaimCount: finalWorkspace?.controls.uncitedClaimCount ?? 0,
    staleStepLabels: finalWorkspace?.steps.filter((step) => step.isStale).map((step) => step.label) ?? [],
    staleControlGaps: finalWorkspace?.controls.controlGaps.filter((gap) => gap.includes("Downstream artifacts")) ?? [],
    writerCanApproveTopicAssessment: topicApprovalRoles.includes("writer"),
    producerCanApproveTopicAssessment: topicApprovalRoles.includes("producer"),
    radarCandidatesBefore: radarBefore.candidates.length,
    radarCandidatesAfter: refreshedRadar.candidates.length,
    topRadarDecision: refreshedRadar.candidates[0]?.decision ?? null,
  };

  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
