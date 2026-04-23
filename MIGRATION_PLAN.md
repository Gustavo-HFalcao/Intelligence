# Migração Bomtempo: Reflex → FastAPI + React

> **Regra de ouro:** Em caso de dúvida entre simplificar e preservar, sempre preserve.
> O objetivo é trocar o framework, não redesenhar o sistema.

---

## Restrições absolutas

- ❌ Não tocar em nada dentro de `bomtempo/` — o Reflex deve continuar executável durante toda a migração
- ❌ Não alterar tabelas, colunas ou RLS do Supabase
- ❌ Não renomear variáveis de ambiente (`.env` permanece idêntico)
- ❌ Não simplificar RBAC ou multi-tenant
- ❌ Não mudar o visual (design tokens Copper/Glass migram para `tailwind.config.ts`)
- ❌ Não reescrever lógica de negócio que já funciona

---

## Stack de destino

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Uvicorn/Gunicorn |
| Jobs assíncronos | Celery + Redis |
| Frontend | React + Vite + TypeScript |
| Roteamento | React Router v6 |
| Data fetching | TanStack Query |
| UI | Tailwind CSS + Shadcn/UI (tokens Copper/Glass) |
| AI | OpenAI (gpt-4o, whisper, vision) — mesmos endpoints |
| Banco | Supabase PostgreSQL (inalterado) |

---

## Estrutura de destino

```
backend/
├── main.py                        # Entry point FastAPI + roteamento dinâmico
├── middleware/
│   ├── auth.py                    # PBKDF2 verify + sessão + RBAC dependency
│   └── tenant.py                  # Resolve client_id por request
├── routers/
│   ├── auth.py                    # POST /api/auth/login, /logout, /reset-password
│   ├── dashboard.py               # GET /api/dashboard (KPIs, filtros, computed vars)
│   ├── hub.py                     # Hub Operações (6 abas)
│   ├── financeiro.py              # S-curve, cockpit, KPIs, cash flow
│   ├── rdo.py                     # RDO form, draft, atividades, GPS, evidências
│   ├── alertas.py                 # Regras + histórico
│   ├── usuarios.py                # CRUD + role assignment
│   ├── master.py                  # Multi-tenant console + feature flags
│   ├── reembolso.py               # Fuel reimbursement + OpenAI vision
│   ├── relatorios.py              # Report builder + export (Celery)
│   ├── om.py                      # O&M: geração, faturamento, performance
│   └── observabilidade.py         # System health + logs + LLM cost
├── services/
│   ├── data_loader.py             # Pandas + cache Redis/pickle (portado do DataLoader)
│   ├── rdo_service.py             # Watermark EXIF + GPS + OSM + PDF + view_token
│   ├── alert_service.py           # Regras + engine
│   └── fuel_service.py            # Receipt analysis + cálculo reembolso
├── integrations/
│   ├── supabase.py                # HTTP REST client sync+async (pool, retry, RPC)
│   ├── ai.py                      # OpenAI: query, stream, agentic, whisper, vision
│   ├── ai_tools.py                # Tool definitions + execute_tool() (SQL, charts, docs)
│   └── email.py                   # Gmail SMTP (reset, alertas, RDO confirmação)
├── workers/
│   ├── celery_app.py              # Celery config + Redis broker
│   └── tasks/
│       ├── pdf_tasks.py           # Geração PDF (RDO, relatórios) em background
│       ├── chat_tasks.py          # Agentic loop com streaming SSE
│       └── email_tasks.py         # Envio de email em background
├── schemas/                       # Pydantic models (request/response)
│   ├── auth.py
│   ├── rdo.py
│   ├── financeiro.py
│   └── ...
└── core/
    └── config.py                  # Env vars (nomes idênticos ao .env atual)

frontend/
├── src/
│   ├── pages/                     # Um arquivo por página (espelha as 31 rotas Reflex)
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── HubOperacoes.tsx       # 6 abas
│   │   ├── RDOForm.tsx            # GPS, fotos EXIF, canvas signature, draft
│   │   ├── Financeiro.tsx         # S-curve, EVM (CPI/SPI/EAC/VAC)
│   │   ├── ChatIA.tsx             # Streaming + gráficos inline
│   │   └── ...                    # + 25 outras páginas
│   ├── components/
│   │   ├── ui/                    # Shadcn/UI customizado com tokens Copper/Glass
│   │   ├── charts/                # Recharts: área, barras, pizza, S-curve
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx
│   │   └── ...
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useTenant.ts
│   │   ├── useDashboard.ts
│   │   ├── useRDO.ts
│   │   └── ...                    # Um hook por domínio (substitui rx.State)
│   ├── services/                  # Chamadas à API FastAPI (axios/fetch)
│   │   ├── api.ts                 # Base client com interceptors de auth
│   │   └── ...
│   └── context/
│       ├── AuthContext.tsx         # Login, logout, sessão persistida
│       └── TenantContext.tsx       # client_id, role, feature flags
├── tailwind.config.ts             # Tokens Copper/Glass (portados de theme.py + styles.py)
└── App.tsx                        # React Router v6 + TanStack Query Provider
```

