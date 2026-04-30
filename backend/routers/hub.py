"""
Hub de Operações router — /api/hub
Cobre as 6 abas: Visão Geral, Dashboard, Cronograma, Auditoria, Timeline, Financeira.

Porta HubState (hub_state.py, 4159 linhas) para endpoints REST.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query

import httpx
from backend.integrations.supabase import (
    sb_delete,
    sb_insert,
    sb_select,
    sb_update,
)
from backend.core.logging import get_logger
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.services.data_loader import DataLoader

logger = get_logger(__name__)

router = APIRouter(prefix="/api/hub", tags=["hub"])

_BRT = timezone(timedelta(hours=-3))

AUDIT_CATEGORIES = [
    {"slug": "equipe",      "label": "Equipe com EPI",   "icon": "hard-hat",      "color": "#22c55e"},
    {"slug": "falhas",      "label": "Falhas & Logs",    "icon": "alert-triangle", "color": "#EF4444"},
    {"slug": "ferramentas", "label": "Ferramentas",      "icon": "wrench",         "color": "#2A9D8F"},
    {"slug": "gerais",      "label": "Imagens Gerais",   "icon": "image",          "color": "#C98B2A"},
]

ENTRY_TYPES = ["Atualização", "Marco", "Reunião", "Decisão", "Alerta", "Falha", "Documento", "Custo"]

FASE_COLORS: Dict[str, str] = {
    "civil": "#C98B2A", "elétrica": "#3B82F6", "eletrica": "#3B82F6",
    "hidráulica": "#2A9D8F", "hidraulica": "#2A9D8F", "estrutural": "#E89845",
    "mecânica": "#A855F7", "mecanica": "#A855F7",
}


def _utc_to_brt(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")[:32])
        return dt.astimezone(_BRT).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ts[:16].replace("T", " ")


def _iso_to_br(v: str) -> str:
    if not v:
        return ""
    try:
        p = str(v)[:10].split("-")
        if len(p) == 3 and len(p[0]) == 4:
            return f"{p[2]}/{p[1]}/{p[0]}"
    except Exception:
        pass
    return str(v)[:10]


def _get_working_days(contrato: str, client_id: str = None) -> set:
    """Retorna o set de dias úteis do contrato. Default seg–sab."""
    rows = sb_select("contratos", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
    if rows:
        return _parse_dias_uteis(rows[0].get("dias_uteis_semana", "") or "")
    return {0, 1, 2, 3, 4, 5}


def _build_hist_map(historico: list) -> dict:
    """Constrói mapa atividade_id → [(date, conclusao_pct_novo)] ordenado por data.
    Usado para calcular realizado estritamente via RDO (não via conclusao_pct atual)."""
    from collections import defaultdict as _dd
    raw: dict = _dd(list)
    for h in historico:
        aid = str(h.get("atividade_id") or "")
        d_str = str(h.get("data") or "")[:10]
        pct = h.get("conclusao_pct_novo")
        if aid and d_str and len(d_str) == 10 and pct is not None:
            try:
                raw[aid].append((date.fromisoformat(d_str), float(pct)))
            except (ValueError, TypeError):
                pass
    return {aid: sorted(entries, key=lambda x: x[0]) for aid, entries in raw.items()}


def _hist_pct_at(hist_map: dict, aid: str, ref: date) -> Optional[float]:
    """Retorna o pct registrado via RDO para a atividade até ref_date. None se sem histórico."""
    entries = hist_map.get(str(aid))
    if not entries:
        return None
    val = None
    for d, pct in entries:
        if d <= ref:
            val = pct
        else:
            break
    return val


def _calc_progress_spi(
    atividades: list,
    today: date,
    working_days: set = None,
    ref_date: date = None,
    hist_map: dict = None,
) -> dict:
    """Calcula progresso físico e SPI usando apenas atividades-folha (sem filhos).

    REGRA FUNDAMENTAL: realizado só existe quando há RDO submetido.
    - ref_date: data do último RDO submetido. None → sem RDO → desvio=0.
    - hist_map: mapa de _build_hist_map(). Quando passado, pct_real vem
      exclusivamente do historico até ref_date. Sem entry = 0% realizado.
      Quando None (callers sem hist), usa conclusao_pct como fallback seguro
      apenas se ref_date não-None (compatibilidade com insights/chat).
    Retorna: progress_pct, prazo_decorrido_pct, spi, desvio_pct"""
    if working_days is None:
        working_days = {0, 1, 2, 3, 4, 5}  # seg–sab como default

    ids_com_filhos = {a["parent_id"] for a in atividades if a.get("parent_id")}
    folhas = [
        a for a in atividades
        if a["id"] not in ids_com_filhos
        and a.get("fase") is not None
    ]
    if not folhas:
        folhas = [a for a in atividades if a.get("fase") is not None] or atividades

    if not folhas:
        return {"progress_pct": 0.0, "prazo_decorrido_pct": 0.0, "spi": 1.0, "desvio_pct": 0.0}

    # REGRA: sem RDO submetido → desvio=0, prazo=0, SPI=1
    if ref_date is None:
        peso_total_z = sum(float(a.get("peso_pct") or 1) for a in folhas) or 1
        if hist_map is not None:
            # sem ref_date não sabemos até quando computar: retorna 0
            progress_z = 0.0
        else:
            progress_z = round(
                sum(float(a.get("conclusao_pct") or 0) * float(a.get("peso_pct") or 1) for a in folhas)
                / peso_total_z,
                1,
            )
        return {"progress_pct": progress_z, "prazo_decorrido_pct": 0.0, "spi": 1.0, "desvio_pct": 0.0}

    ref = ref_date
    peso_total = 0.0
    pct_real_pond = 0.0
    pct_esp_pond = 0.0

    for a in folhas:
        ini_s = str(a.get("inicio_previsto") or "")[:10]
        ter_s = str(a.get("termino_previsto") or "")[:10]
        peso = float(a.get("peso_pct") or 1)

        # Realizado: usa hist_map quando disponível E não-vazio.
        # hist_map vazio = histórico ainda não populado (contrato novo ou dados migrados)
        # → fallback para conclusao_pct para não zerar tudo.
        if hist_map:
            hist_val = _hist_pct_at(hist_map, str(a["id"]), ref)
            pct_real = hist_val if hist_val is not None else 0.0
        else:
            pct_real = float(a.get("conclusao_pct") or 0)

        pct_esp = 0.0
        if ini_s and ter_s:
            try:
                d_ini = date.fromisoformat(ini_s)
                d_ter = date.fromisoformat(ter_s)
                if ref < d_ini:
                    pct_esp = 0.0
                elif ref >= d_ter:
                    pct_esp = 100.0
                else:
                    total_du = max(_count_working_days(ini_s, ter_s, working_days), 1)
                    decorridos_du = _count_working_days(ini_s, ref.isoformat(), working_days)
                    pct_esp = min(100.0, decorridos_du / total_du * 100)
            except ValueError:
                pass

        peso_total += peso
        pct_real_pond += pct_real * peso
        pct_esp_pond += pct_esp * peso

    if peso_total == 0:
        return {"progress_pct": 0.0, "prazo_decorrido_pct": 0.0, "spi": 1.0, "desvio_pct": 0.0}

    progress_pct = round(pct_real_pond / peso_total, 1)
    prazo_decorrido_pct = round(pct_esp_pond / peso_total, 1)
    spi = round(progress_pct / prazo_decorrido_pct, 2) if prazo_decorrido_pct > 0 else 1.0
    desvio_pct = round(progress_pct - prazo_decorrido_pct, 1)
    return {"progress_pct": progress_pct, "prazo_decorrido_pct": prazo_decorrido_pct, "spi": spi, "desvio_pct": desvio_pct}



def _get_last_rdo_date(contrato: str, client_id: Optional[str] = None) -> Optional[date]:
    """Retorna a data do último RDO submetido para o contrato. None se não há RDOs."""
    rows = sb_select(
        "rdo_master",
        filters={"contrato": contrato, "status": "Submetido"},
        client_id=client_id,
        order="data.desc",
        limit=1,
    ) or []
    if not rows:
        return None
    data_str = str(rows[0].get("data", ""))[:10]
    try:
        return date.fromisoformat(data_str)
    except Exception:
        return None


def _working_days_between(d_start: date, d_end: date, working_days: set = None) -> int:
    if working_days is None:
        working_days = {0, 1, 2, 3, 4, 5}  # seg–sab (padrão do contrato)
    if d_end <= d_start:
        return 0
    count = 0
    cur = d_start
    while cur < d_end:
        if cur.weekday() in working_days:
            count += 1
        cur += timedelta(days=1)
    return count


# ── Core Engineering Logic (1:1 Legacy Port) ──────────────────────────────────

def _parse_dias_uteis(dias_str: str) -> set:
    if not dias_str:
        return {0, 1, 2, 3, 4}
    _DIAS_MAP = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "sáb": 5, "dom": 6}
    result = set()
    for d in dias_str.split(","):
        key = d.strip().lower()
        if key in _DIAS_MAP:
            result.add(_DIAS_MAP[key])
    return result if result else {0, 1, 2, 3, 4}


def _add_working_days(start_iso: str, days: int, working_days: set = None) -> str:
    from datetime import date, timedelta
    if working_days is None:
        working_days = {0, 1, 2, 3, 4, 5}  # seg–sab
    try:
        current = date.fromisoformat(start_iso[:10])
        if days <= 1:
            return start_iso
        added = 1
        while added < days:
            current += timedelta(days=1)
            if current.weekday() in working_days:
                added += 1
        return current.isoformat()
    except Exception:
        return start_iso


def _count_working_days(start_iso: str, end_iso: str, working_days: set = None) -> int:
    from datetime import date, timedelta
    if working_days is None:
        working_days = {0, 1, 2, 3, 4, 5}  # seg–sab
    try:
        d0 = date.fromisoformat(start_iso[:10])
        d1 = date.fromisoformat(end_iso[:10])
        if d1 < d0:
            return 0
        count = 0
        cur = d0
        while cur <= d1:
            if cur.weekday() in working_days:
                count += 1
            cur += timedelta(days=1)
        return count
    except Exception:
        return 0


def _recalc_parent_dates(parent_id: str, contrato: str, client_id: str, _visited: set = None):
    """Atualiza APENAS o % do pai com base nos filhos (média ponderada).
    NÃO altera datas baseline — datas são imutáveis após criação para não distorcer o Gantt."""
    if _visited is None:
        _visited = set()
    if parent_id in _visited:
        return  # ciclo detectado — interrompe
    _visited.add(parent_id)

    children = sb_select("hub_atividades", filters={"parent_id": parent_id, "contrato": contrato}, client_id=client_id)
    if not children:
        return

    # Rollup % — weighted average by peso_pct, fallback to simple average
    pesos = [float(c.get("peso_pct") or 0) for c in children]
    pcts  = [float(c.get("conclusao_pct") or 0) for c in children]
    if sum(pesos) > 0:
        pct_macro = round(sum(p * w for p, w in zip(pcts, pesos)) / sum(pesos), 1)
    else:
        pct_macro = round(sum(pcts) / len(pcts), 1) if pcts else 0.0

    sb_update("hub_atividades", filters={"id": parent_id}, data={"conclusao_pct": int(min(100, pct_macro))}, client_id=client_id)

    # Cascade up
    parent_rows = sb_select("hub_atividades", filters={"id": parent_id}, limit=1, client_id=client_id)
    if parent_rows and parent_rows[0].get("parent_id"):
        _recalc_parent_dates(parent_rows[0]["parent_id"], contrato, client_id, _visited)


def _compute_forecast(r: Dict[str, Any], today: date = date.today(), working_days: set = None) -> Dict[str, Any]:
    """Cálculo de EAC e Tendência."""
    if working_days is None:
        working_days = {0, 1, 2, 3, 4, 5}  # seg–sab
    total_qty = float(r.get("total_qty", 0) or 0)
    exec_qty = float(r.get("exec_qty", 0) or 0)
    dias_plan = int(r.get("dias_planejados", 0) or 0)
    pct = float(r.get("conclusao_pct", 0) or 0)
    
    d_inicio = None
    if r.get("inicio_previsto"):
        try: d_inicio = datetime.fromisoformat(r["inicio_previsto"].split("T")[0]).date()
        except Exception: pass
        
    d_termino = None
    if r.get("termino_previsto"):
        try: d_termino = datetime.fromisoformat(r["termino_previsto"].split("T")[0]).date()
        except Exception: pass
    
    if not d_inicio or not d_termino:
        return r

    # Se a atividade foi iniciada antes do previsto (antecipação), usar a data real de início
    # do progresso para não gerar falsos atrasos. A referência é hoje vs prazo planejado.
    effective_start = min(d_inicio, today) if pct > 0 and today < d_inicio else d_inicio
    dias_uteis_decorridos = _working_days_between(effective_start, today)
    dia_atual = min(dias_uteis_decorridos, dias_plan)

    prod_plan = total_qty / dias_plan if total_qty > 0 and dias_plan > 0 else 0.0
    prod_real = exec_qty / max(1, dias_uteis_decorridos) if exec_qty > 0 else 0.0
    desvio_pct = ((prod_real - prod_plan) / prod_plan * 100) if prod_plan > 0 else 0.0
    
    # EAC Projection
    data_fim_prevista = ""
    desvio_dias = 0
    if prod_real > 0 and total_qty > 0 and pct < 100:
        saldo = max(0.0, total_qty - exec_qty)
        dias_restantes = max(1, round(saldo / prod_real))

        current = today
        added = 0
        while added < dias_restantes:
            current += timedelta(days=1)
            if current.weekday() in working_days:
                added += 1
        fim_prev = current
        data_fim_prevista = fim_prev.isoformat()
        if d_termino:
            if fim_prev > d_termino:
                desvio_dias = _working_days_between(d_termino, fim_prev)
            else:
                desvio_dias = -_working_days_between(fim_prev, d_termino)

    # Tendency Logic — atividades antecipadas (iniciadas antes do previsto) são "acima"
    prazo_estourado = desvio_dias > 0
    antecipada = today < d_inicio and pct > 0
    if exec_qty == 0 and not antecipada: tendencia = "sem_dados"
    elif pct >= 100: tendencia = "concluida"
    elif antecipada: tendencia = "acima"  # iniciou antes — sempre positivo
    elif desvio_pct >= 10.0 and not prazo_estourado: tendencia = "acima"
    elif desvio_pct <= -10.0 or prazo_estourado: tendencia = "abaixo"
    else: tendencia = "dentro"

    # pct_esperado: se hoje ainda está antes do início previsto, esperado = 0 (é adiantamento)
    if today < d_inicio:
        pct_esperado_calc = 0.0
    else:
        pct_esperado_calc = round(min(100.0, dia_atual / dias_plan * 100), 1) if dias_plan > 0 else 0.0

    return {
        **r,
        "_tendencia": tendencia,
        "_data_fim_prevista": data_fim_prevista,
        "_desvio_dias": desvio_dias,
        "_prod_plan": round(prod_plan, 2),
        "_prod_real": round(prod_real, 2),
        "_pct_esperado": pct_esperado_calc,
        "_antecipada": today < d_inicio and pct > 0,  # flag para o frontend
    }


def _propagate_schedule_changes(activity_id: str, diff_days: int, contrato: str, client_id: str):
    """Propaga o atraso/antecipação para todos os sucessores vinculados."""
    # Buscar atividades que dependem desta
    successors = sb_select("hub_atividades", filters={"dependencia_id": activity_id, "contrato": contrato}, client_id=client_id)
    
    for s in successors:
        new_ini = _add_working_days(s["inicio_previsto"], diff_days + 1)
        new_ter = _add_working_days(s["termino_previsto"], diff_days + 1)
        
        sb_update("hub_atividades", filters={"id": s["id"]}, data={
            "inicio_previsto": new_ini,
            "termino_previsto": new_ter
        }, client_id=client_id)
        
        # Recursal
        _propagate_schedule_changes(s["id"], diff_days, contrato, client_id)


def _calculate_risk_score(df_proj: Any, financeiro_df: Any, contrato_info: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula Nota de Risco 0-10 para o projeto com 7 fatores ponderados (Port 1:1)."""
    if df_proj.empty:
        return {"nota": "0.0", "label": "CONTROLADO", "color": "#22c55e"}
    
    # 1. Atraso Cronograma (30%)
    today = date.today()
    desvio_total = 0.0
    for _, r in df_proj.iterrows():
        f = _compute_forecast(dict(r), today=today)
        expected = f.get("_pct_esperado", 0)
        actual = float(r.get("conclusao_pct", 0))
        desvio_total += (actual - expected)
    
    avg_desvio = desvio_total / len(df_proj) if not df_proj.empty else 0
    f1_score = 0.0
    if avg_desvio <= -25: f1_score = 10.0
    elif avg_desvio <= -15: f1_score = 8.0
    elif avg_desvio <= -5: f1_score = 5.0
    elif avg_desvio < 0: f1_score = 2.0
    
    # 2. Criticidade (20%)
    criticas_atrasadas = 0
    if "critico" in df_proj.columns:
        criticas = df_proj[df_proj["critico"].astype(str).str.lower().isin(["sim", "1", "true"])]
        for _, r in criticas.iterrows():
             f = _compute_forecast(dict(r), today=today)
             if float(r.get("conclusao_pct", 0)) < f.get("_pct_esperado", 0) - 10:
                 criticas_atrasadas += 1
    f2_score = min(10.0, criticas_atrasadas * 2.0)
    
    # 3. Clima (10%)
    chuva = float(contrato_info.get("chuva_acumulada_mm", 0) or 0)
    f3_score = 0.0
    if chuva > 100: f3_score = 8.0
    elif chuva > 50: f3_score = 5.0
    
    # Final Score (Simplified weighted average)
    nota = round((f1_score * 0.3) + (f2_score * 0.2) + (f3_score * 0.1) + 2.0, 1)
    
    if nota <= 3: label, color = "BAIXO", "#22c55e"
    elif nota <= 6: label, color = "ATENÇÃO", "#F59E0B"
    elif nota <= 8: label, color = "ALTO", "#EF4444"
    else: label, color = "CRÍTICO", "#dc2626"

    criterios = [
        {"nome": "Atraso Cronograma",  "nota": round(f1_score, 1), "peso": "30%"},
        {"nome": "Atividades Críticas","nota": round(f2_score, 1), "peso": "20%"},
        {"nome": "Impacto Climático",  "nota": round(f3_score, 1), "peso": "10%"},
        {"nome": "Baseline",           "nota": 2.0,                "peso": "40%"},
    ]

    return {"nota": str(nota), "label": label, "color": color, "criterios": criterios}


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR DE INTELIGÊNCIA — Velocity, Anomalias, Risk Score, Caminho Crítico, Delta
# ══════════════════════════════════════════════════════════════════════════════

