-- Migration 003: Add name, icon, category, is_default columns to hygiene_preferences
-- Supports custom user-added hygiene items per pet

ALTER TABLE hygiene_preferences
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS icon VARCHAR(10) DEFAULT '🧹',
    ADD COLUMN IF NOT EXISTS category VARCHAR(20) DEFAULT 'daily',
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;

-- Backfill existing default items with correct name, icon, category
UPDATE hygiene_preferences SET name = 'Coat Brushing', icon = '🪮', category = 'daily', is_default = TRUE WHERE item_id = 'coat-brush';
UPDATE hygiene_preferences SET name = 'Teeth Brushing', icon = '🦷', category = 'daily', is_default = TRUE WHERE item_id = 'teeth-brush';
UPDATE hygiene_preferences SET name = 'Ear Cleaning', icon = '👂', category = 'daily', is_default = TRUE WHERE item_id = 'ear-clean';
UPDATE hygiene_preferences SET name = 'Eye Wipe', icon = '👁️', category = 'daily', is_default = TRUE WHERE item_id = 'eye-wipe';
UPDATE hygiene_preferences SET name = 'Bath, brush & nail trim', icon = '🛁', category = 'periodic', is_default = TRUE WHERE item_id = 'bath-nail';
UPDATE hygiene_preferences SET name = 'Anal gland cleaning', icon = '🐾', category = 'periodic', is_default = TRUE WHERE item_id = 'anal-gland';
