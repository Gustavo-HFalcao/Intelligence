---
name: premium-ui-design
description: "Mandatory design rules enforcing 'WOW Factor' premium UI in Reflex, integrating UI/UX Pro Max intelligence without causing Python code spaghetti."
---

# Premium UI Design (Reflex Architecture + UI/UX Pro Max)

You absolutely can and must create a beautiful, dynamic "WOW Factor" UI in Reflex, but you must do it securely and stably by merging high-end Design Intelligence with Reflex's strictly bounded Python component structure.

## 1. Leverage rx.theme() and Radix UI (Style Strategy)
Reflex uses Radix UI under the hood. To achieve Glassmorphism and dark mode, configure the app's root `rx.theme(appearance="dark", accent_color="indigo", radius="large")`. Rely on `rx.color()` and standard Radix variable spacing rather than injecting raw hex codes or margin hacks.

## 2. UI/UX Pro Max: Layout & Typography
- **Hierarchy:** Always establish clear visual hierarchy. H1 should be dramatic, H2/H3 should guide the eye. Use muted secondary colors (e.g., `gray.11` in Radix) for subtitles so the data pops.
- **Grids & Spacing:** Avoid cramped UI. B2B Dashboards need breathing room. Use Reflex's `rx.grid()` and `rx.flex()` with generous, consistent `spacing` props (e.g., `spacing="4"` or `spacing="6"`).

## 3. UI/UX Pro Max: Charts, Data, and Feedback
- **Data Visualization:** Charts must be legible and minimal. Hide unnecessary grid lines. If charting revenue, ensure tooltips and hover states are immediately visible.
- **Form Feedback:** Never leave a user guessing. If an action fails (e.g., a voice transcript fails), use `rx.toast()` or inline alerts with semantic colors (Red/Ruby for error, Amber for warning, Iris/Green for success).

## 4. Component Abstraction
If a card requires complex styling (e.g., `backdrop_filter="blur(10px)"`, complex box shadows, floating layouts), DO NOT repeat these 10 lines of Python `style={...}` dicts inside the main page renderer. You MUST abstract it into a pure Python function `def glass_card(*children):` in a `components/` folder. This keeps the backend code maintainable.

## 5. Subtlety over Complexity
If a micro-animation is requested, use Reflex's native `transition` and `_hover` props. Do not wrap custom raw React/Framer-Motion components unless authorized. Subtle scale updates on hover and smooth opacity fades are enough for a premium feel.
