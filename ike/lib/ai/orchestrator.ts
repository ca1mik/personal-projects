import OpenAI from "openai";
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from "zod";
import { createSourceRef } from "@/lib/citations";
import type { Artifact, StepId } from "@/lib/domain/pipeline";
import { getStepDefinition, formatArtifactToMarkdown } from "@/lib/steps/registry";
import {
  getProjectWorkspace,
  isArtifactApprovalCurrent,
  isArtifactStale,
  recordStepRun,
  saveArtifactVersion,
  selectLatestArtifact,
  syncEvidenceSources,
} from "@/lib/data/repository";
import { createId, nowIso } from "@/lib/server/store";

class WorkflowError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkflowError";
  }
}

type OpenAIGenerationResult = {
  parsedArtifact: unknown | null;
  modelName: string | null;
  errorNote: string | null;
};

type ResponsesApiPayload = {
  output?: Array<{
    content?: Array<{
      type?: string;
      text?: string;
    }>;
  }>;
  output_text?: string;
};

function pickRequiredArtifacts(projectArtifacts: Artifact[], stepIds: StepId[]) {
  return stepIds.map((stepId) => {
    const versions = projectArtifacts
      .filter((artifact) => artifact.stepName === stepId)
      .sort((a, b) => b.version - a.version);
    const approved = versions.find((artifact) => isArtifactApprovalCurrent(artifact, projectArtifacts));
    return approved ?? versions[0] ?? null;
  });
}

function estimateTokens(...parts: string[]) {
  const characters = parts.join(" ").length;
  return Math.max(1, Math.round(characters / 4));
}

function summarizeTopic(projectTopic: string) {
  return projectTopic.replace(/\?$/, "");
}

