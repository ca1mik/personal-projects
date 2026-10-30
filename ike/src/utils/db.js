// src/utils/db.js
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const config = require('./config');

const dbPath = path.resolve(__dirname, '..', config.dataDir, 'database.sqlite');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Failed to connect to SQLite DB:', err);
  } else {
    console.log('Connected to SQLite DB at', dbPath);
  }
});

// Initialize tables if not exist
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    channelId TEXT,
    brief TEXT,
    status TEXT,
    createdAt TEXT,
    updatedAt TEXT
  )`);
});

module.exports = db;
