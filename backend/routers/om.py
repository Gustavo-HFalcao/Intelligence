"""
O&M router — /api/om
Gestão de gerações (om_geracoes): CRUD + KPIs + performance.
"""

import re
from collections import defaultdict
from datetime import date as _date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/om", tags=["om"])

STATUS_OPTIONS = ["previsto","em_andamento","concluido","cancelado"]


def _parse_float(v: Any) -> float:
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s in ("None","nan",""):
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _fmt_brl(v: float) -> str:
    return f"R$ {v:_.2f}".replace(".", "DECPT").replace("_", ".").replace("DECPT", ",")


def _norm(v: Any, fb: str = "") -> str:
    if v is None or str(v) in ("None","NaT","nan",""):
        return fb
    return str(v)


def _fmt_geracao(r: Dict) -> Dict:
    prev = _parse_float(r.get("valor_previsto",0))
    exec_ = _parse_float(r.get("valor_executado",0))
    kwh   = _parse_float(r.get("kwh_gerado",0))
    kwh_p = _parse_float(r.get("kwh_previsto",0))
    return {
        "id":                 _norm(r.get("id")),
        "contrato":           _norm(r.get("contrato")),
        "data":               _norm(r.get("data",""))[:10],
        "periodo":            _norm(r.get("periodo","")),
        "descricao":          _norm(r.get("descricao",""),"—"),
        "status":             _norm(r.get("status"),"previsto"),
        "valor_previsto":     prev,
        "valor_executado":    exec_,
        "valor_previsto_fmt": _fmt_brl(prev),
        "valor_executado_fmt":_fmt_brl(exec_),
        "kwh_gerado":         kwh,
        "kwh_previsto":       kwh_p,
        "fator_capacidade":   float(r.get("fator_capacidade",0) or 0),
        "disponibilidade_pct":float(r.get("disponibilidade_pct",0) or 0),
        "observacoes":        _norm(r.get("observacoes","")),
        "created_at":         _norm(r.get("created_at",""))[:10],
    }


def _compute_om_kpis(rows: List[Dict]) -> Dict:
    total_prev  = sum(r["valor_previsto"] for r in rows)
    total_exec  = sum(r["valor_executado"] for r in rows)
    total_kwh   = sum(r["kwh_gerado"] for r in rows)
    total_kwh_p = sum(r["kwh_previsto"] for r in rows)
    pct_exec    = round(total_exec / total_prev * 100, 1) if total_prev > 0 else 0.0
    pct_kwh     = round(total_kwh / total_kwh_p * 100, 1) if total_kwh_p > 0 else 0.0
    disp_vals   = [r["disponibilidade_pct"] for r in rows if r["disponibilidade_pct"] > 0]
    avg_disp    = round(sum(disp_vals) / len(disp_vals), 1) if disp_vals else 0.0
    fc_vals     = [r["fator_capacidade"] for r in rows if r["fator_capacidade"] > 0]
    avg_fc      = round(sum(fc_vals) / len(fc_vals), 4) if fc_vals else 0.0
    return {
        "total_previsto":       _fmt_brl(total_prev),
        "total_executado":      _fmt_brl(total_exec),
        "total_previsto_raw":   total_prev,
        "total_executado_raw":  total_exec,
        "saldo":                _fmt_brl(total_prev - total_exec),
        "pct_executado":        pct_exec,
        "total_kwh":            round(total_kwh, 1),
        "total_kwh_previsto":   round(total_kwh_p, 1),
        "pct_kwh":              pct_kwh,
        "avg_disponibilidade":  avg_disp,
        "avg_fator_capacidade": avg_fc,
        "total_geracoes":       len(rows),
    }


