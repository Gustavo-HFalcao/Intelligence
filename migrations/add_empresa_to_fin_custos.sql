-- Migration: Adiciona campos empresa e atividade_id em fin_custos
-- Para gestão de custos por fornecedor na obra e vínculo com atividades

ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS empresa TEXT DEFAULT '';
ALTER TABLE fin_custos ADD COLUMN IF NOT EXISTS atividade_id TEXT DEFAULT NULL;

-- Comentário: empresa = nome da empresa/fornecedor (ex: "Construtora ABC")
-- atividade_id = FK para atividade do cronograma (opcional)