function buildDemoArtifact(stepId: StepId, projectTitle: string, topic: string, inputs: Artifact[]): unknown {
  const upstreamSummary = inputs.map((item) => item.contentJson.summary).join(" ");

  switch (stepId) {
    case "channel_diagnosis":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.81,
        summary: `The channel around "${projectTitle}" works best when macro tension is translated into viewer stakes.`,
        content: {
          winning_topics: ["Macro contradictions", "Policy tradeoffs", "Household-level consequences"],
          weak_topics: ["Ticker recaps", "Abstract econ lectures"],
          tone_profile: "Measured, intelligent, skeptical",
          complexity_level: "Intermediate",
          retention_patterns: ["Strong openings with a contradiction", "Drop-off during overlong background sections"],
          title_patterns: ["Question-led", "Tension-led", "Why-now framing"],
          risks: ["Jargon creep", "Delayed stakes"],
          recommendations: ["Lead with a paradox", "Translate policy into daily-life outcomes sooner"],
        },
        qc_notes: [],
      };
    case "audience_hypothesis":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.8,
        summary: `Viewers want ${summarizeTopic(topic)} explained without TV-economist vagueness.`,
        content: {
          segments: ["Curious generalists", "Finance-adjacent viewers", "Cost-of-living focused viewers"],
          knowledge_level: "Beginner to intermediate",
          core_pains: ["Contradictory headlines", "Too much jargon", "Hard to see why it matters"],
          desires: ["Clarity", "Specificity", "A useful mental model"],
          trigger_topics: ["Inflation", "Rates", "Growth", "Wages"],
          objection_patterns: ["Feels too abstract", "Feels repetitive"],
          preferred_explanation_style: "Concrete first, layered second",
          attention_profile: "High when tension escalates and examples stay concrete",
        },
        qc_notes: [],
      };
    case "brief_parsing":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.82,
        summary: `The brief for ${projectTitle} is usable, but still needs a sharper editorial question.`,
        content: {
          requested_topic: summarizeTopic(topic),
          core_thesis: `The script should explain ${summarizeTopic(topic)} through consequences rather than slogans.`,
          desired_outcome: "The viewer should leave with a clearer frame for interpreting the issue.",
          author_intent: "Analytical, grounded, non-hype",
          constraints: ["15-20 minutes", "Why-now angle", "No generic explainer tone"],
          must_include: ["Concrete examples", "Counterarguments", "Interpretation limits"],
          must_avoid: ["Overstating certainty", "Magic-bullet conclusions"],
          ambiguities: ["How broad the scope should be", "Which evidence should anchor the opening"],
        },
        qc_notes: [],
      };
    case "topic_assessment":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.85,
        summary: `The topic is a fit, but it needs a narrower contradiction to stand out for ${projectTitle}.`,
        content: {
          verdict: "go",
          fit_score: 0.88,
          why_now_score: 0.83,
          novelty_score: 0.74,
          risk_score: 0.33,
          problems: ["Current framing is still too broad"],
          pivot_options: ["Lead with what the topic reveals rather than what it is", "Contrast the obvious story with the hidden one"],
          recommended_direction: "Choose one sharp contradiction and build the rest of the script around it.",
        },
        qc_notes: ["Upstream context used: " + upstreamSummary],
      };
    case "evidence_pack":
      {
        const laborSourceRef = createSourceRef("Labor market cooling indicators");
        const fedSourceRef = createSourceRef("Fed minutes summary");
      return {
        step: stepId,
        status: "ok",
        confidence: 0.78,
        summary: `There is enough evidence to support a strong outline for ${projectTitle}, with a few open questions kept visible.`,
        content: {
          key_facts: ["The headline story and the underlying signal are not always the same", "Viewers need context more than raw data"],
          data_points: ["Recent labor and credit signals", "Price pass-through examples"],
          current_news: ["Recent policy commentary sharpened the why-now case"],
          historical_parallels: ["A normalization period", "A stress-response period"],
          expert_positions: ["One camp sees normalization", "Another sees hidden stress"],
          counterarguments: ["A single data release can mislead", "Markets often oversimplify"],
          open_questions: ["Which datapoint best anchors the midpoint turn"],
          sources: [
            {
              title: "Labor market cooling indicators",
              source_ref: laborSourceRef,
              url: null,
              summary: "Labor softening is showing up beneath the headline payroll narrative.",
              trust_level: "high",
              type: "demo",
              source_date: null,
              supported_claims: [
                "Labor softening often appears before headline unemployment spikes.",
                "A first cut can reflect weakening demand rather than pure policy normalization.",
              ],
            },
            {
              title: "Fed minutes summary",
              source_ref: fedSourceRef,
              url: null,
              summary: "Fed communication shows a split between inflation persistence concerns and growth downside risks.",
              trust_level: "high",
              type: "demo",
              source_date: null,
              supported_claims: [
                "A first cut can happen in soft-landing and stress scenarios.",
                "Policy easing can be either relief or warning depending on the reason for the cut.",
              ],
            },
          ],
        },
        qc_notes: [],
      };
      }
    case "editorial_angle":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.86,
        summary: `The strongest angle is to decode the hidden signal behind ${summarizeTopic(topic)}.`,
        content: {
          core_question: `What is ${summarizeTopic(topic)} really telling the viewer?`,
          central_conflict: "The obvious interpretation sounds simpler than the evidence suggests.",
          hook_options: [
            "The story everyone repeats may be the least useful part of the story.",
            "The headline sounds clear until you ask what it is actually signaling.",
          ],
          viewer_promise: "The viewer will understand the hidden logic behind the headline framing.",
          emotional_frame: "Curious skepticism",
          why_this_matters_now: "The public conversation is flattening the topic into something too simple.",
          chosen_angle: "Decode the hidden signal behind the headline story.",
          rejected_angles: ["Generic explainer", "Pure market reaction recap"],
        },
        qc_notes: [],
      };
    case "script_outline":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.84,
        summary: `The outline creates a clean narrative climb from surface story to hidden signal for ${projectTitle}.`,
        content: {
          hook: "The easy interpretation is also the least useful one.",
          blocks: [
            "Open with the misleading intuitive story",
            "Explain why that story feels persuasive",
            "Introduce the hidden contradiction",
            "Test the contradiction with evidence",
            "Compare with historical patterns",
            "Leave the viewer with a checklist",
          ],
          transitions: ["From intuition to evidence", "From current story to historical comparison"],
          midpoint_shift: "The viewer stops asking what happened and starts asking what it means.",
          climax: "The hidden signal becomes more important than the headline itself.",
          ending: "A concise checklist for how to read the next development.",
          est_duration_min: 17,
          block_goals: ["Earn attention", "Reverse intuition", "Ground the claim", "Deliver a takeaway"],
        },
        qc_notes: [],
      };
    case "draft_writer":
      {
        const laborSourceRef = createSourceRef("Labor market cooling indicators");
        const fedSourceRef = createSourceRef("Fed minutes summary");
      return {
        step: stepId,
        status: "ok",
        confidence: 0.79,
        summary: `A complete first draft now exists for ${projectTitle}.`,
        content: {
          title_options: [
            `What ${summarizeTopic(topic)} Is Really Telling Us`,
            `The Hidden Signal Behind ${summarizeTopic(topic)}`,
            `Why the Obvious Read on ${summarizeTopic(topic)} Falls Short`,
          ],
          opening:
            "The easiest story to tell is usually the one viewers already heard everywhere else. The more useful question is what this headline is actually signaling beneath the surface.",
          full_text: [
            "Opening paradox and why the common take feels persuasive.",
            "Reframe the issue as a signal problem rather than a headline problem.",
            "Walk through the evidence in plain language.",
            "Contrast the current pattern with a historical analog.",
            "End with a viewer checklist and what to watch next.",
          ].join("\n\n"),
          cited_claims: [
            {
              claim: "Labor softening can show up before headline unemployment spikes.",
              source_refs: [laborSourceRef],
              note: "Use when explaining why the headline labor story may lag the underlying slowdown.",
            },
            {
              claim: "The first cut can signal either normalization or hidden stress depending on what forced the Fed to move.",
              source_refs: [fedSourceRef],
              note: "Anchor the paradox in policy communication rather than market reaction alone.",
            },
          ],
          callback_points: ["Return to the opening paradox in the ending", "Reinforce the hidden-signal frame after the midpoint"],
        },
        qc_notes: [],
      };
      }
    case "voice_edit":
      return {
        step: stepId,
        status: "ok",
        confidence: 0.83,
        summary: `The draft now reads more like a live spoken script for ${projectTitle}.`,
        content: {
          final_spoken_text: "This version tightens phrasing, removes robotic transitions, and keeps the logic intact for spoken delivery.",
          tightened_sections: ["Opening paragraphs", "Midpoint transition", "Ending checklist"],
          simplified_explanations: ["Technical rate language", "Historical comparison framing"],
          tone_adjustments: ["More direct address", "Shorter sentences", "Cleaner contrast phrases"],
          removed_aiisms: ["Over-signposting", "Overly symmetrical phrasing"],
        },
        qc_notes: [],
      };
    case "final_qc":
      {
        const laborSourceRef = createSourceRef("Labor market cooling indicators");
        const fedSourceRef = createSourceRef("Fed minutes summary");
      return {
        step: stepId,
        status: "ok",
        confidence: 0.8,
        summary: `QC is mostly clean, with a small set of final edits before recording ${projectTitle}.`,
        content: {
          factual_risks: ["Verify any current-data references against the final evidence pack"],
          logic_gaps: ["Ensure the historical analogy matches the current claim"],
          pacing_issues: ["Opening can tighten by 10-15 seconds"],
          style_issues: ["One or two transitions still sound written rather than spoken"],
          legal_reputation_risks: ["Avoid overstating certainty about future outcomes"],
          final_readiness: "needs_edits",
          required_edits: ["Tighten opening", "Verify final citations", "Smooth the last transition into the ending"],
          citation_checks: [
            {
              claim: "Labor softening can show up before headline unemployment spikes.",
              source_refs: [laborSourceRef],
              status: "verified",
              note: "Supported by the labor source scaffold in the evidence pack.",
            },
            {
              claim: "The first cut can signal either normalization or hidden stress depending on why policy moved.",
              source_refs: [fedSourceRef],
              status: "verified",
              note: "Supported by the Fed minutes source scaffold.",
            },
          ],
          final_script: "Final script is attached inside the voice-edited draft and needs the listed QC fixes.",
        },
        qc_notes: [],
      };
      }
  }
}

