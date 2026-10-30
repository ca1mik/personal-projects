const fs = require("fs");
const config = require("./config");
const { ensureDir } = require("./utils");

ensureDir(config.dataDir);
ensureDir(config.tempDir);

const defaultState = {
  chats: {},
};

function loadState() {
  if (!fs.existsSync(config.stateFile)) {
    return { ...defaultState };
  }

  try {
    const raw = fs.readFileSync(config.stateFile, "utf8");
    const parsed = JSON.parse(raw);
    return {
      ...defaultState,
      ...parsed,
      chats: parsed?.chats && typeof parsed.chats === "object" ? parsed.chats : {},
    };
  } catch (error) {
    return { ...defaultState };
  }
}

let state = loadState();

function saveState() {
  fs.writeFileSync(config.stateFile, JSON.stringify(state, null, 2));
}

function ensureChat(chatId) {
  const key = String(chatId);

  if (!state.chats[key]) {
    state.chats[key] = {
      history: [],
      provider: config.defaultProvider,
      model:
        config.defaultProvider === "ollama"
          ? config.ollama.model
          : config.codexSale.model,
    };
    saveState();
  }

  return state.chats[key];
}

function getChatSettings(chatId) {
  return ensureChat(chatId);
}

function updateChatSettings(chatId, patch) {
  const chat = ensureChat(chatId);
  state.chats[String(chatId)] = {
    ...chat,
    ...patch,
  };
  saveState();
  return state.chats[String(chatId)];
}

function getHistory(chatId) {
  return ensureChat(chatId).history || [];
}

function setHistory(chatId, history) {
  const chat = ensureChat(chatId);
  chat.history = history.slice(-config.historyLimit);
  saveState();
}

function clearHistory(chatId) {
  const chat = ensureChat(chatId);
  chat.history = [];
  saveState();
}

module.exports = {
  getChatSettings,
  updateChatSettings,
  getHistory,
  setHistory,
  clearHistory,
};
