-- Migration 050: Reseed supplement catalog from updated product database
--
-- Replaces all existing supplement SKUs (S001-S017) with the new full
-- catalog (S017-S116, 96 SKUs) sourced from:
--   project details/supplements_database.xlsx
--
-- Brands added: MyBeau (SB11), REX (SB12), ProDen (SB13),
--               Ektek Global (SB14), Vetina (SB15), Venkys (SB09)
--
-- Destructive step:
--   TRUNCATE product_supplement CASCADE
--   (also clears cart_items rows referencing supplements via FK)
--
-- Rollback: restore product_supplement from pre-migration Supabase snapshot.
--
-- Safe to re-run: TRUNCATE + INSERT with ON CONFLICT (sku_id) DO UPDATE.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Clear all existing supplement SKUs and dependent cart rows
-- ---------------------------------------------------------------------------
TRUNCATE product_supplement CASCADE;

-- ---------------------------------------------------------------------------
-- 2. Insert new supplement catalog — 96 SKUs (S017–S116, gaps S075–S078)
--    Columns: sku_id, brand_id, brand_name, product_name, type, form,
--             pack_size, mrp, discounted_price, key_ingredients,
--             condition_tags, life_stage_tags, popularity_rank,
--             monthly_units, price_per_unit, in_stock, notes
--    discounted_price = ROUND(mrp * 0.90)
--    popularity_rank  = row order within catalog (no sales data yet)
-- ---------------------------------------------------------------------------
INSERT INTO product_supplement (
    sku_id, brand_id, brand_name, product_name, type, form,
    pack_size, mrp, discounted_price, key_ingredients,
    condition_tags, life_stage_tags, popularity_rank,
    monthly_units, price_per_unit, in_stock, notes
) VALUES

-- ---------------------------------------------------------------------------
-- MyBeau (SB11) — S017–S026
-- ---------------------------------------------------------------------------
('S017', 'SB11', 'MyBeau', 'MyBeau Dog Vitamin & Mineral – 150 ml',
  'multivitamin', 'liquid', '150 ml', 850, 765,
  'Omega 3 & 6, Vitamins A D E B-complex',
  'immunity,general_health,skin,coat', 'adult,puppy',
  1, NULL, 765, TRUE, 'B53; 99.5% absorption rate'),

('S018', 'SB11', 'MyBeau', 'MyBeau Dog Vitamin & Mineral – 300 ml',
  'multivitamin', 'liquid', '300 ml', 1375, 1238,
  'Omega 3 & 6, Vitamins A D E B-complex',
  'immunity,general_health,skin,coat', 'adult,puppy',
  2, NULL, 1238, TRUE, 'B17'),

('S019', 'SB11', 'MyBeau', 'MyBeau Dog Vitamin & Mineral – 1.5 L',
  'multivitamin', 'liquid', '1.5 L', 5300, 4770,
  'Omega 3 & 6, Vitamins A D E B-complex',
  'immunity,general_health,skin,coat', 'adult,puppy',
  3, NULL, 4770, TRUE, 'B18; value size'),

('S020', 'SB11', 'MyBeau', 'MyBeau Cat Vitamin & Mineral – 150 ml',
  'multivitamin', 'liquid', '150 ml', 850, 765,
  'Omega 3 & 6, Vitamins A D E B-complex',
  'immunity,general_health,skin,coat', 'adult,kitten',
  4, NULL, 765, TRUE, 'B16'),

('S021', 'SB11', 'MyBeau', 'MyBeau Cat Vitamin & Mineral – 300 ml',
  'multivitamin', 'liquid', '300 ml', 1375, 1238,
  'Omega 3 & 6, Vitamins A D E B-complex',
  'immunity,general_health,skin,coat', 'adult,kitten',
  5, NULL, 1238, TRUE, 'B19'),

('S022', 'SB11', 'MyBeau', 'MyBeau Bone & Joint – 150 ml',
  'joint_supplement', 'liquid', '150 ml', 1100, 990,
  'Omega 3 & 6, Glucosamine, Chondroitin, NZ Green-lipped Mussel',
  'joint,bone,hip', 'adult,senior',
  6, NULL, 990, TRUE, 'B59'),

('S023', 'SB11', 'MyBeau', 'MyBeau Bone & Joint – 300 ml',
  'joint_supplement', 'liquid', '300 ml', 2050, 1845,
  'Omega 3 & 6, Glucosamine, Chondroitin, NZ Green-lipped Mussel',
  'joint,bone,hip', 'adult,senior',
  7, NULL, 1845, TRUE, 'B22'),

('S024', 'SB11', 'MyBeau', 'MyBeau Vision & Optics – 300 ml',
  'eye_supplement', 'liquid', '300 ml', 2025, 1823,
  'Omega 3 6 9 EPA DHA, Astaxanthin, Lutein, CoQ10',
  'eye,vision,antioxidant', 'adult',
  8, NULL, 1823, TRUE, 'B51'),

('S025', 'SB11', 'MyBeau', 'MyBeau Skin & Hair – 300 ml',
  'skin_supplement', 'liquid', '300 ml', 2025, 1823,
  'Omega 3 & 6, Vitamins A D E B-complex',
  'skin,coat,allergy,shedding', 'adult',
  9, NULL, 1823, TRUE, 'B50'),

