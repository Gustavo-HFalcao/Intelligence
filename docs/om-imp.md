# O&M Intelligence — Implementação

> Sistema de Inteligência Energética para monitoramento de inversores solares.
> Não é um viewer de dados — é uma plataforma de decisão operacional e financeira.

---

## Status Geral

| Sprint | Tema | Status |
|---|---|---|
| Sprint 1 | Base Funcional — Integração Real | ✅ Concluído |
| Sprint 2 | Core de Valor — PR, Previsto, Financeiro | ✅ Concluído |
| Sprint 3 | Alertas Inteligentes | ✅ Concluído |
| Sprint 4 | UX Premium | ✅ Concluído |
| Sprint 5 | Performance Avançada | ✅ Concluído |
| Sprint 5.1 | Backfill Histórico (6 meses, automático) | ✅ Concluído |
| Sprint 6 | Manutenção | ✅ Concluído |
| Sprint 7 | IA & Insights | ⬜ Pendente |
| Sprint 8 | Financeiro Avançado | ⬜ Pendente |
| Sprint 9 | Benchmark entre Usinas | ⬜ Pendente |
| Sprint 10 | Melhorias Técnicas & Expansão | ⬜ Backlog |

---

## 🟢 SPRINT 1 — Base Funcional (Integração Real)

**Objetivo:** Dados reais fluindo, banco consistente, sync automático.

### Plataformas

#### ShineMonitor / Eybond
- [x] Auth SHA-1 sign implementado e validado
- [x] Bug fix: `_signed_params()` — ordem dos parâmetros sensível (não sortear)
- [x] Bug fix: `get_plants()` — campo correto é `dat.info`, não `dat.plant`
- [x] Bug fix: mapeamento tensão CA — campo `"AB voltage/A phase voltage"` normalizado
- [x] `get_latest_reading()` — todos os campos mapeados e validados com dados reais
- [x] `get_energy_history()` — endpoint de histórico mensal implementado
- [x] `discover_and_validate()` — fluxo completo de descoberta automática
- [x] **Usina Eduardo Porto** — online, dados reais confirmados (20 kW, 208.440 kWh total)
- [x] **Usina Alvaro Porto** — online, dados reais confirmados (39 kW, 138.467 kWh total)
- [x] Backfill histórico — 106+108 leituras intraday reais inseridas (3 meses, formato title/row parseado)

#### Solarman / IGEN / Deye
- [x] BASE_URL corrigido para `globalapi.solarmanpv.com`
- [x] Auth OAuth2 + SHA256 implementado (aguardando credenciais do cliente)
- [x] `get_latest_reading()` — mapeamento completo de campos
- [x] `get_historical_readings()` — endpoint de histórico por device implementado
- [x] `discover_and_validate()` — fluxo de discovery implementado
- [x] 13 inversores da **9energia** cadastrados no banco (status: pending)
- [x] Estrutura pronta para ativar assim que `app_id` e `app_secret` chegarem
- [ ] **Aguardando:** `app_id` + `app_secret` da conta `bernardo.veloso@9energia.com` (solicitado via `service@solarmanpv.com`)
- [ ] Ativar sync dos 13 inversores via `PATCH /api/inversores/{id}` com as credenciais
- [ ] Backfill histórico — puxar últimos 30 dias dos 13 inversores

#### Growatt ShineServer
- [x] Adapter implementado (SHA-256 + cookie)
- [x] Growatt Demo cadastrado como placeholder
- [ ] Solicitar OpenAPI key em `openapi.growatt.com`
- [ ] Validar com primeiro cliente real

### Backend
- [x] `client_inverters` table — schema completo com `plant_meta`, `plant_name`
- [x] `inverter_readings` table — núcleo normalizado + `raw_data JSONB`
- [x] Índices de performance: `(inverter_id, ts DESC)`
- [x] Router `/api/inversores` — CRUD completo
- [x] `POST /api/inversores/validate` — valida credenciais antes de salvar
- [x] `POST /api/inversores/{id}/sync` — sync manual por inversor
- [x] `GET /api/inversores/sync-all` — dispara sync de toda a frota
- [x] `GET /api/inversores/{id}/readings` — histórico com série diária
- [x] Auth token cache in-memory com TTL e refresh automático
- [x] Auto-sync assíncrono a cada 10 minutos (asyncio task no lifespan)
- [x] `get_plant_info()` ShineMonitor — captura tarifa, potência, data instalação, endereço, coords
- [x] Enrichment lazy rico: `queryPlantInfo` + geocoding Nominatim quando coords do portal são inválidas
- [x] `POST /api/inversores/{id}/sync-history` — **DESABILITADO** (`queryDeviceDataOneDay` retorna dados de planta, não por dispositivo; reabilitar quando identificar endpoint correto)
- [x] Deduplicação de readings — janela de 4 min no `_save_reading`
- [ ] Retry com backoff exponencial em caso de timeout de API

