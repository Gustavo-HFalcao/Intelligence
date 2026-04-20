"""
Observabilidade router — /api/obs
Logs LLM, system health, custo AI por modelo/tenant.
Table: llm_observability
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query

from backend.integrations.supabase import sb_insert, sb_select
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/obs", tags=["observabilidade"])

_BRT = timezone(timedelta(hours=-3))

PAGE_SIZE = 25


def _utc_to_brt(ts: str) -> str:
    if not ts:
        return "—"
    try:
        ts_norm = ts.replace("Z","+00:00")
        dt = datetime.fromisoformat(ts_norm[:32])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BRT).strftime("%d/%m %H:%M:%S")
    except Exception:
        return ts[:16].replace("T"," ")


def _fmt_log(r: Dict) -> Dict:
    cost    = float(r.get("cost_usd",0) or 0)
    tokens  = int(r.get("total_tokens",0) or 0)
    prompt  = int(r.get("prompt_tokens",0) or 0)
    compl   = int(r.get("completion_tokens",0) or 0)
    latency = float(r.get("latency_ms",0) or 0)
    return {
        "id":               str(r.get("id","")),
        "created_at":       _utc_to_brt(str(r.get("created_at",""))),
        "model":            str(r.get("model","—")),
        "endpoint":         str(r.get("endpoint","—")),
        "cost_usd":         cost,
        "cost_fmt":         f"US$ {cost:.4f}",
        "total_tokens":     tokens,
        "prompt_tokens":    prompt,
        "completion_tokens":compl,
        "latency_ms":       latency,
        "latency_fmt":      f"{latency:.0f} ms",
        "client_id":        str(r.get("client_id","")),
        "user_login":       str(r.get("user_login","—")),
        "success":          bool(r.get("success", True)),
        "error_msg":        str(r.get("error_msg","") or ""),
        "prompt_preview":   str(r.get("prompt_preview",""))[:120],
    }


# ── Logs LLM ──────────────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs(
    page: int = Query(1, ge=1),
    model: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if model:
        filters["model"] = model
    offset  = (page - 1) * PAGE_SIZE
    rows    = sb_select("llm_observability", filters=filters, order="created_at.desc",
                        limit=PAGE_SIZE + 1) or []
    has_next = len(rows) > PAGE_SIZE
    return {
        "logs":     [_fmt_log(r) for r in rows[:PAGE_SIZE]],
        "has_next": has_next,
        "page":     page,
    }


# ── Métricas agregadas ────────────────────────────────────────────────────────

@router.get("/metricas")
async def get_metricas(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("llm_observability", filters=filters, order="created_at.desc", limit=1000) or []

    total_cost   = sum(float(r.get("cost_usd",0) or 0) for r in rows)
    total_tokens = sum(int(r.get("total_tokens",0) or 0) for r in rows)
    total_calls  = len(rows)
    success_n    = sum(1 for r in rows if r.get("success", True))
    error_n      = total_calls - success_n
    latencies    = [float(r.get("latency_ms",0) or 0) for r in rows if r.get("latency_ms")]
    avg_latency  = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    # By model
    by_model: Dict[str, Dict] = defaultdict(lambda: {"cost":0.0,"tokens":0,"calls":0})
    for r in rows:
        m = str(r.get("model","—"))
        by_model[m]["cost"]   += float(r.get("cost_usd",0) or 0)
        by_model[m]["tokens"] += int(r.get("total_tokens",0) or 0)
        by_model[m]["calls"]  += 1

    model_breakdown = [
        {"model": m, "cost_usd": round(v["cost"],4), "tokens": v["tokens"], "calls": v["calls"]}
        for m, v in sorted(by_model.items(), key=lambda x: x[1]["cost"], reverse=True)
    ]

    # Daily series (last 30 days)
    by_day: Dict[str, float] = defaultdict(float)
    for r in rows:
        ts = str(r.get("created_at",""))[:10]
        if ts:
            by_day[ts] += float(r.get("cost_usd",0) or 0)
    daily_series = [
        {"data": d, "custo": round(c,4)}
        for d,c in sorted(by_day.items())[-30:]
    ]

    return {
        "total_calls":     total_calls,
        "total_cost":      round(total_cost, 4),
        "total_cost_fmt":  f"US$ {total_cost:.4f}",
        "total_tokens":    total_tokens,
        "success":         success_n,
        "errors":          error_n,
        "avg_latency_ms":  avg_latency,
        "model_breakdown": model_breakdown,
        "daily_series":    daily_series,
    }


# ── Health check sistema ──────────────────────────────────────────────────────

@router.get("/health")
async def system_health(_user=Depends(get_current_user)) -> Dict[str, Any]:
    checks: Dict[str, Any] = {}

    # Supabase ping
    try:
        sb_select("clients", limit=1)
        checks["supabase"] = {"status": "ok"}
    except Exception as e:
        checks["supabase"] = {"status": "error", "msg": str(e)[:100]}

    # Redis ping
    try:
        from backend.core.redis_cache import is_redis_available
        checks["redis"] = {"status": "ok" if is_redis_available() else "unavailable"}
    except Exception as e:
        checks["redis"] = {"status": "error", "msg": str(e)[:100]}

    # Celery ping
    try:
        from backend.workers.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=2)
        ping = insp.ping()
        checks["celery"] = {"status": "ok" if ping else "no_workers"}
    except Exception as e:
        checks["celery"] = {"status": "error", "msg": str(e)[:100]}

    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


# ── Audit log (write) ─────────────────────────────────────────────────────────

@router.post("/audit")
async def write_audit(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "model":             body.get("model","—"),
        "endpoint":          body.get("endpoint","—"),
        "cost_usd":          float(body.get("cost_usd",0) or 0),
        "total_tokens":      int(body.get("total_tokens",0) or 0),
        "prompt_tokens":     int(body.get("prompt_tokens",0) or 0),
        "completion_tokens": int(body.get("completion_tokens",0) or 0),
        "latency_ms":        float(body.get("latency_ms",0) or 0),
        "success":           bool(body.get("success", True)),
        "error_msg":         body.get("error_msg",""),
        "prompt_preview":    str(body.get("prompt_preview",""))[:200],
        "user_login":        user.get("login",""),
        "client_id":         client_id,
    }
    sb_insert("llm_observability", payload)
    return {"ok": True}
