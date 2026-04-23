-- Migration: Add view_token column to rdo_master for public RDO viewing
ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS view_token text DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS rdo_master_view_token_idx ON rdo_master(view_token) WHERE view_token <> '';
