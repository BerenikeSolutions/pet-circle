-- Migration 032: Generic (No Breed) Nudge Message Library
--
-- Adds 22 new rows to nudge_message_library for users whose pet has no breed set.
-- These cover the three message types that previously had no meaningful fallback
-- for breed-agnostic users:
--   - breed_only       → level 1, WHATSAPP_TEMPLATE_NUDGE_NO_BREED
--   - engagement_only  → level 1, WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED
--   - breed_data       → level 2, WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED
--
-- All rows use breed = 'Generic'. The nudge_scheduler fallback chain is:
--   specific breed → 'Generic' → 'All' (for breed_only / engagement_only)
--   specific breed → 'Generic' → 'Other' → 'All' (for breed_data)
--
-- Source: PetCircle_Nudges_v6.xlsx
--
-- Template variable mapping:
--   WHATSAPP_TEMPLATE_NUDGE_NO_BREED:
--       {{1}} = template_var_1 (insight — variable content after fixed prefix)
--       {{2}} = template_var_2 (CTA question)
--
--   WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED:
--       {{1}} = template_var_1 (insight)
--       {{2}} = template_var_2 (CTA question)
--
--   WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED:
--       {{1}} = template_var_1 (insight)
--       {{2}} = pet_name       (fetched from DB at send time — not stored here)
--       {{3}} = template_var_3 (care category label)
--       {{4}} = template_var_4 (CTA / action prompt)
--
-- Safe to re-run: ON CONFLICT DO NOTHING on all inserts.

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- Register placeholder WhatsApp template configs (body_text updated once Meta approves)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO whatsapp_template_configs
  (template_name, body_text, param_count, language_code, description)
VALUES
(
  'petcircle_nudge_no_breed_v1',
  'Here''s something every dog parent should know — {{1}} 🐾 Worth knowing for your pet. {{2}}

PetCircle is here for you.',
  2,
  'en',
  'No-breed breed_only nudge. {{1}}=insight, {{2}}=CTA. Fires for Level 1 users with no breed set.'
),
(
  'petcircle_nudge_engagement_no_breed_v1',
  'Here''s something most dog parents find fascinating — {{1}} 🐾 Does this sound like your pet? {{2}}

PetCircle is here for you.',
  2,
  'en',
  'No-breed engagement nudge. {{1}}=insight, {{2}}=CTA. Fires for Level 1 users with no breed set.'
),
(
  'petcircle_nudge_breed_data_no_breed_v1',
  'Here''s something every dog parent should know — {{1}} 🐾 Worth knowing for your pet {{2}}.

Here''s what {{3}} recommends: {{4}}

PetCircle is here for you.',
  4,
  'en',
  'No-breed breed+data nudge. {{1}}=insight, {{2}}=pet_name, {{3}}=care_category, {{4}}=CTA. Fires for Level 2 users with no breed set.'
)
ON CONFLICT (template_name) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- BREED ONLY — No Breed (level=1, message_type='breed_only', breed='Generic')
-- Template: WHATSAPP_TEMPLATE_NUDGE_NO_BREED
-- template_var_1 = insight (variable content; fixed prefix lives in the template)
-- template_var_2 = CTA question
-- slot_day = 0 (post-schedule cycling)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO nudge_message_library
  (level, slot_day, seq, message_type, breed, template_key, template_var_1, template_var_2, notes)
VALUES
(1, 0, 1, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'staying current on vaccinations and an annual blood panel covers the majority of preventable health risks for most dogs. Two simple things. That''s the foundation of a long, healthy life for your pet.',
 'Is your pet vaccinated and up to date on blood checks?',
 'Generic no-breed — Bridge: Vaccination & Blood'),
(1, 0, 2, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'most dogs are slightly overfed — not because their owners don''t care, but because the bag recommendation is often higher than what your pet actually needs. The right portion is the single easiest thing you can get right for your pet''s long-term health.',
 'Do you know your pet''s ideal daily portion?',
 'Generic no-breed — Bridge: Weight & Diet'),
(1, 0, 3, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'joint issues are one of the most common reasons dogs slow down as they age — but they''re largely preventable. Keeping your pet lean and active from year one is the most effective thing you can do. Movement now means mobility later.',
 'Is your pet getting regular daily exercise?',
 'Generic no-breed — Bridge: Joint Health'),
