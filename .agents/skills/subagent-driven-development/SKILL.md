---
name: subagent-driven-development
description: "Methodology for orchestrating a main 'Orchestrator' agent that delegates sub-tasks to specialized subagents instead of doing monolithic execution."
license: MIT
metadata:
  date: March 2026
---

# Subagent Driven Development (SDD)

SDD is the practice of breaking down high-level user goals into smaller, specialized subagent tasks. This leads to far more predictable and testable AI behavior.

## When to Apply
- When processing voice inputs where the user asks for multiple distinct actions (e.g., "Log these 5 fuel receipts and then show me the weekly cost chart").
- When a task requires multiple distinct personas (e.g., Data Engineer vs Data Analyst).

## The Orchestrator Pattern
1. **The Orchestrator**: The primary agent that receives the prompt. Its only job is to understand intent, split the prompt, and determine which subagents to invoke.
2. **The Worker**: Subagents with highly specialized prompts (e.g., "Parse unstructured text into JSON").

## Best Practices
- **Define clear interfaces**: Ensure the Orchestrator knows exactly what JSON format the Worker will return.
- **Fail Gracefully**: If a subagent fails, the Orchestrator should know how to retry or report partial success to the user.
- **Limit Context Windows**: Only send the relevant chunk of the context to the subagent to save tokens and improve accuracy.
