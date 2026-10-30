import { cookies } from "next/headers";
import type { Artifact, CompetitorVideoSignal, StepId, StepStatus, TopicCandidate, Upload, UserRole } from "@/lib/domain/pipeline";

export const LOCALE_COOKIE = "ike_locale";
export const LOCALES = ["en", "ru"] as const;
export type Locale = (typeof LOCALES)[number];

function isLocale(value: string): value is Locale {
  return LOCALES.includes(value as Locale);
}

export function resolveLocale(value: string | null | undefined, fallback: Locale = "ru"): Locale {
  return value && isLocale(value) ? value : fallback;
}

export async function getLocaleFromCookies(): Promise<Locale> {
  const store = await cookies();
  const value = store.get(LOCALE_COOKIE)?.value;
  return resolveLocale(value);
}

export function withLang(returnTo: string, locale: Locale) {
  const [pathname, query = ""] = returnTo.split("?");
  const params = new URLSearchParams(query);
  params.set("lang", locale);
  const serialized = params.toString();
  return serialized ? `${pathname}?${serialized}` : pathname;
}

const messages = {
  en: {
    ikeWorkspace: "Ike Workspace",
    editorialPipelineHeadline: "Editorial pipeline for macro YouTube scripts",
    editorialPipelineSubtitle:
      "Not a chat. Each AI step creates its own versioned artifact, supports manual review, and moves forward only when the team says it should.",
    projects: "Projects",
    artifacts: "Artifacts",
    signals: "Signals",
    pipeline: "Pipeline",
    openTopicRadar: "Open Topic Radar",
    newProject: "New Project",
    startFreshPipeline: "Start a fresh editorial pipeline",
    projectTitle: "Project title",
    authorName: "Author name",
    channelName: "Channel name",
    deadline: "Deadline",
    topic: "Topic",
    createProject: "Create Project",
    creating: "Creating...",
    resetDemoData: "Reset demo data",
    author: "Author",
    currentStep: "Current Step",
    updated: "Updated",
    openProject: "Open project",
    duplicate: "Duplicate",
    duplicating: "Duplicating...",
    delete: "Delete",
    deleting: "Deleting...",
    allProjects: "All Projects",
    channel: "Channel",
    generationTrace: "Generation Trace",
    model: "Model",
    tokens: "Tokens",
    costEstimate: "Cost est.",
    structuredView: "Structured View",
    readableDocument: "Readable Document",
    artifactTitle: "Artifact title",
    structuredJson: "Structured JSON",
    markdownDocument: "Markdown document",
    qcNotes: "QC notes",
    saveDraft: "Save Draft",
    saving: "Saving...",
    regenerate: "Regenerate",
    noArtifactYet: "No artifact exists for this step yet.",
    generationHelp:
      "Run generation when the upstream inputs are ready. The result will be stored as a separate versioned document, not a chat message.",
    generate: "Generate",
    generating: "Generating...",
    approve: "Approve",
    approving: "Approving...",
    resolveUpstreamChanges: "Resolve Upstream Changes",
    sendToNextStep: "Send to Next Step",
    sending: "Sending...",
    requestRevision: "Request Revision",
    updating: "Updating...",
    cannotApprove: "cannot approve this step.",
    revisionPlaceholder: "Revision note for this artifact",
    versionHistory: "Version History",
    noVersionsYet: "No versions yet.",
    projectControls: "Project Controls",
    criticalApprovals: "Critical approvals",
    humanEdits: "Human edits",
    sources: "Sources",
    staleSources: "Stale sources",
    controlChecklist: "Control checklist",
    brief: "Brief",
    transcript: "Transcript",
    metrics: "Metrics",
    staleDownstreamArtifacts: "Stale downstream artifacts",
    demoFallbackArtifacts: "Demo fallback artifacts",
    finalQcApproved: "Final QC approved",
    present: "present",
    missing: "missing",
    yes: "yes",
    no: "no",
    currentGaps: "Current gaps",
    noMajorControlGaps: "No major control gaps detected.",
    inputArtifacts: "Input Artifacts",
    noUpstreamArtifacts: "No upstream artifacts for this step.",
    uploads: "Uploads",
    notes: "Notes",
    material: "Material",
    uploadMaterial: "Upload Material",
    uploading: "Uploading...",
    noStoredSources: "No stored sources for this project yet.",
    noQcNotes: "No QC notes yet.",
    auditTrail: "Audit Trail",
    system: "System",
    unknownUser: "Unknown user",
    noAuditEvents: "No audit events recorded yet.",
    actingUser: "Acting user",
    switchSession: "Switch Session",
    switching: "Switching...",
    language: "Language",
    backToProjects: "Back to projects",
    topicRadar: "Topic Radar",
    topicRadarSubtitle:
      "Curated macro news ingestion from authoritative sources, aggregated into potential YouTube topics instead of duplicate headline walls.",
    refreshRadar: "Refresh Radar",
    refreshing: "Refreshing...",
    hotTopics: "Hot Topics",
    curatedSources: "Curated Sources",
    rawSignals: "Raw Signals",
    cluster: "Cluster",
    competitorMomentum: "Competitor Momentum",
    competitorHelp:
      "Lightweight signal only: what topics already showed breakout or strong view velocity in the last two weeks.",
    views: "views",
    perDay: "per day",
    commercialSnapshot: "Commercial Snapshot",
    shootNow: "Shoot now",
    avgCost: "Avg cost",
    avgBreakEven: "Avg break-even",
    topScore: "Top score",
    commercialHelp:
      "Use this as a triage layer: launch `shoot now` ideas first, then feed only approved candidates into the script pipeline.",
    topicCandidate: "Topic Candidate",
    recommendedAngle: "Recommended angle",
    youtubePotential: "YouTube Potential",
    momentum: "Momentum",
    evidence: "Evidence",
    novelty: "Novelty",
    virality: "Virality",
    competition: "Competition",
    competitorLift: "Competitor lift",
    decision: "Decision",
    window: "Window",
    days: "days",
    effort: "Effort",
    unitEconomics: "Unit Economics",
    cost: "Cost",
    breakEven: "Break-even",
    monetizationFit: "Monetization fit",
    whyNow: "Why now",
    updatedLabel: "Updated",
    packagingHooks: "Packaging Hooks",
    createProjectFromTopic: "Create Project From Topic",
    backToPipeline: "Back to pipeline",
    versions: "Versions",
    provenance: "Provenance",
    readableMarkdown: "Readable Markdown",
  },
  ru: {
    ikeWorkspace: "Ike Workspace",
    editorialPipelineHeadline: "Редакторский пайплайн для макроэкономических YouTube-сценариев",
    editorialPipelineSubtitle:
      "Это не чат. Каждый AI-шаг создает отдельный версионируемый артефакт, поддерживает ручную проверку и двигается дальше только после решения команды.",
    projects: "Проекты",
    artifacts: "Артефакты",
    signals: "Сигналы",
    pipeline: "Пайплайн",
    openTopicRadar: "Открыть Topic Radar",
    newProject: "Новый проект",
    startFreshPipeline: "Запустить новый редакторский пайплайн",
    projectTitle: "Название проекта",
    authorName: "Имя автора",
    channelName: "Название канала",
    deadline: "Дедлайн",
    topic: "Тема",
    createProject: "Создать проект",
    creating: "Создание...",
    resetDemoData: "Сбросить демо-данные",
    author: "Автор",
    currentStep: "Текущий шаг",
    updated: "Обновлено",
    openProject: "Открыть проект",
    duplicate: "Дублировать",
    duplicating: "Дублирование...",
    delete: "Удалить",
    deleting: "Удаление...",
    allProjects: "Все проекты",
    channel: "Канал",
    generationTrace: "Трассировка генерации",
    model: "Модель",
    tokens: "Токены",
    costEstimate: "Оценка стоимости",
    structuredView: "Структурированный вид",
    readableDocument: "Читаемый документ",
    artifactTitle: "Название артефакта",
    structuredJson: "Структурированный JSON",
    markdownDocument: "Markdown-документ",
    qcNotes: "QC-заметки",
    saveDraft: "Сохранить черновик",
    saving: "Сохранение...",
    regenerate: "Перегенерировать",
    noArtifactYet: "Для этого шага пока нет артефакта.",
    generationHelp:
      "Запусти генерацию, когда будут готовы входные данные. Результат сохранится как отдельный версионируемый документ, а не как сообщение чата.",
    generate: "Сгенерировать",
    generating: "Генерация...",
    approve: "Утвердить",
    approving: "Утверждение...",
    resolveUpstreamChanges: "Разобрать upstream-изменения",
    sendToNextStep: "Отправить на следующий шаг",
    sending: "Отправка...",
    requestRevision: "Запросить доработку",
    updating: "Обновление...",
    cannotApprove: "не может утвердить этот шаг.",
    revisionPlaceholder: "Комментарий к доработке этого артефакта",
    versionHistory: "История версий",
    noVersionsYet: "Версий пока нет.",
    projectControls: "Контроли проекта",
    criticalApprovals: "Критичные утверждения",
    humanEdits: "Ручные правки",
    sources: "Источники",
    staleSources: "Устаревшие источники",
    controlChecklist: "Контрольный список",
    brief: "Бриф",
    transcript: "Транскрипт",
    metrics: "Метрики",
    staleDownstreamArtifacts: "Устаревшие downstream-артефакты",
    demoFallbackArtifacts: "Артефакты demo fallback",
    finalQcApproved: "Final QC утвержден",
    present: "есть",
    missing: "нет",
    yes: "да",
    no: "нет",
    currentGaps: "Текущие пробелы",
    noMajorControlGaps: "Критичных пробелов в контролях не найдено.",
    inputArtifacts: "Входные артефакты",
    noUpstreamArtifacts: "Для этого шага пока нет upstream-артефактов.",
    uploads: "Загрузки",
    notes: "Заметки",
    material: "Материал",
    uploadMaterial: "Загрузить материал",
    uploading: "Загрузка...",
    noStoredSources: "Для этого проекта пока нет сохраненных источников.",
    noQcNotes: "QC-заметок пока нет.",
    auditTrail: "Аудит-дорожка",
    system: "Система",
    unknownUser: "Неизвестный пользователь",
    noAuditEvents: "Событий аудита пока нет.",
    actingUser: "Текущий пользователь",
    switchSession: "Сменить сессию",
    switching: "Переключение...",
    language: "Язык",
    backToProjects: "Назад к проектам",
    topicRadar: "Topic Radar",
    topicRadarSubtitle:
      "Кураторская агрегация макроэкономических новостей из авторитетных источников, собранная в потенциальные YouTube-темы, а не в бесконечную ленту одинаковых заголовков.",
    refreshRadar: "Обновить Radar",
    refreshing: "Обновление...",
    hotTopics: "Горячие темы",
    curatedSources: "Кураторские источники",
    rawSignals: "Сырые сигналы",
    cluster: "Кластер",
    competitorMomentum: "Импульс конкурентов",
    competitorHelp:
      "Это легкий signal-layer: показывает темы, которые уже дали breakout или сильную скорость просмотров за последние две недели.",
    views: "просмотров",
    perDay: "в день",
    commercialSnapshot: "Коммерческий срез",
    shootNow: "Снимать сейчас",
    avgCost: "Средняя стоимость",
    avgBreakEven: "Средняя точка окупаемости",
    topScore: "Топовый скор",
    commercialHelp:
      "Используй это как triage-слой: сначала запускай идеи со статусом `shoot now`, а в сценарный пайплайн отправляй только утвержденных кандидатов.",
    topicCandidate: "Кандидат в тему",
    recommendedAngle: "Рекомендуемый угол подачи",
    youtubePotential: "Потенциал для YouTube",
    momentum: "Импульс",
    evidence: "Фактура",
    novelty: "Новизна",
    virality: "Виральность",
    competition: "Конкуренция",
    competitorLift: "Подъем у конкурентов",
    decision: "Решение",
    window: "Окно",
    days: "дней",
    effort: "Сложность",
    unitEconomics: "Юнит-экономика",
    cost: "Стоимость",
    breakEven: "Окупаемость",
    monetizationFit: "Совместимость с монетизацией",
    whyNow: "Почему сейчас",
    updatedLabel: "Обновлено",
    packagingHooks: "Упаковочные хуки",
    createProjectFromTopic: "Создать проект из темы",
    backToPipeline: "Назад в пайплайн",
    versions: "Версии",
    provenance: "Происхождение",
    readableMarkdown: "Читаемый Markdown",
  },
} as const;

