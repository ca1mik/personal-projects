/**
 * run-pipeline.ts
 * Прогоняет полный пайплайн напрямую через библиотечные функции.
 * Запуск: npx tsx run-pipeline.ts
 */

// Load .env.local manually (tsx doesn't auto-load Next.js env files)
import { readFileSync } from "fs";
function loadEnv(path: string) {
  try {
    readFileSync(path, "utf8")
      .split("\n")
      .filter((l) => l.trim() && !l.startsWith("#"))
      .forEach((l) => {
        const eq = l.indexOf("=");
        if (eq < 1) return;
        const key = l.slice(0, eq).trim();
        const val = l.slice(eq + 1).trim().replace(/^"|"$/g, "");
        if (!process.env[key]) process.env[key] = val;
      });
  } catch { /* file missing — ignore */ }
}
loadEnv(".env.local");
loadEnv(".env");

import {
  createProject,
  getProjectWorkspace,
  updateArtifactState,
  updateProjectStep,
  selectLatestArtifact,
} from "./lib/data/repository";
import { generateStepArtifact } from "./lib/ai/orchestrator";
import type { StepId } from "./lib/domain/pipeline";

const STEPS: StepId[] = [
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
];

const NEEDS_APPROVAL = new Set<StepId>([
  "topic_assessment",
  "editorial_angle",
  "script_outline",
  "voice_edit",
  "final_qc",
]);

const STEP_LABELS: Record<StepId, string> = {
  channel_diagnosis:    "Диагностика канала",
  audience_hypothesis:  "Гипотеза по аудитории",
  brief_parsing:        "Разбор брифа",
  topic_assessment:     "Оценка темы",
  evidence_pack:        "Пакет фактуры",
  editorial_angle:      "Редакторский угол",
  script_outline:       "Структура сценария",
  draft_writer:         "Черновик сценария",
  voice_edit:           "Редактура под голос",
  final_qc:             "Финальный QC",
};

function log(msg: string, emoji = "▶") {
  console.log(`${emoji}  ${msg}`);
}

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  // ── 1. Create project ──────────────────────────────────────────────────
  log("Создаю проект…", "🆕");

  const project = await createProject({
    title: "Ставка ЦБ: что за разворотом",
    authorName: "Лев",
    channelName: "Silvki Show",
    topic: [
      "Угол: Почему первое снижение ставки ЦБ РФ — это не победа над инфляцией, а возможный сигнал скрытого стресса в экономике",
      "Обещание зрителю: как читать решения ЦБ не по пресс-релизу, а по реальным индикаторам — после этого видео зритель не поведётся на заголовки",
      "Включить обязательно: разрыв между ключевой ставкой и реальными ставками кредитования, динамика инфляционных ожиданий населения vs официальная инфляция, что ЦБ говорит и что делает на самом деле",
      "Избегать: пересказ пресс-конференции ЦБ, прогнозов брокеров, тезисов о «мягкой посадке» без доказательной базы",
      "Почему сейчас: первый намёк ЦБ на разворот за 2 года — рынок в растерянности, момент идеальный для честного разбора",
    ].join("\n"),
    deadline: null,
  });

  log(`Проект: ${project.id} — "${project.title}"`, "✅");

  // ── 2. Run each step ───────────────────────────────────────────────────
  for (const stepId of STEPS) {
    const label = STEP_LABELS[stepId];
    const idx = STEPS.indexOf(stepId) + 1;
    log(`\n[${idx}/${STEPS.length}] ${label}…`, "⚙️ ");

    try {
      const artifact = await generateStepArtifact(project.id, stepId);
      const mode = artifact.provenance.mode;
      log(`готово (${mode}) — статус: ${artifact.status}`, mode === "live_model" ? "🤖" : "🔄");

      // Auto-approve if needed
      if (NEEDS_APPROVAL.has(stepId)) {
        const ws = await getProjectWorkspace(project.id);
        const latest = ws ? selectLatestArtifact(ws.artifacts, stepId) : null;
        if (latest) {
          await updateArtifactState({
            artifactId: latest.id,
            status: "approved",
            approvedByHuman: true,
            approvedByUserId: null,
          });
          log(`одобрено: ${label}`, "👍");
        }
      }

      // Advance project step
      const ws2 = await getProjectWorkspace(project.id);
      if (ws2) {
        const nextIdx = STEPS.indexOf(stepId) + 1;
        const nextStep = nextIdx < STEPS.length ? STEPS[nextIdx] : null;
        await updateProjectStep(project.id, nextStep);
      }

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      log(`ОШИБКА на шаге "${label}": ${msg}`, "❌");
      // Continue to next step
    }

    await sleep(300);
  }

  // ── 3. Done ────────────────────────────────────────────────────────────
  log(`\nПайплайн завершён!`, "🎬");
  log(`http://localhost:3000/projects/${project.id}?lang=ru`, "🔗");
}

main().catch((err) => {
  console.error("❌ Fatal:", err);
  process.exit(1);
});
