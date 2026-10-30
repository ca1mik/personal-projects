export const STEP_STATUSES = [
  "not_started",
  "generating",
  "needs_review",
  "approved",
  "needs_revision",
  "blocked",
  "done",
] as const;

export type StepStatus = (typeof STEP_STATUSES)[number];

export const STEP_IDS = [
  "channel_diagnosis",
  "audience_hypothesis",
  "brief_parsing",
  "topic_assessment",
  "evidence_pack",
  "editorial_angle",
  "script_outline",
  "draft_writer",
  "voice_edit",
  "final_qc",
] as const;

export type StepId = (typeof STEP_IDS)[number];

export type ArtifactOrigin = "ai_generated" | "human_edited";
export type UserRole = "admin" | "producer" | "editor" | "writer" | "author";
export type ArtifactProvenanceMode = "live_model" | "demo_fallback" | "human_edit";
export type AuditEventType =
  | "project_created"
  | "project_deleted"
  | "project_duplicated"
  | "material_uploaded"
  | "step_generated"
  | "artifact_saved"
  | "artifact_approved"
  | "revision_requested"
  | "project_advanced"
  | "current_user_switched";

export type OutputEnvelope<TContent = Record<string, unknown>> = {
  step: StepId;
  status: "ok" | "needs_more_input" | "blocked";
  confidence: number;
  summary: string;
  content: TContent;
  qc_notes: string[];
};

export type User = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  createdAt: string;
  updatedAt: string;
};

export type Project = {
  id: string;
  title: string;
  authorName: string;
  channelName: string;
  status: "draft" | "in_progress" | "completed" | "on_hold";
  currentStepName: StepId;
  topic: string;
  deadline: string | null;
  createdAt: string;
  updatedAt: string;
};

export type StepRun = {
  id: string;
  projectId: string;
  stepName: StepId;
  status: StepStatus;
  version: number;
  startedAt: string;
  finishedAt: string | null;
  modelName: string | null;
  promptSnapshot: {
    system: string;
    user: string;
  } | null;
  inputRefs: {
    artifactIds: string[];
    uploadIds: string[];
    sourceIds: string[];
  };
  outputArtifactId: string | null;
  qcStatus: "pass" | "warn" | "fail" | "approved" | "needs_revision" | null;
  errorMessage: string | null;
  executionMode: ArtifactProvenanceMode;
  tokenEstimate: number | null;
  costEstimateUsd: number | null;
};

export type Artifact = {
  id: string;
  projectId: string;
  stepName: StepId;
  version: number;
  status: StepStatus;
  origin: ArtifactOrigin;
  title: string;
  contentJson: OutputEnvelope;
  contentMarkdown: string;
  qcNotes: string[];
  approvedByHuman: boolean;
  approvedByUserId: string | null;
  parentArtifactId: string | null;
  humanEdited: boolean;
  inputArtifactIds: string[];
  provenance: {
    mode: ArtifactProvenanceMode;
    modelName: string | null;
    note: string | null;
  };
  createdAt: string;
  updatedAt: string;
};

export type Source = {
  id: string;
  projectId: string;
  type: string;
  title: string;
  sourceRef: string;
  url: string | null;
  sourceDate: string | null;
  summary: string;
  trustLevel: "low" | "medium" | "high";
  supportedClaims: string[];
  linkedStep: StepId;
  createdAt: string;
  updatedAt: string;
};

export type Upload = {
  id: string;
  projectId: string;
  kind: "brief" | "transcript" | "metrics" | "notes" | "material";
  fileName: string;
  fileType: string;
  pathOrBlobRef: string | null;
  extractedText: string;
  createdAt: string;
  updatedAt: string;
};

export type NewsRadarSource = {
  id: string;
  label: string;
  category: "official" | "wire" | "research";
  url: string;
  trustLevel: "high" | "medium";
  region: string;
  enabled: boolean;
};

export type NewsSignal = {
  id: string;
  sourceId: string;
  sourceLabel: string;
  title: string;
  url: string;
  summary: string;
  publishedAt: string;
  tags: string[];
  clusterKey: string;
  authorityScore: number;
};