('S026', 'SB11', 'MyBeau', 'MyBeau Dental & Breath – 300 ml',
  'dental_supplement', 'liquid', '300 ml', 2025, 1823,
  'Omega 3 & 6, Ascophyllum, Celery Oil, Aloe Vera',
  'dental,breath,plaque,tartar', 'adult',
  10, NULL, 1823, TRUE, 'B49'),

-- ---------------------------------------------------------------------------
-- REX (SB12) — S027–S031
-- ---------------------------------------------------------------------------
('S027', 'SB12', 'REX', 'REX 100% Wheat Germ Oil – 20 ml',
  'coat_supplement', 'liquid', '20 ml', 70, 63,
  'Wheat Germ Oil, Natural Vitamin E, EFAs',
  'coat,skin,general_health', 'adult,puppy',
  11, NULL, 63, TRUE, 'B46'),

('S028', 'SB12', 'REX', 'REX 100% Wheat Germ Oil – 100 ml',
  'coat_supplement', 'liquid', '100 ml', 195, 176,
  'Wheat Germ Oil, Natural Vitamin E, EFAs',
  'coat,skin,general_health', 'adult,puppy',
  12, NULL, 176, TRUE, 'B60'),

('S029', 'SB12', 'REX', 'REX 100% Wheat Germ Oil – 250 ml',
  'coat_supplement', 'liquid', '250 ml', 475, 428,
  'Wheat Germ Oil, Natural Vitamin E, EFAs',
  'coat,skin,general_health', 'adult,puppy',
  13, NULL, 428, TRUE, 'B61'),

('S030', 'SB12', 'REX', 'REX 100% Wheat Germ Oil – 500 ml',
  'coat_supplement', 'liquid', '500 ml', 900, 810,
  'Wheat Germ Oil, Natural Vitamin E, EFAs',
  'coat,skin,general_health', 'adult,puppy',
  14, NULL, 810, TRUE, 'B62'),

('S031', 'SB12', 'REX', 'REX 100% Wheat Germ Oil – 1 L',
  'coat_supplement', 'liquid', '1 L', 1675, 1508,
  'Wheat Germ Oil, Natural Vitamin E, EFAs',
  'coat,skin,general_health', 'adult,puppy',
  15, NULL, 1508, TRUE, 'B63; value size'),

-- ---------------------------------------------------------------------------
-- ProDen (SB13) — S032–S034
-- ---------------------------------------------------------------------------
('S032', 'SB13', 'ProDen', 'PlaqueOff Powder for Dogs – 20 g',
  'dental_supplement', 'powder', '20 g', 1250, 1125,
  'Seaweed (Ascophyllum nodosum)',
  'dental,breath,plaque,tartar', 'adult,puppy',
  16, NULL, 1125, TRUE, 'B58; sprinkle on food'),

('S033', 'SB13', 'ProDen', 'PlaqueOff Powder for Dogs – 40 g',
  'dental_supplement', 'powder', '40 g', 2150, 1935,
  'Seaweed (Ascophyllum nodosum)',
  'dental,breath,plaque,tartar', 'adult,puppy',
  17, NULL, 1935, TRUE, 'B47'),

('S034', 'SB13', 'ProDen', 'PlaqueOff Powder for Cats – 20 g',
  'dental_supplement', 'powder', '20 g', 1100, 990,
  'Seaweed (Ascophyllum nodosum)',
  'dental,breath,plaque,tartar', 'adult,kitten',
  18, NULL, 990, TRUE, 'FP0502'),

-- ---------------------------------------------------------------------------
-- Ektek Global (SB14) — S035–S071
-- ---------------------------------------------------------------------------
('S035', 'SB14', 'Ektek Global', 'Pet-O-Lac Puppy Milk Formula – 400 g',
  'milk_replacer', 'powder', '400 g', 1100, 990,
  'Milk derivatives, EFAs, Vitamins A D3',
  'growth,nutrition', 'puppy,newborn',
  19, NULL, 990, TRUE, 'Orphan puppies & kittens; Stage 2'),

('S036', 'SB14', 'Ektek Global', 'Bully''s Best Power Gain – 500 g',
  'performance_supplement', 'powder', '500 g', 1100, 990,
  'Creatine Monohydrate',
  'stamina,performance,muscle', 'adult',
  20, NULL, 990, TRUE, 'Sports/working dogs; not for puppies'),

('S037', 'SB14', 'Ektek Global', 'Pet-O-Boost Powder – 250 g',
  'growth_supplement', 'powder', '250 g', 1100, 990,
  'Whey, Vitamins A D B-complex',
  'growth,weight_gain,nutrition', 'puppy,adult',
  21, NULL, 990, TRUE, 'Weight gain; energy boost'),

('S038', 'SB14', 'Ektek Global', 'Pet-O-Boost Powder – 500 g',
  'growth_supplement', 'powder', '500 g', 1100, 990,
  'Whey, Vitamins A D B-complex',
  'growth,weight_gain,nutrition', 'puppy,adult',
  22, NULL, 990, TRUE, 'Value pack'),

