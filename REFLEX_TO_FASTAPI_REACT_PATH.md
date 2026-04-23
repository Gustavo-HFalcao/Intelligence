# Guia Mestre de Migração: Reflex → FastAPI + React
## "Soul Parity 1:1" Path

Este guia define o processo sistemático para migrar aplicações Full-stack Python (**Reflex**) para uma arquitetura desacoplada utilizando **FastAPI** (Backend) e **React** (Frontend). O objetivo central é a **Soul Parity**: preservação absoluta de lógica, visual, regras de acesso e comportamento do banco de dados.

---

## 1. Filosofia de Migração: A Regra de Ouro

> **Em caso de dúvida entre simplificar e preservar, sempre preserve.**

- **Visual Identitário:** O frontend React deve ser um espelho fiel do Reflex. Use os mesmos nomes de componentes, cores, grids e estados hover.
- **Lógica e Integridade:** Toda lógica de cálculo e negócio em Python deve ser portada para o FastAPI com o mínimo de alteração possível.
- **Banco de Dados Intacto:** Não altere tabelas, colunas, RLS policies ou triggers do Supabase. O backend muda, o dado não.
- **Variáveis de Ambiente:** Mantenha os nomes das chaves no `.env` para garantir compatibilidade com scripts de deploy existentes.

---

## 2. Tabela de Equivalências (O Mapa da Alma)

Use esta tabela para localizar onde cada elemento do Reflex deve "morar" na nova stack:

| Elemento Reflex | Origem | Equivalente FastAPI/React | Destino |
| :--- | :--- | :--- | :--- |
| `class State(rx.State)` | `state.py` | Hook `useDomain` + React `Context` | `frontend/src/hooks/` & `context/` |
| `rx.Var` (Computed) | `state.py` | `useMemo` (Frontend) ou campo calculado | `Component.tsx` ou `schemas/` |
| `Event Handler` (async) | `state.py` | Rota `POST/GET` + Service Python | `routers/` & `services/` |
| `@rx.page(route="/x")` | `pages/x.py` | `<Route path="/x" />` | `frontend/src/App.tsx` |
| `rx.on_load` | `pages/x.py` | `useEffect` + TanStack Query | `pages/Page.tsx` |
| `RBAC` (permissões) | Handlers | Dependency `require_role(...)` | `backend/middleware/auth.py` |
| `rx.foreach` | UI | `map()` em arrays | `Component.tsx` |
| `rx.cond` | UI | Operador ternário ou `&&` | `Component.tsx` |

---

## 3. Roadmap de Migração (5 Fases)

### Fase 1: Fundação (Infra & Core)
*Não toque na pasta original do Reflex ainda.*

1. **Estrutura de Pastas:**
   - `backend/`: FastAPI, Routers, Services, Schemas.
   - `frontend/`: React + Vite, Tailwind, TanStack Query.
2. **Core Utilities:**
   - Migre `supabase_client.py` e `config.py` para `backend/integrations/`.
   - Implemente `middleware/auth.py` para validar JWT/Sessão (preservando lógica PBKDF2 se necessário).
   - Implemente `middleware/tenant.py` para isolamento de dados por `client_id`.
3. **Frontend Initial Setup:**
   - Configure o `tailwind.config.ts` com os tokens de cores/design do Reflex (Copper, Glass, etc).
   - Crie o `AuthContext.tsx` e `TenantContext.tsx` para gerenciar o estado global da sessão.

### Fase 2: Backend Porting (Rota por Rota)
*Trabalhe em silos de domínio.*

1. **Schemas (Pydantic):** Crie modelos de Request/Response idênticos ao que o Reflex enviava/esperava.
2. **Services:** Mova a lógica de negócio pura dos `Event Handlers` do Reflex para arquivos de serviço.
3. **Routers:** Exponha os endpoints. Use Dependencies para injetar o tenant e verificar permissões.
   - *Dica:* Teste cada rota com o Swagger (`/docs`) antes de ir para o frontend.

### Fase 3: Frontend Porting (Página por Página)
*Mantenha o Reflex rodando em uma tela e o React na outra.*

1. **Pages:** Crie componentes funcionais para cada rota do Reflex.
2. **Hooks:** Para cada State do Reflex, crie um Hook customizado (ex: `useDashboard`) que gerencia chamadas TanStack Query e estados locais.
3. **Layout Mirroring:** Reutilize componentes como Sidebar e TopBar, garantindo que o espaçamento e iconografia sejam idênticos.

### Fase 4: Integrações Especiais
1. **Background Tasks:** Migre logs pesados ou geração de arquivos (PDF/Excel) para **Celery + Redis**. Isso evita crashes por OOM em ambientes com pouca RAM (Fly.dev/GCP).
2. **AI & Streaming:** Converta o streaming do Reflex para endpoints de **Server-Sent Events (SSE)** no FastAPI para manter o chat reativo.

### Fase 5: Validação e Cutover
1. **Side-by-Side Test:** Compare cada card, gráfico e tabela entre as duas versões.
2. **RBAC Test:** Tente acessar rotas Pro com usuários Free para garantir que o middleware FastAPI está tão rígido quanto o Reflex.
3. **Aprovação Final:** Desligue o container do Reflex e aponte o Load Balancer para a nova stack.

---

## 4. Segurança & Multi-tenant

### Middleware de Tenant (Python)
Para garantir isolamento 1:1, use uma dependência FastAPI que extrai o ID do cliente da sessão e o injeta em todas as queries do banco:
```python
async def get_current_tenant(user: User = Depends(get_current_user)):
    return user.client_id
```

### Route Guards (React)
Implemente um wrapper de rota que verifique se o usuário tem o `role` necessário portado do State original do Reflex:
```tsx
const RoleGuard = ({ role, children }: { role: string[] }) => {
  const { user } = useAuth();
  return role.includes(user.role) ? children : <Navigate to="/unauthorized" />;
};
```

---

## 5. Visual: Design Tokens
Transforme os estilos CSS/Python do Reflex em classes Tailwind:
- **Glassmorphism:** `bg-white/10 backdrop-blur-md border-white/20`
- **Copper Dark:** `bg-[#121212] border-[#2A2A2A] text-slate-200`
- **KPI Cards:** Use `shadcn/ui` customizado para manter o rounding e as sombras originais.

---

## 6. Checklist de Paridade Checklist
- [ ] O `.env` é idêntico?
- [ ] O banco de dados não sofreu alterações?
- [ ] Os cálculos e médias batem centavo por centavo?
- [ ] O fluxo de login e reset de senha é o mesmo?
- [ ] Ícones e cores são 100% iguais?
- [ ] Logs de auditoria continuam sendo gravados no mesmo formato?

---
> **Atenção:** Este guia é agnóstico ao projeto, mas exige rigor técnico na execução para que o usuário final não perceba que o "motor" do sistema mudou.
