## Contexto

Temos um projeto Python construído com o framework **Reflex** que precisa ser migrado para **FastAPI (backend) + React (frontend)**. A motivação é exclusivamente operacional — custo de infraestrutura e manutenibilidade do framework. **Nenhuma regra de negócio, lógica, visual, arquitetura ou integração deve mudar.**

---

## Missão

Você vai atuar como arquiteto de migração. Antes de escrever qualquer linha de código, você vai **mapear o projeto inteiro** e produzir um plano de migração detalhado, arquivo por arquivo.

---

## Fase 1 — Mapeamento completo do projeto

Leia recursivamente todos os arquivos do projeto e produza um inventário estruturado contendo:

### 1.1 Estrutura de arquivos
Liste todos os arquivos `.py`, `.toml`, `.env`, `.json`, `.yaml` e qualquer outro arquivo relevante com uma linha descrevendo o papel de cada um.

### 1.2 Páginas e rotas
Para cada página Reflex existente, documente:
- Nome da página
- Rota (`@rx.page(route=...)`)
- Estado Reflex associado (`class State`)
- Componentes utilizados
- Chamadas de backend (event handlers)
- Proteção de acesso (se houver verificação de autenticação/role)

### 1.3 Estados Reflex (State classes)
Para cada `class State(rx.State)` encontrada:
- Nome da classe
- Variáveis de estado (`rx.Var`)
- Event handlers (`async def`)
- Dependências externas (banco, serviços, APIs)

### 1.4 Lógica de backend
Mapeie toda lógica que **não é UI** — processamento, regras de negócio, integrações:
- Funções de acesso ao banco (Supabase ou outro)
- Integrações com IA / MCP
- Geração de documentos (PDF, relatórios)
- Jobs / tarefas assíncronas
- Autenticação e controle de acesso

### 1.5 Arquitetura Multi-Tenant e RBAC
Documente como está implementado hoje:
- Como o tenant é identificado (campo, header, subdomain?)
- Como os roles são definidos e armazenados
- Como as permissões são verificadas nas páginas e handlers
- Middlewares ou decorators de proteção existentes

### 1.6 Integrações externas
Liste todas as integrações:
- Supabase (tabelas usadas, RLS policies relevantes)
- MCP servers (quais, como são chamados)
- APIs de IA (OpenAI, Anthropic, etc.)
- Chaves de API e variáveis de ambiente (liste os nomes, não os valores)

### 1.7 Banco de dados
- Liste todas as tabelas e seus relacionamentos
- Identifique as queries mais críticas
- Documente se há migrations, seeds ou estruturas específicas do Supabase

---

## Fase 2 — Plano de migração

Com base no mapeamento, produza o plano de migração completo seguindo as regras abaixo.

### Princípios da migração

1. **Zero perda de funcionalidade** — cada feature mapeada precisa ter um equivalente explícito no plano
2. **Mínima mudança de lógica** — toda lógica de processamento em Python permanece em Python, apenas muda onde é chamada (de event handler Reflex para rota FastAPI)
3. **Visual idêntico** — o frontend React deve replicar fielmente o visual e o fluxo das páginas Reflex existentes; use os mesmos nomes de componentes, cores, layouts
4. **Multi-tenant e RBAC intactos** — a lógica de tenant e permissões migra para middleware FastAPI, sem simplificação
5. **Banco inalterado** — nenhuma alteração em tabelas, colunas, policies ou estrutura do Supabase
6. **Variáveis de ambiente inalteradas** — o `.env` existente deve continuar funcionando sem renomear chaves

### Estrutura da nova stack

```
backend/
├── main.py                  # Entry point FastAPI
├── routers/                 # Um arquivo por domínio (ex: auth.py, projects.py)
├── middleware/
│   ├── auth.py              # Verificação JWT / Supabase Auth
│   └── tenant.py            # Resolução de tenant por request
├── services/                # Lógica de negócio (migrada dos State handlers)
├── integrations/
│   ├── supabase.py          # Client e helpers
│   ├── mcp.py               # MCP server calls
│   └── ai.py                # OpenAI / Anthropic
├── jobs/                    # Celery tasks (PDF, processamentos pesados)
└── schemas/                 # Pydantic models (request/response)

frontend/
├── src/
│   ├── pages/               # Um arquivo por página (espelha as rotas Reflex)
│   ├── components/          # Componentes reutilizáveis
│   ├── hooks/               # Custom hooks (estado que era rx.State)
│   ├── services/            # Chamadas à API FastAPI
│   └── context/
│       ├── AuthContext.tsx  # Auth state global
│       └── TenantContext.tsx # Tenant state global
```