### Frontend
- [x] `GestaoInversores.tsx` — hub de gestão com grid/list view, filtros, KPIs
- [x] `InversorDetalhe.tsx` — detalhe por inversor com tabs e charts
- [x] Wizard de cadastro 4 etapas: modo → plataforma → credenciais → metadados
- [x] Tabs: Visão Geral, Dashboard, Strings DC, Financeiro, Lançamentos (manual), Config
- [x] Charts condicionais por `capabilities` (temperatura, strings, bateria, fases)
- [x] Bug fix: curva de potência filtrada para o dia atual (evitar labels duplicados HH:MM)
- [x] Bug fix: tab Strings DC também filtrada para o dia atual
- [x] `plant_name` exibido nos cards quando disponível
- [x] Sync manual por inversor com loading state
- [x] Botão "Sync All" no header da GestaoInversores
- [x] Badge de "aguardando credenciais" para inversores Solarman pending
- [x] Indicador "há Xmin / Xh / Xd" de última leitura no card
- [x] Toast de sucesso/erro no sync com dados resumidos (kW · kWh hoje)

### Banco de Dados
- [x] Deletados demos: "Inversor Demo ShineMonitor", "Deye Demo SolarmanPV"
- [x] Criada "Usina Alvaro Porto" com dados reais
- [x] 13 inversores 9energia inseridos (solarman, pending)
- [x] Coluna `plant_meta JSONB` adicionada
- [x] Coluna `plant_name TEXT` adicionada
- [x] Índices de performance criados
- [x] Limpeza `inverter_readings` — removidas leituras zeradas e de inversores deletados

---

## 🟡 SPRINT 2 — Core de Valor (Diferencial Mínimo)

**Objetivo:** O sistema deve responder: "Está performando bem?" e "Está perdendo dinheiro?"

### Pré-requisitos confirmados ✅
- Tarifa: R$ 0,80/kWh (ambas usinas, via `plant_meta.tariff_kwh`)
- Coordenadas: Alvaro Porto confirmadas; Eduardo Porto provisórias (mesmas coords)
- Potência instalada: 40 kW / 75 kW corrigidos no banco
- Readings real-time acumulando a cada 10 min desde mai/05

### Energia Prevista
- [x] `GET /api/inversores/{id}/irradiance?date=YYYY-MM-DD`
  - Fonte primária: NASA POWER (`ALLSKY_SFC_SW_DWN`) — ~6 dias lag
  - Fallback automático: Open-Meteo (`shortwave_radiation_sum` ÷ 3.6) — dados até hoje
  - Retorna `source: "nasa_power" | "open_meteo"`, `available: bool`
- [x] `E_prevista = irradiância × kWp × 0.80` (eficiência 80% default)
- [x] Bug fix: `plant_meta` gravado como dict (não `json.dumps`) — JSONB nativo no Supabase

### Cálculos de Performance
- [x] `GET /api/inversores/{id}/performance?date=YYYY-MM-DD`
  - Retorna: `{e_real, e_prevista, pr, desvio_pct, perda_rs, status, irradiance, kWp, tariff_kwh}`
- [x] **PR:** `E_real / E_prevista` — ignorado se `e_real < 0.5 kWh`
- [x] **Desvio %:** `(E_real - E_prevista) / E_prevista × 100`
- [x] **Perda R$:** `max(0, E_prevista - E_real) × tariff_kwh`
- [x] Regras de status: Normal ≥ 0.85 / Atenção 0.70–0.85 / Crítico < 0.70

### Frontend
- [x] Bloco "Performance de Hoje" no `TabVisaoGeral` com PR, Previsto, Desvio, Perda
- [x] Badge de status colorido (🟢🟡🔴) com label
- [x] Fonte de irradiância exibida (NASA Power / Open-Meteo)
- [x] Query com `refetchInterval: 300s`, `staleTime: 60s`
- [x] Gráfico "Real vs Previsto" — AreaChart dual (real teal + previsto dashed) com curva senoidal sintética
- [x] Status da usina (PR badge + perda R$) propagado para card na `GestaoInversores`

