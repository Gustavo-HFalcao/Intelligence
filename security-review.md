# Security Review — Bomtempo Intelligence Backend
**Data:** 2026-05-04  
**Escopo:** nginx.conf, backend/main.py, backend/core/config.py, backend/routers/auth.py, .env.example

---

## Resumo executivo

9 pontos auditados. **1 inválido** (account enumeration já está resolvido no código). **8 válidos**, sendo 2 críticos reais, 3 médios e 3 baixos. Os dois críticos reais envolvem cookie `secure=False` em produção e ausência total de headers de segurança no nginx — ambos com fix simples.

---

## Tasklist

### Críticos
- [x] **C1** — Setar `secure=True` no cookie de sessão (`auth.py:81`)
- [x] **C2** — Adicionar headers de segurança no nginx (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)

### Médios
- [x] **M1** — Mudar cookie `samesite` de `lax` para `strict` (`auth.py:79`)
- [x] **M2** — Corrigir `APP_URL` no `.env.example` para HTTPS e garantir isso em produção
- [x] **M3** — Restringir `allow_methods` e `allow_headers` no CORSMiddleware (`main.py:44-45`)

### Baixos
- [x] **B1** — Bloquear método TRACE no nginx
- [x] **B2** — Adicionar `server_tokens off;` no nginx
- [x] **B3** — Fixar versão da imagem nginx no Dockerfile/docker-compose

### Descartado
- [x] ~~Account enumeration~~ — já resolvido: login usa mensagem genérica, reset retorna 200 sempre

---

## Detalhamento

---

### C1 — Cookie de sessão: `secure=False` em produção
**Impacto: CRÍTICO | Complexidade: TRIVIAL (1 linha)**

**Confirmado em** `backend/routers/auth.py:81`:
```python
secure=False,  # True em produção (HTTPS)
```

O comentário indica intenção mas o valor nunca foi alterado. Com `secure=False`, o cookie de sessão é enviado também em requisições HTTP, expondo o token de sessão a interceptação em redes não criptografadas (man-in-the-middle).

**Fix:**
```python
# backend/routers/auth.py
response.set_cookie(
    key=SESSION_COOKIE,
    value=session_id,
    httponly=True,
    samesite="strict",       # C1 + M1 juntos
    max_age=60 * 60 * 24 * 7,
    secure=True,             # ← trocar isso
)
```

> Fazer junto com M1 (samesite).

---

### C2 — Headers de segurança ausentes no nginx
**Impacto: CRÍTICO | Complexidade: BAIXA (bloco de config)**

**Confirmado em** `nginx.conf`: zero `add_header` de segurança no bloco 443. O único `add_header` existente é de cache no bloco `index.html`.

Ausências e seus riscos:
| Header | Risco sem ele |
|---|---|
| `Strict-Transport-Security` | Downgrade HTTP/HTTPS possível |
| `Content-Security-Policy` | XSS sem barreira de segundo nível |
| `X-Frame-Options` | Clickjacking |
| `X-Content-Type-Options` | MIME sniffing pelo browser |
| `Referrer-Policy` | Vazamento de URL em requests externos |

**Fix — adicionar no bloco `server` 443 do nginx.conf:**
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://*.supabase.co;" always;
```

> CSP vai exigir ajuste iterativo — começar com `Content-Security-Policy-Report-Only` para não quebrar o frontend.

---

### M1 — Cookie `samesite="lax"` em vez de `strict`
**Impacto: MÉDIO | Complexidade: TRIVIAL (1 palavra)**

**Confirmado em** `backend/routers/auth.py:79`: `samesite="lax"`.

`Lax` bloqueia POST cross-site vindo de formulários de terceiros (mitiga CSRF básico), mas permite requisições GET cross-site carregando o cookie — e não bloqueia requisições que partem de navegação top-level. `Strict` corta o cookie em absolutamente toda navegação cross-site.

Como o app é um painel interno (não depende de link externo que precise carregar sessão), `strict` não quebra UX.

**Fix:** `samesite="strict"` na linha 79 e no `delete_cookie` do logout (`auth.py:115`). Fazer junto com C1.

---

### M2 — APP_URL com HTTP em `.env.example` e config.py
**Impacto: MÉDIO | Complexidade: BAIXA (config)**

`.env.example` define `APP_URL=http://IP_DA_VM:8080`. `Config.py` usa esta variável para gerar links de reset de senha enviados por e-mail. Se em produção a variável não for sobrescrita para HTTPS, os links de reset chegam como `http://` — bloqueados por browsers modernos em contexto HTTPS (mixed content) e inúteis para o usuário.

**Fix:**
- `.env.example`: `APP_URL=https://34.95.186.98.nip.io`
- Adicionar validação no startup que avise se `APP_URL` começa com `http://` em ambiente com HTTPS ativo

---

### M3 — CORS: `allow_methods=["*"]` e `allow_headers=["*"]`
**Impacto: MÉDIO-BAIXO | Complexidade: BAIXA**

**Confirmado em** `backend/main.py:44-45`. As origens estão corretas (lista explícita, não wildcard), então o risco principal de CORS está mitigado. Mas `allow_methods=["*"]` expõe métodos que o app não usa (TRACE, OPTIONS além do preflight, CONNECT) e `allow_headers=["*"]` permite headers arbitrários, o que pode facilitar bypass de validações futuras.

**Fix:**
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
```

---

### B1 — Método TRACE não bloqueado no nginx
**Impacto: BAIXO | Complexidade: TRIVIAL**

O nginx faz proxy de todos os métodos HTTP sem filtro. TRACE é usado em ataques XST (Cross-Site Tracing) — se habilitado, pode ser usado para roubar cookies HttpOnly via script em contextos específicos.

**Fix — adicionar no bloco `/api/`:**
```nginx
if ($request_method !~ ^(GET|POST|PUT|DELETE|PATCH|OPTIONS)$) {
    return 405;
}
```

---

### B2 — `server_tokens` habilitado (fingerprinting)
**Impacto: BAIXO | Complexidade: TRIVIAL**

O nginx anuncia versão exata no header `Server: nginx/1.x.x`. Não é vetor de ataque direto, mas facilita reconhecimento de versão com vulnerabilidades conhecidas.

**Fix — adicionar no bloco `http` (ou no topo do server block):**
```nginx
server_tokens off;
```

---

### B3 — Imagem nginx sem versão fixa
**Impacto: BAIXO | Complexidade: TRIVIAL**

`nginx:alpine` sem tag de versão — cada `docker pull` pode trazer uma versão diferente, causando comportamento inconsistente entre ambientes.

**Fix:** `nginx:1.27-alpine` (ou versão LTS corrente).

---

### DESCARTADO — Account enumeration
**Status: já resolvido no código**

- `POST /api/auth/login` → retorna `"Credenciais inválidas"` para qualquer falha (auth.py:61)
- `POST /api/auth/reset-request` → retorna `{"ok": True}` mesmo quando e-mail não existe (auth.py:141)
- Reset não expõe diferença de timing visível (consulta ao banco é feita antes do retorno antecipado só quando e-mail não existe)

Sem ação necessária.

---

## Ordem de execução recomendada

| # | Item | Arquivo | Esforço estimado |
|---|---|---|---|
| 1 | C1 + M1 | `auth.py:79-81` | 2 min |
| 2 | C2 | `nginx.conf` | 15 min (CSP iterativo) |
| 3 | M2 | `.env.example` | 2 min |
| 4 | B1 + B2 + B3 | `nginx.conf`, `Dockerfile` | 5 min |
| 5 | M3 | `main.py` | 5 min |
