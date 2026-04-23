---
name: python-performance-optimization
description: "Python and Reflex UI framework optimization to prevent blocking operations and reduce latency for real-time dashboards and async charts."
license: MIT
metadata:
  date: March 2026
---

# Python Performance Optimization for Real-Time Agents

When dealing with Voice inputs, Real-Time Charts, and LLM text streams, latency is critical. A delay of 3 seconds feels like an eternity for voice UI. 

## When to Apply
- When developing Reflex backend states.
- When an agent is streaming data back to the user.
- When analyzing large datasets before generating a chart.

## Core Rules

1. **Never Block the Async Event Loop**
   - Reflex relies on `asyncio`. Any synchronous I/O call (like `requests.get()` or a synchronous `psycopg2` query) blocks the entire server.
   - **Fix**: Use `httpx.AsyncClient` or `aiohttp` instead of `requests`. Use `asyncpg` or Supabase's async client for DB access.

2. **Stream AI Outputs (Generators)**
   - When an LLM generates a large summary or chart data, do not wait for the entire generation to finish before updating the UI.
   - Yield partial results from your Reflex state using Python generator functions `yield` so the frontend updates iteratively byte-by-byte.

3. **Data Caching for Dashboards**
   - For chart generation, avoid querying the raw `events` table every time if it hasn't changed.
   - Use `functools.lru_cache` or a Redis layer (or a materialized view in Postgres) for daily aggregate numbers.

4. **Efficient Data Processing**
   - If processing massive datasets downloaded from Firecrawl/Tavily, use `Polars` or `Pandas` heavily optimized vector operations instead of `for` loops in pure Python.
