"""
Relatorios router — /api/relatorios
Builder de relatórios + geração PDF via Celery (não bloqueia RAM).
Tables: relatorios (saved reports), Bucket: rdo-pdfs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.core.logging import get_logger

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])
logger = get_logger(__name__)

REPORT_TYPES = [
    {"slug": "executive",   "label": "Relatório Executivo",   "icon": "file-text"},
    {"slug": "financial",   "label": "Relatório Financeiro",  "icon": "wallet"},
    {"slug": "physical",    "label": "Avanço Físico",         "icon": "bar-chart-3"},
    {"slug": "rdo_period",  "label": "RDO por Período",       "icon": "clipboard-list"},
    {"slug": "evm",         "label": "EVM — CPI/SPI/EAC",     "icon": "trending-up"},
    {"slug": "om",          "label": "O&M — Performance",     "icon": "zap"},
]


def _norm_report(r: Dict) -> Dict:
    return {
        "id":          str(r.get("id","")),
        "titulo":      str(r.get("titulo","")),
        "tipo":        str(r.get("tipo","")),
        "contrato":    str(r.get("contrato","")),
        "periodo_ini": str(r.get("periodo_ini",""))[:10],
        "periodo_fim": str(r.get("periodo_fim",""))[:10],
        "status":      str(r.get("status","Pendente")),
        "pdf_url":     str(r.get("pdf_url","")),
        "created_at":  str(r.get("created_at",""))[:10],
        "parametros":  r.get("parametros") or {},
    }


@router.get("/tipos")
async def list_tipos(_user=Depends(get_current_user)) -> Dict[str, Any]:
    return {"tipos": REPORT_TYPES}


@router.get("")
async def list_relatorios(
    contrato: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if contrato:
        filters["contrato"] = contrato
    rows = sb_select("relatorios", filters=filters, order="created_at.desc", limit=200) or []
    return {"relatorios": [_norm_report(r) for r in rows]}


@router.post("/generate")
async def generate_report(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    tipo     = body.get("tipo","executive")
    contrato = body.get("contrato","")
    titulo   = body.get("titulo") or f"Relatório {tipo} — {contrato}"

    row = sb_insert("relatorios", {
        "titulo":      titulo,
        "tipo":        tipo,
        "contrato":    contrato,
        "periodo_ini": body.get("periodo_ini") or None,
        "periodo_fim": body.get("periodo_fim") or None,
        "status":      "Processando",
        "client_id":   client_id,
        "solicitado_por": user.get("login",""),
    })
    if not row:
        return {"ok": False, "error": "Falha ao criar registro"}

    report_id = str(row.get("id",""))

    # Enqueue Celery task (async — non-blocking)
    try:
        from backend.workers.celery_app import celery_app
        celery_app.send_task(
            "backend.workers.tasks.pdf_tasks.generate_pdf",
            kwargs={"report_id": report_id, "client_id": client_id, "params": body},
        )
    except Exception as e:
        logger.warning(f"Celery enqueue falhou: {e} — report ficará em Processando")

    return {"ok": True, "report_id": report_id, "report": _norm_report(row)}


@router.get("/{report_id}")
async def get_report(report_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("relatorios", filters={"id": report_id}, limit=1) or []
    if not rows:
        return {"report": None}
    return {"report": _norm_report(rows[0])}


@router.delete("/{report_id}")
async def delete_report(report_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("relatorios", filters={"id": report_id})
    return {"ok": True}
