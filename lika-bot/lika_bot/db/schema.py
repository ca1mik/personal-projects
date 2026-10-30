SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    chat_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_interaction_at TEXT,
    intro_completed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    detected_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    UNIQUE(user_id, video_id)
);

CREATE TABLE IF NOT EXISTS messages_progress (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    intro_seen_at TEXT,
    special_opened_at TEXT,
    final_opened_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_key TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    sent_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_text TEXT,
    UNIQUE(user_id, notification_key)
);

CREATE TABLE IF NOT EXISTS personal_messages_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_key TEXT NOT NULL,
    cycle INTEGER NOT NULL DEFAULT 1,
    delivered_at TEXT NOT NULL,
    UNIQUE(user_id, message_key, cycle)
);

CREATE INDEX IF NOT EXISTS idx_videos_category_active ON videos(category, is_active);
CREATE INDEX IF NOT EXISTS idx_sent_videos_user ON sent_videos(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_user ON scheduled_notifications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_personal_messages_user ON personal_messages_progress(user_id, cycle);
"""
