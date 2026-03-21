-- Migration 008: Custom Preventive Items
-- Adds user-scoped custom preventive items table and links it to preventive_records.
-- The preventive_master table remains frozen. Custom medicines, supplements, and
-- vaccines added by users are stored here, visible only to that user.

-- 1. Create custom_preventive_items table
CREATE TABLE IF NOT EXISTS custom_preventive_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_name VARCHAR(120) NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'complete'
        CHECK (category IN ('essential', 'complete')),
    circle VARCHAR(20) NOT NULL DEFAULT 'health'
        CHECK (circle IN ('health', 'nutrition', 'hygiene')),
    species VARCHAR(10) NOT NULL
        CHECK (species IN ('dog', 'cat', 'both')),
    recurrence_days INTEGER NOT NULL,
    medicine_dependent BOOLEAN DEFAULT FALSE,
    reminder_before_days INTEGER NOT NULL DEFAULT 7,
    overdue_after_days INTEGER NOT NULL DEFAULT 7,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, item_name, species)
);

-- Index for fast lookup by user
CREATE INDEX IF NOT EXISTS ix_custom_preventive_items_user_id
    ON custom_preventive_items(user_id);

-- 2. Add custom_preventive_item_id FK to preventive_records
ALTER TABLE preventive_records
    ADD COLUMN IF NOT EXISTS custom_preventive_item_id UUID
    REFERENCES custom_preventive_items(id) ON DELETE CASCADE;

-- 3. Make preventive_master_id nullable (was implicitly NOT NULL)
ALTER TABLE preventive_records
    ALTER COLUMN preventive_master_id DROP NOT NULL;

-- 4. Idempotency constraint for custom item records
-- (pet_id + custom_preventive_item_id + last_done_date must be unique)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_preventive_record_pet_custom_item_date'
    ) THEN
        ALTER TABLE preventive_records
            ADD CONSTRAINT uq_preventive_record_pet_custom_item_date
            UNIQUE (pet_id, custom_preventive_item_id, last_done_date);
    END IF;
END $$;

-- 5. Check constraint: exactly one of preventive_master_id or custom_preventive_item_id must be set
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_preventive_record_one_source'
    ) THEN
        ALTER TABLE preventive_records
            ADD CONSTRAINT chk_preventive_record_one_source
            CHECK (
                (preventive_master_id IS NOT NULL AND custom_preventive_item_id IS NULL)
                OR
                (preventive_master_id IS NULL AND custom_preventive_item_id IS NOT NULL)
            );
    END IF;
END $$;
