const { handleUserMessage, startConversation } = require('../utils/conversationEngine');

function generateSessionId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function createAssistantController(prefix, flow) {
  const sessions = new Map();

  return {
    async startSession(req, res) {
      try {
        const sessionId = generateSessionId(prefix);
        const session = await startConversation(flow);
        sessions.set(sessionId, session);

        res.json({
          sessionId,
          prompt: session.prompt,
          systemMessages: session.systemMessages,
        });
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    },

    async handleMessage(req, res) {
      try {
        const { sessionId, message } = req.body || {};
        if (!sessionId || typeof message !== 'string') {
          return res.status(400).json({ error: 'sessionId and message are required' });
        }

        const session = sessions.get(sessionId);
        if (!session) {
          return res.status(400).json({ error: 'Invalid sessionId' });
        }

        const result = await handleUserMessage(session, message);
        if (result.completed) {
          sessions.delete(sessionId);
        }

        return res.json(result);
      } catch (error) {
        return res.status(500).json({ error: error.message });
      }
    },
  };
}

module.exports = createAssistantController;
