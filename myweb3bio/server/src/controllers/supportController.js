// server/src/controllers/supportController.js
const { startConversation, handleUserMessage } = require('../utils/conversationEngine');
const supportFlow = require('../flows/supportFlow');

const sessions = {};

function generateSessionId() {
  return 'support_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8);
}

exports.startSession = (req, res) => {
  const sessionId = generateSessionId();
  const session = startConversation(supportFlow);
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
  if (result.completed) {
    delete sessions[sessionId];
  }
  res.json(result);
};
