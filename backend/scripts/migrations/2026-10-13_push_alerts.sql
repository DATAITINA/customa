-- Leftover-food alerts: phones subscribed to a stand's push notifications.
-- New table only (no change to existing tables). Run on Neon BEFORE deploying the backend.
-- Safe to run twice.

CREATE TABLE IF NOT EXISTS pushsubscription (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    endpoint VARCHAR NOT NULL,         -- the browser's push service URL
    p256dh VARCHAR NOT NULL,
    auth VARCHAR NOT NULL,
    CONSTRAINT pushsubscription_workspace_id_endpoint_key UNIQUE (workspace_id, endpoint)
);
CREATE INDEX IF NOT EXISTS ix_pushsubscription_workspace_id ON pushsubscription (workspace_id);
CREATE INDEX IF NOT EXISTS ix_pushsubscription_customer_id ON pushsubscription (customer_id);