---

## Tabela de equivalências Reflex → FastAPI/React

| Elemento Reflex | Arquivo de origem | Equivalente FastAPI/React | Arquivo de destino |
|---|---|---|---|
| `GlobalState` (auth vars) | `state/global_state.py` | `AuthContext` + `POST /api/auth/login` | `context/AuthContext.tsx` + `routers/auth.py` |
| `GlobalState` (chat + agentic loop) | `state/global_state.py` | `useChatIA` + Celery task + SSE | `hooks/useChatIA.ts` + `workers/tasks/chat_tasks.py` |
| `GlobalState` (dashboard computed vars) | `state/global_state.py` | `useDashboard` + `GET /api/dashboard` | `hooks/useDashboard.ts` + `routers/dashboard.py` |
| `HubState` | `state/hub_state.py` | `useHub` + `GET /api/hub/*` | `hooks/useHub.ts` + `routers/hub.py` |
| `FinState` | `state/fin_state.py` | `useFinanceiro` + `GET /api/financeiro/*` | `hooks/useFinanceiro.ts` + `routers/financeiro.py` |
| `RDOState` | `state/rdo_state.py` | `useRDO` + `POST /api/rdo/*` | `hooks/useRDO.ts` + `routers/rdo.py` |
| `AlertasState` | `state/alertas_state.py` | `useAlertas` + `GET/POST /api/alertas` | `hooks/useAlertas.ts` + `routers/alertas.py` |
| `UsuariosState` | `state/usuarios_state.py` | `useUsuarios` + `GET/POST /api/usuarios` | `hooks/useUsuarios.ts` + `routers/usuarios.py` |
| `MasterState` | `state/master_state.py` | `useMaster` + `GET/POST /api/master/*` | `hooks/useMaster.ts` + `routers/master.py` |
| `RelatoriosState` | `state/relatorios_state.py` | `useRelatorios` + Celery task PDF | `hooks/useRelatorios.ts` + `workers/tasks/pdf_tasks.py` |
| `ReembolsoState` | `state/reembolso_state.py` | `useReembolso` + `POST /api/reembolso` | `hooks/useReembolso.ts` + `routers/reembolso.py` |
| `OMState` | `state/om_state.py` | `useOM` + `GET /api/om/*` | `hooks/useOM.ts` + `routers/om.py` |
| `ObservabilityState` | `state/observability_state.py` | `useObservabilidade` + `GET /api/obs/*` | `hooks/useObservabilidade.ts` + `routers/observabilidade.py` |
| `rdo_service.py` | `core/rdo_service.py` | `services/rdo_service.py` (inalterado) | `backend/services/rdo_service.py` |
| `DataLoader` | `core/data_loader.py` | `services/data_loader.py` (inalterado) | `backend/services/data_loader.py` |
| `ai_client.py` | `core/ai_client.py` | `integrations/ai.py` (inalterado) | `backend/integrations/ai.py` |
| `ai_tools.py` | `core/ai_tools.py` | `integrations/ai_tools.py` (inalterado) | `backend/integrations/ai_tools.py` |
| `supabase_client.py` | `core/supabase_client.py` | `integrations/supabase.py` (inalterado) | `backend/integrations/supabase.py` |
| `auth_utils.py` (PBKDF2) | `core/auth_utils.py` | `middleware/auth.py` + Dependency | `backend/middleware/auth.py` |
| `email_service.py` | `core/email_service.py` | `integrations/email.py` (inalterado) | `backend/integrations/email.py` |
| `@rx.page(route="/login")` | `pages/login.py` | `<Route path="/login">` + `Login.tsx` | `frontend/src/pages/Login.tsx` |
| `@rx.page(route="/")` | `pages/index.py` | `<Route path="/">` + `Dashboard.tsx` | `frontend/src/pages/Dashboard.tsx` |
| `@rx.page(route="/hub")` | `pages/hub_operacoes.py` | `<Route path="/hub">` + `HubOperacoes.tsx` | `frontend/src/pages/HubOperacoes.tsx` |
| `@rx.page(route="/rdo-form")` | `pages/rdo_form.py` | `<Route path="/rdo-form">` + `RDOForm.tsx` | `frontend/src/pages/RDOForm.tsx` |
| `@rx.page(route="/financeiro")` | `pages/financeiro.py` | `<Route path="/financeiro">` + `Financeiro.tsx` | `frontend/src/pages/Financeiro.tsx` |
| `@rx.page(route="/chat-ia")` | `pages/chat_ia.py` | `<Route path="/chat-ia">` + `ChatIA.tsx` | `frontend/src/pages/ChatIA.tsx` |
| `@rx.page(route="/rdo/:token")` | `pages/rdo_view.py` | `<Route path="/rdo/:token">` + `RDOView.tsx` | `frontend/src/pages/RDOView.tsx` |
| `stream_chat_bg()` (background) | `state/global_state.py` | Celery task + SSE endpoint | `workers/tasks/chat_tasks.py` + `routers/chat.py` |
| `pdf_utils.html_to_pdf()` | `core/pdf_utils.py` | Celery task | `workers/tasks/pdf_tasks.py` |
| Verificação de role no handler | qualquer State | `Depends(require_role(...))` | `middleware/auth.py` |
| Isolamento `client_id` nas queries | qualquer State | `Depends(get_current_tenant)` | `middleware/tenant.py` |
| Feature flags por contrato | `state/feature_flags_state.py` | Injetado no TenantContext | `context/TenantContext.tsx` |
| `@rx.var` (computed var) | qualquer State | `useMemo` ou campo calculado na API | hook correspondente |
| Thread pools (executors.py) | `core/executors.py` | Celery workers + `asyncio.run_in_executor` | `workers/celery_app.py` |
| Cache Redis/pickle | `core/redis_cache.py` | Cache mantido em `services/data_loader.py` | `backend/services/data_loader.py` |
| `@rx.event(background=True)` | qualquer State | `BackgroundTasks` FastAPI ou Celery task | rota correspondente |

