-- Migration: Add conditions, condition_medications, condition_monitoring, and contacts tables
-- Date: 2026-03-17
-- Purpose: Support extraction and manual entry of pet conditions (with medications/monitoring) and contacts

-- 1. Conditions table
CREATE TABLE IF NOT EXISTS conditions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    diagnosis VARCHAR(500),
    condition_type VARCHAR(20) NOT NULL DEFAULT 'chronic',
    diagnosed_at DATE,
    notes VARCHAR(1000),
    source VARCHAR(20) NOT NULL DEFAULT 'extraction',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_conditions_type CHECK (condition_type IN ('chronic', 'episodic', 'resolved')),
    CONSTRAINT chk_conditions_source CHECK (source IN ('extraction', 'manual')),
    CONSTRAINT uq_conditions_pet_name UNIQUE (pet_id, name)
);

CREATE INDEX IF NOT EXISTS idx_conditions_pet_id ON conditions(pet_id);
CREATE INDEX IF NOT EXISTS idx_conditions_document_id ON conditions(document_id);

-- 2. Condition medications table
CREATE TABLE IF NOT EXISTS condition_medications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condition_id UUID NOT NULL REFERENCES conditions(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    dose VARCHAR(100),
    frequency VARCHAR(100),
    route VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    started_at DATE,
    notes VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_condition_medications_status CHECK (status IN ('active', 'discontinued'))
);

CREATE INDEX IF NOT EXISTS idx_condition_medications_condition_id ON condition_medications(condition_id);

-- 3. Condition monitoring table
CREATE TABLE IF NOT EXISTS condition_monitoring (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condition_id UUID NOT NULL REFERENCES conditions(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    frequency VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_condition_monitoring_condition_id ON condition_monitoring(condition_id);

-- 4. Contacts table
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'veterinarian',
    name VARCHAR(200) NOT NULL,
    clinic_name VARCHAR(200),
    phone VARCHAR(30),
    email VARCHAR(200),
    address VARCHAR(500),
    source VARCHAR(20) NOT NULL DEFAULT 'extraction',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_contacts_role CHECK (role IN ('veterinarian', 'groomer', 'trainer', 'specialist', 'other')),
    CONSTRAINT chk_contacts_source CHECK (source IN ('extraction', 'manual')),
    CONSTRAINT uq_contacts_pet_name_role UNIQUE (pet_id, name, role)
);

CREATE INDEX IF NOT EXISTS idx_contacts_pet_id ON contacts(pet_id);
CREATE INDEX IF NOT EXISTS idx_contacts_document_id ON contacts(document_id);
