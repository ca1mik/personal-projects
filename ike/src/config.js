// src/config.js
module.exports = {
  // LLM configuration
  openaiApiKey: process.env.OPENAI_API_KEY || "",
  model: "gpt-4",
  // News RSS sources (example)
  newsFeeds: [
    "https://news.google.com/rss/search?q=экономика+Россия&hl=ru&gl=RU&ceid=RU:ru",
    "https://news.yandex.ru/rss.xml"
  ],
  // Thresholds
  newsScoreThreshold: 0.5,
  // Paths
  dataDir: "./data",
  logsDir: "./logs"
};
