-- Plate Ajo: prepaid plates at a locked price (platebundle) and each prepaid plate served (plateuse).
-- New tables only; no change to existing tables. Money is never stored, only the plate count.
-- Run on Neon BEFORE deploying the backend that serves /ajo routes. Safe to run twice.

CREATE TABLE IF NOT EXISTS platebundle (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    item VARCHAR NOT NULL,
    unit_price INTEGER NOT NULL,
    plates_total INTEGER NOT NULL,
    plates_used INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL DEFAULT 'pending',
    payer_name VARCHAR,
    confirmed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_platebundle_workspace_id ON platebundle (workspace_id);
CREATE INDEX IF NOT EXISTS ix_platebundle_customer_id ON platebundle (customer_id);
CREATE INDEX IF NOT EXISTS ix_platebundle_status ON platebundle (status);

CREATE TABLE IF NOT EXISTS plateuse (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    bundle_id INTEGER NOT NULL REFERENCES platebundle(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    plate_number INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_plateuse_workspace_id ON plateuse (workspace_id);
CREATE INDEX IF NOT EXISTS ix_plateuse_bundle_id ON plateuse (bundle_id);
CREATE INDEX IF NOT EXISTS ix_plateuse_customer_id ON plateuse (customer_id);