function formatOpenAIError(error: unknown) {
  if (!error || typeof error !== "object") {
    return "Live model output was unavailable.";
  }

  const status = "status" in error && typeof error.status === "number" ? error.status : null;
  const message = "message" in error && typeof error.message === "string" ? error.message : "Live model output was unavailable.";

  if (status === 401) {
    return "OpenAI authentication failed. Check the API key or gateway token for this environment.";
  }

  if (status === 403) {
    return "OpenAI request was forbidden. Check account access, gateway policy, or model permissions.";
  }

  if (status === 404) {
    return "OpenAI endpoint or model was not found. Check OPENAI_BASE_URL and model configuration.";
  }

  if (status === 429) {
    return "OpenAI rate limit was hit. Retry later or lower concurrent generation.";
  }

  return message;
}

function normalizeBaseUrl(baseUrl: string | undefined) {
  return (baseUrl ?? "").trim().replace(/\/+$/, "");
}

function shouldUseResponsesApi(apiKey: string, baseUrl: string | undefined) {
  const normalized = normalizeBaseUrl(baseUrl);
  return apiKey.startsWith("sk-clb-") || normalized.includes("codex.sale");
}

function resolveModelName(stepId: StepId, apiKey: string) {
  const explicitModel = process.env.OPENAI_MODEL?.trim();
  if (explicitModel) {
    return explicitModel;
  }

  if (apiKey.startsWith("sk-clb-")) {
    return "gpt-5.4";
  }

  return getStepDefinition(stepId).preferredModel;
}

