-- Stand photos: one photo of the food stand per stand (shrunk on the phone before upload).
-- New table only (no change to existing tables). Run on Neon BEFORE deploying the backend.
-- Safe to run twice.

CREATE TABLE IF NOT EXISTS standphoto (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    content_type VARCHAR NOT NULL,
    data VARCHAR NOT NULL,             -- base64
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_standphoto_workspace_id ON standphoto (workspace_id);