def _monthly_series(rows: List[Dict]) -> List[Dict]:
    by_month: Dict[str, Dict] = defaultdict(lambda: {"prev": 0.0, "exec": 0.0, "kwh": 0.0})
    for r in rows:
        d = r.get("data","")[:7]  # YYYY-MM
        if not d or len(d) < 7:
            continue
        by_month[d]["prev"] += r["valor_previsto"]
        by_month[d]["exec"] += r["valor_executado"]
        by_month[d]["kwh"]  += r["kwh_gerado"]
    result = []
    for month in sorted(by_month):
        parts = month.split("-")
        label = f"{parts[1]}/{parts[0]}" if len(parts) == 2 else month
        m = by_month[month]
        result.append({
            "mes":       label,
            "previsto":  round(m["prev"],2),
            "executado": round(m["exec"],2),
            "kwh":       round(m["kwh"],1),
        })
    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def get_om_all(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Agrega gerações de todos os contratos do tenant."""
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    raw = sb_select("om_geracoes", filters=filters, order="data.asc", limit=5000) or []
    rows = [_fmt_geracao(r) for r in raw]
    return {
        "geracoes":       rows,
        "kpis":           _compute_om_kpis(rows),
        "serie_mensal":   _monthly_series(rows),
        "status_options": STATUS_OPTIONS,
    }


@router.get("/{contrato}")
async def get_om(
    contrato: str,
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    raw = sb_select("om_geracoes", filters=filters, order="data.asc", limit=500) or []
    rows = [_fmt_geracao(r) for r in raw]
    return {
        "geracoes":     rows,
        "kpis":         _compute_om_kpis(rows),
        "serie_mensal": _monthly_series(rows),
        "status_options": STATUS_OPTIONS,
    }


@router.post("/{contrato}")
async def create_geracao(
    contrato: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "contrato":           contrato,
        "data":               body.get("data") or str(_date.today()),
        "periodo":            body.get("periodo",""),
        "descricao":          body.get("descricao",""),
        "status":             body.get("status","previsto"),
        "valor_previsto":     round(_parse_float(body.get("valor_previsto",0)), 2),
        "valor_executado":    round(_parse_float(body.get("valor_executado",0)), 2),
        "kwh_gerado":         round(_parse_float(body.get("kwh_gerado",0)), 2),
        "kwh_previsto":       round(_parse_float(body.get("kwh_previsto",0)), 2),
        "fator_capacidade":   round(_parse_float(body.get("fator_capacidade",0)), 4),
        "disponibilidade_pct":round(_parse_float(body.get("disponibilidade_pct",0)), 1),
        "observacoes":        body.get("observacoes",""),
        "client_id":          client_id,
    }
    row = sb_insert("om_geracoes", payload)
    return {"ok": True, "row": _fmt_geracao(row) if row else {}}


@router.patch("/{geracao_id}")
async def update_geracao(
    geracao_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"data","periodo","descricao","status","valor_previsto","valor_executado",
               "kwh_gerado","kwh_previsto","fator_capacidade","disponibilidade_pct","observacoes"}
    data = {k: v for k,v in body.items() if k in allowed}
    for fld in ("valor_previsto","valor_executado","kwh_gerado","kwh_previsto"):
        if fld in data:
            data[fld] = round(_parse_float(data[fld]), 2)
    row = sb_update("om_geracoes", filters={"id": geracao_id}, data=data)
    return {"ok": True, "row": _fmt_geracao(row) if row else {}}


@router.delete("/{geracao_id}")
async def delete_geracao(geracao_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("om_geracoes", filters={"id": geracao_id})
    return {"ok": True}


@router.get("/{contrato}/faturamento")
async def get_faturamento(
    contrato: str,
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    raw = sb_select("om_geracoes", filters=filters, order="data.asc", limit=500) or []
    rows = [_fmt_geracao(r) for r in raw]
    concluidos = [r for r in rows if r["status"] in ("concluido","executado")]
    total_faturado = sum(r["valor_executado"] for r in concluidos)
    return {
        "total_faturado":     _fmt_brl(total_faturado),
        "total_faturado_raw": total_faturado,
        "total_geracoes":     len(concluidos),
        "serie_mensal":       _monthly_series(rows),
    }
