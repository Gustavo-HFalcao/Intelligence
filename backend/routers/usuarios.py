"""
Usuarios router — /api/usuarios
CRUD de usuários (login table) + perfis de acesso (roles table).
Tables: login, roles
"""

import hashlib
import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])

MODULES: List[tuple] = [
    ("visao_geral",       "Visão Geral",       "layout-dashboard"),
    ("obras",             "Obras",             "hard-hat"),
    ("projetos",          "Projetos",          "briefcase"),
    ("financeiro",        "Financeiro",        "wallet"),
    ("om",                "O&M",               "zap"),
    ("analytics",         "Analytics",         "bar-chart-3"),
    ("previsoes",         "Previsões ML",      "trending-up"),
    ("relatorios",        "Relatórios",        "file-text"),
    ("chat_ia",           "Chat IA",           "message-square"),
    ("reembolso",         "Reembolso Form",    "fuel"),
    ("reembolso_dash",    "Reembolso Dash",    "receipt"),
    ("rdo_form",          "RDO Diário",        "clipboard-list"),
    ("rdo_historico",     "Meus RDOs",         "clock"),
    ("rdo_dashboard",     "RDO Analytics",     "chart-bar"),
    ("alertas",           "Alertas",           "bell-ring"),
    ("logs_auditoria",    "Logs & Auditoria",  "shield-check"),
    ("gerenciar_usuarios","Gerenciar Usuários","users"),
]

ROLES = ["Administrador","Engenheiro","Gestão-Mobile","Operário"]


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"


def _norm_user(r: Dict) -> Dict:
    return {
        "id":          str(r.get("id","")),
        "login":       str(r.get("login","")),
        "nome":        str(r.get("nome") or r.get("login","")),
        "email":       str(r.get("email","")),
        "role":        str(r.get("role","Operário")),
        "role_id":     str(r.get("role_id","")),
        "contrato":    str(r.get("contrato","")),
        "client_id":   str(r.get("client_id","")),
        "is_active":   bool(r.get("is_active", True)),
        "avatar_icon": str(r.get("avatar_icon","user")),
        "created_at":  str(r.get("created_at",""))[:10],
    }


# ── Usuários ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_users(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("login", filters=filters, order="login.asc", limit=500) or []
    return {"users": [_norm_user(r) for r in rows]}


@router.post("")
async def create_user(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    login    = str(body.get("login","")).strip()
    password = str(body.get("password","")).strip()
    if not login or not password:
        return {"ok": False, "error": "Login e senha obrigatórios"}

    existing = sb_select("login", filters={"login": login}, limit=1) or []
    if existing:
        return {"ok": False, "error": "Login já existe"}

    payload = {
        "login":       login,
        "password":    _hash_password(password),
        "nome":        body.get("nome", login),
        "email":       body.get("email",""),
        "role":        body.get("role","Operário"),
        "role_id":     body.get("role_id") or None,
        "contrato":    body.get("contrato",""),
        "client_id":   client_id,
        "is_active":   True,
        "avatar_icon": body.get("avatar_icon","user"),
    }
    row = sb_insert("login", payload)
    return {"ok": True, "user": _norm_user(row) if row else {}}


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"nome","email","role","role_id","contrato","is_active","avatar_icon"}
    data    = {k: v for k,v in body.items() if k in allowed}
    if "password" in body and body["password"]:
        data["password"] = _hash_password(str(body["password"]))
    row = sb_update("login", filters={"id": user_id}, data=data)
    return {"ok": True, "user": _norm_user(row) if row else {}}


@router.delete("/{user_id}")
async def delete_user(user_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("login", filters={"id": user_id})
    return {"ok": True}


# ── Perfis (roles) ────────────────────────────────────────────────────────────

@router.get("/roles")
async def list_roles(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {"client_id": client_id} if client_id else {}
    rows = sb_select("roles", filters=filters, order="nome.asc", limit=200) or []
    return {
        "roles": rows, 
        "role_options": ROLES, 
        "modules": [{"slug": m[0], "label": m[1], "icon": m[2]} for m in MODULES],
        "default_modules": [m[0] for m in MODULES]
    }


@router.post("/roles")
async def create_role(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "nome":        body.get("nome",""),
        "descricao":   body.get("descricao",""),
        "modulos":     body.get("modulos",[]),
        "permissoes":  body.get("permissoes",{}),
        "client_id":   client_id,
    }
    row = sb_insert("roles", payload)
    return {"ok": True, "role": row}


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"nome","descricao","modulos","permissoes"}
    data    = {k: v for k,v in body.items() if k in allowed}
    row = sb_update("roles", filters={"id": role_id}, data=data)
    return {"ok": True, "role": row}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("roles", filters={"id": role_id})
    return {"ok": True}


# ── Perfil pessoal ────────────────────────────────────────────────────────────

@router.get("/perfil")
async def get_perfil(user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("login", filters={"login": user["login"]}, limit=1) or []
    if not rows:
        return {"user": {}}
    return {"user": _norm_user(rows[0])}


@router.patch("/perfil")
async def update_perfil(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    rows = sb_select("login", filters={"login": user["login"]}, limit=1) or []
    if not rows:
        return {"ok": False, "error": "Usuário não encontrado"}
    user_id = rows[0]["id"]
    data: Dict[str, Any] = {}
    if body.get("nome"):
        data["nome"] = body["nome"]
    if body.get("email"):
        data["email"] = body["email"]
    if body.get("avatar_icon"):
        data["avatar_icon"] = body["avatar_icon"]
    if body.get("password"):
        data["password"] = _hash_password(str(body["password"]))
    row = sb_update("login", filters={"id": user_id}, data=data)
    return {"ok": True, "user": _norm_user(row) if row else {}}
