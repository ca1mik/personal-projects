const path = require("path");
const config = require("../config");
const { runProcess } = require("./process");

function normalizeQuery(value) {
  return String(value || "").trim().toLowerCase();
}

async function searchFilesByName(query, roots = config.searchRoots) {
  const normalizedQuery = normalizeQuery(query);
  if (!normalizedQuery) {
    return [];
  }

  const args = ["--files", ...roots];
  const result = await runProcess("rg", args, {
    timeoutMs: 45000,
  });

  if (result.code !== 0 && !result.stdout) {
    throw new Error(result.stderr.trim() || "File search failed");
  }

  return result.stdout
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => {
      const lower = item.toLowerCase();
      return lower.includes(normalizedQuery) || path.basename(lower).includes(normalizedQuery);
    })
    .slice(0, config.searchMaxResults);
}

async function searchInFiles(query, roots = config.searchRoots) {
  const normalizedQuery = String(query || "").trim();
  if (!normalizedQuery) {
    return [];
  }

  const args = [
    "-n",
    "-F",
    "-i",
    "--max-count",
    "1",
    "--max-filesize",
    "2M",
    normalizedQuery,
    ...roots,
  ];

  const result = await runProcess("rg", args, {
    timeoutMs: 45000,
  });

  if (result.code !== 0 && !result.stdout) {
    return [];
  }

  return result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, config.grepMaxResults);
}

module.exports = {
  searchFilesByName,
  searchInFiles,
};
