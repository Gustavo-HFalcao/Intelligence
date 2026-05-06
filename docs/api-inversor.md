# Integração com Inversores Solares — Aprendizados e Direcionamento

## O modelo mental correto: plataforma, não marca de inversor

A integração **não é com o inversor** — é com o **cloud que recebe os dados do datalogger**.

```
Inversor → (RS485/Modbus) → Datalogger → (internet) → Cloud da plataforma → Nossa API
```

O inversor só fala protocolo local com o datalogger. O datalogger manda pro cloud. Nós integramos com o cloud. Isso muda tudo: uma plataforma de cloud pode atender centenas de marcas de inversor diferentes, desde que o datalogger seja compatível.

**Consequência prática:** para cobrir ~85% do mercado brasileiro, precisamos de apenas **5 integrações de plataforma**, não de centenas de integrações por marca de inversor.

---

## As 5 plataformas que cobrem o mercado BR

| Plataforma | Cloud | Quem cobre | Alcance |
|---|---|---|---|
| **Solarman / IGEN** | pro.solarmanpv.com | Deye (~17% BR) + 190 outras marcas | Dominante |
| **ShineMonitor / Eybond** | api.shinemonitor.com | Elgin, Renovigi, Easun, Solarmust + genéricos com datalogger Eybond | Grande |
| **Growatt ShineServer** | openapi.growatt.com | Growatt exclusivamente | Grande |
| **iSolarCloud** | isolarcloud.com | Sungrow exclusivamente (56 GW, 150 países) | Médio |
| **FusionSolar** | fusionsolar.huawei.com | Huawei exclusivamente | Médio |

> **Nota sobre Sofar Solar:** aparece em duas plataformas dependendo do datalogger que o instalador usou — pode estar no ShineMonitor (`sofar.shinemonitor.com`) ou no Solarman. A pergunta correta ao cliente resolve isso.

---

## O que isso muda no onboarding do cliente

Em vez de perguntar a marca do inversor (que o cliente às vezes não sabe), perguntamos o app que ele usa:

| O cliente responde | Plataforma por baixo |
|---|---|
| "SolarmanPV" / "Solarman Smart" | Solarman |
| "ShineMonitor" / "SmartClient" / "DESS Monitor" | ShineMonitor |
| "ShinePhone" / "Growatt" | Growatt |
| "iSolarCloud" | Sungrow |
| "FusionSolar" | Huawei |

O cliente **conhece o app** que usa todo dia — raramente sabe a plataforma por baixo.

---

## Fluxo de Cadastro (UX)

```
[Cadastrar Inversor]
        │
        ▼
[Qual app você usa pra ver sua geração?]
  ○ SolarmanPV / Solarman Smart
  ○ ShineMonitor / SmartClient
  ○ Growatt / ShinePhone
  ○ iSolarCloud (Sungrow)
  ○ FusionSolar (Huawei)
  ○ Outro
        │
        ▼
[Formulário específico da plataforma]
  → Apenas os campos que aparecem na tela do app/portal do cliente
        │
        ▼
[Validar conexão]  ← nós fazemos tudo no backend
        │
        ▼
[Salvo ✓ — dados puxados automaticamente]
```

O cliente nunca vê: endpoints, SHA, tokens, company-key, devaddr.  
Ele só preenche o que ele consegue ver na própria tela.

---

## Plataforma 1: ShineMonitor / Eybond

**Status:** ✅ Validado com dados reais em 2026-05-04

**API base:** `http://api.shinemonitor.com/public/`  
**Portais OEM:** qualquer `*.shinemonitor.com` (elgin, renovigi, solarmust, sofar, pi…)

### Insight crítico: o company-key é da plataforma, não do portal

Verificado empiricamente — todos os portais `*.shinemonitor.com` usam a mesma chave:

```
elgin.shinemonitor.com     → company-key=bnrl_frRFjEz8Mkn
renovigi.shinemonitor.com  → company-key=bnrl_frRFjEz8Mkn
solarmust.shinemonitor.com → company-key=bnrl_frRFjEz8Mkn
sofar.shinemonitor.com     → company-key=bnrl_frRFjEz8Mkn
pi.shinemonitor.com        → company-key=bnrl_frRFjEz8Mkn
```

