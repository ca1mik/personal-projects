"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { diffLines } from "diff";
import { generateStepArtifact, WorkflowError } from "@/lib/ai/orchestrator";
import {
  appendAuditEvent,
  canAdvance,
  createProject,
  createUpload,
  deleteProject,
  duplicateProject,
  findArtifactById,
  getArtifactHistory,
  getCurrentUser,
  getProjectWorkspace,
  isArtifactStale,
  listUsers,
  nextStepAfter,
  saveArtifactVersion,
  setCurrentUser,
  updateArtifactState,
  updateProjectStep,
} from "@/lib/data/repository";
import { isStepId, type Artifact, type StepId, type UserRole } from "@/lib/domain/pipeline";
import { LOCALE_COOKIE } from "@/lib/i18n";
import { persistUpload } from "@/lib/server/uploads";
import { getStepDefinition } from "@/lib/steps/registry";
import { refreshTopicRadar } from "@/lib/server/topic-radar";

function withFlash(path: string, params: Record<string, string | null | undefined>) {
  const url = new URL(path, "http://ike.local");
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }
  return `${url.pathname}${url.search}`;
}

function getReturnTo(formData: FormData, fallback: string) {
  const value = String(formData.get("returnTo") || "").trim();
  return value.startsWith("/") ? value : fallback;
}

function asStepId(value: FormDataEntryValue | null): StepId {
  if (typeof value !== "string" || !isStepId(value)) {
    throw new Error("Invalid step.");
  }

  return value;
}

function toStringArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string");
}

export async function createProjectAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/projects");
  const title = String(formData.get("title") || "").trim();
  const authorName = String(formData.get("authorName") || "").trim();
  const channelName = String(formData.get("channelName") || "").trim();
  const topic = String(formData.get("topic") || "").trim();
  const deadline = String(formData.get("deadline") || "").trim();

  if (!title || !authorName || !topic) {
    redirect(withFlash(returnTo, { error: "Fill in title, author, and topic before creating a project." }));
  }

  const project = await createProject({
    title,
    authorName,
    channelName,
    topic,
    deadline: deadline || null,
  });

  redirect(`/projects/${project.id}`);
}

export async function deleteProjectAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/projects");
  const projectId = String(formData.get("projectId") || "");
  await deleteProject(projectId);
  redirect(withFlash(returnTo, { notice: "Project deleted." }));
}

export async function duplicateProjectAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/projects");
  const projectId = String(formData.get("projectId") || "");
  const duplicated = await duplicateProject(projectId);

  if (duplicated) {
    redirect(withFlash(`/projects/${duplicated.id}`, { notice: "Project duplicated." }));
  }

  redirect(withFlash(returnTo, { error: "Could not duplicate the project." }));
}

export async function uploadMaterialAction(formData: FormData) {
  const projectId = String(formData.get("projectId") || "");
  const returnTo = getReturnTo(formData, `/projects/${projectId}`);
  const kind = String(formData.get("kind") || "material") as Artifact["stepName"] | "brief" | "transcript" | "metrics" | "notes" | "material";
  const file = formData.get("file");

  if (!(file instanceof File) || !file.name) {
    redirect(withFlash(returnTo, { error: "Choose a file before uploading material." }));
  }

  const persisted = await persistUpload(projectId, file);
  await createUpload({
    projectId,
    kind: ["brief", "transcript", "metrics", "notes", "material"].includes(kind)
      ? (kind as "brief" | "transcript" | "metrics" | "notes" | "material")
      : "material",
    fileName: file.name,
    fileType: file.type || "application/octet-stream",
    pathOrBlobRef: persisted.relativePath,
    extractedText: persisted.extractedText,
  });

  redirect(withFlash(returnTo, { notice: `Uploaded ${file.name}.` }));
}

