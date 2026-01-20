-- Migration: Add legal_basis column to contract_review_items
-- Date: 2024-12-24
-- Description: Add legal_basis field to store review legal basis (laws, regulations, standards)

-- Add legal_basis column to contract_review_items table
ALTER TABLE contract_review_items
ADD COLUMN IF NOT EXISTS legal_basis TEXT DEFAULT '';

-- Add comment
COMMENT ON COLUMN contract_review_items.legal_basis IS '审查依据（法律法规、标准条款等）';
