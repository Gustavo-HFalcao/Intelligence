-- Migration: Add equipe_alocada column to rdo_master
-- Tracks the number of team members on site for each RDO
ALTER TABLE rdo_master
  ADD COLUMN IF NOT EXISTS equipe_alocada integer;
