---
name: token-management
description: "Centralized rules for eliminating context bloat, saving API costs, and preventing LLM rule fatigue."
---

# Token & Context Management

Model stability requires strict token sizing and explicit focus. 

## 1. Diff-Style Generation
Never output an entire 500-line file back to the console or chat when only 2 lines changed. Output only the targeted function or use standard diff formats.

## 2. Prompt Caching Structure
Always place static schema data at the absolute TOP of prompts to leverage OpenAI/Anthropic Prompt Caching. Dynamic data (user audio text) goes at the BOTTOM.

## 3. Strict Context Isolation
Do not open or read `app.py` or unrelated files if the bug is explicitly inside `components/button.py`. Use grep to find the exact line numbers and read only what is necessary.
