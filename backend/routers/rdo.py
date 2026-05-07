"""
RDO router — /api/rdo
Tabelas reais: rdo_master, rdo_atividades, rdo_evidencias
Campos reais confirmados via information_schema.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date as _date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update, sb_upsert
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.core.audit import audit_log, AuditCategory
from backend.core.logging import get_logger
from backend.services.rdo_service import (
    apply_watermark,
    extract_exif_full,
    fetch_map_thumbnail,
    generate_view_token,
    haversine_m,
    reverse_geocode,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/rdo", tags=["rdo"])

_executor = ThreadPoolExecutor(max_workers=3)

CLIMA_OPTIONS  = ["Ensolarado", "Nublado", "Chuvoso", "Parcialmente nublado", "Tempestade", "Ventoso"]
TURNO_OPTIONS  = ["Diurno", "Noturno", "Integral"]
STATUS_OPTIONS = ["Rascunho", "Submetido", "Aprovado", "Rejeitado"]


def _norm(v: Any, fb: str = "") -> str:
    if v is None or str(v) in ("None", "NaT", "nan", ""):
        return fb
    return str(v)


def _fmt_rdo(r: Dict) -> Dict:
    """Normaliza linha do rdo_master para o frontend.
    Mapeamento real: condicao_climatica → clima, assinatura_nome → signatory_name fallback."""
    return {
        "id":                   _norm(r.get("id")),
        "contrato":             _norm(r.get("contrato")),
        "data":                 _norm(r.get("data", ""))[:10],
        "projeto":              _norm(r.get("projeto")),
        "cliente":              _norm(r.get("cliente")),
        "localizacao":          _norm(r.get("localizacao")),
        # condicao_climatica é o campo real na tabela
        "clima":                _norm(r.get("condicao_climatica") or r.get("clima"), "Ensolarado"),
        "turno":                _norm(r.get("turno"), "Diurno"),
        "tipo_tarefa":          _norm(r.get("tipo_tarefa"), "Diário de Obra"),
        "orientacao":           _norm(r.get("orientacao")),
        "km_percorrido":        _norm(r.get("km_percorrido")),
        "hora_inicio":          _norm(r.get("hora_inicio")),
        "hora_termino":         _norm(r.get("hora_termino")),
        "houve_interrupcao":    bool(r.get("houve_interrupcao", False)),
        "motivo_interrupcao":   _norm(r.get("motivo_interrupcao")),
        "equipe_alocada":       _norm(r.get("equipe_alocada")),
        "observacoes":          _norm(r.get("observacoes")),
        "checkin_lat":          float(r.get("checkin_lat") or 0),
        "checkin_lng":          float(r.get("checkin_lng") or 0),
        "checkin_endereco":     _norm(r.get("checkin_endereco")),
        "checkin_timestamp":    _norm(r.get("checkin_timestamp")),
        "checkout_lat":         float(r.get("checkout_lat") or 0),
        "checkout_lng":         float(r.get("checkout_lng") or 0),
        "checkout_endereco":    _norm(r.get("checkout_endereco")),
        "checkout_timestamp":   _norm(r.get("checkout_timestamp")),
        "signatory_name":       _norm(r.get("signatory_name") or r.get("assinatura_nome")),
        "signatory_doc":        _norm(r.get("signatory_doc") or r.get("assinatura_cpf")),
        "signatory_sig_b64":    _norm(r.get("signatory_sig_b64")),
        "houve_chuva":          bool(r.get("houve_chuva", False)),
        "quantidade_chuva":     _norm(r.get("quantidade_chuva")),
        "houve_acidente":       bool(r.get("houve_acidente", False)),
        "descricao_acidente":   _norm(r.get("descricao_acidente")),
        "status":               _norm(r.get("status"), "Rascunho"),
        "view_token":           _norm(r.get("view_token")),
        "pdf_url":              _norm(r.get("pdf_url")),
        "ai_summary":           _norm(r.get("ai_summary")),
        "created_at":           _norm(r.get("created_at")),
    }


def _fmt_atividade(a: Dict) -> Dict:
    """Normaliza linha de rdo_atividades para o frontend.
    Schema real: atividade, quantidade, unidade, efetivo, observacao"""
    return {
        "id":           _norm(a.get("id")),
        "rdo_id":       _norm(a.get("rdo_id")),
        # frontend usa 'descricao' como label — mapeia de 'atividade'
        "descricao":    _norm(a.get("atividade")),
        "atividade":    _norm(a.get("atividade")),
        # pct_executado é a fonte canônica; fallback para quantidade quando unidade="%"
        "pct":          int(a.get("pct_executado") or 0) if a.get("pct_executado") is not None else (int(a.get("quantidade") or 0) if _is_pct(a) else 0),
        "quantidade":   float(a.get("quantidade") or 0),
        "unidade":      _norm(a.get("unidade")),
        "efetivo":      int(a.get("efetivo") or 0),
        "status":       _norm(a.get("observacao")),   # observacao = status/notas
        "observacao":   _norm(a.get("observacao")),
        "created_at":   _norm(a.get("created_at")),
        "is_extra":         bool(a.get("is_extra", False)),
        "atividade_id":     _norm(a.get("atividade_id")),
        "is_marco":         bool(a.get("is_marco", False)),
        "marco_concluido":  bool(a.get("marco_concluido", False)),
    }


def _is_pct(a: Dict) -> bool:
    """Heurística: se unidade é '%' ou vazia e quantidade <= 100, é percentual."""
    u = _norm(a.get("unidade"))
    q = float(a.get("quantidade") or 0)
    return (u in ("%", "") and 0 <= q <= 100)


def _fmt_evidencia(e: Dict) -> Dict:
    """Normaliza linha de rdo_evidencias para o frontend.
    Schema real: foto_url, legenda, tipo, exif_lat, exif_lng, exif_endereco"""
    return {
        "id":       _norm(e.get("id")),
        "rdo_id":   _norm(e.get("rdo_id")),
        "foto_url": _norm(e.get("foto_url")),
        "legenda":  _norm(e.get("legenda")),
        "tipo":     _norm(e.get("tipo"), "evidencia"),
        "lat":      float(e.get("exif_lat") or 0),
        "lng":      float(e.get("exif_lng") or 0),
        "address":  _norm(e.get("exif_endereco")),
        # aliases para compatibilidade
        "exif_lat":      float(e.get("exif_lat") or 0),
        "exif_lng":      float(e.get("exif_lng") or 0),
        "exif_endereco": _norm(e.get("exif_endereco")),
        "created_at":    _norm(e.get("created_at")),
    }


# ── Draft ─────────────────────────────────────────────────────────────────────

@router.get("/draft")
async def get_draft(
    contrato: str = Query(...),
    draft_id: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    if draft_id:
        # Continuar/editar RDO específico (qualquer status)
        rows = sb_select("rdo_master", filters={"id": draft_id}, limit=1) or []
    else:
        # Busca rascunho mais recente do contrato — ignora rascunhos vazios de datas passadas
        filters: Dict[str, Any] = {"contrato": contrato, "status": "Rascunho"}
        if client_id:
            filters["client_id"] = client_id
        candidates = sb_select("rdo_master", filters=filters, order="created_at.desc", limit=10) or []
        today_str = str(_date.today())
        rows = []
        for c in candidates:
            rdo_date = str(c.get("data", ""))[:10]
            # Descarta rascunhos de datas passadas que não têm atividades (fantasmas)
            if rdo_date < today_str:
                has_ats = sb_select("rdo_atividades", filters={"rdo_id": c["id"]}, limit=1) or []
                if not has_ats:
                    continue
            rows = [c]
            break

    if rows:
        r = rows[0]
        rdo_id = r["id"]
        atividades = sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=200) or []
        evidencias = sb_select("rdo_evidencias", filters={"rdo_id": rdo_id}, limit=100) or []
        return {
            "draft": _fmt_rdo(r),
            "atividades": [_fmt_atividade(a) for a in atividades],
            "evidencias": [_fmt_evidencia(e) for e in evidencias],
        }

    # Sem rascunho: calcula o próximo dia útil baseado nos dias_uteis do contrato
    next_rdo_date = str(_date.today())
    try:
        from backend.routers.hub import _add_working_days, _parse_dias_uteis
        # Busca o último RDO submetido para este contrato
        last_rdos = sb_select(
            "rdo_master",
            filters={"contrato": contrato, "status": "Submetido"},
            order="data.desc",
            limit=1,
        ) or []
        # Busca dias úteis do contrato para avançar corretamente
        contrato_row = sb_select("contratos", filters={"contrato": contrato}, limit=1) or []
        dias_str = contrato_row[0].get("dias_uteis_semana", "") if contrato_row else ""
        working_days = _parse_dias_uteis(dias_str)  # ex: {0,1,2,3,4,5} para seg-sab
        if last_rdos:
            last_date = str(last_rdos[0].get("data", ""))[:10]
            if last_date:
                # Avança 1 dia útil a partir do último RDO
                next_rdo_date = _add_working_days(last_date, 2, working_days)  # +2 porque _add_working_days é 1-based
    except Exception:
        pass

    return {"draft": None, "atividades": [], "evidencias": [], "next_rdo_date": next_rdo_date}


@router.post("/draft")
async def save_draft(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    draft_id = body.get("draft_id") or ""
    equipe = body.get("equipe_alocada", "") or ""
    try:
        equipe_int = int(equipe) if equipe else None
    except (ValueError, TypeError):
        equipe_int = None

    payload: Dict[str, Any] = {
        "contrato":            body.get("contrato", ""),
        "data":                body.get("data") or str(_date.today()),
        "projeto":             body.get("projeto", ""),
        "cliente":             body.get("cliente", ""),
        "localizacao":         body.get("localizacao", ""),
        # campo real na tabela é condicao_climatica
        "condicao_climatica":  body.get("clima", "Ensolarado"),
        "turno":               body.get("turno", "Diurno"),
        "tipo_tarefa":         body.get("tipo_tarefa", "Diário de Obra"),
        "orientacao":          body.get("orientacao", ""),
        "hora_inicio":         body.get("hora_inicio") or None,
        "hora_termino":        body.get("hora_termino") or None,
        "km_percorrido":       float(body.get("km_percorrido") or 0) or None,
        "houve_interrupcao":   bool(body.get("houve_interrupcao", False)),
        "motivo_interrupcao":  body.get("motivo_interrupcao", ""),
        "equipe_alocada":      equipe_int,
        "observacoes":         body.get("observacoes", ""),
        "checkin_lat":         body.get("checkin_lat", 0.0),
        "checkin_lng":         body.get("checkin_lng", 0.0),
        "checkin_endereco":    body.get("checkin_endereco", ""),
        "checkin_timestamp":   body.get("checkin_timestamp") or None,
        "checkout_lat":        body.get("checkout_lat", 0.0),
        "checkout_lng":        body.get("checkout_lng", 0.0),
        "checkout_endereco":   body.get("checkout_endereco", ""),
        "checkout_timestamp":  body.get("checkout_timestamp") or None,
        "signatory_name":      body.get("signatory_name", ""),
        "signatory_doc":       body.get("signatory_doc", ""),
        "houve_chuva":         bool(body.get("houve_chuva", False)),
        "quantidade_chuva":    body.get("quantidade_chuva", ""),
        "houve_acidente":      bool(body.get("houve_acidente", False)),
        "descricao_acidente":  body.get("descricao_acidente", ""),
        "status":              "Rascunho",
        "client_id":           client_id,
    }
    if draft_id:
        sb_update("rdo_master", filters={"id": draft_id}, data=payload)
        return {"ok": True, "draft_id": draft_id}
    else:
        row = sb_insert("rdo_master", payload)
        return {"ok": True, "draft_id": row.get("id", "") if isinstance(row, dict) else ""}


@router.delete("/draft/{draft_id}")
async def delete_draft(draft_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("rdo_atividades", filters={"rdo_id": draft_id})
    sb_delete("rdo_evidencias", filters={"rdo_id": draft_id})
    sb_delete("rdo_master", filters={"id": draft_id})
    return {"ok": True}


# ── GPS ───────────────────────────────────────────────────────────────────────

@router.post("/geocode/reverse")
async def geocode_reverse(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    lat = float(body.get("lat", 0))
    lng = float(body.get("lng", 0))
    loop = asyncio.get_event_loop()
    address = await loop.run_in_executor(_executor, reverse_geocode, lat, lng)
    return {"address": address, "lat": lat, "lng": lng}


# ── Atividades ────────────────────────────────────────────────────────────────

@router.get("/{rdo_id}/atividades")
async def list_atividades(rdo_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=200) or []
    return {"atividades": [_fmt_atividade(a) for a in rows]}


@router.post("/{rdo_id}/atividades")
async def add_atividade(
    rdo_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Schema rdo_atividades: atividade, quantidade, unidade, efetivo, observacao"""
    descricao  = body.get("descricao", "")
    pct        = int(body.get("pct", 0))
    status     = body.get("status", "Em andamento")
    is_extra   = bool(body.get("is_extra", False))  # atividade não mapeada no cronograma
    atividade_id = body.get("atividade_id") or None  # link ao hub_atividades

    # Se há unidade específica, quantidade = qtd_executada (produção do dia); senão quantidade = pct
    unidade = body.get("unidade", "") or ""
    if unidade and unidade != "%":
        quantidade = float(body.get("qtd_executada") or 0)
    else:
        quantidade = float(pct)
        unidade = "%"

    is_marco        = bool(body.get("is_marco", False))
    marco_concluido = bool(body.get("marco_concluido", False))

    payload = {
        "rdo_id":           rdo_id,
        "atividade":        descricao,
        "quantidade":       quantidade,
        "unidade":          unidade,
        "efetivo":          int(body.get("efetivo") or 0),
        "observacao":       status,
        "is_extra":         is_extra,
        "atividade_id":     atividade_id,
        "is_marco":         is_marco,
        "marco_concluido":  marco_concluido,
        "pct_executado":    pct,
    }
    row = sb_insert("rdo_atividades", payload)
    return {"ok": True, "row": _fmt_atividade(row) if isinstance(row, dict) else row}


