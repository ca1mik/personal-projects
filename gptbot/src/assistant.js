const path = require("path");
const config = require("./config");
const { chat, listModels } = require("./services/ai");
const { createEmailDraftFile, createCalendarEventFile } = require("./services/drafts");
const { searchFilesByName, searchInFiles } = require("./services/file-search");
const { runWindowsAction } = require("./services/windows");
const { getChatSettings, updateChatSettings, getHistory, setHistory, clearHistory } = require("./state");
const { normalizeWhitespace, parsePipeFields, splitCommandArgs } = require("./utils");

function buildSystemMessage() {
  return {
    role: "system",
    content: config.systemPrompt,
  };
}

function formatList(items) {
  if (!items.length) {
    return "Ничего не найдено.";
  }

  return items.map((item, index) => `${index + 1}. ${item}`).join("\n");
}

async function handleChatMessage(chatId, text) {
  const settings = getChatSettings(chatId);
  const history = getHistory(chatId);
  const messages = [buildSystemMessage(), ...history, { role: "user", content: text }];
  const answer = await chat(settings.provider, settings.model, messages);

  setHistory(chatId, [...history, { role: "user", content: text }, { role: "assistant", content: answer }]);
  return answer;
}

function buildHelpMessage() {
  return [
    "Я умею:",
    "- обычный чат с LLM",
    "- локальную модель через Ollama",
    "- внешний API через codex.sale",
    "- голосовые сообщения",
    "- поиск файлов по имени: /find текст",
    "- поиск по содержимому: /grep текст",
    "- список окон: /windows",
    "- фокус окна: /focus часть_заголовка",
    "- свернуть окно: /minimize [заголовок]",
    "- восстановить окно: /restore [заголовок]",
    "- открыть приложение, файл или URL: /open путь_или_url",
    "- горячие клавиши: /keys ctrl+s",
    "- ввод текста в активное окно: /type ваш текст",
    "- клик мышью: /click x y",
    "- скриншот экрана: /screenshot",
    "- черновик письма Outlook: /mail to|subject|body",
    "- отправка письма Outlook: /sendmail to|subject|body",
    "- встреча в Outlook: /event title|YYYY-MM-DD HH:mm|minutes|location|body",
    "- провайдер: /provider codexsale или /provider ollama",
    "- модель: /model list или /model имя",
    "- статус: /status",
    "- очистка истории: /reset",
    "",
    "Можно и без слэшей: 'сделай скрин', 'найди файл договор', 'открой notepad', 'нажми ctrl+s'.",
  ].join("\n");
}

function parseNaturalLanguage(text) {
  const normalized = normalizeWhitespace(text);

  if (/^(сделай|покажи).*(скрин|скриншот)/i.test(normalized)) {
    return { type: "command", command: "/screenshot", rest: "" };
  }

  if (/^(покажи|список).*(окон|окна)/i.test(normalized)) {
    return { type: "command", command: "/windows", rest: "" };
  }

  if (/^(найди файл|найди документ|найди)\s+/i.test(normalized)) {
    return {
      type: "command",
      command: "/find",
      rest: normalized.replace(/^(найди файл|найди документ|найди)\s+/i, ""),
    };
  }

  if (/^(найди по содержимому|найди в файлах|поиск по тексту)\s+/i.test(normalized)) {
    return {
      type: "command",
      command: "/grep",
      rest: normalized.replace(/^(найди по содержимому|найди в файлах|поиск по тексту)\s+/i, ""),
    };
  }

  if (/^(открой|запусти)\s+/i.test(normalized)) {
    return {
      type: "command",
      command: "/open",
      rest: normalized.replace(/^(открой|запусти)\s+/i, ""),
    };
  }

  if (/^(сверни|минимизируй)/i.test(normalized)) {
    return {
      type: "command",
      command: "/minimize",
      rest: normalized.replace(/^(сверни|минимизируй)(\s+окно)?\s*/i, ""),
    };
  }

  if (/^(восстанови|разверни)/i.test(normalized)) {
    return {
      type: "command",
      command: "/restore",
      rest: normalized.replace(/^(восстанови|разверни)(\s+окно)?\s*/i, ""),
    };
  }

  if (/^(активируй окно|переключись на)\s+/i.test(normalized)) {
    return {
      type: "command",
      command: "/focus",
      rest: normalized.replace(/^(активируй окно|переключись на)\s+/i, ""),
    };
  }

  if (/^(нажми|hotkey)\s+/i.test(normalized)) {
    return {
      type: "command",
      command: "/keys",
      rest: normalized.replace(/^(нажми|hotkey)\s+/i, ""),
    };
  }

  if (/^(введи|напечатай|напиши)\s+/i.test(normalized)) {
    return {
      type: "command",
      command: "/type",
      rest: normalized.replace(/^(введи|напечатай|напиши)\s+/i, ""),
    };
  }

  if (/^клик\s+\d+\s+\d+$/i.test(normalized)) {
    return {
      type: "command",
      command: "/click",
      rest: normalized.replace(/^клик\s+/i, ""),
    };
  }

  return {
    type: "chat",
    text: normalized,
  };
}

