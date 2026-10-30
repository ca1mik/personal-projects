// src/pipeline/brief.js
/**
 * Normalise author brief into a structured object.
 * Expected input format (free text) may contain:
 *   - topic
 *   - desired tone (educational, conversational)
 *   - length in minutes
 *   - any specific points to cover
 * This function extracts those pieces using simple heuristics.
 */
function parseBrief(rawBrief) {
  const result = {};
  const lower = rawBrief.toLowerCase();
  // Topic – first line or after "тема" keyword
  const topicMatch = rawBrief.match(/тема[:\s]+([^\n]+)/i) || rawBrief.split('\n')[0];
  result.topic = typeof topicMatch === 'string' ? topicMatch.trim() : topicMatch[1].trim();

  // Tone detection
  if (lower.includes('обучающий') || lower.includes('образовательный')) result.tone = 'educational';
  else if (lower.includes('разговорный') || lower.includes('неформальный')) result.tone = 'conversational';
  else result.tone = 'neutral';

  // Length in minutes – look for number followed by "минут"
  const lengthMatch = lower.match(/(\d{1,2})\s*минут/);
  result.lengthMinutes = lengthMatch ? parseInt(lengthMatch[1], 10) : 20;

  // Extract bullet‑style points if present
  const points = [];
  rawBrief.split('\n').forEach(line => {
    const trimmed = line.trim();
    if (trimmed.startsWith('-') || trimmed.startsWith('•')) points.push(trimmed.replace(/^[-•]\s*/, ''));
  });
  if (points.length) result.keyPoints = points;

  return result;
}

module.exports = { parseBrief };
