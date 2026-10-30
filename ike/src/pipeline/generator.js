// src/pipeline/generator.js
const logger = require('../utils/logger');
const { OpenAI } = require('openai');
const config = require('../config');

const openai = new OpenAI({ apiKey: config.openaiApiKey });

/**
 * Generate a single scene.
 * `index` – scene number (starting from 1).
 * `context` – object containing previous scenes' summaries, audience hypothesis, news items, brief.
 */
async function generateScene(index, context) {
  logger.info(`Generating scene ${index}`);
  const prompt = `You are a scriptwriter for a 15‑20 minute YouTube video about economics. Create scene ${index}.

Context:
- Audience: ${JSON.stringify(context.audience, null, 2)}
- Brief: ${JSON.stringify(context.brief, null, 2)}
- Top news topics (title only): ${context.topNews.map(n => n.title).join('; ')}
- Previous scenes summary: ${context.previousSummaries.join(' ')}

Write the scene in markdown format with a clear heading, a conversational tone (based on brief.tone), and include at most 150 words.
Return a JSON with fields: {"heading": "...", "content": "..."}`;

  const response = await openai.chat.completions.create({
    model: config.model,
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.7,
  });
  const raw = response.choices[0].message.content;
  try {
    const scene = JSON.parse(raw);
    return scene;
  } catch (e) {
    logger.error('Failed to parse scene JSON');
    return null;
  }
}

/**
 * Assemble full script from an array of scene objects.
 */
function assembleScript(scenes) {
  const parts = scenes.map(s => `## ${s.heading}\n\n${s.content}`).join('\n\n---\n\n');
  const intro = '# Видео сценарий\n\n*Сгенерировано автоматически*\n';
  return `${intro}\n${parts}`;
}

module.exports = { generateScene, assembleScript };