('S039', 'SB14', 'Ektek Global', 'Calcishell Pet Calcium Supplement – 500 g',
  'calcium_supplement', 'powder', '500 g', 1100, 990,
  'Calcium, Phosphorus, Magnesium',
  'bone,teeth,growth', 'puppy,adult,senior',
  23, NULL, 990, TRUE, 'Also for pregnant/lactating'),

('S040', 'SB14', 'Ektek Global', 'Grain-Ex Coat Supplement – 500 g',
  'coat_supplement', 'powder', '500 g', 1100, 990,
  'Omega 3 & 6, Ginseng, Spirulina',
  'coat,skin,shedding,allergy', 'adult,puppy',
  24, NULL, 990, TRUE, 'Grain-free; 33 ingredients'),

('S041', 'SB14', 'Ektek Global', 'Pet-O-Coat Syrup – 200 ml',
  'coat_supplement', 'liquid', '200 ml', 1100, 990,
  'Omega 3 & 6, Biotin, Vitamins B-complex',
  'coat,skin,shedding', 'adult,puppy',
  25, NULL, 990, TRUE, 'Skin & coat'),

('S042', 'SB14', 'Ektek Global', 'Pet-O-Coat Syrup – 450 ml',
  'coat_supplement', 'liquid', '450 ml', 1100, 990,
  'Omega 3 & 6, Biotin, Vitamins B-complex',
  'coat,skin,shedding', 'adult,puppy',
  26, NULL, 990, TRUE, 'Value pack'),

('S043', 'SB14', 'Ektek Global', 'Pet-O-Cal Syrup – 200 ml',
  'calcium_supplement', 'liquid', '200 ml', 1100, 990,
  'Calcium, Phosphorus, Vitamin D3, B12',
  'bone,teeth,pregnancy', 'puppy,adult,senior',
  27, NULL, 990, TRUE, 'Calcium + Phosphorus liquid'),

('S044', 'SB14', 'Ektek Global', 'Pet-O-Cal Syrup – 450 ml',
  'calcium_supplement', 'liquid', '450 ml', 1100, 990,
  'Calcium, Phosphorus, Vitamin D3, B12',
  'bone,teeth,pregnancy', 'puppy,adult,senior',
  28, NULL, 990, TRUE, 'Value pack'),

('S045', 'SB14', 'Ektek Global', 'Multitek Pet Syrup – 200 ml',
  'multivitamin', 'liquid', '200 ml', 1100, 990,
  'Vitamins A D3 E B-complex, Taurine, Amino acids',
  'immunity,general_health,recovery', 'adult,puppy,senior',
  29, NULL, 990, TRUE, 'General multivitamin'),

('S046', 'SB14', 'Ektek Global', 'Ferrimin Iron Tonic Syrup – 200 ml',
  'iron_supplement', 'liquid', '200 ml', 1100, 990,
  'Iron, Vitamin B12, B-complex, Minerals',
  'anemia,immunity,liver', 'adult,puppy,senior',
  30, NULL, 990, TRUE, 'Iron-rich; for sporting & older dogs'),

('S047', 'SB14', 'Ektek Global', 'Pet-O-Cal Tablet – 60 tabs',
  'calcium_supplement', 'tablet', '60 tabs', 1100, 990,
  'Calcium, Phosphorus, Vitamin D3',
  'bone,teeth,immunity', 'puppy,adult,senior',
  31, NULL, 990, TRUE, 'Chewable tablet'),

('S048', 'SB14', 'Ektek Global', 'Pet-O-Vitab Plus Multivitamin – 60 tabs',
  'multivitamin', 'tablet', '60 tabs', 1100, 990,
  'Full amino acid profile, Vitamins A D3 E B-complex, Minerals',
  'immunity,general_health', 'adult,puppy,senior',
  32, NULL, 990, TRUE, 'Full-spectrum multi'),

('S049', 'SB14', 'Ektek Global', 'CoatX Skin & Coat Supplement – 300 ml',
  'coat_supplement', 'liquid', '300 ml', 1100, 990,
  'Omega 3 6 9, MSM, Vitamins, Minerals',
  'coat,skin,shedding', 'adult,puppy',
  33, NULL, 990, TRUE, 'Human-grade ingredients'),

('S050', 'SB14', 'Ektek Global', 'Pet-O-Coat Plus Fatty Acid Tablet – 60 tabs',
  'coat_supplement', 'tablet', '60 tabs', 1100, 990,
  'Marine Lipid, Flaxseed Oil, Omega 3 6, Vitamins',
  'coat,skin,shedding', 'adult,puppy',
  34, NULL, 990, TRUE, 'EFA tablet'),

('S051', 'SB14', 'Ektek Global', 'K-9 Pre+Probiotics Powder – 100 g',
  'probiotic', 'powder', '100 g', 1100, 990,
  'Lactobacillus complex, FOS, Enzyme blend',
  'digestive,gut_health,immunity', 'adult,puppy,senior',
  35, NULL, 990, TRUE, 'Prebiotic + probiotic'),

('S052', 'SB14', 'Ektek Global', 'K-9 Allergy Aid – 100 g',
  'allergy_supplement', 'powder', '100 g', 1100, 990,
  'Colostrum, Turmeric, Salmon Oil, Vitamin C, Licorice',
  'allergy,immunity,skin', 'adult',
  36, NULL, 990, TRUE, 'Anti-oxidative + anti-inflammatory'),

