"""
Financeiro router — /api/financeiro
Custos por contrato, lançamentos de avanço (append-only), S-curve diária, EVM.
"""
import re
from collections import defaultdict
from datetime import date as _date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends

from backend.integrations.supabase import sb_delete, sb_insert, sb_select, sb_update
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.integrations.ai import query as _ai_query

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])

FIN_STATUS_OPTIONS = ["previsto", "em_andamento", "parcial", "concluido", "executado", "cancelado"]


def _parse_float(v: Any) -> float:
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s in ("None", "nan", ""):
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
    s = f"R$ {v:_.2f}".replace(".", "DECPT").replace("_", ".").replace("DECPT", ",")
    return s


def _norm(v: Any, fallback: str = "") -> str:
    if v is None or str(v) in ("None", "NaT", "nan", ""):
        return fallback
    return str(v)


def _load_custos(contrato: str, client_id: Optional[str]) -> List[Dict]:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("fin_custos", filters=filters, order="created_at.asc", limit=1000) or []
    result = []
    for r in rows:
        prev  = _parse_float(r.get("valor_previsto", 0))
        exec_ = _parse_float(r.get("valor_executado", 0))
        result.append({
            "id":                  _norm(r.get("id")),
            "contrato":            _norm(r.get("contrato")),
            "categoria_id":        _norm(r.get("categoria_id")),
            "categoria_nome":      _norm(r.get("categoria_nome"), "—"),
            "empresa":             _norm(r.get("empresa")),
            "descricao":           _norm(r.get("descricao"), "—"),
            "valor_previsto":      prev,
            "valor_executado":     exec_,
            "valor_previsto_fmt":  _fmt_brl(prev),
            "valor_executado_fmt": _fmt_brl(exec_),
            "status":              _norm(r.get("status"), "previsto"),
            "data_custo":          _norm(r.get("data"), "")[:10],
            "atividade_id":        _norm(r.get("atividade_id")),
            "observacoes":         _norm(r.get("observacoes")),
        })
    return result


def _compute_kpis(custos: List[Dict]) -> Dict:
    total_prev = sum(r["valor_previsto"] for r in custos)
    total_exec = sum(r["valor_executado"] for r in custos)
    saldo = total_prev - total_exec
    pct = round(total_exec / total_prev * 100, 1) if total_prev > 0 else 0.0
    concluidos = sum(1 for r in custos if r["status"] in ("concluido", "executado"))
    return {
        "total_previsto":     _fmt_brl(total_prev),
        "total_executado":    _fmt_brl(total_exec),
        "total_previsto_raw": total_prev,
        "total_executado_raw": total_exec,
        "saldo":              _fmt_brl(saldo),
        "saldo_raw":          saldo,
        "pct_executado":      pct,
        "total_itens":        len(custos),
        "concluidos":         concluidos,
    }


def _compute_scurve_diaria(custos: List[Dict], lancamentos: List[Dict]) -> List[Dict]:
    """S-curve dia a dia usando lançamentos reais de execução + datas de custo para previsto."""
    prev_by_date: Dict[str, float] = defaultdict(float)
    exec_by_date: Dict[str, float] = defaultdict(float)

    for r in custos:
        d = (r.get("data_custo") or "")[:10]
        if d and len(d) == 10:
            prev_by_date[d] += r["valor_previsto"]

    # Execução vem dos lançamentos (granularidade real por data)
    for lc in lancamentos:
        d = str(lc.get("data") or "")[:10]
        if d and len(d) == 10:
            exec_by_date[d] += _parse_float(lc.get("valor", 0))

    # Se não há lançamentos, cai de volta para valor_executado do custo
    if not exec_by_date:
        for r in custos:
            d = (r.get("data_custo") or "")[:10]
            if d and len(d) == 10:
                exec_by_date[d] += r["valor_executado"]

    all_dates = sorted(set(list(prev_by_date) + list(exec_by_date)))
    result, acum_prev, acum_exec = [], 0.0, 0.0
    for d in all_dates:
        acum_prev += prev_by_date.get(d, 0.0)
        acum_exec += exec_by_date.get(d, 0.0)
        result.append({
            "data":           d,
            "previsto_acum":  round(acum_prev, 2),
            "executado_acum": round(acum_exec, 2),
        })
    return result


