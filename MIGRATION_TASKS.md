# Tasklist — Migração Bomtempo (Reflex → FastAPI + React)

> Marque cada item com `[x]` ao concluir. Este arquivo é a fonte da verdade para retomar entre sessões.
> Ao iniciar uma nova sessão, leia este arquivo primeiro.

---

## FASE A — Setup da infraestrutura
> Sem tocar em `bomtempo/`. Reflex deve continuar executável.

- [x] **A.1** Criar estrutura de pastas `backend/` e `frontend/` na raiz
- [x] **A.2** Configurar FastAPI (`main.py`, Uvicorn, CORS para porta 5173, roteamento dinâmico)
- [x] **A.3** Migrar `supabase_client.py` → `backend/integrations/supabase.py` (sync + async, pool, retry)
- [x] **A.4** Implementar `middleware/auth.py` (PBKDF2, sessão cookie httpOnly, Dependency `require_role`)
- [x] **A.5** Implementar `middleware/tenant.py` (resolve `client_id` por sessão, injeta no contexto)
- [x] **A.6** Migrar `config.py` → `backend/core/config.py` (nomes de env vars idênticos)
- [x] **A.7** Configurar Celery + Redis (`workers/celery_app.py`)
- [x] **A.8** Criar projeto React com Vite + TypeScript + React Router v6 + TanStack Query
- [x] **A.9** Implementar `AuthContext.tsx` (login, logout, sessão persistida)
- [x] **A.10** Implementar `TenantContext.tsx` + `useTenant` hook (client_id, role, feature flags)
- [x] **A.11** Configurar Tailwind com tokens Copper/Glass (portados de `theme.py` + `styles.py`)
- [x] **A.12** Criar layout principal React (Sidebar + TopBar + Content) espelhando `layouts/default.py`

---

## FASE B — Migração do backend (rota por rota)
> Ordem: Schema Pydantic → Service → Router → Dependency → Teste curl

- [x] **B.1** `routers/auth.py` — login, logout, reset-password
- [x] **B.2** `services/data_loader.py` — Pandas + cache + isolamento `client_id`
- [x] **B.3** `routers/dashboard.py` — KPIs, filtros, computed vars
- [x] **B.4** `routers/hub.py` — 6 abas Hub Operações
- [x] **B.5** `routers/financeiro.py` — S-curve, cockpit, EVM
- [x] **B.6** `routers/rdo.py` — form, draft, GPS, evidências, atividades
- [x] **B.7** `services/rdo_service.py` — watermark EXIF, OSM map, PDF, view_token
- [x] **B.8** `routers/alertas.py` + `services/alert_service.py`
- [x] **B.9** `routers/usuarios.py` — CRUD + role assignment
- [x] **B.10** `routers/master.py` — console multi-tenant + feature flags
- [x] **B.11** `routers/reembolso.py` + `services/fuel_service.py` (OpenAI vision)
- [x] **B.12** `routers/relatorios.py` — builder + Celery task PDF
- [x] **B.13** `routers/om.py` — geração, faturamento, performance
- [x] **B.14** `routers/observabilidade.py` — logs, system health, LLM cost

---

## FASE C — Migração do frontend (página por página)
> Ordem: componente React + hook TanStack Query + route guard (auth + RBAC)

- [x] **C.1**  `Login.tsx` — split-screen + reset password modal
- [x] **C.2**  `Dashboard.tsx` — KPIs, Recharts, filtros globais
- [x] **C.3**  `HubOperacoes.tsx` — 6 abas (Visão Geral, Dashboard, Cronograma, Auditoria, Timeline, Financeira)
- [x] **C.4**  `RDOForm.tsx` — GPS, signature_pad, atividades, draft
- [x] **C.5**  `Financeiro.tsx` — S-curve, cockpit, EVM (CPI/SPI/EAC/VAC)
- [x] **C.6**  `ChatIA.tsx` — SSE streaming
- [x] **C.7**  `Projetos.tsx`, `Obras.tsx`, `EditorDados.tsx`
- [x] **C.8**  `Alertas.tsx`, `Relatorios.tsx`, `ReembolsoDashboard.tsx`, `ReembolsoForm.tsx`
- [x] **C.9**  `RDODashboard.tsx`, `RDOHistorico.tsx`, `RDOView.tsx` (público sem auth)
- [x] **C.10** `Usuarios.tsx`, `Perfil.tsx`, `MasterConsole.tsx`
- [x] **C.11** `Analytics.tsx`, `Previsoes.tsx`, `OM.tsx`, `LogsAuditoria.tsx`, `Observabilidade.tsx`
- [x] **C.12** `AppMobile.tsx`, `MobileChat.tsx` — voice input
- [x] **C.13** Componentes: Sidebar, TopBar, MainLayout — todos wired no App.tsx
- [x] **C.14** Route guards: `PrivateRoute` + `WithLayout` em App.tsx

---

## FASE D — Integrações especiais

- [x] **D.1** `integrations/ai.py` — query, stream, agentic, whisper, vision
- [x] **D.2** `integrations/ai_tools.py` — execute_sql, generate_chart, search_documents
- [x] **D.3** `workers/tasks/chat_tasks.py` — agentic loop Celery + SSE streaming
- [x] **D.4** `workers/tasks/pdf_tasks.py` — PDF em Celery (não bloqueia RAM)
- [x] **D.5** `integrations/email.py` — Gmail SMTP (reset, alertas, RDO)

---

## FASE E — Validação e cutover
> ⚠️ Só iniciar após todas as fases anteriores concluídas

- [ ] **E.1** Rodar Reflex (3000) + React (5173) em paralelo
- [ ] **E.2** Validar cada página lado a lado (visual + dados + fluxos)
- [ ] **E.3** Testar multi-tenant com usuários de tenants diferentes
- [ ] **E.4** Testar todos os roles (Administrador, Engenheiro, Gestão-Mobile, Operário)
- [ ] **E.5** ⚠️ Desligar Reflex — **aguardar aprovação explícita**

---

## Progresso

| Fase | Total | Concluídas | % |
|------|-------|-----------|---|
| A | 12 | 12 | 100% |
| B | 14 | 14 | 100% |
| C | 14 | 14 | 100% |
| D | 5 | 5 | 100% |
| E | 5 | 0 | 0% |
| **Total** | **50** | **45** | **90%** |

---

_Última atualização: 2026-04-17 — Fases A–D 100% concluídas. Pendente: Fase E (validação e cutover)._