type MessageKey = keyof typeof messages.en;

export function t(locale: Locale, key: MessageKey) {
  return messages[locale][key];
}

const stepLabels: Record<Locale, Record<StepId, string>> = {
  en: {
    channel_diagnosis: "Channel Diagnosis",
    audience_hypothesis: "Audience Hypothesis",
    brief_parsing: "Brief Parsing",
    topic_assessment: "Topic Assessment",
    evidence_pack: "Evidence Pack",
    editorial_angle: "Editorial Angle",
    script_outline: "Script Outline",
    draft_writer: "Draft Writer",
    voice_edit: "Voice Edit",
    final_qc: "Final QC",
  },
  ru: {
    channel_diagnosis: "Диагностика канала",
    audience_hypothesis: "Гипотеза по аудитории",
    brief_parsing: "Разбор брифа",
    topic_assessment: "Оценка темы",
    evidence_pack: "Пакет фактуры",
    editorial_angle: "Редакторский угол",
    script_outline: "Структура сценария",
    draft_writer: "Черновик сценария",
    voice_edit: "Редактура под голос",
    final_qc: "Финальный QC",
  },
};

const stepDescriptions: Record<Locale, Record<StepId, string>> = {
  en: {
    channel_diagnosis: "Analyze transcripts, titles, view patterns, and comments.",
    audience_hypothesis: "Infer audience segments, knowledge level, and triggers.",
    brief_parsing: "Normalize the author or producer brief into a usable input.",
    topic_assessment: "Decide whether the topic should go, pivot, or be rejected.",
    evidence_pack: "Assemble facts, counterarguments, and source scaffolding.",
    editorial_angle: "Choose the conflict, core question, and why-now frame.",
    script_outline: "Build the 15-20 minute structure with transitions and climax.",
    draft_writer: "Generate the full first script draft.",
    voice_edit: "Edit the draft into the author's spoken style.",
    final_qc: "Run the last fact, logic, style, and reputational check.",
  },
  ru: {
    channel_diagnosis: "Анализ транскриптов, заголовков, паттернов просмотров и комментариев.",
    audience_hypothesis: "Выявление сегментов аудитории, уровня знаний и триггеров.",
    brief_parsing: "Нормализация брифа автора или продюсера в рабочий вход.",
    topic_assessment: "Решение, идти ли в тему, сужать ее или отклонять.",
    evidence_pack: "Сбор фактуры, контраргументов и опорных источников.",
    editorial_angle: "Выбор конфликта, ключевого вопроса и why-now рамки.",
    script_outline: "Построение структуры на 15-20 минут с переходами и кульминацией.",
    draft_writer: "Генерация полного первого черновика сценария.",
    voice_edit: "Редактура черновика под живую речь автора.",
    final_qc: "Финальная проверка фактов, логики, стиля и репутационных рисков.",
  },
};

