---
name: supabase-rls-security
description: "Zero-Trust security rules for multi-tenant Supabase Postgres schemas, ensuring Row Level Security is never bypassed."
---

# Supabase Row Level Security (RLS)

When agents write SQL migrations for Supabase, they must follow strict multi-tenant data isolation rules.

## 1. Zero-Trust Tables
Never create a generic application table (e.g., `receipts`, `metrics`) without explicitly enabling RLS.
```sql
ALTER TABLE your_table ENABLE ROW LEVEL SECURITY;
```

## 2. Policy Creation Requirements
Always create explicit `SELECT`, `INSERT`, `UPDATE`, and `DELETE` policies tied to `auth.uid()`.
```sql
CREATE POLICY "Users can only view their own receipts"
ON receipts FOR SELECT
USING (auth.uid() = user_id);
```

## 3. Avoid Service Role Keys in Frontend
Do not suggest using the Supabase Service Role Key inside Reflex frontend components. Always use the anonymous key so RLS policies naturally protect the data based on the signed-in session.