---

## Plano de execução detalhado

### FASE A — Setup da infraestrutura

> Duração estimada: Semana 1 | Sem tocar em `bomtempo/`

- [ ] **A.1** Criar estrutura de pastas `backend/` e `frontend/` na raiz do projeto
- [ ] **A.2** Configurar FastAPI (`main.py`, Uvicorn, CORS para porta 5173, roteamento dinâmico)
- [ ] **A.3** Migrar `supabase_client.py` → `backend/integrations/supabase.py` (sync + async, pool, retry idênticos)
- [ ] **A.4** Implementar `middleware/auth.py` (PBKDF2 verify portado de `auth_utils.py`, sessão via cookie httpOnly, Dependency `require_role`)
- [ ] **A.5** Implementar `middleware/tenant.py` (resolve `client_id` por sessão, injeta em contexto da request)
- [ ] **A.6** Migrar `config.py` → `backend/core/config.py` (env vars com nomes idênticos ao `.env` atual)
- [ ] **A.7** Configurar Celery + Redis (`workers/celery_app.py`) para jobs pesados (PDF, IA streaming)
- [ ] **A.8** Criar projeto React com Vite + TypeScript + React Router v6 + TanStack Query
- [ ] **A.9** Implementar `AuthContext.tsx` (login, logout, sessão persistida em cookie/localStorage, auto-refresh)
- [ ] **A.10** Implementar `TenantContext.tsx` + `useTenant` hook (client_id, role, feature flags)
- [ ] **A.11** Configurar Tailwind com tokens Copper/Glass (portados de `theme.py` + `styles.py`)
- [ ] **A.12** Criar layout principal React (Sidebar + TopBar + Content) espelhando `layouts/default.py`