const statusLabels: Record<Locale, Record<StepStatus, string>> = {
  en: {
    not_started: "not started",
    generating: "generating",
    needs_review: "needs review",
    approved: "approved",
    needs_revision: "needs revision",
    blocked: "blocked",
    done: "done",
  },
  ru: {
    not_started: "не начат",
    generating: "генерация",
    needs_review: "нужна проверка",
    approved: "утвержден",
    needs_revision: "нужна доработка",
    blocked: "заблокирован",
    done: "готово",
  },
};

const provenanceLabels: Record<Locale, Record<Artifact["provenance"]["mode"], string>> = {
  en: {
    live_model: "live model",
    demo_fallback: "demo fallback",
    human_edit: "human edit",
  },
  ru: {
    live_model: "живая модель",
    demo_fallback: "демо fallback",
    human_edit: "ручная правка",
  },
};

const roleLabels: Record<Locale, Record<UserRole, string>> = {
  en: {
    admin: "admin",
    producer: "producer",
    editor: "editor",
    writer: "writer",
    author: "author",
  },
  ru: {
    admin: "админ",
    producer: "продюсер",
    editor: "редактор",
    writer: "сценарист",
    author: "автор",
  },
};

const uploadKindLabels: Record<Locale, Record<Upload["kind"], string>> = {
  en: {
    brief: "Brief",
    transcript: "Transcript",
    metrics: "Metrics",
    notes: "Notes",
    material: "Material",
  },
  ru: {
    brief: "Бриф",
    transcript: "Транскрипт",
    metrics: "Метрики",
    notes: "Заметки",
    material: "Материал",
  },
};