('S053', 'SB14', 'Ektek Global', 'K-9 Eye Support – 100 g',
  'eye_supplement', 'powder', '100 g', 1100, 990,
  'Herbal eye support blend',
  'eye,vision', 'adult',
  37, NULL, 990, TRUE, 'Ocular health powder'),

('S054', 'SB14', 'Ektek Global', 'F-9 Pre+Probiotics for Cats',
  'probiotic', 'powder', '100 g', 1100, 990,
  'Lactobacillus complex, FOS, Enzyme blend',
  'digestive,gut_health,immunity', 'adult,kitten,senior',
  38, NULL, 990, TRUE, 'Cat probiotic'),

('S055', 'SB14', 'Ektek Global', 'F-9 Hairball Tablets – 60 tabs',
  'hairball_supplement', 'tablet', '60 tabs', 1100, 990,
  'Psyllium husk, Marshmallow root, Slippery Elm, Enzyme blend',
  'hairball,digestive', 'adult,kitten',
  39, NULL, 990, TRUE, 'Cat hairball control'),

('S056', 'SB14', 'Ektek Global', 'Poop-Repel Coprophagia Tablet – 30 tabs',
  'behaviour_supplement', 'tablet', '30 tabs', 1100, 990,
  'Proprietary blend',
  'coprophagia,behaviour', 'puppy,adult',
  40, NULL, 990, TRUE, 'From 12 weeks age'),

('S057', 'SB14', 'Ektek Global', 'Poop Firm Stool Aid Tablet – 30 tabs',
  'digestive_supplement', 'tablet', '30 tabs', 1100, 990,
  'Pectin, Prebiotic fibre',
  'digestive,loose_stool', 'adult,puppy',
  41, NULL, 990, TRUE, 'Stool firmer with pectin'),

('S058', 'SB14', 'Ektek Global', 'Thyro Mania G Thyroid Support Drops',
  'thyroid_supplement', 'drops', 'drops', 1100, 990,
  'Herbal thyroid blend',
  'thyroid,metabolic,weight', 'adult,senior',
  42, NULL, 990, TRUE, 'For cats & dogs; hyperthyroidism'),

('S059', 'SB14', 'Ektek Global', 'Domicart Hip & Joint Support Drops',
  'joint_supplement', 'drops', 'drops', 1100, 990,
  'Herbal joint blend',
  'joint,hip,arthritis', 'adult,senior',
  43, NULL, 990, TRUE, 'Hip dysplasia support'),

('S060', 'SB14', 'Ektek Global', 'CardioCip Pet Cardiac Tablet – 60 tabs',
  'cardiac_supplement', 'tablet', '60 tabs', 1100, 990,
  'Terminalia arjuna, Ginger, Turmeric, Garlic',
  'cardiac,heart', 'adult,senior',
  44, NULL, 990, TRUE, 'Herbal cardiovascular'),

('S061', 'SB14', 'Ektek Global', 'Easy Breathe Respiratory Drops – 60 ml',
  'respiratory_supplement', 'drops', '60 ml', 1100, 990,
  'Marshmallow root, Holy basil, Curcuma longa',
  'respiratory,cough,wheeze', 'adult,puppy',
  45, NULL, 990, TRUE, 'Ayurveda herbal drops'),

('S062', 'SB14', 'Ektek Global', 'Hemp-O-Tek Calming Drops – 60 ml',
  'calming', 'drops', '60 ml', 1100, 990,
  'Hemp Oil, herbal calming blend',
  'anxiety,stress,behaviour', 'adult,senior',
  46, NULL, 990, TRUE, 'Anxiety relief enriched with hemp oil'),

('S063', 'SB14', 'Ektek Global', 'Diabecip Diabetes Support Syrup – 200 ml',
  'metabolic_supplement', 'liquid', '200 ml', 1100, 990,
  'Karela, Gurmar, Jamun, Methi, Ashwagandha',
  'diabetes,metabolic,immunity', 'adult,senior',
  47, NULL, 990, TRUE, 'Ayurveda; diabetes companion'),

('S064', 'SB14', 'Ektek Global', 'PetCurin Antioxidant Suspension – 200 ml',
  'antioxidant_supplement', 'liquid', '200 ml', 1100, 990,
  'Curcumin 95%, Piperine 95%',
  'antioxidant,immunity,inflammation', 'adult,puppy,senior',
  48, NULL, 990, TRUE, 'Antiviral, antibacterial, anti-cancer'),

('S065', 'SB14', 'Ektek Global', 'Pet-O-Liv Liver Tonic Syrup – 200 ml',
  'liver_supplement', 'liquid', '200 ml', 1100, 990,
  'Punarnava, Kasni, Guduchi, Bhui amla, Bhringraj',
  'liver,hepatic,detox', 'adult,puppy,senior',
  49, NULL, 990, TRUE, 'Herbal liver tonic'),