async function executeCommand(chatId, command, rest) {
  const trimmedRest = normalizeWhitespace(rest);

  switch (command) {
    case "/start":
      clearHistory(chatId);
      return {
        text: "Готово. Я запущен и могу отвечать как LLM-ассистент, искать файлы, делать скриншоты и управлять ПК. Напиши /help для списка команд.",
      };

    case "/help":
      return { text: buildHelpMessage() };

    case "/reset":
      clearHistory(chatId);
      return { text: "История диалога очищена." };

    case "/status": {
      const settings = getChatSettings(chatId);
      return {
        text: [
          "Текущие настройки:",
          `- provider: ${settings.provider}`,
          `- model: ${settings.model}`,
          `- roots: ${config.searchRoots.join("; ")}`,
          `- voice provider: ${config.voice.provider}`,
          `- voice model: ${config.voice.model}`,
        ].join("\n"),
      };
    }

    case "/provider": {
      if (!trimmedRest) {
        const settings = getChatSettings(chatId);
        return {
          text: `Текущий provider: ${settings.provider}\nДоступно: codexsale, ollama`,
        };
      }

      const provider = trimmedRest.toLowerCase();
      if (!["codexsale", "ollama"].includes(provider)) {
        return { text: "Неизвестный provider. Используй codexsale или ollama." };
      }

      const model = provider === "ollama" ? config.ollama.model : config.codexSale.model;
      updateChatSettings(chatId, { provider, model });
      return { text: `Provider переключен на ${provider}. Модель по умолчанию: ${model}` };
    }

    case "/model": {
      if (!trimmedRest) {
        const settings = getChatSettings(chatId);
        return { text: `Текущая модель: ${settings.model}` };
      }

      if (trimmedRest.toLowerCase() === "list") {
        const settings = getChatSettings(chatId);
        const models = await listModels(settings.provider);
        return {
          text: `Модели для ${settings.provider}:\n${formatList(models)}`,
        };
      }

      updateChatSettings(chatId, { model: trimmedRest });
      return { text: `Модель переключена на ${trimmedRest}` };
    }

    case "/find": {
      const results = await searchFilesByName(trimmedRest);
      return {
        text: results.length
          ? `Найденные файлы:\n${formatList(results)}`
          : "Файлы не найдены.",
      };
    }

    case "/grep": {
      const results = await searchInFiles(trimmedRest);
      return {
        text: results.length
          ? `Совпадения по содержимому:\n${formatList(results)}`
          : "Совпадения не найдены.",
      };
    }

    case "/windows": {
      const payload = await runWindowsAction("list_windows");
      const lines = (payload.windows || []).map(
        (window, index) => `${index + 1}. ${window.title} [pid ${window.pid}]`
      );

      return {
        text: lines.length ? `Открытые окна:\n${lines.join("\n")}` : "Открытых окон не найдено.",
      };
    }

    case "/focus": {
      const payload = await runWindowsAction("focus_window", { Title: trimmedRest });
      return { text: payload.message };
    }

    case "/minimize": {
      const payload = await runWindowsAction("minimize_window", { Title: trimmedRest });
      return { text: payload.message };
    }

    case "/restore": {
      const payload = await runWindowsAction("restore_window", { Title: trimmedRest });
      return { text: payload.message };
    }

    case "/open": {
      const payload = await runWindowsAction("open_target", { Target: trimmedRest });
      return { text: payload.message };
    }

    case "/keys": {
      const payload = await runWindowsAction("send_keys", { Keys: trimmedRest });
      return { text: payload.message };
    }

    case "/type": {
      const payload = await runWindowsAction("type_text", { Text: trimmedRest });
      return { text: payload.message };
    }

    case "/click": {
      const [x, y] = trimmedRest.split(/\s+/);
      const payload = await runWindowsAction("click", { X: x, Y: y });
      return { text: payload.message };
    }

    case "/screenshot": {
      const filePath = path.join(config.tempDir, `screenshot-${Date.now()}.png`);
      await runWindowsAction("screenshot", { Path: filePath });
      return {
        text: "Скриншот готов.",
        photoPath: filePath,
      };
    }

    case "/mail":
    case "/sendmail": {
      const fields = parsePipeFields(trimmedRest, ["to", "subject", "body"]);
      try {
        const payload = await runWindowsAction(
          "draft_email",
          {
            To: fields.to,
            Subject: fields.subject,
            Body: fields.body,
            Send: command === "/sendmail" ? "true" : "",
          },
          { timeoutMs: 12000 }
        );
        return { text: payload.message };
      } catch (error) {
        const filePath = createEmailDraftFile(fields);
        return {
          text:
            command === "/sendmail"
              ? `Автоотправка через Outlook не сработала быстро. Сохранил черновик письма в файл:\n${filePath}`
              : `Outlook не ответил быстро. Сохранил черновик письма в файл:\n${filePath}`,
        };
      }
    }

    case "/event": {
      const fields = parsePipeFields(trimmedRest, ["title", "start", "minutes", "location", "body"]);
      try {
        const payload = await runWindowsAction(
          "create_event",
          {
            Subject: fields.title,
            Start: fields.start,
            Minutes: fields.minutes || "60",
            Location: fields.location,
            Body: fields.body,
          },
          { timeoutMs: 12000 }
        );
        return { text: payload.message };
      } catch (error) {
        const filePath = createCalendarEventFile({
          title: fields.title,
          start: fields.start,
          minutes: fields.minutes || "60",
          location: fields.location,
          body: fields.body,
        });
        return {
          text: `Outlook не ответил быстро. Сохранил событие в ICS-файл:\n${filePath}`,
        };
      }
    }

    default:
      return { text: "Неизвестная команда. Напиши /help." };
  }
}

async function handleAssistantInput(chatId, text) {
  const parsed = text.startsWith("/") ? { type: "command", ...splitCommandArgs(text) } : parseNaturalLanguage(text);

  if (parsed.type === "command") {
    return executeCommand(chatId, parsed.command, parsed.rest);
  }

  return {
    text: await handleChatMessage(chatId, parsed.text),
  };
}

module.exports = {
  handleAssistantInput,
};