const topicStatusLabels: Record<Locale, Record<TopicCandidate["status"], string>> = {
  en: {
    hot: "hot",
    watch: "watch",
    commissioned: "commissioned",
    cooling: "cooling",
  },
  ru: {
    hot: "горячо",
    watch: "наблюдать",
    commissioned: "в работе",
    cooling: "остывает",
  },
};

const decisionLabels: Record<Locale, Record<TopicCandidate["decision"], string>> = {
  en: {
    shoot_now: "shoot now",
    hold_watch: "hold watch",
    skip: "skip",
  },
  ru: {
    shoot_now: "снимать сейчас",
    hold_watch: "держать под наблюдением",
    skip: "пропустить",
  },
};

const effortLabels: Record<Locale, Record<TopicCandidate["productionEffort"], string>> = {
  en: {
    low: "low",
    medium: "medium",
    high: "high",
  },
  ru: {
    low: "низкая",
    medium: "средняя",
    high: "высокая",
  },
};

const performanceBandLabels: Record<Locale, Record<CompetitorVideoSignal["performanceBand"], string>> = {
  en: {
    breakout: "breakout",
    strong: "strong",
    baseline: "baseline",
    weak: "weak",
  },
  ru: {
    breakout: "прорыв",
    strong: "сильный",
    baseline: "база",
    weak: "слабый",
  },
};

