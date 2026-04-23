---
name: feature-flag-architecture
description: "Guidelines for implementing dynamic toggles and configurable features without hardcoding if/else logic."
---

# Feature Flag Architecture

For a B2B SaaS (like Fuel Reimbursements), different tenants/companies need different UI configurations. Do not hardcode logic paths if a feature is custom per tenant.

## 1. Database Configuration Layer
Create a `tenant_config` or `feature_flags` JSONB column/table in Supabase. Store boolean values for features like `requires_gps`, `auto_approve_under_50`.

## 2. Dynamic UI Rendering
In the Reflex frontend, the Python State should read this configuration during the `on_load` or parent hydration event. The UI components must render conditionally based on the `rx.cond()` macro reading from the State, rather than evaluating logic locally inside the functional component.

## 3. Graceful Degradation
If the feature flag service/query fails, always fallback to the most secure/restrictive state (e.g., fallback to `False` for auto-approval).
