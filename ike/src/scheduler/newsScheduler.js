// src/scheduler/newsScheduler.js
const cron = require('node-cron');
const { fetchNews, scoreNews } = require('../pipeline/news');
const logger = require('../utils/logger');
const path = require('path');
const fs = require('fs');

// Save top 10 scored news to data/news_scored.json
async function runNewsJob() {
  const raw = await fetchNews();
  const scored = scoreNews(raw);
  const top = scored.slice(0, 10);
  const outPath = path.resolve(__dirname, '..', '..', 'data', 'news_scored.json');
  fs.writeFileSync(outPath, JSON.stringify(top, null, 2));
  logger.info(`Saved ${top.length} scored news items to ${outPath}`);
}

// Schedule every 6 hours
cron.schedule('0 */6 * * *', () => {
  logger.info('Running scheduled news fetch job');
  runNewsJob().catch(err => logger.error('News job error: ' + err.message));
});

module.exports = { runNewsJob };
