---
name: postgresql-table-design
description: "Schema and data modeling practices for storing diverse, unstructured inputs, audit logs, and analytics metrics efficiently in Postgres."
license: MIT
metadata:
  date: March 2026
---

# PostgreSQL Table Design for AI Applications

AI applications, specifically voice-based data entry and investigation dashboards, require schemas that are flexible enough to handle unstructured data while maintaining strict typing for real-time analytics.

## When to Apply
- When designing tables to store AI-generated summaries, chat logs, or voice transcripts.
- When modeling domain tables (e.g. Fuel Reimbursments) that an agent needs to query quickly.

## Rule Categories

### 1. Handling Unstructured Intelligence
- **Rule**: Use `JSONB` for raw AI output, but promote indexable fields to real columns.
- **Why**: An agent might extract 20 different attributes from a voice receipt. Put the exact receipt details in a `metadata JSONB` column, but ensure `total_amount_cents` (Integer) and `date` (Timestamp) are real Postgres columns so your charts don't suffer performance drops querying JSON.

### 2. Audit Trails & Soft Deletes
- **Rule**: Agents make mistakes. Never `DELETE` rows via an agent. Use `deleted_at TIMESTAMP` or an `audit_logs` table.
- **Why**: If a voice command says "Remove all receipts from yesterday", you must have a way for the user to rollback this destructive AI action via soft deletes.

### 3. Timestamp Data Types
- **Rule**: ALWAYS use `TIMESTAMPTZ` (timestamp with time zone). Do not use `TIMESTAMP` (without time zone).
- **Why**: AI agents and the UI operate across time zones. Failing to capture exactly when an event occurred breaks time-series charts.