def _calc_velocity(atividade: dict, historico: list) -> dict:
    """Calcula produtividade real por DIA TRABALHADO (não por dia corrido).
    Retorna velocity_real, dias_trabalhados, saldo, dias_restantes_projetados, eac_date."""
    aid = str(atividade.get("id", ""))
    total_qty = float(atividade.get("total_qty") or 0)
    exec_qty  = float(atividade.get("exec_qty") or 0)

    # Filtra histórico desta atividade, com produção > 0
    registros = sorted(
        [h for h in historico if str(h.get("atividade_id", "")) == aid
         and float(h.get("producao_dia") or 0) > 0],
        key=lambda h: str(h.get("data") or "")
    )

    dias_trabalhados = len(registros)
    producao_acum    = sum(float(h.get("producao_dia") or 0) for h in registros)
    velocity_real    = round(producao_acum / dias_trabalhados, 2) if dias_trabalhados > 0 else 0.0

    saldo = max(0.0, total_qty - exec_qty)
    dias_restantes = round(saldo / velocity_real) if velocity_real > 0 else None

    _wd = {0, 1, 2, 3, 4, 5}  # seg–sab (padrão do contrato)
    eac_date = None
    if dias_restantes is not None:
        current = date.today()
        added = 0
        while added < dias_restantes:
            current += timedelta(days=1)
            if current.weekday() in _wd:
                added += 1
        eac_date = current.isoformat()

    # Aceleração: últimos 3 dias vs todos os outros
    trend = "estavel"
    if len(registros) >= 4:
        recentes = [float(h.get("producao_dia") or 0) for h in registros[-3:]]
        anteriores = [float(h.get("producao_dia") or 0) for h in registros[:-3]]
        v_rec = sum(recentes) / len(recentes)
        v_ant = sum(anteriores) / len(anteriores)
        if v_ant > 0:
            delta = (v_rec - v_ant) / v_ant
            if delta > 0.15:
                trend = "acelerando"
            elif delta < -0.15:
                trend = "desacelerando"

    return {
        "velocity_real":           velocity_real,
        "dias_trabalhados":        dias_trabalhados,
        "saldo":                   saldo,
        "dias_restantes_proj":     dias_restantes,
        "eac_date":                eac_date,
        "trend":                   trend,
        "producao_planejada_dia":  round(total_qty / max(1, int(atividade.get("dias_planejados") or 1)), 2),
    }


def _detect_anomalies(atividades: list, rdo_recentes: list, historico: list) -> list:
    """Detecta anomalias factuais nos dados — sem LLM, sem margem para erro.
    Retorna lista de dicts {tipo, title, body, priority, atividade_id?}."""
    anomalies = []
    today = date.today()

    # Índice de efetivo por atividade nos RDOs recentes
    from backend.integrations.supabase import sb_select as _sb

    # 1. exec_qty > total_qty (produção impossível)
    for a in atividades:
        exec_q = float(a.get("exec_qty") or 0)
        total_q = float(a.get("total_qty") or 0)
        if total_q > 0 and exec_q > total_q * 1.05:
            anomalies.append({
                "tipo": "dados_invalidos",
                "title": f"Produção acima do total: {a.get('atividade','?')[:40]}",
                "body": f"exec_qty={exec_q} > total_qty={total_q} {a.get('unidade','')}. Dado inconsistente — revise o cadastro.",
                "priority": "High",
                "atividade_id": str(a.get("id", "")),
            })

    # 2. Atividade crítica sem nenhum movimento por 3+ dias úteis
    for a in atividades:
        critico_val = a.get("critico")
        if not (critico_val is True or str(critico_val).lower() in ("true", "sim", "1")):
            continue
        pct = float(a.get("conclusao_pct") or 0)
        if pct >= 100:
            continue
        last_rdo = str(a.get("last_rdo_date") or "")[:10]
        ini = str(a.get("inicio_previsto") or "")[:10]
        if not last_rdo and ini and ini <= today.isoformat():
            anomalies.append({
                "tipo": "critica_parada",
                "title": f"Atividade crítica sem registro há 3+ dias",
                "body": f"'{a.get('atividade','?')[:45]}' está em {pct}% e não tem RDO registrado. Verificar imediatamente.",
                "priority": "High",
                "atividade_id": str(a.get("id", "")),
            })
        elif last_rdo:
            try:
                d_last = date.fromisoformat(last_rdo)
                dias_sem_rdo = _working_days_between(d_last, today)
                if dias_sem_rdo >= 3 and pct < 100:
                    anomalies.append({
                        "tipo": "critica_parada",
                        "title": f"Atividade crítica parada há {dias_sem_rdo} dias úteis",
                        "body": f"'{a.get('atividade','?')[:45]}' em {pct}%. Último registro: {last_rdo}. Risco de atraso em cascata.",
                        "priority": "High",
                        "atividade_id": str(a.get("id", "")),
                    })
            except ValueError:
                pass

    # 3. Dias sem RDO (projeto iniciado e sem registro há 2+ dias úteis)
    if rdo_recentes:
        try:
            ultimo = date.fromisoformat(str(rdo_recentes[0].get("data", ""))[:10])
            gap = _working_days_between(ultimo, today)
            if gap >= 2:
                anomalies.append({
                    "tipo": "sem_rdo",
                    "title": f"{gap} dias úteis sem RDO registrado",
                    "body": f"Último RDO em {ultimo.isoformat()}. Sem registros diários, o controle de avanço e a memória de obra ficam comprometidos.",
                    "priority": "Medium",
                })
        except (ValueError, TypeError):
            pass

    # 4. Interrupções recorrentes no mesmo motivo
    motivos: dict = {}
    for r in rdo_recentes:
        obs = str(r.get("observacoes") or "").lower()
        for kw in ["acesso", "energia", "chuva", "material", "equipamento", "andaime"]:
            if kw in obs:
                motivos[kw] = motivos.get(kw, 0) + 1
    for kw, cnt in motivos.items():
        if cnt >= 2:
            anomalies.append({
                "tipo": "recorrencia",
                "title": f"Causa recorrente de interrupção: {kw}",
                "body": f"Mencionado em {cnt} RDOs recentes. Ação preventiva recomendada para eliminar bloqueio sistêmico.",
                "priority": "Medium",
            })
            break  # 1 anomalia de recorrência é suficiente

    return anomalies


def _build_dependency_chain(atividade_id: str, atividades: list, depth: int = 0) -> list:
    """Monta cadeia de sucessores a partir de dependencia_id. Máximo 5 níveis."""
    if depth >= 5:
        return []
    chain = []
    for a in atividades:
        if str(a.get("dependencia_id") or "") == atividade_id:
            chain.append(a)
            chain.extend(_build_dependency_chain(str(a["id"]), atividades, depth + 1))
    return chain


