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
from backend.services.rdo_service import (
    apply_watermark,
    extract_exif_full,
    fetch_map_thumbnail,
    generate_view_token,
    haversine_m,
    reverse_geocode,
)

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
        # frontend usa 'pct' — armazenamos em 'quantidade' (0-100 para percentual)
        "pct":          int(a.get("quantidade") or 0) if _is_pct(a) else 0,
        "quantidade":   float(a.get("quantidade") or 0),
        "unidade":      _norm(a.get("unidade")),
        "efetivo":      int(a.get("efetivo") or 0),
        "status":       _norm(a.get("observacao")),   # observacao = status/notas
        "observacao":   _norm(a.get("observacao")),
        "created_at":   _norm(a.get("created_at")),
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
        # Busca rascunho mais recente do contrato
        filters: Dict[str, Any] = {"contrato": contrato, "status": "Rascunho"}
        if client_id:
            filters["client_id"] = client_id
        rows = sb_select("rdo_master", filters=filters, order="created_at.desc", limit=1) or []

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
    return {"draft": None, "atividades": [], "evidencias": []}


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
) -> Dict[str, Any]:
    """Schema rdo_atividades: atividade, quantidade, unidade, efetivo, observacao"""
    descricao = body.get("descricao", "")
    pct       = int(body.get("pct", 0))
    status    = body.get("status", "Em andamento")
    efetivo   = int(body.get("efetivo") or body.get("qtd_executada") or 0) if not body.get("unidade") else 0

    # Se há unidade específica, quantidade = qtd_executada; senão quantidade = pct
    unidade = body.get("unidade", "") or ""
    if unidade and unidade != "%":
        quantidade = float(body.get("qtd_executada") or body.get("pct") or 0)
    else:
        quantidade = float(pct)
        unidade = "%"

    payload = {
        "rdo_id":    rdo_id,
        "atividade": descricao,
        "quantidade": quantidade,
        "unidade":   unidade,
        "efetivo":   int(body.get("efetivo") or 0),
        "observacao": status,
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
    if "status" in body:
        data["observacao"] = body["status"]
    if "efetivo" in body:
        data["efetivo"] = int(body["efetivo"] or 0)
    if "qtd_executada" in body and body.get("unidade", "%") != "%":
        data["quantidade"] = float(body["qtd_executada"] or 0)
        data["unidade"] = body.get("unidade", "")
    row = sb_update("rdo_atividades", filters={"id": at_id, "rdo_id": rdo_id}, data=data)
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

        for at in atividades_rdo:
            atividade_nome = _norm(at.get("atividade"))
            quantidade     = float(at.get("quantidade") or 0)
            unidade_at     = _norm(at.get("unidade"))

            if not atividade_nome:
                continue

            # Busca atividade no hub pelo nome + contrato
            hub_rows = sb_select(
                "hub_atividades",
                filters={"contrato": contrato},
                raw_filters={"atividade": f"ilike.*{atividade_nome[:40]}*"},
                limit=1,
                client_id=client_id,
            ) or []

            if not hub_rows:
                continue

            hub = hub_rows[0]
            hub_id = hub["id"]
            pct_atual = int(hub.get("conclusao_pct") or 0)

            # Se unidade é % e quantidade > pct atual → atualiza progresso
            if unidade_at == "%" and quantidade > pct_atual:
                novo_pct = min(100, int(quantidade))
                hub_update: Dict[str, Any] = {
                    "conclusao_pct": novo_pct,
                    "last_rdo_date": today_str,
                }
                sb_update("hub_atividades", filters={"id": hub_id}, data=hub_update, client_id=client_id)

                # Histórico
                sb_insert("hub_atividade_historico", {
                    "atividade_id":       hub_id,
                    "contrato":           contrato,
                    "conclusao_pct_novo": novo_pct,
                    "conclusao_pct_anterior": pct_atual,
                    "rdo_id":             rdo_id,
                    "data":               today_str,
                    "created_at":         datetime.utcnow().isoformat(),
                    "client_id":          client_id,
                })
            elif unidade_at != "%" and quantidade > 0:
                # Quantidade física → atualiza exec_qty
                exec_atual = float(hub.get("exec_qty") or 0)
                novo_exec  = exec_atual + quantidade
                total_qty  = float(hub.get("total_qty") or 0)
                novo_pct   = min(100, int(novo_exec / total_qty * 100)) if total_qty > 0 else pct_atual

                hub_update = {
                    "exec_qty":      novo_exec,
                    "last_rdo_date": today_str,
                }
                if novo_pct > pct_atual:
                    hub_update["conclusao_pct"] = novo_pct

                sb_update("hub_atividades", filters={"id": hub_id}, data=hub_update, client_id=client_id)

                sb_insert("hub_atividade_historico", {
                    "atividade_id":       hub_id,
                    "contrato":           contrato,
                    "conclusao_pct_novo": novo_pct,
                    "conclusao_pct_anterior": pct_atual,
                    "exec_qty_novo":      novo_exec,
                    "producao_dia":       quantidade,
                    "total_qty":          total_qty,
                    "unidade":            unidade_at,
                    "rdo_id":             rdo_id,
                    "data":               today_str,
                    "created_at":         datetime.utcnow().isoformat(),
                    "client_id":          client_id,
                })

        # ── Auto-gerar insights após submit ──────────────────────────────────
        _trigger_insights(contrato, rdo_id, client_id)

    return {"ok": True, "view_token": view_token}


def _trigger_insights(contrato: str, rdo_id: str, client_id: Optional[str]):
    """Gera e persiste insights de IA para o contrato após submit de RDO."""
    try:
        from datetime import date
        today = date.today()

        atividades = sb_select(
            "hub_atividades",
            filters={"contrato": contrato},
            client_id=client_id,
            limit=500,
        ) or []

        insights: List[Dict] = []

        if atividades:
            total = len(atividades)
            atrasadas = []
            criticas_baixo_pct = []
            prazo_7dias = []

            for a in atividades:
                pct  = int(a.get("conclusao_pct") or 0)
                ter  = a.get("termino_previsto", "")
                ini  = a.get("inicio_previsto", "")
                nome = a.get("atividade", "Atividade")
                critico = bool(a.get("critico"))

                if pct >= 100 or not ter:
                    continue

                try:
                    d_ter = date.fromisoformat(ter[:10])
                    d_ini = date.fromisoformat(ini[:10]) if ini else today
                except Exception:
                    continue

                dias_total = max(1, (d_ter - d_ini).days)
                dias_dec   = max(0, (today - d_ini).days)
                pct_esperado = min(100, int(dias_dec / dias_total * 100))
                spi = pct / pct_esperado if pct_esperado > 0 else 1.0

                if d_ter < today and pct < 100:
                    atrasadas.append({"nome": nome, "ter": ter, "pct": pct, "critico": critico})

                if critico and pct < 80 and pct_esperado > 70:
                    criticas_baixo_pct.append({"nome": nome, "pct": pct, "esperado": pct_esperado})

                dias_restantes = (d_ter - today).days
                if 0 <= dias_restantes <= 7 and pct < 90:
                    prazo_7dias.append({"nome": nome, "dias": dias_restantes, "pct": pct})

            # Insight 1: Atividades atrasadas
            if atrasadas:
                mais_critica = next((a for a in atrasadas if a["critico"]), atrasadas[0])
                insights.append({
                    "priority": "High",
                    "title":    f"{len(atrasadas)} atividade(s) com prazo vencido",
                    "body":     f"'{mais_critica['nome'][:50]}' deveria ter sido concluída em {mais_critica['ter'][:10]} e está em {mais_critica['pct']}%. Prioridade máxima de ação."
                })

            # Insight 2: Atividades críticas com baixo SPI
            if criticas_baixo_pct:
                a = criticas_baixo_pct[0]
                insights.append({
                    "priority": "High",
                    "title":    "Atividade crítica com progresso insuficiente",
                    "body":     f"'{a['nome'][:50]}' está em {a['pct']}% quando o esperado é {a['esperado']}%. Risco de desvio no caminho crítico."
                })

            # Insight 3: Prazo 7 dias
            if prazo_7dias:
                a = prazo_7dias[0]
                insights.append({
                    "priority": "Medium",
                    "title":    f"{len(prazo_7dias)} atividade(s) vencem em até 7 dias",
                    "body":     f"'{a['nome'][:50]}' vence em {a['dias']} dia(s) com {a['pct']}% de conclusão. Requer atenção imediata."
                })

            # Insight 4: Status geral
            concluidas = sum(1 for a in atividades if int(a.get("conclusao_pct") or 0) >= 100)
            pct_medio  = int(sum(int(a.get("conclusao_pct") or 0) for a in atividades) / max(1, total))
            if pct_medio >= 80:
                insights.append({
                    "priority": "Low",
                    "title":    f"Projeto em fase avançada — {pct_medio}% de progresso médio",
                    "body":     f"{concluidas} de {total} atividades concluídas. Mantenha o ritmo para entrega dentro do prazo."
                })
            elif not insights:
                insights.append({
                    "priority": "Low",
                    "title":    f"Cronograma em andamento — {pct_medio}% progresso médio",
                    "body":     f"{concluidas} de {total} atividades concluídas. Acompanhe as atividades previstas para os próximos dias."
                })

        # Persiste no agente_insights (upsert por contrato)
        existing = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
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

    except Exception:
        pass  # Insights nunca devem bloquear o submit


# ── Histórico ─────────────────────────────────────────────────────────────────

@router.get("/historico")
async def list_historico(
    contrato: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, le=100),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    raw_filters: Dict[str, str] = {}
    if status and status != "Todos":
        filters["status"] = status
    if date_from:
        raw_filters["data"] = f"gte.{date_from}"
    if date_to:
        if "data" in raw_filters:
            # Can't do both with raw_filters easily — use gte and accept lte separately
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


# ── Subscribers (notificações por e-mail) ─────────────────────────────────────

@router.get("/subscribers")
async def list_subscribers(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {"contract": contrato, "module": "rdo"}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("email_sender", filters=filters, limit=100) or []
    return {"subscribers": [{"id": r["id"], "email": r["email"]} for r in rows]}


@router.post("/subscribers")
async def add_subscriber(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    contrato = body.get("contrato", "")
    email    = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        return JSONResponse(status_code=400, content={"error": "E-mail inválido"})

    # Check duplicate
    existing = sb_select("email_sender", filters={"contract": contrato, "module": "rdo", "email": email}, limit=1) or []
    if existing:
        return {"ok": True, "id": existing[0]["id"]}

    row = sb_insert("email_sender", {
        "contract":    contrato,
        "module":      "rdo",
        "email":       email,
        "created_by":  str(user.get("id", "")),
        "client_id":   client_id,
    })
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

    # Busca insights do agente para esse contrato
    insight_rows = sb_select("agente_insights", filters={"contrato": contrato}, limit=1) or []
    insights = []
    if insight_rows:
        raw = insight_rows[0].get("insights") or []
        insights = raw if isinstance(raw, list) else []

    return {
        "rdo":        _fmt_rdo(r),
        "atividades": [_fmt_atividade(a) for a in atividades],
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