function resolveResponsesEndpoint(baseUrl: string | undefined) {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) {
    return "https://codex.sale/v1/responses";
  }

  return normalized.endsWith("/responses") ? normalized : `${normalized}/responses`;
}

function extractResponsesApiText(payload: ResponsesApiPayload) {
  if (typeof payload.output_text === "string" && payload.output_text.trim()) {
    return payload.output_text.trim();
  }

  const text = payload.output
    ?.flatMap((item) => item.content ?? [])
    .filter((content) => content.type === "output_text" && typeof content.text === "string")
    .map((content) => content.text?.trim() ?? "")
    .filter(Boolean)
    .join("\n");

  return text && text.trim() ? text.trim() : null;
}

function formatResponsesApiError(status: number, body: string, endpoint: string) {
  if (status === 401) {
    return `OpenAI authentication failed for ${endpoint}. Check the API key or gateway token for this environment.`;
  }

  if (status === 403) {
    return `OpenAI request was forbidden by ${endpoint}. Check gateway policy or model permissions.`;
  }

  if (status === 404) {
    return `OpenAI endpoint or model was not found at ${endpoint}. Check OPENAI_BASE_URL and model configuration.`;
  }

  if (status === 429) {
    return `OpenAI rate limit was hit at ${endpoint}. Retry later or lower concurrent generation.`;
  }

  const bodySnippet = body.trim().slice(0, 240);
  return bodySnippet
    ? `Live model request failed at ${endpoint}: ${bodySnippet}`
    : `Live model request failed at ${endpoint}.`;
}

function parseStructuredJsonText(rawText: string) {
  const cleaned = rawText
    .trim()
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();

  return JSON.parse(cleaned);
}

