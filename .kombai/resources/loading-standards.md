# BOMTEMPO Loading Standards

## Enterprise Loading Model

Use `page_centered_loader` from `bomtempo/components/skeletons.py` for ALL page/section loading states.
Never use `rx.spinner()` alone, `table_skeleton`, or `page_loading_skeleton` as the primary loader.

### Import
```python
from bomtempo.components.skeletons import page_centered_loader
```

### Signature
```python
def page_centered_loader(
    title: str = "CARREGANDO DADOS",
    subtitle: str = "Conectando ao banco de dados operacional…",
    icon: str = "database",
    **props,          # passed directly to outer rx.box for layout overrides
) -> rx.Component:
```

### Visual Design (matches image "CARREGANDO ALERTAS")
- Dark `BG_DEPTH` background with 40px copper grid overlay (opacity 4%)
- Rotating radar sweep animation (conic-gradient, copper)
- Concentric copper rings (44px / 80px / 116px / 140px)
- Icon centered in innermost ring with glow effect
- BOLD UPPERCASE title (Rajdhani, 700)
- Muted subtitle below

### Page-Specific Presets

| Page            | title                    | subtitle                                              | icon          |
|-----------------|--------------------------|-------------------------------------------------------|---------------|
| Obras (to list) | `"CARREGANDO OBRA"`      | `"Buscando dados operacionais e análise de risco"`    | `"hard-hat"`  |
| Obras (back)    | `"RETORNANDO"`           | `"Voltando para lista de obras"`                      | `"arrow-left"`|
| Alertas         | `"CARREGANDO ALERTAS"`   | `"Verificando subscrições e histórico de disparos..."` | `"bell"`     |
| Logs            | `"CARREGANDO LOGS"`      | `"Verificando registros e eventos de auditoria..."`   | `"shield-check"` |
| Usuários        | `"CARREGANDO USUÁRIOS"`  | `"Sincronizando perfis e permissões..."`              | `"users"`     |
| Reembolso       | `"CARREGANDO REEMBOLSOS"`| `"Verificando solicitações e status financeiro..."`   | `"receipt"`   |

### As Absolute Overlay (e.g., obras card transition)
Pass positional style via `**props`:
```python
page_centered_loader(
    "CARREGANDO OBRA",
    "Buscando dados operacionais e análise de risco",
    "hard-hat",
    position="absolute",
    top="0", left="0", right="0", bottom="0",
    z_index="20",
    border_radius=S.R_CARD,
    min_height="unset",
    height="100%",
    padding="0",
)
```

### Inside Glass Card (transparent background)
```python
page_centered_loader(
    "CARREGANDO LOGS",
    "Verificando registros e eventos de auditoria...",
    "shield-check",
    border="none",
    border_radius="0",
    background="transparent",
    min_height="280px",
)
```

## Instant Click Feedback (CSS)
Card clicks get immediate visual feedback via CSS `:active` — zero WebSocket latency:
```css
.project-card:active {
    transform: scale(0.97);
    opacity: 0.8;
    border-color: var(--copper-500) !important;
    transition: transform 0.08s ease, opacity 0.08s ease;
}
```
Apply similar patterns to any clickable cards. WebSocket state (`obras_navigating`) shows
the enterprise overlay after the first round-trip (~100-200ms).

## Anti-Patterns (DO NOT USE)
- ❌ `rx.spinner()` standalone as a page loader
- ❌ `table_skeleton()` as the primary loading state
- ❌ `page_loading_skeleton()` — deprecated, only kept for legacy
- ❌ Simple `rx.center(rx.spinner(...))` overlay
