-- migrations/001_initial_schema.sql

-- Topics table: Stores information about each piece of knowledge.
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY, -- Unique identifier for the topic (UUID)
    parent_id TEXT,      -- ID of the parent topic in the hierarchy (NULL for root topics)
    title TEXT NOT NULL, -- User-defined or auto-generated title for the topic
    text_file_uuid TEXT NOT NULL UNIQUE, -- UUID linking to the .txt file containing the topic's content
    created_at TIMESTAMP NOT NULL,       -- Timestamp of when the topic was created
    updated_at TIMESTAMP NOT NULL,       -- Timestamp of when the topic was last updated
    display_order INTEGER,               -- Optional: for manual ordering of sibling topics
    FOREIGN KEY (parent_id) REFERENCES topics (id) ON DELETE CASCADE -- If a parent is deleted, its children are also deleted
);

-- Extractions table: Links extracted text segments (child topics) to their source (parent topics).
CREATE TABLE IF NOT EXISTS extractions (
    id TEXT PRIMARY KEY, -- Unique identifier for the extraction record (UUID)
    parent_topic_id TEXT NOT NULL,      -- ID of the topic from which text was extracted
    child_topic_id TEXT NOT NULL UNIQUE,-- ID of the new topic created with the extracted text
    parent_text_start_char INTEGER NOT NULL, -- Start character offset of the extraction in the parent's text file
    parent_text_end_char INTEGER NOT NULL,   -- End character offset of the extraction in the parent's text file
    FOREIGN KEY (parent_topic_id) REFERENCES topics (id) ON DELETE CASCADE,
    FOREIGN KEY (child_topic_id) REFERENCES topics (id) ON DELETE CASCADE
);

-- Optional: Indexes for frequently queried columns to improve performance
CREATE INDEX IF NOT EXISTS idx_topics_parent_id ON topics (parent_id);
CREATE INDEX IF NOT EXISTS idx_extractions_parent_topic_id ON extractions (parent_topic_id);
CREATE INDEX IF NOT EXISTS idx_extractions_child_topic_id ON extractions (child_topic_id);