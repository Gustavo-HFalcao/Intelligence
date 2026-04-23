-- Migration: Adiciona todas as colunas faltantes em fin_custos
-- Rode este script no Supabase SQL Editor

ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS data_custo      DATE          DEFAULT NULL;
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS atividade_id    TEXT          DEFAULT NULL;
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS empresa         TEXT          DEFAULT '';
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS categoria_id    TEXT          DEFAULT NULL;
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS categoria_nome  TEXT          DEFAULT '';
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS observacoes     TEXT          DEFAULT '';
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS valor_previsto  NUMERIC(15,2) DEFAULT 0;
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS valor_executado NUMERIC(15,2) DEFAULT 0;
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS status          TEXT          DEFAULT 'previsto';
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS contrato        TEXT          DEFAULT NULL;
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS descricao       TEXT          DEFAULT '';

-- Recarrega schema cache do PostgREST (necessário após ALTER TABLE)
NOTIFY pgrst, 'reload schema';
