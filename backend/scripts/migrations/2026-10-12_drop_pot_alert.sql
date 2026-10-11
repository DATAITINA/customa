-- Pot Alert was removed from Customa. This drops its two tables and their data
-- (customers' WhatsApp numbers and "ready now" calls). Destructive: run only when approved.
-- Safe to run twice.
DROP TABLE IF EXISTS potwatch;
DROP TABLE IF EXISTS potready;