def _calc_risk_score(atividade: dict, velocity: dict, today: date) -> float:
    """Score de risco 0-10 por atividade.
    Fatores: desvio de progresso (40%), dias até prazo (30%), caminho crítico (20%), trend (10%)."""
    score = 0.0

    pct_real = float(atividade.get("conclusao_pct") or 0)
    if pct_real >= 100:
        return 0.0

    ini_s = str(atividade.get("inicio_previsto") or "")[:10]
    ter_s = str(atividade.get("termino_previsto") or "")[:10]
    if not ini_s or not ter_s:
        return 2.0  # sem datas = risco base

    try:
        d_ini = date.fromisoformat(ini_s)
        d_ter = date.fromisoformat(ter_s)
    except ValueError:
        return 2.0

    _wd = {0, 1, 2, 3, 4, 5}  # seg–sab

    # Fator 1: desvio de progresso vs esperado (40%) — usa dias úteis
    total_du = max(_count_working_days(ini_s, ter_s, _wd), 1)
    decorridos_du = max(_count_working_days(ini_s, today.isoformat(), _wd), 0) if today >= d_ini else 0
    pct_esp = min(100.0, decorridos_du / total_du * 100)
    desvio = pct_esp - pct_real  # positivo = atrasado
    f1 = min(10.0, max(0.0, desvio / 10.0))
    score += f1 * 0.40

    # Fator 2: urgência de prazo (30%) — em dias úteis
    dias_ate_prazo = _working_days_between(today, d_ter, _wd)
    if today > d_ter:
        f2 = 10.0  # já venceu
    elif dias_ate_prazo <= 2:
        f2 = 8.0
    elif dias_ate_prazo <= 5:
        f2 = 5.0
    elif dias_ate_prazo <= 10:
        f2 = 2.0
    else:
        f2 = 0.0
    score += f2 * 0.30

    # Fator 3: caminho crítico (20%) — campo booleano no DB
    critico_val = atividade.get("critico")
    is_critico = critico_val is True or str(critico_val).lower() in ("true", "sim", "1")
    f3 = 8.0 if is_critico else 0.0
    score += f3 * 0.20

    # Fator 4: trend de produtividade (10%)
    trend = velocity.get("trend", "estavel")
    if trend == "desacelerando":
        f4 = 6.0
    elif trend == "acelerando":
        f4 = 0.0
    else:
        f4 = 2.0
    score += f4 * 0.10

    return round(min(10.0, score), 1)


def _build_insights_llm(
    atividades: list,
    rdo_recentes: list,
    contrato: str,
    today: date,
    historico: list | None = None,
    insights_anteriores: list | None = None,
) -> list:
    """Gera insights via LLM com contexto completo:
    velocity por dia trabalhado, anomalias, caminho crítico, delta vs anterior."""
    import json

    historico = historico or []
    insights_anteriores = insights_anteriores or []

    # Sem RDOs submetidos: não há base para análise de desvio/atraso
    rdos_submetidos_b = [r for r in rdo_recentes if r.get("status") == "Submetido"]
    if not rdos_submetidos_b and atividades:
        primeiro_ini = min(
            (str(a.get("inicio_previsto", ""))[:10] for a in atividades if a.get("inicio_previsto")),
            default=today.isoformat()
        )
        try:
            dias_sem_rdo = max(0, (today - date.fromisoformat(primeiro_ini)).days)
        except Exception:
            dias_sem_rdo = 0
        return [{
            "title": "Nenhum RDO submetido ainda",
            "body": f"Obra com {dias_sem_rdo} dia(s) sem RDO. Envie o primeiro RDO para ativar o monitoramento de progresso.",
            "priority": "Medium", "tipo": "risco",
        }]

    # ── #1 Velocity Engine ─────────────────────────────────────────────────────
    velocities: dict = {}
    for a in atividades:
        if float(a.get("total_qty") or 0) > 0:
            velocities[str(a["id"])] = _calc_velocity(a, historico)

    # ── #2 Anomaly Detection ───────────────────────────────────────────────────
    anomalias = _detect_anomalies(atividades, rdo_recentes, historico)

    # ── #3 Risk Score ──────────────────────────────────────────────────────────
    for a in atividades:
        vel = velocities.get(str(a.get("id", "")), {})
        a["_risk_score"] = _calc_risk_score(a, vel, today)

    # ── #5 Caminho Crítico ─────────────────────────────────────────────────────
    # last_rdo: pega o mais recente dos rdos_recentes (já filtrado por Submetido no caller)
    _last_rdo_ref = None
    if rdo_recentes:
        try:
            _last_rdo_ref = date.fromisoformat(str(rdo_recentes[0].get("data", ""))[:10])
        except Exception:
            pass
    _hmap_llm = _build_hist_map(historico)
    kpis = _calc_progress_spi(atividades, today, ref_date=_last_rdo_ref, hist_map=_hmap_llm)
    _ref_rdo = _last_rdo_ref or today
    em_andamento = [a for a in atividades if 0 < float(a.get("conclusao_pct") or 0) < 100]
    # Atrasada: prazo vencido na data do último RDO E atividade já deveria ter iniciado
    atrasadas    = [a for a in atividades if a.get("termino_previsto")
                    and str(a["termino_previsto"])[:10] < _ref_rdo.isoformat()
                    and str(a.get("inicio_previsto",""))[:10] <= _ref_rdo.isoformat()
                    and float(a.get("conclusao_pct") or 0) < 100]
    # proximos_7d: só atividades que já iniciaram ou iniciam até a data do RDO
    proximos_7d  = [a for a in atividades if a.get("termino_previsto")
                    and str(a.get("inicio_previsto",""))[:10] <= _ref_rdo.isoformat()
                    and 0 <= (date.fromisoformat(str(a["termino_previsto"])[:10]) - today).days <= 7
                    and float(a.get("conclusao_pct") or 0) < 100]
    antecipadas  = [a for a in atividades if a.get("inicio_previsto")
                    and str(a["inicio_previsto"])[:10] > today.isoformat()
                    and float(a.get("conclusao_pct") or 0) > 0]
    concluidas   = [a for a in atividades if float(a.get("conclusao_pct") or 0) >= 100]

    # Atividades por risk score (mais críticas primeiro)
    top_risco = sorted(
        [a for a in atividades if float(a.get("conclusao_pct") or 0) < 100],
        key=lambda a: a.get("_risk_score", 0), reverse=True
    )[:6]

    ativ_ctx = []
    for a in top_risco:
        aid = str(a.get("id", ""))
        vel = velocities.get(aid, {})
        cadeia = _build_dependency_chain(aid, atividades)
        cadeia_txt = " → ".join([c.get("atividade", "?")[:25] for c in cadeia[:3]]) if cadeia else ""

        # Calcula % esperado para esta atividade na data do último RDO
        pct_esperado_txt = ""
        ini_s = str(a.get("inicio_previsto",""))[:10]
        ter_s = str(a.get("termino_previsto",""))[:10]
        if ini_s and ter_s:
            try:
                d_ini = date.fromisoformat(ini_s)
                d_ter = date.fromisoformat(ter_s)
                d_total = max(1, (d_ter - d_ini).days)
                if d_ini > _ref_rdo:
                    pct_esperado_txt = " | FUTURA(não iniciada)"
                else:
                    d_decorrido = min(d_total, max(0, (_ref_rdo - d_ini).days))
                    pct_esp = round(d_decorrido / d_total * 100)
                    pct_real = float(a.get("conclusao_pct") or 0)
                    delta = round(pct_real - pct_esp)
                    pct_esperado_txt = f" | esp={pct_esp}% real={pct_real:.0f}% delta={delta:+d}%"
            except Exception:
                pass

        vel_txt = ""
        if vel.get("velocity_real", 0) > 0:
            vel_txt = (
                f" | vel={vel['velocity_real']}/dia"
                f"({vel['trend']})"
                f" | EAC={vel.get('eac_date','?')}"
                f" | saldo={vel.get('saldo',0):.0f}"
            )

        ativ_ctx.append(
            f"  - [RISCO={a.get('_risk_score',0)}] {a.get('atividade','?')[:45]}: "
            f"{a.get('conclusao_pct',0)}% | ini={ini_s} | prazo={ter_s}"
            f"{pct_esperado_txt}{vel_txt}"
            + (f" | BLOQUEIA: {cadeia_txt}" if cadeia_txt else "")
        )

    # RDO context rico
    rdo_ctx = []
    for r in rdo_recentes[:5]:
        rdo_ctx.append(
            f"  - {str(r.get('data',''))[:10]}: clima={r.get('condicao_climatica','?')},"
            f" equipe={r.get('equipe_alocada','?')}p,"
            f" chuva={r.get('houve_chuva',False)},"
            f" interr={r.get('houve_interrupcao',False)},"
            f" acid={r.get('houve_acidente',False)},"
            f" obs='{str(r.get('observacoes',''))[:80]}'"
        )

    # Anomalias detectadas
    anom_ctx = [f"  - [ANOMALIA/{a['tipo'].upper()}] {a['title']}: {a['body']}" for a in anomalias]

    # ── #4 Delta vs insights anteriores ───────────────────────────────────────
    delta_ctx = ""
    if insights_anteriores:
        titulos_ant = [i.get("title", "") for i in insights_anteriores]
        delta_ctx = f"\nINSIGHTS ANTERIORES (para gerar continuidade e delta):\n"
        delta_ctx += "\n".join(f"  - {t}" for t in titulos_ant)
        delta_ctx += "\nGere insights que EVOLUEM em relação aos anteriores — mostre o que mudou.\n"

    # Dia livre próximo
    dia_livre = ""
    if rdo_recentes:
        try:
            d_prox = date.fromisoformat(str(rdo_recentes[0].get("data",""))[:10]) + timedelta(days=1)
            atv_amanha = [a for a in atividades
                if str(a.get("inicio_previsto",""))[:10] <= d_prox.isoformat() <= str(a.get("termino_previsto",""))[:10]
                and float(a.get("conclusao_pct") or 0) < 100]
            if not atv_amanha:
                dia_livre = f"\nATENÇÃO: {d_prox.isoformat()} não tem atividades programadas — oportunidade de antecipação.\n"
        except Exception:
            pass

    rdos_submetidos_llm = [r for r in rdo_recentes if r.get("status") == "Submetido"]
    sem_rdo_aviso = "" if rdos_submetidos_llm else "\n⚠️ ATENÇÃO: Nenhum RDO submetido ainda. NÃO reporte atrasos. O único insight relevante é alertar que RDOs precisam ser enviados.\n"

    context = f"""CONTRATO: {contrato} | DATA: {today.isoformat()}
{sem_rdo_aviso}
PROGRESSO FÍSICO:
  Realizado={kpis['progress_pct']}% | Esperado={kpis['prazo_decorrido_pct']}% | Desvio={kpis['desvio_pct']:+.1f}% | SPI={kpis['spi']}
  Total={len(atividades)} ativs | Concluídas={len(concluidas)} | Em andamento={len(em_andamento)} | Atrasadas={len(atrasadas)} | Vencendo 7d={len(proximos_7d)}

ATIVIDADES POR RISCO (score 0-10, velocity real, caminho crítico):
{chr(10).join(ativ_ctx) if ativ_ctx else '  Nenhuma atividade pendente'}

ANOMALIAS DETECTADAS AUTOMATICAMENTE:
{chr(10).join(anom_ctx) if anom_ctx else '  Nenhuma anomalia detectada'}

RDOs RECENTES:
{chr(10).join(rdo_ctx) if rdo_ctx else '  Sem RDOs'}
{dia_livre}{delta_ctx}"""

    system_prompt = """Você é o Agente de Inteligência Artificial da plataforma Bomtempo — especialista sênior em gestão de obras de infraestrutura.

Analise os dados fornecidos e gere EXATAMENTE 4 insights em JSON. Cada insight:
- "title": título direto, max 55 chars
- "body": análise COM NÚMEROS REAIS — cite atividades, datas, delta, velocity, EAC. Max 180 chars.
- "priority": "High" | "Medium" | "Low"
- "tipo": "risco" | "oportunidade" | "anomalia" | "producao" | "equipe" | "clima" | "delta"

REGRAS INVIOLÁVEIS — leia antes de qualquer análise:

1. ATIVIDADES FUTURAS: qualquer atividade marcada com "FUTURA(não iniciada)" NÃO tem atraso, risco ou pendência.
   Nunca alerte sobre atividades que ainda não deveriam ter iniciado.

2. FREQUÊNCIA DE RDO: RDO é registro diário da obra — 1 por dia útil trabalhado é o correto.
   Se há 1 RDO para cada dia de projeto, a frequência está PERFEITA. Nunca sugira "enviar mais RDOs" quando a cobertura já é total.

3. SAÚDE DO PROJETO: Se SPI ≥ 1.0 e desvio ≥ 0% → projeto adiantado ou no ritmo.
   Neste caso, NÃO gere alertas de atraso. Gere oportunidades (antecipar atividades, manter ritmo).

4. PRODUTIVIDADE: Se delta de uma atividade ≥ 0% (real ≥ esperado) → produtividade positiva.
   Destaque como ponto forte. Se velocity_real > taxa_plan → atividade será concluída antes do prazo.

5. ATRASADA: atividade só está atrasada se termino_previsto < data_ultimo_rdo E inicio_previsto ≤ data_ultimo_rdo E pct < 100%.
   Não chame de atrasada atividade futura, não iniciada, ou dentro do prazo.

6. DADOS REAIS: Nunca invente dados. Use apenas o que está no contexto. Se não há informação suficiente, diga "dados insuficientes".

HIERARQUIA DE PRIORIZAÇÃO (aplicar nesta ordem):
1. Anomalias reais (dados impossíveis, atividade crítica com delta muito negativo)
2. Atividade atrasada (conforme regra 5) com caminho crítico bloqueado
3. Velocity abaixo do necessário em atividade que já iniciou
4. Oportunidade: ritmo acima do esperado, antecipação possível, conclusão antes do prazo
5. Padrão climático ou interrupções afetando produção

DIRETRIZES DE QUALIDADE:
- Seja cirúrgico: "Perfuração: 80/dia real, taxa plan 100/dia, delta -20% → EAC 3 dias além do prazo" é melhor que "produção insuficiente"
- Se delta ≥ 0% para atividade em andamento: "Atividade X está +Yd% acima do esperado, tende a concluir antes do prazo"
- Se há delta vs insights anteriores: diga o que MUDOU
- Se não houver RDOs: o único insight válido é alertar a falta de RDOs

Responda SOMENTE com JSON array:
[{"title":"...","body":"...","priority":"...","tipo":"..."},...]"""

    try:
        from backend.integrations.ai import query as ai_query
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": context},
        ]
        response_text = ai_query(messages, max_tokens=1000, temperature=0.3)
        if not response_text:
            raise ValueError("empty response")

        start = response_text.find("[")
        end   = response_text.rfind("]") + 1
        if start >= 0 and end > start:
            parsed = json.loads(response_text[start:end])
            valid = [
                {
                    "title":    i.get("title", "Insight"),
                    "body":     i.get("body", ""),
                    "priority": i.get("priority", "Medium"),
                    "tipo":     i.get("tipo", "risco"),
                }
                for i in parsed if isinstance(i, dict)
            ]
            if valid:
                return valid

    except Exception as e:
        logger.warning(f"LLM insights failed for {contrato}: {e}")

    return _rule_based_insights(atividades, rdo_recentes, today, anomalias, velocities)


