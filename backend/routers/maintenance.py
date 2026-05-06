"""
Maintenance router — /api/maintenance
Tarefas e ordens de serviço vinculadas a inversores.

Fluxo de status: pending → in_progress → done | cancelled
Prioridade: low | medium | high | critical
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

_VALID_STATUS   = {"pending", "in_progress", "done", "cancelled"}
_VALID_PRIORITY = {"low", "medium", "high", "critical"}


# ── GET /api/maintenance ───────────────────────────────────────────────────────

@router.get("")
def list_tasks(
    inverter_id: Optional[str] = Query(None),
    status:      Optional[str] = Query(None),
    priority:    Optional[str] = Query(None),
    limit:       int           = Query(100, ge=1, le=500),
    _user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
):
    filters: dict = {}
    if tenant:
        filters["client_id"] = tenant
    if inverter_id:
        filters["inverter_id"] = inverter_id
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority

    tasks = sb_select(
        "inverter_maintenance",
        filters=filters,
        order="created_at.desc",
        limit=limit,
    ) or []
    return tasks


# ── GET /api/maintenance/inversor/{inverter_id}/open-count ────────────────────
# Registrado ANTES de /{task_id} para evitar captura incorreta pela rota dinâmica

@router.get("/inversor/{inverter_id}/open-count")
def open_count(inverter_id: str, _user=Depends(get_current_user), tenant=Depends(get_current_tenant)):
    """Contagem de tarefas abertas para badge no card."""
    filters: dict = {"inverter_id": inverter_id}
    if tenant:
        filters["client_id"] = tenant

    rows = sb_select(
        "inverter_maintenance",
        filters=filters,
        limit=500,
    ) or []
    open_tasks = [r for r in rows if r.get("status") in ("pending", "in_progress")]
    return {"inverter_id": inverter_id, "open_count": len(open_tasks)}


# ── GET /api/maintenance/{task_id} ────────────────────────────────────────────

@router.get("/{task_id}")
def get_task(task_id: str, _user=Depends(get_current_user), tenant=Depends(get_current_tenant)):
    rows = sb_select("inverter_maintenance", filters={"id": task_id}, limit=1) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    task = rows[0]
    if tenant and task.get("client_id") and task["client_id"] != tenant:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return task


# ── POST /api/maintenance ──────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_task(
    body: dict = Body(...),
    _user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
):
    inverter_id = body.get("inverter_id")
    title       = (body.get("title") or "").strip()
    if not inverter_id:
        raise HTTPException(status_code=422, detail="inverter_id obrigatório")
    if not title:
        raise HTTPException(status_code=422, detail="title obrigatório")

    priority = body.get("priority", "medium")
    status   = body.get("status", "pending")
    if priority not in _VALID_PRIORITY:
        raise HTTPException(status_code=422, detail=f"priority inválida: {priority}")
    if status not in _VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status inválido: {status}")

    row = {
        "inverter_id": inverter_id,
        "client_id":   tenant,
        "title":       title,
        "description": body.get("description", ""),
        "status":      status,
        "priority":    priority,
        "assignee":    body.get("assignee", ""),
        "due_date":    body.get("due_date") or None,
        "alert_id":    body.get("alert_id"),
        "notes":       body.get("notes", ""),
    }

    created = sb_insert("inverter_maintenance", row)
    return created


# ── PATCH /api/maintenance/{task_id} ──────────────────────────────────────────

@router.patch("/{task_id}")
def update_task(
    task_id: str,
    body:    dict = Body(...),
    _user=Depends(get_current_user),
    tenant=Depends(get_current_tenant),
):
    rows = sb_select("inverter_maintenance", filters={"id": task_id}, limit=1) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    task = rows[0]
    if tenant and task.get("client_id") and task["client_id"] != tenant:
        raise HTTPException(status_code=403, detail="Acesso negado")

    allowed = {"title", "description", "status", "priority", "assignee", "due_date", "notes"}
    patch: dict = {k: v for k, v in body.items() if k in allowed}

    if "status" in patch and patch["status"] not in _VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status inválido: {patch['status']}")
    if "priority" in patch and patch["priority"] not in _VALID_PRIORITY:
        raise HTTPException(status_code=422, detail=f"priority inválida: {patch['priority']}")

    if not patch:
        return task

    updated = sb_update("inverter_maintenance", {"id": task_id}, patch)
    return updated


# ── DELETE /api/maintenance/{task_id} ─────────────────────────────────────────

@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, _user=Depends(get_current_user), tenant=Depends(get_current_tenant)):
    rows = sb_select("inverter_maintenance", filters={"id": task_id}, limit=1) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    task = rows[0]
    if tenant and task.get("client_id") and task["client_id"] != tenant:
        raise HTTPException(status_code=403, detail="Acesso negado")

    sb_delete("inverter_maintenance", {"id": task_id})
