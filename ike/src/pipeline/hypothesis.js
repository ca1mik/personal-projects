// src/pipeline/hypothesis.js
const logger = require('../utils/logger');
const { OpenAI } = require('openai');
const config = require('../config');

const openai = new OpenAI({ apiKey: config.openaiApiKey });

/**
 * Build audience hypothesis based on channel analytics.
 * Returns an object with demographic guesses.
 */
async function buildAudienceHypothesis(analytics) {
  logger.info('Generating audience hypothesis');
  const prompt = `You are a market researcher. Based on the following channel analytics, describe the most probable target audience for a YouTube channel that creates economic and macro‑economic video content.
Analytics: ${JSON.stringify(analytics, null, 2)}
Provide a JSON object with fields: ageRange, interests, profession, educationLevel, geographicRegion.`;

  const response = await openai.chat.completions.create({
    model: config.model,
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.3,
  });

  const content = response.choices[0].message.content;
  try {
    const hypothesis = JSON.parse(content);
    return hypothesis;
  } catch (e) {
    logger.error('Failed to parse hypothesis JSON');
    return null;
  }
}

module.exports = { buildAudienceHypothesis };
