import type {
  AppStore,
  AuditEvent,
  Artifact,
  CompetitorVideoSignal,
  NewsRadarSource,
  NewsSignal,
  OutputEnvelope,
  Project,
  Source,
  StepId,
  StepRun,
  TopicCandidate,
  Upload,
  User,
} from "@/lib/domain/pipeline";
import { createSourceRef } from "@/lib/citations";

function envelope<T extends Record<string, unknown>>(
  step: StepId,
  summary: string,
  content: T,
  qcNotes: string[] = [],
): OutputEnvelope<T> {
  return {
    step,
    status: "ok",
    confidence: 0.84,
    summary,
    content,
    qc_notes: qcNotes,
  };
}

function artifact(params: {
  id: string;
  projectId: string;
  stepName: StepId;
  version: number;
  status: Artifact["status"];
  origin: Artifact["origin"];
  title: string;
  contentJson: OutputEnvelope;
  contentMarkdown: string;
  qcNotes?: string[];
  approvedByHuman?: boolean;
  approvedByUserId?: string | null;
  parentArtifactId?: string | null;
  humanEdited?: boolean;
  inputArtifactIds?: string[];
  provenance?: Artifact["provenance"];
  createdAt: string;
  updatedAt: string;
}): Artifact {
  const {
    qcNotes = [],
    approvedByHuman = false,
    approvedByUserId = null,
    parentArtifactId = null,
    humanEdited = false,
    inputArtifactIds = [],
    provenance = {
      mode: params.origin === "human_edited" ? "human_edit" : "live_model",
      modelName: params.origin === "human_edited" ? "manual_edit" : "demo-seeded-model",
      note: null,
    },
    ...rest
  } = params;

  return {
    ...rest,
    qcNotes,
    approvedByHuman,
    approvedByUserId,
    parentArtifactId,
    humanEdited,
    inputArtifactIds,
    provenance,
  };
}

function stepRun(params: {
  id: string;
  projectId: string;
  stepName: StepId;
  version: number;
  status: StepRun["status"];
  modelName: string | null;
  promptSnapshot: StepRun["promptSnapshot"];
  inputRefs: StepRun["inputRefs"];
  outputArtifactId: string | null;
  qcStatus: StepRun["qcStatus"];
  startedAt: string;
  finishedAt: string | null;
  errorMessage?: string | null;
  executionMode?: StepRun["executionMode"];
  tokenEstimate?: StepRun["tokenEstimate"];
  costEstimateUsd?: StepRun["costEstimateUsd"];
}): StepRun {
  const {
    errorMessage = null,
    executionMode = params.modelName === "manual_edit" ? "human_edit" : "live_model",
    tokenEstimate = null,
    costEstimateUsd = null,
    ...rest
  } = params;

  return {
    ...rest,
    errorMessage,
    executionMode,
    tokenEstimate,
    costEstimateUsd,
  };
}

