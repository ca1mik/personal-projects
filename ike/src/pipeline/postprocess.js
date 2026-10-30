// src/pipeline/postprocess.js
const logger = require('../utils/logger');
const { OpenAI } = require('openai');
const config = require('../config');

const openai = new OpenAI({ apiKey: config.openaiApiKey });

/**
 * Clean script: remove filler words, enforce conversational style.
 * Then run a second‑pass quality check that returns a score 0‑1.
 */
async function postprocessScript(rawScript) {
  logger.info('Post‑processing script');
  const cleanPrompt = `You are an editor. Take the following markdown script for a YouTube video about economics and improve it:
- Remove repetitive phrases and filler words.
- Make the tone more conversational if the brief requests it.
- Keep the structure (headings) intact.
Return the cleaned markdown only.`;

  const cleanResp = await openai.chat.completions.create({
    model: config.model,
    messages: [{ role: 'user', content: `${cleanPrompt}\n\n${rawScript}` }],
    temperature: 0.3,
  });
  const cleaned = cleanResp.choices[0].message.content;

  // Quality check – ask LLM to give a coherence/engagement score
  const qualityPrompt = `Rate the following script on a scale 0‑1 for coherence, engagement and suitability for a 15‑20 minute YouTube video about economics. Provide ONLY the numeric value.`;
  const qualityResp = await openai.chat.completions.create({
    model: config.model,
    messages: [{ role: 'user', content: `${qualityPrompt}\n\n${cleaned}` }],
    temperature: 0.0,
  });
  const scoreStr = qualityResp.choices[0].message.content.trim();
  const score = parseFloat(scoreStr);

  return { cleanedScript: cleaned, qualityScore: isNaN(score) ? 0 : score };
}

module.exports = { postprocessScript };
