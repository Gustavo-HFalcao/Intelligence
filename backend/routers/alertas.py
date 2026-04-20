"""
Alertas router — /api/alertas
Subscriptions, history, alert rules (enterprise), trigger manual.
Tables: email_sender, alert_subscriptions, alert_history, alert_rules
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/alertas", tags=["alertas"])

_BRT = timezone(timedelta(hours=-3))

ALERT_TYPES: Dict[str, Dict[str, str]] = {
    "daily": {
        "label": "Resumo Diário", "category": "cronologico",
        "icon": "sun", "color": "#2A9D8F",
        "description": "Resumo automático enviado diariamente às 18h.",
        "schedule": "Todos os dias às 18h",
    },
    "weekly": {
        "label": "Resumo Semanal", "category": "cronologico",
        "icon": "calendar-days", "color": "#3B82F6",
        "description": "Consolidado semanal todo segunda às 8h.",
        "schedule": "Toda segunda-feira às 8h",
    },
    "monthly": {
        "label": "Fechamento de Medição", "category": "cronologico",
        "icon": "file-text", "color": "#C98B2A",
        "description": "Balanço financeiro todo dia 25.",
        "schedule": "Todo dia 25 às 9h",
    },
    "risk_high": {
        "label": "Risco Alto (≥70)", "category": "reativo",
        "icon": "alert-triangle", "color": "#EF4444",
        "description": "Score de risco ≥ 70.",
        "schedule": "Verificado diariamente às 18h",
    },
    "budget_overage": {
        "label": "Budget Estourado >5%", "category": "reativo",
        "icon": "trending-up", "color": "#F59E0B",
        "description": "Realizado ultrapassa planejado em >5%.",
        "schedule": "Verificado diariamente às 18h",
    },
    "rdo_pending": {
        "label": "RDO Pendente (48h)", "category": "reativo",
        "icon": "clock", "color": "#8B5CF6",
        "description": "Sem RDO submetido há mais de 48 horas.",
        "schedule": "Verificado diariamente às 18h",
    },
}

_SENTINEL = "scheduler@bomtempo.com.br"


def _utc_to_brt(ts: str) -> str:
    if not ts or ts in ("—",""):
        return ts
    try:
        ts_norm = ts.replace("Z","+00:00")
        dt = datetime.fromisoformat(ts_norm[:32])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BRT).strftime("%d/%m %H:%M")
    except Exception:
        return ts[:16].replace("T"," ") if len(ts) >= 16 else ts


def _fmt_hist(h: Dict) -> Dict:
    at  = str(h.get("alert_type","—"))
    ts  = str(h.get("timestamp") or h.get("created_at") or "—")
    msg = str(h.get("message","—"))
    contract = "—"
    if msg.startswith("[") and "]" in msg:
        contract = msg[1:msg.index("]")]
        msg      = msg[msg.index("]")+2:]
    return {
        "id":          str(h.get("id","")),
        "contract":    contract,
        "alert_type":  at,
        "alert_label": ALERT_TYPES.get(at,{}).get("label", at),
        "alert_color": ALERT_TYPES.get(at,{}).get("color","#C98B2A"),
        "message":     msg[:140],
        "is_read":     bool(h.get("is_read", False)),
        "timestamp":   _utc_to_brt(ts),
    }


# ── Alert type registry ────────────────────────────────────────────────────────

@router.get("/tipos")
async def list_tipos(_user=Depends(get_current_user)) -> Dict[str, Any]:
    return {"tipos": ALERT_TYPES}


# ── Subscriptions ─────────────────────────────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(
    contrato: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if contrato:
        filters["contrato"] = contrato

    subs = sb_select("alert_subscriptions", filters=filters, limit=500) or []
    emails = sb_select("email_sender", filters=filters, limit=500) or []

    # Group by (alert_type, contrato)
    from collections import defaultdict
    groups: Dict[str, Dict] = {}
    for s in subs:
        at  = str(s.get("alert_type",""))
        ct  = str(s.get("contrato",""))
        key = f"{at}|{ct}"
        if key not in groups:
            groups[key] = {
                "alert_type":  at,
                "alert_label": ALERT_TYPES.get(at,{}).get("label", at),
                "alert_color": ALERT_TYPES.get(at,{}).get("color","#C98B2A"),
                "contract":    ct,
                "is_active":   bool(s.get("is_active", True)),
                "key":         key,
                "email_chips": [],
                "count":       "0",
            }

    for e in emails:
        at  = str(e.get("module","")).replace("alertas_","")
        ct  = str(e.get("contrato",""))
        em  = str(e.get("email",""))
        if em == _SENTINEL:
            continue
        key = f"{at}|{ct}"
        if key in groups:
            groups[key]["email_chips"].append({"email": em, "id": str(e.get("id",""))})

    result = []
    for g in groups.values():
        g["emails_display"] = ", ".join(c["email"] for c in g["email_chips"])
        g["count"] = str(len(g["email_chips"]))
        result.append(g)

    return {"subscriptions": result}


@router.post("/subscriptions")
async def upsert_subscription(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    at      = body.get("alert_type","")
    ct      = body.get("contrato","")
    active  = bool(body.get("is_active", True))
    filters: Dict[str, Any] = {"alert_type": at}
    if ct:
        filters["contrato"] = ct
    existing = sb_select("alert_subscriptions", filters=filters, limit=1) or []
    if existing:
        sb_update("alert_subscriptions", filters={"id": existing[0]["id"]}, data={"is_active": active})
    else:
        sb_insert("alert_subscriptions", {
            "alert_type": at,
            "contrato":   ct,
            "is_active":  active,
            "client_id":  client_id,
            "user_email": _SENTINEL,
        })
    return {"ok": True}


@router.post("/subscriptions/email")
async def add_email(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    at    = body.get("alert_type","")
    ct    = body.get("contrato","")
    email = str(body.get("email","")).strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "error": "Email inválido"}
    row = sb_insert("email_sender", {
        "module":     f"alertas_{at}",
        "contrato":   ct,
        "email":      email,
        "client_id":  client_id,
    })
    return {"ok": True, "row": row}


@router.delete("/subscriptions/email/{email_id}")
async def remove_email(email_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("email_sender", filters={"id": email_id})
    return {"ok": True}


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
async def list_history(
    contrato: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, le=100),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("alert_history", filters=filters, order="created_at.desc", limit=page_size + 1) or []
    has_next = len(rows) > page_size
    if contrato:
        rows = [r for r in rows if contrato in str(r.get("message",""))]
    return {
        "history":  [_fmt_hist(r) for r in rows[:page_size]],
        "has_next": has_next,
        "page":     page,
    }


@router.patch("/history/{hist_id}/read")
async def mark_read(hist_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_update("alert_history", filters={"id": hist_id}, data={"is_read": True})
    return {"ok": True}


# ── Alert Rules (enterprise) ──────────────────────────────────────────────────

@router.get("/rules")
async def list_rules(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("alert_rules", filters=filters, order="created_at.desc", limit=200) or []
    return {"rules": rows}


@router.post("/rules")
async def create_rule(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "name":        body.get("name",""),
        "category":    body.get("category","threshold"),
        "metric":      body.get("metric",""),
        "operator":    body.get("operator","gte"),
        "threshold":   body.get("threshold"),
        "contrato":    body.get("contrato",""),
        "channel":     body.get("channel","email"),
        "recipients":  body.get("recipients",""),
        "is_active":   bool(body.get("is_active", True)),
        "client_id":   client_id,
    }
    row = sb_insert("alert_rules", payload)
    return {"ok": True, "row": row}


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"name","category","metric","operator","threshold","contrato","channel","recipients","is_active"}
    data = {k: v for k,v in body.items() if k in allowed}
    row = sb_update("alert_rules", filters={"id": rule_id}, data=data)
    return {"ok": True, "row": row}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("alert_rules", filters={"id": rule_id})
    return {"ok": True}
