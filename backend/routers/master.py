"""
Master router — /api/master
Console multi-tenant exclusivo para BTP_MASTER.
Tables: clients, master_stats (view), login, llm_observability, feature_flags
"""

import hashlib
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/master", tags=["master"])

ALL_MODULES = [
    "visao_geral","obras","projetos","financeiro","om","analytics","previsoes",
    "relatorios","chat_ia","reembolso","reembolso_dash","rdo_form","rdo_historico",
    "rdo_dashboard","alertas","logs_auditoria","gerenciar_usuarios",
]


def _require_master(user: Dict) -> bool:
    return user.get("is_master", False) or user.get("role") == "Administrador"


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"


# ── Tenants ───────────────────────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("master_stats", limit=200) or []
    tenants = [
        {
            "client_id":     str(r.get("client_id","")),
            "client_name":   str(r.get("client_name","")),
            "is_master":     bool(r.get("is_master", False)),
            "status":        str(r.get("status","active")),
            "ai_budget":     float(r.get("ai_budget", 100)),
            "user_count":    int(r.get("user_count", 0)),
            "total_logs":    int(r.get("total_logs", 0)),
            "session_count": int(r.get("session_count", 0)),
        }
        for r in rows
    ]
    return {"tenants": tenants}


@router.post("/tenants")
async def create_tenant(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    name       = str(body.get("name","")).strip()
    admin_user = str(body.get("admin_username","")).strip()
    admin_pw   = str(body.get("admin_password","")).strip()

    if not name or not admin_user or not admin_pw:
        return {"ok": False, "error": "name, admin_username e admin_password obrigatórios"}

    budget = float(body.get("ai_budget", 100))

    tenant = sb_insert("clients", {
        "name":      name,
        "is_master": False,
        "ai_budget": budget,
        "status":    "active",
    })
    if not tenant:
        return {"ok": False, "error": "Falha ao criar tenant"}

    new_client_id = str(tenant.get("id",""))

    role = sb_insert("roles", {
        "nome":      "Administrador",
        "modulos":   ALL_MODULES,
        "client_id": new_client_id,
    })
    role_id = str(role.get("id","")) if role else None

    sb_insert("login", {
        "login":     admin_user,
        "password":  _hash_password(admin_pw),
        "nome":      admin_user,
        "role":      "Administrador",
        "role_id":   role_id,
        "client_id": new_client_id,
        "is_active": True,
    })

    return {"ok": True, "client_id": new_client_id, "tenant": tenant}


@router.patch("/tenants/{client_id}")
async def update_tenant(
    client_id: str,
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"name","status","ai_budget","feature_flags"}
    data    = {k: v for k,v in body.items() if k in allowed}
    row = sb_update("clients", filters={"id": client_id}, data=data)
    return {"ok": True, "tenant": row}


@router.delete("/tenants/{client_id}")
async def delete_tenant(client_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
    # Soft delete — set status inactive
    sb_update("clients", filters={"id": client_id}, data={"status": "inactive"})
    return {"ok": True}


# ── All users (cross-tenant) ──────────────────────────────────────────────────

@router.get("/users")
async def list_all_users(
    client_id_filter: Optional[str] = Query(None),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id_filter:
        filters["client_id"] = client_id_filter
    rows    = sb_select("login", filters=filters, order="login.asc", limit=1000) or []
    clients = sb_select("clients", limit=200) or []
    client_map = {str(c.get("id","")): str(c.get("name","—")) for c in clients}
    users = [
        {
            "id":          str(r.get("id","")),
            "login":       str(r.get("login","")),
            "nome":        str(r.get("nome") or r.get("login","")),
            "role":        str(r.get("role","Operário")),
            "client_id":   str(r.get("client_id","")),
            "client_name": client_map.get(str(r.get("client_id","")), "—"),
            "email":       str(r.get("email","") or ""),
            "is_active":   bool(r.get("is_active", True)),
        }
        for r in rows
    ]
    return {"users": users}


# ── Feature flags ─────────────────────────────────────────────────────────────

@router.get("/feature-flags/{client_id}")
async def get_feature_flags(client_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("clients", filters={"id": client_id}, limit=1) or []
    if not rows:
        return {"flags": {}}
    return {"flags": rows[0].get("feature_flags") or {}}


@router.patch("/feature-flags/{client_id}")
async def set_feature_flags(
    client_id: str,
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    flags = body.get("flags", {})
    sb_update("clients", filters={"id": client_id}, data={"feature_flags": flags})
    return {"ok": True, "flags": flags}


# ── AI Budget ─────────────────────────────────────────────────────────────────

@router.get("/ai-usage")
async def get_ai_usage(user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("llm_observability", order="created_at.desc", limit=500) or []
    clients = sb_select("clients", limit=200) or []
    client_map = {str(c.get("id","")): str(c.get("name","—")) for c in clients}

    from collections import defaultdict
    by_tenant: Dict[str, Dict] = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "calls": 0})
    for r in rows:
        cid = str(r.get("client_id","—"))
        by_tenant[cid]["cost"]   += float(r.get("cost_usd", 0) or 0)
        by_tenant[cid]["tokens"] += int(r.get("total_tokens", 0) or 0)
        by_tenant[cid]["calls"]  += 1

    result = []
    for cid, stats in by_tenant.items():
        result.append({
            "client_id":   cid,
            "client_name": client_map.get(cid,"—"),
            "cost_usd":    round(stats["cost"],4),
            "tokens":      stats["tokens"],
            "calls":       stats["calls"],
        })
    result.sort(key=lambda x: x["cost_usd"], reverse=True)
    return {"by_tenant": result}


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metricas")
async def get_metricas(user=Depends(get_current_user)) -> Dict[str, Any]:
    clients  = sb_select("clients", limit=200) or []
    users    = sb_select("login", limit=1000) or []
    logs     = sb_select("llm_observability", order="created_at.desc", limit=100) or []

    active_tenants = sum(1 for c in clients if c.get("status","active") == "active")
    total_cost     = sum(float(r.get("cost_usd",0) or 0) for r in logs)
    total_tokens   = sum(int(r.get("total_tokens",0) or 0) for r in logs)

    return {
        "total_tenants":   len(clients),
        "active_tenants":  active_tenants,
        "total_users":     len(users),
        "total_ai_cost":   round(total_cost, 4),
        "total_ai_tokens": total_tokens,
        "recent_ai_calls": len(logs),
    }


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("clients", filters={"is_master": True}, limit=1) or []
    return {"settings": rows[0] if rows else {}}


@router.patch("/settings")
async def update_settings(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    rows = sb_select("clients", filters={"is_master": True}, limit=1) or []
    if not rows:
        return {"ok": False, "error": "Master client não encontrado"}
    allowed = {"ai_budget","feature_flags","status"}
    data    = {k: v for k,v in body.items() if k in allowed}
    sb_update("clients", filters={"id": rows[0]["id"]}, data=data)
    return {"ok": True}
