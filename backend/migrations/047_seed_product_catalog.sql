-- Migration 047: Seed product catalog (cart-rules-engine)
--
-- Populates product_food (F001..F025, 25 rows) and product_supplement
-- (S001..S016, 16 rows) with the signal-level SKUs used by the cart
-- rules engine resolver.
--
-- Source of truth: backend/scripts/seed_product_catalog.py
-- Safe to re-run: uses ON CONFLICT (sku_id) DO UPDATE (upsert).
-- Tables must already exist (created in migration 044).

BEGIN;

-- ---------------------------------------------------------------------------
-- Food SKUs (25 rows) — F001..F025
-- ---------------------------------------------------------------------------
INSERT INTO product_food (
    sku_id, brand_id, brand_name, product_line, life_stage, breed_size,
    pack_size_kg, mrp, discounted_price, condition_tags, breed_tags,
    vet_diet_flag, popularity_rank, monthly_units_sold, price_per_kg,
    in_stock, notes
) VALUES
('F001', 'BR01', 'Royal Canin',         'Hypoallergenic',          'All',   'All',    2,    1690, 1520, 'allergy,skin,hypoallergenic',     'all',         TRUE,  3,  210, 760,  TRUE,  'Prescription range'),
('F002', 'BR01', 'Royal Canin',         'Hypoallergenic',          'All',   'All',    7,    4990, 4490, 'allergy,skin,hypoallergenic',     'all',         TRUE,  1,  420, 641,  TRUE,  'Most popular pack'),
('F003', 'BR01', 'Royal Canin',         'Hypoallergenic',          'All',   'All',    14,   8900, 7990, 'allergy,skin,hypoallergenic',     'all',         TRUE,  4,  85,  571,  TRUE,  'Value pack'),
('F004', 'BR01', 'Royal Canin',         'Labrador Adult',          'Adult', 'Large',  3,    2100, 1890, 'joint,weight',                    'labrador',    FALSE, 2,  310, 630,  FALSE, 'Breed-specific'),
('F005', 'BR01', 'Royal Canin',         'Labrador Adult',          'Adult', 'Large',  12,   7200, 6480, 'joint,weight',                    'labrador',    FALSE, 5,  90,  540,  FALSE, NULL),
('F006', 'BR01', 'Royal Canin',         'Large Adult',             'Adult', 'Large',  4,    2400, 2160, 'joint,digestive',                 'large_breed', FALSE, 6,  180, 540,  FALSE, NULL),
('F007', 'BR01', 'Royal Canin',         'Large Puppy',             'Puppy', 'Large',  4,    2600, 2340, 'growth',                          'large_breed', FALSE, 7,  150, 585,  FALSE, NULL),
('F008', 'BR01', 'Royal Canin',         'Renal',                   'All',   'All',    2,    2100, 1890, 'kidney,renal',                    'all',         TRUE,  8,  45,  945,  TRUE,  'Prescription'),
('F009', 'BR01', 'Royal Canin',         'Renal',                   'All',   'All',    7,    6500, 5850, 'kidney,renal',                    'all',         TRUE,  9,  30,  836,  TRUE,  NULL),
('F010', 'BR01', 'Royal Canin',         'Gastrointestinal',        'All',   'All',    2,    2200, 1980, 'digestive,IBD,gastrointestinal',  'all',         TRUE,  10, 60,  990,  TRUE,  NULL),
('F011', 'BR02', 'Hills Science Diet',  'i/d Digestive',           'All',   'All',    1.5,  1800, 1620, 'digestive,IBD',                   'all',         TRUE,  11, 55,  1080, TRUE,  NULL),
('F012', 'BR02', 'Hills Science Diet',  'k/d Kidney Care',         'All',   'All',    1.5,  2100, 1890, 'kidney,renal',                    'all',         TRUE,  12, 40,  1260, TRUE,  'Prescription renal'),
('F013', 'BR02', 'Hills Science Diet',  'z/d Allergy',             'All',   'All',    3.5,  4200, 3780, 'allergy,skin',                    'all',         TRUE,  13, 35,  1080, TRUE,  NULL),
('F014', 'BR02', 'Hills Science Diet',  'Large Breed Adult',       'Adult', 'Large',  6,    3800, 3420, 'joint',                           'large_breed', FALSE, 14, 120, 570,  FALSE, NULL),
('F015', 'BR02', 'Hills Science Diet',  'Large Breed Puppy',       'Puppy', 'Large',  6,    4100, 3690, 'growth',                          'large_breed', FALSE, 15, 95,  615,  TRUE,  NULL),
('F016', 'BR03', 'Drools',              'Focus Adult Large',       'Adult', 'Large',  3,    1200, 1080, 'joint',                           'large_breed', FALSE, 16, 380, 360,  TRUE,  'Value India brand'),
('F017', 'BR03', 'Drools',              'Focus Adult Large',       'Adult', 'Large',  12,   4200, 3780, 'joint',                           'large_breed', FALSE, 17, 160, 315,  TRUE,  NULL),
('F018', 'BR03', 'Drools',              'Focus Puppy Large',       'Puppy', 'Large',  3,    1350, 1215, 'growth',                          'large_breed', FALSE, 18, 290, 405,  TRUE,  NULL),
('F019', 'BR03', 'Drools',              'Absolute Calcium',        'Puppy', 'All',    3,    1100, 990,  'growth,bone',                     'all',         FALSE, 19, 210, 330,  TRUE,  NULL),
('F020', 'BR04', 'Pedigree',            'Adult',                   'Adult', 'All',    10,   2200, 1980, NULL,                              'all',         FALSE, 20, 850, 198,  TRUE,  'Mass market'),
('F021', 'BR04', 'Pedigree',            'Puppy',                   'Puppy', 'All',    3,    750,  675,  'growth',                          'all',         FALSE, 21, 620, 225,  TRUE,  NULL),
('F022', 'BR05', 'Farmina N&D',         'GF Ancestral Grain Boar', 'Adult', 'Medium', 3,    3900, 3510, 'skin,coat,grain_free',            'all',         FALSE, 22, 70,  1170, TRUE,  'Premium grain-free'),
('F023', 'BR05', 'Farmina N&D',         'Ocean Cod Puppy',         'Puppy', 'All',    2.5,  3200, 2880, 'growth,skin',                     'all',         FALSE, 23, 45,  1152, TRUE,  NULL),
('F024', 'BR06', 'Acana',               'Regionals Meadowland',    'Adult', 'All',    2,    3500, 3150, 'skin,coat',                       'all',         FALSE, 24, 30,  1575, TRUE,  'Super-premium import'),
('F025', 'BR01', 'Royal Canin',         'Satiety Weight Mgmt',     'All',   'All',    1.5,  1900, 1710, 'obesity,weight',                  'all',         TRUE,  25, 65,  1140, TRUE,  'Prescription weight')
ON CONFLICT (sku_id) DO UPDATE SET
    brand_id           = EXCLUDED.brand_id,
    brand_name         = EXCLUDED.brand_name,
    product_line       = EXCLUDED.product_line,
    life_stage         = EXCLUDED.life_stage,
    breed_size         = EXCLUDED.breed_size,
    pack_size_kg       = EXCLUDED.pack_size_kg,
    mrp                = EXCLUDED.mrp,
    discounted_price   = EXCLUDED.discounted_price,
    condition_tags     = EXCLUDED.condition_tags,
    breed_tags         = EXCLUDED.breed_tags,
    vet_diet_flag      = EXCLUDED.vet_diet_flag,
    popularity_rank    = EXCLUDED.popularity_rank,
    monthly_units_sold = EXCLUDED.monthly_units_sold,
    price_per_kg       = EXCLUDED.price_per_kg,
    in_stock           = EXCLUDED.in_stock,
    notes              = EXCLUDED.notes,
    active             = TRUE;