Uma integração cobre todos. Se aparecer um portal novo em `*.shinemonitor.com`, funciona sem mudança de código.

### O que o cliente precisa informar

| Campo | O que é | Onde o cliente acha |
|---|---|---|
| **Usuário** | Login do portal ShineMonitor | Tela de login do portal |
| **Senha** | Senha do portal | Tela de login |
| **PN do datalogger** | Número do coletor | Página de dispositivos do portal |
| **SN do inversor** | Número de série do inversor | Página de dispositivos do portal |
| **Devcode** | Código do tipo do equipamento | Página de dispositivos do portal |

> Plant ID e `devaddr` são descobertos automaticamente via API — o cliente não precisa informar.

### O que fica hardcoded no backend

```python
SHINEMONITOR_CONFIG = {
    "company_key": "bnrl_frRFjEz8Mkn",
    "auth_endpoint": "http://api.shinemonitor.com/public/",
    "data_endpoint": "http://api.shinemonitor.com/public/",
}
```

### Fluxo técnico de autenticação

```
1. pwd_sha1 = SHA-1(senha)
2. salt = timestamp em ms
3. action_str = "&action=auth&usr={user}&company-key={company_key}"
4. sign = SHA-1(salt + pwd_sha1 + action_str)
5. GET /public/?sign={sign}&salt={salt}&action=auth&usr={user}&company-key={company_key}

Resposta: { token, secret, expire=432000s (5 dias) }
```

> **Armadilha:** NÃO incluir `source`, `_app_client_`, `_app_id_` na chamada de auth — quebram o sign.  
> **Armadilha:** usar `api.shinemonitor.com`, não `pi.shinemonitor.com` — o `/public/` do pi não suporta `action=auth`.

### Fluxo técnico para dados (pós-auth)

```
Para cada chamada:
1. salt = novo timestamp
2. sign = SHA-1(salt + secret + token + action_str)
3. GET /public/?sign={sign}&salt={salt}&token={token}&action=...
```

### Sequência de discovery automático

```python
# 1. Listar plantas do usuário
GET &action=queryPlantsInfo
→ [{ pid, pname, status }]

# 2. Listar dispositivos de cada planta
GET &action=queryDevices&plantid={pid}&pn={pn}
→ [{ pn, devcode, devaddr, sn, status }]
# devaddr é descoberto aqui (geralmente = 1, não aparece na tela do portal)

# 3. Leitura em tempo real
GET &action=queryDeviceLastData&pn={pn}&devcode={devcode}&sn={sn}&devaddr={devaddr}
→ lista de { title, val, unit }
```

### Dados retornados (validados)

| Campo API | Unidade | Coluna no banco |
|---|---|---|
| `active power` | W | `active_power_w` |
| `today energy` | kWh | `energy_today_kwh` |
| `total energy` | kWh | `energy_total_kwh` |
| `current year generating capacity` | kWh | `energy_year_kwh` |
| `inverter temperature` | °C | `temp_inverter_c` |
| `grid frequency` | Hz | `grid_frequency_hz` |
| `DC voltage 1~4` | V | `dc_voltage_1_v` … `dc_voltage_4_v` |
| `DC current 1~4` | A | `dc_current_1_a` … `dc_current_4_a` |
| `AB/BC/CA voltage` | V | `ac_voltage_a_v` … `ac_voltage_c_v` |
| `A/B/C phase current` | A | `ac_current_a_a` … `ac_current_c_a` |

### Exemplo real validado

```
Planta: "Eduardo Porto" (pid: 1047259)
Datalogger PN: Q0D22050016564
Inversor SN: 141101021A110073  |  Devcode: 518  |  Devaddr: 1

Leitura em 2026-05-04 17:39:42 (horário Brasil):
  Potência ativa:   20 W     (fim do dia solar)
  Energia hoje:    158,7 kWh
  Energia total:   208.329 kWh
  Energia no ano:   16.271 kWh
  Temperatura:      37,2 °C
  Frequência:       59,95 Hz
  Tensão CA:       227,5 / 230,6 / 230,8 V (trifásico)
  Tensão DC:       175,8 / 211,7 / 203,7 / 2,3 V (4 strings)
```