export function createSeedStore(): AppStore {
  const users: User[] = [
    {
      id: "user_ira",
      name: "Ira Mikhailova",
      email: "ira@editorial.local",
      role: "producer",
      createdAt: "2026-06-15T09:00:00.000Z",
      updatedAt: "2026-06-15T09:00:00.000Z",
    },
    {
      id: "user_roman",
      name: "Roman Belov",
      email: "roman@editorial.local",
      role: "editor",
      createdAt: "2026-06-15T09:05:00.000Z",
      updatedAt: "2026-06-15T09:05:00.000Z",
    },
    {
      id: "user_maksim",
      name: "Maksim Volkov",
      email: "maksim@editorial.local",
      role: "author",
      createdAt: "2026-06-15T09:10:00.000Z",
      updatedAt: "2026-06-15T09:10:00.000Z",
    },
    {
      id: "user_nadia",
      name: "Nadia Sokolova",
      email: "nadia@editorial.local",
      role: "writer",
      createdAt: "2026-06-15T09:15:00.000Z",
      updatedAt: "2026-06-15T09:15:00.000Z",
    },
  ];

  const projects: Project[] = [
    {
      id: "project_fed",
      title: "Can the Fed Cut Rates Without Breaking Growth?",
      authorName: "Maksim Volkov",
      channelName: "Macro Dispatch",
      status: "in_progress",
      currentStepName: "draft_writer",
      topic: "Will a 2026 Fed easing cycle help or hurt the real economy?",
      deadline: "2026-06-27T12:00:00.000Z",
      createdAt: "2026-06-15T09:00:00.000Z",
      updatedAt: "2026-06-18T08:30:00.000Z",
    },
    {
      id: "project_commodities",
      title: "Why Commodity Inflation Keeps Coming Back",
      authorName: "Anna Lebedeva",
      channelName: "Macro Dispatch",
      status: "in_progress",
      currentStepName: "topic_assessment",
      topic: "The return of commodity inflation and what it means for households",
      deadline: "2026-07-02T12:00:00.000Z",
      createdAt: "2026-06-16T09:00:00.000Z",
      updatedAt: "2026-06-18T09:00:00.000Z",
    },
  ];

  const uploads: Upload[] = [
    {
      id: "upload_fed_brief",
      projectId: "project_fed",
      kind: "brief",
      fileName: "fed-brief.md",
      fileType: "text/markdown",
      pathOrBlobRef: "seed://fed-brief.md",
      extractedText:
        "Author wants a 15-20 minute explainer on whether the first Fed cuts could reignite inflation, create a growth scare, or simply normalize policy. Must include labor and credit context. Avoid doom framing.",
      createdAt: "2026-06-15T09:10:00.000Z",
      updatedAt: "2026-06-15T09:10:00.000Z",
    },
    {
      id: "upload_fed_transcript",
      projectId: "project_fed",
      kind: "transcript",
      fileName: "transcript-growth.txt",
      fileType: "text/plain",
      pathOrBlobRef: "seed://transcript-growth.txt",
      extractedText:
        "Recent channel transcript: the audience responds best when the script starts with a contradiction and then translates jargon into household-level consequences.",
      createdAt: "2026-06-15T09:12:00.000Z",
      updatedAt: "2026-06-15T09:12:00.000Z",
    },
    {
      id: "upload_fed_metrics",
      projectId: "project_fed",
      kind: "metrics",
      fileName: "channel-metrics.csv",
      fileType: "text/csv",
      pathOrBlobRef: "seed://channel-metrics.csv",
      extractedText:
        "Why Inflation Feels Worse Than CPI Says,412000 views,6.8 CTR,08:31 AVD\nWill the ECB Blink First?,188000 views,4.9 CTR,06:12 AVD",
      createdAt: "2026-06-15T09:14:00.000Z",
      updatedAt: "2026-06-15T09:14:00.000Z",
    },
    {
      id: "upload_commodities_brief",
      projectId: "project_commodities",
      kind: "brief",
      fileName: "commodity-brief.md",
      fileType: "text/markdown",
      pathOrBlobRef: "seed://commodity-brief.md",
      extractedText:
        "Need a timely video on commodity inflation. The author wants a fresher angle than a generic inflation explainer and wants concrete examples.",
      createdAt: "2026-06-16T09:10:00.000Z",
      updatedAt: "2026-06-16T09:10:00.000Z",
    },
    {
      id: "upload_commodities_transcript",
      projectId: "project_commodities",
      kind: "transcript",
      fileName: "transcript-energy.txt",
      fileType: "text/plain",
      pathOrBlobRef: "seed://transcript-energy.txt",
      extractedText:
        "Channel transcript excerpt: viewers stay longer when the argument is anchored in one concrete question, then widened into geopolitics and policy choices.",
      createdAt: "2026-06-16T09:12:00.000Z",
      updatedAt: "2026-06-16T09:12:00.000Z",
    },
  ];

  const sources: Source[] = [
    {
      id: "source_fed_labor",
      projectId: "project_fed",
      type: "macro_data",
      title: "Labor market cooling indicators",
      sourceRef: createSourceRef("Labor market cooling indicators"),
      url: "https://example.com/labor",
      sourceDate: "2026-06-10T00:00:00.000Z",
      summary: "Hiring is slowing faster than payroll headlines imply.",
      trustLevel: "high",
      supportedClaims: [
        "Labor softening often appears before headline unemployment spikes.",
        "A first cut can reflect weakening demand rather than pure normalization.",
      ],
      linkedStep: "evidence_pack",
      createdAt: "2026-06-17T09:00:00.000Z",
      updatedAt: "2026-06-17T09:00:00.000Z",
    },
    {
      id: "source_fed_minutes",
      projectId: "project_fed",
      type: "central_bank",
      title: "Fed minutes summary",
      sourceRef: createSourceRef("Fed minutes summary"),
      url: "https://example.com/fed-minutes",
      sourceDate: "2026-06-05T00:00:00.000Z",
      summary: "Committee members are split between inflation persistence and growth downside.",
      trustLevel: "high",
      supportedClaims: [
        "A first cut can happen in soft-landing and stress scenarios.",
        "Policy easing can be either relief or warning depending on the reason for the cut.",
      ],
      linkedStep: "evidence_pack",
      createdAt: "2026-06-17T09:00:00.000Z",
      updatedAt: "2026-06-17T09:00:00.000Z",
    },
    {
      id: "source_commodities_news",
      projectId: "project_commodities",
      type: "news",
      title: "Shipping and food inputs rebound",
      sourceRef: createSourceRef("Shipping and food inputs rebound"),
      url: "https://example.com/commodities",
      sourceDate: "2026-06-12T00:00:00.000Z",
      summary: "Input costs are rising again but unevenly across sectors.",
      trustLevel: "medium",
      supportedClaims: [
        "Commodity inflation is returning unevenly across sectors.",
        "Shipping and food inputs are reintroducing inflation pressure before broad CPI fully reflects it.",
      ],
      linkedStep: "topic_assessment",
      createdAt: "2026-06-17T09:00:00.000Z",
      updatedAt: "2026-06-17T09:00:00.000Z",
    },
  ];

  const artifacts: Artifact[] = [
    artifact({
      id: "artifact_fed_diagnosis_v1",
      projectId: "project_fed",
      stepName: "channel_diagnosis",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Channel Diagnosis v1",
      contentJson: envelope("channel_diagnosis", "The channel wins when it frames macro stories as felt tradeoffs, not forecasts.", {
        winning_topics: ["Inflation contradictions", "Central bank dilemmas", "Household consequences"],
        weak_topics: ["Pure market recaps", "Jargon-heavy policy lectures"],
        tone_profile: "Calm, skeptical, analytical, conversational",
        complexity_level: "Intermediate",
        retention_patterns: ["Strong first 90 seconds when conflict is explicit", "Drop-off on long background sections"],
        title_patterns: ["Question-led titles", "Contradiction-based hooks"],
        risks: ["Jargon creep", "Too many caveats upfront"],
        recommendations: ["Lead with a macro paradox", "Translate policy into wage, loan, and prices consequences early"],
      }),
      contentMarkdown:
        "# Channel Diagnosis\n\nThe audience rewards analytical clarity when the script opens with a contradiction they can feel.\n\n- Winning topics: inflation contradictions, policy dilemmas, household consequences\n- Weak topics: market-only coverage, jargon-heavy explainers\n- Risk: background sections get too abstract too early",
      createdAt: "2026-06-16T08:00:00.000Z",
      updatedAt: "2026-06-16T08:00:00.000Z",
    }),
    artifact({
      id: "artifact_fed_audience_v1",
      projectId: "project_fed",
      stepName: "audience_hypothesis",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Audience Hypothesis v1",
      contentJson: envelope("audience_hypothesis", "Core viewers are curious non-specialists who want macro explained without being talked down to.", {
        segments: ["Professionals tracking cost of living", "Finance-adjacent viewers", "Curious generalists"],
        knowledge_level: "Informed non-specialist",
        core_pains: ["News feels contradictory", "Too much jargon", "Hard to connect policy to daily life"],
        desires: ["Clear big-picture explanation", "Confidence about what matters", "Actionable mental models"],
        trigger_topics: ["Inflation", "Rates", "Housing", "Recession risk"],
        objection_patterns: ["Sounds too abstract", "Feels recycled"],
        preferred_explanation_style: "One sharp question, plain language, layered complexity",
        attention_profile: "High if tension is sustained; low tolerance for slow warm-up",
      }),
      contentMarkdown:
        "# Audience Hypothesis\n\nThe sweet spot is an informed audience that wants rigorous reasoning without lecture-mode delivery.\n\n- Knowledge level: informed non-specialist\n- Key need: connect policy to concrete consequences\n- Attention profile: fast hook, escalating stakes, minimal fluff",
      createdAt: "2026-06-16T08:30:00.000Z",
      updatedAt: "2026-06-16T08:30:00.000Z",
    }),
    artifact({
      id: "artifact_fed_brief_v1",
      projectId: "project_fed",
      stepName: "brief_parsing",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Brief Parsing v1",
      contentJson: envelope("brief_parsing", "The brief asks for a timely but measured take on the first Fed cuts and real-economy consequences.", {
        requested_topic: "Whether Fed cuts help growth or reignite inflation",
        core_thesis: "The first cut matters less than the reason behind it.",
        desired_outcome: "Viewer should understand why the first cut can signal either relief or weakness.",
        author_intent: "Measured, analytical, not alarmist",
        constraints: ["15-20 minutes", "Timely", "Avoid doom rhetoric"],
        must_include: ["Labor context", "Credit conditions", "Inflation path"],
        must_avoid: ["Binary hot-take framing", "Speculative market calls"],
        ambiguities: ["How much market commentary the author wants"],
      }),
      contentMarkdown:
        "# Brief Parsing\n\nThe brief is strong but needs one sharper editorial question before drafting starts.\n\n- Main thesis: the first cut matters less than the reason for it\n- Must include: labor, credit, inflation\n- Ambiguity: how much market reaction coverage belongs in the script",
      qcNotes: ["Brief does not specify whether equity-market reactions should be part of the narrative."],
      createdAt: "2026-06-16T09:00:00.000Z",
      updatedAt: "2026-06-16T09:00:00.000Z",
    }),
    artifact({
      id: "artifact_fed_topic_v1",
      projectId: "project_fed",
      stepName: "topic_assessment",
      version: 1,
      status: "needs_review",
      origin: "ai_generated",
      title: "Topic Assessment v1",
      contentJson: envelope("topic_assessment", "Topic fits the channel, but the strongest version focuses on why the first cut can mean opposite things.", {
        verdict: "go",
        fit_score: 0.91,
        why_now_score: 0.88,
        novelty_score: 0.72,
        risk_score: 0.29,
        problems: ["Generic rate-cut optimism framing feels tired"],
        pivot_options: ["Frame around what the first cut reveals", "Compare normalization cuts vs panic cuts"],
        recommended_direction: "Anchor the story in the contradiction that easier policy can be either relief or warning.",
      }),
      contentMarkdown:
        "# Topic Assessment\n\nRecommendation: proceed, but avoid generic rate-cut optimism framing.\n\n- Verdict: go\n- Best angle: what the first cut reveals, not whether cuts are good\n- Main risk: novelty collapses if the topic stays too broad",
      qcNotes: ["Needs human approval before editorial angle is generated."],
      createdAt: "2026-06-16T10:00:00.000Z",
      updatedAt: "2026-06-16T10:00:00.000Z",
    }),
    artifact({
      id: "artifact_fed_topic_v2",
      projectId: "project_fed",
      stepName: "topic_assessment",
      version: 2,
      status: "approved",
      origin: "human_edited",
      title: "Topic Assessment v2",
      contentJson: envelope("topic_assessment", "Approved direction narrows the topic to the meaning of the first cut rather than a generic policy explainer.", {
        verdict: "go",
        fit_score: 0.93,
        why_now_score: 0.89,
        novelty_score: 0.78,
        risk_score: 0.27,
        problems: ["Keep the market tangent short"],
        pivot_options: ["Use yield-curve context only as supporting evidence"],
        recommended_direction: "Build the script around the question: if the Fed cuts first, what problem is it responding to?",
      }),
      contentMarkdown:
        "# Topic Assessment\n\nApproved editorial constraint: decode the signal behind the first cut, not the cut itself.\n\n- Verdict: go\n- Keep market tangent short\n- Use household impact as proof, not the main frame",
      qcNotes: ["Approved by producer after narrowing the scope."],
      approvedByHuman: true,
      approvedByUserId: "user_ira",
      parentArtifactId: "artifact_fed_topic_v1",
      humanEdited: true,
      createdAt: "2026-06-16T11:00:00.000Z",
      updatedAt: "2026-06-16T11:15:00.000Z",
    }),
    artifact({
      id: "artifact_fed_evidence_v1",
      projectId: "project_fed",
      stepName: "evidence_pack",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Evidence Pack v1",
      contentJson: envelope("evidence_pack", "The fact base is sufficient for outlining and drafting, though inflation persistence still needs careful phrasing.", {
        key_facts: ["A first cut can happen in soft-landing and stress scenarios", "Labor softening often appears before headline unemployment spikes"],
        data_points: ["Credit card delinquencies trending higher", "Business hiring intentions cooling"],
        current_news: ["Recent Fed minutes show a split committee"],
        historical_parallels: ["1995 normalization vs 2001 stress response"],
        expert_positions: ["Doves emphasize growth insurance", "Hawks emphasize sticky inflation"],
        counterarguments: ["Markets may overread one cut", "Inflation can reaccelerate even with slowing growth"],
        open_questions: ["How much household balance-sheet stress to emphasize"],
        sources: [
          {
            title: "Labor market cooling indicators",
            source_ref: createSourceRef("Labor market cooling indicators"),
            trust_level: "high",
            supported_claims: [
              "Labor softening often appears before headline unemployment spikes.",
              "A first cut can reflect weakening demand rather than pure normalization.",
            ],
          },
          {
            title: "Fed minutes summary",
            source_ref: createSourceRef("Fed minutes summary"),
            trust_level: "high",
            supported_claims: [
              "A first cut can happen in soft-landing and stress scenarios.",
              "Policy easing can be either relief or warning depending on the reason for the cut.",
            ],
          },
        ],
      }),
      contentMarkdown:
        "# Evidence Pack\n\nEnough evidence is assembled to support the outline and the coming draft.\n\n- Historical anchor: 1995 vs 2001\n- Current context: split Fed and softening labor\n- Watchout: avoid overstating sticky inflation claims",
      qcNotes: ["Inflation persistence claims should be sourced explicitly in final draft."],
      createdAt: "2026-06-16T12:00:00.000Z",
      updatedAt: "2026-06-16T12:00:00.000Z",
    }),
    artifact({
      id: "artifact_fed_angle_v1",
      projectId: "project_fed",
      stepName: "editorial_angle",
      version: 1,
      status: "approved",
      origin: "human_edited",
      title: "Editorial Angle v1",
      contentJson: envelope("editorial_angle", "The strongest promise is to teach viewers why the first Fed cut can be reassuring and alarming at the same time.", {
        core_question: "If the Fed cuts first, is that good news or a warning sign?",
        central_conflict: "Cheaper money sounds positive, but the reason for the cut may reveal hidden weakness.",
        hook_options: [
          "The first Fed cut can make markets cheer for the wrong reason.",
          "A rate cut is supposed to feel like relief. So why can it be a bad sign?",
        ],
        viewer_promise: "You will understand what the first cut is really signaling about growth, inflation, and your own finances.",
        emotional_frame: "Curious skepticism",
        why_this_matters_now: "Markets obsess over the cut itself, while viewers need the context that explains whether it means relief or trouble.",
        chosen_angle: "Decode the signal behind the first cut.",
        rejected_angles: ["Pure market reaction explainer", "Fed 101 background lesson"],
      }),
      contentMarkdown:
        "# Editorial Angle\n\nChosen angle: decode the signal behind the first cut and why the same policy move can mean two different stories.\n\n- Core question: good news or warning sign?\n- Emotional frame: skeptical, not apocalyptic\n- Rejected angles: generic Fed explainer, market-only framing",
      qcNotes: ["Approved after tightening the promise in the opening 60 seconds."],
      approvedByHuman: true,
      approvedByUserId: "user_ira",
      humanEdited: true,
      createdAt: "2026-06-17T08:00:00.000Z",
      updatedAt: "2026-06-17T08:20:00.000Z",
    }),
    artifact({
      id: "artifact_fed_outline_v1",
      projectId: "project_fed",
      stepName: "script_outline",
      version: 1,
      status: "needs_review",
      origin: "ai_generated",
      title: "Script Outline v1",
      contentJson: envelope("script_outline", "Outline is structurally strong but needs a sharper midpoint transition into labor and credit evidence.", {
        hook: "Why can the same rate cut feel like relief and danger at once?",
        blocks: [
          "Open on the paradox",
          "Explain why markets cheer rate cuts",
          "Show why the reason for the cut matters more",
          "Move into labor and credit evidence",
          "Compare normalization vs panic cuts",
          "Land on what viewers should watch next",
        ],
        transitions: ["From market reaction to economic signal", "From policy theory to labor and credit evidence"],
        midpoint_shift: "The cut itself stops being the story; the hidden weakness becomes the story.",
        climax: "Reveal the tests that distinguish a healthy normalization cut from a stress cut.",
        ending: "Leave the audience with a checklist for interpreting the next Fed move.",
        est_duration_min: 17,
        block_goals: ["Earn attention with a contradiction", "Reframe viewer intuition", "Support argument with evidence", "Deliver a durable mental model"],
      }),
      contentMarkdown:
        "# Script Outline\n\nThe outline has the right spine and needs one editorial pass on the evidence transition.\n\n- Estimated length: 17 minutes\n- Midpoint shift: the cut is not the point; the reason is\n- Main fix: stronger bridge into labor and credit data",
      qcNotes: ["Needs approval before drafting."],
      createdAt: "2026-06-17T09:00:00.000Z",
      updatedAt: "2026-06-17T09:00:00.000Z",
    }),
    artifact({
      id: "artifact_fed_outline_v2",
      projectId: "project_fed",
      stepName: "script_outline",
      version: 2,
      status: "approved",
      origin: "human_edited",
      title: "Script Outline v2",
      contentJson: envelope("script_outline", "Approved outline strengthens the turn from policy theory into real-economy evidence.", {
        hook: "A rate cut should feel like good news. So why can it also be a warning flare?",
        blocks: [
          "Hook with the false comfort of a cut",
          "Explain the intuitive bullish story",
          "Flip the frame: the cut reveals what is breaking",
          "Test the economy through labor, credit, and inflation",
          "Compare two historical types of first cuts",
          "Finish with a viewer checklist",
        ],
        transitions: ["From what people assume to what the Fed is responding to", "From abstract policy to labor, credit, and pricing evidence"],
        midpoint_shift: "The viewer stops asking whether cuts are good and starts asking why the Fed needed one.",
        climax: "The historical comparison shows that identical cuts can imply opposite economic realities.",
        ending: "A checklist: labor cooling, credit stress, and inflation persistence.",
        est_duration_min: 18,
        block_goals: ["Hook the paradox", "Reverse the default interpretation", "Ground the argument in evidence", "Leave the audience with a diagnostic framework"],
      }),
      contentMarkdown:
        "# Script Outline\n\nApproved structure tightens the evidence handoff and gives the ending a stronger practical checklist.\n\n- Estimated length: 18 minutes\n- Climax: identical cuts can signal opposite realities\n- Ending: labor, credit, inflation checklist",
      qcNotes: ["Approved after manual rewrite of the midpoint bridge."],
      approvedByHuman: true,
      approvedByUserId: "user_ira",
      parentArtifactId: "artifact_fed_outline_v1",
      humanEdited: true,
      createdAt: "2026-06-17T09:30:00.000Z",
      updatedAt: "2026-06-17T09:45:00.000Z",
    }),
    artifact({
      id: "artifact_commodities_diagnosis_v1",
      projectId: "project_commodities",
      stepName: "channel_diagnosis",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Channel Diagnosis v1",
      contentJson: envelope("channel_diagnosis", "The audience responds when invisible macro pressure becomes visible in daily life.", {
        winning_topics: ["Cost-of-living contradictions", "Policy pressure points"],
        weak_topics: ["Broad market recaps"],
        tone_profile: "Measured and explanatory",
        complexity_level: "Intermediate",
        retention_patterns: ["Hooks that start with a household effect outperform abstract openings"],
        title_patterns: ["Question-led, consequence-focused"],
        risks: ["Too many caveats"],
        recommendations: ["Open with one concrete symptom before zooming out"],
      }),
      contentMarkdown:
        "# Channel Diagnosis\n\nThe audience responds when invisible macro pressure becomes visible in daily life.\n\n- Lead with household symptom\n- Avoid broad market summary openings",
      createdAt: "2026-06-17T08:00:00.000Z",
      updatedAt: "2026-06-17T08:00:00.000Z",
    }),
    artifact({
      id: "artifact_commodities_audience_v1",
      projectId: "project_commodities",
      stepName: "audience_hypothesis",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Audience Hypothesis v1",
      contentJson: envelope("audience_hypothesis", "Viewers want a fresh inflation frame rather than another CPI explainer.", {
        segments: ["Curious household-budget viewers", "Policy-aware generalists"],
        knowledge_level: "Beginner to intermediate",
        core_pains: ["Inflation stories feel repetitive"],
        desires: ["Fresh angles and concrete examples"],
        trigger_topics: ["Food", "Energy", "Shipping", "Wages"],
        objection_patterns: ["Too abstract", "Too repetitive"],
        preferred_explanation_style: "Concrete first, systems second",
        attention_profile: "Needs novelty early",
      }),
      contentMarkdown:
        "# Audience Hypothesis\n\nThe viewer is not asking what inflation is. They are asking why it keeps returning in new forms.\n\n- Novelty is essential\n- Concrete examples should come first",
      createdAt: "2026-06-17T08:30:00.000Z",
      updatedAt: "2026-06-17T08:30:00.000Z",
    }),
    artifact({
      id: "artifact_commodities_brief_v1",
      projectId: "project_commodities",
      stepName: "brief_parsing",
      version: 1,
      status: "done",
      origin: "ai_generated",
      title: "Brief Parsing v1",
      contentJson: envelope("brief_parsing", "The brief clearly asks for a sharper angle than a generic inflation explainer, but the thesis still needs narrowing.", {
        requested_topic: "Commodity inflation resurgence",
        core_thesis: "Commodity inflation is returning unevenly and may hit households before headline CPI fully reflects it.",
        desired_outcome: "Viewers understand why commodity inflation can return in waves.",
        author_intent: "Surprising but practical",
        constraints: ["Timely", "Avoid generic inflation explainer"],
        must_include: ["Concrete examples", "Why-now argument"],
        must_avoid: ["Textbook intro"],
        ambiguities: ["Which commodity buckets matter most", "How global the scope should be"],
      }),
      contentMarkdown:
        "# Brief Parsing\n\nThe brief is directionally strong but still too broad for editorial approval.\n\n- Need a narrower thesis\n- Need a sharper why-now case",
      qcNotes: ["Topic assessment should decide whether the script centers on food, energy, or shipping."],
      createdAt: "2026-06-17T09:00:00.000Z",
      updatedAt: "2026-06-17T09:00:00.000Z",
    }),
  ];

  const stepRuns: StepRun[] = artifacts.map((item) =>
    stepRun({
      id: `run_${item.id}`,
      projectId: item.projectId,
      stepName: item.stepName,
      version: item.version,
      status: item.status,
      modelName: item.origin === "ai_generated" ? "demo-seeded-model" : "manual_edit",
      promptSnapshot: {
        system: `Seeded system prompt for ${item.stepName}`,
        user: "Demo store record",
      },
      inputRefs: {
        artifactIds: [],
        uploadIds: uploads.filter((upload) => upload.projectId === item.projectId).map((upload) => upload.id),
        sourceIds: sources.filter((source) => source.projectId === item.projectId).map((source) => source.id),
      },
      outputArtifactId: item.id,
      qcStatus: item.approvedByHuman ? "approved" : "pass",
      startedAt: item.createdAt,
      finishedAt: item.updatedAt,
    }),
  );

  const radarSources: NewsRadarSource[] = [
    {
      id: "radar_fed",
      label: "Federal Reserve",
      category: "official",
      url: "https://www.federalreserve.gov/feeds/press_all.xml",
      trustLevel: "high",
      region: "US",
      enabled: true,
    },
    {
      id: "radar_ecb",
      label: "European Central Bank",
      category: "official",
      url: "https://www.ecb.europa.eu/rss/press.html",
      trustLevel: "high",
      region: "EU",
      enabled: true,
    },
    {
      id: "radar_imf",
      label: "IMF",
      category: "official",
      url: "https://www.imf.org/en/News/RSS",
      trustLevel: "high",
      region: "Global",
      enabled: true,
    },
    {
      id: "radar_bis",
      label: "BIS",
      category: "research",
      url: "https://www.bis.org/list/pressreleases/index.rss",
      trustLevel: "high",
      region: "Global",
      enabled: true,
    },
  ];

  const newsSignals: NewsSignal[] = [
    {
      id: "signal_1",
      sourceId: "radar_fed",
      sourceLabel: "Federal Reserve",
      title: "Officials signal caution on inflation persistence despite softer growth pockets",
      url: "https://example.com/fed-signal",
      summary: "The message is not simply about rates, but about whether growth is weakening faster than inflation is cooling.",
      publishedAt: "2026-06-17T08:00:00.000Z",
      tags: ["rates", "inflation", "growth", "fed"],
      clusterKey: "rates-signal-vs-weakness",
      authorityScore: 0.96,
    },
    {
      id: "signal_2",
      sourceId: "radar_ecb",
      sourceLabel: "European Central Bank",
      title: "ECB comments reinforce split between disinflation progress and fragile demand",
      url: "https://example.com/ecb-signal",
      summary: "European commentary sharpens the same tension between easing policy and weak underlying demand.",
      publishedAt: "2026-06-16T11:00:00.000Z",
      tags: ["rates", "demand", "europe", "inflation"],
      clusterKey: "rates-signal-vs-weakness",
      authorityScore: 0.92,
    },
    {
      id: "signal_3",
      sourceId: "radar_imf",
      sourceLabel: "IMF",
      title: "Global trade frictions raise the risk of renewed goods inflation",
      url: "https://example.com/imf-trade",
      summary: "The inflation story is reappearing through trade, logistics, and geopolitical channels rather than broad overheating.",
      publishedAt: "2026-06-17T10:00:00.000Z",
      tags: ["trade", "inflation", "geopolitics", "shipping"],
      clusterKey: "trade-frictions-renew-goods-inflation",
      authorityScore: 0.9,
    },
    {
      id: "signal_4",
      sourceId: "radar_bis",
      sourceLabel: "BIS",
      title: "Credit conditions suggest hidden strain beneath stable headline markets",
      url: "https://example.com/bis-credit",
      summary: "A divergence is opening between calm asset pricing and more fragile real-economy financing conditions.",
      publishedAt: "2026-06-15T13:00:00.000Z",
      tags: ["credit", "banking", "markets", "growth"],
      clusterKey: "credit-strain-under-calm-markets",
      authorityScore: 0.91,
    },
  ];

  const topicCandidates: TopicCandidate[] = [
    {
      id: "candidate_1",
      title: "Почему первое снижение ставки может быть плохой новостью",
      angle: "Не обсуждать сам cut, а разобрать, какую скрытую слабость он может сигнализировать.",
      summary: "Несколько источников сходятся в одном противоречии: мягче политика не всегда значит сильнее экономика.",
      whyNow: "Тема одновременно поддержана центральными банками и уже понятна широкой аудитории по боли вокруг ставок и роста.",
      youtubePotentialScore: 91,
      viralityScore: 89,
      evidenceStrength: 88,
      noveltyScore: 79,
      momentumScore: 86,
      competitorMomentumScore: 88,
      macroRelevanceScore: 93,
      competitionPressure: 72,
      monetizationFitScore: 90,
      timingWindowDays: 7,
      productionEffort: "medium",
      decision: "shoot_now",
      packagingHooks: [
        "Снижение ставки как плохая новость",
        "Рынок радуется не тому сигналу",
      ],
      economics: {
        researchCostUsd: 28,
        scriptingCostUsd: 24,
        totalCostUsd: 52,
        breakEvenViews: 26000,
      },
      recommendedFormat: "Question-led explainer with contradiction hook",
      status: "hot",
      clusterKey: "rates-signal-vs-weakness",
      signalIds: ["signal_1", "signal_2"],
      tags: ["rates", "inflation", "growth", "central banks"],
      createdAt: "2026-06-18T08:00:00.000Z",
      updatedAt: "2026-06-18T08:00:00.000Z",
    },
    {
      id: "candidate_2",
      title: "Возвращается ли инфляция через торговые войны и логистику",
      angle: "Не общий ролик про CPI, а история про новый канал инфляции: trade friction, shipping, geopolitics.",
      summary: "Вместо очередной абстрактной инфляции можно собрать конкретную тему про возврат goods inflation через мировые цепочки.",
      whyNow: "Геополитика делает тему и экономической, и политической одновременно.",
      youtubePotentialScore: 87,
      viralityScore: 84,
      evidenceStrength: 84,
      noveltyScore: 82,
      momentumScore: 79,
      competitorMomentumScore: 76,
      macroRelevanceScore: 89,
      competitionPressure: 61,
      monetizationFitScore: 86,
      timingWindowDays: 10,
      productionEffort: "medium",
      decision: "shoot_now",
      packagingHooks: [
        "Инфляция возвращается не через спрос, а через торговлю",
        "Новый канал роста цен, который все пропускают",
      ],
      economics: {
        researchCostUsd: 32,
        scriptingCostUsd: 24,
        totalCostUsd: 56,
        breakEvenViews: 28000,
      },
      recommendedFormat: "Why-now breakdown with concrete product examples",
      status: "hot",
      clusterKey: "trade-frictions-renew-goods-inflation",
      signalIds: ["signal_3"],
      tags: ["inflation", "trade", "shipping", "geopolitics"],
      createdAt: "2026-06-18T08:05:00.000Z",
      updatedAt: "2026-06-18T08:05:00.000Z",
    },
    {
      id: "candidate_3",
      title: "Почему рынки спокойны, если кредит уже трещит",
      angle: "Построить ролик на расхождении между спокойными headline-маркетами и скрытым напряжением в кредитном контуре.",
      summary: "Это сильная редакторская тема, если нужна более взрослая, чуть менее массовая история.",
      whyNow: "Поддерживается качественными источниками, но требует чуть более аккуратной упаковки для массового YouTube.",
      youtubePotentialScore: 76,
      viralityScore: 67,
      evidenceStrength: 85,
      noveltyScore: 83,
      momentumScore: 68,
      competitorMomentumScore: 58,
      macroRelevanceScore: 87,
      competitionPressure: 44,
      monetizationFitScore: 73,
      timingWindowDays: 12,
      productionEffort: "high",
      decision: "hold_watch",
      packagingHooks: [
        "Рынки спокойны, но кредит уже сжимается",
        "Почему настоящая слабость пока не в headline",
      ],
      economics: {
        researchCostUsd: 38,
        scriptingCostUsd: 27,
        totalCostUsd: 65,
        breakEvenViews: 32500,
      },
      recommendedFormat: "Signal-decoding explainer for advanced audience",
      status: "watch",
      clusterKey: "credit-strain-under-calm-markets",
      signalIds: ["signal_4"],
      tags: ["credit", "banking", "markets"],
      createdAt: "2026-06-18T08:10:00.000Z",
      updatedAt: "2026-06-18T08:10:00.000Z",
    },
  ];

  const competitorSignals: CompetitorVideoSignal[] = [
    {
      id: "competitor_1",
      channelName: "MacroScope",
      title: "The Fed Cut Everyone Is Misreading",
      url: "https://youtube.com/watch?v=example1",
      publishedAt: "2026-06-07T12:00:00.000Z",
      topicLabel: "Rates as warning signal",
      views: 412000,
      viewsPerDay: 37454,
      performanceBand: "breakout",
      notes: "Strong contradiction title and clear why-now framing.",
    },
    {
      id: "competitor_2",
      channelName: "Econ Frontline",
      title: "Why Goods Inflation Could Return Fast",
      url: "https://youtube.com/watch?v=example2",
      publishedAt: "2026-06-10T12:00:00.000Z",
      topicLabel: "Trade and goods inflation",
      views: 198000,
      viewsPerDay: 24750,
      performanceBand: "strong",
      notes: "Concrete examples carried the click and retention promise.",
    },
    {
      id: "competitor_3",
      channelName: "Policy Ledger",
      title: "Credit Stress Nobody Wants to Talk About",
      url: "https://youtube.com/watch?v=example3",
      publishedAt: "2026-06-09T12:00:00.000Z",
      topicLabel: "Hidden credit strain",
      views: 71000,
      viewsPerDay: 8875,
      performanceBand: "baseline",
      notes: "Smart topic, but more niche packaging.",
    },
  ];

  const auditEvents: AuditEvent[] = [
    {
      id: "audit_project_fed_created",
      projectId: "project_fed",
      artifactId: null,
      stepRunId: null,
      actorUserId: "user_ira",
      type: "project_created",
      message: "Project created for Fed easing cycle coverage.",
      metadata: {
        currentStepName: "draft_writer",
      },
      createdAt: "2026-06-15T09:00:00.000Z",
    },
    {
      id: "audit_project_fed_topic_approved",
      projectId: "project_fed",
      artifactId: "artifact_fed_topic_v2",
      stepRunId: null,
      actorUserId: "user_ira",
      type: "artifact_approved",
      message: "Topic Assessment approved after narrowing the editorial direction.",
      metadata: {
        stepName: "topic_assessment",
        version: 2,
      },
      createdAt: "2026-06-16T11:15:00.000Z",
    },
    {
      id: "audit_project_fed_outline_saved",
      projectId: "project_fed",
      artifactId: "artifact_fed_outline_v2",
      stepRunId: null,
      actorUserId: "user_roman",
      type: "artifact_saved",
      message: "Outline revised to strengthen the midpoint transition.",
      metadata: {
        stepName: "script_outline",
        version: 2,
        humanEdited: true,
      },
      createdAt: "2026-06-17T09:45:00.000Z",
    },
  ];

  return {
    users,
    activeUserId: "user_ira",
    projects,
    stepRuns,
    artifacts,
    sources,
    uploads,
    radarSources,
    newsSignals,
    topicCandidates,
    competitorSignals,
    auditEvents,
  };
}