def _rule_based_insights(
    atividades: list,
    rdo_recentes: list,
    today: date,
    anomalias: list | None = None,
    velocities: dict | None = None,
) -> list:
    """Fallback rule-based enriquecido com velocity e anomalias."""
    _last_rdo = None
    if rdo_recentes:
        try:
            _last_rdo = date.fromisoformat(str(rdo_recentes[0].get("data", ""))[:10])
        except Exception:
            pass
    kpis       = _calc_progress_spi(atividades, today, ref_date=_last_rdo)
    anomalias  = anomalias or []
    velocities = velocities or {}
    insights: list = []

    # Sem RDOs submetidos: único insight relevante é alertar sobre RDOs faltando
    rdos_submetidos = [r for r in rdo_recentes if r.get("status") == "Submetido"]
    if not rdos_submetidos and atividades:
        # Calcula quantos dias de obra passaram sem RDO
        primeiro_ini = min(
            (str(a.get("inicio_previsto", ""))[:10] for a in atividades if a.get("inicio_previsto")),
            default=today.isoformat()
        )
        try:
            dias_sem_rdo = max(0, (today - date.fromisoformat(primeiro_ini)).days)
        except Exception:
            dias_sem_rdo = 0
        insights.append({
            "title": "Nenhum RDO submetido ainda",
            "body": f"Obra com {dias_sem_rdo} dia(s) sem RDO. Desvio e SPI só são calculados após o primeiro RDO.",
            "priority": "Medium", "tipo": "risco",
        })
        return insights[:4]

    # Anomalias primeiro — são factuais
    for a in anomalias[:2]:
        insights.append({"title": a["title"], "body": a["body"], "priority": a["priority"], "tipo": "anomalia"})

    # Atividades atrasadas somente se há RDO (ref_date preenchida)
    _ref_iso = (_last_rdo or today).isoformat()
    atrasadas = [a for a in atividades
                 if a.get("termino_previsto")
                 and str(a["termino_previsto"])[:10] < _ref_iso
                 and float(a.get("conclusao_pct") or 0) < 100]
    proximos_7d = []
    antecipadas = []
    for a in atividades:
        try:
            ter = str(a.get("termino_previsto", ""))[:10]
            ini = str(a.get("inicio_previsto", ""))[:10]
            pct = float(a.get("conclusao_pct") or 0)
            if ter and 0 <= (date.fromisoformat(ter) - today).days <= 7 and pct < 80:
                proximos_7d.append(a)
            if ini and ini > today.isoformat() and pct > 0:
                antecipadas.append(a)
        except Exception:
            pass

    if atrasadas and len(insights) < 4:
        critica = next((a for a in atrasadas if a.get("critico") is True or str(a.get("critico","")).lower() in ("true","sim","1")), atrasadas[0])
        vel = velocities.get(str(critica.get("id","")), {})
        eac_txt = f" EAC={vel['eac_date']}." if vel.get("eac_date") else ""
        insights.append({
            "title": f"{len(atrasadas)} atividade(s) com prazo vencido",
            "body": f"'{critica.get('atividade','?')[:40]}' em {critica.get('conclusao_pct',0)}% após prazo.{eac_txt} SPI={kpis['spi']:.2f}.",
            "priority": "High", "tipo": "risco",
        })

    # Velocity insight para atividades com quantidade e velocity calculada
    vel_insights = []
    for a in atividades:
        vel = velocities.get(str(a.get("id","")), {})
        if not vel or vel.get("velocity_real", 0) == 0:
            continue
        plan = vel.get("producao_planejada_dia", 0)
        real = vel["velocity_real"]
        if plan > 0 and real < plan * 0.5:  # produzindo menos de 50% do planejado
            gap = round(plan - real, 1)
            vel_insights.append({
                "title": f"Ritmo insuficiente: {a.get('atividade','?')[:35]}",
                "body": f"Produz {real}/dia vs {plan}/dia planejado (gap={gap}/dia). Saldo: {vel.get('saldo',0):.0f} {a.get('unidade','')}. EAC: {vel.get('eac_date','?')}.",
                "priority": "High", "tipo": "producao",
            })
    if vel_insights and len(insights) < 4:
        insights.append(vel_insights[0])

    if kpis["spi"] < 0.85 and len(insights) < 4:
        insights.append({
            "title": "Produtividade abaixo do planejado",
            "body": f"SPI={kpis['spi']:.2f}. Realizado {kpis['progress_pct']}% vs esperado {kpis['prazo_decorrido_pct']}%. Revise alocação.",
            "priority": "High" if kpis["spi"] < 0.70 else "Medium", "tipo": "risco",
        })
    elif kpis["spi"] > 1.10 and len(insights) < 4:
        insights.append({
            "title": "Projeto adiantado — oportunidade",
            "body": f"SPI={kpis['spi']:.2f}. Antecipe marcos ou realoque equipe para frentes críticas.",
            "priority": "Low", "tipo": "oportunidade",
        })

    if proximos_7d and len(insights) < 4:
        nomes = ", ".join([f"'{a.get('atividade','?')[:20]}'" for a in proximos_7d[:2]])
        insights.append({
            "title": f"{len(proximos_7d)} atividade(s) vencendo em 7 dias",
            "body": f"{nomes} com menos de 80% de conclusão. Ação imediata.",
            "priority": "Medium", "tipo": "risco",
        })

    if rdo_recentes and len(insights) < 4:
        chuva_d = sum(1 for r in rdo_recentes if r.get("houve_chuva") or str(r.get("condicao_climatica","")).lower() in ("chuvoso","tempestade"))
        inter_d = sum(1 for r in rdo_recentes if r.get("houve_interrupcao"))
        if chuva_d >= 2 or inter_d >= 2:
            insights.append({
                "title": "Impacto recorrente de interrupções",
                "body": f"{chuva_d} dia(s) chuva, {inter_d} interrupção(ões) em {len(rdo_recentes)} RDOs. Buffer de prazo recomendado.",
                "priority": "Medium", "tipo": "clima",
            })

    if not insights:
        insights.append({
            "title": "Operação dentro do planejado",
            "body": f"SPI={kpis['spi']:.2f}. Desvio={kpis['desvio_pct']:+.1f}%. Ritmo nominal.",
            "priority": "Low", "tipo": "oportunidade",
        })

    return insights[:4]


def _persist_insights(contrato: str, insights: list, client_id: str | None, last_rdo_id: str = "") -> None:
    """Upsert em agente_insights."""
    payload = {
        "contrato":    contrato,
        "insights":    insights,
        "last_rdo_id": last_rdo_id,
        "updated_at":  datetime.utcnow().isoformat(),
        "client_id":   client_id,
    }
    existing = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
    if existing:
        sb_update("agente_insights", filters={"id": existing[0]["id"]}, data=payload)
    else:
        sb_insert("agente_insights", payload)


@router.get("/agente/insights")
async def get_agente_insights(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Retorna insights persistidos. Se não houver, gera ao vivo."""
    existing = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
    if existing and existing[0].get("insights"):
        raw = existing[0]["insights"]
        insights = raw if isinstance(raw, list) else []
        if insights:
            _ativs = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
            _hist_gi = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
            kpis = _calc_progress_spi(
                _ativs,
                date.today(),
                _get_working_days(contrato, client_id),
                ref_date=_get_last_rdo_date(contrato, client_id),
                hist_map=_build_hist_map(_hist_gi),
            )
            return {"insights": insights, "spi": kpis["spi"], "pct_geral": kpis["progress_pct"]}

    return await trigger_insights_generation(body={"contrato": contrato}, _user=_user, client_id=client_id)


@router.post("/agente/insights/generate")
async def trigger_insights_generation(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Gera insights via LLM (velocity + anomalias + caminho crítico + delta), persiste e retorna."""
    contrato = body.get("contrato", "")
    if not contrato:
        return {"ok": False, "error": "contrato obrigatório"}

    today      = date.today()
    atividades = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    rdos       = sb_select("rdo_master",     filters={"contrato": contrato, "status": "Submetido"}, client_id=client_id, order="data.desc", limit=7) or []
    historico  = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=300) or []

    # Carrega insights anteriores para o delta
    existing = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
    insights_ant = (existing[0].get("insights") or []) if existing else []

    insights = _build_insights_llm(atividades, rdos, contrato, today, historico, insights_ant)
    last_rdo_date = _get_last_rdo_date(contrato, client_id)
    _hmap_ins = _build_hist_map(historico)
    kpis     = _calc_progress_spi(atividades, today, _get_working_days(contrato, client_id), ref_date=last_rdo_date, hist_map=_hmap_ins)

    try:
        _persist_insights(contrato, insights, client_id)
    except Exception:
        pass

    return {"ok": True, "insights": insights, "spi": kpis["spi"], "pct_geral": kpis["progress_pct"]}


# ── Agente: Chat Contextual sobre a Obra ──────────────────────────────────────