export function getStepLabel(locale: Locale, stepId: StepId) {
  return stepLabels[locale][stepId];
}

export function getStepDescription(locale: Locale, stepId: StepId) {
  return stepDescriptions[locale][stepId];
}

export function getStatusLabel(locale: Locale, status: StepStatus) {
  return statusLabels[locale][status];
}

export function getProvenanceLabel(locale: Locale, mode: Artifact["provenance"]["mode"]) {
  return provenanceLabels[locale][mode];
}

export function getRoleLabel(locale: Locale, role: UserRole) {
  return roleLabels[locale][role];
}

export function getUploadKindLabel(locale: Locale, kind: Upload["kind"]) {
  return uploadKindLabels[locale][kind];
}

export function getTopicStatusLabel(locale: Locale, status: TopicCandidate["status"]) {
  return topicStatusLabels[locale][status];
}

export function getDecisionLabel(locale: Locale, decision: TopicCandidate["decision"]) {
  return decisionLabels[locale][decision];
}

export function getEffortLabel(locale: Locale, effort: TopicCandidate["productionEffort"]) {
  return effortLabels[locale][effort];
}

export function getPerformanceBandLabel(locale: Locale, band: CompetitorVideoSignal["performanceBand"]) {
  return performanceBandLabels[locale][band];
}
