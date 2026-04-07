-- Migration 040: Drop obsolete agent_onboarding_sessions table
--
-- Agentic onboarding has been removed from the codebase, so this table is no
-- longer used. Keep migration 014 for historical integrity; this migration
-- performs forward cleanup in deployed environments.
--
-- Safe to re-run: uses IF EXISTS.

BEGIN;

DROP TABLE IF EXISTS agent_onboarding_sessions;

COMMIT;