@router.patch("/{rdo_id}/atividades/{at_id}")
async def update_atividade(
    rdo_id: str,
    at_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if "descricao" in body:
        data["atividade"] = body["descricao"]
    if "pct" in body:
        data["quantidade"] = float(body["pct"])
        data["pct_executado"] = int(body["pct"])
        if body.get("unidade", "%") == "%":
            data["unidade"] = "%"
    if "status" in body:
        data["observacao"] = body["status"]
    if "efetivo" in body:
        data["efetivo"] = int(body["efetivo"] or 0)
    if "qtd_executada" in body and body.get("unidade", "%") != "%":
        data["quantidade"] = float(body["qtd_executada"] or 0)
        data["unidade"] = body.get("unidade", "")
    if "marco_concluido" in body:
        data["marco_concluido"] = bool(body["marco_concluido"])
        # Garante que is_marco fica true quando marcando conclusão
        data["is_marco"] = True
    if "is_marco" in body:
        data["is_marco"] = bool(body["is_marco"])
    if "quantidade" in body and "pct" not in body and "qtd_executada" not in body:
        data["quantidade"] = float(body["quantidade"] or 0)
    sb_update("rdo_atividades", filters={"id": at_id, "rdo_id": rdo_id}, data=data)
    return {"ok": True}


@router.delete("/{rdo_id}/atividades/{at_id}")
async def delete_atividade(rdo_id: str, at_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("rdo_atividades", filters={"id": at_id, "rdo_id": rdo_id})
    return {"ok": True}


# ── Evidências (fotos) ────────────────────────────────────────────────────────

@router.post("/{rdo_id}/evidencias")
async def upload_evidencia(
    rdo_id: str,
    file: UploadFile = File(...),
    legenda: str = Form(""),
    tipo: str = Form("evidencia"),
    exif_lat: float = Form(0.0),
    exif_lng: float = Form(0.0),
    checkin_lat: float = Form(0.0),
    checkin_lng: float = Form(0.0),
    contrato: str = Form(""),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    img_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"

    loop = asyncio.get_event_loop()

    exif_data = await loop.run_in_executor(_executor, extract_exif_full, img_bytes)
    exif_lat_real, exif_lng_real, exif_dt = exif_data

    lat = exif_lat_real if exif_lat_real else (exif_lat or checkin_lat)
    lng = exif_lng_real if exif_lng_real else (exif_lng or checkin_lng)

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    local_str = exif_dt.strftime("%d/%m/%Y %H:%M:%S") if exif_dt else now_str

    address = ""
    map_bytes = None
    if lat and lng:
        address, map_bytes = await asyncio.gather(
            loop.run_in_executor(_executor, reverse_geocode, lat, lng),
            loop.run_in_executor(_executor, fetch_map_thumbnail, lat, lng),
        )

    meta = {
        "rede_time":  now_str,
        "local_time": local_str,
        "lat": lat, "lng": lng,
        "address": address,
        "contrato": contrato,
        "map_bytes": map_bytes,
    }
    watermarked = await loop.run_in_executor(_executor, apply_watermark, img_bytes, meta, content_type)

    from backend.integrations.supabase import sb_storage_upload
    ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
    path = f"{rdo_id}/{rdo_id}_{len(img_bytes)}.{ext}"
    url = sb_storage_upload("rdo-evidencias", path, watermarked, content_type) or ""

    valid_tipos = {"epi", "evidencia", "ferramentas"}
    tipo_safe = tipo if tipo in valid_tipos else "evidencia"

    row = sb_insert("rdo_evidencias", {
        "rdo_id":        rdo_id,
        "foto_url":      url,
        "legenda":       legenda,
        "exif_lat":      lat,
        "exif_lng":      lng,
        "exif_endereco": address,
        "content_type":  content_type,
        "tipo":          tipo_safe,
    })
    return {"ok": True, "row": _fmt_evidencia(row) if isinstance(row, dict) else row, "url": url}


@router.delete("/{rdo_id}/evidencias/{ev_id}")
async def delete_evidencia(rdo_id: str, ev_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("rdo_evidencias", filters={"id": ev_id, "rdo_id": rdo_id})
    return {"ok": True}


@router.patch("/{rdo_id}/evidencias/{ev_id}")
async def update_evidencia_legenda(
    rdo_id: str,
    ev_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    sb_update("rdo_evidencias", filters={"id": ev_id, "rdo_id": rdo_id}, data={"legenda": body.get("legenda", "")})
    return {"ok": True}


# ── Submit ────────────────────────────────────────────────────────────────────

@router.post("/{rdo_id}/submit")
async def submit_rdo(
    rdo_id: str,
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    view_token = generate_view_token()
    sig_b64    = body.get("signatory_sig_b64", "")
    updates    = {
        "status":            "Submetido",
        "view_token":        view_token,
        "signatory_name":    body.get("signatory_name", ""),
        "signatory_doc":     body.get("signatory_doc", ""),
        "signatory_sig_b64": sig_b64,
        "updated_at":        datetime.utcnow().isoformat(),
    }
    sb_update("rdo_master", filters={"id": rdo_id}, data=updates)

    # ── RDO → Cronograma ─────────────────────────────────────────────────────
    # rdo_atividades não tem atividade_id (link ao hub), mas buscamos via nome
    # A integração real usa a tabela hub_atividades: busca por nome de atividade + contrato
    master_rows = sb_select("rdo_master", filters={"id": rdo_id}, limit=1) or []
    contrato = master_rows[0].get("contrato", "") if master_rows else ""

    if contrato:
        atividades_rdo = sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=200) or []
        today_str = str(_date.today())
        # data_rdo é a data do dia de obra — pode ser diferente de today (RDO retroativo)
        rdo_data_str = str(master_rows[0].get("data") or today_str)[:10] if master_rows else today_str
        _affected_parents: set = set()  # track parents that need % rollup

        for at in atividades_rdo:
            if at.get("is_extra"):
                continue  # extras são tratados no bloco seguinte
            atividade_nome  = _norm(at.get("atividade"))
            unidade_at      = _norm(at.get("unidade"))
            is_marco        = bool(at.get("is_marco", False))
            marco_concluido = bool(at.get("marco_concluido", False))
            # Fallback: se is_marco e observacao indica conclusão, tratar como concluído
            if is_marco and not marco_concluido:
                obs_lower = _norm(at.get("observacao")).lower()
                if obs_lower in ("concluída", "concluida", "concluído", "concluido", "100%"):
                    marco_concluido = True

            # quantidade armazenada: para %, é o pct; para física, é qtd_executada
            if unidade_at == "%":
                quantidade = float(at.get("quantidade") or 0)
            else:
                # campo "quantidade" na tabela JÁ guarda o qtd_executada para unidades físicas
                quantidade = float(at.get("quantidade") or 0)

            if not atividade_nome:
                continue

            # Preferência: atividade_id direto (novo fluxo); fallback: busca por nome
            hub_rows = []
            if at.get("atividade_id"):
                # Busca pelo ID diretamente — sem client_id pois hub_atividades pode não ter client_id preenchido
                hub_rows = sb_select("hub_atividades", filters={"id": at["atividade_id"]}, limit=1) or []
            if not hub_rows:
                hub_rows = sb_select(
                    "hub_atividades",
                    filters={"contrato": contrato},
                    raw_filters={"atividade": f"ilike.*{atividade_nome[:40]}*"},
                    limit=1,
                ) or []

            if not hub_rows:
                continue

            hub = hub_rows[0]
            hub_id = hub["id"]
            pct_atual = int(hub.get("conclusao_pct") or 0)
            cur_status = str(hub.get("status_atividade") or "")
            efetivo_at = int(at.get("efetivo") or 0)
            if hub.get("parent_id"):
                _affected_parents.add((hub["parent_id"], contrato))

            # Verifica se tem sub-atividades — se sim, % é driven by subs
            has_subs = bool(sb_select("hub_atividades", filters={"parent_id": hub_id}, limit=1) or [])

            hub_update: Dict[str, Any] = {"last_rdo_date": rdo_data_str}
            novo_pct = pct_atual
            producao_dia = None
            novo_exec = None
            unidade_hist = str(hub.get("unidade") or "")

            # ── Marco concluído → 100% imediato + exec_qty = total_qty para display correto ─
            if is_marco and marco_concluido:
                novo_pct = 100
                if not has_subs:
                    hub_update["conclusao_pct"] = 100
                    # Garante exec_qty = total_qty para que o cronograma mostre corretamente
                    total_qty_hub = float(hub.get("total_qty") or 1)
                    hub_update["exec_qty"] = total_qty_hub if total_qty_hub > 0 else 1.0
            # ── Percentual direto (não marco) ─────────────────────────────────
            elif unidade_at == "%" and quantidade > pct_atual:
                novo_pct = min(100, int(quantidade))
                if not has_subs:
                    hub_update["conclusao_pct"] = novo_pct
            # ── Quantidade física → incrementa exec_qty ───────────────────────
            elif unidade_at not in ("%", "marco", "") and quantidade > 0:
                exec_atual = float(hub.get("exec_qty") or 0)
                total_qty  = float(hub.get("total_qty") or 0)
                novo_exec  = exec_atual + quantidade
                producao_dia = quantidade
                unidade_hist = unidade_at
                hub_update["exec_qty"] = novo_exec
                if total_qty > 0 and not has_subs:
                    calc_pct = min(100, int(novo_exec / total_qty * 100))
                    if calc_pct > pct_atual:
                        novo_pct = calc_pct
                        hub_update["conclusao_pct"] = novo_pct

            # ── Auto-transiciona status_atividade ─────────────────────────────
            if novo_pct >= 100 and not has_subs:
                hub_update["status_atividade"] = "concluida"
            elif novo_pct > 0 and cur_status in ("nao_iniciada", "pronta_iniciar", "Não Iniciada", ""):
                hub_update["status_atividade"] = "em_execucao"

            # ── Registra efetivo alocado ──────────────────────────────────────
            if efetivo_at > 0:
                hub_update["efetivo_alocado"] = efetivo_at

            sb_update("hub_atividades", filters={"id": hub_id}, data=hub_update)

            # ── Histórico completo (auditoria) ────────────────────────────────
            hist: Dict[str, Any] = {
                "atividade_id":           hub_id,
                "contrato":               contrato,
                "conclusao_pct_novo":     novo_pct,
                "conclusao_pct_anterior": pct_atual,
                "rdo_id":                 rdo_id,
                "data":                   rdo_data_str,
                "created_at":             datetime.utcnow().isoformat(),
                "client_id":              client_id,
            }
            if producao_dia is not None:
                hist["producao_dia"] = producao_dia
            if novo_exec is not None:
                hist["exec_qty_novo"] = novo_exec
                total_qty_h = float(hub.get("total_qty") or 0)
                if total_qty_h:
                    hist["total_qty"] = total_qty_h
            if unidade_hist:
                hist["unidade"] = unidade_hist
            sb_insert("hub_atividade_historico", hist)

        # ── Atividades extras (não mapeadas) → pendentes de aprovação no hub ────
        for at in atividades_rdo:
            if not at.get("is_extra"):
                continue
            atividade_nome = _norm(at.get("atividade"))
            if not atividade_nome:
                continue
            # Cria no hub como pendente de aprovação — gestor completa macro, fase, datas
            try:
                sb_insert("hub_atividades", {
                    "contrato":           contrato,
                    "atividade":          atividade_nome,
                    "nivel":              "micro",
                    "status_atividade":   "Pendente Aprovação",
                    "conclusao_pct":      0,
                    "exec_qty":           float(at.get("quantidade") or 0),
                    "unidade":            _norm(at.get("unidade")),
                    "fase":               "Extra",
                    "fase_macro":         "Não Mapeada",
                    "last_rdo_date":      today_str,
                    "observacoes":        f"Registrada via RDO {rdo_id} — aguarda aprovação do gestor",
                    "client_id":          client_id,
                })
            except Exception:
                pass

        # ── Rollup % para macros afetadas ────────────────────────────────────
        try:
            from backend.routers.hub import _recalc_parent_dates, _cronograma_cache_key
            from backend.core.redis_cache import cache_invalidate
            for parent_id, cont in _affected_parents:
                _recalc_parent_dates(parent_id, cont, client_id or "")
            # Invalida cache do cronograma — dados mudaram com o RDO
            cache_invalidate(client_id or "global", _cronograma_cache_key(contrato))
            # Invalida DataLoader (contratos/dashboard) para o hub refletir imediatamente
            from backend.core.data_loader import DataLoader
            DataLoader.invalidate_cache(client_id or "")
        except Exception:
            pass


        # ── Pipeline background: Insights + IA + PDF + Email ────────────────────
        # Tudo em thread daemon — não bloqueia o response ao usuário
        # Re-fetch para garantir que temos o registro com status=Submetido e view_token
        fresh_rows = sb_select("rdo_master", filters={"id": rdo_id}, limit=1) or master_rows
        rdo_row_snap = dict(fresh_rows[0]) if fresh_rows else {}
        if not rdo_row_snap:
            logger.warning(f"submit_rdo: rdo_row_snap vazio para rdo_id={rdo_id} — pipeline background abortado")
        rdo_row_snap["data_rdo"] = str(rdo_row_snap.get("data", today_str))[:10]
        atividades_snap = list(sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=200) or [])
        evidencias_snap = list(sb_select("rdo_evidencias", filters={"rdo_id": rdo_id}, limit=100) or [])
        # Filtra subscribers pelo client_id para evitar vazamento entre tenants
        _subs_all = sb_select("email_sender", filters={"contract": contrato, "module": "rdo"}, limit=50) or []
        if client_id:
            # Inclui subscribers sem client_id (legado) e do tenant correto
            subs = [s for s in _subs_all if not s.get("client_id") or s.get("client_id") == client_id]
        else:
            subs = _subs_all
        email_list = [s["email"] for s in subs if s.get("email")]

        import threading as _threading
        from backend.core.config import Config as _Config

        _contrato_bg = contrato
        _client_id_bg = client_id
        _rdo_id_bg = rdo_id

        def _background_pipeline():
            _ai_summary = ""
            _pdf_path = ""
            _pdf_url = ""

            # 1. IA — gera ai_summary primeiro (dados do RDO frescos)
            try:
                _ai_summary = _generate_ai_summary_sync(rdo_row_snap, atividades_snap, _client_id_bg or "")
                if _ai_summary:
                    sb_update("rdo_master", filters={"id": _rdo_id_bg}, data={"ai_summary": _ai_summary})
            except Exception as _e:
                import logging as _log
                _log.getLogger("rdo").warning(f"AI summary falhou: {_e}")

            # 2. Insights do cronograma — depois da IA, com last_rdo_id=rdo_id para o view detectar
            try:
                _trigger_insights(_contrato_bg, _rdo_id_bg, _client_id_bg)
            except Exception as _e:
                import logging as _log
                _log.getLogger("rdo").warning(f"Insights falhou: {_e}")

            # 3. PDF — gera com ai_summary já disponível no banco
            _pdf_bytes_bg: bytes = b""
            try:
                from backend.workers.tasks.pdf_tasks import generate_rdo_pdf as _pdf_task
                _result = _pdf_task.run(rdo_id=_rdo_id_bg, client_id=_client_id_bg or "")
                if isinstance(_result, dict):
                    _pdf_url       = _result.get("pdf_url", "")
                    _pdf_path      = _result.get("pdf_path", "")
                    _pdf_bytes_bg  = _result.get("pdf_bytes") or b""
            except Exception as _e:
                import logging as _log
                _log.getLogger("rdo").warning(f"PDF falhou: {_e}")

            # 4. Email executivo (com atividades, ai_summary, pdf anexado, link view)
            if email_list:
                try:
                    from backend.integrations.email import send_rdo_executivo
                    _view_url = f"{_Config.APP_URL}/rdo/{view_token}"
                    send_rdo_executivo(
                        to_emails=email_list,
                        rdo=rdo_row_snap,
                        atividades=atividades_snap,
                        ai_summary=_ai_summary,
                        view_url=_view_url,
                        pdf_path=_pdf_path,
                        pdf_bytes=_pdf_bytes_bg or None,
                    )
                except Exception as _e:
                    import logging as _log
                    _log.getLogger("rdo").error(f"Email executivo falhou: {_e}")

        if rdo_row_snap:
            _threading.Thread(target=_background_pipeline, daemon=True).start()

        # ── Alertas reativos — check event hooks ─────────────────────────────
        try:
            from backend.workers.tasks.alert_tasks import check_alert_event
            check_alert_event.delay(
                event_type="rdo_submitted",
                contrato=contrato,
                client_id=client_id or "",
                metadata={"rdo_id": rdo_id},
            )
        except Exception:
            pass  # Celery optional — alerts won't fire but RDO submit succeeds

    audit_log(
        category=AuditCategory.RDO_CREATE,
        action=f"RDO submetido: {rdo_id} — contrato {contrato}",
        username=user.get("login", ""),
        entity_type="rdo_master",
        entity_id=rdo_id,
        client_id=str(client_id or ""),
        metadata={"contrato": contrato, "view_token": view_token},
    )

    return {"ok": True, "view_token": view_token}


def _generate_ai_summary_sync(rdo: Dict[str, Any], atividades: list, client_id: str) -> str:
    """Gera ai_summary para o RDO usando OpenAI. Chamado em thread — não bloqueia response."""
    try:
        from backend.integrations.ai import query as _ai_query

        contrato = rdo.get("contrato", "")
        data_rdo = str(rdo.get("data") or rdo.get("data_rdo") or "")[:10]
        clima = str(rdo.get("condicao_climatica") or rdo.get("clima") or "")
        chuva = "Sim" if rdo.get("houve_chuva") else "Não"
        interrupcao = str(rdo.get("motivo_interrupcao") or "") if rdo.get("houve_interrupcao") else "Não houve"
        acidente = str(rdo.get("descricao_acidente") or "") if rdo.get("houve_acidente") else "Não houve"
        observacoes = str(rdo.get("observacoes") or "")
        orientacao = str(rdo.get("orientacao") or "")
        equipe = int(rdo.get("equipe_alocada") or 0)
        hora_i = str(rdo.get("hora_inicio") or "")[:5]
        hora_f = str(rdo.get("hora_termino") or "")[:5]

        # today_rdo: data do RDO — DEVE ser definida antes de qualquer cálculo de prazo
        try:
            today_rdo = _date.fromisoformat(data_rdo[:10])
        except Exception:
            today_rdo = _date.today()

        # Prazo e valor do contrato (Tier 1)
        dias_restantes_rdo = ""
        valor_contrato_rdo = ""
        try:
            cinfo = sb_select("contratos", filters={"contrato": contrato}, limit=1) or []
            if cinfo:
                ci = cinfo[0]
                dt_fim = ci.get("data_termino") or ci.get("data_fim")
                if dt_fim:
                    d_fim_r = _date.fromisoformat(str(dt_fim)[:10])
                    dr = (d_fim_r - today_rdo).days
                    from backend.routers.hub import _working_days_between as _wdb_sum
                    du = _wdb_sum(today_rdo, d_fim_r)
                    dias_restantes_rdo = f"{dr}d corridos ({du} úteis) até {d_fim_r.strftime('%d/%m/%Y')}"
                v = float(ci.get("valor_contratado") or 0)
                if v > 0:
                    valor_contrato_rdo = f"R$ {v:,.0f}"
        except Exception:
            pass

        # Enriquece atividades com dados do cronograma
        hub_ativs = sb_select("hub_atividades", filters={"contrato": contrato}, limit=500) or []
        hub_by_id   = {str(h.get("id", "")): h for h in hub_ativs}
        hub_by_name = {str(h.get("atividade", "")).lower().strip(): h for h in hub_ativs}

        ativ_lines = []
        for at in atividades:
            nome       = str(at.get("atividade") or "").strip()
            qty        = at.get("quantidade", 0)
            unit       = str(at.get("unidade") or "")
            efetivo    = int(at.get("efetivo") or 0)
            is_marco   = bool(at.get("is_marco"))
            marco_conc = bool(at.get("marco_concluido"))

            ha        = hub_by_id.get(str(at.get("atividade_id") or "")) or hub_by_name.get(nome.lower().strip(), {})
            pct_atual = float(ha.get("conclusao_pct") or 0)
            ter       = str(ha.get("termino_previsto", "?"))[:10]
            ini       = str(ha.get("inicio_previsto", "?"))[:10]
            total_qty = float(ha.get("total_qty") or 0)
            exec_qty  = float(ha.get("exec_qty") or 0)
            critico   = str(ha.get("critico", "")).lower() in ("sim", "true", "1")

            # Posição dia X/Y e delta vs esperado (âncora = data do RDO)
            pct_esp_txt = ""
            saldo_txt   = ""
            try:
                from backend.routers.hub import _working_days_between as _wdb
                from datetime import timedelta as _td
                d_ini = _date.fromisoformat(ini)
                d_ter = _date.fromisoformat(ter)
                d_total_wd = max(1, _wdb(d_ini, d_ter + _td(days=1)))
                d_dec_wd   = min(d_total_wd, max(0, _wdb(d_ini, today_rdo + _td(days=1))))
                pct_esp    = round(d_dec_wd / d_total_wd * 100)
                delta      = round(pct_atual - pct_esp)
                status_p   = "ADIANTADO" if delta > 5 else "NO RITMO" if delta >= -5 else "ATRASADO"
                pct_esp_txt = f", dia {d_dec_wd}/{d_total_wd}, esp={pct_esp}%, acum={pct_atual:.0f}%, delta={delta:+d}% [{status_p}]"
                # Saldo físico para cálculo de efetivo mínimo pelo LLM
                if total_qty > 0 and delta < 0:
                    saldo = max(0.0, total_qty - exec_qty)
                    # Conta dias úteis APÓS o dia do RDO até a data de término (inclusive)
                    dias_restantes_at = _wdb(today_rdo + _td(days=1), d_ter + _td(days=1))
                    saldo_txt = f", saldo={saldo:.0f}{unit}, prazo em {dias_restantes_at}du restantes após hoje"
            except Exception:
                pass

            if is_marco:
                status_str = "MARCO CONCLUÍDO" if marco_conc else "marco pendente"
            elif unit == "%":
                status_str = f"{int(qty)}% executado hoje"
            elif total_qty > 0:
                status_str = f"{qty}{unit} hoje (acum: {exec_qty:.0f}/{total_qty:.0f}{unit})"
            else:
                status_str = f"{qty}{unit} executado"

            # Produtividade por pessoa — usa efetivo específico desta atividade no RDO
            prod_pessoa_txt = ""
            if efetivo > 0 and float(qty or 0) > 0 and unit not in ("%", "marco", ""):
                try:
                    pp = round(float(qty) / efetivo, 1)
                    prod_pessoa_txt = f", {pp}{unit}/pessoa"
                except Exception:
                    pass

            obs_campo  = str(at.get("observacao") or "").strip()
            obs_txt    = f"\n      Obs: \"{obs_campo[:120]}\"" if obs_campo else ""
            efetivo_txt = f" ({efetivo}p{prod_pessoa_txt})" if efetivo else ""

            ativ_lines.append(
                f"  - {nome}{efetivo_txt}: {status_str}{pct_esp_txt}{saldo_txt}, prazo={ter}"
                f"{' [CRÍTICO]' if critico else ''}{obs_txt}"
            )

        ativ_text = "\n".join(ativ_lines) or "  Nenhuma atividade registrada."

        _ex_neg = (
            "Ex: Vedacao (3p, 161un/pessoa): -13%, saldo=189un, 1du restante."
            " Efetivo min=ceil(189/161)=2p — atual tem 3p, suficiente se mantiver ritmo."
            " Fixacao (+3%) pode ceder 1p se necessario."
        )

        system_prompt = (
            "Você é um gestor sênior de obras escrevendo a análise executiva do RDO.\n\n"
            "REGRAS ABSOLUTAS:\n"
            "1. delta >= 0% = ADIANTADA/NO RITMO — NUNCA gere alerta de prazo.\n"
            "2. 'Obs campo' = voz do engenheiro — use para contextualizar desvios.\n"
            "3. Só alerte risco quando: delta < -5% E dias restantes insuficientes para recuperação natural.\n"
            "4. Tom executivo: objetivo, sem alarmismo, com números reais.\n\n"
            "OBRIGATÓRIO para atividades com delta negativo — CALCULE e APRESENTE:\n"
            "  a) Prod/pessoa/dia (informada no contexto como 'X un/pessoa')\n"
            "  b) Efetivo mínimo: ceil(saldo / (dias_restantes_úteis × prod/pessoa))\n"
            "  c) Fonte: há atividade adiantada que pode ceder pessoas? Recomende a realocação.\n"
            "  d) Use EXATAMENTE o campo 'prazo em Xdu restantes após hoje' — NUNCA recalcule dias a partir das datas brutas.\n"
            f"  {_ex_neg}\n\n"
            "FORMATO: 3-5 frases corridas em português:\n"
            "  Frase 1: balanço do dia (produtividade geral, condições, eficiência)\n"
            "  Frases 2-3: cada atividade — números reais, dia X/Y, delta, obs do campo\n"
            "  Frases 4-5: recomendação acionável com cálculo explícito de efetivo"
        )

        user_content = (
            f"DATA: {data_rdo} | CONTRATO: {contrato}\n"
            f"PRAZO: {dias_restantes_rdo or 'não informado'} | VALOR: {valor_contrato_rdo or 'não informado'}\n"
            f"CLIMA: {clima} | CHUVA: {chuva} | ACIDENTE: {acidente}\n"
            f"EQUIPE TOTAL: {equipe}p | HORÁRIO: {hora_i}–{hora_f}\n"
            f"INTERRUPÇÃO: {interrupcao}\n"
            f"OBS GERAIS: {observacoes}\n"
            f"ORIENTAÇÃO AMANHÃ: {orientacao}\n\n"
            "ATIVIDADES (efetivo | prod/pessoa | dia X/Y | esp% | delta [ritmo] | saldo | prazo):\n"
            f"{ativ_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ]
        summary = _ai_query(
            messages,
            max_tokens=600,
            temperature=0.3,
            client_id=client_id,
            prompt_preview=f"RDO summary {contrato} {data_rdo}",
        )
        summary = summary.strip() if summary else ""
        if summary:
            logger.info(f"AI summary gerado: rdo={str(rdo.get('id', ''))[:8]} chars={len(summary)}")
        return summary
    except Exception as e:
        logger.warning(f"_generate_ai_summary_sync falhou: {e}")
        return ""


def _trigger_insights(contrato: str, rdo_id: str, client_id: Optional[str]):
    """Gera e persiste insights de IA (LLM + velocity + anomalias + delta) após submit de RDO."""
    try:
        from datetime import date
        from backend.routers.hub import _build_insights_llm
        from backend.integrations.supabase import sb_select as _sb

        today        = date.today()
        # Busca SEM client_id para garantir que encontra o RDO recém submetido
        # (hub_atividades e rdo_master podem não ter client_id preenchido em todos os registros)
        atividades   = sb_select("hub_atividades",          filters={"contrato": contrato}, limit=500) or []
        rdo_recentes = sb_select("rdo_master",              filters={"contrato": contrato, "status": "Submetido"}, order="data.desc", limit=7) or []
        historico    = sb_select("hub_atividade_historico", filters={"contrato": contrato}, limit=300) or []
        contrato_rows_t = sb_select("contratos",           filters={"contrato": contrato}, limit=1) or []
        contrato_info_t = contrato_rows_t[0] if contrato_rows_t else {}

        existing     = sb_select("agente_insights", filters={"contrato": contrato}, limit=1) or []
        insights_ant = (existing[0].get("insights") or []) if existing else []

        insights = _build_insights_llm(atividades, rdo_recentes, contrato, today, historico, insights_ant, contrato_info=contrato_info_t)

        # Persiste no agente_insights (upsert por contrato)
        existing = sb_select("agente_insights", filters={"contrato": contrato}, limit=1) or []
        payload  = {
            "contrato":    contrato,
            "insights":    insights,
            "last_rdo_id": rdo_id,
            "updated_at":  datetime.utcnow().isoformat(),
            "client_id":   client_id,
        }
        if existing:
            sb_update("agente_insights", filters={"id": existing[0]["id"]}, data=payload)
        else:
            sb_insert("agente_insights", payload)

    except Exception as exc:
        import logging
        logging.getLogger("rdo").error(f"_trigger_insights error: {exc}")
        # Insights nunca devem bloquear o submit


# ── PDF Generation ────────────────────────────────────────────────────────────

@router.post("/{rdo_id}/generate-pdf")
async def generate_rdo_pdf(
    rdo_id: str,
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Gera PDF do RDO inline (fpdf2 é rápido, sem overhead de fila)."""
    loop = asyncio.get_event_loop()
    from backend.workers.tasks.pdf_tasks import generate_rdo_pdf as _gen
    result = await loop.run_in_executor(
        None,
        lambda: _gen.run(rdo_id=rdo_id, client_id=client_id or ""),
    )
    return result


# ── Histórico ─────────────────────────────────────────────────────────────────

@router.get("/historico")
async def list_historico(
    contrato: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, le=100),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if contrato:
        filters["contrato"] = contrato
    if client_id:
        filters["client_id"] = client_id

    raw_filters: Dict[str, str] = {}
    if status and status != "Todos":
        filters["status"] = status
    if date_from:
        raw_filters["data"] = f"gte.{date_from}"
    if date_to:
        if "data" in raw_filters:
            pass
        raw_filters["data"] = f"lte.{date_to}" if not date_from else raw_filters.get("data", "")

    # Simple approach: fetch enough rows and filter/paginate in python
    rows = sb_select("rdo_master", filters=filters, order="data.desc", limit=500, raw_filters=raw_filters) or []

    # Client-side date range if both provided
    if date_from and date_to:
        rows = [r for r in rows if date_from <= str(r.get("data", ""))[:10] <= date_to]
    elif date_from:
        rows = [r for r in rows if str(r.get("data", ""))[:10] >= date_from]
    elif date_to:
        rows = [r for r in rows if str(r.get("data", ""))[:10] <= date_to]

    total    = len(rows)
    offset   = (page - 1) * page_size
    page_rows = rows[offset: offset + page_size]
    has_next = (offset + page_size) < total

    return {
        "rdos":     [_fmt_rdo(r) for r in page_rows],
        "has_next": has_next,
        "page":     page,
        "total":    total,
    }


# ── Contratos do tenant (para dropdowns) ──────────────────────────────────────

@router.get("/contratos")
async def list_rdo_contratos(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Lista todos os contratos do tenant — busca direta, sem cache, para dropdowns."""
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("contratos", filters=filters, limit=500) or []
    contratos = sorted({
        str(r.get("contrato") or "").strip()
        for r in rows
        if r.get("contrato")
    })
    return {"contratos": contratos}


# ── Subscribers (notificações por e-mail) ─────────────────────────────────────

@router.get("/subscribers")
async def list_subscribers(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    # Filtra por contrato + module; client_id é opcional
    filters: Dict[str, Any] = {"contract": contrato, "module": "rdo"}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("email_sender", filters=filters, limit=100) or []
    # Fallback sem client_id para usuários RDO sem tenant definido
    if not rows and client_id:
        rows = sb_select("email_sender", filters={"contract": contrato, "module": "rdo"}, limit=100) or []
    return {"subscribers": [{"id": r["id"], "email": r["email"]} for r in rows]}


@router.post("/subscribers")
async def add_subscriber(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    from datetime import datetime as _dt
    contrato = body.get("contrato", "").strip()
    email    = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        return JSONResponse(status_code=400, content={"error": "E-mail inválido"})
    if not contrato:
        return JSONResponse(status_code=400, content={"error": "Selecione um contrato antes de adicionar o e-mail"})

    # Constraint real: UNIQUE(module, email, contract) — mesmo email pode ter contratos diferentes
    existing = sb_select(
        "email_sender",
        filters={"module": "rdo", "email": email, "contract": contrato},
        limit=1,
    ) or []
    if existing:
        return {"ok": True, "id": existing[0]["id"], "info": "já cadastrado para este contrato"}

    try:
        row = sb_insert("email_sender", {
            "contract":    contrato,
            "module":      "rdo",
            "email":       email,
            "created_by":  str(user.get("email") or user.get("username") or user.get("id") or "sistema"),
            "updated_date": _dt.now().isoformat(),
            "client_id":   client_id or None,
        })
    except ValueError as exc:
        err_str = str(exc)
        if "23505" in err_str or "already exists" in err_str:
            # Race condition — busca o existente e retorna ok
            dup = sb_select("email_sender", filters={"module": "rdo", "email": email, "contract": contrato}, limit=1) or []
            return {"ok": True, "id": dup[0]["id"] if dup else None, "info": "já cadastrado"}
        return JSONResponse(status_code=400, content={"error": f"Erro ao salvar: {err_str[:200]}"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)[:200]})

    if row is None:
        return JSONResponse(status_code=500, content={"error": "Falha ao salvar — tabela email_sender pode estar ausente"})
    return {"ok": True, "id": row.get("id") if isinstance(row, dict) else None}


@router.delete("/subscribers/{sub_id}")
async def delete_subscriber(
    sub_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    sb_delete("email_sender", filters={"id": sub_id})
    return {"ok": True}


# ── View público (sem auth) ───────────────────────────────────────────────────

@router.get("/view/{view_token}")
async def view_rdo_public(view_token: str) -> Dict[str, Any]:
    rows = sb_select("rdo_master", filters={"view_token": view_token}, limit=1) or []
    if not rows:
        return JSONResponse(status_code=404, content={"error": "RDO não encontrado"})
    r = rows[0]
    rdo_id   = r["id"]
    contrato = r.get("contrato", "")

    atividades = sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=200) or []
    evidencias = sb_select("rdo_evidencias", filters={"rdo_id": rdo_id}, limit=100) or []

    # Enriquecer atividades com status atual do cronograma (hub_atividades)
    if contrato and atividades:
        hub_ativs = sb_select("hub_atividades", filters={"contrato": contrato}, limit=500) or []
        hub_by_id:   Dict[str, Dict] = {str(ha.get("id", "")): ha for ha in hub_ativs}
        hub_by_name: Dict[str, Dict] = {}
        for ha in hub_ativs:
            nome = _norm(ha.get("atividade")).lower().strip()
            if nome:
                hub_by_name[nome] = ha

        enriched = []
        for at in atividades:
            fmt = _fmt_atividade(at)
            # Lookup priority: atividade_id direto > nome fuzzy
            ha = hub_by_id.get(str(at.get("atividade_id") or ""))
            if not ha:
                nome_lower = _norm(at.get("atividade")).lower().strip()
                ha = hub_by_name.get(nome_lower)
            if ha:
                conclusao_pct = int(ha.get("conclusao_pct") or 0)
                status_at = _norm(ha.get("status_atividade"))
                exec_qty  = float(ha.get("exec_qty") or 0)
                total_qty = float(ha.get("total_qty") or 0)
                fmt["conclusao_pct"]     = conclusao_pct
                fmt["status_cronograma"] = status_at
                fmt["pct"]               = conclusao_pct
                fmt["exec_qty"]          = exec_qty
                fmt["total_qty"]         = total_qty
                fmt["unidade"]           = _norm(ha.get("unidade")) or fmt["unidade"]
                fmt["termino_previsto"]  = _norm(ha.get("termino_previsto"))
                fmt["critico"]           = str(ha.get("critico", "")).lower() in ("sim", "true", "1")
                # Produtividade: desvio simples exec_qty vs pct_esperado×total_qty
                try:
                    from datetime import date as _d, timedelta as _td
                    from backend.routers.hub import _working_days_between as _wdb
                    _ini = str(ha.get("inicio_previsto") or "")[:10]
                    _ter = str(ha.get("termino_previsto") or "")[:10]
                    # Usa a DATA DO RDO como referência — não today.
                    # O RDO é uma foto do dia de obra; today distorceria o % esperado.
                    _rdo_date_str = str(r.get("data", ""))[:10]
                    try:
                        _ref_date = _d.fromisoformat(_rdo_date_str)
                    except Exception:
                        _ref_date = _d.today()
                    if _ini and _ter:
                        _d_ini = _d.fromisoformat(_ini)
                        _d_ter = _d.fromisoformat(_ter)
                        _total_wd = max(1, _wdb(_d_ini, _d_ter + _td(days=1)))
                        _dec_wd   = min(_total_wd, max(0, _wdb(_d_ini, _ref_date + _td(days=1))))
                        _pct_esp  = round(_dec_wd / _total_wd * 100)
                        fmt["pct_esperado"] = _pct_esp
                        fmt["dia_x"]        = _dec_wd
                        fmt["dia_total"]    = _total_wd
                        fmt["delta_pct"]    = round(conclusao_pct - _pct_esp)
                        if total_qty > 0 and _pct_esp > 0:
                            cum_plan = total_qty * _pct_esp / 100
                            fmt["prod_pct"] = round(exec_qty / cum_plan * 100) if cum_plan > 0 else None
                        else:
                            fmt["prod_pct"] = None
                    else:
                        fmt["pct_esperado"] = None
                        fmt["prod_pct"] = None
                        fmt["dia_x"] = None
                        fmt["dia_total"] = None
                        fmt["delta_pct"] = None
                except Exception:
                    fmt["pct_esperado"] = None
                    fmt["prod_pct"] = None
                    fmt["dia_x"] = None
                    fmt["dia_total"] = None
                    fmt["delta_pct"] = None
            else:
                # Atividade extra (não mapeada): usa o pct do próprio RDO
                raw_pct = int(float(at.get("quantidade") or 0)) if _is_pct(at) else 0
                fmt["conclusao_pct"]    = raw_pct
                fmt["pct"]              = raw_pct
                fmt["status_cronograma"] = "Não mapeada"
            enriched.append(fmt)
        atividades_fmt = enriched
    else:
        atividades_fmt = [_fmt_atividade(a) for a in atividades]

    # Busca insights do agente para esse contrato
    # Só usa insights do agente se foram gerados a partir deste RDO (last_rdo_id bate)
    # — evita mostrar insights stale de antes do submit quando o pipeline ainda não terminou
    insight_rows = sb_select("agente_insights", filters={"contrato": contrato}, limit=1) or []
    insights = []
    if insight_rows:
        row_ins = insight_rows[0]
        # Só exibe se os insights foram gerados incluindo este RDO
        if str(row_ins.get("last_rdo_id") or "") == str(rdo_id):
            raw = row_ins.get("insights") or []
            insights = raw if isinstance(raw, list) else []

    # Fallback: ai_summary do próprio RDO (gerado após IA terminar)
    if not insights and r.get("ai_summary"):
        insights = [{
            "priority": "Low",
            "title":    "Análise do dia",
            "body":     str(r["ai_summary"]),
        }]
    # Último fallback: insights anteriores do contrato mesmo sem bater o rdo_id
    # (melhor que mostrar "Nenhum RDO submetido")
    if not insights and insight_rows:
        raw = insight_rows[0].get("insights") or []
        candidate = raw if isinstance(raw, list) else []
        # Filtra o insight de "sem RDO" — não faz sentido mostrar após submit
        insights = [i for i in candidate if "nenhum rdo" not in str(i.get("body", "")).lower()
                    and "envie o primeiro" not in str(i.get("body", "")).lower()]

    return {
        "rdo":        _fmt_rdo(r),
        "atividades": atividades_fmt,
        "evidencias": [_fmt_evidencia(e) for e in evidencias],
        "insights":   insights,
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def rdo_dashboard(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("rdo_master", filters=filters, order="data.desc", limit=200) or []
    total      = len(rows)
    submetidos = sum(1 for r in rows if r.get("status") == "Submetido")
    rascunhos  = sum(1 for r in rows if r.get("status") == "Rascunho")
    com_inter  = sum(1 for r in rows if r.get("houve_interrupcao"))
    return {
        "total":           total,
        "submetidos":      submetidos,
        "rascunhos":       rascunhos,
        "com_interrupcao": com_inter,
        "rdos_recentes":   [_fmt_rdo(r) for r in rows[:5]],
    }
