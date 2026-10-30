// src/routes/assistantRoutes.js
const express = require('express');
const { v4: uuidv4 } = require('uuid');
const logger = require('../utils/logger');
const db = require('../utils/db');
const { analyzeChannel } = require('../pipeline/analysis');
const { buildAudienceHypothesis } = require('../pipeline/hypothesis');
const { parseBrief } = require('../pipeline/brief');
const { fetchNews, scoreNews } = require('../pipeline/news');
const { generateScene, assembleScript } = require('../pipeline/generator');
const { postprocessScript } = require('../pipeline/postprocess');
const path = require('path');
const fs = require('fs');

const router = express.Router();

/**
 * POST /api/runPipeline
 * Body: { channelId: string, brief?: string }
 * Returns: { runId, status }
 */
router.post('/runPipeline', async (req, res) => {
  const { channelId, brief } = req.body;
  if (!channelId) return res.status(400).json({ error: 'channelId required' });

  const runId = uuidv4();
  const createdAt = new Date().toISOString();
  db.run(
    `INSERT INTO runs (id, channelId, status, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?)`,
    [runId, channelId, 'STARTED', createdAt, createdAt],
    err => {
      if (err) logger.error('DB insert error: ' + err.message);
    }
  );

  // Async pipeline – fire‑and‑forget, user can poll status later
  (async () => {
    try {
      logger.info(`Pipeline started for run ${runId}`);
      const analytics = await analyzeChannel(channelId);

      const audience = await buildAudienceHypothesis(analytics);

      const briefObj = brief ? parseBrief(brief) : {};

      const rawNews = await fetchNews();
      const scoredNews = scoreNews(rawNews);
      const topNews = scoredNews.filter(item => item.score >= (require('../config').newsScoreThreshold));

      // Generate 5 scenes as example
      const scenes = [];
      const previousSummaries = [];
      for (let i = 1; i <= 5; i++) {
        const scene = await generateScene(i, { audience, brief: briefObj, topNews, previousSummaries });
        if (scene) {
          scenes.push(scene);
          previousSummaries.push(scene.content);
        }
      }

      const rawScript = assembleScript(scenes);
      const { cleanedScript, qualityScore } = await postprocessScript(rawScript);

      const outDir = path.resolve(__dirname, '..', '..', 'data', 'scenarios', runId);
      fs.mkdirSync(outDir, { recursive: true });
      const scriptPath = path.join(outDir, 'full.md');
      fs.writeFileSync(scriptPath, cleanedScript);

      // Update DB status
      const finishedAt = new Date().toISOString();
      db.run(
        `UPDATE runs SET status = ?, updatedAt = ? WHERE id = ?`,
        [qualityScore >= 0.8 ? 'COMPLETED' : 'FAILED', finishedAt, runId],
        err => {
          if (err) logger.error('DB update error: ' + err.message);
        }
      );

      logger.info(`Pipeline finished for run ${runId} with score ${qualityScore}`);
    } catch (e) {
      logger.error(`Pipeline error for run ${runId}: ${e.message}`);
      db.run(`UPDATE runs SET status = ?, updatedAt = ? WHERE id = ?`, ['ERROR', new Date().toISOString(), runId]);
    }
  })();

  res.json({ runId, status: 'STARTED' });
});

/**
 * GET /api/status/:runId
 */
router.get('/status/:runId', (req, res) => {
  const { runId } = req.params;
  db.get('SELECT status, updatedAt FROM runs WHERE id = ?', [runId], (err, row) => {
    if (err) return res.status(500).json({ error: err.message });
    if (!row) return res.status(404).json({ error: 'Run not found' });
    res.json({ runId, status: row.status, updatedAt: row.updatedAt });
  });
});

/**
 * GET /api/result/:runId – returns the script file if completed.
 */
router.get('/result/:runId', (req, res) => {
  const { runId } = req.params;
  const scriptPath = path.resolve(__dirname, '..', '..', 'data', 'scenarios', runId, 'full.md');
  if (fs.existsSync(scriptPath)) {
    res.sendFile(scriptPath);
  } else {
    res.status(404).json({ error: 'Result not ready' });
  }
});

module.exports = router;
