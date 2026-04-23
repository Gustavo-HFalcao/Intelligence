---
name: async-heavy-lifters
description: "Architecture rules for managing long-running AI generation without breaking Supabase RLS policies."
---

# Async Heavy Lifters (Secure Background Actions)

Heavy tasks (OpenAI generation) must not block the UI. However, security is paramount.

## 1. RLS is Non-Negotiable
When using Reflex `rx.background`, the background task loses the immediate browser WebSocket context. You MUST NOT bypass RLS by falling back to the `SERVICE_ROLE_KEY`.

## 2. Passing Auth State
Before dispatching the background task, capture the user's Supabase JWT access token from the active `rx.State` and pass it explicitly into the async thread. The thread must instantiate its own Supabase client using that specific token so that the Postgres Row Level Security policies remain intact.

## 3. UI Feedback
Update the state to `is_loading = True` before firing the thread, and `is_loading = False` when the thread completes.
