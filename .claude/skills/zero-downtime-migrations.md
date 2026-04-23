---
name: zero-downtime-migrations
description: "Mandates non-blocking SQL procedures when altering tables in production Supabase databases."
---

# Zero-Downtime Database Migrations

Altering a table with millions of rows in Postgres can lock it, taking the entire SaaS offline. Agents must script migrations defensively.

## 1. Never RENAME Columns Directly
To rename or change a type:
1. Add the new column.
2. Backfill data in small batches.
3. Update the frontend/Reflex Python to read/write to the new column.
4. Drop the old column in a later migration.

## 2. CONCURRENTLY Index Creation
Always use `CREATE INDEX CONCURRENTLY`. Never use a standard index creation command on a large, live production table, as it locks writes.

## 3. Backwards Compatibility
Ensure the Python backend can gracefully handle the database state *while* the migration is rolling out. Never assume the database schema updates instantly across all distributed transactions.