def _compute_by_categoria(custos: List[Dict]) -> List[Dict]:
    prev_cat: Dict[str, float] = defaultdict(float)
    exec_cat: Dict[str, float] = defaultdict(float)
    for r in custos:
        cat = r.get("categoria_nome") or "Outros"
        prev_cat[cat] += r["valor_previsto"]
        exec_cat[cat] += r["valor_executado"]
    cats = sorted(set(list(prev_cat) + list(exec_cat)))
    return [{"categoria": c, "previsto": round(prev_cat.get(c, 0), 2), "executado": round(exec_cat.get(c, 0), 2)} for c in cats]


def _compute_evm(custos: List[Dict], avg_activity_pct: float = 0.0) -> Dict:
    if not custos:
        return {}
    BAC = sum(r["valor_previsto"] for r in custos)
    AC  = sum(r["valor_executado"] for r in custos)
    if BAC <= 0:
        return {}
    today_str = str(_date.today())
    PV = sum(r["valor_previsto"] for r in custos if (r.get("data_custo") or "")[:10] <= today_str and (r.get("data_custo") or ""))
    physical_pct = avg_activity_pct if avg_activity_pct > 0 else (AC / BAC * 100 if BAC > 0 else 0)
    EV   = BAC * (min(physical_pct, 100) / 100)
    CPI  = EV / AC if AC > 0 else 1.0
    SPI  = EV / PV if PV > 0 else 1.0
    EAC  = BAC / CPI if CPI > 0 else BAC
    VAC  = BAC - EAC
    CV   = EV - AC
    SV   = EV - PV
    remaining_budget = BAC - AC
    remaining_work   = BAC - EV
    TCPI = remaining_work / remaining_budget if remaining_budget > 0 else 0.0
    return {
        "BAC": BAC, "AC": AC, "EV": EV, "PV": PV, "EAC": EAC, "VAC": VAC, "CV": CV, "SV": SV,
        "BAC_fmt": _fmt_brl(BAC), "AC_fmt": _fmt_brl(AC), "EV_fmt": _fmt_brl(EV),
        "PV_fmt":  _fmt_brl(PV),  "EAC_fmt": _fmt_brl(EAC),
        "VAC_fmt": _fmt_brl(abs(VAC)), "CV_fmt": _fmt_brl(abs(CV)), "SV_fmt": _fmt_brl(abs(SV)),
        "CPI": round(CPI, 2), "SPI": round(SPI, 2), "TCPI": round(TCPI, 2),
        "physical_pct": round(physical_pct, 1),
        "cost_pct":     round(AC / BAC * 100, 1),
        "is_overrun":   VAC < 0,
        "is_behind":    SV < 0,
    }