---

### FASE B — Migração do backend (rota por rota)

> Duração estimada: Semana 2 | Cada item: Schema → Service → Router → Dependency → Teste com curl

- [ ] **B.1** `routers/auth.py` — `POST /api/auth/login`, `/logout`, `/reset-password` (portado de `GlobalState.check_login + send_reset_link`)
- [ ] **B.2** `services/data_loader.py` — Pandas, cache Redis/pickle, isolamento por `client_id` (portado do `DataLoader` atual)
- [ ] **B.3** `routers/dashboard.py` — KPIs globais, filtros, computed vars (portado de `GlobalState` vars de dashboard)
- [ ] **B.4** `routers/hub.py` — 6 abas: Visão Geral, Dashboard, Cronograma, Auditoria (Bolsão), Timeline, Financeira
- [ ] **B.5** `routers/financeiro.py` — S-curve, cockpit, KPIs EVM (CPI/SPI/EAC/VAC), cash flow
- [ ] **B.6** `routers/rdo.py` — form, draft auto-save, atividades com cascata, GPS check-in/out, evidências
- [ ] **B.7** `services/rdo_service.py` — watermark EXIF + GPS + OSM map thumbnail + ReportLab PDF + view_token (portado direto)
- [ ] **B.8** `routers/alertas.py` + `services/alert_service.py` — regras + histórico de disparos
- [ ] **B.9** `routers/usuarios.py` — CRUD usuários, role assignment, multi-tenant
- [ ] **B.10** `routers/master.py` — console multi-tenant, feature flags, métricas de uso
- [ ] **B.11** `routers/reembolso.py` + `services/fuel_service.py` — receipt upload + OpenAI vision analysis
- [ ] **B.12** `routers/relatorios.py` — builder + disparo de Celery task para geração PDF
- [ ] **B.13** `routers/om.py` — geração, faturamento, performance O&M
- [ ] **B.14** `routers/observabilidade.py` — system health, logs, LLM cost (tabela `llm_observability`)

---

### FASE C — Migração do frontend (página por página)

> Duração estimada: Semana 3 | Cada item: componente React + hook + conexão TanStack Query + route guard

