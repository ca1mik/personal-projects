import { NextResponse } from "next/server";
import OpenAI from "openai";
import { z } from "zod";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL,
});

const generatedBriefSchema = z.object({
  core_question: z.string().min(8),
  core_thesis: z.string().min(8),
  viewer_outcome: z.string().min(8),
  author_intent: z.string().min(8),
  must_include: z.array(z.string().min(3)).min(2).max(6),
  must_avoid: z.array(z.string().min(3)).min(2).max(6),
  why_now: z.string().min(8).optional(),
});

function stripMarkdownFences(raw: string) {
  return raw
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

function parseGeneratedBrief(raw: string) {
  try {
    const parsed = JSON.parse(stripMarkdownFences(raw));
    const result = generatedBriefSchema.safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}

function parseLineFallback(raw: string) {
  return stripMarkdownFences(raw)
    .split(/\n+/)
    .map((line) => line.replace(/^[\-\d.)\s]+/, "").trim())
    .filter((line) => line.length > 10)
    .slice(0, 7);
}

function formatTheses(
  brief: z.infer<typeof generatedBriefSchema>,
  locale: "ru" | "en",
  durationMin: number,
) {
  const includeText = brief.must_include.join("; ");
  const avoidText = brief.must_avoid.join("; ");

  const theses =
    locale === "ru"
      ? [
          `Главный вопрос: ${brief.core_question}`,
          `Главный тезис: ${brief.core_thesis}`,
          `Что зритель должен понять: ${brief.viewer_outcome}`,
          `Авторский подход: ${brief.author_intent}`,
          `Включить обязательно: ${includeText}`,
          `Избегать: ${avoidText}`,
        ]
      : [
          `Core question: ${brief.core_question}`,
          `Core thesis: ${brief.core_thesis}`,
          `Viewer outcome: ${brief.viewer_outcome}`,
          `Author intent: ${brief.author_intent}`,
          `Must include: ${includeText}`,
          `Must avoid: ${avoidText}`,
        ];

  if (brief.why_now?.trim() && durationMin >= 15) {
    theses.push(
      locale === "ru"
        ? `Почему сейчас: ${brief.why_now.trim()}`
        : `Why now: ${brief.why_now.trim()}`,
    );
  }

  return theses;
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const topic: string = body.topic?.trim();
    const locale: "ru" | "en" = body.locale === "en" ? "en" : "ru";
    const durationMin = Number(body.durationMin) || 15;

    if (!topic || topic.length < 3) {
      return NextResponse.json({ error: "Topic too short" }, { status: 400 });
    }

    const isRu = locale === "ru";

    const systemPrompt = isRu
      ? [
          "Ты редактор, который превращает сырую тему в mini-brief для дальнейшей генерации сценария.",
          "Дальше этот brief будет использоваться шагами brief_parsing, topic_assessment, editorial_angle, script_outline и draft_writer.",
          "Поэтому нужны не общие идеи по теме, а поля, из которых можно собрать сильный сценарий.",
          "Правила:",
          "- Не уходи в соседние темы, если их нет в исходной формулировке.",
          "- Если тема про помощь в эмиграции или переезде, не переключайся на малый бизнес, рынки, инвестиции, макроэкономику или геополитику без прямого запроса.",
          "- Не подменяй тему более широкой или более удобной для тебя.",
          "- Не перечисляй абстрактные факты. Формулируй редакторские решения.",
          "- Главный тезис должен быть спорным, но защищаемым утверждением, а не названием темы.",
          "- Что включить обязательно: это конкретные линии разбора, примеры, риски, механики, точки выбора, а не общие слова.",
          "- Чего избегать: это конкретные ложные рамки, мифы, уводы в сторону, банальности, морализаторство.",
          "- Авторский подход опиши как способ разговора со зрителем: тон, позиция, обещание, границы.",
          "- Если тема практическая, делай акцент на решениях, рисках, последовательности действий и реальных дилеммах зрителя.",
          "Верни только JSON-объект без markdown с ключами:",
          "core_question, core_thesis, viewer_outcome, author_intent, must_include, must_avoid, why_now",
        ].join("\n")
      : [
          "You are an editor turning a raw topic into a mini-brief for later script generation.",
          "This brief will feed brief_parsing, topic_assessment, editorial_angle, script_outline, and draft_writer.",
          "So do not generate generic ideas. Generate the fields that make a strong script possible.",
          "Rules:",
          "- Stay inside the exact topic the user gave you.",
          "- Do not drift into adjacent domains unless the topic explicitly asks for them.",
          "- If the topic is about migration help or relocation, do not pivot to small business, markets, investing, macroeconomics, or geopolitics unless explicitly requested.",
          "- Do not turn the topic into a broader or easier topic.",
          "- Do not list abstract facts. Write editorial decisions.",
          "- The core thesis must be a defensible claim, not a subject label.",
          "- Must include should name concrete lines of analysis, examples, risks, mechanisms, decision points, or tradeoffs.",
          "- Must avoid should name concrete myths, bad frames, tangents, cliches, or preachy turns.",
          "- Author intent should describe the stance, tone, viewer promise, and boundaries.",
          "- For practical topics, prioritize decisions, risks, sequence, and real viewer dilemmas.",
          "Return only one JSON object with keys:",
          "core_question, core_thesis, viewer_outcome, author_intent, must_include, must_avoid, why_now",
        ].join("\n");

    const userPrompt = isRu
      ? [
          `Тема: "${topic}"`,
          `Длительность видео: ${durationMin} минут`,
          "",
          "Собери mini-brief для сценария.",
          "Пиши максимально конкретно под эту тему.",
          "must_include и must_avoid верни как массивы коротких пунктов.",
          "Если тема узкая или прикладная, не расширяй ее до общественных, экономических или бизнес-обобщений.",
        ].join("\n")
      : [
          `Topic: "${topic}"`,
          `Video duration: ${durationMin} minutes`,
          "",
          "Build a script mini-brief.",
          "Be maximally specific to this topic.",
          "Return must_include and must_avoid as arrays of short items.",
          "If the topic is narrow or practical, do not broaden it into social, economic, or business generalities.",
        ].join("\n");

    const completion = await client.chat.completions.create({
      model: process.env.OPENAI_MODEL ?? "gpt-4o",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.35,
      max_tokens: 900,
    });

    const raw = completion.choices[0]?.message?.content ?? "{}";
    const parsedBrief = parseGeneratedBrief(raw);

    if (parsedBrief) {
      return NextResponse.json({
        theses: formatTheses(parsedBrief, locale, durationMin),
      });
    }

    return NextResponse.json({ theses: parseLineFallback(raw) });
  } catch (err) {
    console.error("[suggest-theses] error:", err);
    return NextResponse.json({ error: "Generation failed" }, { status: 500 });
  }
}
