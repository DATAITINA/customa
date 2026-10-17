-- Plan the next visit ("When you go come back?"): one active plan per customer per stand, its
-- reminder and its outcome. New table only (no change to existing tables). Run on Neon BEFORE
-- deploying the backend. Safe to run twice.

CREATE TABLE IF NOT EXISTS visitplan (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    day DATE NOT NULL,                       -- Nigeria time
    slot VARCHAR NOT NULL,                   -- morning, lunch or evening
    status VARCHAR NOT NULL DEFAULT 'active', -- active, kept, missed, cancelled
    reminder_due_at TIMESTAMP,               -- UTC, about 1 hour before the slot
    reminder_sent_at TIMESTAMP,              -- set once, before sending (never twice)
    reminder_channel VARCHAR,                -- push, sms or none
    kept_visit_id INTEGER REFERENCES visit(id) ON DELETE SET NULL,
    noted_visit_id INTEGER REFERENCES visit(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_visitplan_workspace_id ON visitplan (workspace_id);
CREATE INDEX IF NOT EXISTS ix_visitplan_customer_id ON visitplan (customer_id);