@router.post("/agente/chat")
async def agente_chat(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Chat com o Agente IA sobre o cronograma da obra.
    Mantém sessão por contrato. Contexto completo injetado no system prompt."""
    import json as _json

    contrato   = body.get("contrato", "")
    mensagem   = body.get("mensagem", "").strip()
    session_id = body.get("session_id")  # None = nova sessão

    if not contrato or not mensagem:
        return {"ok": False, "error": "contrato e mensagem obrigatórios"}

    today      = date.today()
    atividades = sb_select("hub_atividades",          filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    rdos       = sb_select("rdo_master",              filters={"contrato": contrato, "status": "Submetido"}, client_id=client_id, order="data.desc", limit=5) or []
    historico  = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=200) or []
    _last_rdo_chat = _get_last_rdo_date(contrato, client_id)
    _hmap_chat = _build_hist_map(historico)
    kpis       = _calc_progress_spi(atividades, today, _get_working_days(contrato, client_id), ref_date=_last_rdo_chat, hist_map=_hmap_chat)

    # Velocity para todas as atividades com qty
    velocities = {}
    for a in atividades:
        if float(a.get("total_qty") or 0) > 0:
            velocities[str(a["id"])] = _calc_velocity(a, historico)

    # Anomalias
    anomalias = _detect_anomalies(atividades, rdos, historico)

    # Contexto da obra para o system prompt
    _ref_chat   = (_last_rdo_chat or today).isoformat()
    atrasadas   = [a for a in atividades if a.get("termino_previsto") and str(a["termino_previsto"])[:10] < _ref_chat and float(a.get("conclusao_pct") or 0) < 100]
    proximos_7d = [a for a in atividades if a.get("termino_previsto") and 0 <= (date.fromisoformat(str(a["termino_previsto"])[:10]) - today).days <= 7 and float(a.get("conclusao_pct") or 0) < 100]

    ativ_resumo = []
    for a in sorted(atividades, key=lambda x: float(x.get("_risk_score") or 0), reverse=True)[:15]:
        vel = velocities.get(str(a.get("id","")), {})
        total_qty = float(a.get("total_qty") or 0)
        exec_qty  = float(a.get("exec_qty") or 0)
        # Se velocity_real = 0 mas há qty, calcula taxa planejada para estimativas
        if vel.get("velocity_real", 0) > 0:
            vel_txt = f", vel_real={vel['velocity_real']}/dia, EAC={vel.get('eac_date','?')}"
        elif total_qty > 0:
            # Taxa planejada: total_qty / dias_planejados do contrato
            ini_s = str(a.get("inicio_previsto",""))[:10]
            ter_s = str(a.get("termino_previsto",""))[:10]
            if ini_s and ter_s:
                try:
                    dp = max(1, (date.fromisoformat(ter_s) - date.fromisoformat(ini_s)).days)
                    taxa_plan = round(total_qty / dp, 1)
                    vel_txt = f", vel_real=0(sem RDO), taxa_plan={taxa_plan}/dia, saldo={total_qty - exec_qty:.0f}"
                except Exception:
                    vel_txt = f", vel_real=0(sem histórico), saldo={total_qty - exec_qty:.0f}"
            else:
                vel_txt = ""
        else:
            vel_txt = ""
        ini_chat = str(a.get("inicio_previsto",""))[:10]
        futura_txt = " [FUTURA]" if ini_chat > _ref_chat.isoformat() else ""
        ativ_resumo.append(
            f"  {a.get('atividade','?')[:45]}: {a.get('conclusao_pct',0)}%"
            f", ini={ini_chat}, prazo={str(a.get('termino_previsto','?'))[:10]}"
            f", exec={a.get('exec_qty',0)}/{a.get('total_qty',0)} {a.get('unidade','')}"
            f"{vel_txt}{futura_txt}"
        )

    system_ctx = f"""Você é o Agente de IA da obra {contrato} na plataforma Bomtempo.
Responda perguntas do gestor com base nos dados reais abaixo. Seja direto, cite números reais.

ESTADO DA OBRA (data ref: {_ref_chat} | hoje: {today.isoformat()}):
  SPI={kpis['spi']} | Progresso={kpis['progress_pct']}% | Esperado={kpis['prazo_decorrido_pct']}% | Desvio={kpis['desvio_pct']:+.1f}%
  Atrasadas={len(atrasadas)} (prazo vencido na ref + já iniciadas) | Vencendo 7d={len(proximos_7d)}
  {"✅ OBRA ADIANTADA — SPI>1 e desvio positivo" if kpis['spi'] >= 1.0 and kpis['desvio_pct'] >= 0 else "⚠️ OBRA ATRASADA" if kpis['desvio_pct'] < -5 else "🟡 OBRA NO RITMO"}

ATIVIDADES (top 15 por risco | FUTURA = não iniciada ainda):
{chr(10).join(ativ_resumo)}

ANOMALIAS: {'; '.join(a['title'] for a in anomalias) if anomalias else 'Nenhuma'}

RDOs RECENTES: {'; '.join(f"{str(r.get('data',''))[:10]}(equipe={r.get('equipe_alocada','?')}p)" for r in rdos[:3])}

REGRAS DO AGENTE:
- Atividades marcadas como "FUTURA" não têm atraso, risco ou pendência — são futuras por design.
- Se SPI ≥ 1.0 e desvio ≥ 0%: obra saudável. Não afirme atrasos sem evidência.
- Quando perguntarem "adicionar X pessoas": saldo / (velocity_atual × (1 + X/equipe_atual)) = dias_necessários.
- Quando perguntarem "o que antecipar": liste atividades FUTURAS com predecessores concluídos.
- Se vel_real=0 mas taxa_plan existe: use taxa_plan e informe que é estimativa do planejamento.
- Se não houver RDOs: não afirme atrasos. Diga que sem RDOs o progresso não é mensurável.
- Para alocação: se velocity_real < taxa_plan, sugira reforço e calcule o delta necessário."""

    # Gerencia sessão
    if not session_id:
        sess = sb_insert("chat_sessions", {
            "title":     f"Obra {contrato} — {today.isoformat()}",
            "username":  str(user.get("email") or user.get("login") or "gestor"),
            "client_id": client_id,
            "metadata":  {"contrato": contrato},
        })
        session_id = sess["id"] if sess else None

    # Carrega histórico da sessão (últimas 10 trocas)
    historico_chat: list = []
    if session_id:
        msgs = sb_select("chat_messages", filters={"session_id": session_id}, limit=20) or []
        msgs_sorted = sorted(msgs, key=lambda m: str(m.get("created_at") or ""))
        for m in msgs_sorted[-20:]:
            if m.get("role") in ("user", "assistant"):
                historico_chat.append({"role": m["role"], "content": m.get("content", "")})

    # Monta mensagens para o LLM
    messages_llm = [{"role": "system", "content": system_ctx}]
    messages_llm.extend(historico_chat)
    messages_llm.append({"role": "user", "content": mensagem})

    # Persiste mensagem do usuário
    if session_id:
        sb_insert("chat_messages", {
            "session_id": session_id,
            "role":       "user",
            "content":    mensagem,
            "client_id":  client_id,
        })

    try:
        from backend.integrations.ai import query as ai_query
        resposta = ai_query(messages_llm, max_tokens=600, temperature=0.4)
    except Exception as e:
        resposta = f"Erro ao consultar o agente: {e}"

    # Persiste resposta
    if session_id:
        sb_insert("chat_messages", {
            "session_id": session_id,
            "role":       "assistant",
            "content":    resposta,
            "client_id":  client_id,
        })

    return {
        "ok":        True,
        "resposta":  resposta,
        "session_id": session_id,
    }


# ── Aba: Visão Geral ──────────────────────────────────────────────────────────

@router.get("/visao-geral")
async def get_visao_geral(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Pulse cards + KPIs de progresso para o contrato selecionado."""
    loader = DataLoader(client_id=client_id or "")
    data = loader.load_all()

    import pandas as pd

    contratos_df = data.get("contratos", pd.DataFrame())
    projetos_df = data.get("projeto", pd.DataFrame())
    financeiro_df = data.get("financeiro", pd.DataFrame())

    # Contrato info
    contrato_info: Dict[str, Any] = {}
    if not contratos_df.empty and "contrato" in contratos_df.columns:
        rows = contratos_df[contratos_df["contrato"] == contrato]
        if not rows.empty:
            contrato_info = rows.iloc[0].to_dict()
            for k, v in contrato_info.items():
                if hasattr(v, "isoformat"):
                    contrato_info[k] = v.isoformat()
                elif str(v) in ("NaT", "nan", "None"):
                    contrato_info[k] = None

    today = date.today()

    # Dias úteis do contrato para cálculo de progresso correto
    _wd_str = contrato_info.get("dias_uteis_semana", "") if contrato_info else ""
    _wd_set = _parse_dias_uteis(_wd_str) if _wd_str else None

    # Progresso + SPI — usando atividades-folha para evitar dupla contagem
    # ref_date = data do último RDO submetido (regra: só há desvio quando há RDO do dia)
    ativ_para_calc  = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    last_rdo_date   = _get_last_rdo_date(contrato, client_id)
    _hist_vg = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    _hmap_vg = _build_hist_map(_hist_vg)
    kpis = _calc_progress_spi(ativ_para_calc, today, _wd_set, ref_date=last_rdo_date, hist_map=_hmap_vg)
    progress_pct = kpis["progress_pct"]
    prazo_decorrido_pct = kpis["prazo_decorrido_pct"]
    spi = kpis["spi"]

    total_ativ = len(ativ_para_calc)
    ativ_concluidas = sum(1 for a in ativ_para_calc if float(a.get("conclusao_pct") or 0) >= 100)
    criticas_pendentes = sum(
        1 for a in ativ_para_calc
        if (a.get("critico") is True or str(a.get("critico","")).lower() in ("true","sim","1"))
        and float(a.get("conclusao_pct") or 0) < 100
    )

    # Budget
    budget_planejado = 0.0
    budget_realizado = 0.0
    if not financeiro_df.empty and "contrato" in financeiro_df.columns:
        fin_c = financeiro_df[financeiro_df["contrato"] == contrato]
        if "valor_previsto" in fin_c.columns:
            budget_planejado = float(pd.to_numeric(fin_c["valor_previsto"], errors="coerce").fillna(0).sum())
        if "valor_executado" in fin_c.columns:
            budget_realizado = float(pd.to_numeric(fin_c["valor_executado"], errors="coerce").fillna(0).sum())

    # RDOs recentes — busca rdo_master (tabela correta)
    rdo_filters2: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        rdo_filters2["client_id"] = client_id
    rdos = sb_select("rdo_master", filters=rdo_filters2, order="data.desc", limit=7) or []

    # Desvio em % (realizado - planejado) — já calculado em kpis
    desvio_pct = kpis["desvio_pct"]

    # Telemetria: clima e temperatura do RDO mais recente
    # condicao_climatica é o campo real na tabela rdo_master
    temperatura = None
    clima_resumido = None
    if rdos:
        ultimo = rdos[0]
        clima_resumido = ultimo.get("condicao_climatica") or ultimo.get("clima") or None
        temp = ultimo.get("temperatura")
        if temp:
            try:
                temperatura = float(temp)
            except (ValueError, TypeError):
                pass

    # Insights: usa cache persistido (gerado no submit do RDO ou via botão)
    # Fallback: rule-based rápido para primeira carga
    insight_rows = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
    final_insights: list = []
    if insight_rows:
        raw = insight_rows[0].get("insights") or []
        if isinstance(raw, list) and raw:
            final_insights = raw
    if not final_insights:
        final_insights = _rule_based_insights(ativ_para_calc, rdos, today)

    # Nota de risco baseada em SPI e atividades atrasadas
    atrasadas_count = sum(1 for a in ativ_para_calc if a.get("termino_previsto") and str(a["termino_previsto"])[:10] < today.isoformat() and float(a.get("conclusao_pct") or 0) < 100)
    risco_nota = round(min(10, max(0, (1 - kpis["spi"]) * 5 + atrasadas_count * 1.5)), 1)
    if risco_nota >= 7:
        risco_label, risco_color = "CRÍTICO", "#EF4444"
    elif risco_nota >= 4:
        risco_label, risco_color = "MODERADO", "#C98B2A"
    else:
        risco_label, risco_color = "CONTROLADO", "#2A9D8F"

    return {
        "contrato_info": contrato_info,
        "progress_pct": round(progress_pct, 1),
        "spi": spi,
        "prazo_decorrido_pct": round(prazo_decorrido_pct, 1),
        "desvio_pct": desvio_pct,
        "total_atividades": total_ativ,
        "atividades_concluidas": ativ_concluidas,
        "atividades_criticas": criticas_pendentes,
        "budget_planejado": budget_planejado,
        "budget_realizado": budget_realizado,
        "budget_pct": f"{((budget_realizado/budget_planejado)*100) if budget_planejado > 0 else 0:.1f}%",
        "rdos_7d": len(rdos),
        "temperatura": temperatura,
        "clima_resumido": clima_resumido,
        "insights": final_insights,
        "risk": {"nota": str(risco_nota), "label": risco_label, "color": risco_color},
    }


# ── Aba: Cronograma ───────────────────────────────────────────────────────────

_CRONOGRAMA_TTL = 30  # segundos — invalida no submit do RDO


def _cronograma_cache_key(contrato: str) -> str:
    return f"cronograma:{contrato}"


@router.get("/cronograma")
async def get_cronograma(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Atividades hierárquicas (macro → micro → sub) com datas e progresso."""
    from backend.core.redis_cache import cache_get, cache_set

    cache_key = _cronograma_cache_key(contrato)
    cached = cache_get(client_id or "global", cache_key)
    if cached is not None:
        return cached

    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("hub_atividades", filters=filters, limit=1000) or []

    # Historico de produção para velocity e risk score
    hist_rows = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    today_d    = date.today()
    # Referência para atraso: apenas após RDO submetido do dia
    last_rdo_d = _get_last_rdo_date(contrato, client_id)
    ref_d      = last_rdo_d if last_rdo_d is not None else today_d

    # Map to list and apply forecast
    atividades = []
    for r in rows:
        # Apply parity forecast
        f = _compute_forecast(r, today=today_d)

        # Format for display
        f["inicio_br"] = _iso_to_br(str(r.get("inicio_previsto", ""))[:10])
        f["termino_br"] = _iso_to_br(str(r.get("termino_previsto", ""))[:10])
        f["fase_color"] = FASE_COLORS.get(str(r.get("fase", "")).lower().strip(), "#889999")

        # Map status like legacy
        pct = float(r.get("conclusao_pct", 0) or 0)
        ini_s = str(r.get("inicio_previsto", "") or "")[:10]
        ter_s = str(r.get("termino_previsto", "") or "")[:10]
        st = "pendente"
        if pct >= 100: st = "concluida"
        elif ini_s:
            try:
                ini_d = date.fromisoformat(ini_s)
                ter_d = date.fromisoformat(ter_s) if ter_s else None
                if pct > 0:
                    st = "em_execucao"
                    # Atraso: termino < último RDO (não today) — regra do usuário
                    if ter_d and ter_d < ref_d and pct < 100:
                        if ini_d <= ref_d:
                            st = "atrasada"
                elif ini_d <= today_d:
                    st = "em_execucao"
                    if ter_d and ter_d < today_d:
                        st = "atrasada"
            except: pass
        f["status"] = st

        # Risk score e velocity por atividade
        vel = {}
        if float(r.get("total_qty") or 0) > 0:
            vel = _calc_velocity(r, hist_rows)
        f["_risk_score"]    = _calc_risk_score(r, vel, today_d)
        f["_velocity"]      = vel.get("velocity_real", 0)
        f["_eac_date"]      = vel.get("eac_date")
        f["_trend"]         = vel.get("trend", "estavel")
        f["_dias_trabalhados"] = vel.get("dias_trabalhados", 0)

        atividades.append(f)

    # Gantt rows — sort by fase code then start date, always macro before children
    def _fase_sort_key(r: Dict) -> tuple:
        fase = str(r.get("fase") or "").strip()
        nivel = r.get("nivel", "macro")
        # Numeric sort for "1", "1.1", "2.3" style codes
        parts = []
        for seg in fase.split("."):
            try: parts.append(int(seg))
            except: parts.append(0)
        nivel_ord = {"macro": 0, "micro": 1, "sub": 2}.get(str(nivel), 1)
        ini = str(r.get("inicio_previsto") or "")[:10]
        return (parts or [0], nivel_ord, ini)

    sorted_atividades = sorted(atividades, key=_fase_sort_key)

    gantt = []
    for r in sorted_atividades[:120]:
        ini = str(r.get("inicio_previsto") or "")[:10]
        ter = str(r.get("termino_previsto") or "")[:10]
        if not (ini and ter and len(ini) == 10 and len(ter) == 10):
            continue
        eac = str(r.get("_data_fim_prevista") or "")[:10]
        gantt.append({
            "label":          r.get("atividade", "")[:35],
            "start_iso":      ini,
            "end_iso":        ter,
            "forecast_end":   eac if eac and eac != ter else None,
            "pct":            str(int(float(r.get("conclusao_pct") or 0))),
            "critico":        r.get("critico", "Nao"),
            "responsavel":    r.get("responsavel", ""),
            "nivel":          r.get("nivel", "macro"),
            "fase":           r.get("fase", ""),
            "color":          "#EF4444" if (r.get("critico") is True or str(r.get("critico","")).lower() in ("true","sim","1")) else r.get("fase_color", "#C98B2A"),
        })

    # KPIs de progresso — mesma lógica da visão-geral para consistência total
    _hmap_cron = _build_hist_map(hist_rows)
    _wd_cron   = _get_working_days(contrato, client_id)
    kpis_cron  = _calc_progress_spi(rows, today_d, _wd_cron, ref_date=last_rdo_d, hist_map=_hmap_cron)

    result = {
        "atividades": sorted_atividades,
        "gantt": gantt,
        "total": len(atividades),
        "kpis": kpis_cron,
    }
    cache_set(client_id or "global", cache_key, result, ttl=_CRONOGRAMA_TTL)
    return result


@router.patch("/cronograma/{atividade_id}")
async def update_atividade(
    atividade_id: str,
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Atualiza campos de uma atividade (progresso, datas, responsável)."""
    allowed = {
        "conclusao_pct", "inicio_previsto", "termino_previsto",
        "responsavel", "peso_pct", "critico", "observacoes",
        "total_qty", "exec_qty", "unidade", "dias_planejados",
        "status_atividade", "fase_macro", "fase",
        "dep_tipo", "dependencia_id", "atividade", "parent_id",
    }
    data = {k: v for k, v in body.items() if k in allowed}
    if not data:
        return {"ok": False, "error": "Nenhum campo válido para atualizar"}

    _normalize_atividade_payload(data)
    updated = sb_update("hub_atividades", filters={"id": atividade_id}, data=data, client_id=client_id)
    
    updated_dict = updated if isinstance(updated, dict) else {}

    # Logic Parity: If dates changed, trigger propagation
    if updated_dict and body.get("propagar_impacto"):
        old_ter = body.get("old_termino")
        new_ter = updated_dict.get("termino_previsto")
        if old_ter and new_ter and old_ter != new_ter:
            try:
                d_old = date.fromisoformat(old_ter[:10])
                d_new = date.fromisoformat(new_ter[:10])
                diff = _count_working_days(d_old.isoformat(), d_new.isoformat()) - 1
                if diff != 0:
                    _propagate_schedule_changes(atividade_id, diff, updated_dict.get("contrato", ""), client_id or "")
            except (ValueError, TypeError):
                pass

    # Recalc parent bounds
    contrato_upd = updated_dict.get("contrato", body.get("contrato", ""))
    if updated_dict and updated_dict.get("parent_id"):
        _recalc_parent_dates(updated_dict["parent_id"], contrato_upd, client_id or "")

    # Invalidate cronograma cache for this contract
    if contrato_upd:
        from backend.core.redis_cache import cache_invalidate
        cache_invalidate(client_id or "global", _cronograma_cache_key(contrato_upd))

    return {"ok": True, "row": updated_dict}


def _normalize_atividade_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza valores de enum antes de persistir no banco."""
    # Frontend envia 'porcentagem', banco aceita 'percentual'
    if data.get("tipo_medicao") == "porcentagem":
        data["tipo_medicao"] = "percentual"
    # Frontend envia status com espaço, banco usa underscore
    _status_map = {
        "em andamento": "em_execucao",
        "em_andamento": "em_execucao",
        "nao iniciada": "nao_iniciada",
        "pendente":     "nao_iniciada",
    }
    if data.get("status_atividade"):
        data["status_atividade"] = _status_map.get(
            str(data["status_atividade"]).lower(), data["status_atividade"]
        )
    return data


@router.post("/cronograma")
async def create_atividade(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    body["client_id"] = client_id
    _normalize_atividade_payload(body)
    row = sb_insert("hub_atividades", body, client_id=client_id)
    if row and row.get("parent_id"):
        _recalc_parent_dates(row["parent_id"], row.get("contrato", ""), client_id or "")
    if row and row.get("contrato"):
        from backend.core.redis_cache import cache_invalidate
        cache_invalidate(client_id or "global", _cronograma_cache_key(row["contrato"]))
    return {"ok": True, "row": row}


@router.delete("/cronograma/{atividade_id}")
async def delete_atividade(
    atividade_id: str,
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    # Grab contrato before deletion for cache invalidation
    target = sb_select("hub_atividades", filters={"id": atividade_id}, limit=1, client_id=client_id) or []
    contrato_del = target[0].get("contrato", "") if target else ""

    # Cascade: remove filhos antes de remover o pai
    children = sb_select("hub_atividades", filters={"parent_id": atividade_id}, client_id=client_id) or []
    for child in children:
        grandchildren = sb_select("hub_atividades", filters={"parent_id": child["id"]}, client_id=client_id) or []
        for gc in grandchildren:
            sb_delete("hub_atividades", filters={"id": gc["id"]})
        sb_delete("hub_atividades", filters={"id": child["id"]})
    sb_delete("hub_atividades", filters={"id": atividade_id})

    if contrato_del:
        from backend.core.redis_cache import cache_invalidate
        cache_invalidate(client_id or "global", _cronograma_cache_key(contrato_del))

    return {"ok": True}


@router.post("/cronograma/recalcular")
async def recalcular_datas(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Recalcula datas de todas as atividades do contrato com base em dependências."""
    contrato = body.get("contrato", "")
    if not contrato:
        return {"ok": False, "error": "Contrato obrigatório"}

    rows = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=1000) or []

    # Para cada atividade com dependencia_id: ajusta inicio baseado no término da dependência
    updated = 0
    for row in rows:
        dep_id = row.get("dependencia_id")
        dep_tipo = row.get("dep_tipo", "sem_dependencia")
        if not dep_id or dep_tipo == "sem_dependencia":
            continue

        dep = next((r for r in rows if r["id"] == dep_id), None)
        if not dep:
            continue

        if dep_tipo == "depende_termino" and dep.get("termino_previsto") and row.get("inicio_previsto"):
            # início deve ser >= término da dependência (FS — Finish-to-Start)
            dep_ter = dep["termino_previsto"][:10]
            row_ini = row["inicio_previsto"][:10]
            if row_ini < dep_ter:
                dias = int(row.get("dias_planejados") or 0)
                new_ini = dep_ter
                new_ter = _add_working_days(new_ini, dias) if dias > 0 else new_ini
                sb_update("hub_atividades", filters={"id": row["id"]}, data={
                    "inicio_previsto": new_ini,
                    "termino_previsto": new_ter,
                }, client_id=client_id)
                updated += 1

        elif dep_tipo == "depende_inicio" and dep.get("inicio_previsto") and row.get("inicio_previsto"):
            # início deve ser >= início da dependência (SS — Start-to-Start)
            dep_ini = dep["inicio_previsto"][:10]
            row_ini = row["inicio_previsto"][:10]
            if row_ini < dep_ini:
                dias = int(row.get("dias_planejados") or 0)
                new_ini = dep_ini
                new_ter = _add_working_days(new_ini, dias) if dias > 0 else new_ini
                sb_update("hub_atividades", filters={"id": row["id"]}, data={
                    "inicio_previsto": new_ini,
                    "termino_previsto": new_ter,
                }, client_id=client_id)
                updated += 1

    if updated > 0:
        from backend.core.redis_cache import cache_invalidate
        cache_invalidate(client_id or "global", _cronograma_cache_key(contrato))

    return {"ok": True, "recalculadas": updated, "total": len(rows)}


# ── Aba: Auditoria ────────────────────────────────────────────────────────────

@router.get("/auditoria")
async def get_auditoria(
    contrato: str = Query(...),
    categoria: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Bolsões de imagens agrupados por categoria."""
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    if categoria:
        filters["categoria"] = categoria

    imgs = sb_select("hub_auditoria_imgs", filters=filters, limit=200) or []

    # Group by category
    by_cat: Dict[str, List] = {c["slug"]: [] for c in AUDIT_CATEGORIES}
    for img in imgs:
        cat = img.get("categoria", "gerais")
        if cat in by_cat:
            by_cat[cat].append({
                "id":          img.get("id"),
                "url":         img.get("url", ""),
                "legenda":     img.get("legenda", ""),
                "data_captura": img.get("data_captura", ""),
                "autor":       img.get("autor", ""),
            })

    return {
        "categories": AUDIT_CATEGORIES,
        "por_categoria": by_cat,
        "total": len(imgs),
    }


@router.post("/auditoria/upload")
async def upload_auditoria_img(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Registra metadados de imagem já upada para Supabase Storage."""
    body["client_id"] = client_id
    row = sb_insert("hub_auditoria_imgs", body)
    return {"ok": True, "row": row}


@router.delete("/auditoria/{img_id}")
async def delete_auditoria_img(
    img_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    sb_delete("hub_auditoria_imgs", filters={"id": img_id})
    return {"ok": True}


# ── Aba: Timeline ─────────────────────────────────────────────────────────────

@router.get("/timeline")
async def get_timeline(
    contrato: str = Query(...),
    tipo: Optional[str] = Query(None),
    limit: int = Query(50),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Log de eventos/registros + documentos do contrato."""
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    if tipo:
        filters["tipo"] = tipo

    rows = sb_select("hub_timeline", filters=filters, limit=limit) or []

    entries = []
    for r in rows:
        entries.append({
            "id":          r.get("id"),
            "tipo":        r.get("tipo", "Atualização"),
            "titulo":      r.get("titulo", ""),
            "descricao":   r.get("descricao", ""),
            "autor":       r.get("autor", ""),
            "mencoes":     r.get("mencoes", []),
            "is_document": r.get("is_document", False),
            "is_cost":     r.get("is_cost", False),
            "anexo_url":   r.get("anexo_url", ""),
            "anexo_nome":  r.get("anexo_nome", ""),
            "created_at":  r.get("created_at", ""),
            "created_at_br": _utc_to_brt(r.get("created_at", "")),
        })

    return {
        "eventos": entries,
        "entry_types": ENTRY_TYPES,
        "total": len(entries),
    }


@router.post("/timeline")
async def create_timeline_entry(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    body["client_id"] = client_id
    row = sb_insert("hub_timeline", body)
    return {"ok": True, "row": row}


@router.delete("/timeline/{entry_id}")
async def delete_timeline_entry(
    entry_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    sb_delete("hub_timeline", filters={"id": entry_id})
    return {"ok": True}


# ── Aba: Dashboard (Hub KPIs) ─────────────────────────────────────────────────

@router.get("/dashboard")
async def get_hub_dashboard(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Endpoints de Dashboard com S-Curve, SPI, Produtividade e Disciplinas (1:1 Port)."""
    loader = DataLoader(client_id=client_id or "")
    data = loader.load_all()

    import pandas as pd
    import numpy as np

    df_proj = data.get("projeto", pd.DataFrame())
    df_hist = data.get("hub_historico", pd.DataFrame())
    df_contr = data.get("contratos", pd.DataFrame())

    # Carrega financeiro direto do Supabase (bypassa cache DataLoader que pode estar stale)
    from backend.integrations.supabase import sb_select as _sb_select
    _fin_filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        _fin_filters["client_id"] = client_id
    _fin_rows = _sb_select("fin_custos", filters=_fin_filters, limit=2000) or []
    df_fin = pd.DataFrame(_fin_rows) if _fin_rows else pd.DataFrame()

    if df_proj.empty or "contrato" not in df_proj.columns:
        return {"scurve": [], "spi_trend": [], "productivity": [], "disciplinas": [], "kpis": {}}

    df_c = df_proj[df_proj["contrato"] == contrato].copy()
    if df_c.empty:
        return {"scurve": [], "spi_trend": [], "productivity": [], "disciplinas": [], "kpis": {}}

    # 1. S-Curve Calculation (Previsto vs Realizado Acumulado)
    df_c["inicio_previsto"] = pd.to_datetime(df_c["inicio_previsto"], errors="coerce")
    df_c["termino_previsto"] = pd.to_datetime(df_c["termino_previsto"], errors="coerce")
    all_valid = df_c.dropna(subset=["inicio_previsto", "termino_previsto"]).copy()

    if all_valid.empty:
        return {"scurve": [], "spi_trend": [], "productivity": [], "disciplinas": [], "kpis": {}}

    # Mesma lógica de folhas do _calc_progress_spi: exclui macros que têm filhos
    # e atividades sem fase (avulsas sem hierarquia definida) — evita dupla contagem
    ids_com_filhos = set(all_valid["parent_id"].dropna().astype(str))
    valid = all_valid[
        (~all_valid["id"].astype(str).isin(ids_com_filhos)) &
        (all_valid["fase"].notna()) &
        (all_valid["fase"].astype(str).str.strip() != "")
    ].copy()
    if valid.empty:
        valid = all_valid.copy()

    start_date = valid["inicio_previsto"].min()
    end_date = valid["termino_previsto"].max()
    today = pd.Timestamp(date.today())
    plot_end = max(end_date, today + pd.Timedelta(days=1))

    duration = (plot_end - start_date).days
    freq = "D" if duration <= 60 else "W-MON" if duration <= 180 else "MS"
    dates = pd.date_range(start=start_date, end=plot_end, freq=freq)

    scurve = []
    total_peso = valid["peso_pct"].sum() if "peso_pct" in valid.columns else len(valid)
    if total_peso == 0: total_peso = 1

    # History map for Realizado — APENAS entradas com data de RDO não-nula
    # REGRA: realizado só existe quando há RDO submetido para aquele dia.
    # Nunca usa conclusao_pct atual como fallback — isso contaminaria dias sem RDO.
    last_rdo_date_sc: Optional[date] = _get_last_rdo_date(contrato, client_id)
    # Usa sb_select direto (não cache) para garantir dados frescos — igual ao bloco de KPIs.
    _hist_sc_rows = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    hist_map = _build_hist_map(_hist_sc_rows)

    for d in dates:
        d_end = d if freq == "D" else (d + pd.Timedelta(days=6)) if freq == "W-MON" else (d + pd.DateOffset(months=1) - pd.Timedelta(days=1))
        
        prev_acc = 0.0
        real_acc = 0.0
        
        for _, row in valid.iterrows():
            ini, ter = row["inicio_previsto"], row["termino_previsto"]
            peso = (float(row.get("peso_pct", 1)) / total_peso) * 100
            
            # Previsto Linear (Working Days)
            dur_wd = _working_days_between(ini.date(), ter.date() + timedelta(days=1))
            if d_end.date() < ini.date():
                frac = 0.0
            elif d_end.date() >= ter.date():
                frac = 1.0
            else:
                frac = _working_days_between(ini.date(), d_end.date() + timedelta(days=1)) / max(1, dur_wd)
            prev_acc += frac * peso
            
            # Realizado: via hist_map quando populado; fallback para conclusao_pct
            # quando hist_map vazio (histórico ainda não gerado para este contrato).
            # Dias além do last_rdo_date nunca têm realizado — regra do usuário.
            if last_rdo_date_sc is not None and d.date() <= last_rdo_date_sc:
                aid = str(row.get("id", ""))
                val = 0.0
                if hist_map:
                    if aid in hist_map:
                        for dt, pct in hist_map[aid]:
                            # dt é datetime.date (via _build_hist_map), d_end é pd.Timestamp
                            dt_d = dt if isinstance(dt, date) else dt.date()
                            if dt_d <= d_end.date():
                                val = float(pct)
                            else:
                                break
                else:
                    # fallback: sem histórico usa conclusao_pct para qualquer
                    # dia dentro do período com RDO (não limita a today)
                    val = float(row.get("conclusao_pct", 0))
                real_acc += (val / 100.0) * peso

        pt = {"data": d.strftime("%d/%m" if freq != "MS" else "%m/%y"), "previsto": round(prev_acc, 1)}
        if last_rdo_date_sc is not None and d.date() <= last_rdo_date_sc:
            pt["realizado"] = round(real_acc, 1)
        scurve.append(pt)

    # 2. Daily Productivity — produção física real por dia (fonte: hub_atividade_historico)
    #    Usa producao_dia acumulada por dia de RDO. Fallback: efetivo se não houver histórico.
    prod_data = []
    hist_prod = sb_select(
        "hub_atividade_historico",
        filters={"contrato": contrato},
        client_id=client_id or None,
        order="data.asc",
        limit=200,
    ) or []

    if hist_prod:
        from collections import defaultdict
        # Agrupa por data: soma producao_dia de todas as atividades naquele dia
        by_day_hist: Dict[str, float] = defaultdict(float)
        for h in hist_prod:
            d_key = str(h.get("data") or "")[:10]
            if d_key and len(d_key) == 10:
                by_day_hist[d_key] += float(h.get("producao_dia") or 0)

        # Previsto por dia: média da produção planejada das atividades ativas naquele período
        # Simplificado: usamos a meta diária do cronograma (total_qty / dias_planejados)
        ativ_com_qty = [a for a in valid.to_dict("records") if float(a.get("total_qty", 0) or 0) > 0 and int(a.get("dias_planejados", 0) or 0) > 0]

        for d_key in sorted(by_day_hist.keys())[-14:]:
            try:
                d_label = date.fromisoformat(d_key).strftime("%d/%m")
            except Exception:
                d_label = d_key
            # Previsto: soma das metas diárias de atividades ativas nessa data
            previsto_dia = sum(
                float(a.get("total_qty", 0)) / int(a.get("dias_planejados", 1))
                for a in ativ_com_qty
                if str(a.get("inicio_previsto", ""))[:10] <= d_key <= str(a.get("termino_previsto", ""))[:10]
            )
            prod_data.append({
                "data": d_label,
                "realizado": round(by_day_hist[d_key], 1),
                "previsto": round(previsto_dia, 1),
            })
    else:
        # Fallback: S-curve incremental deltas
        for i in range(1, len(scurve)):
            if "realizado" in scurve[i]:
                meta = max(0, scurve[i]["previsto"] - scurve[i-1]["previsto"])
                real = max(0, scurve[i]["realizado"] - scurve[i-1]["realizado"])
                prod_data.append({"data": scurve[i]["data"], "realizado": round(real, 2), "previsto": round(meta, 2)})

    # 3. SPI Trend
    spi_trend = []
    for pt in scurve:
        if "realizado" in pt and pt["previsto"] > 1.0:
            spi_trend.append({"data": pt["data"], "spi": round(pt["realizado"] / pt["previsto"], 2), "baseline": 1.0})

    # 4. Disciplinas Progress (por fase_macro das macros, weighted)
    por_disciplina = []
    fase_col = "fase_macro" if "fase_macro" in df_c.columns else ("fase" if "fase" in df_c.columns else None)
    if fase_col:
        df_c["conclusao_pct"] = pd.to_numeric(df_c["conclusao_pct"], errors="coerce").fillna(0)
        df_c["peso_pct"] = pd.to_numeric(df_c.get("peso_pct", pd.Series(1, index=df_c.index)), errors="coerce").fillna(1)
        # Apenas macros (sem parent_id) para representar disciplinas
        df_macros = df_c[df_c["parent_id"].isna() | (df_c["parent_id"] == "")] if "parent_id" in df_c.columns else df_c
        if df_macros.empty:
            df_macros = df_c
        for fase, grp in df_macros.groupby(fase_col):
            peso_sum = grp["peso_pct"].sum()
            pct_medio = float((grp["conclusao_pct"] * grp["peso_pct"]).sum() / peso_sum) if peso_sum > 0 else float(grp["conclusao_pct"].mean())
            por_disciplina.append({"disciplina": str(fase)[:20], "pct": round(pct_medio, 1)})
        por_disciplina.sort(key=lambda x: x["pct"], reverse=True)

    # 5. Orçamento mensal (financeiro)
    orcamento_mensal = []
    if not df_fin.empty and "contrato" in df_fin.columns:
        df_fin_c = df_fin[df_fin["contrato"] == contrato].copy()
        if not df_fin_c.empty and "data" in df_fin_c.columns:
            df_fin_c["data"] = pd.to_datetime(df_fin_c["data"], errors="coerce")
            df_fin_c["mes"] = df_fin_c["data"].dt.strftime("%m/%y")
            grp_fin = df_fin_c.groupby("mes").agg(
                previsto=("valor_previsto", "sum"),
                realizado=("valor_executado", "sum"),
            ).reset_index()
            orcamento_mensal = grp_fin.to_dict("records")

    # 6. KPIs + Risk Score
    contrato_info_dict = df_contr[df_contr["contrato"] == contrato].iloc[0].to_dict() if not df_contr.empty else {}
    risk = _calculate_risk_score(df_c, df_fin, contrato_info_dict)

    # KPIs canônicos via _calc_progress_spi — mesma fonte que visão-geral e cronograma
    _ativ_dash  = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    _hist_dash  = sb_select("hub_atividade_historico", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    _lrdo_dash  = last_rdo_date_sc  # já calculado acima para a S-curve
    _hmap_dash  = _build_hist_map(_hist_dash)
    _wd_dash    = _get_working_days(contrato, client_id)
    _kpis_calc  = _calc_progress_spi(_ativ_dash, date.today(), _wd_dash, ref_date=_lrdo_dash, hist_map=_hmap_dash)

    return {
        "scurve": scurve,
        "productivity": prod_data,
        "produtividade_diaria": prod_data,
        "spi_trend": spi_trend,
        "disciplinas": disciplinas if "disciplinas" in dir() else [],
        "por_disciplina": por_disciplina,
        "orcamento_mensal": orcamento_mensal,
        "risk": risk,
        "kpis": {
            "progress_global": _kpis_calc["progress_pct"],
            "spi":             _kpis_calc["spi"],
            "desvio_pct":      _kpis_calc["desvio_pct"],
            "prazo_decorrido": _kpis_calc["prazo_decorrido_pct"],
            "total_atividades": len(df_c),
            "concluidas": int((df_c["conclusao_pct"] >= 100).sum()),
        }
    }



# ── Aba: Financeira (do Hub) ──────────────────────────────────────────────────

@router.get("/financeira")
async def get_hub_financeira(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Resumo financeiro do contrato — consulta fin_custos + fin_lancamentos diretamente (sem cache DataLoader)."""
    from backend.integrations.supabase import sb_select
    import re as _re

    def _pf(v) -> float:
        if v is None:
            return 0.0
        s = str(v).strip()
        if not s or s in ("None", "nan", ""):
            return 0.0
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        s = _re.sub(r"[^\d.\-]", "", s)
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id
    custos_rows = sb_select("fin_custos", filters=filters, order="data.asc", limit=2000) or []

    # Lançamentos reais de execução (append-only)
    lanc_filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        lanc_filters["client_id"] = client_id
    lanc_rows = sb_select("fin_lancamentos", filters=lanc_filters, order="data.asc", limit=5000) or []

    budget_planejado = 0.0
    prev_by_date: Dict[str, float] = defaultdict(float)
    exec_by_date: Dict[str, float] = defaultdict(float)

    for r in custos_rows:
        prev = _pf(r.get("valor_previsto", 0))
        budget_planejado += prev
        d = str(r.get("data") or "")[:10]
        if len(d) == 10:
            prev_by_date[d] += prev

    # Execução via lançamentos; fallback para valor_executado se não há lançamentos
    if lanc_rows:
        for lc in lanc_rows:
            d = str(lc.get("data") or "")[:10]
            if len(d) == 10:
                exec_by_date[d] += _pf(lc.get("valor", 0))
    else:
        for r in custos_rows:
            d = str(r.get("data") or "")[:10]
            if len(d) == 10:
                exec_by_date[d] += _pf(r.get("valor_executado", 0))

    budget_realizado = sum(exec_by_date.values())

    # S-curve acumulada dia a dia
    all_dates = sorted(set(list(prev_by_date) + list(exec_by_date)))
    series, acum_prev, acum_exec = [], 0.0, 0.0
    for d in all_dates:
        acum_prev += prev_by_date.get(d, 0.0)
        acum_exec += exec_by_date.get(d, 0.0)
        series.append({
            "data":           d,
            "previsto_acum":  round(acum_prev, 2),
            "executado_acum": round(acum_exec, 2),
        })

    saldo = budget_planejado - budget_realizado
    cpi = round(budget_realizado / budget_planejado, 3) if budget_planejado > 0 else 0.0

    return {
        "budget_planejado": budget_planejado,
        "budget_realizado": budget_realizado,
        "saldo": saldo,
        "cpi": cpi,
        "series": series,
    }


# ── Lista de contratos disponíveis ───────────────────────────────────────────

@router.get("/contratos")
async def list_contratos(
    search: str = Query(""),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Lista pulse cards de contratos para a Visão Geral do Hub."""
    loader = DataLoader(client_id=client_id or "")
    data = loader.load_all()

    import pandas as pd

    contratos_df = data.get("contratos", pd.DataFrame())
    projetos_df = data.get("projeto", pd.DataFrame())

    if contratos_df.empty:
        return {"contratos": []}

    if search:
        mask = (
            contratos_df.get("contrato", pd.Series(dtype=str)).str.contains(search, case=False, na=False)
            | contratos_df.get("projeto", pd.Series(dtype=str)).str.contains(search, case=False, na=False)
            | contratos_df.get("cliente", pd.Series(dtype=str)).str.contains(search, case=False, na=False)
        )
        contratos_df = contratos_df[mask]

    result = []
    for _, row in contratos_df.iterrows():
        cod = str(row.get("contrato", ""))
        # Usa _calc_progress_spi para consistência com visao-geral
        ativ_contrato   = sb_select("hub_atividades", filters={"contrato": cod}, client_id=client_id, limit=500) or []
        _last_rdo_c     = _get_last_rdo_date(cod, client_id)
        _hist_c = sb_select("hub_atividade_historico", filters={"contrato": cod}, client_id=client_id, limit=500) or []
        _hmap_c = _build_hist_map(_hist_c)
        kpis_c = _calc_progress_spi(ativ_contrato, date.today(), _get_working_days(cod, client_id), ref_date=_last_rdo_c, hist_map=_hmap_c)
        prog = kpis_c["progress_pct"]

        item: Dict[str, Any] = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                item[k] = v.isoformat()
            elif str(v) in ("NaT", "nan", "None"):
                item[k] = None
            else:
                item[k] = v
        item["progress"] = round(prog, 1)

        # Campos para card do Projetos: termino, saude, desvio_pct, localizacao
        # data_termino é o campo real na tabela contratos
        termino = item.get("data_termino") or item.get("termino") or None
        item["termino"] = termino

        # Localização: campo localizacao na tabela
        if not item.get("localizacao"):
            item["localizacao"] = None

        # Aliases lat/lng → latitude/longitude para o frontend (Windy e mapa)
        # A tabela contratos usa lat/lng; o frontend espera latitude/longitude
        if item.get("lat") and not item.get("latitude"):
            item["latitude"] = float(item["lat"])
        if item.get("lng") and not item.get("longitude"):
            item["longitude"] = float(item["lng"])

        # Saúde calculada: desvio já vem do _calc_progress_spi (mesma lógica em todas as páginas)
        desvio_pct_v = kpis_c["desvio_pct"]

        item["desvio_pct"] = desvio_pct_v
        if desvio_pct_v >= -5:
            item["saude"] = "OK"
            item["saude_color"] = "#2A9D8F"
        elif desvio_pct_v >= -15:
            item["saude"] = "ATENÇÃO"
            item["saude_color"] = "#C98B2A"
        else:
            item["saude"] = "CRÍTICO"
            item["saude_color"] = "#EF4444"

        result.append(item)

    return {"contratos": result}


# ── Gerenciamento de Projetos (CRUD) ──────────────────────────────────────────

async def _get_coords(address: str) -> tuple:
    """Helper: busca lat/long no Nominatim."""
    if not address:
        return 0, 0
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers={"User-Agent": "Bomtempo-Platform/1.0"})
            if r.status_code == 200:
                data = r.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return 0, 0


@router.post("/contratos")
async def create_contrato(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Cria um novo projeto/contrato no sistema com geocoding automático."""
    body["client_id"] = client_id
    if not body.get("contrato"):
        return {"ok": False, "error": "Código do contrato é obrigatório"}

    # Normaliza aliases de datas (frontend pode enviar inicio/termino ou data_inicio/data_termino)
    if body.get("inicio") and not body.get("data_inicio"):
        body["data_inicio"] = body.pop("inicio")
    if body.get("termino") and not body.get("data_termino"):
        body["data_termino"] = body.pop("termino")
    # Alias potencia
    if body.get("potencia_kwp_contratada") and not body.get("potencia_kwp"):
        body["potencia_kwp"] = body.get("potencia_kwp_contratada")

    # Geocoding automático se lat/long forem 0
    if not body.get("latitude") and not body.get("longitude") and body.get("localizacao"):
        lat, lon = await _get_coords(body["localizacao"])
        body["latitude"] = lat
        body["longitude"] = lon

    # Normaliza latitude/longitude → lat/lng (nome real na tabela contratos)
    if "latitude" in body:
        body["lat"] = body.pop("latitude")
    if "longitude" in body:
        body["lng"] = body.pop("longitude")

    # Campos permitidos na tabela contratos
    ALLOWED_CREATE = {
        "contrato", "projeto", "cliente", "gestor", "localizacao", "valor_contratado",
        "data_inicio", "data_termino", "status", "lat", "lng",
        "potencia_kwp", "prioridade", "terceirizado", "dias_uteis_semana", "obs", "client_id",
    }
    body = {k: v for k, v in body.items() if k in ALLOWED_CREATE}

    row = sb_insert("contratos", body)
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True, "row": row}


@router.patch("/contratos/{contrato_code}")
async def update_contrato(
    contrato_code: str,
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Atualiza metadados de um projeto existente."""
    filters = {"contrato": contrato_code}
    if client_id:
        filters["client_id"] = client_id

    # Normaliza aliases de datas
    if body.get("inicio") and not body.get("data_inicio"):
        body["data_inicio"] = body["inicio"]
    if body.get("termino") and not body.get("data_termino"):
        body["data_termino"] = body["termino"]
    if body.get("potencia_kwp_contratada") and not body.get("potencia_kwp"):
        body["potencia_kwp"] = body["potencia_kwp_contratada"]

    # Se mudar localização e não tiver lat/long, re-geocodificar
    if body.get("localizacao") and not body.get("lat") and not body.get("latitude"):
        lat, lon = await _get_coords(body["localizacao"])
        body["lat"] = lat
        body["lng"] = lon

    # Normaliza latitude/longitude → lat/lng (nome real na tabela contratos)
    if "latitude" in body:
        body["lat"] = body.pop("latitude")
    if "longitude" in body:
        body["lng"] = body.pop("longitude")

    # Campos permitidos na tabela contratos (evita erro de coluna desconhecida)
    ALLOWED = {
        "projeto", "cliente", "gestor", "localizacao", "valor_contratado",
        "data_inicio", "data_termino", "status", "lat", "lng",
        "potencia_kwp", "prioridade", "terceirizado", "dias_uteis_semana", "obs",
    }
    data = {k: v for k, v in body.items() if k in ALLOWED}

    import logging as _log
    _log.getLogger("hub").info(
        f"update_contrato | code={contrato_code!r} | fields={list(data.keys())} | client_id={client_id!r}"
    )

    if not data:
        _log.getLogger("hub").warning(f"update_contrato | code={contrato_code!r} | nenhum campo valido enviado")
        return {"ok": True, "note": "no updatable fields"}

    # Usa HTTP direto com Prefer=return=minimal para evitar comportamento inconsistente
    # do PostgREST com return=representation quando 0 rows são afetadas.
    from backend.integrations.supabase import SUPABASE_URL, SUPABASE_KEY, _WRITE_TIMEOUT, _request_with_retry
    REST_BASE_LOCAL = f"{SUPABASE_URL}/rest/v1"
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",  # retorna 204 sempre, sem body
    }
    params = {"contrato": f"eq.{contrato_code}"}
    try:
        resp = _request_with_retry(
            "patch", f"{REST_BASE_LOCAL}/contratos",
            headers=h, params=params, json=data, timeout=_WRITE_TIMEOUT,
        )
        _log.getLogger("hub").info(
            f"update_contrato | code={contrato_code!r} | supabase_status={resp.status_code} | body={resp.text[:200]!r}"
        )
        if resp.status_code not in (200, 204):
            return {"ok": False, "error": f"Supabase {resp.status_code}: {resp.text[:300]}"}
    except Exception as exc:
        _log.getLogger("hub").error(f"update_contrato | code={contrato_code!r} | exception={exc}")
        return {"ok": False, "error": str(exc)}

    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True}


@router.delete("/contratos/{contrato_code}")
async def delete_contrato(
    contrato_code: str,
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Remove um projeto e limpa todas as atividades vinculadas em cascata."""
    filters = {"contrato": contrato_code}
    if client_id:
        filters["client_id"] = client_id
    
    # Excluir dependências
    sb_delete("hub_atividades", filters=filters)
    sb_delete("hub_auditoria_imgs", filters=filters)
    sb_delete("hub_timeline", filters=filters)
    sb_delete("contratos", filters=filters)
    
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True}


@router.post("/contratos/{contrato_code}/duplicate")
async def duplicate_contrato(
    contrato_code: str,
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Faz um 'Deep Clone' do projeto: duplica o contrato e todas as atividades."""
    filters = {"contrato": contrato_code}
    if client_id:
        filters["client_id"] = client_id
    
    # 1. Carrega o original
    orig_list = sb_select("contratos", filters=filters, limit=1)
    if not orig_list:
        return {"ok": False, "error": "Projeto original não encontrado"}
    
    orig = orig_list[0]
    new_code = f"{contrato_code}-CLONE-{datetime.now().strftime('%H%M%S')}"
    
    # 2. Insere novo contrato
    new_con = orig.copy()
    new_con.pop("id", None)
    new_con["contrato"] = new_code
    new_con["projeto"] = f"[CLONE] {orig.get('projeto', '')}"
    new_con["created_at"] = datetime.now(timezone.utc).isoformat()
    
    sb_insert("contratos", new_con)
    
    # 3. Duplica atividades mantendo hierarquia (UUID mapping)
    atividades = sb_select("hub_atividades", filters=filters, limit=1000)
    id_map = {}
    
    # First pass: clone objects and store ID mapping
    for ativ in atividades:
        old_id = ativ.get("id")
        new_ativ = ativ.copy()
        new_ativ.pop("id", None)
        new_ativ["contrato"] = new_code
        new_ativ["client_id"] = client_id
        
        inserted = sb_insert("hub_atividades", new_ativ, client_id=client_id)
        if inserted:
            id_map[old_id] = inserted.get("id")

    # Second pass: update parent_id references in new activities
    new_ativs = sb_select("hub_atividades", filters={"contrato": new_code}, limit=1000)
    for na in new_ativs:
        old_parent_id = na.get("parent_id")
        if old_parent_id in id_map:
            sb_update("hub_atividades", filters={"id": na["id"]}, data={"parent_id": id_map[old_parent_id]}, client_id=client_id)

    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True, "new_code": new_code}