---

## 🟢 SPRINT 3 — Alertas Inteligentes

**Objetivo:** Sistema detecta problemas automaticamente, sem o usuário precisar olhar gráficos.

### Engine de Alertas
- [x] Tabela `inverter_alerts` — `id, inverter_id, client_id, alert_type, severity, status, title, detail, value, threshold, opened_at, resolved_at, muted_until, meta`
- [x] Alert types: `offline`, `low_generation`, `string_imbalance`, `high_temp`, `pr_degradation`
- [x] Deduplicação: nenhum alert duplicado enquanto há um aberto do mesmo tipo
- [x] Auto-resolve: fecha alert quando condição deixa de ser verdadeira

### Detecção
- [x] **Offline:** último sync > 35 min — abre `critical`; resolve quando sync retorna
- [x] **Baixa Geração:** potência atual < 60% da esperada (com irradiância ≥ 0.5 kWh/m²); ignora noite (<5 W)
- [x] **String Discrepante:** `(max - min) / média > 15%`; ignora strings com < 10% da máxima e períodos noturnos
- [x] **Temperatura Alta:** média > 75°C nos últimos 15 min
- [x] **PR Degradação:** PR médio 7 dias < 75%; busca dados do banco internamente; roda a cada 4h

### Backend
- [x] `backend/integrations/alerts.py` — engine isolado, chamado após cada sync
- [x] `GET /api/inversores/{id}/alerts?status=open|resolved|all`
- [x] `PATCH /api/inversores/{id}/alerts/{alert_id}/resolve`
- [x] `PATCH /api/inversores/{id}/alerts/{alert_id}/mute?hours=24`
- [x] Verificação de ownership no resolve/mute (404 se não pertence ao inversor)
- [x] Integrado no `_sync_all_inversors_background` — roda após cada sync bem-sucedido

### Frontend
- [x] `AlertBanner` — banner no topo do `InversorDetalhe` com todos os alertas abertos
- [x] Cores por severity: vermelho (critical) / âmbar (warning) / azul (info)
- [x] Botões inline: "24h" (silenciar) e "✕" (resolver)
- [x] Badge de alertas abertos no card da `GestaoInversores` (vermelho se critical, âmbar se warning)
- [x] Queries com refetch automático (2min no detalhe, 5min nos cards)

### Correções de Precisão (aplicadas nesta sessão)
- [x] **Bug `raw_data` JSONB:** `json.dumps()` removido — 266 leituras corrigidas no banco
- [x] **Timezone PR:** `day_readings` filtrado por data BRT (não UTC) — fix para leituras 00–03h UTC
- [x] **Open-Meteo forecast flag:** `is_forecast: True` quando fonte é Open-Meteo e data ≥ hoje; disclaimer no frontend
- [x] **Readings scope:** performance endpoint busca 300 leituras (não 500) com comentário justificando

---

## 🟢 SPRINT 4 — UX Premium

**Objetivo:** Experiência visual sofisticada e orientada a decisão.

- [x] **Status ring colorido** no ícone do card — teal (active/night), teal neon (live), vermelho (error), âmbar (pending)
- [x] **Pulse animation** quando inversor está live (online + sync < 20 min) — `animate-ping` no anel e nos dots da fleet strip
- [x] **Fleet Status Strip** — barra de dots coloridos entre KPI e filtros, mostrando status de toda a frota em tempo real
- [x] **Tooltip rico** no gráfico de potência — potência real, previsto, acumulado kWh, temperatura, tudo em um card
- [x] **Gráfico de potência + previsto** — `ComposedChart` com `Area` real + `Line` dashed previsto (seno calibrado: `P_pico = E_prev × π / 24`)
- [x] **Timeline de eventos** — lista cronológica de syncs + alertas abertos/resolvidos com dots coloridos e linha vertical
- [ ] Comparativo entre inversores (mini-ranking por PR) — depende de endpoint de fleet-performance (Sprint 5)
- [ ] Modo dark/light — skip (já é dark-first)
- [ ] Responsivo mobile completo — parcialmente funcional, melhoria contínua

---

## 🟢 SPRINT 5 — Performance Avançada

**Objetivo:** Métricas de engenharia para o usuário avançado.

