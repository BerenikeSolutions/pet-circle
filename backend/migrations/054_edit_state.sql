-- Migration 054: Add edit_state and edit_data columns to users table
-- Supports the agentic WhatsApp edit flow for post-onboarding profile corrections.

ALTER TABLE users ADD COLUMN IF NOT EXISTS edit_state VARCHAR(30);
ALTER TABLE users ADD COLUMN IF NOT EXISTS edit_data  JSONB;