export async function generateStepAction(formData: FormData) {
  const projectId = String(formData.get("projectId") || "");
  const returnTo = getReturnTo(formData, `/projects/${projectId}`);
  const stepId = asStepId(formData.get("stepId"));

  try {
    await generateStepArtifact(projectId, stepId);
  } catch (error) {
    if (error instanceof WorkflowError) {
      redirect(withFlash(returnTo, { error: error.message }));
    }
    redirect(withFlash(returnTo, { error: "Step generation failed. Check upstream inputs and try again." }));
  }

  redirect(withFlash(returnTo, { notice: `Generated ${stepId.replaceAll("_", " ")} artifact.` }));
}

export async function saveArtifactDraftAction(formData: FormData) {
  const projectId = String(formData.get("projectId") || "");
  const returnTo = getReturnTo(formData, `/projects/${projectId}`);
  const stepId = asStepId(formData.get("stepId"));
  const parentArtifactId = String(formData.get("parentArtifactId") || "") || null;
  const title = String(formData.get("title") || "").trim() || `${getStepDefinition(stepId).label} Draft`;
  const contentJsonText = String(formData.get("contentJson") || "");
  const contentMarkdown = String(formData.get("contentMarkdown") || "");
  const qcNotesText = String(formData.get("qcNotes") || "");

  let validated: Artifact["contentJson"];
  try {
    const parsedJson = JSON.parse(contentJsonText);
    validated = getStepDefinition(stepId).outputSchema.parse(parsedJson);
  } catch {
    redirect(withFlash(returnTo, { error: "Structured JSON is invalid for this step schema." }));
  }
  const qcNotes = qcNotesText
    .split("\n")
    .map((note) => note.trim())
    .filter(Boolean);

  await saveArtifactVersion({
    projectId,
    stepName: stepId,
    parentArtifactId,
    title,
    contentJson: validated!,
    contentMarkdown,
    qcNotes,
    origin: "human_edited",
    humanEdited: true,
    status: getStepDefinition(stepId).requiresHumanApproval ? "needs_review" : "done",
    provenance: {
      mode: "human_edit",
      modelName: "manual_edit",
      note: "Saved through the manual editor.",
    },
  });

  redirect(withFlash(returnTo, { notice: "Draft saved as a new artifact version." }));
}

export async function approveArtifactAction(formData: FormData) {
  const projectId = String(formData.get("projectId") || "");
  const returnTo = getReturnTo(formData, `/projects/${projectId}`);
  const artifactId = String(formData.get("artifactId") || "");
  const user = await getCurrentUser();
  const artifact = await findArtifactById(artifactId);

  if (!artifact) {
    redirect(withFlash(returnTo, { error: "Artifact not found." }));
  }

  const approvalRoles = getStepDefinition(artifact.stepName).approvalRoles as readonly UserRole[];
  if (!user || !approvalRoles.includes(user.role)) {
    redirect(withFlash(returnTo, { error: "Your current role is not allowed to approve this step." }));
  }

  const workspace = await getProjectWorkspace(artifact.projectId);
  if (!workspace || isArtifactStale(artifact, workspace.artifacts)) {
    redirect(withFlash(returnTo, { error: "This artifact is stale after upstream changes. Regenerate or save a new version before approval." }));
  }

  await updateArtifactState({
    artifactId,
    status: "approved",
    approvedByHuman: true,
    approvedByUserId: user?.id ?? null,
  });

  redirect(withFlash(returnTo, { notice: "Artifact approved." }));
}

export async function requestRevisionAction(formData: FormData) {
  const projectId = String(formData.get("projectId") || "");
  const returnTo = getReturnTo(formData, `/projects/${projectId}`);
  const artifactId = String(formData.get("artifactId") || "");
  const notes = String(formData.get("revisionNotes") || "")
    .split("\n")
    .map((note) => note.trim())
    .filter(Boolean);

  await updateArtifactState({
    artifactId,
    status: "needs_revision",
    qcNotes: notes,
  });

  redirect(withFlash(returnTo, { notice: "Revision requested." }));
}