### Backend
- [x] `GET /api/inversores/{id}/pr-history?days=30` — PR diário com batch de irradiância
  - NASA POWER: **request único** cobrindo todo o período (sem loop de chamadas)
  - Open-Meteo fallback automático para datas dos últimos ~6 dias (lag NASA)
  - Retorna: `{days: [{date, e_real_kwh, irr_kwh_m2, e_prevista_kwh, pr, perda_rs}], summary: {avg_pr, best_pr, worst_pr, total_perda_rs}}`
  - Filtragem BRT correta no agrupamento de energia (max energy_today_kwh por dia)

### Frontend — Tab "Análise" (nova tab, visível apenas em inversores API)
- [x] **PR Histórico** — LineChart 30 dias com reference lines em 0.85 (Normal) e 0.70 (Atenção)
- [x] **Geração Real vs Irradiância** — ComposedChart dual Y-axis: barras kWh + linha kWh/m²
- [x] **Temperatura vs Potência** — ScatterChart de correlação (visível apenas com `has_temperature`)
- [x] **Specific Yield** — `E_total / kWp` (kWh/kWp), calculado client-side
- [x] **Capacity Factor** — `E_total / (kWp × horas_desde_instalação)`, com base na `install_date`
- [x] **Export CSV** — download do histórico de PR como `.csv` gerado client-side
- [ ] Comparativo ano-a-ano — requer histórico de 12+ meses (futuro)
- [ ] Fator de Potência elétrico — disponível apenas em alguns modelos com V+I CA completos

---

## 🟢 SPRINT 5.1 — Backfill Histórico

**Objetivo:** Novo cliente vê 6 meses de dados reais no dia 1, sem ação manual.

### Backend
- [x] `backend/integrations/backfill.py` — engine de backfill isolado, agnóstico de plataforma
- [x] **Phase 1 (diário, rápido):** `queryDeviceDataOneDay datetype=month` ShineMonitor — 6 calls para 6 meses; `time_type=3` Solarman — 1 call para todo o período
- [x] **Phase 2 (intraday, lento):** `datetype=day` ShineMonitor — 1 call/dia, ~180 calls; `time_type=2 horário` Solarman — 1 call/semana, ~26 calls
- [x] `_bulk_insert()` — POST em chunks de 200 diretamente ao Supabase REST (fallback individual)
- [x] `_fetch_existing_dates()` — 1 round-trip para set de datas já cobertas (Phase 1 dedup)
- [x] `_fetch_existing_buckets()` — 1 round-trip para set de buckets de 5 min (Phase 2 dedup cross-run)
- [x] `_month_first()` — aritmética correta de meses (não `i×28`)
- [x] `POST /api/inversores/{id}/backfill?months=6&phase=both` — dispara em thread daemon
- [x] `GET /api/inversores/{id}/backfill-status` — progresso em tempo real (days_done/days_total)
- [x] **Auto-trigger:** Phase 1 dispara automaticamente na primeira sync bem-sucedida de cada inversor
- [x] **Auto-retry:** backfill com status `error` retenta no próximo ciclo de 10 min
- [x] Persiste `plant_meta.backfill.done` no banco — sobrevive restart, nunca re-dispara desnecessariamente

### Frontend (aba Config)
- [x] Seção "Dados Históricos" com status chips por fase
- [x] Seletor de período (1–6 meses) e granularidade (Diário / Intraday / Ambos)
- [x] Barra de progresso em tempo real (polling 3s apenas quando `status=running`)
- [x] Cards de resultado: "X inseridos / Y já existiam"
- [x] Estimativa de tempo antes de disparar

### Cobertura de plataformas
| Plataforma | Phase 1 | Phase 2 |
|---|---|---|
| ShineMonitor | ✅ | ✅ |
| Solarman | ✅ | ✅ |
| Growatt | ❌ endpoint não mapeado | ❌ |

---

## 🟢 SPRINT 6 — Manutenção

**Objetivo:** Workflow operacional para equipe técnica.

- [x] Tabela `inverter_maintenance` — tarefas e ordens de serviço (migration aplicada)
- [x] Criar/editar/fechar tarefas vinculadas a um inversor (CRUD completo: GET, POST, PATCH, DELETE)
- [x] Atribuir responsável + prazo
- [x] Status: `pending → in_progress → done | cancelled` (trigger DB auto-preenche `closed_at`)
- [x] Criação automática de tarefa quando alerta crítico abre (`alerts.py` → `_AUTO_MAINTENANCE`)
- [x] Histórico de manutenções por inversor (tab "Manutenção" em InversorDetalhe com filtro Abertas/Fechadas/Todas)
- [x] Badge de OS abertas no card de GestaoInversores
- [x] Badge no tab "Manutenção" com contagem de tarefas abertas
- [x] RLS: `client_id = auth.uid()` (isolamento por tenant)

