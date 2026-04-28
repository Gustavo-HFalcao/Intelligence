"""
Usuarios router — /api/usuarios
CRUD de usuários (login table) + perfis de acesso (roles table).
Schema real: login(id, username, password, user_role, avatar_icon, email, client_id, project, pw_hash)
             roles(id, name, modules, icon, client_id, landing_page)
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

LANDING_OPTIONS: List[tuple] = [
    ("/hub",              "Hub de Operações"),
    ("/rdo-form",         "Novo RDO"),
    ("/rdo-historico",    "Histórico de RDOs"),
    ("/financeiro",       "Financeiro"),
    ("/relatorios",       "Relatórios"),
    ("/om",               "O&M"),
    ("/reembolso",        "Reembolso"),
    ("/usuarios",         "Usuários"),
]


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"


def _norm_user(r: Dict) -> Dict:
    return {
        "id":          str(r.get("id", "")),
        "login":       str(r.get("username", "")),
        "username":    str(r.get("username", "")),
        "nome":        str(r.get("username", "")),  # login table tem apenas username
        "email":       str(r.get("email", "")),
        "role":        str(r.get("user_role", "Operário")),
        "user_role":   str(r.get("user_role", "Operário")),
        "contrato":    str(r.get("project", "")),
        "project":     str(r.get("project", "")),
        "client_id":   str(r.get("client_id", "")),
        "is_active":   True,  # campo não existe na tabela — assume ativo
        "avatar_icon": str(r.get("avatar_icon", "user")),
        "created_at":  str(r.get("created_at", ""))[:10],
    }


def _norm_role(r: Dict) -> Dict:
    return {
        "id":           str(r.get("id", "")),
        "nome":         str(r.get("name", "")),
        "name":         str(r.get("name", "")),
        "descricao":    str(r.get("icon", "")),  # usando icon como descrição curta
        "modulos":      r.get("modules") or [],
        "modules":      r.get("modules") or [],
        "landing_page": str(r.get("landing_page", "")),
        "client_id":    str(r.get("client_id", "")),
        "created_at":   str(r.get("created_at", ""))[:10],
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
    rows = sb_select("login", filters=filters, order="username.asc", limit=500) or []
    return {"users": [_norm_user(r) for r in rows]}


@router.post("")
async def create_user(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    username = str(body.get("login", body.get("username", ""))).strip()
    password = str(body.get("password", "")).strip()
    if not username or not password:
        return {"ok": False, "error": "Login e senha obrigatórios"}

    existing = sb_select("login", filters={"username": username}, limit=1) or []
    if existing:
        return {"ok": False, "error": "Login já existe"}

    pw_hash = _hash_password(password)
    payload = {
        "username":   username,
        "password":   pw_hash,
        "pw_hash":    pw_hash,
        "user_role":  body.get("role", body.get("user_role", "Operário")),
        "email":      body.get("email", ""),
        "project":    body.get("contrato", body.get("project", "")),
        "avatar_icon": body.get("avatar_icon", "user"),
        "client_id":  client_id,
    }
    row = sb_insert("login", payload)
    return {"ok": True, "user": _norm_user(row) if row else {}}


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if "role" in body or "user_role" in body:
        data["user_role"] = body.get("role") or body.get("user_role")
    if "email" in body:
        data["email"] = body["email"]
    if "contrato" in body or "project" in body:
        data["project"] = body.get("contrato") or body.get("project")
    if "avatar_icon" in body:
        data["avatar_icon"] = body["avatar_icon"]
    if "password" in body and body["password"]:
        pw = _hash_password(str(body["password"]))
        data["password"] = pw
        data["pw_hash"]  = pw
    if not data:
        return {"ok": True}
    row = sb_update("login", filters={"id": user_id}, data=data)
    return {"ok": True, "user": _norm_user(row) if isinstance(row, dict) else {}}


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
    rows = sb_select("roles", filters=filters, order="name.asc", limit=200) or []
    return {
        "roles":           [_norm_role(r) for r in rows],
        "modules":         [{"slug": m[0], "label": m[1], "icon": m[2]} for m in MODULES],
        "landing_options": [{"path": p[0], "label": p[1]} for p in LANDING_OPTIONS],
        "default_modules": [m[0] for m in MODULES],
    }


@router.post("/roles")
async def create_role(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "name":         body.get("nome", body.get("name", "")),
        "modules":      body.get("modulos", body.get("modules", [])),
        "icon":         body.get("descricao", body.get("icon", "")),
        "landing_page": body.get("landing_page", ""),
        "client_id":    client_id,
    }
    row = sb_insert("roles", payload)
    return {"ok": True, "role": _norm_role(row) if row else {}}


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if "nome" in body or "name" in body:
        data["name"] = body.get("nome") or body.get("name")
    if "modulos" in body or "modules" in body:
        data["modules"] = body.get("modulos") or body.get("modules")
    if "descricao" in body or "icon" in body:
        data["icon"] = body.get("descricao") or body.get("icon")
    if "landing_page" in body:
        data["landing_page"] = body["landing_page"]
    if not data:
        return {"ok": True}
    row = sb_update("roles", filters={"id": role_id}, data=data)
    return {"ok": True, "role": _norm_role(row) if isinstance(row, dict) else {}}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("roles", filters={"id": role_id})
    return {"ok": True}


# ── Perfil pessoal ────────────────────────────────────────────────────────────

@router.get("/perfil")
async def get_perfil(user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("login", filters={"username": user.get("login", user.get("username", ""))}, limit=1) or []
    if not rows:
        return {"user": {}}
    return {"user": _norm_user(rows[0])}


@router.patch("/perfil")
async def update_perfil(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    username = user.get("login") or user.get("username", "")
    rows = sb_select("login", filters={"username": username}, limit=1) or []
    if not rows:
        return {"ok": False, "error": "Usuário não encontrado"}
    user_id = rows[0]["id"]
    data: Dict[str, Any] = {}
    if body.get("email"):
        data["email"] = body["email"]
    if body.get("avatar_icon"):
        data["avatar_icon"] = body["avatar_icon"]
    if body.get("password"):
        pw = _hash_password(str(body["password"]))
        data["password"] = pw
        data["pw_hash"]  = pw
    if not data:
        return {"ok": True}
    row = sb_update("login", filters={"id": user_id}, data=data)
    return {"ok": True, "user": _norm_user(row) if isinstance(row, dict) else {}}
