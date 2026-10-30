const fs = require("fs");
const path = require("path");
const config = require("../config");
const { runProcess } = require("./process");

function normalizeContent(content) {
  if (typeof content === "string") {
    return content.trim();
  }

  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (item && typeof item.text === "string") {
          return item.text;
        }

        if (item && item.type === "text" && typeof item.text === "string") {
          return item.text;
        }

        if (item && item.type === "output_text" && typeof item.text === "string") {
          return item.text;
        }

        return "";
      })
      .join("\n")
      .trim();
  }

  return "";
}

async function fetchJson(url, options = {}, timeoutMs = config.requestTimeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json().catch(() => ({}))
      : await response.text();

    if (!response.ok) {
      throw new Error(payload?.error?.message || payload?.message || `HTTP ${response.status}`);
    }

    return payload;
  } finally {
    clearTimeout(timeout);
  }
}

async function chatWithCodexSale(model, messages) {
  const payload = await fetchJson(`${config.codexSale.baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.codexSale.apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.3,
      stream: false,
    }),
  });

  const answer = normalizeContent(payload?.choices?.[0]?.message?.content);
  if (!answer) {
    throw new Error("Empty response from codex.sale");
  }

  return answer;
}

async function chatWithOllama(model, messages) {
  const payload = await fetchJson(
    `${config.ollama.host}/api/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages,
        stream: false,
      }),
    },
    config.ollama.requestTimeoutMs
  );

  const answer = normalizeContent(payload?.message?.content);
  if (!answer) {
    throw new Error("Empty response from Ollama");
  }

  return answer;
}

async function chat(provider, model, messages) {
  if (provider === "ollama") {
    return chatWithOllama(model, messages);
  }

  return chatWithCodexSale(model, messages);
}

async function listCodexSaleModels() {
  const payload = await fetchJson(`${config.codexSale.baseUrl}/models`, {
    headers: {
      Authorization: `Bearer ${config.codexSale.apiKey}`,
    },
  });

  return (payload?.data || []).map((item) => item.id).filter(Boolean);
}

function parseOllamaList(output) {
  return output
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split(/\s{2,}/)[0])
    .filter(Boolean);
}

async function listOllamaModels() {
  const result = await runProcess("ollama", ["list"], {
    timeoutMs: 20000,
  });

  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || "Failed to list Ollama models");
  }

  return parseOllamaList(result.stdout);
}

async function listModels(provider) {
  if (provider === "ollama") {
    return listOllamaModels();
  }

  return listCodexSaleModels();
}

async function transcribeAudio(filePath) {
  if (config.voice.provider !== "codexsale") {
    throw new Error("Voice transcription is configured only for codexsale right now");
  }

  const buffer = fs.readFileSync(filePath);
  const formData = new FormData();
  const file = new File([buffer], path.basename(filePath), {
    type: "audio/mpeg",
  });

  formData.append("model", config.voice.model);
  formData.append("file", file);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.requestTimeoutMs);

  try {
    const response = await fetch(`${config.codexSale.baseUrl}/audio/transcriptions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.codexSale.apiKey}`,
      },
      body: formData,
      signal: controller.signal,
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.error?.message || payload?.message || `HTTP ${response.status}`);
    }

    const text = normalizeContent(payload?.text || payload?.transcript);
    if (!text) {
      throw new Error("Empty transcription result");
    }

    return text;
  } finally {
    clearTimeout(timeout);
  }
}

module.exports = {
  chat,
  listModels,
  transcribeAudio,
};
