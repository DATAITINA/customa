-- Lunch Crew: friends share one card at a stand; each crew jara goes to the next member in turn.
-- New tables only (no change to existing tables). Run on Neon BEFORE deploying the backend.
-- Safe to run twice.

CREATE TABLE IF NOT EXISTS crew (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    name VARCHAR NOT NULL,
    code VARCHAR NOT NULL,             -- invite code in the share link
    plate_count INTEGER NOT NULL DEFAULT 0,
    next_turn INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_crew_workspace_id ON crew (workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_crew_code ON crew (code);

CREATE TABLE IF NOT EXISTS crewmember (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    crew_id INTEGER NOT NULL REFERENCES crew(id),
    customer_id INTEGER NOT NULL REFERENCES customer(id),
    position INTEGER NOT NULL,         -- join order
    CONSTRAINT crewmember_workspace_id_customer_id_key UNIQUE (workspace_id, customer_id)
);
CREATE INDEX IF NOT EXISTS ix_crewmember_workspace_id ON crewmember (workspace_id);
CREATE INDEX IF NOT EXISTS ix_crewmember_crew_id ON crewmember (crew_id);
CREATE INDEX IF NOT EXISTS ix_crewmember_customer_id ON crewmember (customer_id);

-- Marks a visit as a crew plate. crew_id becomes NULL when an empty crew is deleted, so the
-- visit still never counts on the scanner's own card.
CREATE TABLE IF NOT EXISTS crewplate (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
    crew_id INTEGER REFERENCES crew(id) ON DELETE SET NULL,
    visit_id INTEGER NOT NULL REFERENCES visit(id),
    recipient_customer_id INTEGER REFERENCES customer(id) ON DELETE SET NULL,
    CONSTRAINT crewplate_visit_id_key UNIQUE (visit_id)
);
CREATE INDEX IF NOT EXISTS ix_crewplate_workspace_id ON crewplate (workspace_id);
CREATE INDEX IF NOT EXISTS ix_crewplate_crew_id ON crewplate (crew_id);
-- If an earlier build already created crewplate with crew_id NOT NULL, allow NULL now.
ALTER TABLE crewplate ALTER COLUMN crew_id DROP NOT NULL;
