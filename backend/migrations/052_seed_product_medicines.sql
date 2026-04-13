-- Migration 052: Seed product_medicines table with tick, flea, deworming, and antibiotic data
--
-- Populates product_medicines (SKU-001 to SKU-054, 54 rows) with medicines data.
-- Source: project details/PetCircle_TickFlea_Deworming_DB.xlsx
-- Safe to re-run: uses ON CONFLICT (sku_id) DO UPDATE (upsert).

BEGIN;

-- Insert or update all 54 medicine SKUs
INSERT INTO product_medicines (
    sku_id, brand_id, brand_name, product_name, type, form, pack_size,
    mrp_paise, discounted_paise, key_ingredients, condition_tags, life_stage_tags,
    active, popularity_rank, monthly_units_sold, price_per_unit_paise, in_stock,
    dosage, repeat_frequency, notes
) VALUES
-- NexGard Spectra (Boehringer) — Combined Tick, Flea, Heartworm & Deworming
('SKU-001', 'BR-001', 'Boehringer', 'NexGard Spectra 2–3.5 kg', 'Tick, Flea & Deworming (Combined)', 'Chewables', 'Box of 1', 60000, 60000, 'Afoxolaner 9mg + Milbemycin Oxime 1.5mg', 'ticks,fleas,heartworm,roundworm,hookworm', 'dog', TRUE, 1, NULL, 60000, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks; Not for cats'),
('SKU-002', 'BR-001', 'Boehringer', 'NexGard Spectra 3.5–7.5 kg', 'Tick, Flea & Deworming (Combined)', 'Chewables', 'Box of 1', 80000, 80000, 'Afoxolaner 19mg + Milbemycin Oxime 3.1mg', 'ticks,fleas,heartworm,roundworm,hookworm', 'dog', TRUE, 2, NULL, 80000, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks'),
('SKU-003', 'BR-001', 'Boehringer', 'NexGard Spectra 7.5–15 kg', 'Tick, Flea & Deworming (Combined)', 'Chewables', 'Box of 1', 110000, 110000, 'Afoxolaner 38mg + Milbemycin Oxime 6.25mg', 'ticks,fleas,heartworm,roundworm,hookworm', 'dog', TRUE, 3, NULL, 110000, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks'),
('SKU-004', 'BR-001', 'Boehringer', 'NexGard Spectra 15–30 kg', 'Tick, Flea & Deworming (Combined)', 'Chewables', 'Box of 1', 140000, 140000, 'Afoxolaner 75mg + Milbemycin Oxime 12.5mg', 'ticks,fleas,heartworm,roundworm,hookworm', 'dog', TRUE, 4, NULL, 140000, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks'),
('SKU-005', 'BR-001', 'Boehringer', 'NexGard Spectra 30–60 kg', 'Tick, Flea & Deworming (Combined)', 'Chewables', 'Box of 1', 180000, 180000, 'Afoxolaner 150mg + Milbemycin Oxime 25mg', 'ticks,fleas,heartworm,roundworm,hookworm', 'dog', TRUE, 5, NULL, 180000, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks; Large breeds'),

-- NexGard (Boehringer) — Tick & Flea only
('SKU-006', 'BR-001', 'Boehringer', 'NexGard 2–4 kg', 'Tick & Flea Protection', 'Chewables', '3 Chewable Tablets', 50000, 50000, 'Afoxolaner 11.3mg', 'ticks,fleas', 'dog', TRUE, 6, NULL, 16667, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks, min weight 2kg'),
('SKU-007', 'BR-001', 'Boehringer', 'NexGard 4–10 kg', 'Tick & Flea Protection', 'Chewables', '3 Chewable Tablets', 80000, 80000, 'Afoxolaner 28.3mg', 'ticks,fleas', 'dog', TRUE, 7, NULL, 26667, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks, min weight 4kg'),
('SKU-008', 'BR-001', 'Boehringer', 'NexGard 10–25 kg', 'Tick & Flea Protection', 'Chewables', '3 Chewable Tablets', 120000, 120000, 'Afoxolaner 68mg', 'ticks,fleas', 'dog', TRUE, 8, NULL, 40000, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks, min weight 10kg'),
('SKU-009', 'BR-001', 'Boehringer', 'NexGard 25–50 kg', 'Tick & Flea Protection', 'Chewables', '3 Chewable Tablets', 160000, 160000, 'Afoxolaner 136mg', 'ticks,fleas', 'dog', TRUE, 9, NULL, 53333, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks, min weight 25kg; Large breeds'),

-- Broadline (Boehringer) — Spot-on for cats
('SKU-010', 'BR-001', 'Boehringer', 'Broadline <2.5 kg', 'Tick, Flea & Deworming (Combined)', 'Spot-on, pipette', '1 (0.3ml)', 80000, 80000, 'Fipronil 25mg + Methoprene 6.25mg + Eprinomectin 0.5mg + Praziquantel 15mg', 'ticks,fleas,roundworm,hookworm,tapeworm,lungworm,heartworm', 'cat', TRUE, 10, NULL, 80000, TRUE, '1 pipette per month', 'Monthly', 'For cats <2.5kg; min age 7 weeks'),
('SKU-011', 'BR-001', 'Boehringer', 'Broadline 2.5–7.5 kg', 'Tick, Flea & Deworming (Combined)', 'Spot-on, pipette', '1 (0.9ml)', 120000, 120000, 'Fipronil 50mg + Methoprene 60mg + Eprinomectin 0.5mg + Praziquantel 15mg', 'ticks,fleas,roundworm,hookworm,tapeworm,lungworm,heartworm', 'cat', TRUE, 11, NULL, 120000, TRUE, '1 pipette per month', 'Monthly', 'For cats 2.5–7.5kg; min age 7 weeks'),

-- Frontline Plus (Boehringer) — Spot-on for dogs and cats
('SKU-012', 'BR-001', 'Boehringer', 'Frontline Plus 2–10 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '3 pipettes (0.67ml each)', 90000, 90000, 'Fipronil 9.8% + (S)-Methoprene 8.8%', 'ticks,fleas,flea_eggs,flea_larvae', 'dog', TRUE, 12, NULL, 30000, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks; covers 2–10kg'),
('SKU-013', 'BR-001', 'Boehringer', 'Frontline Plus 10–20 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '3 pipettes (1.34ml each)', 130000, 130000, 'Fipronil 9.8% + (S)-Methoprene 8.8%', 'ticks,fleas,flea_eggs,flea_larvae', 'dog', TRUE, 13, NULL, 43333, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks; covers 10–20kg'),
('SKU-014', 'BR-001', 'Boehringer', 'Frontline Plus 20–40 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '3 pipettes (2.68ml each)', 180000, 180000, 'Fipronil 9.8% + (S)-Methoprene 8.8%', 'ticks,fleas,flea_eggs,flea_larvae', 'dog', TRUE, 14, NULL, 60000, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks; covers 20–40kg'),
('SKU-015', 'BR-001', 'Boehringer', 'Frontline Plus Cat', 'Tick & Flea Protection', 'Spot-on, pipette', '3 pipettes (0.5ml each)', 100000, 100000, 'Fipronil 9.8% + (S)-Methoprene 11.8%', 'ticks,fleas,flea_eggs,flea_larvae', 'cat', TRUE, 15, NULL, 33333, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks; single SKU for all cats'),

-- Drontal Plus (Elanco) — Deworming tablets
('SKU-016', 'BR-002', 'Elanco', 'Drontal Plus Tasty Tablets', 'Deworming', 'Tablets', '17×6 Tablets', 120000, 120000, 'Febantel 150mg + Pyrantel 144mg + Praziquantel 50mg', 'roundworm,hookworm,whipworm,tapeworm', 'dog', TRUE, 16, NULL, 1176, TRUE, '1 tablet per 10kg body weight', 'Every 3 months (adults); every 2 weeks till 3 months, monthly 3–6 months', 'Min weight 2kg; tasty beef flavour; puppies require more frequent dosing'),
('SKU-017', 'BR-002', 'Elanco', 'Drontal Puppy Suspension', 'Deworming', 'Syrup', '1 bottle (20ml)', 80000, 80000, 'Pyrantel 14.4mg/ml + Febantel 15mg/ml', 'roundworm,hookworm', 'dog-puppy', TRUE, 17, NULL, 80000, TRUE, '1ml per kg body weight', 'Every 2 weeks till 3 months age; monthly from 3–6 months', 'For puppies from 2 weeks of age'),

-- Milbemax (Elanco) — Deworming + Heartworm prevention
('SKU-018', 'BR-002', 'Elanco', 'Milbemax Tablets', 'Deworming', 'Tablets', '24×2 Tablets', 150000, 150000, 'Milbemycin Oxime 12.5mg + Praziquantel 125mg', 'roundworm,hookworm,whipworm,lungworm,eyeworm,heartworm', 'dog', TRUE, 18, NULL, 3125, TRUE, '1 tablet per 25kg body weight', 'Every 3 months', 'Min weight 5kg; also for heartworm prevention'),

-- Advocate (Elanco) — Flea & Deworming combined (NOT tick cover)
('SKU-019', 'BR-002', 'Elanco', 'Advocate 10–25 kg', 'Flea & Deworming (Combined)', 'Spot-on, pipette', '1 (2.5ml)', 120000, 120000, 'Imidacloprid 10% + Moxidectin 2.5%', 'fleas,heartworm,roundworm,hookworm,whipworm,mange,ear_mites', 'dog', TRUE, 19, NULL, 120000, TRUE, 'Apply once per month', 'Monthly', 'Min age 7 weeks; does NOT cover ticks'),
('SKU-020', 'BR-002', 'Elanco', 'Advocate 25–40 kg', 'Flea & Deworming (Combined)', 'Spot-on, pipette', '1 (4ml)', 180000, 180000, 'Imidacloprid 10% + Moxidectin 2.5%', 'fleas,heartworm,roundworm,hookworm,whipworm,mange,ear_mites', 'dog', TRUE, 20, NULL, 180000, TRUE, 'Apply once per month', 'Monthly', 'Min age 7 weeks; for 25-40kg dogs'),
('SKU-021', 'BR-002', 'Elanco', 'Advocate Cat 4–8 kg', 'Flea & Deworming (Combined)', 'Spot-on, pipette', '1 (0.8ml)', 140000, 140000, 'Imidacloprid 10% + Moxidectin 1%', 'fleas,heartworm,roundworm,hookworm,lungworm,ear_mites', 'cat', TRUE, 21, NULL, 140000, TRUE, 'Apply once per month', 'Monthly', 'Min age 9 weeks; does NOT cover ticks'),

-- Advantix (Elanco) — Tick & Flea ONLY (NOT for cats — TOXIC)
('SKU-022', 'BR-002', 'Elanco', 'Advantix 25–40 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '1 (4ml)', 100000, 100000, 'Imidacloprid 10% + Permethrin 50%', 'ticks,fleas,sand_flies,mosquitoes,stable_flies', 'dog', TRUE, 22, NULL, 100000, TRUE, 'Apply once every 2 weeks in high-exposure areas', 'Every 2 weeks (high-exposure); Monthly (standard)', 'TOXIC TO CATS; min age 7 weeks, min weight 1.5kg'),

-- Seresto (Elanco) — Tick & Flea Collar
('SKU-023', 'BR-002', 'Elanco', 'Seresto Small (upto 8kg)', 'Tick & Flea Protection', 'Collar', '1 collar', 200000, 200000, 'Imidacloprid 10% + Flumethrin 4.5%', 'ticks,fleas,lice', 'dog', TRUE, 23, NULL, 200000, TRUE, '1 collar, continuous release', '8 months protection per collar', 'Water-resistant; for dogs upto 8kg'),
('SKU-024', 'BR-002', 'Elanco', 'Seresto Large (>8kg)', 'Tick & Flea Protection', 'Collar', '1 collar', 250000, 250000, 'Imidacloprid 10% + Flumethrin 4.5%', 'ticks,fleas,lice', 'dog', TRUE, 24, NULL, 250000, TRUE, '1 collar, continuous release', '8 months protection per collar', 'Water-resistant; for dogs >8kg'),

-- Kiltix (Elanco) — Budget Tick & Flea Collar
('SKU-025', 'BR-002', 'Elanco', 'Kiltix Medium (upto 19kg)', 'Tick & Flea Protection', 'Collar', '1 collar', 80000, 80000, 'Propoxur 16% + Flumethrin 1.8%', 'ticks,fleas', 'dog', TRUE, 25, NULL, 80000, TRUE, '1 collar, continuous release', '3 months protection per collar', 'Budget-friendly option'),
('SKU-026', 'BR-002', 'Elanco', 'Kiltix Large (>19kg)', 'Tick & Flea Protection', 'Collar', '1 collar', 90000, 90000, 'Propoxur 16% + Flumethrin 1.8%', 'ticks,fleas', 'dog', TRUE, 26, NULL, 90000, TRUE, '1 collar, continuous release', '3 months protection per collar', 'Budget-friendly option; for dogs >19kg'),

-- Fluracto (Fluralaner—Indian brand)
('SKU-027', 'BR-003', 'Fluracto', 'Fluracto SoftChew 2–4.5 kg', 'Tick & Flea Protection', 'Soft Chew, Chewable', '1', 100000, 100000, 'Fluralaner 56.25mg', 'ticks,fleas', 'dog', TRUE, 27, NULL, 100000, TRUE, '1 chewable every 3 months', 'Every 3 months (12 weeks)', 'Min age 8 weeks, min weight 2kg; Indian brand'),
('SKU-028', 'BR-003', 'Fluracto', 'Fluracto SoftChew 4.5–10 kg', 'Tick & Flea Protection', 'Soft Chew, Chewable', '1', 120000, 120000, 'Fluralaner 112.5mg', 'ticks,fleas', 'dog', TRUE, 28, NULL, 120000, TRUE, '1 chewable every 3 months', 'Every 3 months (12 weeks)', 'Min age 8 weeks'),
('SKU-029', 'BR-003', 'Fluracto', 'Fluracto SoftChew 10–20 kg', 'Tick & Flea Protection', 'Soft Chew, Chewable', '1', 150000, 150000, 'Fluralaner 250mg', 'ticks,fleas', 'dog', TRUE, 29, NULL, 150000, TRUE, '1 chewable every 3 months', 'Every 3 months (12 weeks)', 'Min age 8 weeks'),
('SKU-030', 'BR-003', 'Fluracto', 'Fluracto SoftChew 20–40 kg', 'Tick & Flea Protection', 'Soft Chew, Chewable', '1', 200000, 200000, 'Fluralaner 500mg', 'ticks,fleas', 'dog', TRUE, 30, NULL, 200000, TRUE, '1 chewable every 3 months', 'Every 3 months (12 weeks)', 'Min age 8 weeks'),
('SKU-031', 'BR-003', 'Fluracto', 'Fluracto SoftChew 40–56 kg', 'Tick & Flea Protection', 'Soft Chew, Chewable', '1', 250000, 250000, 'Fluralaner 750mg', 'ticks,fleas', 'dog', TRUE, 31, NULL, 250000, TRUE, '1 chewable every 3 months', 'Every 3 months (12 weeks)', 'Min age 8 weeks; for large breeds'),

-- Bravecto (MSD Animal Health) — 12-week Flea & Tick
('SKU-032', 'BR-004', 'MSD Animal Health', 'Bravecto 2–4.5 kg', 'Tick & Flea Protection', 'Chewables', '1', 80000, 80000, 'Fluralaner 112.5mg', 'ticks,fleas', 'dog', TRUE, 32, NULL, 80000, TRUE, '1 chewable every 12 weeks', 'Every 3 months (12 weeks)', 'Min age 8 weeks; longest-acting oral flea+tick'),
('SKU-033', 'BR-004', 'MSD Animal Health', 'Bravecto 4.5–10 kg', 'Tick & Flea Protection', 'Chewables', '1', 120000, 120000, 'Fluralaner 250mg', 'ticks,fleas', 'dog', TRUE, 33, NULL, 120000, TRUE, '1 chewable every 12 weeks', 'Every 3 months (12 weeks)', 'Min age 8 weeks'),
('SKU-034', 'BR-004', 'MSD Animal Health', 'Bravecto 10–20 kg', 'Tick & Flea Protection', 'Chewables', '1', 150000, 150000, 'Fluralaner 500mg', 'ticks,fleas', 'dog', TRUE, 34, NULL, 150000, TRUE, '1 chewable every 12 weeks', 'Every 3 months (12 weeks)', 'Min age 8 weeks'),
('SKU-035', 'BR-004', 'MSD Animal Health', 'Bravecto 20–40 kg', 'Tick & Flea Protection', 'Chewables', '1', 200000, 200000, 'Fluralaner 1000mg', 'ticks,fleas', 'dog', TRUE, 35, NULL, 200000, TRUE, '1 chewable every 12 weeks', 'Every 3 months (12 weeks)', 'Min age 8 weeks'),
('SKU-036', 'BR-004', 'MSD Animal Health', 'Bravecto Spot-on Cat 2.8–6.25 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '1 pipette', 120000, 120000, 'Fluralaner 280mg', 'ticks,fleas,ear_mites', 'cat', TRUE, 36, NULL, 120000, TRUE, '1 pipette every 12 weeks', 'Every 3 months (12 weeks)', 'Min age 6 months; also covers ear mites'),

-- Bayrocin (Elanco) — Antibiotic
('SKU-037', 'BR-002', 'Elanco', 'Bayrocin Enrofloxacin 150mg', 'Antibiotic (Bacterial Infections)', 'Tablets', 'Strip of 10 tablets', 120000, 120000, 'Enrofloxacin 150mg', 'skin_infection,uti,respiratory_infection,wound_infection,gi_infection', 'dog,cat', TRUE, 37, NULL, 12000, TRUE, '5mg/kg body weight every 24 hours', '3–5 days course', 'Prescription required; not for ticks/fleas/worms'),

-- Drontal Cat (Elanco)
('SKU-038', 'BR-002', 'Elanco', 'Drontal Cat Deworming', 'Deworming', 'Tablets', 'Strip of 2 tablets', 60000, 60000, 'Pyrantel 230mg + Praziquantel 20mg', 'roundworm,hookworm,tapeworm', 'cat', TRUE, 38, NULL, 30000, TRUE, '1 tablet per 4kg body weight', 'Every 3 months', 'For cats above 6 weeks; not for pregnant cats'),

-- Interceptor Plus (MSD) — Heartworm + Deworming
('SKU-039', 'BR-004', 'MSD Animal Health', 'Interceptor Plus 2–8 kg', 'Deworming', 'Tablets', 'Box of 6', 120000, 120000, 'Milbemycin Oxime 2.3mg + Praziquantel 22.8mg', 'heartworm,roundworm,hookworm,whipworm,tapeworm', 'dog', TRUE, 39, NULL, 20000, TRUE, '1 tablet monthly', 'Monthly', 'Min age 6 weeks; beef flavoured'),

-- Himalaya Erina EP (Indian brand)
('SKU-040', 'BR-005', 'Himalaya', 'Erina EP Tick & Flea Spray', 'Tick & Flea Protection', 'Spray', '200ml bottle', 20000, 20000, 'Permethrin 0.1% + Pyrethrin 0.05%', 'ticks,fleas', 'dog', TRUE, 40, NULL, 20000, TRUE, 'Spray on coat, avoid eyes; repeat as needed', 'Every 7–10 days or as needed', 'OTC; India-made; budget option; not for cats'),

-- Beaphar Collar (Beaphar—Netherlands)
('SKU-041', 'BR-006', 'Beaphar', 'Beaphar Tick & Flea Collar Dog', 'Tick & Flea Protection', 'Collar', '1 collar', 60000, 60000, 'Deltamethrin 4%', 'ticks,fleas', 'dog', TRUE, 41, NULL, 60000, TRUE, '1 collar, continuous release', '4 months protection', 'Water-resistant; budget collar option in India'),

-- Panacur (Merck)
('SKU-042', 'BR-007', 'Merck Animal Health', 'Panacur Fenbendazole 10% Suspension', 'Deworming', 'Syrup/Suspension', '250ml bottle', 120000, 120000, 'Fenbendazole 100mg/ml', 'roundworm,hookworm,whipworm,giardia', 'dog', TRUE, 42, NULL, 120000, TRUE, '50mg/kg (0.5ml/kg) once daily for 3–5 days', 'Every 3 months or as per vet', 'Safe for pregnant animals; also treats Giardia'),

-- Milpro (Virbac)
('SKU-043', 'BR-008', 'Virbac', 'Milpro Deworming <5kg', 'Deworming', 'Tablets', '1 strip', 80000, 80000, 'Milbemycin Oxime 2.5mg + Praziquantel 25mg', 'roundworm,hookworm,whipworm,tapeworm,heartworm', 'dog', TRUE, 43, NULL, 80000, TRUE, '1 tablet per 5kg body weight', 'Every 3 months', 'Min age 2 weeks, min weight 0.5kg'),
('SKU-044', 'BR-008', 'Virbac', 'Milpro Deworming >5kg', 'Deworming', 'Tablets', '1 strip', 100000, 100000, 'Milbemycin Oxime 5mg + Praziquantel 50mg', 'roundworm,hookworm,whipworm,tapeworm,heartworm', 'dog', TRUE, 44, NULL, 100000, TRUE, '1 tablet per 5kg body weight', 'Every 3 months', 'Min age 2 weeks, min weight 5kg'),
('SKU-045', 'BR-008', 'Virbac', 'Milpro Deworming Cat', 'Deworming', 'Tablets', '1 strip', 70000, 70000, 'Milbemycin Oxime 4mg + Praziquantel 10mg', 'roundworm,hookworm,tapeworm,heartworm', 'cat', TRUE, 45, NULL, 70000, TRUE, '1 tablet per 2kg body weight', 'Every 3 months', 'Min age 6 weeks, min weight 0.5kg'),

-- Effipro (Virbac)
('SKU-046', 'BR-008', 'Virbac', 'Effipro 2–10 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '4 pipettes (0.67ml each)', 80000, 80000, 'Fipronil 9.7%', 'ticks,fleas', 'dog', TRUE, 46, NULL, 20000, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks; fipronil without IGR'),
('SKU-047', 'BR-008', 'Virbac', 'Effipro 10–20 kg', 'Tick & Flea Protection', 'Spot-on, pipette', '4 pipettes (1.34ml each)', 120000, 120000, 'Fipronil 9.7%', 'ticks,fleas', 'dog', TRUE, 47, NULL, 30000, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks'),
('SKU-048', 'BR-008', 'Virbac', 'Effipro Cat', 'Tick & Flea Protection', 'Spot-on, pipette', '4 pipettes (0.5ml each)', 100000, 100000, 'Fipronil 9.7%', 'ticks,fleas', 'cat', TRUE, 48, NULL, 25000, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks'),

-- Simparica (Zoetis)
('SKU-049', 'BR-009', 'Zoetis', 'Simparica 1.3–2.5 kg', 'Tick & Flea Protection', 'Chewables', 'Box of 3', 100000, 100000, 'Sarolaner 5mg', 'ticks,fleas,mange_demodex,mange_sarcoptes', 'dog', TRUE, 49, NULL, 33333, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks, min weight 1.3kg'),
('SKU-050', 'BR-009', 'Zoetis', 'Simparica 2.5–5 kg', 'Tick & Flea Protection', 'Chewables', 'Box of 3', 130000, 130000, 'Sarolaner 10mg', 'ticks,fleas,mange', 'dog', TRUE, 50, NULL, 43333, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks'),
('SKU-051', 'BR-009', 'Zoetis', 'Simparica 5–10 kg', 'Tick & Flea Protection', 'Chewables', 'Box of 3', 160000, 160000, 'Sarolaner 20mg', 'ticks,fleas,mange', 'dog', TRUE, 51, NULL, 53333, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks'),
('SKU-052', 'BR-009', 'Zoetis', 'Simparica 10–20 kg', 'Tick & Flea Protection', 'Chewables', 'Box of 3', 220000, 220000, 'Sarolaner 40mg', 'ticks,fleas,mange', 'dog', TRUE, 52, NULL, 73333, TRUE, '1 chewable per month', 'Monthly', 'Min age 8 weeks'),

-- Stronghold (Zoetis) — For cats (NO TICK cover)
('SKU-053', 'BR-009', 'Zoetis', 'Stronghold 2.6–7.5 kg Cat', 'Flea & Deworming (Combined)', 'Spot-on, pipette', '3 pipettes (0.75ml each)', 120000, 120000, 'Selamectin 60mg/ml', 'fleas,heartworm,roundworm,hookworm,ear_mites,mange', 'cat', TRUE, 53, NULL, 40000, TRUE, 'Apply once per month', 'Monthly', 'Min age 8 weeks; does NOT cover ticks in cats'),

-- Wormectin Plus (Indian Immunologicals)
('SKU-054', 'BR-010', 'Indian Immunologicals', 'Wormectin Plus Tablets Dog', 'Deworming', 'Tablets', '1 strip', 60000, 60000, 'Ivermectin 6mcg/kg + Praziquantel 5mg/kg', 'roundworm,hookworm,tapeworm,mange_external', 'dog', TRUE, 54, NULL, 60000, TRUE, 'As directed by vet', 'Every 3 months or as per vet', 'Budget dewormer; widely available in India; vet prescription advised')

ON CONFLICT (sku_id) DO UPDATE SET
    brand_id             = EXCLUDED.brand_id,
    brand_name           = EXCLUDED.brand_name,
    product_name         = EXCLUDED.product_name,
    type                 = EXCLUDED.type,
    form                 = EXCLUDED.form,
    pack_size            = EXCLUDED.pack_size,
    mrp_paise            = EXCLUDED.mrp_paise,
    discounted_paise     = EXCLUDED.discounted_paise,
    key_ingredients      = EXCLUDED.key_ingredients,
    condition_tags       = EXCLUDED.condition_tags,
    life_stage_tags      = EXCLUDED.life_stage_tags,
    active               = TRUE,
    popularity_rank      = EXCLUDED.popularity_rank,
    monthly_units_sold   = EXCLUDED.monthly_units_sold,
    price_per_unit_paise = EXCLUDED.price_per_unit_paise,
    in_stock             = EXCLUDED.in_stock,
    dosage               = EXCLUDED.dosage,
    repeat_frequency     = EXCLUDED.repeat_frequency,
    notes                = EXCLUDED.notes;

-- Sanity check row count before commit
DO $$
DECLARE
    medicines_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO medicines_count FROM product_medicines;

    IF medicines_count < 54 THEN
        RAISE EXCEPTION 'product_medicines seed failed: expected >= 54 rows, got %', medicines_count;
    END IF;

    RAISE NOTICE 'Seed complete: product_medicines=%', medicines_count;
END $$;

COMMIT;
