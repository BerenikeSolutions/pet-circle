-- Migration 048: Supplement micronutrient enrichment
--
-- Enriches key_ingredients and condition_tags for omega-3, omega-6, and
-- glucosamine supplement SKUs so the signal resolver can match them
-- correctly from AI-returned micronutrient gap data.
--
-- Also inserts S017 (Venkys Vitamin D3 + Calcium), which was missing
-- from the catalog entirely — no vitamin_d3 SKU existed before this.
--
-- SKUs touched:
--   S001, S002, S003  — Omega-3 (Honst, Zesty Paws fish oil)
--   S011              — Omega-6 (Virbac Megaderm)
--   S004, S008, S010  — Glucosamine (Zesty Paws, Drools, NutriVet)
--   S017              — Vitamin D3 NEW INSERT (Venkys)
--
-- Safe to re-run: UPDATEs are idempotent; INSERT uses ON CONFLICT DO UPDATE.
-- Prerequisite: migration 047_seed_product_catalog.sql must have run.

BEGIN;

-- =====================================================================
-- OMEGA-3: S001, S002, S003
-- =====================================================================

UPDATE product_supplement
SET
    key_ingredients = 'Omega-3, EPA, DHA (Marine Salmon Oil)',
    condition_tags  = 'coat,skin,joint,inflammation,omega_3,omega3'
WHERE sku_id = 'S001';

UPDATE product_supplement
SET
    key_ingredients = 'Omega-3, EPA, DHA (Marine Salmon Oil)',
    condition_tags  = 'coat,skin,joint,omega_3,omega3'
WHERE sku_id = 'S002';

UPDATE product_supplement
SET
    key_ingredients = 'Omega-3, EPA, DHA, Zinc',
    condition_tags  = 'coat,skin,omega_3,omega3'
WHERE sku_id = 'S003';

-- =====================================================================
-- OMEGA-6: S011 Virbac Megaderm
-- =====================================================================

UPDATE product_supplement
SET
    key_ingredients = 'Omega-6 (Linoleic Acid), Evening Primrose Oil, Vitamin E',
    condition_tags  = 'skin,allergy,coat,omega_6,omega6,dermatology'
WHERE sku_id = 'S011';

-- =====================================================================
-- GLUCOSAMINE: S004, S008, S010
-- =====================================================================

UPDATE product_supplement
SET
    key_ingredients = 'Glucosamine HCl, Chondroitin Sulphate, UC-II Collagen',
    condition_tags  = 'joint,hip,arthritis,glucosamine,mobility',
    notes           = 'Glucosamine + Chondroitin + UC-II; best for arthritis and senior joint support'
WHERE sku_id = 'S004';

UPDATE product_supplement
SET
    key_ingredients = 'Glucosamine, Calcium, Phosphorus',
    condition_tags  = 'joint,bone,glucosamine,large_breed',
    notes           = 'Calcium + Phosphorus + Glucosamine; value powder for large breed bone support'
WHERE sku_id = 'S008';

UPDATE product_supplement
SET
    key_ingredients = 'Glucosamine Sulphate, Chondroitin, MSM',
    condition_tags  = 'joint,hip,glucosamine,senior'
WHERE sku_id = 'S010';

-- =====================================================================
-- VITAMIN D3: New SKU S017 (no vitamin_d3 SKU existed before this)
-- =====================================================================

INSERT INTO product_supplement (
    sku_id, brand_id, brand_name, product_name,
    type, form, pack_size,
    mrp, discounted_price,
    key_ingredients, condition_tags, life_stage_tags,
    popularity_rank, monthly_units, price_per_unit,
    in_stock, notes
) VALUES (
    'S017', 'SB09', 'Venkys',
    'Vitamin D3 + Calcium - 60 tabs',
    'vitamin_supplement', 'tablet', '60 tabs',
    550, 495,
    'Vitamin D3 (Cholecalciferol), Calcium Carbonate',
    'bone,calcium,vitamin_d3,indoor,deficiency',
    'adult,puppy,senior',
    17, 120, 495,
    TRUE,
    'Supports calcium absorption and bone mineralisation; especially useful for indoor dogs'
)
ON CONFLICT (sku_id) DO UPDATE SET
    brand_id         = EXCLUDED.brand_id,
    brand_name       = EXCLUDED.brand_name,
    product_name     = EXCLUDED.product_name,
    type             = EXCLUDED.type,
    form             = EXCLUDED.form,
    pack_size        = EXCLUDED.pack_size,
    mrp              = EXCLUDED.mrp,
    discounted_price = EXCLUDED.discounted_price,
    key_ingredients  = EXCLUDED.key_ingredients,
    condition_tags   = EXCLUDED.condition_tags,
    life_stage_tags  = EXCLUDED.life_stage_tags,
    popularity_rank  = EXCLUDED.popularity_rank,
    monthly_units    = EXCLUDED.monthly_units,
    price_per_unit   = EXCLUDED.price_per_unit,
    in_stock         = EXCLUDED.in_stock,
    notes            = EXCLUDED.notes,
    active           = TRUE;

-- =====================================================================
-- Sanity check — verify all 8 rows landed correctly
-- =====================================================================

DO $$
DECLARE
    omega3_count      INTEGER;
    omega6_count      INTEGER;
    glucosamine_count INTEGER;
    d3_count          INTEGER;
BEGIN
    SELECT COUNT(*) INTO omega3_count
        FROM product_supplement
        WHERE sku_id IN ('S001', 'S002', 'S003')
          AND key_ingredients LIKE '%Omega-3%';

    SELECT COUNT(*) INTO omega6_count
        FROM product_supplement
        WHERE sku_id = 'S011'
          AND key_ingredients LIKE '%Omega-6%';

    SELECT COUNT(*) INTO glucosamine_count
        FROM product_supplement
        WHERE sku_id IN ('S004', 'S008', 'S010')
          AND key_ingredients LIKE '%Glucosamine%';

    SELECT COUNT(*) INTO d3_count
        FROM product_supplement
        WHERE sku_id = 'S017'
          AND key_ingredients LIKE '%Vitamin D3%';

    IF omega3_count < 3 THEN
        RAISE EXCEPTION 'Migration 048 failed: omega-3 update incomplete, expected 3 rows got %', omega3_count;
    END IF;
    IF omega6_count < 1 THEN
        RAISE EXCEPTION 'Migration 048 failed: omega-6 update incomplete, S011 not updated';
    END IF;
    IF glucosamine_count < 3 THEN
        RAISE EXCEPTION 'Migration 048 failed: glucosamine update incomplete, expected 3 rows got %', glucosamine_count;
    END IF;
    IF d3_count < 1 THEN
        RAISE EXCEPTION 'Migration 048 failed: vitamin D3 insert incomplete, S017 not found';
    END IF;

    RAISE NOTICE 'Migration 048 complete: omega3=%, omega6=%, glucosamine=%, vitamin_d3=%',
        omega3_count, omega6_count, glucosamine_count, d3_count;
END $$;

COMMIT;
