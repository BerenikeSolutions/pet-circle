-- Migration 009: Create hygiene_tip_cache table
-- Caches AI-generated one-line tips per (species, breed, item_id)

CREATE TABLE IF NOT EXISTS hygiene_tip_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    species VARCHAR(10) NOT NULL,
    breed_normalized VARCHAR(100) NOT NULL,
    item_id VARCHAR(50) NOT NULL,
    tip VARCHAR(300) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_hygiene_tip_lookup UNIQUE (species, breed_normalized, item_id)
);

CREATE INDEX IF NOT EXISTS idx_hygiene_tip_cache_lookup
    ON hygiene_tip_cache (species, breed_normalized);
