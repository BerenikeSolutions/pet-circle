-- Migration 032: Update whatsapp_template_configs with new approved body texts
--
-- Reflects the template changes documented in docs/whatsapp-templates.md:
--   - All 4 reminder templates: updated body text (friendlier tone)
--   - petcircle_nudge_va_personal_v1: updated body + param_count 2→3
--   - petcircle_nudge_engagement_v1: updated body text
--   - petcircle_nudge_breed_v1: updated body text
--   - petcircle_nudge_breed_data_v1: updated body + param_count 4→5
--   - petcircle_conflict_v1: INSERT with correct versioned name + new body
--   - birthday_celebration_v1: INSERT with correct versioned name + new body
--   - order_fulfillment_check_v1: INSERT with correct versioned name + full body

BEGIN;

-- ─── Reminder templates ────────────────────────────────────────────────────

UPDATE whatsapp_template_configs
SET
    body_text   = 'Hi {{1}}! A quick heads-up from PetCircle 🐾' || E'\n\n' ||
                  '{{2}}''s {{3}} is coming up on {{4}}.' || E'\n\n' ||
                  'We''ll remind you again on the due date, but if it''s already done, just let us know below!',
    param_count = 4,
    updated_at  = NOW()
WHERE template_name = 'petcircle_reminder_t7_v1';

UPDATE whatsapp_template_configs
SET
    body_text   = 'Hi {{1}}, today is the day! 🐾' || E'\n\n' ||
                  '{{2}}''s {{3}} is due today.' || E'\n\n' ||
                  'Please let us know once it''s done so we can update the health record and schedule the next one.',
    param_count = 3,
    updated_at  = NOW()
WHERE template_name = 'petcircle_reminder_due_v1';

UPDATE whatsapp_template_configs
SET
    body_text   = 'Hi {{1}}, just checking in on {{2}} 🐾' || E'\n\n' ||
                  'We haven''t heard back about {{3}}, which was due on {{4}}.' || E'\n\n' ||
                  'Did it get done? Tap below to log it or let us know if you need to reschedule.',
    param_count = 4,
    updated_at  = NOW()
WHERE template_name = 'petcircle_reminder_d3_v1';

UPDATE whatsapp_template_configs
SET
    body_text   = 'Hi {{1}}, a gentle nudge from PetCircle 🐾' || E'\n\n' ||
                  '{{2}}''s {{3}} is now {{4}} days overdue.' || E'\n\n' ||
                  '{{5}}' || E'\n\n' ||
                  'We''re here to help you stay on track. Tap below to log it as done, snooze, or reschedule.',
    param_count = 5,
    updated_at  = NOW()
WHERE template_name = 'petcircle_reminder_overdue_v1';

-- ─── Nudge templates ──────────────────────────────────────────────────────

-- va_personal: param_count 2 → 3 (added {{3}} = pet_name in closing line)
UPDATE whatsapp_template_configs
SET
    body_text   = 'Hi! Here''s something worth knowing for {{1}} 🐾' || E'\n\n' ||
                  '{{2}}' || E'\n\n' ||
                  'Reply anytime to ask a question about {{3}}''s health.',
    param_count = 3,
    updated_at  = NOW()
WHERE template_name = 'petcircle_nudge_va_personal_v1';

UPDATE whatsapp_template_configs
SET
    body_text   = '🐾 A quick note from PetCircle' || E'\n\n' ||
                  '{{1}}' || E'\n\n' ||
                  '{{2}}' || E'\n\n' ||
                  'We are here to help you.',
    param_count = 2,
    updated_at  = NOW()
WHERE template_name = 'petcircle_nudge_engagement_v1';

UPDATE whatsapp_template_configs
SET
    body_text   = '🐾 Did you know this about {{1}}?' || E'\n\n' ||
                  '{{2}}' || E'\n\n' ||
                  'PetCircle is here for you.',
    param_count = 2,
    updated_at  = NOW()
WHERE template_name = 'petcircle_nudge_breed_v1';

-- breed_data: param_count 4 → 5 (added {{1}}=pet_name, {{5}}=breed; reordered)
-- {{1}}=pet_name, {{2}}=insight, {{3}}=health_area, {{4}}=CTA, {{5}}=breed
UPDATE whatsapp_template_configs
SET
    body_text   = '🐾PetCircle has a Health update for {{1}} who is a {{5}}' || E'\n\n' ||
                  '{{2}}' || E'\n\n' ||
                  'Health area: {{3}}' || E'\n\n' ||
                  '{{4}}' || E'\n\n' ||
                  'We are here to help.',
    param_count = 5,
    updated_at  = NOW()
WHERE template_name = 'petcircle_nudge_breed_data_v1';

-- ─── Versioned template entries (conflict / birthday / order fulfillment) ──
-- The legacy entries used non-versioned names (petcircle_conflict, etc.)
-- but env vars point to the versioned names. Insert the correct entries.

INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description)
VALUES (
    'petcircle_conflict_v1',
    'Hi! We found a date conflict for {{1}}''s {{2}}.' || E'\n\n' ||
    'Existing record: {{3}}' || E'\n' ||
    'Newly uploaded: {{4}}' || E'\n\n' ||
    'Which date should we keep? Reply below to choose.',
    4,
    'Conflict resolution — buttons (Keep Existing / Use New) embedded in template'
)
ON CONFLICT (template_name) DO UPDATE
    SET body_text   = EXCLUDED.body_text,
        param_count = EXCLUDED.param_count,
        description = EXCLUDED.description,
        updated_at  = NOW();

INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description)
VALUES (
    'birthday_celebration_v1',
    '🎂 Happy Birthday, {{1}}!' || E'\n\n' ||
    'Today, {{2}}, is a very special day — wishing your furry companion a year full of good health, great walks, and plenty of treats!' || E'\n\n' ||
    'From all of us at PetCircle 🐾',
    2,
    'Birthday celebration — pet_name + birthday_date'
)
ON CONFLICT (template_name) DO UPDATE
    SET body_text   = EXCLUDED.body_text,
        param_count = EXCLUDED.param_count,
        description = EXCLUDED.description,
        updated_at  = NOW();

INSERT INTO whatsapp_template_configs (template_name, body_text, param_count, description)
VALUES (
    'order_fulfillment_check_v1',
    'New PetCircle order received!' || E'\n\n' ||
    'Customer: {{1}}' || E'\n' ||
    'Phone: {{2}}' || E'\n' ||
    'Pet: {{3}}' || E'\n' ||
    'Category: {{4}}' || E'\n' ||
    'Items: {{5}}' || E'\n' ||
    'Order ID: {{6}}' || E'\n\n' ||
    'Please process and confirm delivery with the customer.',
    6,
    'Admin order notification — buttons (Yes fulfilled / No cancelled) embedded in template'
)
ON CONFLICT (template_name) DO UPDATE
    SET body_text   = EXCLUDED.body_text,
        param_count = EXCLUDED.param_count,
        description = EXCLUDED.description,
        updated_at  = NOW();

COMMIT;
