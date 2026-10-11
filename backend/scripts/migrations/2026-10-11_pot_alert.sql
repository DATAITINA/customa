-- Pot Alert: customers who want to hear when a dish is ready, and the vendor's "ready now" calls.
-- New tables only. Run on Neon BEFORE deploying the backend that uses them. Safe to run twice.

CREATE TABLE IF NOT EXISTS potwatch (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    item VARCHAR NOT NULL,
    -- Normalised to 234XXXXXXXXXX. Shown only to the stand's vendor.
    phone VARCHAR NOT NULL,
    CONSTRAINT potwatch_workspace_id_customer_id_item_key UNIQUE (workspace_id, customer_id, item)
);
CREATE INDEX IF NOT EXISTS ix_potwatch_workspace_id ON potwatch (workspace_id);
CREATE INDEX IF NOT EXISTS ix_potwatch_customer_id ON potwatch (customer_id);

CREATE TABLE IF NOT EXISTS potready (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    item VARCHAR NOT NULL,
    plates_left INTEGER,
    ended BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_potready_workspace_id ON potready (workspace_id);
