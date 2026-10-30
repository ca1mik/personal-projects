import { z } from "zod";
import type { Artifact, OutputEnvelope, Project, Source, StepId, Upload, UserRole } from "@/lib/domain/pipeline";

const baseEnvelope = <T extends z.ZodTypeAny>(step: StepId, content: T) =>
  z.object({
    step: z.literal(step),
    status: z.enum(["ok", "needs_more_input", "blocked"]),
    confidence: z.number().min(0).max(1),
    summary: z.string(),
    content,
    qc_notes: z.array(z.string()),
  });

const sourcesArraySchema = z.array(
  z.object({
    title: z.string(),
    source_ref: z.string(),
    url: z.string().nullable().optional(),
    summary: z.string(),
    trust_level: z.enum(["low", "medium", "high"]).default("medium"),
    type: z.string().optional(),
    source_date: z.string().nullable().optional(),
    supported_claims: z.array(z.string()).default([]),
  }),
);

const citationClaimSchema = z.object({
  claim: z.string(),
  source_refs: z.array(z.string()),
  note: z.string().nullable().optional(),
});

const citationCheckSchema = z.object({
  claim: z.string(),
  source_refs: z.array(z.string()),
  status: z.enum(["verified", "needs_review", "missing_support"]),
  note: z.string(),
});

const channelDiagnosisSchema = baseEnvelope(
  "channel_diagnosis",
  z.object({
    winning_topics: z.array(z.string()),
    weak_topics: z.array(z.string()),
    tone_profile: z.string(),
    complexity_level: z.string(),
    retention_patterns: z.array(z.string()),
    title_patterns: z.array(z.string()),
    risks: z.array(z.string()),
    recommendations: z.array(z.string()),
  }),
);

const audienceHypothesisSchema = baseEnvelope(
  "audience_hypothesis",
  z.object({
    segments: z.array(z.string()),
    knowledge_level: z.string(),
    core_pains: z.array(z.string()),
    desires: z.array(z.string()),
    trigger_topics: z.array(z.string()),
    objection_patterns: z.array(z.string()),
    preferred_explanation_style: z.string(),
    attention_profile: z.string(),
  }),
);

const briefParsingSchema = baseEnvelope(
  "brief_parsing",
  z.object({
    requested_topic: z.string(),
    core_thesis: z.string(),
    desired_outcome: z.string(),
    author_intent: z.string(),
    constraints: z.array(z.string()),
    must_include: z.array(z.string()),
    must_avoid: z.array(z.string()),
    ambiguities: z.array(z.string()),
  }),
);

const topicAssessmentSchema = baseEnvelope(
  "topic_assessment",
  z.object({
    verdict: z.enum(["go", "pivot", "reject"]),
    fit_score: z.number().min(0).max(1),
    why_now_score: z.number().min(0).max(1),
    novelty_score: z.number().min(0).max(1),
    risk_score: z.number().min(0).max(1),
    problems: z.array(z.string()),
    pivot_options: z.array(z.string()),
    recommended_direction: z.string(),
  }),
);

const evidencePackSchema = baseEnvelope(
  "evidence_pack",
  z.object({
    key_facts: z.array(z.string()),
    data_points: z.array(z.string()),
    current_news: z.array(z.string()),
    historical_parallels: z.array(z.string()),
    expert_positions: z.array(z.string()),
    counterarguments: z.array(z.string()),
    open_questions: z.array(z.string()),
    sources: sourcesArraySchema,
  }),
);

const editorialAngleSchema = baseEnvelope(
  "editorial_angle",
  z.object({
    core_question: z.string(),
    central_conflict: z.string(),
    hook_options: z.array(z.string()),
    viewer_promise: z.string(),
    emotional_frame: z.string(),
    why_this_matters_now: z.string(),
    chosen_angle: z.string(),
    rejected_angles: z.array(z.string()),
  }),
);