('S066', 'SB14', 'Ektek Global', 'DigipEt Digestive Stimulant Syrup – 200 ml',
  'digestive_supplement', 'liquid', '200 ml', 1100, 990,
  'Pudina, Sonth, Harad, Amla, Jeera, Ajwain',
  'digestive,gut_health,flatulence', 'adult,puppy,senior',
  50, NULL, 990, TRUE, 'Anti-flatulent, bowel regulator'),

('S067', 'SB14', 'Ektek Global', 'Pet-O-Ease Calming & Stress Syrup',
  'calming', 'liquid', '200 ml', 1100, 990,
  'Ashwagandha, Brahmi, Shankhpushpi, Jatamansi',
  'anxiety,stress,behaviour,hyperactivity', 'adult,puppy',
  51, NULL, 990, TRUE, 'Anxiolytic, behaviour modifier'),

('S068', 'SB14', 'Ektek Global', 'DigiSpas Digestive Drops – 30 ml',
  'digestive_supplement', 'drops', '30 ml', 1100, 990,
  'Dill oil, Giloe, Amla, Kasni',
  'digestive,colic,flatulence', 'adult,puppy,kitten',
  52, NULL, 990, TRUE, 'Bowel movement regulator'),

('S069', 'SB14', 'Ektek Global', 'Pet-O-Lact Lactation Booster Syrup – 200 ml',
  'reproductive_supplement', 'liquid', '200 ml', 1100, 990,
  'Shatavar, Tulsi, Fenugreek, Milk Thistle',
  'lactation,nursing', 'adult',
  53, NULL, 990, TRUE, 'Natural lactation booster for nursing females'),

('S070', 'SB14', 'Ektek Global', 'Adinatek Adrenal Support Drops',
  'adrenal_supplement', 'drops', 'drops', 1100, 990,
  'Herbal adrenal support blend',
  'adrenal,cushings,hormonal', 'adult,senior',
  54, NULL, 990, TRUE, 'Cushing''s disease support'),

('S071', 'SB14', 'Ektek Global', 'Platogrow Platelet Enhancer Syrup',
  'immunity_supplement', 'liquid', '200 ml', 1100, 990,
  'Giloy, Papita, Tulsi, Pudina, Apple',
  'platelets,immunity,blood', 'adult',
  55, NULL, 990, TRUE, 'Thrombocytopenia support'),

-- ---------------------------------------------------------------------------
-- Vetina (SB15) — S072–S074, S079–S101
-- (S075–S078 not present in source data)
-- ---------------------------------------------------------------------------
('S072', 'SB15', 'Vetina', 'Soft Coat Skin & Coat Supplement – 200 ml',
  'coat_supplement', 'liquid', '200 ml', 1100, 990,
  'Omega 6 (3000mg), Omega 3, EPA, DHA, Biotin, Curcumin',
  'coat,skin,allergy,shedding,inflammation', 'adult,puppy',
  56, NULL, 990, TRUE, '0.5ml/kg/day; dogs & cats'),

('S073', 'SB15', 'Vetina', 'Allergia Allergy Relief Tablet – 30 tabs',
  'allergy_supplement', 'tablet', '30 tabs', 1100, 990,
  'Quercetin, Citrus bioflavonoids, Omega 3, Vitamins A C E',
  'allergy,skin,immunity,sneezing', 'adult,puppy',
  57, NULL, 990, TRUE, 'Nature''s Benadryl – Quercetin formula'),

('S074', 'SB15', 'Vetina', 'Omeglo Skin & Joint Supplement – 200 ml',
  'coat_supplement', 'liquid', '200 ml', 1100, 990,
  'Cold-pressed Linseed Oil, Marine Algae Oil, Rice Bran Oil, Vitamins A D3',
  'coat,skin,joint,dermatosis', 'adult,puppy',
  58, NULL, 990, TRUE, 'Ireland origin; complementary dietetic feed'),

('S079', 'SB15', 'Vetina', 'Vetramil Auris Ear Drops – 50 ml',
  'ear_supplement', 'drops', '50 ml', 1100, 990,
  'Honey, Propylene glycol, Polysorbate',
  'ear,otitis,infection', 'adult',
  59, NULL, 990, TRUE, 'Netherlands; with canule'),

('S080', 'SB15', 'Vetina', 'Puppy & Kitten Milk Replacer – 200 g',
  'milk_replacer', 'powder', '200 g', 1100, 990,
  'Whey, Colostrum, Vitamins, Minerals, Probiotics',
  'growth,nutrition,immunity', 'puppy,newborn',
  60, NULL, 990, TRUE, 'Includes feeding bottle; Saccharomyces probiotic'),

('S081', 'SB15', 'Vetina', 'Puppy Serelac Weaning Formula – 400 g',
  'milk_replacer', 'powder', '400 g', 1100, 990,
  'Protein, Colostrum, DHA, Vitamins, Minerals, Amino Acids',
  'growth,nutrition,weaning', 'puppy',
  61, NULL, 990, TRUE, 'Enriched weaning formula; 3-10 weeks'),

('S082', 'SB15', 'Vetina', 'Vet DMG 125 Immune Performance Drops – 15 ml',
  'performance_supplement', 'drops', '15 ml', 1100, 990,
  'N,N-Dimethylglycine (DMG) 125mg/ml',
  'immunity,performance,stamina,liver', 'adult',
  62, NULL, 990, TRUE, 'Twice daily 2 wks then once daily'),

