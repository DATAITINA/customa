-- Save your card / "Already have a card?": a customer's card follows them to any browser.
-- New tables only (no change to existing tables). Run on Neon BEFORE deploying the backend.
-- Safe to run twice.

CREATE TABLE IF NOT EXISTS customerphone (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL UNIQUE REFERENCES customer(id),
    phone_hash VARCHAR NOT NULL,   -- keyed hash of the number; the number itself is never stored
    phone_masked VARCHAR NOT NULL, -- "0803 ••• 4521"
    pin_hash VARCHAR NOT NULL,     -- bcrypt (msflib.core.security), PIN peppered with SECRET_KEY
    UNIQUE (workspace_id, phone_hash)
);
CREATE INDEX IF NOT EXISTS ix_customerphone_workspace_id ON customerphone (workspace_id);
CREATE INDEX IF NOT EXISTS ix_customerphone_phone_hash ON customerphone (phone_hash);

CREATE TABLE IF NOT EXISTS customerdevicekey (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    key VARCHAR NOT NULL,
    came_from_customer_id INTEGER REFERENCES customer(id) ON DELETE SET NULL,
    UNIQUE (workspace_id, key)
);
CREATE INDEX IF NOT EXISTS ix_customerdevicekey_workspace_id ON customerdevicekey (workspace_id);
CREATE INDEX IF NOT EXISTS ix_customerdevicekey_customer_id ON customerdevicekey (customer_id);
CREATE INDEX IF NOT EXISTS ix_customerdevicekey_key ON customerdevicekey (key);

CREATE TABLE IF NOT EXISTS recoveryattempt (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    phone_hash VARCHAR NOT NULL,
    ip_hash VARCHAR NOT NULL,
    customer_id INTEGER REFERENCES customer(id) ON DELETE SET NULL,
    kind VARCHAR NOT NULL,    -- link, pin, sms_send, sms_code
    outcome VARCHAR NOT NULL  -- ok, wrong, locked, limited, taken, sent, skipped
);
CREATE INDEX IF NOT EXISTS ix_recoveryattempt_workspace_id ON recoveryattempt (workspace_id);
CREATE INDEX IF NOT EXISTS ix_recoveryattempt_phone_hash ON recoveryattempt (phone_hash);
CREATE INDEX IF NOT EXISTS ix_recoveryattempt_ip_hash ON recoveryattempt (ip_hash);

CREATE TABLE IF NOT EXISTS recoverycode (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    phone_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_recoverycode_workspace_id ON recoverycode (workspace_id);
CREATE INDEX IF NOT EXISTS ix_recoverycode_phone_hash ON recoverycode (phone_hash);
