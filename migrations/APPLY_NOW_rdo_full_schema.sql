-- ============================================================
-- MIGRATION CONSOLIDADA — RDO Full Schema
-- Aplicar no Supabase SQL Editor do projeto DASH-BT
-- Idempotente: usa ADD COLUMN IF NOT EXISTS em tudo
-- ============================================================

-- 1. rdo_atividades — campos de marco e link ao cronograma
ALTER TABLE rdo_atividades
    ADD COLUMN IF NOT EXISTS is_marco        boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS marco_concluido boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS is_extra        boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS atividade_id    uuid    REFERENCES hub_atividades(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS rdo_atividades_atividade_id_idx ON rdo_atividades (atividade_id);

-- 2. hub_atividades — tipo de medição e campos de histórico RDO
ALTER TABLE hub_atividades
    ADD COLUMN IF NOT EXISTS tipo_medicao   text NOT NULL DEFAULT 'porcentagem'
        CHECK (tipo_medicao IN ('marco', 'porcentagem', 'quantidade')),
    ADD COLUMN IF NOT EXISTS exec_qty       float8 NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_qty      float8 NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_rdo_date  date,
    ADD COLUMN IF NOT EXISTS last_rdo_id    uuid;

-- 3. agente_insights — tabela para insights do agente de IA
CREATE TABLE IF NOT EXISTS agente_insights (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contrato    text NOT NULL,
    client_id   uuid,
    insights    jsonb NOT NULL DEFAULT '[]'::jsonb,
    last_rdo_id uuid,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (contrato)
);

CREATE INDEX IF NOT EXISTS agente_insights_contrato_idx ON agente_insights (contrato);

-- 4. hub_atividade_historico — histórico de atualizações via RDO
CREATE TABLE IF NOT EXISTS hub_atividade_historico (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    atividade_id            uuid REFERENCES hub_atividades(id) ON DELETE CASCADE,
    contrato                text NOT NULL,
    rdo_id                  uuid,
    data                    date,
    conclusao_pct_anterior  int NOT NULL DEFAULT 0,
    conclusao_pct_novo      int NOT NULL DEFAULT 0,
    exec_qty_novo           float8,
    producao_dia            float8,
    total_qty               float8,
    unidade                 text,
    client_id               uuid,
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS hub_atividade_historico_atividade_idx ON hub_atividade_historico (atividade_id);
CREATE INDEX IF NOT EXISTS hub_atividade_historico_contrato_idx  ON hub_atividade_historico (contrato);
CREATE INDEX IF NOT EXISTS hub_atividade_historico_rdo_idx       ON hub_atividade_historico (rdo_id);

-- 5. rdo_master — view_token (se não existir)
ALTER TABLE rdo_master
    ADD COLUMN IF NOT EXISTS view_token text UNIQUE;

-- 6. Confirmar
SELECT
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='rdo_atividades'    AND column_name='is_marco')        AS rdo_is_marco_ok,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='rdo_atividades'    AND column_name='atividade_id')    AS rdo_atividade_id_ok,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='hub_atividades'    AND column_name='exec_qty')        AS hub_exec_qty_ok,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='hub_atividades'    AND column_name='last_rdo_date')   AS hub_last_rdo_date_ok,
    (SELECT COUNT(*) FROM information_schema.tables   WHERE table_name='agente_insights')                                    AS agente_insights_ok,
    (SELECT COUNT(*) FROM information_schema.tables   WHERE table_name='hub_atividade_historico')                           AS historico_ok;