('S083', 'SB15', 'Vetina', 'CaniGel Nutritional Energizing Gel – 120 g',
  'growth_supplement', 'gel', '120 g', 1100, 990,
  'L-Carnitine, Vitamins, Minerals, B-complex',
  'weight_gain,nutrition,recovery', 'puppy,adult',
  63, NULL, 990, TRUE, 'High-calorie; for inappetence & recovery'),

('S084', 'SB15', 'Vetina', 'Well Up Multivitamin Tablet – 30 tabs',
  'multivitamin', 'tablet', '30 tabs', 1100, 990,
  'Vitamins A D3 E B-complex, DL-Methionine, L-Lysine, Taurine, Zinc',
  'immunity,general_health,growth', 'adult,puppy,kitten',
  64, NULL, 990, TRUE, 'All life stages; chelated Zinc'),

('S085', 'SB15', 'Vetina', 'Multiplex Vitamin & Mineral Powder – 200 g',
  'multivitamin', 'powder', '200 g', 1100, 990,
  'Vitamins A D3 E K B-complex, Taurine, Methionine, Choline, Biotin',
  'immunity,general_health', 'adult,puppy,senior',
  65, NULL, 990, TRUE, 'Ireland; complementary feed supplement'),

('S086', 'SB15', 'Vetina', 'Ventrogermina Probiotic Suspension – 10×5 ml',
  'probiotic', 'liquid', '10 x 5 ml', 1100, 990,
  'Bacillus clausii 2 billion spores/5ml',
  'digestive,diarrhea,gut_health', 'adult,puppy,senior',
  66, NULL, 990, TRUE, 'Lactose/sugar/gluten free; antibiotic-associated diarrhea'),

('S087', 'SB15', 'Vetina', 'Canigest Probiotic Paste – 30 ml',
  'probiotic', 'paste', '30 ml', 1100, 990,
  'Enterococcus Faecium, FOS, MOS, Kaolin, Pectin, Glutamine',
  'digestive,gut_health,diarrhea', 'adult,puppy',
  67, NULL, 990, TRUE, 'Ireland; 5-day course'),

('S088', 'SB15', 'Vetina', 'Canigest Combi Probiotic Paste – 32 ml',
  'probiotic', 'paste', '32 ml', 1100, 990,
  'Enterococcus Faecium, Lactobacillus Acidophilus, FOS, Kaolin',
  'digestive,gut_health,diarrhea', 'adult,puppy',
  68, NULL, 990, TRUE, '2 probiotic strains; COMBI formula'),

('S089', 'SB15', 'Vetina', 'Cat Hairball Protector Paste – 60 g',
  'hairball_supplement', 'paste', '60 g', 1100, 990,
  'Malt extract 50.6%, Petrolatum, Psyllium husk, Vitamin E',
  'hairball,digestive', 'adult,kitten',
  69, NULL, 990, TRUE, 'USA; do not use <6 months'),

('S090', 'SB15', 'Vetina', 'Fecal Deterrent Coprophagia Tablet – 30 tabs',
  'behaviour_supplement', 'tablet', '30 tabs', 1100, 990,
  'Monosodium Glutamate, Oleoresin Capsicum',
  'coprophagia,behaviour', 'adult,puppy',
  70, NULL, 990, TRUE, 'Imparts unpleasant taste to stool'),

('S091', 'SB15', 'Vetina', 'Cardio-Support Cardiac Tablet – 30 tabs',
  'cardiac_supplement', 'tablet', '30 tabs', 1100, 990,
  'L-Carnitine, Taurine, Hawthorn extract, CoQ10, Arjuna extract',
  'cardiac,heart', 'adult,senior',
  71, NULL, 990, TRUE, 'Ireland; 30 tab / 10×1×10 tab'),

('S092', 'SB15', 'Vetina', 'Hepa Support Liver Tablet – 30 tabs',
  'liver_supplement', 'tablet', '30 tabs', 1100, 990,
  'L-Methionine, N-Acetyl Cysteine, Milk Thistle, Curcumin, Phosphatidylcholine',
  'liver,hepatic,detox', 'adult,senior',
  72, NULL, 990, TRUE, 'Ireland; Glutathione support'),

('S093', 'SB15', 'Vetina', 'Vetina Urso Tablet 300 mg',
  'liver_supplement', 'tablet', '10×10 tabs', 1100, 990,
  'Ursodeoxycholic Acid 300mg, Silymarin 140mg',
  'liver,hepatic,cholestasis', 'adult,senior',
  73, NULL, 990, TRUE, 'Hepatoprotective; vet-grade'),

('S094', 'SB15', 'Vetina', 'Vetina Urso Suspension 125 mg – 100 ml',
  'liver_supplement', 'liquid', '100 ml', 1100, 990,
  'Ursodeoxycholic Acid 125mg/5ml, Silymarin 50mg/5ml',
  'liver,hepatic,cholestasis', 'adult,senior',
  74, NULL, 990, TRUE, 'Vet-grade; chronic hepatitis'),

