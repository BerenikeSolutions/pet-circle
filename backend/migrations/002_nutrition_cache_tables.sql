-- PetCircle Phase 1 — Migration 002: Nutrition Cache Tables
-- Adds two cache tables for AI-generated nutrition data.
-- Run in Supabase SQL editor after 001_add_dashboard_tables.sql.

-- 1. Cache for AI-generated breed-specific nutrition targets
CREATE TABLE IF NOT EXISTS nutrition_target_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    species VARCHAR(10) NOT NULL,
    breed_normalized VARCHAR(100) NOT NULL,
    age_category VARCHAR(20) NOT NULL,
    targets_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_nutrition_target_lookup UNIQUE (species, breed_normalized, age_category)
);

-- 2. Cache for AI-estimated nutrition of unknown/homemade foods
CREATE TABLE IF NOT EXISTS food_nutrition_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    food_label_normalized VARCHAR(200) NOT NULL,
    food_type VARCHAR(20) NOT NULL,
    nutrition_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_food_nutrition_lookup UNIQUE (food_label_normalized, food_type)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_nutrition_target_lookup
    ON nutrition_target_cache (species, breed_normalized, age_category);

CREATE INDEX IF NOT EXISTS idx_food_nutrition_lookup
    ON food_nutrition_cache (food_label_normalized, food_type);
