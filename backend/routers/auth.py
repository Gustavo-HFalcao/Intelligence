"""
Auth router — Bomtempo Backend (FastAPI)
Portado de GlobalState.check_login(), send_reset_link() e reset_password().

Rotas:
  POST /api/auth/login          — autentica e cria sessão
  POST /api/auth/logout         — destrói sessão
  GET  /api/auth/me             — retorna dados do usuário autenticado
  POST /api/auth/reset-request  — envia email de reset de senha
  POST /api/auth/reset-password — troca senha com token válido
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import (
    SESSION_COOKIE,
    create_session,
    destroy_session,
    get_current_user,
    hash_password,
    login_user,
)
from backend.core.audit import audit_log, audit_error, AuditCategory

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str       # aceita username ou email
    password: str


class ResetRequestBody(BaseModel):
    email: str


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, response: Response):
    user = login_user(body.email, body.password)
    if not user:
        audit_log(
            category=AuditCategory.LOGIN,
            action=f"Tentativa de login falhou: {body.email[:50]}",
            username=body.email[:50],
            status="error",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    session_id = create_session(user)

    audit_log(
        category=AuditCategory.LOGIN,
        action=f"Login bem-sucedido: {user.get('login', user.get('email', ''))}",
        username=user.get("login", user.get("email", "")),
        entity_type="login",
        entity_id=str(user.get("user_id", "")),
        client_id=str(user.get("client_id") or ""),
        metadata={"role": user.get("role_name"), "client": user.get("client_name")},
    )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,  # 7 dias
        secure=True,
    )

    return {
        "user_id": user["user_id"],
        "login": user.get("login", ""),
        "email": user["email"],
        "role_name": user["role_name"],
        "client_id": user["client_id"],
        "client_name": user["client_name"],
        "is_master": user["is_master"],
        "allowed_modules": user.get("allowed_modules", []),
        "avatar_icon": user.get("avatar_icon", ""),
        "whatsapp": user.get("whatsapp", ""),
    }


@router.post("/logout")
async def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    # Não requer autenticação — idempotente: chamadas repetidas são seguras
    from backend.middleware.auth import get_session
    user = get_session(session_id) if session_id else None
    if user:
        audit_log(
            category=AuditCategory.LOGOUT,
            action=f"Logout: {user.get('login', user.get('email', ''))}",
            username=user.get("login", user.get("email", "")),
            client_id=str(user.get("client_id") or ""),
        )
    if session_id:
        destroy_session(session_id)
    response.delete_cookie(SESSION_COOKIE, samesite="strict")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "login": user.get("login", ""),
        "email": user["email"],
        "role_name": user["role_name"],
        "client_id": user["client_id"],
        "client_name": user.get("client_name"),
        "is_master": user.get("is_master", False),
        "allowed_modules": user.get("allowed_modules", []),
        "avatar_icon": user.get("avatar_icon", ""),
        "whatsapp": user.get("whatsapp", ""),
    }


@router.post("/reset-request")
async def reset_request(body: ResetRequestBody):
    """Envia email de reset de senha. Portado de GlobalState.send_reset_link()."""
    rows = sb_select("login", filters={"email": body.email})
    if not rows:
        # Retorna 200 mesmo se email não existir (evita enumeração)
        return {"ok": True}

    user = rows[0]
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    # Invalida tokens antigos do mesmo usuário
    sb_delete("password_reset_tokens", {"user_id": user["id"]})

    sb_insert("password_reset_tokens", {
        "user_id": user["id"],
        "token": token,
        "expires_at": expires_at,
    })

    from backend.core.config import Config
    try:
        from backend.integrations.email import send_reset_password
        send_reset_password(body.email, token, Config.APP_URL)
    except Exception:
        pass  # Email não configurado — ok em dev

    return {"ok": True}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordBody):
    """Troca senha com token válido. Portado de GlobalState.reset_password_with_token()."""
    rows = sb_select("password_reset_tokens", filters={"token": body.token})
    if not rows:
        raise HTTPException(status_code=400, detail="Token inválido")

    record = rows[0]
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expirado")

    new_hash = hash_password(body.new_password)
    sb_update("login", {"id": record["user_id"]}, {"password_hash": new_hash})
    sb_delete("password_reset_tokens", {"token": body.token})

    return {"ok": True}