-- ---------------------------------------------------------------------------
-- Supplement SKUs (16 rows) — S001..S016
-- ---------------------------------------------------------------------------
INSERT INTO product_supplement (
    sku_id, brand_id, brand_name, product_name, type, form, pack_size,
    mrp, discounted_price, key_ingredients, condition_tags, life_stage_tags,
    popularity_rank, monthly_units, price_per_unit, in_stock, notes
) VALUES
('S001', 'SB01', 'Honst',       'Fish Oil - Salmon 300ml',    'fish_oil',           'liquid', '300 ml',    850,  765,  'Omega',         'coat,skin,joint,inflammation,omega3', 'adult,puppy',        1,  340, 765,  TRUE,  NULL),
('S002', 'SB01', 'Honst',       'Fish Oil - Salmon 150ml',    'fish_oil',           'liquid', '150 ml',    499,  449,  'Fish Oil',      'coat,skin,joint,omega3',              'adult,puppy',        2,  510, 449,  TRUE,  'Starter size'),
('S003', 'SB02', 'Zesty Paws',  'Omega Bites - 90 chews',     'fish_oil',           'chew',   '90 chews',  1800, 1620, 'UC-II & Zinc',  'coat,skin,omega3',                    'adult',              3,  180, 1620, TRUE,  'Chew form'),
('S004', 'SB02', 'Zesty Paws',  'Mobility Bites - 90 chews',  'joint_supplement',   'chew',   '90 chews',  2100, 1890, NULL,            'joint,hip,arthritis',                 'senior,adult',       4,  145, 1890, FALSE, 'Glucosamine + Chondroitin'),
('S005', 'SB02', 'Zesty Paws',  'Multivitamin Bites - 90',    'multivitamin',       'chew',   '90 chews',  1600, 1440, NULL,            'immunity,general_health',             'adult,puppy',        5,  220, 1440, FALSE, NULL),
('S006', 'SB03', 'Beaphar',     'Puppy Milk',                 'milk_replacer',      'powder', '500 g',     900,  810,  NULL,            'growth,nutrition',                    'puppy',              6,  90,  810,  FALSE, 'For puppies < 6 weeks'),
('S007', 'SB03', 'Beaphar',     'Multivitamin Syrup',         'multivitamin',       'liquid', '200 ml',    650,  585,  NULL,            'immunity,general_health',             'adult,puppy,senior', 7,  210, 585,  FALSE, NULL),
('S008', 'SB04', 'Drools',      'Absolute Boneup - 500g',     'joint_supplement',   'powder', '500 g',     750,  675,  NULL,            'joint,bone',                          'senior,large_breed', 8,  320, 675,  TRUE,  'Calcium + Phosphorus'),
('S009', 'SB05', 'Himalaya',    'Erina EP Coat Supplement',   'coat_supplement',    'liquid', '200 ml',    280,  252,  NULL,            'coat,skin',                           'adult',              9,  480, 252,  TRUE,  'Affordable India brand'),
('S010', 'SB06', 'NutriVet',    'Joint Health Chews - 60',    'joint_supplement',   'chew',   '60 chews',  1400, 1260, NULL,            'joint,hip',                           'senior',             10, 95,  1260, TRUE,  NULL),
('S011', 'SB07', 'Virbac',      'Megaderm - 250 ml',          'skin_supplement',    'liquid', '250 ml',    1100, 990,  NULL,            'skin,allergy,coat,omega6',            'adult',              11, 75,  990,  TRUE,  'Dermatology-grade'),
('S012', 'SB07', 'Virbac',      'Pronefra - 180 ml',          'kidney_supplement',  'liquid', '180 ml',    1800, 1620, NULL,            'kidney,renal',                        'adult,senior',       12, 30,  1620, TRUE,  'Vet-grade phosphate binder'),
('S013', 'SB08', 'Vet Activ',   'Probiotic Paste - 30g',      'probiotic',          'paste',  '30 g',      750,  675,  NULL,            'digestive,gut_health',                'adult,puppy,senior', 13, 165, 675,  TRUE,  NULL),
('S014', 'SB08', 'Vet Activ',   'Urinary Care - 100 tabs',    'urinary_supplement', 'tablet', '100 tabs',  1200, 1080, NULL,            'urinary,bladder',                     'adult',              14, 55,  1080, FALSE, 'D-mannose + cranberry'),
('S015', 'SB09', 'Venkys',      'Gro Pet - 500g',             'growth_supplement',  'powder', '500 g',     650,  585,  NULL,            'growth,bone',                         'puppy',              15, 190, 585,  TRUE,  'Value puppy supplement'),
('S016', 'SB10', 'Pet Health',  'CBD Calming Chews - 30',     'calming',            'chew',   '30 chews',  2200, 1980, NULL,            'anxiety,stress,behaviour',            'adult,senior',       16, 40,  1980, TRUE,  'New category')
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


-- Sanity check row counts before commit.
DO $$
DECLARE
    food_count       INTEGER;
    supplement_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO food_count       FROM product_food;
    SELECT COUNT(*) INTO supplement_count FROM product_supplement;

    IF food_count < 25 THEN
        RAISE EXCEPTION 'product_food seed failed: expected >= 25 rows, got %', food_count;
    END IF;
    IF supplement_count < 16 THEN
        RAISE EXCEPTION 'product_supplement seed failed: expected >= 16 rows, got %', supplement_count;
    END IF;

    RAISE NOTICE 'Seed complete: product_food=%, product_supplement=%',
        food_count, supplement_count;
END $$;

COMMIT;
