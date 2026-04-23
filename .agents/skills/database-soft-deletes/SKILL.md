---
name: database-soft-deletes
description: "Financial systems require extreme audit capabilities. Never use DELETE FROM."
---

# Soft Deletes (Audit Compliance)

In a B2B financial or reimbursement SaaS, destroying a record completely ruins accounting compliance and audit trails.

## 1. The Golden Rule
Agents are strictly prohibited from writing or executing `DELETE FROM table_name` SQL queries or REST calls against any domain-level data.

## 2. Implementing Soft Deletes
All tables must contain a `deleted_at TIMESTAMPTZ` column.
To "delete" a record, execute `UPDATE table_name SET deleted_at = NOW()`.

## 3. Querying Active Data
All subsequent `SELECT` statements must append `WHERE deleted_at IS NULL` to ensure users don't see deleted records in their active UI grids.
