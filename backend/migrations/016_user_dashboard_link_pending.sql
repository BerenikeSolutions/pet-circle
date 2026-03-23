-- Migration 016: Add dashboard_link_pending flag to users table
--
-- When _finalize_onboarding() fires while document extractions are still
-- in-flight (extraction_status='pending'), the dashboard link is held back
-- and this flag is set to TRUE. Once all pending extractions complete,
-- _send_extraction_summary() appends the dashboard link to the summary
-- message and clears this flag.
--
-- Safe to re-run: uses IF NOT EXISTS / idempotent ALTER.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS dashboard_link_pending BOOLEAN NOT NULL DEFAULT FALSE;