('S095', 'SB15', 'Vetina', 'Uro Support Bladder Tablet – 30 tabs',
  'urinary_supplement', 'tablet', '30 tabs', 1100, 990,
  'Pumpkin seed, Cranberry extract, Rehmannia root, Dandelion, Vitamin C',
  'urinary,bladder,incontinence', 'adult,senior',
  75, NULL, 990, TRUE, 'Ireland; bladder muscle support'),

('S096', 'SB15', 'Vetina', 'Furinaid Plus Cystitis Liquid – 200 ml',
  'urinary_supplement', 'liquid', '200 ml', 1100, 990,
  'N-Acetyl Glucosamine, L-Tryptophan',
  'urinary,bladder,cystitis,stress', 'adult',
  76, NULL, 990, TRUE, 'Ireland; idiopathic cystitis support'),

('S097', 'SB15', 'Vetina', 'Stride Plus Joint Supplement – 200 ml',
  'joint_supplement', 'liquid', '200 ml', 1100, 990,
  'Glucosamine HCl, MSM, Chondroitin Sulphate, Sodium Hyaluronate',
  'joint,cartilage,arthritis,mobility', 'adult,senior',
  77, NULL, 990, TRUE, 'Ireland; 200ml pump bottle'),

('S098', 'SB15', 'Vetina', 'Stride Advanced Joint Supplement – 200 ml',
  'joint_supplement', 'liquid', '200 ml', 1100, 990,
  'Glucosamine HCl, Marine Algae Oil, Chondroitin Sulphate, MSM, Hyaluronic Acid',
  'joint,cartilage,arthritis,mobility', 'adult,senior',
  78, NULL, 990, TRUE, 'Ireland; vegan formula; EPA+DHA algae'),

('S099', 'SB15', 'Vetina', 'Stride Advanced Joint Supplement – 500 ml',
  'joint_supplement', 'liquid', '500 ml', 1100, 990,
  'Glucosamine HCl, Marine Algae Oil, Chondroitin Sulphate, MSM, Hyaluronic Acid',
  'joint,cartilage,arthritis,mobility', 'adult,senior',
  79, NULL, 990, TRUE, 'Value pack; vegan formula'),

('S100', 'SB15', 'Vetina', 'Nerve On Nerve Support Tablet – 30 tabs',
  'nerve_supplement', 'tablet', '30 tabs', 1100, 990,
  'Methylcobalamin 500mcg, Alpha Lipoic Acid 100mg, Lycopene, Selenium',
  'nerve,neuropathy,pain', 'adult,senior',
  80, NULL, 990, TRUE, 'Neuroprotective; anti-oxidant'),

('S101', 'SB15', 'Vetina', 'Calm On Calming Tablet – 30 tabs',
  'calming', 'tablet', '30 tabs', 1100, 990,
  'Chamomile 45mg, Valerian root 45mg, Ginger 45mg',
  'anxiety,stress,behaviour,travel', 'adult,senior',
  81, NULL, 990, TRUE, 'Natural; for fireworks/travel/grooming stress'),

-- ---------------------------------------------------------------------------
-- Venkys (SB09) — S102–S116
-- ---------------------------------------------------------------------------
('S102', 'SB09', 'Venkys', 'VenCoat Omega 3 & 6 Powder – 200 g',
  'coat_supplement', 'powder', '200 g', 1100, 990,
  'Linoleic Acid, Linolenic Acid, EPA 42.5mg, DHA 27.5mg, Vitamins A D3 E',
  'coat,skin,shedding', 'adult,puppy',
  82, NULL, 990, TRUE, '5g/day; skin, hair coat & general condition'),

('S103', 'SB09', 'Venkys', 'VenCoat Omega 3 & 6 Powder – 450 g',
  'coat_supplement', 'powder', '450 g', 1100, 990,
  'Linoleic Acid, Linolenic Acid, EPA, DHA, Vitamins A D3 E',
  'coat,skin,shedding', 'adult,puppy',
  83, NULL, 990, TRUE, 'Value pack'),

('S104', 'SB09', 'Venkys', 'VenCoat Omega 3 & 6 Liquid with Biotin – 200 g',
  'coat_supplement', 'liquid', '200 g', 1100, 990,
  'Omega 6 6000mg, Omega 3 600mg, Biotin 50mcg per 10g',
  'coat,skin,shedding', 'adult,puppy',
  84, NULL, 990, TRUE, '10g/day; lustrous & shiny coat'),

('S105', 'SB09', 'Venkys', 'VenCal-P Calcium Supplement Syrup – 200 ml',
  'calcium_supplement', 'liquid', '200 ml', 1100, 990,
  'Calcium 100mg, Phosphorus 50mg, Magnesium, Vit D3, Vit B12',
  'bone,teeth,pregnancy,growth', 'puppy,adult,senior',
  85, NULL, 990, TRUE, '5-10ml twice daily'),

('S106', 'SB09', 'Venkys', 'VenCal-P Calcium Supplement Syrup – 1 L',
  'calcium_supplement', 'liquid', '1 L', 1100, 990,
  'Calcium 100mg, Phosphorus 50mg, Magnesium, Vit D3, Vit B12',
  'bone,teeth,pregnancy,growth', 'puppy,adult,senior',
  86, NULL, 990, TRUE, 'Value pack'),

