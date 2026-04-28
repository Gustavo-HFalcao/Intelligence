-- Migration: adiciona campos is_marco e marco_concluido em rdo_atividades
-- Run once in Supabase SQL editor

ALTER TABLE rdo_atividades
    ADD COLUMN IF NOT EXISTS is_marco        boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS marco_concluido boolean NOT NULL DEFAULT false;