const scriptOutlineSchema = baseEnvelope(
  "script_outline",
  z.object({
    hook: z.string(),
    blocks: z.array(z.string()),
    transitions: z.array(z.string()),
    midpoint_shift: z.string(),
    climax: z.string(),
    ending: z.string(),
    est_duration_min: z.number().int().min(1),
    block_goals: z.array(z.string()),
  }),
);

const draftWriterSchema = baseEnvelope(
  "draft_writer",
  z.object({
    title_options: z.array(z.string()),
    opening: z.string(),
    full_text: z.string(),
    cited_claims: z.array(citationClaimSchema),
    callback_points: z.array(z.string()),
  }),
);

const voiceEditSchema = baseEnvelope(
  "voice_edit",
  z.object({
    final_spoken_text: z.string(),
    tightened_sections: z.array(z.string()),
    simplified_explanations: z.array(z.string()),
    tone_adjustments: z.array(z.string()),
    removed_aiisms: z.array(z.string()),
  }),
);

const finalQcSchema = baseEnvelope(
  "final_qc",
  z.object({
    factual_risks: z.array(z.string()),
    logic_gaps: z.array(z.string()),
    pacing_issues: z.array(z.string()),
    style_issues: z.array(z.string()),
    legal_reputation_risks: z.array(z.string()),
    final_readiness: z.enum(["not_ready", "needs_edits", "ready"]),
    required_edits: z.array(z.string()),
    citation_checks: z.array(citationCheckSchema),
    final_script: z.string(),
  }),
);

export type StepContext = {
  project: Project;
  inputArtifacts: Artifact[];
  uploads: Upload[];
  sources: Source[];
};

type StepDefinition<TSchema extends z.ZodTypeAny> = {
  id: StepId;
  label: string;
  description: string;
  purpose: string;
  allowedInputs: string[];
  inputArtifactSteps: StepId[];
  outputSchema: TSchema;
  qcRules: string[];
  failConditions: string[];
  humanReviewCriteria: string[];
  requiresHumanApproval: boolean;
  approvalRoles: UserRole[];
  nextStepRules: string[];
  preferredModel: string;
  promptBuilder: (context: StepContext) => {
    system: string;
    user: string;
  };
};

function summarizeArtifacts(artifacts: Artifact[]) {
  return artifacts
    .map((artifact) => {
      const content = JSON.stringify(artifact.contentJson.content, null, 2);
      return `Step: ${artifact.stepName}\nVersion: ${artifact.version}\nSummary: ${artifact.contentJson.summary}\nContent:\n${content}`;
    })
    .join("\n\n");
}

function summarizeUploads(uploads: Upload[]) {
  return uploads
    .map((upload) => `Upload (${upload.kind}) ${upload.fileName}:\n${upload.extractedText}`)
    .join("\n\n");
}

function summarizeSources(sources: Source[]) {
  return sources
    .map((source) => `${source.title} (${source.trustLevel})${source.url ? ` - ${source.url}` : ""}\n${source.summary}`)
    .join("\n\n");
}

function commonSystemPrompt(stepLabel: string, purpose: string) {
  return [
    `You are producing the "${stepLabel}" artifact in a multi-step editorial workflow for macroeconomics YouTube scripting.`,
    purpose,
    "Rules:",
    "- Only do the work for this step. Do not pre-empt later steps.",
    "- Use only the provided inputs.",
    "- Separate facts from interpretation.",
    "- If information is missing, say so explicitly.",
    "- Never invent sources or certainty.",
    "- When citing evidence, use stable source_ref values from the evidence pack or provided sources.",
    "- Return only a structured JSON artifact matching the schema.",
  ].join("\n");
}

