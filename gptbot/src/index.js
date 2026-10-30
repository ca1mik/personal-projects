require("dotenv").config();

const fs = require("fs");
const TelegramBot = require("node-telegram-bot-api");
const config = require("./config");
const { handleAssistantInput } = require("./assistant");
const { chunkText, ensureDir } = require("./utils");
const { transcribeTelegramVoice } = require("./services/voice");

if (!config.telegramToken) {
  console.error("Missing TELEGRAM_BOT_TOKEN in .env");
  process.exit(1);
}

if (!config.codexSale.apiKey && config.defaultProvider === "codexsale") {
  console.error("Missing CODEX_SALE_API_KEY in .env");
  process.exit(1);
}

ensureDir(config.dataDir);
ensureDir(config.tempDir);

const bot = new TelegramBot(config.telegramToken, { polling: true });
const activeChats = new Set();

async function sendLongMessage(chatId, text) {
  const chunks = chunkText(text);
  for (const chunk of chunks) {
    await bot.sendMessage(chatId, chunk);
  }
}

async function withTyping(chatId, task) {
  await bot.sendChatAction(chatId, "typing");
  const interval = setInterval(() => {
    bot.sendChatAction(chatId, "typing").catch(() => {});
  }, 4000);

  try {
    return await task();
  } finally {
    clearInterval(interval);
  }
}

async function processText(chatId, text) {
  const result = await withTyping(chatId, () => handleAssistantInput(chatId, text));

  if (result.photoPath) {
    await bot.sendPhoto(chatId, result.photoPath);
    if (fs.existsSync(result.photoPath)) {
      fs.unlinkSync(result.photoPath);
    }
  }

  if (result.text) {
    await sendLongMessage(chatId, result.text);
  }
}

async function handleMessage(msg) {
  const chatId = msg.chat.id;

  if (activeChats.has(chatId)) {
    await bot.sendMessage(chatId, "Я еще занят предыдущей задачей. Подожди пару секунд.");
    return;
  }

  activeChats.add(chatId);

  try {
    if (msg.voice) {
      await bot.sendMessage(chatId, "Получил голосовое, расшифровываю...");
      const transcript = await transcribeTelegramVoice(bot, msg.voice);
      await bot.sendMessage(chatId, `Распознал:\n${transcript}`);
      await processText(chatId, transcript);
      return;
    }

    if (msg.text) {
      await processText(chatId, msg.text.trim());
      return;
    }

    await bot.sendMessage(
      chatId,
      "Сейчас я понимаю текст и voice. Для команд напиши /help."
    );
  } catch (error) {
    console.error("Assistant error:", error);
    const message =
      error?.name === "AbortError"
        ? `Запрос превысил лимит ожидания (${Math.round(config.requestTimeoutMs / 1000)} сек).`
        : error.message || "Неизвестная ошибка";

    await bot.sendMessage(chatId, `Ошибка: ${message}`);
  } finally {
    activeChats.delete(chatId);
  }
}

bot.on("message", async (msg) => {
  await handleMessage(msg);
});

bot.on("polling_error", (error) => {
  console.error("Polling error:", error.message);
});

console.log(
  `Assistant started. Default provider: ${config.defaultProvider}, model: ${
    config.defaultProvider === "ollama" ? config.ollama.model : config.codexSale.model
  }`
);