### Backend
- [x] `backend/routers/maintenance.py` — GET/POST/PATCH/DELETE + endpoint `/inversor/{id}/open-count`
- [x] `backend/integrations/alerts.py` — auto-cria tarefa para `offline`, `high_temp`, `pr_degradation`
- [x] Registrado em `backend/main.py`

### Frontend
- [x] Tab "Manutenção" em `InversorDetalhe.tsx` com formulário de criação, lista filtrável, edição inline
- [x] Badge de contagem no tab e no card de `GestaoInversores.tsx`
- [x] Indicador visual de tarefa atrasada (due_date vencida em vermelho)
- [x] Tarefas geradas por alerta marcadas com `⚠ Gerada por alerta`

---

## ⬜ SPRINT 7 — IA & Insights

**Objetivo:** O sistema explica o que está acontecendo, não só mostra dados.

- [ ] Detecção de anomalias com ML (Isolation Forest ou Z-score adaptativo)
- [ ] Diagnóstico automático em texto: "String 2 produzindo 23% abaixo da média — possível sombra ou sujeira"
- [ ] Previsão de geração para amanhã (modelo simples: média histórica + irradiância prevista)
- [ ] Insights textuais no topo do InversorDetalhe (LLM via Claude)
- [ ] "O que fazer?" — recomendações acionáveis por tipo de problema
- [ ] Integrar com `agente_insights` existente no banco

---

## ⬜ SPRINT 8 — Financeiro Avançado

**Objetivo:** Payback, projeções e perdas acumuladas.

- [ ] Receita acumulada: `E_total × tarifa`
- [ ] Perda acumulada histórica (soma de todos os dias abaixo do previsto)
- [ ] Projeção anual: `E_média_dia × 365`
- [ ] Payback estimado: `investimento / receita_anual`
- [ ] Comparativo custo de energia evitado vs tarifa da concessionária
- [ ] Dashboard financeiro consolidado por tenant

---

## ⬜ SPRINT 9 — Benchmark entre Usinas

**Objetivo:** Ranking e comparativo de performance entre projetos do mesmo cliente.

- [ ] Ranking de PR por usina
- [ ] Ranking de specific yield
- [ ] Mapa com localização das usinas e status visual
- [ ] Comparativo de geração entre usinas (gráfico de barras agrupado)
- [ ] "Usina mais eficiente do portfólio"
- [ ] Benchmark com médias do setor (se disponível via API pública)

---

## ⬜ SPRINT 10 — Melhorias Técnicas & Expansão (Backlog)

**Objetivo:** Dívidas técnicas identificadas em produção + expansão de plataformas.
Itens priorizados por impacto, sem data definida.

### Backfill & Sync
- [ ] **Growatt histórico:** mapear endpoint de histórico por inversor (hoje só há totais de planta via `energyMonthGraphic`)
- [ ] **Phase 2 auto-trigger silencioso:** fila com throttle (ex: 1 inversor por vez, horário noturno) para não concorrer com sync real-time
- [ ] **Semáforo de backfills simultâneos:** limitar N threads de backfill paralelas (hoje ilimitado) — `threading.Semaphore(5)`
- [ ] **Retry com backoff exponencial no sync:** timeouts de API deixam inversor em `error` permanente até próximo ciclo
- [ ] **`_backfill_tasks` multi-worker:** em deploy com múltiplos uvicorn workers, o dict in-memory não é compartilhado; mover estado para banco ou Redis
- [ ] **`_fetch_existing_buckets` coluna seletiva:** hoje faz `SELECT *` para construir set de timestamps; trocar para `SELECT ts` (requer `select` param no `sb_select`)

### Plataformas
- [ ] **Sungrow iSolarCloud:** adapter OAuth2, maior fabricante chinês com presença crescente no BR
- [ ] **Huawei FusionSolar:** adapter OAuth2, market share relevante em utilidades
- [ ] **Solarman 9energia:** ativar sync quando `app_id`/`app_secret` chegarem; backfill automático dos 13 inversores pending

