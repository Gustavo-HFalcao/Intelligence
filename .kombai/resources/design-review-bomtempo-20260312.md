# Design Review Results: BOMTEMPO Dashboard — All Routes

**Review Date**: 2026-03-12
**Routes Reviewed**: / · /financeiro · /obras · /projetos · /om · /analytics · /previsoes · /chat-ia · /rdo-form · /rdo-dashboard · /reembolso · /reembolso-dash · /relatorios · /alertas · /logs-auditoria
**Focus Areas**: Visual Design · UX/Usability · Responsive/Mobile · Consistency · Performance

---

## Summary

The BOMTEMPO Dashboard has a strong, distinctive "Deep Tectonic" visual identity with well-crafted glassmorphism, copper/patina accents and good typography hierarchy. However, there are meaningful inconsistencies in page-level layout patterns, critical sidebar navigation gaps that make some routes unreachable, and a very heavy ambient glow border that dominates the visual experience on all pages. Mobile experience is functional but incomplete due to hidden navigation.

---

## Issues

| # | Issue | Criticality | Category | Location |
|---|-------|-------------|----------|----------|
| 1 | **Sidebar missing navigation entries** — Alertas, Logs & Auditoria, Previsões and Analytics routes are **not listed in the sidebar**, making them unreachable without knowing the direct URL. The sidebar only shows 10 of 14 routes. | 🔴 Critical | UX/Usability | `bomtempo/components/sidebar.py` |
| 2 | **Session lost on admin routes** — Navigating to `/reembolso-dash` and `/admin/editar_dados` redirects to login even when already authenticated. Guard logic likely checks roles strictly, but the redirect gives no feedback to the user (silent fail). | 🔴 Critical | UX/Usability | `bomtempo/state/global_state.py` — `guard_*` event handlers |
| 3 | **RDO Dashboard never finishes loading** — `/rdo-dashboard` shows "Sincronizando dados..." spinner indefinitely. The page never renders content within 10+ seconds, suggesting a failed or very slow async call with no timeout/error fallback UI. | 🔴 Critical | Performance / UX | `bomtempo/pages/rdo_dashboard.py` · `bomtempo/state/rdo_dashboard_state.py` |
| 4 | **Copper ambient border glow is overwhelming** — A full-height, very bright orange-copper border glow is rendered around the entire viewport on every page (visible as a wide glowing bar on the right and top edges). Intended as atmosphere, it currently saturates the visual field and reduces content legibility at a glance. The effect should be much more subtle (reduce `opacity` and `spread`). | 🟠 High | Visual Design | `assets/style.css` — `.fab-chat`, `fabGlow` · `bomtempo/layouts/default.py` — outer wrapper style |
| 5 | **Inconsistent page header patterns** — Dashboard and Previsões have rich hero banners (gradient background, badge, large icon, description). Financeiro, Obras, Projetos, O&M, Analytics, Relatorios, Alertas, Logs use plain text `H2` titles with no banner. This inconsistency breaks visual rhythm when navigating. Either all pages should have a hero header, or none should. | 🟠 High | Consistency | `bomtempo/pages/index.py:1-60` vs `bomtempo/pages/financeiro.py:1-30`, `bomtempo/pages/om.py:1-30` |
| 6 | **O&M chart Y-axis labels clipped** — On the "Performance de Geração" chart, the left Y-axis numeric labels (`155000`, `270000`, `385000`, etc.) are partially cut off because the chart container has no left padding/margin to accommodate the axis labels. Only the last digits are visible. | 🟠 High | Visual Design | `bomtempo/pages/om.py` — `performance_chart()` function · Recharts `<YAxis>` `width` prop likely too small |
| 7 | **Financeiro — "Status de Medição Global" chart renders blank** — The left chart card is empty (white/blank area with only the legend). The `rx.recharts` component appears to not receive data or fails to render the donut/pie chart silently. | 🟠 High | Visual Design / Performance | `bomtempo/pages/financeiro.py` — `status_medicao_chart()` |
| 8 | **Mobile: No accessible navigation drawer** — On mobile (≤640px), the hamburger menu icon (`≡`) is visible at top-left, but tapping it does not open a drawer/overlay showing all sidebar navigation items. Users on mobile have no way to navigate between pages. | 🟠 High | Responsive/Mobile | `bomtempo/components/sidebar.py` — mobile drawer logic · `assets/style.css` mobile breakpoints |
| 9 | **Mobile: Prominent orange scrollbar dominates viewport** — The custom WebKit scrollbar (6px wide, copper-colored) renders as an extremely bright, nearly full-height orange bar on the right edge on mobile viewports. The visual weight at mobile size makes it look like a colored border rather than a scrollbar indicator. | 🟠 High | Responsive/Mobile | `assets/style.css:187-204` — `::-webkit-scrollbar-thumb` |
| 10 | **Reembolso form has no sidebar layout** — `/reembolso` renders as a completely standalone page without the sidebar, header, or any shared layout. This breaks the product shell consistency and makes users feel they have "left" the app. | 🟠 High | Consistency | `bomtempo/pages/reembolso_form.py` — wraps `reembolso_form_page()` directly, not via `default_layout()` · `bomtempo/bomtempo.py:161-165` |
| 11 | **RDO Stepper labels truncated** — In the 5-step RDO form wizard, the step labels read "Cabeçalho", "Mão de O...", "Equipam...", "Atividades", "Materiais". The middle three labels are truncated with ellipsis because the stepper container does not provide enough horizontal space for the full text. This is especially problematic for new users learning the flow. | 🟡 Medium | UX/Usability | `bomtempo/pages/rdo_form.py` — stepper component, step label `font-size` / `white-space` |
| 12 | **Obras and Projetos: large empty space with only 3 cards** — Both pages render 3 project cards in a `3-column grid` that leaves the entire lower half of the page blank. When there are few records, the page looks unfinished. An empty state or summary panel should fill the space. | 🟡 Medium | UX/Usability / Visual Design | `bomtempo/pages/obras.py` · `bomtempo/pages/projetos.py` |
| 13 | **Sidebar tagline animation is distracting** — The animated typing cursor (`Transformando dados em resultados.▍`) in the sidebar cycles and blinks continuously throughout the session. While charming on first load, it remains active indefinitely and draws the eye away from content during work. Should stop after the initial animation completes. | 🟡 Medium | UX/Usability / Visual Design | `bomtempo/components/sidebar.py` — tagline component with cursor animation |
| 14 | **Logs & Auditoria: category filter chips overflow into two rows** — The category chip strip has 14 chips that wrap onto two lines, creating an uneven layout. The filter area should use a horizontally-scrollable single row (with `overflow-x: auto; white-space: nowrap`) or a compact dropdown grouping for secondary categories. | 🟡 Medium | Visual Design / UX | `bomtempo/pages/logs_auditoria.py` — category chips container |
| 15 | **Large initial bundle size (3.6 MB)** — The page load transfers 3.6 MB of assets on the first visit. This significantly impacts Time to Interactive (FCP 1.6s on localhost — much worse on real networks). Code-splitting, lazy-loading chart libraries (Recharts), and tree-shaking unused components should be evaluated. | 🟡 Medium | Performance | `bomtempo/bomtempo.py` — all pages imported at top level; no dynamic imports |
| 16 | **Card background color inconsistency** — KPI cards on the Dashboard use `var(--bg-glass)` / `rgba(14,26,23,0.7)`, while Previsões cards use the hardcoded `#0D2A23` and Financeiro cards appear darker. The glass effect differs between pages because some use `class_name="glass-panel"` and others use inline `bg="#0D2A23"`. | 🟡 Medium | Consistency | `bomtempo/pages/previsoes.py:113` · `bomtempo/pages/financeiro.py` — KPI card bg |
| 17 | **Deprecated Reflex APIs in use** — Compilation logs show `rx.Base` (deprecated, use `rx.Model`) and `state_auto_setters` warnings. These are not visual issues yet but will cause breakage in future Reflex upgrades and already produce console noise. | 🟡 Medium | Performance / Code Quality | `bomtempo/state/global_state.py` · multiple state files |
| 18 | **Chat IA — large empty vertical area** — The chat interface has a large empty white space area between the AI welcome message and the suggestion chips at the bottom. On first load with no messages, the conversation area is mostly black void. A subtle visual indicator (e.g., "Ask me anything about your projects…" watermark or light illustration) would improve perceived quality. | ⚪ Low | Visual Design / UX | `bomtempo/pages/chat_ia.py` — chat messages container empty state |
| 19 | **No breadcrumb or secondary navigation** — Pages with sub-sections (RDO has form + historico + dashboard; Reembolso has Nova Solicitação + Meus Reembolsos + E-mails) use tab patterns locally, but there is no global breadcrumb showing where the user is within the app hierarchy. Deep links feel disconnected. | ⚪ Low | UX/Usability | `bomtempo/layouts/default.py` — no breadcrumb component |
| 20 | **`project-card` CSS class defined twice** — `.project-card` is defined twice in `style.css` (lines ~418 and ~577). The second definition overrides the first's `transition` property. This is dead/duplicate code that can cause confusion during maintenance. | ⚪ Low | Consistency / Code Quality | `assets/style.css:418-446` and `assets/style.css:577-605` |
| 21 | **RDO Dashboard redirect after load fails silently** — When `/rdo-dashboard` fails to load data, the page remains in a spinner state forever with no error message, retry button, or redirect. Users are left with no feedback about what happened or what to do. | ⚪ Low | UX/Usability | `bomtempo/pages/rdo_dashboard.py` — loading state has no timeout/error branch |
| 22 | **Analytics & Benchmarking — radar chart left axis label clipped** — The "Rentabilidade" axis label is cropped on the left edge of the radar chart because the container has `overflow: hidden` and the chart's left margin is insufficient. | ⚪ Low | Visual Design | `bomtempo/pages/analytics.py` — radar chart component |

