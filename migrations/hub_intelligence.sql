-- Migration: Hub Intelligence cache table
-- Stores AI-generated insights per contract with TTL support
CREATE TABLE IF NOT EXISTS hub_intelligence (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contrato    text NOT NULL,
    client_id   uuid,
    insight_type text NOT NULL DEFAULT 'obra_insight',  -- 'obra_insight' | 'predictive'
    insight_text text NOT NULL DEFAULT '',
    generated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (contrato, insight_type)
);

CREATE INDEX IF NOT EXISTS hub_intelligence_contrato_idx ON hub_intelligence (contrato, insight_type);
CREATE INDEX IF NOT EXISTS hub_intelligence_client_idx ON hub_intelligence (client_id);