export type TopicCandidate = {
  id: string;
  title: string;
  angle: string;
  summary: string;
  whyNow: string;
  youtubePotentialScore: number;
  viralityScore: number;
  evidenceStrength: number;
  noveltyScore: number;
  momentumScore: number;
  competitorMomentumScore: number;
  macroRelevanceScore: number;
  competitionPressure: number;
  monetizationFitScore: number;
  timingWindowDays: number;
  productionEffort: "low" | "medium" | "high";
  decision: "shoot_now" | "hold_watch" | "skip";
  packagingHooks: string[];
  economics: {
    researchCostUsd: number;
    scriptingCostUsd: number;
    totalCostUsd: number;
    breakEvenViews: number;
  };
  recommendedFormat: string;
  status: "watch" | "hot" | "commissioned" | "cooling";
  clusterKey: string;
  signalIds: string[];
  tags: string[];
  createdAt: string;
  updatedAt: string;
};

export type CompetitorVideoSignal = {
  id: string;
  channelName: string;
  title: string;
  url: string;
  publishedAt: string;
  topicLabel: string;
  views: number;
  viewsPerDay: number;
  performanceBand: "breakout" | "strong" | "baseline" | "weak";
  notes: string;
};

export type AuditEvent = {
  id: string;
  projectId: string | null;
  artifactId: string | null;
  stepRunId: string | null;
  actorUserId: string | null;
  type: AuditEventType;
  message: string;
  metadata: Record<string, string | number | boolean | null>;
  createdAt: string;
};

export type AppStore = {
  users: User[];
  activeUserId: string | null;
  projects: Project[];
  stepRuns: StepRun[];
  artifacts: Artifact[];
  sources: Source[];
  uploads: Upload[];
  radarSources: NewsRadarSource[];
  newsSignals: NewsSignal[];
  topicCandidates: TopicCandidate[];
  competitorSignals: CompetitorVideoSignal[];
  auditEvents: AuditEvent[];
};

export type PipelineStepMeta = {
  id: StepId;
  label: string;
  shortLabel: string;
  description: string;
  critical: boolean;
};

export const PIPELINE_STEPS: PipelineStepMeta[] = [
  {
    id: "channel_diagnosis",
    label: "Channel Diagnosis",
    shortLabel: "Diagnosis",
    description: "Analyze transcripts, titles, view patterns, and comments.",
    critical: false,
  },
  {
    id: "audience_hypothesis",
    label: "Audience Hypothesis",
    shortLabel: "Audience",
    description: "Infer audience segments, knowledge level, and triggers.",
    critical: false,
  },
  {
    id: "brief_parsing",
    label: "Brief Parsing",
    shortLabel: "Brief",
    description: "Normalize the author or producer brief into a usable input.",
    critical: false,
  },
  {
    id: "topic_assessment",
    label: "Topic Assessment",
    shortLabel: "Assessment",
    description: "Decide whether the topic should go, pivot, or be rejected.",
    critical: true,
  },
  {
    id: "evidence_pack",
    label: "Evidence Pack",
    shortLabel: "Evidence",
    description: "Assemble facts, counterarguments, and source scaffolding.",
    critical: false,
  },
  {
    id: "editorial_angle",
    label: "Editorial Angle",
    shortLabel: "Angle",
    description: "Choose the conflict, core question, and why-now frame.",
    critical: true,
  },
  {
    id: "script_outline",
    label: "Script Outline",
    shortLabel: "Outline",
    description: "Build the 15-20 minute structure with transitions and climax.",
    critical: true,
  },
  {
    id: "draft_writer",
    label: "Draft Writer",
    shortLabel: "Draft",
    description: "Generate the full first script draft.",
    critical: false,
  },
  {
    id: "voice_edit",
    label: "Voice Edit",
    shortLabel: "Voice",
    description: "Edit the draft into the author's spoken style.",
    critical: true,
  },
  {
    id: "final_qc",
    label: "Final QC",
    shortLabel: "QC",
    description: "Run final editorial, factual, and reputational checks.",
    critical: true,
  },
];

export function getStepIndex(stepId: StepId) {
  return STEP_IDS.indexOf(stepId);
}

export function getStepMeta(stepId: StepId) {
  return PIPELINE_STEPS.find((step) => step.id === stepId);
}

export function getNextStepId(stepId: StepId): StepId | null {
  const index = getStepIndex(stepId);
  return index >= 0 && index < STEP_IDS.length - 1 ? STEP_IDS[index + 1] : null;
}

export function isStepId(value: string): value is StepId {
  return STEP_IDS.includes(value as StepId);
}

export function requiresApproval(stepId: StepId) {
  return Boolean(getStepMeta(stepId)?.critical);
}