### Tabela de equivalências Reflex → FastAPI/React

Para cada item mapeado na Fase 1, produza a equivalência exata:

| Elemento Reflex | Arquivo de origem | Equivalente FastAPI/React | Arquivo de destino |
|---|---|---|---|
| `class State` com vars e handlers | `pages/X.py` | Hook `useX` + rota `POST /api/x` | `hooks/useX.ts` + `routers/x.py` |
| `@rx.page(route="/dashboard")` | `pages/dashboard.py` | `<Route path="/dashboard">` | `pages/Dashboard.tsx` |
| Event handler com acesso ao banco | `state.py` | `service.py` + rota FastAPI | `services/x.py` + `routers/x.py` |
| Verificação de role no handler | qualquer State | Dependency FastAPI `require_role()` | `middleware/auth.py` |
| Chamada MCP no handler | qualquer State | Service + rota assíncrona | `integrations/mcp.py` |

_(Preencha esta tabela para cada elemento encontrado no projeto)_

### Plano de execução por fases

#### Fase A — Setup da infraestrutura (sem tocar no Reflex ainda)
- [ ] Criar estrutura de pastas do backend FastAPI
- [ ] Configurar FastAPI com Uvicorn + Gunicorn
- [ ] Migrar conexão Supabase para `integrations/supabase.py`
- [ ] Implementar middleware de autenticação JWT (Supabase Auth)
- [ ] Implementar middleware de tenant
- [ ] Configurar CORS para o frontend React
- [ ] Criar projeto React com Vite + TypeScript
- [ ] Configurar TanStack Query para chamadas à API
- [ ] Configurar React Router com as mesmas rotas do Reflex
- [ ] Implementar AuthContext e TenantContext

#### Fase B — Migração do backend (rota por rota)
Para cada State/handler mapeado:
- [ ] Criar o Pydantic schema correspondente
- [ ] Mover a lógica de negócio para `services/`
- [ ] Criar a rota FastAPI em `routers/`
- [ ] Aplicar as dependencies de auth e tenant
- [ ] Testar a rota isoladamente com curl/Postman antes de conectar ao frontend

#### Fase C — Migração do frontend (página por página)
Para cada página Reflex mapeada:
- [ ] Criar o componente React correspondente
- [ ] Replicar o layout visual com fidelidade
- [ ] Criar o custom hook que substitui o `rx.State`
- [ ] Conectar o hook às rotas FastAPI via TanStack Query
- [ ] Implementar proteção de rota (auth + role) idêntica à do Reflex

#### Fase D — Integrações especiais
- [ ] Migrar todas as chamadas MCP para `integrations/mcp.py`
- [ ] Migrar chamadas de IA para `integrations/ai.py`
- [ ] Configurar Celery + Redis para jobs pesados (PDF, processamentos)
- [ ] Testar cada integração em isolamento

#### Fase E — Validação e cutover
- [ ] Rodar Reflex e FastAPI/React em paralelo
- [ ] Validar cada página/funcionalidade lado a lado
- [ ] Testar multi-tenant com usuários de tenants diferentes
- [ ] Testar todos os roles e permissões
- [ ] Só depois de validação completa: desligar o Reflex

---

## Fase 3 — Execução

Após apresentar o plano e receber aprovação, execute a migração na ordem definida. Para cada arquivo criado:

1. Mostre o arquivo completo
2. Explique o que foi preservado e o que mudou (deve ser quase nada)
3. Aponte qualquer divergência que precise de decisão

**Regra de ouro:** Em caso de dúvida entre simplificar e preservar, sempre preserve. O objetivo é trocar o framework, não redesenhar o sistema.

---

## O que NÃO fazer

- ❌ Não simplificar o RBAC "por enquanto"
- ❌ Não remover multi-tenant "para testar primeiro"
- ❌ Não alterar nomes de tabelas ou colunas no banco
- ❌ Não renomear variáveis de ambiente
- ❌ Não mudar o visual das páginas
- ❌ Não reescrever lógica de negócio que já funciona
- ❌ Não pular a fase de mapeamento e ir direto para o código
- ❌ Não modificar, mover ou apagar nenhum arquivo dentro da pasta app/. Todo código novo vai exclusivamente para backend/ e frontend/. O projeto Reflex deve continuar executável durante toda a migração.
---

## Comece agora

Inicie pelo **mapeamento completo (Fase 1)**. Leia todos os arquivos do projeto antes de escrever qualquer linha de código ou plano. Quando terminar o mapeamento, apresente o inventário e aguarde confirmação para prosseguir para a Fase 2.
