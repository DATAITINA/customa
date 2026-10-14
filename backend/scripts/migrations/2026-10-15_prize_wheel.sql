-- Prize Wheel: the vendor's food prizes and each jara's spin. New tables only (no change to
-- existing tables). Run on Neon BEFORE deploying the backend. Safe to run twice.

CREATE TABLE IF NOT EXISTS wheelitem (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    position INTEGER NOT NULL DEFAULT 0,
    name VARCHAR NOT NULL,
    description VARCHAR,
    prize VARCHAR,
    weight INTEGER NOT NULL DEFAULT 3,       -- 1 rarely, 3 sometimes, 5 often
    available BOOLEAN NOT NULL DEFAULT TRUE,
    photo_type VARCHAR,
    photo_data VARCHAR,                      -- base64, shrunk on the phone
    photo_version INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_wheelitem_workspace_id ON wheelitem (workspace_id);

CREATE TABLE IF NOT EXISTS jaraprize (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,   -- when the wheel was spun
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    jara_id INTEGER NOT NULL UNIQUE REFERENCES jarareward(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    item_id INTEGER REFERENCES wheelitem(id) ON DELETE SET NULL,
    name VARCHAR NOT NULL,
    prize VARCHAR,
    photo_path VARCHAR,
    wheel VARCHAR NOT NULL,                  -- the wheel at the spin (JSON)
    slot INTEGER NOT NULL,
    landing DOUBLE PRECISION NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    redeemed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_jaraprize_workspace_id ON jaraprize (workspace_id);
CREATE INDEX IF NOT EXISTS ix_jaraprize_customer_id ON jaraprize (customer_id);
