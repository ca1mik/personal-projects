// server/src/index.js
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const assistantRoutes = require('./routes/assistantRoutes');

const app = express();
app.use(cors());
app.use(express.json());
app.use('/api', assistantRoutes);

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok', ts: new Date().toISOString() }));

// Global error handler
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: err.message });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`✅ Backend listening on http://localhost:${PORT}`);
});
