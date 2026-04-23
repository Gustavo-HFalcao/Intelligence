---
name: dispatching-parallel-agents
description: "Best practices and system patterns for dispatching subagents in parallel via MCP to avoid latency bottlenecks and increase application responsiveness."
license: MIT
metadata:
  date: March 2026
---

# Dispatching Parallel Agents

When executing complex tasks—such as querying external data while simultaneously rendering a chart—agents must run in parallel rather than blocking each other in a synchronous thread.

## When to Apply
- When a user requests data that requires both data extraction (Supabase) and external insights (MCP Tools).
- When generating complex responses that take several seconds.

## Core Principles
1. **Identify Independent Workloads**: Always split operations that do not depend on each other (e.g., fetching rows from a DB vs summarization).
2. **Concurrent Tool Calling**: When your agent infrastructure supports multiple tool calls concurrently, issue them in a single generation loop.
3. **Promise/Future Patterns**: If coding backend orchestration in Python (Reflex), use `asyncio.gather()` to dispatch multiple AI calls to sub-agents.

## Examples
### Correct Approach
```python
# Launch sub-agents in parallel
async def generate_dashboard_data():
    results = await asyncio.gather(
        analyze_financial_data(user_id),
        create_visual_chart(user_id)
    )
    return results
```

### Incorrect Approach
```python
# Blocking, sync execution causes lag
data = await analyze_financial_data(user_id)
chart = await create_visual_chart(user_id)
```
