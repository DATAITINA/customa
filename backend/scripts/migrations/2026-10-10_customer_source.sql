-- Save how a customer first arrived ("qr" = scanned the stand's QR code).
-- Nullable, no default: existing customers stay NULL and keep the stand's normal window.
-- Run on Neon BEFORE deploying the backend that reads customer.source. Safe to run twice.
ALTER TABLE customer ADD COLUMN IF NOT EXISTS source VARCHAR;
