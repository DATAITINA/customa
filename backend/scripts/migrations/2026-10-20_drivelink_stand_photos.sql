-- MSFLib drivelink (the vendor's file drive) and stand photos kept in it. New tables only.
-- drivelinknode is MSFLib's own table, generated from msflib.drivelink.models.DrivelinkNode.
-- Run on Neon BEFORE deploying the backend. Safe to run twice.

DO $$ BEGIN
    CREATE TYPE drivelinkkind AS ENUM ('folder', 'file');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS drivelinknode (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    drivelink_id INTEGER,
    account_id INTEGER NOT NULL REFERENCES account(id),
    workspace_id INTEGER,
    parent_id INTEGER REFERENCES drivelinknode(id),
    kind drivelinkkind NOT NULL,
    name VARCHAR(512) NOT NULL,
    path VARCHAR(4096) NOT NULL,
    storage_method VARCHAR(32),
    storage_url VARCHAR(4096),
    storage_parent_folder VARCHAR(512),
    storage_bucket VARCHAR(512),
    storage_filename VARCHAR(512),
    mime_type VARCHAR(255),
    size_bytes INTEGER,
    checksum_sha256 VARCHAR(128),
    original_filename VARCHAR(512),
    deleted_at TIMESTAMP,
    trash_expires_at TIMESTAMP,
    version INTEGER NOT NULL,
    is_starred BOOLEAN NOT NULL,
    color_label VARCHAR(32),
    custom_properties JSON
);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_storage_filename ON drivelinknode (storage_filename);
CREATE INDEX IF NOT EXISTS ix_drivelink_owner_parent_name ON drivelinknode (account_id, parent_id, name);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_path ON drivelinknode (path);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_parent_id ON drivelinknode (parent_id);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_storage_method ON drivelinknode (storage_method);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_account_id ON drivelinknode (account_id);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_workspace_id ON drivelinknode (workspace_id);
CREATE INDEX IF NOT EXISTS ix_drivelink_owner_workspace ON drivelinknode (account_id, workspace_id, drivelink_id);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_drivelink_id ON drivelinknode (drivelink_id);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_deleted_at ON drivelinknode (deleted_at);
CREATE INDEX IF NOT EXISTS ix_drivelinknode_storage_bucket ON drivelinknode (storage_bucket);

CREATE TABLE IF NOT EXISTS standphotofile (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    node_id INTEGER NOT NULL REFERENCES drivelinknode(id),
    account_id INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_standphotofile_workspace_id ON standphotofile (workspace_id);
