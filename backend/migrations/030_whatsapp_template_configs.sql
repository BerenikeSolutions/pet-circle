-- Migration 030: whatsapp_template_configs
--
-- Purpose:
--   Create a master registry of all WhatsApp-approved templates used by PetCircle.
--   Stores the body_text (with {{1}}, {{2}} placeholders), param_count, and description
--   for each template so that the full rendered message can be reconstructed at send time.
--
-- After running this migration:
--   Update body_text for 'petcircle_onboarding_complete' and 'petcircle_order_fulfillment_check'
--   once the approved Meta template text is known.
--   Also update any body_text values that differ from the placeholder wording below.

BEGIN;

CREATE TABLE IF NOT EXISTS whatsapp_template_configs (
    template_name   VARCHAR(100) PRIMARY KEY,
    body_text       TEXT         NOT NULL DEFAULT '',
    param_count     INTEGER      NOT NULL DEFAULT 0,
    language_code   VARCHAR(10)  NOT NULL DEFAULT 'en',
    description     TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── Reminder templates (multi-stage engine) ──────────────────────────────
-- T-7: params → [parent_name, pet_name, item_desc, due_date]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_reminder_t7_v1',
    'Hi {{1}}! 🐾 Just a heads-up — {{2}}''s {{3}} is coming up on {{4}}. Please book an appointment soon.',
    4,
    'Reminder T-7: sent 7 days before due date'
)
ON CONFLICT (template_name) DO NOTHING;

-- Due: params → [parent_name, pet_name, item_desc]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_reminder_due_v1',
    'Hi {{1}}! 🐾 Today is the day — {{2}}''s {{3}} is due today. Please complete it at the earliest.',
    3,
    'Reminder Due: sent on the due date'
)
ON CONFLICT (template_name) DO NOTHING;

-- D+3: params → [parent_name, pet_name, item_desc, original_due_date]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_reminder_d3_v1',
    'Hi {{1}}! 🐾 Just checking in — {{2}}''s {{3}} was due on {{4}}. Have you been able to get it done?',
    4,
    'Reminder D+3: follow-up 3 days after due date'
)
ON CONFLICT (template_name) DO NOTHING;

-- Overdue insight: params → [parent_name, pet_name, item_desc, days_overdue, breed_consequence]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_reminder_overdue_v1',
    'Hi {{1}}! ⚠️ {{2}}''s {{3}} is now {{4}} days overdue. {{5}} Please consult your vet as soon as possible.',
    5,
    'Overdue insight: monthly follow-up with breed-specific consequence'
)
ON CONFLICT (template_name) DO NOTHING;

-- ─── Nudge templates ──────────────────────────────────────────────────────
-- Level 0/1 static value-add: no params
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_nudge_va_static_v1',
    'Did you know? Regular preventive care can add years to your pet''s life. PetCircle helps you stay on top of every milestone. 🐾',
    0,
    'Level 0/1 static value-add nudge — no variables'
)
ON CONFLICT (template_name) DO NOTHING;

-- Level 1 engagement: params → [var1, var2]  (from NudgeMessageLibrary.template_var_1/2)
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_nudge_engagement_v1',
    '{{1}} {{2}}',
    2,
    'Level 1 engagement nudge — 2 vars from NudgeMessageLibrary'
)
ON CONFLICT (template_name) DO NOTHING;

-- Level 1 breed: params → [var1, var2]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_nudge_breed_v1',
    '{{1}} {{2}}',
    2,
    'Level 1 breed-info nudge — 2 vars from NudgeMessageLibrary'
)
ON CONFLICT (template_name) DO NOTHING;

-- Level 2 breed+data: params → [var1, var2, var3 (category), var4]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_nudge_breed_data_v1',
    '{{1}} {{2}} 📌 *{{3}}*: {{4}}',
    4,
    'Level 2 breed + data nudge — 4 vars from NudgeMessageLibrary'
)
ON CONFLICT (template_name) DO NOTHING;

-- Level 2 personalized: params → [pet_name, gpt_insight]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_nudge_va_personal_v1',
    '🐾 {{1}} — {{2}}',
    2,
    'Level 2 GPT-personalized value-add nudge — pet_name + insight'
)
ON CONFLICT (template_name) DO NOTHING;

-- ─── Legacy / other templates ─────────────────────────────────────────────
-- Legacy reminder (upcoming): params → [pet_name, item_name, due_date]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_reminder',
    '🐾 Reminder: {{1}}''s {{2}} is due on {{3}}. Please schedule an appointment.',
    3,
    'Legacy upcoming reminder (pre-stage engine)'
)
ON CONFLICT (template_name) DO NOTHING;

-- Legacy overdue: params → [pet_name, item_name, due_date]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_overdue',
    '⚠️ {{1}}''s {{2}} was due on {{3}} and is now overdue. Please consult your vet.',
    3,
    'Legacy overdue reminder (pre-stage engine)'
)
ON CONFLICT (template_name) DO NOTHING;

-- Legacy nudge: no params
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_nudge',
    'Stay on top of your pet''s health with PetCircle! Check the dashboard for upcoming preventive care. 🐾',
    0,
    'Legacy nudge (pre-scheduler)'
)
ON CONFLICT (template_name) DO NOTHING;

-- Conflict: params → [pet_name, item_name, existing_date, new_date]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_conflict',
    'We found a date conflict for {{1}}''s {{2}}. Existing date: {{3}}. New date from document: {{4}}. Please choose which date to keep.',
    4,
    'Conflict resolution — user must choose between two dates'
)
ON CONFLICT (template_name) DO NOTHING;

-- Onboarding complete: update body_text + param_count to match approved Meta template
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_onboarding_complete',
    '',
    0,
    'Onboarding done confirmation — update body_text to match approved Meta template'
)
ON CONFLICT (template_name) DO NOTHING;

-- Order fulfillment check: update body_text + param_count to match approved Meta template
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_order_fulfillment_check',
    '',
    0,
    'Order follow-up check — update body_text to match approved Meta template'
)
ON CONFLICT (template_name) DO NOTHING;

-- Birthday: params → [pet_name, birthday_date]
INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description) VALUES
(
    'petcircle_birthday',
    '🎂 Happy Birthday {{1}}! Wishing {{1}} a wonderful birthday on {{2}}. Give them extra treats today! 🐾',
    2,
    'Birthday wish — pet_name + birthday date'
)
ON CONFLICT (template_name) DO NOTHING;

COMMIT;
