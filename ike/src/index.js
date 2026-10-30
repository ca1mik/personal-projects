// src/index.js
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const logger = require('./utils/logger');
const assistantRoutes = require('./routes/assistantRoutes');

const app = express();
app.use(cors());
app.use(express.json());
app.use('/api', assistantRoutes);

const PORT = process.env.PORT || 4000;

if (require.main === module) {
  app.listen(PORT, () => {
    logger.info(`Backend listening on port ${PORT}`);
    console.log(`Backend listening on port ${PORT}`);
  });
}

module.exports = app;
