-- Migration: agente_insights table + rdo_atividades extras + hub_atividades tipo_medicao
-- Run once in Supabase SQL editor

-- 1. Tabela agente_insights (upsert por contrato, guarda array JSON de insights)
CREATE TABLE IF NOT EXISTS agente_insights (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contrato    text NOT NULL,
    client_id   uuid,
    insights    jsonb NOT NULL DEFAULT '[]'::jsonb,
    last_rdo_id uuid,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (contrato, client_id)
);

CREATE INDEX IF NOT EXISTS agente_insights_contrato_idx ON agente_insights (contrato);
CREATE INDEX IF NOT EXISTS agente_insights_client_idx   ON agente_insights (client_id);

-- 2. rdo_atividades — campos para atividades extras (não mapeadas no cronograma)
ALTER TABLE rdo_atividades
    ADD COLUMN IF NOT EXISTS is_extra      boolean     NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS atividade_id  uuid        REFERENCES hub_atividades(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS rdo_atividades_atividade_id_idx ON rdo_atividades (atividade_id);

-- 3. hub_atividades — tipo de medição: marco | porcentagem | quantidade
ALTER TABLE hub_atividades
    ADD COLUMN IF NOT EXISTS tipo_medicao text NOT NULL DEFAULT 'porcentagem'
        CHECK (tipo_medicao IN ('marco', 'porcentagem', 'quantidade'));

-- 4. hub_atividades — status para aprovação de atividades extras
-- Garante que 'Pendente Aprovação' é valor aceito (se houver enum, adiciona)
DO $$
BEGIN
    -- Se status_atividade for enum, adiciona valor; se for text, não precisa fazer nada
    IF EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_attribute a ON a.atttypid = t.oid
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = 'hub_atividades' AND a.attname = 'status_atividade'
        LIMIT 1
    ) THEN
        -- É enum: adiciona novo valor se não existir
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname LIKE '%status%' AND e.enumlabel = 'Pendente Aprovação'
        ) THEN
            ALTER TYPE status_atividade_enum ADD VALUE IF NOT EXISTS 'Pendente Aprovação';
        END IF;
    END IF;
END$$;
