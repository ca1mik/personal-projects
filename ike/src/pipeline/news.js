// src/pipeline/news.js
const logger = require('../utils/logger');
const Parser = require('rss-parser');
const config = require('../config');
const crypto = require('crypto');

const parser = new Parser();

/**
 * Fetch raw news items from configured RSS feeds.
 * Returns an array of objects { title, link, pubDate, source }.
 */
async function fetchNews() {
  logger.info('Fetching news from RSS feeds');
  const allItems = [];
  for (const feedUrl of config.newsFeeds) {
    try {
      const feed = await parser.parseURL(feedUrl);
      feed.items.forEach(item => {
        allItems.push({
          id: crypto.createHash('md5').update(item.link).digest('hex'),
          title: item.title,
          link: item.link,
          pubDate: item.pubDate,
          source: feed.title || feedUrl,
        });
      });
    } catch (e) {
      logger.error(`Failed to fetch RSS ${feedUrl}: ${e.message}`);
    }
  }
  return allItems;
}

/**
 * Simple TF‑IDF‑like scoring based on keyword overlap with a predefined
 * list of economic terms. Returns items sorted by score descending.
 */
function scoreNews(items) {
  const keywords = ['экономика', 'инфляция', 'валюта', 'рост', 'спад', 'рынок', 'инвестиции', 'политика', 'госдолг'];
  const scored = items.map(item => {
    const text = `${item.title} ${item.source}`.toLowerCase();
    const matches = keywords.filter(k => text.includes(k)).length;
    // Freshness factor: newer items get higher weight (days since publication)
    const ageDays = item.pubDate ? (Date.now() - new Date(item.pubDate)) / (1000 * 60 * 60 * 24) : 30;
    const freshness = Math.max(0, 1 - ageDays / 30); // 0‑1 range for up to 30 days
    const score = (matches * 0.6) + (freshness * 0.4);
    return { ...item, score };
  });
  return scored.sort((a, b) => b.score - a.score);
}

module.exports = { fetchNews, scoreNews };
