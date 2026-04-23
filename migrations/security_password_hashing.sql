-- ============================================================
-- Migration: Password Hashing + Row Level Security
-- Applied manually in Supabase on ~2026-03-23
-- ============================================================

-- 1. Add pw_hash column to login table (stores PBKDF2 hash)
--    The old 'password' column is kept temporarily for rollback safety.
ALTER TABLE login ADD COLUMN IF NOT EXISTS pw_hash text;

-- 2. Copy existing plain-text passwords to pw_hash as-is.
--    The application's verify_password() handles plain-text as fallback
--    during the transition period. After all users log in once, passwords
--    will have been re-hashed on the Python side.
--    NOTE: If you already migrated via the Python script, skip this step.
UPDATE login SET pw_hash = password WHERE pw_hash IS NULL AND password IS NOT NULL;

-- 3. Ensure the 'username' column exists (used as filter key in sb_select)
--    The login table may have 'user' as the primary user identifier.
--    The code handles both via _get_password_field().

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Enable RLS on all tables that store sensitive or business data.
-- The service role key (SUPABASE_SERVICE_KEY) bypasses RLS,
-- so all PostgREST calls from the backend use it and are unaffected.
-- RLS protects against: direct client access, dashboard key exposure.
-- ============================================================

-- Core business tables
ALTER TABLE contratos ENABLE ROW LEVEL SECURITY;
ALTER TABLE projetos ENABLE ROW LEVEL SECURITY;
ALTER TABLE obras ENABLE ROW LEVEL SECURITY;
ALTER TABLE financeiro ENABLE ROW LEVEL SECURITY;
ALTER TABLE om ENABLE ROW LEVEL SECURITY;

-- Auth & access
ALTER TABLE login ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;

-- Operational modules
ALTER TABLE rdo_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE fuel_reimbursements ENABLE ROW LEVEL SECURITY;
ALTER TABLE relatorios ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_sender ENABLE ROW LEVEL SECURITY;

-- Observability
ALTER TABLE system_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;

-- Config
ALTER TABLE contract_features ENABLE ROW LEVEL SECURITY;

-- Block all direct (anon/authenticated JWT) access — service role bypasses this
-- Apply this policy to every table above:
-- CREATE POLICY "deny_all_direct_access" ON <table> USING (false);
-- (Replace <table> with each table name above)

-- ============================================================
-- NOTES
-- ============================================================
-- 1. The application uses SUPABASE_SERVICE_KEY for ALL database
--    operations (via supabase_client.py). This key bypasses RLS.
--    RLS is a defense-in-depth measure, not the primary auth layer.
--
-- 2. The 'fallback' hardcoded account was removed from global_state.py.
--
-- 3. auth_utils.py uses PBKDF2-HMAC-SHA256 (260k iterations).
--    Legacy SHA-256 "salt:hash" format and plain text are handled
--    as read-only fallbacks for backwards compatibility.
--
-- 4. The execute_safe_query RPC has a whitelist of 11 operational tables.
--    login, roles, and system_logs are NOT accessible via AI SQL queries.
