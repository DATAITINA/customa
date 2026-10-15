-- Pay for a plate (Paystack test mode, or cash the vendor confirms). New table only (no change to
-- existing tables). Run on Neon BEFORE deploying the backend. Safe to run twice.

CREATE TABLE IF NOT EXISTS payment (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    customer_id INTEGER REFERENCES customer(id) ON DELETE SET NULL, -- empty after "Delete my data"
    reference VARCHAR NOT NULL UNIQUE,         -- ours, also the Paystack reference
    method VARCHAR NOT NULL,                   -- paystack or cash
    status VARCHAR NOT NULL DEFAULT 'pending', -- pending, paid, failed, cancelled
    item VARCHAR NOT NULL,
    amount_naira INTEGER NOT NULL,
    match_code VARCHAR NOT NULL,               -- 3 letters the customer shows for cash
    visit_id INTEGER REFERENCES visit(id) ON DELETE SET NULL, -- the stamp it counted
    paid_at TIMESTAMP,
    confirmed_by INTEGER                       -- account id of the staff member (cash)
);
CREATE INDEX IF NOT EXISTS ix_payment_workspace_id ON payment (workspace_id);
CREATE INDEX IF NOT EXISTS ix_payment_customer_id ON payment (customer_id);
CREATE INDEX IF NOT EXISTS ix_payment_reference ON payment (reference);