export async function sendToNextStepAction(formData: FormData) {
  const projectId = String(formData.get("projectId") || "");
  const returnTo = getReturnTo(formData, `/projects/${projectId}`);
  const stepId = asStepId(formData.get("stepId"));
  const history = await getArtifactHistory(projectId, stepId);

  if (!history) {
    redirect(withFlash(returnTo, { error: "Artifact history not found." }));
  }

  const latestArtifact = history.versions[0] ?? null;
  if (!canAdvance(stepId, latestArtifact, history.workspace.artifacts)) {
    const stepState = history.workspace.steps.find((step) => step.id === stepId);
    redirect(withFlash(returnTo, { error: stepState?.blockingIssue ?? "This step is not ready to advance." }));
  }

  const nextStep = nextStepAfter(stepId);
  await updateProjectStep(projectId, nextStep);
  redirect(
    withFlash(
      nextStep ? `/projects/${projectId}?step=${nextStep}` : `/projects/${projectId}`,
      { notice: nextStep ? "Moved to the next step." : "Project marked complete." },
    ),
  );
}

export async function artifactDiffAction(formData: FormData) {
  const older = String(formData.get("older") || "");
  const newer = String(formData.get("newer") || "");
  const olderLines = older || "";
  const newerLines = newer || "";

  return diffLines(olderLines, newerLines);
}

export async function resetDemoStoreAction() {
  const { resetStore } = await import("@/lib/server/store");
  await resetStore();
  redirect(withFlash("/projects", { notice: "Demo data reset." }));
}

export async function parseArtifactQcNotes(contentJson: Artifact["contentJson"]) {
  return toStringArray(contentJson.qc_notes);
}

export async function refreshTopicRadarAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/radar");
  const result = await refreshTopicRadar();
  redirect(
    withFlash(returnTo, {
      notice: result.usedFallback
        ? "Radar refresh failed over to stored data."
        : `Radar refreshed: ${result.signals.length} signals, ${result.candidates.length} topic candidates.`,
    }),
  );
}

export async function createProjectFromCandidateAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/radar");
  const title = String(formData.get("title") || "").trim();
  const topic = String(formData.get("topic") || "").trim();
  const angle = String(formData.get("angle") || "").trim();

  if (!title || !topic) {
    redirect(withFlash(returnTo, { error: "Candidate data is missing." }));
  }

  const project = await createProject({
    title,
    authorName: "TBD author",
    channelName: "Macro Dispatch",
    topic: angle ? `${topic}\n\nEditorial angle seed: ${angle}` : topic,
    deadline: null,
  });

  redirect(withFlash(`/projects/${project.id}`, { notice: "Project created from topic candidate." }));
}

export async function switchCurrentUserAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/projects");
  const userId = String(formData.get("userId") || "").trim();

  if (!userId) {
    redirect(withFlash(returnTo, { error: "Choose a session user." }));
  }

  const user = await setCurrentUser(userId);
  if (!user) {
    redirect(withFlash(returnTo, { error: "User session could not be switched." }));
  }

  const users = await listUsers();
  await appendAuditEvent({
    projectId: null,
    actorUserId: user.id,
    type: "current_user_switched",
    message: `Current session switched to ${user.name}.`,
    metadata: {
      role: user.role,
      availableUsers: users.length,
    },
  });

  redirect(withFlash(returnTo, { notice: `Session switched to ${user.name}.` }));
}

export async function setLocaleAction(formData: FormData) {
  const returnTo = getReturnTo(formData, "/projects");
  const locale = String(formData.get("locale") || "").trim();

  if (locale !== "ru" && locale !== "en") {
    redirect(returnTo);
  }

  const store = await cookies();
  store.set(LOCALE_COOKIE, locale, {
    path: "/",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 365,
  });

  redirect(returnTo);
}
