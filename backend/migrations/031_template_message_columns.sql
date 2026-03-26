-- Migration 031: Add template_name, template_params, message_body to reminders and nudge_delivery_log
--
-- Purpose:
--   Record the exact WhatsApp template used and the fully rendered message body
--   for every reminder and nudge sent, enabling complete audit trails without
--   parsing message_logs.payload JSONB.
--
--   template_name   — the approved WhatsApp template name (e.g. petcircle_reminder_t7_v1)
--   template_params — interpolated parameter list as a JSON array
--                     e.g. ["John", "Max", "Rabies", "30 Mar 2026"]
--   message_body    — fully rendered message text after substituting params into body_text
--
-- Safe to run on populated tables (nullable columns, IF NOT EXISTS guards).

BEGIN;

ALTER TABLE reminders
    ADD COLUMN IF NOT EXISTS template_name   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS template_params JSONB,
    ADD COLUMN IF NOT EXISTS message_body    TEXT;

ALTER TABLE nudge_delivery_log
    ADD COLUMN IF NOT EXISTS template_name   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS template_params JSONB,
    ADD COLUMN IF NOT EXISTS message_body    TEXT;

COMMIT;
