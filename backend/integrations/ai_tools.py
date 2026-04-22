"""
AI Tools — ferramentas do loop agentic com full awareness dos dados do tenant.
"""

import json
from datetime import date
from typing import Any, Dict, List

from backend.core.logging import get_logger
from backend.integrations.supabase import sb_select

logger = get_logger(__name__)

TOOL_SCHEMAS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_contracts",
            "description": "Lista todos os contratos/projetos do tenant com status, progresso e datas. Use sempre como primeiro passo para saber quais contratos existem.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contract_kpis",
            "description": "KPIs completos de um contrato: atividades, progresso físico, SPI, atividades críticas e atrasadas, budget, EVM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string", "description": "Código do contrato"},
                },
                "required": ["contrato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activities",
            "description": "Lista atividades de um contrato com fase, progresso, datas, responsável, status. Suporta filtro por status: 'atrasadas', 'criticas', 'em_andamento', 'pendentes'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string"},
                    "filtro":   {"type": "string", "enum": ["todas", "atrasadas", "criticas", "em_andamento", "pendentes", "concluidas"], "default": "todas"},
                    "query":    {"type": "string", "description": "Palavra-chave opcional para buscar no nome da atividade"},
                },
                "required": ["contrato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Resumo financeiro: previsto vs executado, CPI, saldo por categoria. Se contrato for omitido, agrega todos os contratos do tenant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string", "description": "Código do contrato (opcional — omitir para visão geral)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rdo_history",
            "description": "Últimos RDOs de um contrato: data, clima, equipe, interrupções, atividades executadas, observações.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string"},
                    "limit":    {"type": "integer", "default": 10},
                },
                "required": ["contrato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_om_data",
            "description": "Dados de O&M: gerações mensais, performance, PR ratio, disponibilidade de sistemas instalados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string", "description": "Código do contrato (opcional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alerts",
            "description": "Alertas e notificações ativas do tenant: atrasos, impedimentos, anomalias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string", "description": "Filtrar por contrato (opcional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline",
            "description": "Eventos recentes da timeline de um contrato: marcos, reuniões, decisões, documentos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string"},
                    "limit":    {"type": "integer", "default": 10},
                },
                "required": ["contrato"],
            },
        },
    },
]


# ── Executor ──────────────────────────────────────────────────────────────────

def execute_tool(name: str, args: Dict[str, Any], client_id: str = "") -> str:
    try:
        if name == "list_contracts":
            return _list_contracts(client_id)
        elif name == "get_contract_kpis":
            return _get_contract_kpis(args.get("contrato", ""), client_id)
        elif name == "get_activities":
            return _get_activities(args.get("contrato", ""), args.get("filtro", "todas"), args.get("query", ""), client_id)
        elif name == "get_financial_summary":
            return _get_financial_summary(args.get("contrato", ""), client_id)
        elif name == "get_rdo_history":
            return _get_rdo_history(args.get("contrato", ""), int(args.get("limit", 10)), client_id)
        elif name == "get_om_data":
            return _get_om_data(args.get("contrato", ""), client_id)
        elif name == "get_alerts":
            return _get_alerts(args.get("contrato", ""), client_id)
        elif name == "get_timeline":
            return _get_timeline(args.get("contrato", ""), int(args.get("limit", 10)), client_id)
        else:
            return json.dumps({"error": f"Tool '{name}' não encontrada"})
    except Exception as e:
        logger.warning(f"Tool {name} error: {e}")
        return json.dumps({"error": str(e)})


def make_executor(client_id: str):
    def _executor(name: str, args: Dict[str, Any]) -> str:
        return execute_tool(name, args, client_id)
    return _executor


# ── Implementations ───────────────────────────────────────────────────────────