def _load_lancamentos(contrato: str, client_id: Optional[str], custo_id: Optional[str] = None) -> List[Dict]:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    if custo_id:
        filters["custo_id"] = custo_id
    rows = sb_select("fin_lancamentos", filters=filters, order="data.asc,created_at.asc", limit=5000) or []
    result = []
    for r in rows:
        val = _parse_float(r.get("valor", 0))
        result.append({
            "id":         _norm(r.get("id")),
            "custo_id":   _norm(r.get("custo_id")),
            "contrato":   _norm(r.get("contrato")),
            "valor":      val,
            "valor_fmt":  _fmt_brl(val),
            "data":       _norm(r.get("data"), "")[:10],
            "observacoes": _norm(r.get("observacoes")),
            "criado_por": _norm(r.get("criado_por")),
            "created_at": _norm(r.get("created_at")),
        })
    return result


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
async def get_financeiro_all(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("fin_custos", filters=filters, order="created_at.asc", limit=5000) or []
    custos = []
    for r in rows:
        prev  = _parse_float(r.get("valor_previsto", 0))
        exec_ = _parse_float(r.get("valor_executado", 0))
        custos.append({
            "id":                  _norm(r.get("id")),
            "contrato":            _norm(r.get("contrato")),
            "categoria_id":        _norm(r.get("categoria_id")),
            "categoria_nome":      _norm(r.get("categoria_nome"), "—"),
            "empresa":             _norm(r.get("empresa")),
            "descricao":           _norm(r.get("descricao"), "—"),
            "valor_previsto":      prev,
            "valor_executado":     exec_,
            "valor_previsto_fmt":  _fmt_brl(prev),
            "valor_executado_fmt": _fmt_brl(exec_),
            "status":              _norm(r.get("status"), "previsto"),
            "data_custo":          _norm(r.get("data"), "")[:10],
            "atividade_id":        _norm(r.get("atividade_id")),
            "observacoes":         _norm(r.get("observacoes")),
        })
    # Per-contract breakdown
    por_contrato: Dict[str, list] = defaultdict(list)
    for r in custos:
        por_contrato[r["contrato"]].append(r)
    contratos_kpis = []
    for cod, items in sorted(por_contrato.items()):
        k = _compute_kpis(items)
        evm_c = _compute_evm(items)
        contratos_kpis.append({
            "contrato":            cod,
            "total_previsto":      k["total_previsto"],
            "total_executado":     k["total_executado"],
            "total_previsto_raw":  k["total_previsto_raw"],
            "total_executado_raw": k["total_executado_raw"],
            "saldo":               k["saldo"],
            "pct_executado":       k["pct_executado"],
            "n_itens":             k["total_itens"],
            "cpi":                 evm_c.get("CPI", 0),
            "is_overrun":          evm_c.get("is_overrun", False),
        })

    cats = sb_select("fin_categorias", order="nome.asc", limit=100) or []
    return {
        "custos":         custos,
        "kpis":           _compute_kpis(custos),
        "scurve":         _compute_scurve_diaria(custos, []),
        "by_categoria":   _compute_by_categoria(custos),
        "evm":            _compute_evm(custos),
        "categorias":     [{"id": str(c.get("id","")), "nome": str(c.get("nome",""))} for c in cats],
        "status_options": FIN_STATUS_OPTIONS,
        "por_contrato":   contratos_kpis,
    }


@router.get("/insights")
async def get_financeiro_insights(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Gera insights executivos sobre a carteira financeira via AI — visão de diretor."""
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("fin_custos", filters=filters, order="created_at.asc", limit=5000) or []

    por_contrato: Dict[str, list] = defaultdict(list)
    for r in rows:
        prev = _parse_float(r.get("valor_previsto", 0))
        exec_ = _parse_float(r.get("valor_executado", 0))
        por_contrato[_norm(r.get("contrato"))].append({
            "valor_previsto": prev, "valor_executado": exec_,
            "status": _norm(r.get("status"), "previsto"),
            "data_custo": _norm(r.get("data"), "")[:10],
        })

    linhas = []
    total_bac = total_ac = 0.0
    overruns = []
    for cod, items in sorted(por_contrato.items()):
        k = _compute_kpis(items)
        e = _compute_evm(items)
        bac = sum(i["valor_previsto"] for i in items)
        ac  = sum(i["valor_executado"] for i in items)
        total_bac += bac
        total_ac  += ac
        cpi = e.get("CPI", 1.0)
        if e.get("is_overrun"):
            overruns.append(cod)
        linhas.append(
            f"  {cod}: BAC={_fmt_brl(bac)} AC={_fmt_brl(ac)} burn={k['pct_executado']:.1f}%"
            f" CPI={cpi:.2f} SPI={e.get('SPI', 1.0):.2f} {'⚠ OVERRUN' if e.get('is_overrun') else 'OK'}"
        )

    if not linhas:
        return {"insights": []}

    context = (
        f"CARTEIRA: {len(por_contrato)} contratos | BAC total={_fmt_brl(total_bac)} | AC total={_fmt_brl(total_ac)}"
        f" | Burn geral={round(total_ac/total_bac*100,1) if total_bac else 0}%\n\n"
        f"POR CONTRATO:\n" + "\n".join(linhas)
    )

    system_prompt = (
        "Você é o diretor financeiro da construtora. Analise a carteira de obras e gere EXATAMENTE 3 insights executivos em JSON.\n"
        "Formato: [{\"title\": str, \"body\": str, \"priority\": \"High\"|\"Medium\"|\"Low\", \"tipo\": str}]\n"
        "Regras: use APENAS os dados fornecidos. title ≤ 55 chars. body ≤ 280 chars com números reais e recomendação acionável.\n"
        "Foco executivo: eficiência de custo (CPI), estouro orçamentário, oportunidades de realocação, tendência geral da carteira."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": context},
    ]
    try:
        raw = _ai_query(messages, max_tokens=700, temperature=0.3, client_id=client_id,
                        prompt_preview="financeiro_insights_exec")
        import json as _json
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        insights = _json.loads(raw[start:end]) if start >= 0 else []
    except Exception:
        insights = []

    return {"insights": insights, "overruns": overruns, "n_contratos": len(por_contrato)}


@router.get("/{contrato}")
async def get_financeiro(
    contrato: str,
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    custos = _load_custos(contrato, client_id)
    lancamentos = _load_lancamentos(contrato, client_id)

    # Soma lançamentos em valor_executado de cada custo
    exec_por_custo: Dict[str, float] = defaultdict(float)
    for lc in lancamentos:
        exec_por_custo[lc["custo_id"]] += lc["valor"]
    if exec_por_custo:
        for c in custos:
            if c["id"] in exec_por_custo:
                c["valor_executado"]     = exec_por_custo[c["id"]]
                c["valor_executado_fmt"] = _fmt_brl(exec_por_custo[c["id"]])

    avg_pct = 0.0
    try:
        f: Dict[str, Any] = {"contrato": contrato}
        if client_id:
            f["client_id"] = client_id
        ativ = sb_select("hub_atividades", filters=f, limit=300) or []
        if ativ:
            pcts = [float(r.get("conclusao_pct", 0) or 0) for r in ativ]
            avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
    except Exception:
        pass

    cats = sb_select("fin_categorias", order="nome.asc", limit=100) or []

    return {
        "custos":         custos,
        "lancamentos":    lancamentos,
        "kpis":           _compute_kpis(custos),
        "scurve":         _compute_scurve_diaria(custos, lancamentos),
        "by_categoria":   _compute_by_categoria(custos),
        "evm":            _compute_evm(custos, avg_pct),
        "categorias":     [{"id": str(c.get("id","")), "nome": str(c.get("nome",""))} for c in cats],
        "status_options": FIN_STATUS_OPTIONS,
    }


@router.post("/{contrato}")
async def create_custo(
    contrato: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    payload = {
        "contrato":        contrato,
        "categoria_id":    body.get("categoria_id") or None,
        "categoria_nome":  body.get("categoria_nome", ""),
        "empresa":         body.get("empresa", ""),
        "descricao":       body.get("descricao", ""),
        "valor_previsto":  round(_parse_float(body.get("valor_previsto", 0)), 2),
        "valor_executado": 0.0,
        "status":          body.get("status", "previsto"),
        "data":            body.get("data_custo") or None,
        "atividade_id":    body.get("atividade_id") or None,
        "observacoes":     body.get("observacoes", ""),
        "client_id":       client_id,
    }
    row = sb_insert("fin_custos", payload)
    from backend.services.data_loader import DataLoader
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True, "row": row}


@router.patch("/{custo_id}")
async def update_custo(
    custo_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    allowed = {"categoria_id","categoria_nome","empresa","descricao","valor_previsto",
               "status","data","atividade_id","observacoes"}
    data = {k: v for k, v in body.items() if k in allowed}
    if "valor_previsto" in data:
        data["valor_previsto"] = round(_parse_float(data["valor_previsto"]), 2)
    row = sb_update("fin_custos", filters={"id": custo_id}, data=data)
    from backend.services.data_loader import DataLoader
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True, "row": row}


@router.delete("/{custo_id}")
async def delete_custo(
    custo_id: str,
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    sb_delete("fin_lancamentos", filters={"custo_id": custo_id})
    sb_delete("fin_custos", filters={"id": custo_id})
    from backend.services.data_loader import DataLoader
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True}


# ── Lançamentos (avanços de execução) ─────────────────────────────────────────

@router.post("/{contrato}/lancamentos/{custo_id}")
async def create_lancamento(
    contrato: str,
    custo_id: str,
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Registra um avanço de execução (append-only) e atualiza valor_executado no custo."""
    valor = round(_parse_float(body.get("valor", 0)), 2)
    if valor <= 0:
        return {"ok": False, "error": "Valor deve ser maior que zero"}

    data_lanc = body.get("data") or str(_date.today())
    obs = body.get("observacoes", "")
    criado_por = user.get("email", "") or user.get("nome", "")

    row = sb_insert("fin_lancamentos", {
        "custo_id":   custo_id,
        "contrato":   contrato,
        "client_id":  client_id,
        "valor":      valor,
        "data":       data_lanc,
        "observacoes": obs,
        "criado_por": criado_por,
    })

    # Recalcula valor_executado como soma de todos lançamentos
    todos = sb_select("fin_lancamentos", filters={"custo_id": custo_id}, limit=5000) or []
    total_exec = sum(_parse_float(r.get("valor", 0)) for r in todos)
    custo_rows = sb_select("fin_custos", filters={"id": custo_id}, limit=1) or []
    val_prev = _parse_float((custo_rows[0].get("valor_previsto", 0)) if custo_rows else 0)

    novo_status = "previsto"
    if total_exec >= val_prev and val_prev > 0:
        novo_status = "concluido"
    elif total_exec > 0:
        novo_status = "em_andamento"

    sb_update("fin_custos", filters={"id": custo_id}, data={
        "valor_executado": round(total_exec, 2),
        "status": novo_status,
    })

    from backend.services.data_loader import DataLoader
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True, "row": row, "total_executado": round(total_exec, 2)}


@router.get("/{contrato}/lancamentos/{custo_id}")
async def list_lancamentos(
    contrato: str,
    custo_id: str,
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    rows = _load_lancamentos(contrato, client_id, custo_id)
    return {"lancamentos": rows}


@router.delete("/lancamentos/{lancamento_id}")
async def delete_lancamento(
    lancamento_id: str,
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    rows = sb_select("fin_lancamentos", filters={"id": lancamento_id}, limit=1) or []
    if not rows:
        return {"ok": False, "error": "Lançamento não encontrado"}
    custo_id = rows[0].get("custo_id")
    sb_delete("fin_lancamentos", filters={"id": lancamento_id})

    if custo_id:
        todos = sb_select("fin_lancamentos", filters={"custo_id": custo_id}, limit=5000) or []
        total_exec = sum(_parse_float(r.get("valor", 0)) for r in todos)
        custo_rows = sb_select("fin_custos", filters={"id": custo_id}, limit=1) or []
        val_prev = _parse_float((custo_rows[0].get("valor_previsto", 0)) if custo_rows else 0)
        novo_status = "previsto"
        if total_exec >= val_prev and val_prev > 0:
            novo_status = "concluido"
        elif total_exec > 0:
            novo_status = "em_andamento"
        sb_update("fin_custos", filters={"id": custo_id}, data={
            "valor_executado": round(total_exec, 2),
            "status": novo_status,
        })

    from backend.services.data_loader import DataLoader
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True}


# ── Categorias ────────────────────────────────────────────────────────────────

@router.get("/categorias/list")
async def list_categorias(_user=Depends(get_current_user)) -> Dict[str, Any]:
    rows = sb_select("fin_categorias", order="nome.asc", limit=100) or []
    return {"categorias": rows}


@router.post("/categorias/create")
async def create_categoria(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    nome = str(body.get("nome", "")).strip()
    existing = sb_select("fin_categorias", limit=200) or []
    for r in existing:
        if str(r.get("nome", "")).strip().lower() == nome.lower():
            return {"ok": True, "row": r, "created": False}
    row = sb_insert("fin_categorias", {"nome": nome, "cor": "#889999", "icone": "tag"})
    return {"ok": True, "row": row, "created": True}
