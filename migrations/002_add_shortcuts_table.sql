-- Add shortcuts table
CREATE TABLE IF NOT EXISTS shortcuts (
    action_id TEXT PRIMARY KEY,
    shortcut TEXT NOT NULL
);