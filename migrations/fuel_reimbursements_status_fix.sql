-- Fix: fuel_reimbursements.status was storing timestamp; add proper submitted_at column
-- Run this once in Supabase SQL editor

-- Add submitted_at column if missing
ALTER TABLE fuel_reimbursements
  ADD COLUMN IF NOT EXISTS submitted_at timestamptz;

-- Migrate existing rows: if status looks like a timestamp, copy to submitted_at
UPDATE fuel_reimbursements
SET
  submitted_at = status::timestamptz,
  status = 'pendente'
WHERE status ~ '^\d{4}-\d{2}-\d{2}T';

-- Ensure status has a default for new rows
ALTER TABLE fuel_reimbursements
  ALTER COLUMN status SET DEFAULT 'pendente';
