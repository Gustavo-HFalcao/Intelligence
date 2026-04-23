---
name: reflex-e2e-testing
description: "Standards for verifying Reflex Python logic and React component rendering without manual checks."
---

# End-to-End Testing in Reflex

Wait, Reflex is not just Python. It translates to a React frontend. A `pytest` alone does not prove the website works.

## 1. State Unit Tests
Use standard Python `pytest` to instantiate your `rx.State` class, call its events, and verify that the mutable variables updated correctly.

## 2. Playwright / Browser Verification
Before marking a UI ticket complete, use playwright or a browser automation agent tool to physically navigate to `localhost:3000` and verify the CSS, text presence, and clickability of the buttons. Trusting just the Python syntax is forbidden.
