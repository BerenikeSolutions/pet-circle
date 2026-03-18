-- PetCircle Phase 1 — Dashboard Tables Migration
-- Creates tables for weight history, diet items, hygiene preferences,
-- product catalog, nudges, and cart items.

-- Weight history: tracks pet weight measurements over time
CREATE TABLE IF NOT EXISTS weight_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    weight DECIMAL(5,2) NOT NULL,
    recorded_at DATE NOT NULL,
    note VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_weight_history_pet_id ON weight_history(pet_id);

-- Diet items: food and supplements in a pet's daily diet
CREATE TABLE IF NOT EXISTS diet_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,
    icon VARCHAR(10),
    label VARCHAR(200) NOT NULL,
    detail VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_diet_item UNIQUE (pet_id, label, type)
);
CREATE INDEX IF NOT EXISTS idx_diet_items_pet_id ON diet_items(pet_id);

-- Hygiene preferences: grooming frequency and reminder settings
CREATE TABLE IF NOT EXISTS hygiene_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    item_id VARCHAR(50) NOT NULL,
    freq INTEGER NOT NULL DEFAULT 1,
    unit VARCHAR(10) NOT NULL DEFAULT 'month',
    reminder BOOLEAN NOT NULL DEFAULT FALSE,
    last_done VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_hygiene_pref UNIQUE (pet_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_hygiene_preferences_pet_id ON hygiene_preferences(pet_id);

-- Product catalog: imported from nutrition Excel database
CREATE TABLE IF NOT EXISTS product_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(30) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    description TEXT,
    crude_protein DECIMAL(5,2),
    crude_fat DECIMAL(5,2),
    crude_fibre DECIMAL(5,2),
    moisture DECIMAL(5,2),
    ash DECIMAL(5,2),
    calcium DECIMAL(5,3),
    phosphorus DECIMAL(5,3),
    omega_3 INTEGER,
    omega_6 INTEGER,
    vitamin_e INTEGER,
    vitamin_d3 INTEGER,
    glucosamine INTEGER,
    probiotics VARCHAR(30),
    energy_kcal INTEGER,
    active_ingredient TEXT,
    indication TEXT,
    dosage TEXT,
    frequency VARCHAR(200),
    formulation VARCHAR(50),
    prescription_required BOOLEAN,
    life_stage VARCHAR(50),
    breed_size VARCHAR(50),
    type VARCHAR(50),
    pack_size VARCHAR(100),
    mrp VARCHAR(100),
    notes TEXT,
    cart_item_id VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_product_catalog_category ON product_catalog(category);

-- Nudges: actionable health recommendations
CREATE TABLE IF NOT EXISTS nudges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    category VARCHAR(30) NOT NULL,
    priority VARCHAR(10) NOT NULL,
    icon VARCHAR(10),
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    mandatory BOOLEAN NOT NULL DEFAULT FALSE,
    orderable BOOLEAN NOT NULL DEFAULT FALSE,
    price VARCHAR(20),
    order_type VARCHAR(30),
    cart_item_id VARCHAR(10),
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_nudges_pet_id ON nudges(pet_id);

-- Cart items: shopping cart for pet health products
CREATE TABLE IF NOT EXISTS cart_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    product_id VARCHAR(10) NOT NULL,
    icon VARCHAR(10),
    name VARCHAR(200) NOT NULL,
    sub VARCHAR(200),
    price INTEGER NOT NULL,
    tag VARCHAR(30),
    tag_color VARCHAR(10),
    in_cart BOOLEAN NOT NULL DEFAULT FALSE,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_cart_item UNIQUE (pet_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_cart_items_pet_id ON cart_items(pet_id);

-- Add custom_recurrence_days to preventive_records for vaccine frequency persistence
ALTER TABLE preventive_records ADD COLUMN IF NOT EXISTS custom_recurrence_days INTEGER DEFAULT NULL;

-- Ideal weight cache: AI-generated breed-specific weight ranges
-- Keyed by (species, breed, gender, age_category) — shared across all pets of same combo
CREATE TABLE IF NOT EXISTS ideal_weight_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    species VARCHAR(10) NOT NULL,
    breed_normalized VARCHAR(100) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    age_category VARCHAR(20) NOT NULL,
    min_weight DECIMAL(5,2) NOT NULL,
    max_weight DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ideal_weight_lookup UNIQUE (species, breed_normalized, gender, age_category)
);