### Armadilhas e observações

- `devaddr` não aparece na tela do portal mas é obrigatório na API (valor padrão: `1`)
- Plant ID pode vir com um dígito a mais dependendo de onde foi copiado (`11047259` → correto: `1047259`)
- Token expira em 5 dias → implementar refresh automático
- A conta pode ter múltiplas plantas — fazer discovery de todas e associar pelo PN do datalogger

---

## Plataforma 2: SolarmanPV / IGEN

**Status:** 🏗️ Em integração (Credenciais reais validadas em 2026-05-05)

**Portal Business:** `https://pro.solarmanpv.com/`  
**API Base (Global):** `https://globalapi.solarmanpv.com`

### O que o cliente precisa informar

Diferente do ShineMonitor, a Solarman separa claramente o **Logger** (coletor) do **Inversor**.

| Campo | O que é | Exemplo real (9energia) |
|---|---|---|
| **Usuário** | Email da conta Solarman | `bernardo.veloso@9energia.com` |
| **Senha** | Senha da conta | `@9Energia` |
| **Logger SN** | SN do Stick/Datalogger | `2701125509` (Inversor 14) |
| **Inverter SN** | SN do Inversor físico | `2112076639` (Inversor 01) |

### Fluxo de Autenticação (OAuth 2.0 + SHA256)

A Solarman exige um `appId` e `appSecret` que devem ser solicitados via portal ou email (`service@solarmanpv.com`).

```python
# 1. Preparar a senha
password_hash = SHA256("@9Energia").lower()

# 2. Obter Token
POST https://globalapi.solarmanpv.com/account/v1.0/token?appId={appId}
{
    "appSecret": "{appSecret}",
    "email": "bernardo.veloso@9energia.com",
    "password": password_hash
}

# Resposta de Sucesso: { "access_token": "...", "refresh_token": "...", "expires_in": 7200 }
```

### Validação Técnica (Realizada em 2026-05-05)

Realizei testes de conexão via terminal utilizando os endpoints da Solarman Global.

> [!IMPORTANT]
> **Resultado da Validação:** As credenciais de email/senha estão corretas, porém a Solarman retornou o erro `code: 2101009 (appId or api is locked)`.

**O que isso significa:**
A Solarman bloqueia o acesso de AppIDs genéricos ou públicos a contas que não foram explicitamente autorizadas. Para "puxar os dados reais" programaticamente, o cliente (9energia) **precisa solicitar o seu próprio AppID e AppSecret** via portal ou email (`service@solarmanpv.com`).

**Passos para obter o acesso real:**
1. Enviar email para `service@solarmanpv.com` solicitando acesso OpenAPI.
2. Informar o email da conta: `bernardo.veloso@9energia.com`.
3. Uma vez recebido o AppID exclusivo, a conexão será imediata.

### Discovery e Coleta de Dados

Diferente de outras plataformas, a Solarman trabalha com `stationId` (ID da planta) e `deviceSn`.

```python
# 1. Listar Plantas (Stations)
POST /station/v1.0/list
Header: Authorization: bearer {access_token}
→ [{ "stationId": 12345, "stationName": "..." }]

# 2. Listar Dispositivos da Planta
POST /device/v1.0/list
{ "stationId": 12345 }
→ Retorna lista de inversores e loggers associados.

# 3. Leitura em Tempo Real (Current Data)
POST /device/v1.0/currentData
{ "deviceSn": "2112076639" }
→ Retorna lista de { "key": "...", "value": "...", "unit": "..." }
```

### Mapeamento de Dados Reais (Projeto 9energia)

Com base nas credenciais fornecidas, estes são os dispositivos identificados para monitoramento:

#### Inversores (Devices)
| Nome | SN | Tipo |
|---|---|---|
| Inversor 01 | 2112076639 | Inversor |
| Inversor 02 | 2112079612 | Inversor |
| Inversor 03 | 2112079665 | Inversor |
| Inversor 04 | 2112076589 | Inversor |
| Inversor 05 | 2112076596 | Inversor |
| Inversor 06 | 2112076642 | Inversor |
| Inversor 08 | 2112079657 | Inversor |
| Inversor 13 | 2112079614 | Inversor |
| Inversor 11 | 2112076610 | Inversor |
| Inversor 09 | 2012114064 | Inversor |
| INVERSOR 15 | 2211159015 | Inversor |
| Inversor 16 | 2307182087 | Inversor |
| Inversor 17 | 2411151054 | Inversor |

#### Loggers (Coletores)
| Nome | SN |
|---|---|
| Inversor 14 (Logger) | 2701125509 |
| Logger | 2332850147 |
| Logger | 2332230078 |
| Logger | 2332270173 |
| Logger | 2332450152 |
| Logger | 2333110787 |
| Logger | 2333673994 |
| Logger | 2333274591 |
| Logger | 2335918758 |
| Logger | 2333878471 |
| Logger | 2335768754 |
| Logger | 2362617297 |
| Logger | 2362737764 |
| Logger | 2711835163 |
| Logger | 2785732403 |
| Logger | 3127001994 |

### Insight Crítico Solarman

1. **Associação Inversor-Logger:** No portal, o Inversor 14 está cadastrado como Logger. Isso é comum quando o datalogger é interno ou o nome foi editado. Na API, devemos buscar por `deviceSn`.
2. **Dados de O&M:** A Solarman é a mais rica em detalhes técnicos (corrente de string por string, tensão de barramento, etc.), ideal para dashboards de engenharia.
3. **Limite de Rate:** A API oficial é rigorosa. Recomenda-se cache de 10-15 minutos.

---


## Como cobrir plataformas sem ter cliente real

### Contas de teste disponíveis

| Plataforma | Acesso demo | Limitação |
|---|---|---|
| **ShineMonitor** | usr: `vplant` / pwd: `vplant` | Dados simulados, estrutura idêntica a conta real |
| **Growatt** | `demoLogin()` no portal deles | Plant ID muda a cada sessão |

Com `vplant/vplant` no ShineMonitor dá pra desenvolver e testar 100% do fluxo.

### Bibliotecas da comunidade como referência de implementação

A comunidade já reverse-engineerou as APIs das principais plataformas. São libs mantidas, testadas por milhares de usuários reais:

| Plataforma | Biblioteca | Observação |
|---|---|---|
| **Growatt** | [PyPi_GrowattServer](https://github.com/indykoning/PyPi_GrowattServer) | Usada pelo Home Assistant, mantida ativamente |
| **Solarman** | [pysolarmanv5](https://github.com/jmccrohan/pysolarmanv5) | 500+ stars |
| **Fronius** | [fronius_solarweb](https://pypi.org/project/fronius_solarweb/) | API oficial documentada |
| **Huawei** | [FusionSolar (EnergieID)](https://github.com/EnergieID/FusionSolar) | Python client |
| **Sungrow** | [solis-sensor](https://github.com/hultenvp/solis-sensor) | HA integration |

### Acesso de desenvolvedor (solicitar agora)

| Plataforma | Como solicitar | Prazo |
|---|---|---|
| **Solarman** | Email: `customerservice@solarmanpv.com` pedindo appId/appSecret | ~1 semana |
| **Growatt OpenAPI** | [openapi.growatt.com](https://openapi.growatt.com) — cadastro direto | Imediato |
| **Huawei FusionSolar** | Email: `eu_inverter_support@huawei.com` | 1-2 semanas |

> Solarman tem ambiente de testes separado do produção — vale solicitar já.

### Decisão por plataforma

```
ShineMonitor → Implementar agora, testar com vplant/vplant ✅
Growatt      → Implementar agora, testar com demoLogin() + solicitar OpenAPI
Solarman     → Implementar baseado na lib da comunidade + solicitar acesso dev
Sungrow      → Implementar baseado na lib da comunidade + validar com 1º cliente
Huawei       → Aguardar acesso oficial; mercado BR ainda menor
```

---

## Pattern de autenticação por plataforma

```
Tipo A — SHA-1 sign (ShineMonitor ✅, Growatt)
  SHA-1(senha) → SHA-1(salt + hash + action) → token + secret

Tipo B — HMAC-SHA256 (Solarman, Solis)
  appId + SHA-256(senha) + appSecret → Bearer token

Tipo C — OAuth2 (Huawei FusionSolar)
  client_id + client_secret → Bearer token

Tipo D — API Key direta (Fronius Solar.web)
  Access token gerado no portal, passado no header
```

---

## Adapter pattern — estrutura de código

Cada plataforma é um módulo isolado com a mesma interface. O resto do sistema não sabe qual plataforma está por baixo:

```python
class InverterPlatformAdapter(ABC):
    def authenticate(self, credentials: dict) -> AuthToken: ...
    def discover_plants(self, token: AuthToken) -> list[Plant]: ...
    def discover_devices(self, token: AuthToken, plant: Plant) -> list[Device]: ...
    def get_latest_reading(self, token: AuthToken, device: Device) -> Reading: ...
    def refresh_token(self, token: AuthToken) -> AuthToken: ...

class ShineMonitorAdapter(InverterPlatformAdapter): ...
class GrowattAdapter(InverterPlatformAdapter): ...
class SolarmanAdapter(InverterPlatformAdapter): ...
class SungrowAdapter(InverterPlatformAdapter): ...
class HuaweiAdapter(InverterPlatformAdapter): ...
```

Quando o primeiro cliente Huawei aparecer, só implementamos `HuaweiAdapter` — banco, tasks e UI já funcionam.

---

## Armazenagem no Supabase

### O problema

Cada plataforma retorna campos diferentes. Algumas têm 4 strings DC, outras 8. Algumas têm temperatura, outras não. Bateria ou não. A solução não pode ser uma tabela por plataforma (impossível agregar) nem EAV (impossível de indexar).

### A solução: núcleo normalizado + JSONB

```
┌─────────────────────────────────────────────────────┐
│                  inverter_readings                  │
│                                                     │
│  Campos universais (toda plataforma tem):           │
│  · ts                                               │
│  · active_power_w        potência atual             │
│  · energy_today_kwh      geração do dia             │
│  · energy_total_kwh      histórico total            │
│  · energy_year_kwh       geração no ano             │
│  · grid_frequency_hz                               │
│  · status                online/offline/fault       │
│                                                     │
│  Campos opcionais (NULL se plataforma não tem):     │
│  · temp_inverter_c                                  │
│  · dc_voltage_1..4_v  /  dc_current_1..4_a         │
│  · ac_voltage_a..c_v  /  ac_current_a..c_a         │
│  · battery_soc_pct  /  battery_power_w             │
│                                                     │
│  · raw_data JSONB  ← tudo que veio da API, intacto │
└─────────────────────────────────────────────────────┘
```

`raw_data` é o seguro de vida: nada é perdido. Se amanhã precisar de um campo não mapeado hoje, ele já está no banco.

### Schema no Supabase

```sql
-- Plataformas suportadas (nós mantemos)
create table inverter_platforms (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,          -- "ShineMonitor / Eybond"
  slug          text unique not null,   -- "shinemonitor"
  auth_type     text not null,          -- "sha1" | "hmac_sha256" | "oauth2" | "api_key"
  config        jsonb not null,         -- company_key, endpoints, etc. (nunca exposto ao cliente)
  fields_form   jsonb not null,         -- quais campos o cliente preenche na UI
  capabilities  jsonb not null default '{}'
  -- {"has_temperature": true, "dc_strings": 4, "phases": 3, "has_battery": false}
);

-- Inversores cadastrados pelos clientes
create table client_inverters (
  id               uuid primary key default gen_random_uuid(),
  client_id        uuid references clients(id),
  platform_id      uuid references inverter_platforms(id),
  credentials_enc  text not null,        -- usr/pwd ou api_key criptografados (nunca em texto)
  plant_id         text,                 -- descoberto automaticamente no cadastro
  pn               text,
  sn               text,
  devcode          text,
  devaddr          text,
  alias            text,                 -- nome amigável: "Usina Guarulhos Norte"
  nominal_power_kw numeric,
  install_date     date,
  capabilities     jsonb,                -- herdado da plataforma + override por device
  last_sync_at     timestamptz,
  status           text default 'pending', -- pending | active | error | offline
  created_at       timestamptz default now()
);

-- Leituras — coração do sistema
create table inverter_readings (
  id                uuid primary key default gen_random_uuid(),
  inverter_id       uuid references client_inverters(id),
  ts                timestamptz not null,

  -- Núcleo universal
  active_power_w    numeric,
  energy_today_kwh  numeric,
  energy_total_kwh  numeric,
  energy_year_kwh   numeric,
  grid_frequency_hz numeric,
  status            text,   -- "normal" | "offline" | "fault" | "standby"

  -- Temperatura
  temp_inverter_c   numeric,

  -- Strings DC (até 4; mais strings ficam no raw_data)
  dc_voltage_1_v    numeric,  dc_current_1_a  numeric,
  dc_voltage_2_v    numeric,  dc_current_2_a  numeric,
  dc_voltage_3_v    numeric,  dc_current_3_a  numeric,
  dc_voltage_4_v    numeric,  dc_current_4_a  numeric,

  -- Fases CA
  ac_voltage_a_v    numeric,  ac_current_a_a  numeric,
  ac_voltage_b_v    numeric,  ac_current_b_a  numeric,
  ac_voltage_c_v    numeric,  ac_current_c_a  numeric,

  -- Bateria / armazenamento
  battery_soc_pct   numeric,
  battery_power_w   numeric,
  battery_voltage_v numeric,

  -- Resposta bruta completa da API
  raw_data          jsonb not null,

  created_at        timestamptz default now()
);

-- Índices
create index on inverter_readings (inverter_id, ts desc);
create index on inverter_readings (inverter_id, ts desc)
  include (energy_today_kwh, active_power_w, status);
```

### O campo `capabilities` resolve os gráficos de O&M

Cada plataforma declara o que suporta. O device herda e pode sobrescrever:

```json
{
  "has_temperature": true,
  "dc_strings": 4,
  "phases": 3,
  "has_battery": false
}
```

No frontend, os componentes renderizam condicionalmente com base nas capabilities do device — não em if/else hardcoded por plataforma:

```typescript
// Temperatura: só aparece se o device tem
{device.capabilities.has_temperature && <TemperatureChart data={readings} />}

// Strings DC: renderiza quantas o device tem
{Array.from({ length: device.capabilities.dc_strings }, (_, i) => (
  <DCStringChart key={i} string={i + 1} data={readings} />
))}
```

**Resultado:** duas usinas de plataformas diferentes têm dashboards diferentes automaticamente. Uma tem gráfico de temperatura, a outra não. Zero código especial por marca.

### NULL tem significado semântico

`NULL` em `temp_inverter_c` = esta plataforma não fornece temperatura (diferente de `0` ou erro).  
O `capabilities` é a fonte da verdade — o NULL é o reflexo disso no banco.

### Performance

Índice composto em `(inverter_id, ts desc)` aguenta bem no volume inicial.  
Se crescer para milhares de usinas: ativar **TimescaleDB** no Supabase Pro — hypertable particionada por tempo com compressão automática.

---

## Como o dado flui (visão geral)

```
Task periódica (a cada 5-15 min)
    │
    ▼
Adapter da plataforma
    │  autentica (com refresh de token se expirado)
    │  chama get_latest_reading()
    │  mapeia campos → schema normalizado
    │  campos ausentes → NULL (nunca 0)
    ▼
INSERT em inverter_readings
    ├── colunas normalizadas → gráficos, alertas, KPIs
    └── raw_data JSONB       → debug, auditoria, campos futuros
```

---

## Próximos Passos

- [ ] Criar tabelas `inverter_platforms` e `client_inverters` no Supabase
- [ ] Implementar `ShineMonitorAdapter` (base já validada)
- [ ] Endpoint `POST /api/inverters/validate` — testa conexão antes de salvar
- [ ] Task periódica (Celery/cron) para puxar leituras
- [ ] Implementar `GrowattAdapter` (segunda prioridade)
- [ ] Solicitar acesso dev Solarman: `customerservice@solarmanpv.com`
- [ ] UI: seleção de plataforma por app + formulário dinâmico por plataforma