---

## Criticality Legend

- 🔴 **Critical** — Breaks core functionality or makes pages unreachable
- 🟠 **High** — Significantly impacts UX, visual coherence or mobile access
- 🟡 **Medium** — Noticeable issue that degrades quality; should be addressed soon
- ⚪ **Low** — Polish / nice-to-have improvement

---

## Positive Highlights

- ✅ **Excellent visual identity** — Deep Tectonic theme with copper/patina palette is cohesive and distinctive
- ✅ **Glass panel system** — `.glass-panel`, `.kpi-card`, `.project-card` CSS classes are well-structured and reused consistently
- ✅ **RDO multi-step wizard** — Excellent UX pattern; stepper is clear and progressive
- ✅ **Alertas page** — Clean two-column layout (Cronológicos / Reativos) with clear card hierarchy
- ✅ **Relatorios page** — Best-in-class page design; three modes (Dossier, IA, Custom) are clearly differentiated
- ✅ **Microinteractions** — Button press scale, card hover lift, FAB glow pulse are all polished
- ✅ **"EM CONSTRUÇÃO" banners** — Honest and clear about mock data; great for stakeholder demos
- ✅ **Zero console errors** — No JavaScript errors detected across all pages reviewed
- ✅ **Scrollbar theming** — Custom copper scrollbar is a nice touch on desktop; just needs mobile tuning

---

## Recommended Priority Order

1. 🔴 Fix sidebar to include all 14 routes (Issue #1)
2. 🔴 Fix RDO Dashboard loading / add error state (Issue #3)
3. 🔴 Add user-facing feedback when auth guard redirects (Issue #2)
4. 🟠 Reduce ambient glow border intensity (Issue #4)
5. 🟠 Add mobile navigation drawer (Issue #8)
6. 🟠 Wrap Reembolso in default_layout (Issue #10)
7. 🟠 Fix O&M chart Y-axis clipping (Issue #6) and Financeiro chart blank (Issue #7)
8. 🟠 Standardize page header pattern across all pages (Issue #5)
9. 🟡 Fix stepper label truncation in RDO form (Issue #11)
10. 🟡 Add empty/summary state to Obras and Projetos (Issue #12)
