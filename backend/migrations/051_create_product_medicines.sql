-- Migration 051: Create product_medicines table for tick, flea, deworming, and antibiotic products
--
-- Creates product_medicines table (SKU-001 to SKU-054) with medicines for:
--   - Tick & Flea prevention (oral, spot-on, collars)
--   - Deworming products (tablets, suspensions)
--   - Flea & Deworming combined
--   - Antibiotics (Bacterial infections)
--   - Heartworm prevention
--
-- Source of truth: project details/PetCircle_TickFlea_Deworming_DB.xlsx
-- Safe to re-run: uses ON CONFLICT (sku_id) DO UPDATE (upsert).

BEGIN;

-- Create product_medicines table
CREATE TABLE product_medicines (
    sku_id                  VARCHAR(10)     PRIMARY KEY,
    brand_id                VARCHAR(10)     NOT NULL,
    brand_name              VARCHAR(100)    NOT NULL,
    product_name            VARCHAR(255)    NOT NULL,
    type                    VARCHAR(100)    NOT NULL,   -- Tick & Flea, Deworming, Combined, Antibiotic, etc.
    form                    VARCHAR(50)     NOT NULL,   -- Chewables, Spot-on, Tablets, Syrup, Collar, Spray, etc.
    pack_size               VARCHAR(100)    NOT NULL,   -- "Box of 1", "3 pipettes", "Strip of 10", etc.
    mrp_paise               INTEGER         NOT NULL,   -- MRP in paise (to avoid decimals)
    discounted_paise        INTEGER         NOT NULL,   -- Discounted price in paise
    key_ingredients         TEXT            NULL,
    condition_tags          TEXT            NULL,       -- comma-separated: ticks,fleas,heartworm,roundworm,etc.
    life_stage_tags         TEXT            NULL,       -- comma-separated: dog,cat,puppy,adult,senior
    active                  BOOLEAN         NOT NULL DEFAULT TRUE,
    popularity_rank         INTEGER         NULL,
    monthly_units_sold      INTEGER         NULL,
    price_per_unit_paise    INTEGER         NULL,       -- calculated price per unit
    in_stock                BOOLEAN         NOT NULL DEFAULT TRUE,
    dosage                  TEXT            NULL,       -- Dosage instructions
    repeat_frequency        VARCHAR(100)    NULL,       -- Frequency: Monthly, Every 3 months, Every 12 weeks, etc.
    notes                   TEXT            NULL,       -- Special notes, warnings, restrictions
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_medicines_brand_id
    ON product_medicines (brand_id);

CREATE INDEX idx_product_medicines_type
    ON product_medicines (type);

CREATE INDEX idx_product_medicines_condition_tags
    ON product_medicines (condition_tags);

CREATE INDEX idx_product_medicines_life_stage_tags
    ON product_medicines (life_stage_tags);

COMMIT;