- [ ] **C.1** `Login.tsx` — split-screen desktop + mobile, reset password modal
- [ ] **C.2** `Dashboard.tsx` — KPIs, gráficos Recharts, filtros globais (`useGlobalData` hook)
- [ ] **C.3** `HubOperacoes.tsx` — 6 abas (Visão Geral, Dashboard, Cronograma Gantt, Auditoria Bolsão + Lightbox, Timeline, Financeira)
- [ ] **C.4** `RDOForm.tsx` — GPS, fotos com EXIF (exifr.js), atividades com cascata macro→micro, canvas signature, draft localStorage
- [ ] **C.5** `Financeiro.tsx` — S-curve acumulada, cockpit KPIs, painel EVM (CPI/SPI/EAC/VAC)
- [ ] **C.6** `ChatIA.tsx` — streaming SSE, tool results inline, gráficos Recharts dentro do chat
- [ ] **C.7** `Projetos.tsx`, `Obras.tsx`, `EditorDados.tsx` — listagens, filtros, edição inline
- [ ] **C.8** `Alertas.tsx`, `Relatorios.tsx`, `ReembolsoDashboard.tsx`, `ReembolsoForm.tsx`
- [ ] **C.9** `RDODashboard.tsx`, `RDOHistorico.tsx`, `RDOView.tsx` (público, sem auth, token-based)
- [ ] **C.10** `Usuarios.tsx`, `Perfil.tsx`, `MasterConsole.tsx`, `MasterMetricas.tsx`, `MasterSettings.tsx`
- [ ] **C.11** `Analytics.tsx`, `Previsoes.tsx`, `OM.tsx`, `LogsAuditoria.tsx`, `Observabilidade.tsx`
- [ ] **C.12** `AppMobile.tsx` (`/app-mobile`), `MobileChat.tsx` (`/mobile-chat`) — voice input + chat
- [ ] **C.13** Componentes reutilizáveis: `Charts/` (Recharts), `KPICard`, `Sidebar`, `TopBar`, `Skeletons`, `WeatherWidget`, `WindyMap`
- [ ] **C.14** Route guards: `PrivateRoute` (auth) + `RoleRoute` (RBAC) espelhando verificações do Reflex

---

### FASE D — Integrações especiais

> Duração estimada: Semana 4

- [ ] **D.1** `integrations/ai.py` — OpenAI: `query`, `stream`, `query_agentic`, `transcribe_audio`, `analyze_receipt_image` (portado de `ai_client.py`)
- [ ] **D.2** `integrations/ai_tools.py` — tool definitions + `execute_tool()`: `execute_sql`, `generate_chart_data`, `search_documents` (portado de `ai_tools.py`)
- [ ] **D.3** `workers/tasks/chat_tasks.py` — agentic loop (até 5 iterações, tool calling) via Celery + SSE endpoint para streaming de tokens
- [ ] **D.4** `workers/tasks/pdf_tasks.py` — geração PDF (RDO + relatórios) via Celery (não bloqueia 1GB RAM do processo principal)
- [ ] **D.5** `integrations/email.py` — Gmail SMTP: reset, alertas, confirmação RDO (portado de `email_service.py` + `alert_email_service.py`)

---

### FASE E — Validação e cutover

> Só executar após todas as fases anteriores completas

- [ ] **E.1** Rodar Reflex (porta 3000) e React (porta 5173) em paralelo para validação lado a lado
- [ ] **E.2** Validar cada página/funcionalidade lado a lado (visual, dados, fluxos completos)
- [ ] **E.3** Testar multi-tenant com usuários de tenants diferentes (isolamento de dados)
- [ ] **E.4** Testar todos os roles e permissões (Administrador, Engenheiro, Gestão-Mobile, Operário)
- [ ] **E.5** ⚠️ Desligar Reflex — **só executar após aprovação explícita do time**

---

## Variáveis de ambiente (nomes preservados)

| Variável | Uso |
|----------|-----|
| `SUPABASE_URL` | API base Supabase |
| `SUPABASE_SERVICE_KEY` | Server-side key (bypassa RLS) |
| `OPENAI_API_KEY` | Chat + Whisper |
| `OPENAI_VISION_KEY` | Análise de notas fiscais (gpt-4o vision) |
| `RDO_EMAIL_USER` | Gmail SMTP sender |
| `RDO_EMAIL_PASSWORD` | Gmail app password |
| `REDIS_URL` | Celery broker + cache (opcional no dev) |

---

## Tabelas Supabase (inalteradas)

`login` · `clients` · `roles` · `user_roles` · `contratos` · `hub_atividades` · `fin_custos` · `om_geracoes` · `rdo_master` · `rdo2_mao_obra` · `rdo2_atividades` · `rdo2_evidencias` · `chat_sessions` · `chat_messages` · `llm_observability` · `fuel_reimbursements` · `password_reset_tokens` · `alert_rules` · `alert_logs`

---

## Storage buckets Supabase (inalterados)

`rdo-pdfs` · `rdo-evidencias` · `relatorios-pdfs` · `fuel_reimbursements_nf` · `fuel_reimbursements_pdfs`
