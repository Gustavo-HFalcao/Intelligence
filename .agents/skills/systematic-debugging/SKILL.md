---
name: systematic-debugging
description: "Framework for strict, systematic debugging. Prevents the AI from guessing solutions or entering a repetitive failure loop."
---

# Systematic Debugging for AI Agents

Agents often fall into the trap of "guessing" a fix, applying it, and hoping the error goes away. This rule enforces a strict debugging methodology.

## Rules of Engagement
1. **Never Guess**: Do not change a line of code until you have absolute proof of why it's failing.
2. **Gather Evidence**: If a component fails to render or an API returns 500, inject `print()` or `console.log()` statements to inspect the payload, or run a test script. Read the terminal output.
3. **Formulate a Hypothesis**: State your hypothesis clearly (e.g. "The error occurs because `user_id` is passed as a string instead of an int").
4. **Locate the True Source**: Often, the error is thrown in a component, but the bad data was generated in a parent state or database query. Trace it back.
5. **Fix & Verify**: Apply the exact fix. Never rewrite the entire file to fix a single line bug.
