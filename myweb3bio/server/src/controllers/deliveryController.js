// server/src/controllers/deliveryController.js
const { startConversation, handleUserMessage } = require('../utils/conversationEngine');
const deliveryFlow = require('../flows/deliveryFlow');

const sessions = {};

function generateSessionId() {
  return 'delivery_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8);
}

exports.startSession = (req, res) => {
  const sessionId = generateSessionId();
  const session = startConversation(deliveryFlow);
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
