-- Migration 033: Reminder Sub-Type Column + Scheduled Template Configs
--
-- Adds sub_type to the reminders table to distinguish between two reminder flows
-- for food, supplement, and chronic medicine categories:
--
--   'supply_led' — triggered by calculated supply date (pack_size ÷ daily_portion)
--                  fires T-7 before supply runs out. Existing behaviour.
--
--   'scheduled'  — triggered at O+21 for first-time users with no supply data.
--                  Messages ask the user to check stock and reorder if needed.
--                  Lists ALL current items of that category in the message body.
--                  Repeats every 30 days until a supply-led reminder takes over.
--
-- NULL in sub_type means legacy reminder — treated identically to 'supply_led'.
--
-- Also registers 3 new WhatsApp template config placeholder rows for
-- the Scheduled variant messages.
--
-- Source: PetCircle_Nudges_v6.xlsx — Reminders sheet
-- Safe to re-run: ADD COLUMN IF NOT EXISTS; ON CONFLICT DO NOTHING.

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- Add sub_type column to reminders table
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS sub_type VARCHAR(30);

COMMENT ON COLUMN reminders.sub_type IS
  'supply_led = triggered by pack supply countdown; scheduled = O+21 first-time prompt; NULL = legacy (treated as supply_led)';

-- ─────────────────────────────────────────────────────────────────────────────
-- Register placeholder WhatsApp template configs for Scheduled variants
-- body_text will be updated once Meta approves the templates.
--
-- Scheduled template variable mapping:
--   {{1}} = parent_name
--   {{2}} = pet_name
--   {{3}} = all current items of that category (bullet list string)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO whatsapp_template_configs
  (template_name, body_text, param_count, language_code, description)
VALUES
(
  'petcircle_reminder_food_scheduled_v1',
  'Hi {{1}} 🐾 Time for a quick check — how''s {{2}}''s food supply looking? If you''re getting low, tap below to reorder and keep their routine on track.

{{3}}

PetCircle is here for you.',
  3,
  'en',
  'Food order scheduled reminder. Fires at O+21 for first-time users. {{1}}=parent_name, {{2}}=pet_name, {{3}}=food items list. Repeats every 30 days.'
),
(
  'petcircle_reminder_supplement_scheduled_v1',
  'Hi {{1}} 🐾 Quick reminder to check {{2}}''s supplement supply! Running low on any of them? Tap below to reorder and keep their daily routine on track.

{{3}}

PetCircle is here for you.',
  3,
  'en',
  'Supplement scheduled reminder. Fires at O+21 for first-time users. {{1}}=parent_name, {{2}}=pet_name, {{3}}=supplement items list. Repeats every 30 days.'
),
(
  'petcircle_reminder_chronic_scheduled_v1',
  'Hi {{1}} 🐾 Quick reminder to check {{2}}''s medicine supply! Running low on any of them? Tap below to reorder and keep their daily routine on track.

{{3}}

PetCircle is here for you.',
  3,
  'en',
  'Chronic medicine scheduled reminder. Fires at O+21 for first-time users. {{1}}=parent_name, {{2}}=pet_name, {{3}}=medicine list. Repeats every 30 days.'
)
ON CONFLICT (template_name) DO NOTHING;

COMMIT;
