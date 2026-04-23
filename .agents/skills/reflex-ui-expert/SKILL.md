---
name: reflex-ui-expert
description: "Specific guidelines for AI Agents generating code for the Reflex framework (Python to React UI)."
---

# Reflex Framework Expert Guidelines

Reflex translates Python code into a React frontend. To write maintainable and robust code, follow these strict rules:

## 1. State Management (`rx.State`)
- **Immutability vs Mutation**: Standard Python objects inside `rx.State` should be updated by re-assigning them, so Reflex can detect the change and trigger a render. Avoid deeply mutating dicts directly without re-assigning the reference.
- **Computed Vars (`@rx.var`)**: Use `rx.var` for properties that depend on other state variables. Do not store redundant data in the state. They should be lightweight, as they recalculate frequently.

## 2. Event Handlers
- **Async Execution**: Any event handler that talks to Supabase or an external API MUST be `async`. Reflex handles `async def` handlers perfectly and allows other UI interactions while waiting.
- **Yielding Updates**: For long-running Agent tasks (like streaming an LLM response), use `yield` inside the event handler to update the frontend progressively. Example: `yield ReflexState.update(...)`.

## 3. Component Architecture
- **Keep Components Pure**: UI Components (functions returning `rx.Component`) should never contain business logic, database queries, or state mutation. They just map State variables to UI parameters.
- **Styling**: Prefer Reflex native style props (e.g. `padding="1em"`, `color="var(--accent-9)"`) over raw CSS. Wait for exact UI library implementations if available in the project.