('S107', 'SB09', 'Venkys', 'Ventriliv Pet Liver Stimulant Syrup – 200 ml',
  'liver_supplement', 'liquid', '200 ml', 1100, 990,
  'Silybum marianum, Andrographis, Eclipta alba, Phyllanthus niruri, Choline',
  'liver,hepatic,detox,appetite', 'adult,puppy,senior',
  87, NULL, 990, TRUE, 'Herbal; enriched with choline chloride'),

('S108', 'SB09', 'Venkys', 'Pet Spark Growth & Multivitamin Syrup – 200 ml',
  'growth_supplement', 'liquid', '200 ml', 1100, 990,
  'Amino acids (Lysine Methionine etc), Vitamins A D3 E B-complex, Minerals',
  'growth,nutrition,immunity,breeding', 'adult,puppy',
  88, NULL, 990, TRUE, '10ml twice daily; libido + breeding'),

('S109', 'SB09', 'Venkys', 'VenGro Drops – 20 ml',
  'growth_supplement', 'drops', '20 ml', 1100, 990,
  'Amino acids, DHA, EPA, Taurine, Vitamins A D3 E C B-complex',
  'growth,brain_development,vision', 'puppy,kitten',
  89, NULL, 990, TRUE, 'Paediatric; 0.5-2ml daily'),

('S110', 'SB09', 'Venkys', 'VenGro Syrup – 200 ml',
  'growth_supplement', 'liquid', '200 ml', 1100, 990,
  'Amino acids, DHA, EPA, Taurine, Vitamins A D3 E C B-complex',
  'growth,brain_development,vision', 'puppy,adult',
  90, NULL, 990, TRUE, '5ml twice daily; dogs cats & birds'),

('S111', 'SB09', 'Venkys', 'Fe-folate Iron Supplement Syrup – 200 ml',
  'iron_supplement', 'liquid', '200 ml', 1100, 990,
  'Elemental Iron 50mg, Folic Acid 175mcg, Vitamin B12 per 5ml',
  'anemia,iron_deficiency,blood', 'puppy,adult',
  91, NULL, 990, TRUE, '5ml twice daily; anemia & blood formation'),

('S112', 'SB09', 'Venkys', 'Thromb Beat Platelet Enhancer Syrup – 100 ml',
  'immunity_supplement', 'liquid', '100 ml', 1100, 990,
  'Papaya leaf extract, Tinospora, Withania, Iron, Folic acid',
  'platelets,immunity,tick_fever,blood', 'adult',
  92, NULL, 990, TRUE, 'Thrombocytopenia & tick fever support'),

('S113', 'SB09', 'Venkys', 'Biofit Liver & Kidney Cleanser Syrup – 200 ml',
  'liver_supplement', 'liquid', '200 ml', 1100, 990,
  'Milk thistle, Liquorice, Tribulus, Dandelion, Asparagus',
  'liver,kidney,detox', 'adult',
  93, NULL, 990, TRUE, 'Removes toxins; herbal blend'),

('S114', 'SB09', 'Venkys', 'Venlyte Pet Electrolyte Supplement',
  'electrolyte_supplement', 'powder', 'sachet', 1100, 990,
  'Sodium, Potassium, Vitamin C, Organic nutritive carrier',
  'dehydration,diarrhea,stress', 'adult,puppy',
  94, NULL, 990, TRUE, 'Dissolve in 1L drinking water; 300 mOsmol/L'),

('S115', 'SB09', 'Venkys', 'Gutwell Probiotic Prebiotic Powder – 30 g',
  'probiotic', 'powder', '30 g', 1100, 990,
  'Saccharomyces cerevisiae, Lactobacillus complex, FOS, MOS, Enzyme blend',
  'digestive,gut_health,immunity,hairball', 'adult,puppy,senior',
  95, NULL, 990, TRUE, '800 million CFU + enzyme complex'),

('S116', 'SB09', 'Venkys', 'Ventripro Puppy & Kitten Milk Replacer – 200 g',
  'milk_replacer', 'powder', '200 g', 1100, 990,
  'Protein, Fat, Colostrum, DHA, Calcium, Vitamins, Minerals',
  'growth,nutrition,immunity', 'puppy,newborn',
  96, NULL, 990, TRUE, 'Complete milk replacer; 1:4 dilution')

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

-- ---------------------------------------------------------------------------
-- 3. Sanity check: verify expected row count before commit
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    supplement_count INTEGER;
    brand_count      INTEGER;
BEGIN
    SELECT COUNT(*)                             INTO supplement_count FROM product_supplement;
    SELECT COUNT(DISTINCT brand_id)             INTO brand_count      FROM product_supplement;

    IF supplement_count <> 96 THEN
        RAISE EXCEPTION
            'Migration 050 failed: expected 96 supplement rows, got %',
            supplement_count;
    END IF;

    IF brand_count <> 6 THEN
        RAISE EXCEPTION
            'Migration 050 failed: expected 6 distinct brands (SB09,SB11-SB15), got %',
            brand_count;
    END IF;

    RAISE NOTICE
        'Migration 050 complete: product_supplement rows=%, brands=%',
        supplement_count, brand_count;
END $$;

COMMIT;
