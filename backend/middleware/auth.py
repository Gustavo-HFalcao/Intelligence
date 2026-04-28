"""
Auth middleware — Bomtempo Backend (FastAPI)
Portado de bomtempo/core/auth_utils.py + lógica de check_login do GlobalState.

Fornece:
- verify_password()   — PBKDF2 verify (3 formatos, backwards compat)
- hash_password()     — PBKDF2 hash (novo padrão)
- get_current_user()  — FastAPI Dependency: lê sessão do cookie
- require_role()      — FastAPI Dependency factory: verifica role do usuário
- login_user()        — autentica credenciais e cria sessão
"""

import hashlib
import hmac
import json
import os
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status

from backend.integrations.supabase import sb_select

SESSION_COOKIE = "bomtempo_session"
_SESSION_TTL   = 60 * 60 * 24 * 7  # 7 dias

# ── Sessão via Redis (funciona com múltiplos workers) ─────────────────────────
def _get_redis():
    import redis as redis_lib
    from backend.core.config import Config
    return redis_lib.from_url(Config.REDIS_URL, decode_responses=True)


def _session_key(sid: str) -> str:
    return f"session:{sid}"

# ── Password hashing (PBKDF2-HMAC-SHA256) ─────────────────────────────────────
# Portado integralmente de bomtempo/core/auth_utils.py — sem alteração de lógica.

_ITERATIONS = 260_000
_HASH_NAME = "sha256"
_PREFIX = "pbkdf2:sha256"


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS)
    return f"{_PREFIX}:{_ITERATIONS}${salt}${dk.hex()}"


def verify_password(stored: str, provided: str) -> bool:
    if not stored:
        return False

    # PBKDF2 novo formato
    if stored.startswith("pbkdf2:"):
        try:
            _, algo, rest = stored.split(":", 2)
            iters_s, salt, stored_hash = rest.split("$", 2)
            dk = hashlib.pbkdf2_hmac(algo, provided.encode("utf-8"), salt.encode("utf-8"), int(iters_s))
            return hmac.compare_digest(dk.hex(), stored_hash)
        except (ValueError, KeyError):
            return False

    # SHA256:salt formato antigo
    if ":" in stored:
        try:
            salt, stored_hash = stored.split(":", 1)
            if len(stored_hash) == 64:
                candidate = hashlib.sha256((provided + salt).encode()).hexdigest()
                return hmac.compare_digest(candidate, stored_hash)
        except (ValueError, AttributeError):
            return False

    # Texto plano (desenvolvimento)
    return stored == provided


# ── Autenticação ───────────────────────────────────────────────────────────────

def login_user(username: str, password: str) -> Optional[dict]:
    """Verifica credenciais. Lógica idêntica ao check_login() do GlobalState Reflex."""
    val = username.strip()
    
    # 1. Busca usuário (ilike para ignorar case no email/user)
    rows = sb_select("login", raw_filters={"or": f"(username.ilike.{val},email.ilike.{val})"}, limit=1)
    
    if not rows:
        return None
    
    user = rows[0]

    # 2. Identifica campo de senha e valida (mesma prioridade do Reflex)
    stored = ""
    for key in ("pw_hash", "password", "senha", "pass", "pwd"):
        p_val = user.get(key)
        if p_val is not None:
            stored = str(p_val).strip()
            break

    if not verify_password(stored, password):
        return None



    # 3. Identifica Role (mesma prioridade do Reflex)
    role_name = "Visitante"
    for key in ("user_role", "role", "permissao", "perfil"):
        r_val = user.get(key)
        if r_val is not None:
            role_name = str(r_val).strip()
            break

    client_id = user.get("client_id")
    client_name = ""
    is_master = False
    allowed_modules = []

    # 4. Busca info do Cliente (Paridade 1:1)
    if client_id:
        clients = sb_select("clients", filters={"id": client_id}, limit=1)
        if clients:
            client_name = str(clients[0].get("name", ""))
            is_master = bool(clients[0].get("is_master", False))

    # 5. Busca Permissões do Role (Paridade 1:1)
    # No backend, o formatador de permissões do Reflex é simplificado aqui
    landing_page = ""
    try:
        role_rows = sb_select("roles", filters={"name": role_name, "client_id": client_id})
        if role_rows:
            allowed_modules = list(role_rows[0].get("modules", []))
            landing_page    = str(role_rows[0].get("landing_page") or "")
    except Exception as e:
        print(f"DEBUG AUTH: Erro ao buscar permissões: {e}")

    # Retorna o dict completo idêntico ao que o Reflex guarda no State
    return {
        "user_id":        user.get("id"),
        "login":          str(user.get("username") or user.get("user") or val),
        "email":          str(user.get("email") or ""),
        "client_id":      client_id,
        "client_name":    client_name,
        "role_name":      role_name,
        "is_master":      is_master,
        "allowed_modules": allowed_modules,
        "landing_page":   landing_page,
        "avatar_icon":    str(user.get("avatar_icon") or ""),
        "avatar_type":    str(user.get("avatar_type") or "initial"),
        "whatsapp":       str(user.get("whatsapp") or ""),
        "project":        str(user.get("project") or ""),
    }


def create_session(user_data: dict) -> str:
    """Cria sessão no Redis, retorna session_id."""
    session_id = os.urandom(32).hex()
    try:
        r = _get_redis()
        r.setex(_session_key(session_id), _SESSION_TTL, json.dumps(user_data))
    except Exception:
        # fallback em memória se Redis indisponível
        _fallback[session_id] = user_data
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    try:
        r = _get_redis()
        raw = r.get(_session_key(session_id))
        if raw:
            return json.loads(raw)
    except Exception:
        return _fallback.get(session_id)
    return _fallback.get(session_id)


def destroy_session(session_id: str) -> None:
    try:
        r = _get_redis()
        r.delete(_session_key(session_id))
    except Exception:
        pass
    _fallback.pop(session_id, None)


_fallback: dict[str, dict] = {}


# ── FastAPI Dependencies ───────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict:
    """Dependency: lê usuário da sessão. Lança 401 se não autenticado."""
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    user = get_session(session_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada")
    return user


def require_role(*roles: str):
    """Dependency factory: verifica se o usuário tem um dos roles especificados.

    Uso:
        @router.get("/admin", dependencies=[Depends(require_role("Administrador"))])
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role_name") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Roles permitidos: {', '.join(roles)}",
            )
        return user
    return _check


def require_master():
    """Dependency: exige que o usuário seja do tenant master (Administrador global)."""
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if not user.get("is_master") and user.get("role_name") != "Administrador":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao master")
        return user
    return _check
