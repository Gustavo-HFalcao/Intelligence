"""
AI Tools — ferramentas disponíveis para o loop agentic do Chat IA.
Cada tool é uma função Python chamada pelo tool_executor durante query_agentic().

Tools disponíveis:
  execute_sql        — consulta SQL lida em Supabase via PostgREST
  generate_chart     — retorna dados formatados para Recharts
  search_documents   — busca semântica simples em hub_atividades / fin_custos
  get_contract_kpis  — KPIs de um contrato específico
  get_evm_metrics    — métricas EVM de um contrato
"""

import json
from typing import Any, Dict, List

from backend.core.logging import get_logger
from backend.integrations.supabase import sb_select

logger = get_logger(__name__)

# ── Tool schemas (OpenAI function calling format) ─────────────────────────────

TOOL_SCHEMAS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_contract_kpis",
            "description": "Retorna KPIs de um contrato: atividades, progresso físico, budget, EVM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type":"string", "description":"Código do contrato, ex: CT-001"},
                },
                "required": ["contrato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_activities",
            "description": "Busca atividades de um contrato por palavra-chave no nome ou descrição.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type":"string", "description":"Código do contrato"},
                    "query":    {"type":"string", "description":"Palavra-chave para buscar"},
                },
                "required": ["contrato", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Retorna resumo financeiro (previsto vs executado) de um contrato.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type":"string"},
                },
                "required": ["contrato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_contracts",
            "description": "Lista todos os contratos disponíveis com status e progresso.",
            "parameters": {"type":"object", "properties":{}, "required":[]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rdo_history",
            "description": "Retorna os últimos RDOs de um contrato.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type":"string"},
                    "limit":    {"type":"integer", "default":5},
                },
                "required": ["contrato"],
            },
        },
    },
]


# ── Executor ──────────────────────────────────────────────────────────────────

def execute_tool(name: str, args: Dict[str, Any], client_id: str = "") -> str:
    """Dispatch tool call and return result as JSON string."""
    try:
        if name == "get_contract_kpis":
            return _get_contract_kpis(args.get("contrato",""), client_id)
        elif name == "search_activities":
            return _search_activities(args.get("contrato",""), args.get("query",""), client_id)
        elif name == "get_financial_summary":
            return _get_financial_summary(args.get("contrato",""), client_id)
        elif name == "list_contracts":
            return _list_contracts(client_id)
        elif name == "get_rdo_history":
            return _get_rdo_history(args.get("contrato",""), int(args.get("limit",5)), client_id)
        else:
            return json.dumps({"error": f"Tool '{name}' não encontrada"})
    except Exception as e:
        logger.warning(f"Tool {name} error: {e}")
        return json.dumps({"error": str(e)})


def make_executor(client_id: str):
    """Returns a closure with client_id bound for use in query_agentic."""
    def _executor(name: str, args: Dict[str, Any]) -> str:
        return execute_tool(name, args, client_id)
    return _executor


# ── Tool implementations ──────────────────────────────────────────────────────

def _get_contract_kpis(contrato: str, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    atividades = sb_select("hub_atividades", filters=filters, limit=500) or []
    custos     = sb_select("fin_custos",     filters=filters, limit=500) or []

    total    = len(atividades)
    concl    = sum(1 for a in atividades if a.get("status") == "Concluído")
    criticas = sum(1 for a in atividades if a.get("is_critical"))
    pcts     = [float(a.get("conclusao_pct",0) or 0) for a in atividades]
    avg_pct  = round(sum(pcts)/len(pcts), 1) if pcts else 0.0

    total_prev = sum(float(c.get("valor_previsto",0) or 0) for c in custos)
    total_exec = sum(float(c.get("valor_executado",0) or 0) for c in custos)
    saldo      = total_prev - total_exec

    return json.dumps({
        "contrato":            contrato,
        "total_atividades":    total,
        "concluidas":          concl,
        "criticas":            criticas,
        "avg_conclusao_pct":   avg_pct,
        "budget_previsto":     round(total_prev, 2),
        "budget_executado":    round(total_exec, 2),
        "saldo":               round(saldo, 2),
        "pct_budget_executado": round(total_exec/total_prev*100, 1) if total_prev > 0 else 0,
    }, ensure_ascii=False)


def _search_activities(contrato: str, query: str, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("hub_atividades", filters=filters, limit=500) or []
    q    = query.lower()
    hits = [
        {
            "id":           str(r.get("id","")),
            "nome":         str(r.get("nome","")),
            "status":       str(r.get("status","")),
            "conclusao_pct": float(r.get("conclusao_pct",0) or 0),
            "data_inicio":  str(r.get("data_inicio",""))[:10],
            "data_fim":     str(r.get("data_fim",""))[:10],
        }
        for r in rows
        if q in str(r.get("nome","")).lower() or q in str(r.get("descricao","")).lower()
    ][:10]

    return json.dumps({"query":query, "contrato":contrato, "results":hits, "total":len(hits)}, ensure_ascii=False)


def _get_financial_summary(contrato: str, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    custos = sb_select("fin_custos", filters=filters, limit=500) or []

    from collections import defaultdict
    by_cat: Dict[str, Dict] = defaultdict(lambda: {"prev":0.0,"exec":0.0})
    for c in custos:
        cat = str(c.get("categoria_nome","Outros"))
        by_cat[cat]["prev"] += float(c.get("valor_previsto",0) or 0)
        by_cat[cat]["exec"] += float(c.get("valor_executado",0) or 0)

    total_prev = sum(v["prev"] for v in by_cat.values())
    total_exec = sum(v["exec"] for v in by_cat.values())

    return json.dumps({
        "contrato":      contrato,
        "total_previsto": round(total_prev, 2),
        "total_executado": round(total_exec, 2),
        "saldo":          round(total_prev - total_exec, 2),
        "pct_executado":  round(total_exec/total_prev*100, 1) if total_prev > 0 else 0,
        "por_categoria":  [
            {"categoria":k, "previsto":round(v["prev"],2), "executado":round(v["exec"],2)}
            for k,v in by_cat.items()
        ],
    }, ensure_ascii=False)


def _list_contracts(client_id: str) -> str:
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("contratos", filters=filters, limit=100) or []
    result = [
        {
            "contrato": str(r.get("contrato","")),
            "projeto":  str(r.get("projeto","")),
            "cliente":  str(r.get("cliente","")),
            "status":   str(r.get("status","")),
        }
        for r in rows
    ]
    return json.dumps({"contratos": result, "total": len(result)}, ensure_ascii=False)


def _get_rdo_history(contrato: str, limit: int, client_id: str) -> str:
    filters: Dict[str, Any] = {"contrato": contrato, "status": "Submetido"}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("rdo_master", filters=filters, order="data.desc", limit=limit) or []
    result = [
        {
            "id":    str(r.get("id","")),
            "data":  str(r.get("data",""))[:10],
            "clima": str(r.get("clima","")),
            "turno": str(r.get("turno","")),
            "equipe": str(r.get("equipe_alocada","")),
            "obs":   str(r.get("observacoes",""))[:200],
        }
        for r in rows
    ]
    return json.dumps({"contrato":contrato, "rdos":result, "total":len(result)}, ensure_ascii=False)
