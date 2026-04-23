-- Migration: add dep_tipo column to hub_atividades
-- dep_tipo values: 'sem_dep' | 'tradicional' | 'progresso'
-- Backfill: activities with a dependencia_id → 'tradicional', others → 'sem_dep'

ALTER TABLE hub_atividades
  ADD COLUMN IF NOT EXISTS dep_tipo text NOT NULL DEFAULT 'sem_dep';

UPDATE hub_atividades
  SET dep_tipo = 'tradicional'
  WHERE dependencia_id IS NOT NULL
    AND dependencia_id != ''
    AND dep_tipo = 'sem_dep';
