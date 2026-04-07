-- Clear all data from the database.
-- Tables PRESERVED (reference/seed data — never cleared):
--   preventive_master, product_catalog, nudge_config,
--   nudge_message_library, breed_consequence_library,
--   whatsapp_template_configs
-- Truncates tables in FK-safe order (children first) using CASCADE.
--
-- TARGETED RESET (single test number — replace phone number below):
-- Resets onboarding session and user state without wiping the full DB.
--
--   DO $$
--   DECLARE v_uid UUID;
--   BEGIN
--     SELECT id INTO v_uid FROM users WHERE phone_number = '919XXXXXXXXX';
--     DELETE FROM agent_order_sessions       WHERE user_id = v_uid;
--     UPDATE users
--        SET onboarding_state        = 'awaiting_consent',
--            dashboard_link_pending  = FALSE
--      WHERE id = v_uid;
--   END $$;
--

-- Logs & engagement
TRUNCATE TABLE message_logs CASCADE;
TRUNCATE TABLE nudge_delivery_log CASCADE;
TRUNCATE TABLE nudge_engagement CASCADE;
TRUNCATE TABLE shown_fun_facts CASCADE;

-- AI insights & agent sessions
TRUNCATE TABLE pet_ai_insights CASCADE;
TRUNCATE TABLE pet_life_stage_traits CASCADE;
TRUNCATE TABLE agent_order_sessions CASCADE;
TRUNCATE TABLE deferred_care_plan_pending CASCADE;

-- Flags & conflicts
TRUNCATE TABLE conflict_flags CASCADE;

-- Reminders & preventive records
TRUNCATE TABLE reminders CASCADE;
TRUNCATE TABLE preventive_records CASCADE;
TRUNCATE TABLE custom_preventive_items CASCADE;

-- Diagnostics
TRUNCATE TABLE diagnostic_test_results CASCADE;

-- Conditions
TRUNCATE TABLE condition_medications CASCADE;
TRUNCATE TABLE condition_monitoring CASCADE;
TRUNCATE TABLE conditions CASCADE;

-- Nutrition & diet
TRUNCATE TABLE diet_items CASCADE;
TRUNCATE TABLE food_nutrition_cache CASCADE;
TRUNCATE TABLE nutrition_target_cache CASCADE;
TRUNCATE TABLE ideal_weight_cache CASCADE;

-- Weight & hygiene
TRUNCATE TABLE weight_history CASCADE;
TRUNCATE TABLE hygiene_preferences CASCADE;
TRUNCATE TABLE hygiene_tip_cache CASCADE;

-- Nudges (nudge_config is reference data — skip it)
TRUNCATE TABLE nudges CASCADE;

-- Orders & cart
TRUNCATE TABLE cart_items CASCADE;
TRUNCATE TABLE order_recommendations CASCADE;
TRUNCATE TABLE orders CASCADE;

-- Dashboard visits (nudge level tracking — migration 027)
TRUNCATE TABLE dashboard_visits CASCADE;

-- Documents & tokens
TRUNCATE TABLE documents CASCADE;
TRUNCATE TABLE dashboard_tokens CASCADE;

-- Preferences & contacts
TRUNCATE TABLE pet_preferences CASCADE;
TRUNCATE TABLE contacts CASCADE;

-- Core entities (cascade clears remaining child FKs)
TRUNCATE TABLE pets CASCADE;
TRUNCATE TABLE users CASCADE;
