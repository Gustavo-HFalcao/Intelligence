---
name: automated-documentation-writer
description: "Ensures no legacy code is left behind. Instructs AI to document its own modules and tables via docstrings and README updates."
---

# Automated Documentation Writer

AI agents write code 10x faster than humans, which means technical debt accumulates 10x faster if left undocumented.

## 1. Docstrings are Mandatory
Any complex function or class generated for the backend (especially Reflex states, async tasks, or Data extractors) must include a PEP-257 compliant docstring explaining the "Why" and the expected `args`/`returns`.

## 2. Table Schemas
When migrating a new Supabase table, use Postgres `COMMENT ON TABLE` and `COMMENT ON COLUMN` commands. This allows downstream MCP tools and future agents to understand what `receipts.amount` actually means without guessing.

## 3. High-Level Architecture
If you implement a brand new feature (e.g. "Voice Processing Pipeline"), update the root `README.md` or the `docs/` folder. State clearly how the new module hooks into the existing system.
