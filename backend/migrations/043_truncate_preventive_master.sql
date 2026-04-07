-- Migration 043: Truncate preventive_master for clean re-seed
--
-- The seeder only populates when the table is empty. Items added to
-- SEED_DATA after the initial seed (e.g. Kennel Cough, CCoV) were
-- never inserted. Truncating lets the seeder run fresh on next startup
-- and insert all current SEED_DATA items.
--
-- Safe: preventive_master is a frozen reference table with no user data.
-- CASCADE removes dependent FK references if any exist.

BEGIN;

TRUNCATE preventive_master CASCADE;

COMMIT;