### Dados & Qualidade
- [ ] **Índice único `(inverter_id, ts)`** na tabela `inverter_readings`: previne duplicatas no nível do banco, elimina necessidade de dedup em código para Phase 2
- [ ] **Purge automático de readings antigas:** política de retenção (ex: manter intraday 90 dias, diário 2 anos) para controlar crescimento do banco
- [ ] **Eduardo Porto coords reais:** confirmar lat/lon com cliente e atualizar `plant_meta`

### Analytics & UX
- [ ] **Comparativo ano-a-ano:** requer histórico 12+ meses; exibir na tab Análise (Sprint 5 pendente)
- [ ] **Fator de Potência elétrico:** `PF = P / (V × I)`, disponível apenas em modelos com V+I CA completos
- [ ] **Responsividade mobile completa:** layouts de grid colapsam corretamente em < 375px
- [ ] **Comparativo mini-ranking entre inversores por PR** na GestaoInversores (Sprint 4 pendente)
- [ ] **Notificações push / email:** alertas críticos enviados por email/Slack sem abrir o sistema

---

## Arquitetura Técnica

### Stack
| Camada | Tecnologia |
|---|---|
| Backend | FastAPI (Python) |
| Banco | PostgreSQL via Supabase |
| Sync | asyncio task (10 min) — futuro: Celery + Redis |
| Cache auth | In-memory dict com TTL |
| Frontend | React + Recharts + TanStack Query |
| Auth | Cookie session (FastAPI) |

### Plataformas (padrão horizontal)
| Plataforma | Status | Auth |
|---|---|---|
| ShineMonitor / Eybond | ✅ Produção | SHA-1 sign |
| Solarman / IGEN / Deye | 🟡 Aguardando credenciais | OAuth2 + SHA256 |
| Growatt ShineServer | 🔵 Implementado / sem cliente real | SHA-256 + cookie |
| Sungrow iSolarCloud | ⬜ Futuro | OAuth2 |
| Huawei FusionSolar | ⬜ Futuro | OAuth2 |

### Inversores Cadastrados
| Alias | Plataforma | Status | Dados |
|---|---|---|---|
| Usina Eduardo Porto | ShineMonitor | ✅ active | **40 kW**, 208.493 kWh total, tarifa R$0,80/kWh, instalada 2022-07-03, coords provisórias (Canhotinho/PE) |
| Usina Alvaro Porto | ShineMonitor | ✅ active | **75 kW**, 138.596 kWh total, tarifa R$0,80/kWh, instalada 2025-04-16, Canhotinho PE lat=-8.8765 lon=-36.1979 |
| 9energia — Inversores 01–17 (13x) | Solarman | ⏳ pending | Aguardando app_id/secret |
| Growatt Demo | Growatt | 🔵 mock | Placeholder sem dados reais |

### Pendências de Qualidade de Dados
- **Eduardo Porto coords:** ShineMonitor portal sem endereço cadastrado. Coords temporariamente iguais à Alvaro Porto. Confirmar localização real com cliente (`coords_source: "temp_same_as_alvaro"`).
- **Backfill Sprint 5.1:** Phase 1 roda automaticamente na próxima sync de Eduardo Porto e Alvaro Porto (deduplicação protege dados existentes). Phase 2 requer ação manual na aba Config.

### Pendências de Credenciais
- **Solarman 9energia:** aguardando `app_id` + `app_secret` de `bernardo.veloso@9energia.com`
  - Quando chegar: `PATCH /api/inversores/{id}` com `{"app_id":"...","app_secret":"..."}` para cada um (ou script bulk)
- **Growatt OpenAPI:** solicitar em `openapi.growatt.com` quando surgir primeiro cliente real

---

## Regras de Negócio Críticas

```
PR = E_real / E_prevista

desvio% = (E_real - E_prevista) / E_prevista × 100

perda_R$ = (E_prevista - E_real) × tarifa_kWh
  → só calcular com irradiância válida
  → ignorar potência < 5 W (período noturno)

desbalanceamento_string = (max_string - min_string) / média_strings
  → ignorar strings com potência < 10% da máxima
  → alertar se desvio > 15%
```

### Padronização de Unidades
| Grandeza | Unidade | Casas decimais |
|---|---|---|
| Potência | kW | 1 |
| Energia | kWh | 1 |
| Moeda | R$ | 2 |
| Performance Ratio | — | 3 |
| Temperatura | °C | 1 |
| Frequência | Hz | 2 |
| Data | dd/mm/aaaa | — |
