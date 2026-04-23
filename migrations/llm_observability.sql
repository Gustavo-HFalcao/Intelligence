-- ─────────────────────────────────────────────────────────────────────────────
-- LLM Observability Table
-- Tracks every AI call: model, tokens, cost, tools used, duration, errors.
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New Query).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS llm_observability (
    id              uuid            DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at      timestamptz     DEFAULT now() NOT NULL,

    -- Who / What
    model           text            NOT NULL DEFAULT 'gpt-4o',
    username        text            NOT NULL DEFAULT 'system',
    session_id      text            NOT NULL DEFAULT '',
    call_type       text            NOT NULL DEFAULT 'query',  -- 'agentic' | 'stream' | 'query'

    -- Token usage
    prompt_tokens       integer     NOT NULL DEFAULT 0,
    completion_tokens   integer     NOT NULL DEFAULT 0,
    total_tokens        integer     NOT NULL DEFAULT 0,

    -- Cost estimate (USD)
    cost_usd        float8          NOT NULL DEFAULT 0.0,

    -- Tools invoked in this call
    tool_names      text[]          DEFAULT '{}',

    -- Performance
    duration_ms     integer         NOT NULL DEFAULT 0,

    -- Error (NULL = success)
    error           text
);

-- Index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_llm_obs_created_at ON llm_observability (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_obs_username   ON llm_observability (username);
CREATE INDEX IF NOT EXISTS idx_llm_obs_model      ON llm_observability (model);
CREATE INDEX IF NOT EXISTS idx_llm_obs_error      ON llm_observability (error) WHERE error IS NOT NULL;

-- Disable RLS (server-side only via service key)
ALTER TABLE llm_observability DISABLE ROW LEVEL SECURITY;
