-- Clear all data from the database (keeps preventive_master, product_catalog, nudge_config reference data).
-- Truncates tables in FK-safe order (children first) using CASCADE.

-- Logs & engagement
TRUNCATE TABLE message_logs CASCADE;
TRUNCATE TABLE nudge_delivery_log CASCADE;
TRUNCATE TABLE nudge_engagement CASCADE;
TRUNCATE TABLE shown_fun_facts CASCADE;

-- Flags & conflicts
TRUNCATE TABLE conflict_flags CASCADE;

-- Reminders & preventive records
TRUNCATE TABLE reminders CASCADE;
TRUNCATE TABLE preventive_records CASCADE;
TRUNCATE TABLE custom_preventive_items CASCADE;

-- Diagnostics & medicines
TRUNCATE TABLE diagnostic_test_results CASCADE;
TRUNCATE TABLE prescribed_medicines CASCADE;

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

-- Documents & tokens
TRUNCATE TABLE documents CASCADE;
TRUNCATE TABLE dashboard_tokens CASCADE;

-- Preferences & contacts
TRUNCATE TABLE pet_preferences CASCADE;
TRUNCATE TABLE contacts CASCADE;

-- Core entities (cascade clears remaining child FKs)
TRUNCATE TABLE pets CASCADE;
TRUNCATE TABLE users CASCADE;
