/**
 * run-pipeline.mjs
 * Прогоняет полный пайплайн через Next.js API на localhost:3000.
 * Создаёт проект → генерирует все 10 шагов → одобряет где нужно.
 *
 * Запуск: node run-pipeline.mjs
 */

const BASE = "http://localhost:3000";

const PROJECT = {
  title: "Ставка ЦБ: что будет дальше",
  authorName: "Лев",
  channelName: "Silvki Show",
  topic: [
    "Угол: Почему первое снижение ставки ЦБ РФ может быть сигналом скрытого стресса, а не победы над инфляцией",
    "Обещание зрителю: зритель поймёт, как читать решения ЦБ между строк — не по пресс-релизу, а по реальным индикаторам",
    "Включить обязательно: динамика инфляционных ожиданий населения, разрыв между ключевой ставкой и кредитными ставками банков, позиция ЦБ vs реальный кредитный импульс",
    "Избегать: пересказ пресс-конференции ЦБ, прогнозов брокеров, абстрактных тезисов о «мягкой посадке»",
    "Почему сейчас: ЦБ РФ впервые за 2 года намекает на разворот, рынок не понимает — это сигнал или ошибка"
  ].join("\n"),
  deadline: "",
  targetDurationMin: "15",
};

const STEPS = [
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

// Steps that require human approval before the next step runs
const APPROVAL_REQUIRED = new Set([
  "topic_assessment",
  "editorial_angle",
  "script_outline",
  "voice_edit",
  "final_qc",
]);

function log(msg, emoji = "▶") {
  console.log(`\n${emoji}  ${msg}`);
}

async function postForm(path, fields) {
  const body = new URLSearchParams();
  for (const [k, v] of Object.entries(fields)) {
    if (v != null) body.append(k, String(v));
  }

  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    redirect: "manual",
  });

  // Server actions redirect on success — follow redirect to get final URL
  const location = res.headers.get("location") ?? "";
  return { status: res.status, location };
}

async function getPage(path) {
  const res = await fetch(`${BASE}${path}`, { redirect: "follow" });
  return res.status;
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ─── 1. Create project ──────────────────────────────────────────────────────
log("Создаю проект...", "🆕");
const createRes = await postForm("/projects", {
  ...PROJECT,
  returnTo: "/projects",
});

if (createRes.status !== 303 && createRes.status !== 302) {
  console.error("❌ Не удалось создать проект. Status:", createRes.status);
  process.exit(1);
}

// Extract projectId from redirect location: /projects/project_XXXX
const projectMatch = createRes.location.match(/\/projects\/(project_[a-zA-Z0-9]+)/);
if (!projectMatch) {
  console.error("❌ Не нашёл projectId в редиректе:", createRes.location);
  process.exit(1);
}
const projectId = projectMatch[1];
log(`Проект создан: ${projectId}`, "✅");

// ─── 2. Run each step ───────────────────────────────────────────────────────
for (const stepId of STEPS) {
  log(`Генерирую шаг: ${stepId}`, "⚙️");

  const returnTo = `/projects/${projectId}?step=${stepId}&lang=ru`;

  // Generate
  const genRes = await postForm(`/projects/${projectId}`, {
    projectId,
    stepId,
    returnTo,
    _action: "generateStep",
  });

  // The form action is mapped via Next.js server actions. We need to call via the
  // direct action endpoint. Let's use the /api approach instead.
  // Actually server actions are embedded in the page POST. Let's call via fetch with
  // the Next.js action header.
  
  // Try the proper server action path
  const actionRes = await fetch(`${BASE}/projects/${projectId}?step=${stepId}&lang=ru`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "Next-Action": "generateStepAction",
    },
    body: new URLSearchParams({
      projectId,
      stepId,
      returnTo: `/projects/${projectId}?step=${stepId}&lang=ru`,
    }).toString(),
    redirect: "manual",
  });

  log(`  → generate HTTP ${actionRes.status} (location: ${actionRes.headers.get("location") ?? "–"})`, "  ");

  // If 303/302 = success redirect; wait for Next.js to finish
  await sleep(2000);

  // If this step needs approval, auto-approve it
  if (APPROVAL_REQUIRED.has(stepId)) {
    log(`  Одобряю шаг: ${stepId}`, "👍");

    // First get the artifact id from the page
    const pageRes = await fetch(`${BASE}/projects/${projectId}?step=${stepId}&lang=ru`);
    const html = await pageRes.text();

    // Find artifactId in hidden inputs
    const artifactMatch = html.match(/name="artifactId"\s+value="(artifact_[a-zA-Z0-9]+)"/);
    if (!artifactMatch) {
      log(`  ⚠️  Не нашёл artifactId для одобрения шага ${stepId} — пропускаю`, "⚠️");
      continue;
    }

    const artifactId = artifactMatch[1];
    const approveRes = await fetch(`${BASE}/projects/${projectId}?step=${stepId}&lang=ru`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        projectId,
        artifactId,
        returnTo: `/projects/${projectId}?step=${stepId}&lang=ru`,
        _action: "approveArtifact",
      }).toString(),
      redirect: "manual",
    });

    log(`  → approve HTTP ${approveRes.status}`, "  ");
    await sleep(500);
  }
}

log(`🎉 Пайплайн завершён! Открой: ${BASE}/projects/${projectId}?lang=ru`, "🎬");
