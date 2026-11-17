-- Migration 001: add optimistic-locking version to locations.
--
-- For databases created from the baseline schema (commit 8b68e36),
-- where locations had no version column. Existing rows get version 1.
--
-- docs/schema.sql already contains this column, so a fresh database
-- does not need the migration. IF NOT EXISTS makes a repeated run
-- (or a run on a fresh database) a harmless no-op instead of an error.

BEGIN;

ALTER TABLE locations
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1
CHECK (version > 0);

COMMIT;