export const stepRegistry = {
  channel_diagnosis: {
    id: "channel_diagnosis",
    label: "Channel Diagnosis",
    description: "Analyze what the channel already wins and loses on.",
    purpose: "Diagnose format, retention, tone, and editorial fit before audience or topic work starts.",
    allowedInputs: ["brief upload", "transcripts", "channel metrics", "notes"],
    inputArtifactSteps: [],
    outputSchema: channelDiagnosisSchema,
    qcRules: [
      "Differentiate strong and weak topics.",
      "Surface retention and title patterns separately.",
      "Recommendations must be channel-specific.",
    ],
    failConditions: ["No transcripts or metrics provided", "Output drifts into audience persona work"],
    humanReviewCriteria: ["Does this reflect the real channel voice and performance patterns?"],
    requiresHumanApproval: false,
    approvalRoles: [],
    nextStepRules: ["Proceed once a usable diagnosis exists."],
    preferredModel: "gpt-4.1-mini",
    promptBuilder: ({ project, uploads }) => ({
      system: commonSystemPrompt("Channel Diagnosis", "Analyze the editorial DNA of the channel from prior materials."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nMaterials:\n${summarizeUploads(uploads)}`,
    }),
  },
  audience_hypothesis: {
    id: "audience_hypothesis",
    label: "Audience Hypothesis",
    description: "Infer who the audience is and how they want to be taught.",
    purpose: "Turn channel diagnosis into a practical audience model for later editorial choices.",
    allowedInputs: ["channel diagnosis", "transcripts", "brief upload"],
    inputArtifactSteps: ["channel_diagnosis"],
    outputSchema: audienceHypothesisSchema,
    qcRules: ["Avoid generic personas.", "Tie audience needs to explanation style."],
    failConditions: ["No diagnosis artifact", "Output repeats channel diagnosis without audience implications"],
    humanReviewCriteria: ["Would the producer agree these are the channel's real viewers?"],
    requiresHumanApproval: false,
    approvalRoles: [],
    nextStepRules: ["Proceed when audience segments and attention profile are clear."],
    preferredModel: "gpt-4.1-mini",
    promptBuilder: ({ project, inputArtifacts, uploads }) => ({
      system: commonSystemPrompt("Audience Hypothesis", "Infer the audience without inventing unsupported demographics."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}\n\nMaterials:\n${summarizeUploads(uploads)}`,
    }),
  },
  brief_parsing: {
    id: "brief_parsing",
    label: "Brief Parsing",
    description: "Normalize the brief into an editorially usable summary.",
    purpose: "Extract the requested topic, thesis, constraints, and ambiguities from the brief.",
    allowedInputs: ["brief upload", "producer notes"],
    inputArtifactSteps: [],
    outputSchema: briefParsingSchema,
    qcRules: ["List ambiguities explicitly.", "Separate must-include from must-avoid."],
    failConditions: ["No brief-like input", "Output resolves ambiguities without evidence"],
    humanReviewCriteria: ["Does the normalized brief reflect what the author actually asked for?"],
    requiresHumanApproval: false,
    approvalRoles: [],
    nextStepRules: ["Proceed once the brief is normalized and ambiguities are visible."],
    preferredModel: "gpt-4.1-mini",
    promptBuilder: ({ project, uploads }) => ({
      system: commonSystemPrompt("Brief Parsing", "Normalize the brief, keeping author intent and uncertainty visible."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nMaterials:\n${summarizeUploads(uploads.filter((upload) => upload.kind === "brief" || upload.kind === "notes"))}`,
    }),
  },
  topic_assessment: {
    id: "topic_assessment",
    label: "Topic Assessment",
    description: "Decide whether the topic fits, needs a pivot, or should be rejected.",
    purpose: "Test channel fit, novelty, and why-now strength before research deepens.",
    allowedInputs: ["channel diagnosis", "audience hypothesis", "brief parsing", "early sources"],
    inputArtifactSteps: ["channel_diagnosis", "audience_hypothesis", "brief_parsing"],
    outputSchema: topicAssessmentSchema,
    qcRules: ["Verdict must be explicit.", "Problems and pivot options must be actionable."],
    failConditions: ["Missing upstream editorial context", "Output confuses assessment with angle-writing"],
    humanReviewCriteria: ["Would a producer trust this verdict before resourcing the script?"],
    requiresHumanApproval: true,
    approvalRoles: ["admin", "producer", "editor", "author"],
    nextStepRules: ["Must be human-approved before editorial angle."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts, sources }) => ({
      system: commonSystemPrompt("Topic Assessment", "Assess the topic honestly and recommend go, pivot, or reject."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}\n\nSources:\n${summarizeSources(sources)}`,
    }),
  },
  evidence_pack: {
    id: "evidence_pack",
    label: "Evidence Pack",
    description: "Collect facts, analogies, sources, and counterarguments.",
    purpose: "Build the research base that later steps can rely on without inventing evidence.",
    allowedInputs: ["brief parsing", "topic assessment", "source list", "manual notes"],
    inputArtifactSteps: ["brief_parsing", "topic_assessment"],
    outputSchema: evidencePackSchema,
    qcRules: ["Include counterarguments.", "Do not fabricate sources.", "Flag open questions.", "Assign a stable source_ref to every source."],
    failConditions: ["No assessment artifact", "Sources are missing or obviously fabricated"],
    humanReviewCriteria: ["Are the facts and source scaffolding strong enough to support angle and outline work?"],
    requiresHumanApproval: false,
    approvalRoles: [],
    nextStepRules: ["Proceed when the evidence base is sufficient and uncertainties are visible."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts, sources, uploads }) => ({
      system: commonSystemPrompt("Evidence Pack", "Assemble a fact base and expose uncertainty instead of smoothing it over."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}\n\nSources:\n${summarizeSources(sources)}\n\nMaterials:\n${summarizeUploads(uploads)}`,
    }),
  },
  editorial_angle: {
    id: "editorial_angle",
    label: "Editorial Angle",
    description: "Choose the core question, conflict, and promise.",
    purpose: "Turn the topic and evidence into one editorially sharp angle that can carry a full video.",
    allowedInputs: ["topic assessment", "evidence pack", "audience hypothesis", "brief parsing"],
    inputArtifactSteps: ["topic_assessment", "evidence_pack", "audience_hypothesis", "brief_parsing"],
    outputSchema: editorialAngleSchema,
    qcRules: ["The chosen angle must be singular and specific.", "Rejected angles should explain tradeoffs."],
    failConditions: ["Topic assessment is not approved", "Output drifts into full outline writing"],
    humanReviewCriteria: ["Is this the angle the team actually wants to commit to?"],
    requiresHumanApproval: true,
    approvalRoles: ["admin", "producer", "editor", "author"],
    nextStepRules: ["Must be human-approved before script outline."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts }) => ({
      system: commonSystemPrompt("Editorial Angle", "Choose one strong angle and explain why competing angles lose."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}`,
    }),
  },
  script_outline: {
    id: "script_outline",
    label: "Script Outline",
    description: "Build the 15-20 minute block structure and narrative climb.",
    purpose: "Create the structural scaffold for the draft without writing the full script.",
    allowedInputs: ["editorial angle", "evidence pack", "topic assessment"],
    inputArtifactSteps: ["editorial_angle", "evidence_pack", "topic_assessment"],
    outputSchema: scriptOutlineSchema,
    qcRules: ["Blocks must imply progression, not a list.", "Include a midpoint shift and climax."],
    failConditions: ["Editorial angle is not approved", "Outline collapses into a draft"],
    humanReviewCriteria: ["Does this structure earn 15-20 minutes of attention?"],
    requiresHumanApproval: true,
    approvalRoles: ["admin", "producer", "editor", "author"],
    nextStepRules: ["Must be human-approved before draft writing."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts }) => ({
      system: commonSystemPrompt("Script Outline", "Design structure, transitions, and escalation without drafting prose."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}`,
    }),
  },
  draft_writer: {
    id: "draft_writer",
    label: "Draft Writer",
    description: "Generate the full first script draft.",
    purpose: "Produce a full-text draft that follows the approved outline and cites claims responsibly.",
    allowedInputs: ["script outline", "editorial angle", "evidence pack"],
    inputArtifactSteps: ["script_outline", "editorial_angle", "evidence_pack"],
    outputSchema: draftWriterSchema,
    qcRules: [
      "Honor the approved outline.",
      "Surface cited claims separately.",
      "Every cited claim must point to one or more source_ref values when support exists.",
      "Avoid spoken-voice polish; that belongs later.",
    ],
    failConditions: ["Outline is not approved", "Draft tries to imitate final voice-edit stage"],
    humanReviewCriteria: ["Is the draft structurally sound enough for voice edit?"],
    requiresHumanApproval: false,
    approvalRoles: [],
    nextStepRules: ["Proceed once a structurally sound draft exists."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts }) => ({
      system: commonSystemPrompt("Draft Writer", "Write the full draft, but do not perform the later voice-edit step."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}`,
    }),
  },
  voice_edit: {
    id: "voice_edit",
    label: "Voice Edit",
    description: "Edit the draft into the live spoken voice of the author.",
    purpose: "Turn the draft into speech-ready copy while preserving editorial structure and claims.",
    allowedInputs: ["draft writer", "channel diagnosis", "transcripts"],
    inputArtifactSteps: ["draft_writer", "channel_diagnosis"],
    outputSchema: voiceEditSchema,
    qcRules: ["Tighten explanations.", "Remove AI-isms.", "Keep logic intact."],
    failConditions: ["No draft exists", "Output introduces new factual claims or structural changes"],
    humanReviewCriteria: ["Does this sound like the real author speaking on camera?"],
    requiresHumanApproval: true,
    approvalRoles: ["admin", "producer", "editor", "author"],
    nextStepRules: ["Must be human-approved before final QC is trusted."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts, uploads }) => ({
      system: commonSystemPrompt("Voice Edit", "Edit for live spoken delivery while preserving substance."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}\n\nTranscripts:\n${summarizeUploads(uploads.filter((upload) => upload.kind === "transcript"))}`,
    }),
  },
  final_qc: {
    id: "final_qc",
    label: "Final QC",
    description: "Run the final logic, fact, pacing, and reputational check.",
    purpose: "Deliver a QC report and the final script artifact for publishing readiness.",
    allowedInputs: ["voice edit", "evidence pack", "sources"],
    inputArtifactSteps: ["voice_edit", "evidence_pack"],
    outputSchema: finalQcSchema,
    qcRules: [
      "Flag factual risks, logic gaps, pacing issues, and style issues separately.",
      "Return citation_checks that verify or challenge the cited claims with source_ref values.",
    ],
    failConditions: ["Voice edit is not approved", "QC report claims certainty without evidence"],
    humanReviewCriteria: ["Would the editor sign off on this script going to record?"],
    requiresHumanApproval: true,
    approvalRoles: ["admin", "producer", "editor", "author"],
    nextStepRules: ["Final step; if approved, the project can be marked completed."],
    preferredModel: "gpt-4.1",
    promptBuilder: ({ project, inputArtifacts, sources }) => ({
      system: commonSystemPrompt("Final QC", "Perform factual and editorial quality control and return the final script."),
      user: `Project: ${project.title}\nTopic: ${project.topic}\n\nArtifacts:\n${summarizeArtifacts(inputArtifacts)}\n\nSources:\n${summarizeSources(sources)}`,
    }),
  },
} satisfies Record<StepId, StepDefinition<z.ZodTypeAny>>;

export const stepDefinitions = Object.values(stepRegistry);

export function getStepDefinition(stepId: StepId) {
  return stepRegistry[stepId];
}

export function formatArtifactToMarkdown(artifact: OutputEnvelope) {
  const lines = [
    `# ${artifact.step}`,
    "",
    artifact.summary,
    "",
    "## Structured Content",
    "```json",
    JSON.stringify(artifact.content, null, 2),
    "```",
  ];

  if (artifact.qc_notes.length) {
    lines.push("", "## QC Notes", ...artifact.qc_notes.map((note) => `- ${note}`));
  }

  return lines.join("\n");
}
