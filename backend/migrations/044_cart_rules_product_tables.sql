-- Migration 044: Cart Rules Engine — Rebuild product catalog
--
-- Replaces the monolithic product_catalog table with two structured
-- tables: product_food (25 SKUs, F001-F025) and product_supplement
-- (16 SKUs, S001-S016). These power the signal-level cart resolver
-- (see .spec/cart-rules-engine/design.md).
--
-- Destructive steps:
--   - TRUNCATE cart_items: stale product_id references to old catalog
--   - TRUNCATE order_recommendations: cached GPT recommendations reference old product IDs
--   - DROP product_catalog: replaced by product_food + product_supplement
--
-- Preserved (NOT touched):
--   - orders: uses free-text items_description, no FK to product_catalog
--   - pet_preferences: independent of product catalog
--
-- Rollback: restore from pre-migration Supabase snapshot. The old
-- product_catalog schema is in backend/app/models/product_catalog.py
-- (to be removed in a later task).

BEGIN;

-- 1. Clear stale references to the old catalog
TRUNCATE cart_items CASCADE;
TRUNCATE order_recommendations CASCADE;

-- 2. Drop the old monolithic catalog
DROP TABLE IF EXISTS product_catalog CASCADE;

-- 3. Create product_food (food SKUs: F001-F025)
CREATE TABLE product_food (
    sku_id              VARCHAR(10)     PRIMARY KEY,
    brand_id            VARCHAR(10)     NOT NULL,
    brand_name          VARCHAR(100)    NOT NULL,
    product_line        VARCHAR(200)    NOT NULL,
    life_stage          VARCHAR(20)     NOT NULL,   -- Puppy, Adult, Senior, All
    breed_size          VARCHAR(20)     NOT NULL,   -- Small, Medium, Large, All
    pack_size_kg        NUMERIC(5, 1)   NOT NULL,
    mrp                 INTEGER         NOT NULL,   -- Rs.
    discounted_price    INTEGER         NOT NULL,   -- Rs.
    condition_tags      TEXT            NULL,       -- comma-separated
    breed_tags          TEXT            NULL,       -- comma-separated
    vet_diet_flag       BOOLEAN         NOT NULL DEFAULT FALSE,
    active              BOOLEAN         NOT NULL DEFAULT TRUE,
    popularity_rank     INTEGER         NOT NULL,
    monthly_units_sold  INTEGER         NULL,
    price_per_kg        INTEGER         NULL,       -- Rs.
    in_stock            BOOLEAN         NOT NULL DEFAULT TRUE,
    notes               TEXT            NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_food_brand_id
    ON product_food (brand_id);

CREATE INDEX idx_product_food_life_stage_breed
    ON product_food (life_stage, breed_size);

CREATE INDEX idx_product_food_condition_tags
    ON product_food (condition_tags);

-- 4. Create product_supplement (supplement SKUs: S001-S016)
CREATE TABLE product_supplement (
    sku_id              VARCHAR(10)     PRIMARY KEY,
    brand_id            VARCHAR(10)     NOT NULL,
    brand_name          VARCHAR(100)    NOT NULL,
    product_name        VARCHAR(200)    NOT NULL,
    type                VARCHAR(50)     NOT NULL,   -- fish_oil, joint_supplement, multivitamin, ...
    form                VARCHAR(30)     NOT NULL,   -- liquid, chew, powder, paste, tablet
    pack_size           VARCHAR(50)     NOT NULL,   -- "300 ml", "90 chews", ...
    mrp                 INTEGER         NOT NULL,   -- Rs.
    discounted_price    INTEGER         NOT NULL,   -- Rs.
    key_ingredients     TEXT            NULL,
    condition_tags      TEXT            NULL,       -- comma-separated
    life_stage_tags     TEXT            NULL,       -- comma-separated
    active              BOOLEAN         NOT NULL DEFAULT TRUE,
    popularity_rank     INTEGER         NOT NULL,
    monthly_units       INTEGER         NULL,
    price_per_unit      INTEGER         NULL,       -- Rs.
    in_stock            BOOLEAN         NOT NULL DEFAULT TRUE,
    notes               TEXT            NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_supplement_brand_id
    ON product_supplement (brand_id);

CREATE INDEX idx_product_supplement_type
    ON product_supplement (type);

COMMIT;
