-- Private chat memory with the stand character: one row per customer.
-- New table only (no change to existing tables). Run on Neon BEFORE deploying the backend.
-- Safe to run twice.

CREATE TABLE IF NOT EXISTS chatmemory (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    visit_id INTEGER REFERENCES visit(id),   -- the plate this visit's chat belongs to
    messages_used INTEGER NOT NULL DEFAULT 0,
    closed BOOLEAN NOT NULL DEFAULT FALSE,
    opener VARCHAR,
    favourite_item VARCHAR,
    last_item VARCHAR,
    follow_up VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_chatmemory_workspace_id ON chatmemory (workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_chatmemory_customer_id ON chatmemory (customer_id);