async function generateWithResponsesApi(stepId: StepId, system: string, user: string): Promise<OpenAIGenerationResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return {
      parsedArtifact: null,
      modelName: null,
      errorNote: "OpenAI API key is not configured for this environment.",
    };
  }

  const definition = getStepDefinition(stepId);
  const modelName = resolveModelName(stepId, apiKey);
  const endpoint = resolveResponsesEndpoint(process.env.OPENAI_BASE_URL);
  const schemaJson = JSON.stringify(z.toJSONSchema(definition.outputSchema), null, 2);
  const strictInstructions = [
    system,
    "Return exactly one JSON object that matches the JSON schema below.",
    "Do not wrap the result in an outer object keyed by the step name.",
    "Do not include markdown fences.",
    "Do not include explanatory text before or after the JSON.",
    "If information is missing, still return the exact envelope with status set appropriately.",
    `JSON Schema:\n${schemaJson}`,
  ].join("\n\n");

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: modelName,
        instructions: strictInstructions,
        input: user,
        max_output_tokens: 4000,
      }),
    });

    const body = await response.text();
    if (!response.ok) {
      return {
        parsedArtifact: null,
        modelName,
        errorNote: formatResponsesApiError(response.status, body, endpoint),
      };
    }

    const payload = JSON.parse(body) as ResponsesApiPayload;
    const rawText = extractResponsesApiText(payload);
    if (!rawText) {
      return {
        parsedArtifact: null,
        modelName,
        errorNote: "OpenAI returned an empty structured response.",
      };
    }

    return {
      parsedArtifact: parseStructuredJsonText(rawText),
      modelName,
      errorNote: null,
    };
  } catch (error) {
    return {
      parsedArtifact: null,
      modelName,
      errorNote: formatOpenAIError(error),
    };
  }
}

async function generateWithOpenAI(stepId: StepId, system: string, user: string): Promise<OpenAIGenerationResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return {
      parsedArtifact: null,
      modelName: null,
      errorNote: "OpenAI API key is not configured for this environment.",
    };
  }

  if (shouldUseResponsesApi(apiKey, process.env.OPENAI_BASE_URL)) {
    return generateWithResponsesApi(stepId, system, user);
  }

  try {
    const definition = getStepDefinition(stepId);
    const modelName = resolveModelName(stepId, apiKey);
    const client = new OpenAI({
      apiKey,
      baseURL: process.env.OPENAI_BASE_URL || undefined,
    });
    const completion = await client.chat.completions.parse({
      model: modelName,
      messages: [
        { role: "developer", content: system },
        { role: "user", content: user },
      ],
      response_format: zodResponseFormat(definition.outputSchema, `${stepId}_artifact`),
    });

    return {
      parsedArtifact: completion.choices[0]?.message.parsed ?? null,
      modelName,
      errorNote: completion.choices[0]?.message.parsed ? null : "OpenAI returned an empty structured response.",
    };
  } catch (error) {
    return {
      parsedArtifact: null,
      modelName: resolveModelName(stepId, apiKey),
      errorNote: formatOpenAIError(error),
    };
  }
}

