-- Migration 016: Add dashboard_link_pending flag to users table
--
-- When _finalize_onboarding() fires while document extractions are still
-- in-flight (extraction_status='pending'), the dashboard link is held back
-- and this flag is set to TRUE. Once all pending extractions complete,
-- the deferred care-plan message appends the dashboard link and clears
-- this flag.
--
-- Safe to re-run: uses IF NOT EXISTS / idempotent ALTER.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS dashboard_link_pending BOOLEAN NOT NULL DEFAULT FALSE;
