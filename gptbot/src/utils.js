const fs = require("fs");

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function chunkText(text, maxLength = 3900) {
  const chunks = [];
  let remaining = text;

  while (remaining.length > maxLength) {
    let splitIndex = remaining.lastIndexOf("\n", maxLength);
    if (splitIndex < 500) {
      splitIndex = maxLength;
    }

    chunks.push(remaining.slice(0, splitIndex));
    remaining = remaining.slice(splitIndex).trimStart();
  }

  if (remaining) {
    chunks.push(remaining);
  }

  return chunks;
}

function normalizeWhitespace(value) {
  return String(value || "")
    .replace(/\r/g, "")
    .trim();
}

function splitCommandArgs(text) {
  const trimmed = normalizeWhitespace(text);
  const [command, ...rest] = trimmed.split(/\s+/);
  return {
    command: command || "",
    rest: rest.join(" ").trim(),
  };
}

function parsePipeFields(text, expectedFields) {
  const parts = text.split("|").map((part) => part.trim());
  const result = {};

  expectedFields.forEach((field, index) => {
    result[field] = parts[index] || "";
  });

  return result;
}

function safeJsonParse(text, fallback) {
  try {
    return JSON.parse(text);
  } catch (error) {
    return fallback;
  }
}

module.exports = {
  ensureDir,
  chunkText,
  normalizeWhitespace,
  splitCommandArgs,
  parsePipeFields,
  safeJsonParse,
};
