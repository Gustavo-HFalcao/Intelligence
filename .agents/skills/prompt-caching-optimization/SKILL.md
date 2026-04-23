---
name: prompt-caching-optimization
description: "Rules for structuring prompts to maximize Anthropic/OpenAI prompt caching, destroying input token costs."
---

# Prompt Caching Optimization

Passing massive Database Schemas or company context in every single voice prompt will burn through the GPT/Claude budget instantly.

## 1. Static vs Dynamic Prompt Segments
Always place static, unchanging context (e.g. the entire 500-line Postgres schema DDL) at the VERY TOP of the System Prompt.

## 2. Utilizing Provider Caching
Both Anthropic (Claude) and OpenAI support native Prompt Caching for the top sections of the prompt. If the start of your prompt does not change across 50 voice requests, you will pay 90% less for those tokens.

## 3. Variable Data Placement
Place the dynamic data (the transcribed user audio, the current dashboard state) at the VERY END of the prompt. Mixing dynamic text into the middle of the schema documentation ruins the cache hit rate.
