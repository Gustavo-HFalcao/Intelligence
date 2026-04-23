---
name: context-management
description: "Trains the agent to act like a laser rather than reading entire directories, preventing context window bloat."
---

# Context Management (Laser Execution)

An agent's context window is precious. Filling it with 10 files of irrelevant code degrades logic, reasoning, and burns tokens rapidly.

## 1. Do Not Read Unnecessary Files
If the task is to fix the color of a button, do NOT read `database_schema.py` or the entire `app.py`. Find the exact component using a specific text search (`grep`) and open ONLY that file.

## 2. Read Chunks via Lines
If you open a file with 1,500 lines of code, do not load the whole file into the chat context if you only need a single function. Read lines by specific ranges (e.g. line 200 to 250) whenever possible.

## 3. Stop Hallucinating Paths
Use `ls` or `tree` functionality to explicitly check if a file exists before trying to read it. Guessing paths burns tokens on failed tool executions.
