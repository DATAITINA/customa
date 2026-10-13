-- Animal characters: panda, chick, bunny and cat join the character bodies.
-- Adds values to the existing enum type only (no data changes). Run on Neon BEFORE deploying
-- the backend. Safe to run twice.

ALTER TYPE characterbody ADD VALUE IF NOT EXISTS 'panda';
ALTER TYPE characterbody ADD VALUE IF NOT EXISTS 'chick';
ALTER TYPE characterbody ADD VALUE IF NOT EXISTS 'bunny';
ALTER TYPE characterbody ADD VALUE IF NOT EXISTS 'cat';