(1, 0, 4, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'dental disease is one of the most common yet preventable conditions in dogs. A regular brush at home and an annual dental check covers most of what it takes to keep your pet''s teeth and gums healthy. Two simple habits. That''s all it takes.',
 'How often do you clean your pet''s teeth?',
 'Generic no-breed — Bridge: Dental Health'),
(1, 0, 5, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'regular brushing does far more than keep your pet looking good. It stimulates blood flow, distributes natural oils, and helps catch early signs of skin issues before they become a problem. One simple habit with benefits that go much deeper than the coat.',
 'Is brushing part of your pet''s regular routine?',
 'Generic no-breed — Bridge: Coat & Grooming'),
(1, 0, 6, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'a dog''s skin is their largest organ — and it''s often the first place health issues show up. Regular grooming, the right diet, and a quick check during brushing sessions go a long way in catching problems early.',
 'When did you last check your pet''s skin during a brush?',
 'Generic no-breed — Bridge: Skin Care'),
(1, 0, 7, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'eye discharge and dryness are easy to miss but surprisingly common in dogs. A quick daily eye wipe takes under two minutes and prevents a lot of unnecessary discomfort — and expensive vet visits — down the line.',
 'Is eye care part of your pet''s daily routine?',
 'Generic no-breed — Bridge: Eye Care'),
(1, 0, 8, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'tick and flea protection is one of the most overlooked yet most impactful things you can do for your pet in India''s climate. It''s low cost, simple to maintain, and makes a bigger difference than most owners realise.',
 'Is your pet''s tick and flea protection up to date?',
 'Generic no-breed — Bridge: Tick & Flea Protection'),
(1, 0, 9, 'breed_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_NO_BREED',
 'the two things that matter most for most dogs are also the simplest — a consistent vaccination schedule and an annual vet check. Most preventable conditions are caught or avoided entirely with just these two habits in place.',
 'Has your pet had an annual vet check this year?',
 'Generic no-breed — Bridge: Preventive Care')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- ENGAGEMENT ONLY — No Breed (level=1, message_type='engagement_only', breed='Generic')
-- Template: WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED
-- template_var_1 = full insight text (no fixed prefix to strip)
-- template_var_2 = CTA question
-- seq 1–3 = Msg1 type; seq 4–6 = Msg2 type (scheduler cycles through all 6)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO nudge_message_library
  (level, slot_day, seq, message_type, breed, template_key, template_var_1, template_var_2, notes)
VALUES
(1, 0, 1, 'engagement_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED',
 'Dogs are the only animals on Earth that have evolved specifically to understand human emotion — they can read your facial expressions, interpret your tone of voice, and even follow your gaze in a way no other species can. Your pet was literally shaped by evolution to understand you.',
 'Have you caught your pet reading your mood?',
 'Generic no-breed — Msg1: Origin Wow'),
(1, 0, 2, 'engagement_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED',
 'A dog''s nose is between 10,000 and 100,000 times more sensitive than a human''s — every time your pet sniffs a patch of grass on a walk, they''re processing as much information as you''d get from reading a newspaper. That stop-and-sniff moment isn''t delay — it''s your pet downloading the news.',
 'Does your pet stop to sniff everything?',
 'Generic no-breed — Msg1: Superpower Wow'),
(1, 0, 3, 'engagement_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED',
 'Dogs dream — and they dream about their owners. MRI studies show dogs experience REM sleep just like humans, and their brain activity during sleep mirrors what happens when they''re playing with or following the person they''re most bonded to. Those paws twitching mid-nap? That''s probably you.',
 'Have you watched your pet dream?',
 'Generic no-breed — Msg1: Behaviour Explanation'),
(1, 0, 4, 'engagement_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED',
 'Dogs are one of the only animals that choose to make eye contact with humans — wolves, even those raised by humans, rarely do it. When your pet looks up at you, their brain releases oxytocin — the same bonding hormone released between a parent and a newborn. It''s not just affection. It''s biology.',
 'Does your pet stare at you?',
 'Generic no-breed — Msg2: Loyalty Superpower'),
