-- Leftover-food alerts by text message: a customer's phone number per stand, with when they agreed.
-- New table only (no change to existing tables). Run on Neon BEFORE deploying the backend.
-- Safe to run twice.

CREATE TABLE IF NOT EXISTS smssubscription (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    phone VARCHAR NOT NULL,            -- international digits, e.g. 2348031234567
    agreed_at TIMESTAMP NOT NULL,      -- when the customer agreed to get texts
    terms_version VARCHAR NOT NULL,    -- which wording they agreed to
    CONSTRAINT smssubscription_workspace_id_customer_id_key UNIQUE (workspace_id, customer_id),
    CONSTRAINT smssubscription_workspace_id_phone_key UNIQUE (workspace_id, phone)
);
CREATE INDEX IF NOT EXISTS ix_smssubscription_workspace_id ON smssubscription (workspace_id);
CREATE INDEX IF NOT EXISTS ix_smssubscription_customer_id ON smssubscription (customer_id);