def _list_contracts(client_id: str) -> str:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("contratos", filters=filters, limit=100) or []
    today = date.today()
    result = []
    for r in rows:
        termino = str(r.get("data_termino") or r.get("termino") or "")[:10]
        dias_restantes = None
        if termino:
            try:
                dias_restantes = (date.fromisoformat(termino) - today).days
            except Exception:
                pass
        result.append({
            "contrato":        str(r.get("contrato", "")),
            "projeto":         str(r.get("projeto", "")),
            "cliente":         str(r.get("cliente", "")),
            "status":          str(r.get("status", "")),
            "localizacao":     str(r.get("localizacao", "")),
            "data_inicio":     str(r.get("data_inicio") or r.get("inicio") or "")[:10],
            "data_termino":    termino,
            "dias_restantes":  dias_restantes,
            "valor_contratado": float(r.get("valor_contratado") or 0),
            "potencia_kwp":    float(r.get("potencia_kwp") or r.get("potencia_kwp_contratada") or 0),
            "gestor":          str(r.get("gestor") or ""),
            "prioridade":      str(r.get("prioridade") or "Normal"),
        })
    return json.dumps({"contratos": result, "total": len(result)}, ensure_ascii=False)


def _get_contract_kpis(contrato: str, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    atividades = sb_select("hub_atividades", filters=filters, limit=500) or []
    custos     = sb_select("fin_custos",     filters=filters, limit=500) or []
    rdos       = sb_select("rdo_master",     filters={**filters, "status": "Submetido"}, order="data.desc", limit=30) or []

    today = date.today()
    total = len(atividades)
    concl = sum(1 for a in atividades if float(a.get("conclusao_pct") or 0) >= 100)
    criticas_pendentes = [
        a for a in atividades
        if str(a.get("critico", "")).lower() == "sim" and float(a.get("conclusao_pct") or 0) < 100
    ]
    atrasadas = []
    for a in atividades:
        ter = str(a.get("termino_previsto") or "")[:10]
        pct = float(a.get("conclusao_pct") or 0)
        if ter and pct < 100:
            try:
                if date.fromisoformat(ter) < today:
                    atrasadas.append({"atividade": a.get("atividade", ""), "fase": a.get("fase", ""), "pct": pct, "atraso_dias": (today - date.fromisoformat(ter)).days})
            except Exception:
                pass

    pcts = [float(a.get("conclusao_pct") or 0) for a in atividades]
    avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0.0

    # SPI simples
    contrato_rows = sb_select("contratos", filters=filters, limit=1) or []
    spi = None
    if contrato_rows:
        c = contrato_rows[0]
        try:
            d_ini = date.fromisoformat(str(c.get("data_inicio") or c.get("inicio") or "")[:10])
            d_fim = date.fromisoformat(str(c.get("data_termino") or c.get("termino") or "")[:10])
            total_d = max((d_fim - d_ini).days, 1)
            dec_d = max((today - d_ini).days, 0)
            prazo_pct = min(100.0, dec_d / total_d * 100)
            spi = round(avg_pct / prazo_pct, 2) if prazo_pct > 0 else None
        except Exception:
            pass

    total_prev = sum(float(c.get("valor_previsto") or 0) for c in custos)
    total_exec = sum(float(c.get("valor_executado") or 0) for c in custos)

    chuva_dias = sum(1 for r in rdos if r.get("houve_chuva") or str(r.get("condicao_climatica", "")).lower() in ("chuvoso", "tempestade"))
    interrupcoes = sum(1 for r in rdos if r.get("houve_interrupcao"))

    return json.dumps({
        "contrato":           contrato,
        "total_atividades":   total,
        "concluidas":         concl,
        "em_andamento":       total - concl,
        "avg_conclusao_pct":  avg_pct,
        "spi":                spi,
        "criticas_pendentes": len(criticas_pendentes),
        "atrasadas":          atrasadas[:5],
        "total_atrasadas":    len(atrasadas),
        "budget_previsto":    round(total_prev, 2),
        "budget_executado":   round(total_exec, 2),
        "saldo":              round(total_prev - total_exec, 2),
        "cpi":                round(total_exec / total_prev, 3) if total_prev > 0 else None,
        "rdos_submetidos":    len(rdos),
        "dias_com_chuva_30d": chuva_dias,
        "interrupcoes_30d":   interrupcoes,
    }, ensure_ascii=False)


def _get_activities(contrato: str, filtro: str, query: str, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("hub_atividades", filters=filters, limit=500) or []
    today = date.today()

    if query:
        q = query.lower()
        rows = [r for r in rows if q in str(r.get("atividade", "")).lower() or q in str(r.get("fase", "")).lower()]

    if filtro == "atrasadas":
        rows = [r for r in rows if str(r.get("termino_previsto") or "")[:10] and
                float(r.get("conclusao_pct") or 0) < 100 and
                _is_past(str(r.get("termino_previsto", ""))[:10], today)]
    elif filtro == "criticas":
        rows = [r for r in rows if str(r.get("critico", "")).lower() == "sim" and float(r.get("conclusao_pct") or 0) < 100]
    elif filtro == "em_andamento":
        rows = [r for r in rows if 0 < float(r.get("conclusao_pct") or 0) < 100]
    elif filtro == "pendentes":
        rows = [r for r in rows if float(r.get("conclusao_pct") or 0) == 0]
    elif filtro == "concluidas":
        rows = [r for r in rows if float(r.get("conclusao_pct") or 0) >= 100]

    result = [{
        "atividade":        str(r.get("atividade", "")),
        "fase":             str(r.get("fase", "")),
        "responsavel":      str(r.get("responsavel", "")),
        "conclusao_pct":    float(r.get("conclusao_pct") or 0),
        "inicio_previsto":  str(r.get("inicio_previsto") or "")[:10],
        "termino_previsto": str(r.get("termino_previsto") or "")[:10],
        "critico":          str(r.get("critico", "")),
        "total_qty":        float(r.get("total_qty") or 0),
        "exec_qty":         float(r.get("exec_qty") or 0),
        "unidade":          str(r.get("unidade") or ""),
    } for r in rows[:30]]

    return json.dumps({"contrato": contrato, "filtro": filtro, "atividades": result, "total": len(result)}, ensure_ascii=False)


def _get_financial_summary(contrato: str, client_id: str) -> str:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if contrato:
        filters["contrato"] = contrato

    custos = sb_select("fin_custos", filters=filters, limit=1000) or []

    from collections import defaultdict
    by_cat: Dict[str, Dict] = defaultdict(lambda: {"prev": 0.0, "exec": 0.0})
    for c in custos:
        cat = str(c.get("categoria_nome") or c.get("categoria") or "Outros")
        by_cat[cat]["prev"] += float(c.get("valor_previsto") or 0)
        by_cat[cat]["exec"] += float(c.get("valor_executado") or 0)

    total_prev = sum(v["prev"] for v in by_cat.values())
    total_exec = sum(v["exec"] for v in by_cat.values())

    return json.dumps({
        "contrato":        contrato or "todos",
        "total_previsto":  round(total_prev, 2),
        "total_executado": round(total_exec, 2),
        "saldo":           round(total_prev - total_exec, 2),
        "cpi":             round(total_exec / total_prev, 3) if total_prev > 0 else None,
        "pct_executado":   round(total_exec / total_prev * 100, 1) if total_prev > 0 else 0,
        "por_categoria":   [
            {"categoria": k, "previsto": round(v["prev"], 2), "executado": round(v["exec"], 2),
             "desvio": round(v["exec"] - v["prev"], 2)}
            for k, v in sorted(by_cat.items(), key=lambda x: x[1]["prev"], reverse=True)
        ],
    }, ensure_ascii=False)


def _get_rdo_history(contrato: str, limit: int, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato, "status": "Submetido"}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("rdo_master", filters=filters, order="data.desc", limit=limit) or []
    result = []
    for r in rows:
        rdo_id = r.get("id")
        ativs = sb_select("rdo_atividades", filters={"rdo_id": rdo_id}, limit=20) or [] if rdo_id else []
        result.append({
            "data":            str(r.get("data") or "")[:10],
            "turno":           str(r.get("turno") or ""),
            "clima":           str(r.get("condicao_climatica") or r.get("clima") or ""),
            "equipe_alocada":  r.get("equipe_alocada"),
            "hora_inicio":     str(r.get("hora_inicio") or ""),
            "hora_termino":    str(r.get("hora_termino") or ""),
            "houve_chuva":     bool(r.get("houve_chuva")),
            "houve_interrupcao": bool(r.get("houve_interrupcao")),
            "motivo_interrupcao": str(r.get("motivo_interrupcao") or ""),
            "houve_acidente":  bool(r.get("houve_acidente")),
            "observacoes":     str(r.get("observacoes") or "")[:300],
            "atividades_executadas": [str(a.get("atividade") or "") for a in ativs],
            "responsavel":     str(r.get("signatory_name") or r.get("assinatura_nome") or ""),
        })

    return json.dumps({"contrato": contrato, "rdos": result, "total": len(result)}, ensure_ascii=False)


def _get_om_data(contrato: str, client_id: str) -> str:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if contrato:
        filters["contrato"] = contrato

    geracoes = sb_select("om_geracoes", filters=filters, order="mes.desc", limit=24) or []

    total_gerado = sum(float(g.get("geracao_kwh") or 0) for g in geracoes)
    total_esperado = sum(float(g.get("esperado_kwh") or 0) for g in geracoes)
    pr_values = [float(g.get("pr_ratio") or 0) for g in geracoes if g.get("pr_ratio")]
    pr_medio = round(sum(pr_values) / len(pr_values), 3) if pr_values else None

    return json.dumps({
        "contrato":      contrato or "todos",
        "total_gerado_kwh":   round(total_gerado, 1),
        "total_esperado_kwh": round(total_esperado, 1),
        "pr_medio":      pr_medio,
        "disponibilidade_media": round(
            sum(float(g.get("disponibilidade") or 0) for g in geracoes) / len(geracoes), 1
        ) if geracoes else None,
        "meses": [{
            "mes":         str(g.get("mes") or "")[:7],
            "geracao_kwh": float(g.get("geracao_kwh") or 0),
            "esperado_kwh": float(g.get("esperado_kwh") or 0),
            "pr_ratio":    float(g.get("pr_ratio") or 0),
        } for g in geracoes[:12]],
    }, ensure_ascii=False)


def _get_alerts(contrato: str, client_id: str) -> str:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    if contrato:
        filters["contrato"] = contrato

    rows = sb_select("alertas", filters=filters, order="created_at.desc", limit=20) or []
    result = [{
        "tipo":      str(r.get("tipo") or ""),
        "titulo":    str(r.get("titulo") or ""),
        "descricao": str(r.get("descricao") or "")[:200],
        "contrato":  str(r.get("contrato") or ""),
        "nivel":     str(r.get("nivel") or ""),
        "criado_em": str(r.get("created_at") or "")[:16],
    } for r in rows]

    return json.dumps({"alertas": result, "total": len(result)}, ensure_ascii=False)


def _get_timeline(contrato: str, limit: int, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("hub_timeline", filters=filters, order="created_at.desc", limit=limit) or []
    result = [{
        "tipo":      str(r.get("tipo") or ""),
        "titulo":    str(r.get("titulo") or ""),
        "descricao": str(r.get("descricao") or "")[:300],
        "autor":     str(r.get("autor") or ""),
        "criado_em": str(r.get("created_at") or "")[:16],
    } for r in rows]

    return json.dumps({"contrato": contrato, "eventos": result, "total": len(result)}, ensure_ascii=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_past(date_str: str, today: date) -> bool:
    try:
        return date.fromisoformat(date_str) < today
    except Exception:
        return False
