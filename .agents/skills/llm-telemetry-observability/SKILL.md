---
name: llm-telemetry-observability
description: "Guidelines for mandatory instrumentation and tracking of all LLM requests, token usage, and latency."
---

# LLM Telemetry & Observability

AI agents interacting with OpenAI/Anthropic models cost money. Latency and token usage must be tracked in production.

## 1. Mandatory Logging
Whenever a backend Python route (Reflex) or Python worker makes an LLM API call, you must wrap it in a timing metric. Once the LLM call completes, calculate the latency and token count.

## 2. Database Insertion
Insert the structured telemetry payload (`tokens_input`, `tokens_output`, `latency_ms`, `model`, `feature_name`) into the `llm_observability` Supabase table. Do NOT omit this step when building a new AI feature.

## 3. Graceful Fallbacks
If the observability logging fails, do not crash the user's primary AI flow. Trap the error and move on.
