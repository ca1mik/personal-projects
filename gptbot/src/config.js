const path = require("path");
const os = require("os");
const fs = require("fs");

function parseInteger(value, fallback, minValue) {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) {
    return fallback;
  }

  return Math.max(parsed, minValue);
}

function uniquePaths(paths) {
  return [...new Set(paths.filter(Boolean))];
}

function existingPaths(paths) {
  return uniquePaths(paths).filter((entry) => {
    try {
      return fs.existsSync(entry);
    } catch (error) {
      return false;
    }
  });
}

function existingDefaultRoots() {
  const home = process.env.USERPROFILE || os.homedir();

  return existingPaths([
    home,
    path.join(home, "Desktop"),
    path.join(home, "Documents"),
    path.join(home, "Downloads"),
  ]);
}

function parseRoots(value) {
  if (!value) {
    return existingDefaultRoots();
  }

  const roots = existingPaths(
    value
      .split(";")
      .map((entry) => entry.trim())
      .filter(Boolean)
  );

  return roots.length ? roots : existingDefaultRoots();
}

const dataDir = path.join(process.cwd(), "data");
const tempDir = path.join(process.cwd(), "tmp");

module.exports = {
  telegramToken: process.env.TELEGRAM_BOT_TOKEN,
  stateFile: path.join(dataDir, "state.json"),
  dataDir,
  tempDir,
  historyLimit: parseInteger(process.env.MAX_HISTORY_MESSAGES, 20, 2),
  requestTimeoutMs: parseInteger(process.env.REQUEST_TIMEOUT_MS, 90000, 10000),
  searchMaxResults: parseInteger(process.env.SEARCH_MAX_RESULTS, 10, 1),
  grepMaxResults: parseInteger(process.env.GREP_MAX_RESULTS, 10, 1),
  searchRoots: parseRoots(process.env.SEARCH_ROOTS),
  defaultProvider: (process.env.AI_PROVIDER || "codexsale").trim().toLowerCase(),
  codexSale: {
    apiKey: process.env.CODEX_SALE_API_KEY,
    baseUrl: process.env.CODEX_SALE_BASE_URL || "https://codex.sale/v1",
    model: process.env.CODEX_SALE_MODEL || "gpt-5.4-mini",
  },
  ollama: {
    host: process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434",
    model: process.env.OLLAMA_MODEL || "qwen3:4b",
    requestTimeoutMs: parseInteger(process.env.OLLAMA_REQUEST_TIMEOUT_MS, 180000, 30000),
  },
  voice: {
    provider: (process.env.VOICE_PROVIDER || "codexsale").trim().toLowerCase(),
    model: process.env.VOICE_MODEL || "gpt-4o-transcribe",
  },
  systemPrompt:
    process.env.SYSTEM_PROMPT ||
    "You are a helpful desktop automation assistant inside Telegram. Reply in the user's language, be concise, and confirm actions clearly.",
};
