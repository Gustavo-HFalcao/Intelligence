---
name: reflex-auth-state-sync
description: "Handles syncing Supabase JWT session cookies seamlessly with the Python-backed Reflex WebSocket."
---

# Reflex & Supabase Authentication Sync

In Reflex, Python state lives on the server and communicates via WebSockets. Supabase Auth lives primarily on the client (browser cookies/localStorage). 

## 1. Secure Token Harvesting
Ensure the user's Supabase JWT `access_token` is captured safely on the front-end (via `rx.cookie` or LocalStorage) and strictly dehydrated into the `rx.State`.

## 2. Authenticated RLS Queries
Every time the Python backend performs an action, it must instantiate the Supabase client using that specific user's `access_token` bound to the state, ensuring that Postgres RLS policies natively block unauthorized data access.

## 3. Session Expiration
Listen for token expiration events. If the token is invalid, trigger an `rx.redirect` to the `/login` page immediately. Do not hide failures behind a generic "Server Error".
