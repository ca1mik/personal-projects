// server/src/controllers/sdrController.js
const { startConversation, handleUserMessage } = require('../utils/conversationEngine');
const sdrFlow = require('../flows/sdrFlow');

// In‑memory store of sessions: { sessionId: { flow, state } }
const sessions = {};

function generateSessionId() {
  return 'sdr_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8);
}

exports.startSession = (req, res) => {
  const sessionId = generateSessionId();
  const session = startConversation(sdrFlow);
  sessions[sessionId] = session;
  res.json({ sessionId, prompt: session.prompt });
};

exports.handleMessage = (req, res) => {
  const { sessionId } = req.body;
  const userMessage = req.body.message;
  if (!sessions[sessionId]) {
    return res.status(400).json({ error: 'Invalid sessionId' });
  }
  const result = handleUserMessage(sessions[sessionId], userMessage);
  // result contains nextPrompt, completed (bool), collectedData, toolCalls etc.
  if (result.completed) {
    delete sessions[sessionId];
  }
  res.json(result);
};
