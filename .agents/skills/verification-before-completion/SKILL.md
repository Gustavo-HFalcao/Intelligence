---
name: verification-before-completion
description: "Mandates that an AI Agent must actively verify its own work (run tests, check logs, ping endpoints) before declaring a task finished."
---

# Verification Before Completion

As autonomous agents, the definition of "Done" is not "I wrote the code". The definition of "Done" is "I proved the code works in the deployment environment".

## Core Principles
1. **Never Assume**: Just because the Python syntax is correct doesn't mean the Reflex UI rendered it correctly. 
2. **Compile & Run**: Always use terminal commands to trigger a fast compilation or type-check (e.g., `reflex init`, `python -m py_compile`, or running a quick test script).
3. **Check Side Effects**: If you changed a database schema, run a `SELECT` query via MCP to ensure the data is actually returned in the new format.
4. **Read Warnings**: If the build returns warnings (even if it doesn't crash), do not ignore them. Address them before moving on.
