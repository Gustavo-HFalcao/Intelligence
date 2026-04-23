---
name: mcp-push-integrations
description: "Rules for autonomous agents to push their results (PDFs, daily briefings) out of the software via Slack, Email, or WhatsApp MCPs."
---

# MCP Push Integrations

Proactive agents generating Morning Briefings shouldn't just let the data sit inside Postgres.

## 1. Outbound Actions
When writing the final step of an autonomous agent task, instruct the agent to use an MCP connection (e.g. standard SMTP Python, a Slack webhook, or a dedicated MCP server) to dispatch the content directly to the user's pocket.

## 2. Formatting Payloads
Emails and Slack messages must be formatted properly (Markdown for Slack, simple HTML for emails). Provide a 2-sentence summary and a hyperlink to the full Supabase URL where the user can view the complete chart or dashboard context.
