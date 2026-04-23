---
name: plan-before-code
description: "Forces the agent to outline a step-by-step plan for complex features before altering any code, preventing cascading failures."
---

# Plan Before Code

When receiving a complex prompt, Agents often rush to edit files immediately. This behavior is prohibited for feature-level development.

## 1. Always Think First
Before running file-editing tools, output a concise Markdown checklist of what needs to be done. 

## 2. Validate The Architecture
If the feature spans multiple layers (e.g. adding a new table, writing the Python state, and creating the UI component), explicitly ask the user: "Does this step-by-step approach look correct to run?"

## 3. Atomic Updates
Check off items in your plan one by one. Do not attempt to accomplish the entirety of the plan in a single massive code edit.
