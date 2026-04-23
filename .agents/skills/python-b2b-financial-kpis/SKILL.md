---
name: python-b2b-financial-kpis
description: "Trains the agent to think like a CFO. Requirs financial metrics (EBITDA, Markup, Burn Rate) instead of basic sums when generating charts."
---

# Python B2B Financial KPIs (Inteligência Financeira)

When the user requests a "dashboard", "chart", or "financial summary", the agent must elevate the business value of the data. 

## 1. Reject Shallow Metrics
Do not just plot "Total Income vs Total Expense". B2B decision-makers need derived metrics. 

## 2. Standard Calculations
Always consider implementing (where data allows):
- **EBITDA**: Earnings Before Interest, Taxes, Depreciation, and Amortization.
- **Burn Rate**: How fast the company is spending its cash reserves.
- **Ticket Médio (Average Order Value)**: Total revenue divided by number of receipts/clients.
- **CAC (Customer Acquisition Cost)**: Total marketing/sales spend over new clients.

## 3. Python Implementation
Use `Pandas` or `Polars` to pivot and aggregate these standard KPIs in backend memory before passing them to the Reflex frontend `rx.recharts` components. Do not force the database to do complex window functions if Python can do it cleanly in-memory for the dashboard.
