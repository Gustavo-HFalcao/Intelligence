-- Migration: Add email and whatsapp columns to login table
-- These are used for alert notifications and Action AI document delivery
ALTER TABLE login ADD COLUMN IF NOT EXISTS email text DEFAULT '';
ALTER TABLE login ADD COLUMN IF NOT EXISTS whatsapp text DEFAULT '';