(1, 0, 5, 'engagement_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED',
 'Dogs yawn to communicate, not because they''re tired. A yawn directed at you means your pet is trying to calm a situation down — it''s a peace signal, borrowed from wolf behaviour. When your pet yawns during something stressful, they''re actively trying to de-escalate.',
 'Have you noticed your pet do this?',
 'Generic no-breed — Msg2: Behaviour Explanation'),
(1, 0, 6, 'engagement_only', 'Generic', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED',
 'Dogs can smell time — studies show that as the scent of their owner fades through the day, dogs can estimate how long until they return home. The longer you''ve been out, the more your scent has dispersed. Your pet isn''t just excited to see you — they predicted you were coming.',
 'Does your pet wait for you near the door?',
 'Generic no-breed — Msg2: Superpower Wow')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- BREED + DATA — No Breed (level=2, message_type='breed_data', breed='Generic')
-- Template: WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED
-- template_var_1 = insight text ({{1}})
-- template_var_2 = NULL ({{2}} = pet_name, injected from DB at send time)
-- template_var_3 = care category label ({{3}})
-- template_var_4 = CTA / action prompt ({{4}})
-- Categories mapped to NUDGE_L2_DATA_PRIORITY canonical values.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO nudge_message_library
  (level, slot_day, seq, message_type, breed, category, template_key, template_var_1, template_var_3, template_var_4, notes)
VALUES
(2, 0, 1, 'breed_data', 'Generic', 'vaccine', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'most preventable diseases in dogs are stopped by one simple habit — staying current on vaccinations. A missed booster can leave your pet exposed to conditions that are almost entirely avoidable with an up-to-date schedule.',
 'vaccination',
 'Is your pet''s vaccination up to date? Share the last record.',
 'Generic no-breed — Vaccination'),
(2, 0, 2, 'breed_data', 'Generic', 'flea_tick', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'tick-borne diseases are among the most common yet overlooked health threats for dogs in India. Monthly tick and flea protection is the single most effective way to prevent infections that can affect your pet''s energy, appetite, and organ health.',
 'tick & flea protection',
 'Is your pet on monthly tick & flea protection? Log the last dose.',
 'Generic no-breed — Tick & Flea'),
(2, 0, 3, 'breed_data', 'Generic', 'deworming', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'most dogs carry intestinal parasites at some point — and many show no symptoms at all. Deworming every 3 months is the simplest way to protect your pet''s gut health, immunity, and energy levels year-round.',
 'deworming',
 'Is your pet''s deworming up to date? Share when it was last done.',
 'Generic no-breed — Deworming'),
(2, 0, 4, 'breed_data', 'Generic', 'nutrition', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'what your pet eats shows up everywhere — in their coat, energy, weight, and how they move. The right food isn''t just about preference. It''s the foundation everything else builds on, and it matters more than most pet parents realise.',
 'nutrition and diet',
 'What does your pet currently eat? Share their food details.',
 'Generic no-breed — Food / Nutrition'),
(2, 0, 5, 'breed_data', 'Generic', 'supplement', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'the right supplements fill the gaps that even a good diet can leave — joint support, Omega-3, and digestive health supplements are among the most commonly recommended by vets for dogs across all breeds and life stages.',
 'supplement',
 'Is your pet on any supplements? Share what they''re taking.',
 'Generic no-breed — Supplements'),
(2, 0, 6, 'breed_data', 'Generic', 'condition', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'an annual vet check is the single most reliable way to catch health issues before they become serious. Most conditions that are expensive to treat are inexpensive to prevent — and a yearly visit is where that prevention starts.',
 'vet visit',
 'When was your pet''s last annual vet check? Share the date.',
 'Generic no-breed — Vet Visit'),
(2, 0, 7, 'breed_data', 'Generic', 'diagnostics', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED',
 'an annual blood panel is the most effective preventive tool available for dogs — it screens organ function, flags early metabolic changes, and gives your vet a baseline to track your pet''s health over time.',
 'lab and diagnostic history',
 'Has your pet had a blood panel this year? Upload the report.',
 'Generic no-breed — Diagnostic')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

COMMIT;
