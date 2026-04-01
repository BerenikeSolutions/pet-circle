-- Migration 034: Add onboarding_data (users) and age_text (pets)
--
-- onboarding_data: JSONB column for transient onboarding step metadata
--   (food_type, breed_age_attempts, preventive_attempts, needs_species).
--   Cleared to NULL when onboarding completes.
--
-- age_text: Stores the user's original age input (e.g. "4 years", "6 months",
--   "puppy") so services can display age as stated. DOB is still computed from
--   age_text for date-based preventive scheduling.

ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_data JSONB;

ALTER TABLE pets ADD COLUMN IF NOT EXISTS age_text VARCHAR(50);
