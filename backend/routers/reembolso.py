"""
Reembolso router — /api/reembolso
Formulário de reembolso de combustível com análise IA (OpenAI Vision).
Tables: reembolso (ou fuel_reembolsos), Bucket: reembolso-nf
"""

import hashlib
import io
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.core.logging import get_logger

router = APIRouter(prefix="/api/reembolso", tags=["reembolso"])
logger = get_logger(__name__)

_BRT = timezone(timedelta(hours=-3))

COMBUSTIVEL_OPTIONS = ["Gasolina","Gasolina Aditivada","Etanol","Diesel","Diesel S10","GNV"]
STATUS_OPTIONS      = ["Pendente","Aprovado","Rejeitado","Pago"]


def _fmt_brl(v: float) -> str:
    s = f"R$ {v:_.2f}".replace(".", "DECPT").replace("_", ".").replace("DECPT", ",")
    return s


def _fmt_date_br(ts: str) -> str:
    if not ts or ts in ("—","None",""):
        return "—"
    try:
        if "T" in ts or len(ts) > 10:
            dt = datetime.fromisoformat(ts.replace("Z","+00:00")[:32])
            return dt.astimezone(_BRT).strftime("%d/%m/%Y")
        parts = ts[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return ts[:10]


def _norm_item(r: Dict) -> Dict:
    vt = float(r.get("valor_total",0) or 0)
    vl = float(r.get("valor_litro",0) or 0)
    lt = float(r.get("litros",0) or 0)
    return {
        "id":                  str(r.get("id","")),
        "combustivel":         str(r.get("combustivel","Gasolina")),
        "litros":              lt,
        "valor_litro":         vl,
        "valor_total":         vt,
        "valor_total_fmt":     _fmt_brl(vt),
        "data_abastecimento":  _fmt_date_br(str(r.get("data_abastecimento",""))),
        "cidade":              str(r.get("cidade","")),
        "estado":              str(r.get("estado","")),
        "km_inicial":          str(r.get("km_inicial","")),
        "km_final":            str(r.get("km_final","")),
        "rota":                str(r.get("rota","")),
        "finalidade":          str(r.get("finalidade","")),
        "checkin_lat":         float(r.get("checkin_lat",0) or 0),
        "checkin_lng":         float(r.get("checkin_lng",0) or 0),
        "checkin_endereco":    str(r.get("checkin_endereco","")),
        "nf_url":              str(r.get("nf_url","")),
        "status":              str(r.get("status","Pendente")),
        "ai_score":            int(r.get("ai_score",0) or 0),
        "ai_verified":         bool(r.get("ai_verified", False)),
        "image_hash":          str(r.get("image_hash","")),
        "usuario_login":       str(r.get("usuario_login","")),
        "created_at":          _fmt_date_br(str(r.get("created_at",""))),
        "contrato":            str(r.get("contrato","")),
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("reembolso", filters=filters, order="created_at.desc", limit=500) or []
    items = [_norm_item(r) for r in rows]

    total_valor   = sum(float(r.get("valor_total",0) or 0) for r in rows)
    pendentes     = sum(1 for r in rows if r.get("status") == "Pendente")
    aprovados     = sum(1 for r in rows if r.get("status") == "Aprovado")
    ai_verified_n = sum(1 for r in rows if r.get("ai_verified"))

    return {
        "items":          items,
        "total_valor":    _fmt_brl(total_valor),
        "total_valor_raw": total_valor,
        "pendentes":      pendentes,
        "aprovados":      aprovados,
        "ai_verified":    ai_verified_n,
        "total":          len(rows),
        "status_options": STATUS_OPTIONS,
    }


# ── Submit form ───────────────────────────────────────────────────────────────

@router.post("/submit")
async def submit_reembolso(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "combustivel":         body.get("combustivel","Gasolina"),
        "litros":              float(body.get("litros",0) or 0),
        "valor_litro":         float(body.get("valor_litro",0) or 0),
        "valor_total":         float(body.get("valor_total",0) or 0),
        "data_abastecimento":  body.get("data_abastecimento") or str(datetime.utcnow().date()),
        "cidade":              body.get("cidade",""),
        "estado":              body.get("estado",""),
        "km_inicial":          body.get("km_inicial",""),
        "km_final":            body.get("km_final",""),
        "rota":                body.get("rota",""),
        "finalidade":          body.get("finalidade",""),
        "checkin_lat":         float(body.get("checkin_lat",0) or 0),
        "checkin_lng":         float(body.get("checkin_lng",0) or 0),
        "checkin_endereco":    body.get("checkin_endereco",""),
        "nf_url":              body.get("nf_url",""),
        "signature_b64":       body.get("signature_b64",""),
        "status":              "Pendente",
        "ai_score":            int(body.get("ai_score",0) or 0),
        "ai_verified":         bool(body.get("ai_verified", False)),
        "image_hash":          body.get("image_hash",""),
        "usuario_login":       user.get("login",""),
        "contrato":            body.get("contrato",""),
        "client_id":           client_id,
    }
    row = sb_insert("reembolso", payload)
    return {"ok": True, "row": _norm_item(row) if row else {}}


# ── Upload NF ─────────────────────────────────────────────────────────────────

@router.post("/upload-nf")
async def upload_nf(
    file: UploadFile = File(...),
    contrato: str = Form(""),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    img_bytes    = await file.read()
    content_type = file.content_type or "image/jpeg"
    img_hash     = hashlib.md5(img_bytes).hexdigest()
    ext          = content_type.split("/")[-1] if "/" in content_type else "jpg"
    path         = f"nf_{img_hash[:12]}.{ext}"

    from backend.integrations.supabase import sb_storage_upload
    url = sb_storage_upload("reembolso-nf", path, img_bytes, content_type) or ""

    # AI Vision analysis (best-effort — needs OPENAI_API_KEY)
    ai_result: Dict[str, Any] = {}
    try:
        import base64
        import os
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY","")
        if api_key:
            client_ai = OpenAI(api_key=api_key)
            b64 = base64.b64encode(img_bytes).decode()
            resp = client_ai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "Você é um auditor de NF de combustível. Extraia do cupom fiscal: "
                            "combustivel, litros (float), valor_litro (float), valor_total (float), data (YYYY-MM-DD), cidade, estado. "
                            "Responda SOMENTE JSON com essas chaves."
                        )},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
                    ],
                }],
                max_tokens=300,
            )
            import json
            raw = resp.choices[0].message.content or "{}"
            raw = raw.strip().strip("```json").strip("```").strip()
            ai_result = json.loads(raw)
    except Exception as e:
        logger.warning(f"AI NF analysis: {e}")

    return {"ok": True, "url": url, "image_hash": img_hash, "ai_extracted": ai_result}


# ── Status update (admin) ─────────────────────────────────────────────────────

@router.patch("/{reembolso_id}")
async def update_reembolso(
    reembolso_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"status","observacao_admin"}
    data    = {k: v for k,v in body.items() if k in allowed}
    row = sb_update("reembolso", filters={"id": reembolso_id}, data=data)
    return {"ok": True, "row": _norm_item(row) if row else {}}


@router.delete("/{reembolso_id}")
async def delete_reembolso(reembolso_id: str, _user=Depends(get_current_user)) -> Dict[str, Any]:
    sb_delete("reembolso", filters={"id": reembolso_id})
    return {"ok": True}
