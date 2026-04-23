---
name: proactive-agent
description: "Patterns for setting up proactive, autonomous agents that perform scheduled data aggregation, routine notifications, and autonomous tasks without immediate direct user prompts."
license: MIT
metadata:
  date: March 2026
---

# Proactive Agents

Most AI integrations are reactive (waiting for a prompt). Proactive agents run in the background, analyzing state, and initiating actions (like daily morning briefings).

## When to Apply
- Sending automated "Morning Briefings" via TTS or email.
- Monitoring databases to detect anomalies (e.g., a fuel spike) and proactively warning the user.
- Pre-computing slow analytical queries before the user opens the dashboard.

## Implementation Guidelines
1. **Background Jobs / Cron**: Use Python `Celery`, `apscheduler`, or Supabase Cron to trigger the proactive agent.
2. **Context Assembly**: When triggered, the agent must fetch the last 24h of data (logs, receipts, external news) before generating output.
3. **Delivery Mechanism**: Push the results to a structured location (e.g., `morning_briefings` table) so the UI can notify the user upon login, or push directly via Discord/Slack/Email.

## Rules of Proactivity
- **Don't Spam**: Only alert the user if the synthesized data reaches a minimum "importance" threshold.
- **Actionable Output**: A proactive agent should not just give data, it should propose actions (e.g., "Approve these 3 pending reimbursements").
