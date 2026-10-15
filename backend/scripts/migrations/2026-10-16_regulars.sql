-- Regular-arrived alert ("Ime don land!"): arrivals for "Who's here now", the customer's own
-- "my usual", and vendors' phones that asked for a ping. New tables only (no change to existing
-- tables). Run on Neon BEFORE deploying the backend. Safe to run twice.

CREATE TABLE IF NOT EXISTS arrival (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,   -- when the plate was counted
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    visit_id INTEGER NOT NULL UNIQUE REFERENCES visit(id) ON DELETE CASCADE,
    visit_number INTEGER NOT NULL,           -- the customer's nth plate at this stand
    previous_at TIMESTAMP,                   -- their plate before this one
    greeted_at TIMESTAMP,                    -- staff tapped "Greeted"
    pinged_at TIMESTAMP                      -- the vendor's phones were pinged
);
CREATE INDEX IF NOT EXISTS ix_arrival_workspace_id ON arrival (workspace_id);
CREATE INDEX IF NOT EXISTS ix_arrival_customer_id ON arrival (customer_id);

CREATE TABLE IF NOT EXISTS customerusual (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL UNIQUE REFERENCES customer(id),
    item VARCHAR NOT NULL                    -- a menu item the customer picked
);
CREATE INDEX IF NOT EXISTS ix_customerusual_workspace_id ON customerusual (workspace_id);

CREATE TABLE IF NOT EXISTS vendorpushsubscription (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    account_id INTEGER NOT NULL REFERENCES account(id),
    endpoint VARCHAR NOT NULL,
    p256dh VARCHAR NOT NULL,
    auth VARCHAR NOT NULL,
    CONSTRAINT vendorpushsubscription_workspace_id_endpoint_key UNIQUE (workspace_id, endpoint)
);
CREATE INDEX IF NOT EXISTS ix_vendorpushsubscription_workspace_id ON vendorpushsubscription (workspace_id);
CREATE INDEX IF NOT EXISTS ix_vendorpushsubscription_account_id ON vendorpushsubscription (account_id);