export async function generateStepArtifact(projectId: string, stepId: StepId) {
  const workspace = await getProjectWorkspace(projectId);
  if (!workspace) {
    throw new WorkflowError("Project not found.");
  }

  const definition = getStepDefinition(stepId);
  const inputArtifacts = pickRequiredArtifacts(workspace.artifacts, definition.inputArtifactSteps);
  const missingArtifacts = inputArtifacts.some((artifact) => artifact === null);

  if (missingArtifacts) {
    throw new WorkflowError("Required upstream artifacts are missing for this step.");
  }

  const unapprovedCriticalInputs = definition.inputArtifactSteps
    .map((inputStepId) => ({
      inputStepId,
      artifact: selectLatestArtifact(workspace.artifacts, inputStepId),
    }))
    .filter(({ artifact }) => artifact !== null)
    .filter(
      ({ inputStepId, artifact }) =>
        getStepDefinition(inputStepId).requiresHumanApproval &&
        artifact !== null &&
        !isArtifactApprovalCurrent(artifact, workspace.artifacts),
    )
    .map(({ inputStepId }) => getStepDefinition(inputStepId).label);

  if (unapprovedCriticalInputs.length) {
    throw new WorkflowError(`Required approvals are missing for: ${unapprovedCriticalInputs.join(", ")}.`);
  }

  const context = {
    project: workspace.project,
    inputArtifacts: inputArtifacts.filter(Boolean) as Artifact[],
    uploads: workspace.uploads,
    sources: workspace.sources,
  };

  const prompt = definition.promptBuilder(context);
  const startedAt = nowIso();
  const liveResult = await generateWithOpenAI(stepId, prompt.system, prompt.user);
  let parsedArtifact: unknown = liveResult.parsedArtifact;
  let executionMode: "live_model" | "demo_fallback" = "live_model";
  let modelName = liveResult.modelName ?? "demo-fallback";
  let provenanceNote: string | null = null;

  if (!parsedArtifact) {
    executionMode = "demo_fallback";
    modelName = "demo-fallback";
    provenanceNote = liveResult.errorNote
      ? `${liveResult.errorNote} The system used deterministic demo fallback content instead.`
      : "Live model output was unavailable, so the system used deterministic demo fallback content.";
    parsedArtifact = buildDemoArtifact(stepId, workspace.project.title, workspace.project.topic, context.inputArtifacts);
  }

  const validated = definition.outputSchema.parse(parsedArtifact);
  const qcNotes = [...validated.qc_notes];
  if (provenanceNote) {
    qcNotes.push(provenanceNote);
  }
  const artifact = await saveArtifactVersion({
    projectId,
    stepName: stepId,
    parentArtifactId: selectLatestArtifact(workspace.artifacts, stepId)?.id ?? null,
    title: `${definition.label} v${workspace.artifacts.filter((item) => item.stepName === stepId).length + 1}`,
    contentJson: validated,
    contentMarkdown: formatArtifactToMarkdown(validated),
    qcNotes,
    origin: "ai_generated",
    humanEdited: false,
    status: definition.requiresHumanApproval ? "needs_review" : "done",
    inputArtifactIds: context.inputArtifacts.map((item) => item.id),
    provenance: {
      mode: executionMode,
      modelName,
      note: provenanceNote,
    },
  });
  const tokenEstimate = estimateTokens(prompt.system, prompt.user, JSON.stringify(validated));
  const costEstimateUsd =
    executionMode === "demo_fallback"
      ? 0
      : Number((tokenEstimate / 1_000_000).toFixed(6));

  await recordStepRun({
    id: createId("run"),
    projectId,
    stepName: stepId,
    status: artifact.status,
    version: artifact.version,
    startedAt,
    finishedAt: nowIso(),
    modelName,
    promptSnapshot: prompt,
    inputRefs: {
      artifactIds: context.inputArtifacts.map((item) => item.id),
      uploadIds: context.uploads.map((item) => item.id),
      sourceIds: context.sources.map((item) => item.id),
    },
    outputArtifactId: artifact.id,
    qcStatus: definition.requiresHumanApproval ? "warn" : "pass",
    errorMessage: executionMode === "demo_fallback" ? liveResult.errorNote : null,
    executionMode,
    tokenEstimate,
    costEstimateUsd,
  });

  if (stepId === "evidence_pack") {
    const evidenceContent = validated.content as { sources?: Array<Record<string, unknown>> };
    const sourceCandidates = Array.isArray(evidenceContent.sources) ? evidenceContent.sources : [];
    await syncEvidenceSources(projectId, stepId, sourceCandidates);
  }

  if (isArtifactStale(artifact, [...workspace.artifacts, artifact])) {
    throw new WorkflowError("Generated artifact is already stale against newer upstream inputs.");
  }

  return artifact;
}

export { WorkflowError };
