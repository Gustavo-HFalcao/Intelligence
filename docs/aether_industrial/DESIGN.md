# Design System Strategy: Industrial Intelligence & Tonal Depth

## 1. Overview & Creative North Star: "The Digital Foreman"
This design system moves beyond the "SaaS Template" look to embrace **Industrial Tech Realism**. The Creative North Star is **"The Digital Foreman"**—an interface that feels like a high-end, ruggedized head-up display (HUD) found in advanced construction machinery. 

We break the standard grid through **intentional asymmetry** and **high-contrast data layering**. By mixing the mechanical precision of `JetBrains Mono` with the futuristic, angular geometry of `Rajdhani`, we create a workspace that feels authoritative, premium, and purpose-built for high-stakes project management. This is not a social app; it is a command center.

---

## 2. Colors: Void, Copper, and Patina
The palette is rooted in construction materials: weathered copper, oxidized patina, and deep obsidian shadows.

### Core Palette
- **BG_VOID (Primary Background):** `#030504` – The absolute foundation. Use for the lowest architectural layer.
- **BG_DEPTH (Secondary):** `#081210` – Used for sidebar navigation and secondary layout containers.
- **BG_SURFACE (Tertiary):** `#0e1a17` – The primary card surface color.
- **COPPER (Accent):** `#C98B2A` – High-energy focal points, CTAs, and active states. 
- **PATINA (Success/Progress):** `#2A9D8F` – For positive growth, milestones, and completed phases.

### The "No-Line" & "Ghost Border" Rules
*   **The No-Line Rule:** Traditional 1px solid borders for sectioning are strictly prohibited. Boundaries must be defined by background shifts (e.g., a `surface-container-low` card nested within a `surface` section). 
*   **The Ghost Border Fallback:** If a border is required for extreme contrast or accessibility, use a **Ghost Border**: `rgba(255, 255, 255, 0.08)` at 1px. Never use 100% opaque borders.

### The Glass & Gradient Rule
Floating elements (Modals, Tooltips, Popovers) must utilize **Glassmorphism**.
- **Surface:** `rgba(14, 26, 23, 0.6)`
- **Blur:** `backdrop-filter: blur(12px)`
- **Gradient:** Main CTAs should use a subtle linear gradient from `COPPER (#C98B2A)` to `primary-container (#c98b2a)` at a 135-degree angle to simulate the metallic sheen of industrial hardware.

---

## 3. Typography: The Triple-Threat Scale
We use three distinct typefaces to categorize information types instantly.

| Level | Typeface | Token | Usage |
| :--- | :--- | :--- | :--- |
| **Display** | Rajdhani | `display-lg` | Hero KPIs and Project Names. All-caps for impact. |
| **Headline** | Rajdhani | `headline-md` | Section headers and Dashboard Widget titles. |
| **Body** | Outfit | `body-md` | Descriptions, updates, and general UI text. |
| **Data** | JetBrains Mono | `label-md` | Coordinates, timestamps, budget figures, and telemetry. |

**Editorial Note:** Use `Rajdhani` with a slightly increased letter-spacing (`0.05em`) for headlines to enhance the "tech-blueprint" aesthetic.

---

## 4. Elevation & Depth: Tonal Layering
In this system, depth is a physical property of the "glass" sheets rather than a lighting effect.

*   **The Layering Principle:** Stack surfaces from darkest to lightest. 
    1.  Base: `BG_VOID`
    2.  Container: `surface-container-low`
    3.  Element: `surface-container-highest`
*   **Ambient Shadows:** For floating elements, use a "Patina Tinted Shadow": `0 20px 40px rgba(0, 0, 0, 0.4), 0 0 10px rgba(42, 157, 143, 0.05)`. This creates a subtle glow that feels like a powered-on screen.
*   **Hover States:** When hovering over a card, the `Ghost Border` should transition from `0.08` opacity to `COPPER (#C98B2A)` at `0.4` opacity. This "lights up" the component.

---

## 5. Components: Precision Machined

### Buttons (Industrial Grade)
- **Primary:** `COPPER` background, `on-primary` (dark) text. Rectangular with `DEFAULT (0.25rem)` corners. No rounded pills.
- **Secondary:** Transparent background, `Ghost Border`, `COPPER` text.
- **State Transition:** On hover, the background color shifts to `#E0A63B` with a subtle `box-shadow: 0 0 15px rgba(201, 139, 42, 0.3)`.

### Input Fields
- **Background:** `surface-container-lowest (#06100e)`.
- **Active State:** A bottom-only border of `COPPER` (2px).
- **Labels:** Always use `Rajdhani` in `label-sm` for field labels to maintain the technical HUD look.

### Cards & Data Lists
- **Rule:** Forbid divider lines. Use vertical spacing (`spacing-6`) or a background shift to `surface-variant` to separate list items.
- **Industrial KPIs:** Large `Rajdhani` numbers paired with small `JetBrains Mono` percentage changes.

### Custom Component: The "Telemetry Bar"
A thin, horizontal progress bar using `PATINA` for the fill and `BG_VOID` for the track. Used for site completion or heavy machinery uptime.

---

## 6. Do’s and Don'ts

### Do:
- **Do** use `JetBrains Mono` for all numerical data. It reinforces the "Intelligence Dashboard" precision.
- **Do** allow elements to overlap slightly (e.g., an icon breaking the boundary of a card) to create a bespoke, non-template feel.
- **Do** use `Lucide React` icons at a `1.5px` stroke width for a light, technical appearance.

### Don’t:
- **Don’t** use pure white (`#FFFFFF`). Use `on-surface (#dae5e1)` for text to prevent eye strain in dark environments.
- **Don’t** use standard blue/gray palettes. Every color must feel like it belongs on a construction site (Steel, Copper, Earth, Patina).
- **Don’t** use large border-radii. Keep it "industrial" with `sm (0.125rem)` or `md (0.375rem)`. Avoid the "bubbly" look.
- **Don’t** use drop shadows on nested cards; use color-stepping (tonal shifts) instead.