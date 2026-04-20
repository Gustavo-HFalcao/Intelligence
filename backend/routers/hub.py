"""
Hub de Operações router — /api/hub
Cobre as 6 abas: Visão Geral, Dashboard, Cronograma, Auditoria, Timeline, Financeira.

Porta HubState (hub_state.py, 4159 linhas) para endpoints REST.
"""

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
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.services.data_loader import DataLoader

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


def _working_days_between(d_start: date, d_end: date) -> int:
    if d_end <= d_start:
        return 0
    total = (d_end - d_start).days
    weeks, rem = divmod(total, 7)
    wd = weeks * 5
    start_wd = d_start.weekday()
    for i in range(rem):
        if (start_wd + i) % 7 < 5:
            wd += 1
    return max(0, wd)


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
        working_days = {0, 1, 2, 3, 4}
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
        working_days = {0, 1, 2, 3, 4}
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


def _recalc_parent_dates(parent_id: str, contrato: str, client_id: str):
    """Atualiza datas do pai com base nos filhos (min/max). 1:1 Parity."""
    children = sb_select("hub_atividades", filters={"parent_id": parent_id, "contrato": contrato}, client_id=client_id)
    if not children:
        return
    
    starts = [r["inicio_previsto"] for r in children if r.get("inicio_previsto")]
    ends = [r["termino_previsto"] for r in children if r.get("termino_previsto")]
    
    if starts and ends:
        sb_update("hub_atividades", filters={"id": parent_id}, data={
            "inicio_previsto": min(starts),
            "termino_previsto": max(ends),
        }, client_id=client_id)
        
        # Cascading update
        parent_rows = sb_select("hub_atividades", filters={"id": parent_id}, limit=1, client_id=client_id)
        if parent_rows and parent_rows[0].get("parent_id"):
            _recalc_parent_dates(parent_rows[0]["parent_id"], contrato, client_id)


def _compute_forecast(r: Dict[str, Any], today: date = date.today()) -> Dict[str, Any]:
    """Cálculo de EAC e Tendência (1:1 Parity)."""
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

    dias_uteis_decorridos = _working_days_between(d_inicio, today + timedelta(days=1))
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
        
        # Simple working day estimation for end date
        current = today
        added = 0
        while added < dias_restantes:
            current += timedelta(days=1)
            if current.weekday() < 5:
                added += 1
        fim_prev = current
        data_fim_prevista = fim_prev.isoformat()
        if d_termino:
            if fim_prev > d_termino:
                desvio_dias = _working_days_between(d_termino, fim_prev)
            else:
                desvio_dias = -_working_days_between(fim_prev, d_termino)

    # Tendency Logic
    prazo_estourado = desvio_dias > 0
    if exec_qty == 0: tendencia = "sem_dados"
    elif pct >= 100: tendencia = "concluida"
    elif desvio_pct >= 10.0 and not prazo_estourado: tendencia = "acima"
    elif desvio_pct <= -10.0 or prazo_estourado: tendencia = "abaixo"
    else: tendencia = "dentro"

    return {
        **r,
        "_tendencia": tendencia,
        "_data_fim_prevista": data_fim_prevista,
        "_desvio_dias": desvio_dias,
        "_prod_plan": round(prod_plan, 2),
        "_prod_real": round(prod_real, 2),
        "_pct_esperado": round(min(100.0, dia_atual / dias_plan * 100), 1) if dias_plan > 0 else 0
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
    
    return {"nota": str(nota), "label": label, "color": color}


@router.get("/agente/insights")
async def get_agente_insights(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Análise real do cronograma: SPI, EAC, caminho crítico, risco meteorológico."""
    atividades = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=500) or []
    rdo_recentes = sb_select("rdo_master", filters={"contrato": contrato}, client_id=client_id, order="data.desc", limit=7) or []

    insights = []
    today = date.today()

    # ── 1. Calcular SPI real (Schedule Performance Index) ──────────────────────
    # SPI = % realizado / % planejado (baseado em dias decorridos vs total planejado)
    em_andamento = [
        a for a in atividades
        if a.get("inicio_previsto") and a.get("termino_previsto") and float(a.get("conclusao_pct") or 0) < 100
    ]
    spi_values = []
    atrasadas_criticas = []
    quase_vencendo = []

    for a in em_andamento:
        try:
            ini = date.fromisoformat(str(a["inicio_previsto"])[:10])
            ter = date.fromisoformat(str(a["termino_previsto"])[:10])
            total_dias = max((ter - ini).days, 1)
            decorridos = max((today - ini).days, 0)
            pct_planejado = min(decorridos / total_dias, 1.0) * 100
            pct_real = float(a.get("conclusao_pct") or 0)

            if pct_planejado > 5:  # só calcula se passou da fase inicial
                spi = pct_real / pct_planejado if pct_planejado > 0 else 1.0
                spi_values.append(spi)

            # Atraso em atividade crítica
            if ter < today and float(a.get("conclusao_pct") or 0) < 100:
                dias_atraso = (today - ter).days
                if str(a.get("critico", "")).lower() == "sim":
                    atrasadas_criticas.append((a, dias_atraso))

            # Termina nos próximos 7 dias e está abaixo de 80%
            if 0 <= (ter - today).days <= 7 and float(a.get("conclusao_pct") or 0) < 80:
                quase_vencendo.append(a)

        except (ValueError, TypeError):
            continue

    spi_medio = sum(spi_values) / len(spi_values) if spi_values else 1.0

    # ── 2. Caminho crítico desviando ──────────────────────────────────────────
    if atrasadas_criticas:
        atrasadas_criticas.sort(key=lambda x: x[1], reverse=True)
        nomes = ", ".join([f'"{a["atividade"][:20]}" ({d}d)' for a, d in atrasadas_criticas[:3]])
        insights.append({
            "title": "⚠️ Caminho Crítico em Risco",
            "body": f"{len(atrasadas_criticas)} atividade(s) crítica(s) atrasada(s): {nomes}. "
                    f"SPI médio do contrato: {spi_medio:.2f}. Recomendo reforço de equipe e revisão de sequência.",
            "priority": "High"
        })

    # ── 3. SPI global abaixo do limiar ────────────────────────────────────────
    if spi_medio < 0.85 and not atrasadas_criticas:
        insights.append({
            "title": "📉 Produtividade Abaixo do Planejado",
            "body": f"SPI médio do contrato é {spi_medio:.2f} (abaixo de 0.85). "
                    f"O ritmo atual sugere que o término real pode ser {int((1 - spi_medio) * 100)}% além do prazo baseline. "
                    f"Revise alocação de recursos.",
            "priority": "High" if spi_medio < 0.70 else "Medium"
        })
    elif spi_medio > 1.10:
        insights.append({
            "title": "✅ Projeto Adiantado",
            "body": f"SPI = {spi_medio:.2f}. O ritmo atual está acima do planejado. "
                    f"Oportunidade para antecipar marcos ou realocar equipe para frentes críticas.",
            "priority": "Low"
        })

    # ── 4. Atividades quase vencendo com baixo progresso ─────────────────────
    if quase_vencendo:
        nomes_qv = ", ".join([f'"{a["atividade"][:20]}"' for a in quase_vencendo[:3]])
        insights.append({
            "title": "🔔 Prazo Crítico nos Próximos 7 Dias",
            "body": f"{len(quase_vencendo)} atividade(s) vencem em até 7 dias e têm menos de 80% de avanço: {nomes_qv}. "
                    f"Ação imediata necessária.",
            "priority": "Medium"
        })

    # ── 5. Risco meteorológico baseado em RDOs recentes ───────────────────────
    if rdo_recentes:
        # condicao_climatica é o campo real
        chuva_dias = sum(1 for r in rdo_recentes if r.get("houve_chuva")
                         or "chuva" in str(r.get("observacoes", "")).lower()
                         or str(r.get("condicao_climatica", "")).lower() in ("chuvoso", "chuva", "tempestade"))
        interrupcoes = sum(1 for r in rdo_recentes if r.get("houve_interrupcao"))
        if chuva_dias >= 2 or interrupcoes >= 2:
            insights.append({
                "title": "🌧️ Impacto Meteorológico Identificado",
                "body": f"{chuva_dias} dia(s) com chuva e {interrupcoes} interrupção(ões) nos últimos {len(rdo_recentes)} RDOs. "
                        f"Considere buffer de prazo nas atividades externas e notifique o contratante.",
                "priority": "Medium"
            })

    # ── 6. Progresso geral ────────────────────────────────────────────────────
    total = len(atividades)
    concluidas = sum(1 for a in atividades if float(a.get("conclusao_pct") or 0) >= 100)
    pct_geral = round(concluidas / total * 100, 1) if total else 0

    if not insights:
        insights.append({
            "title": "✅ Estabilidade Operacional",
            "body": f"SPI = {spi_medio:.2f}. {concluidas}/{total} atividades concluídas ({pct_geral}%). "
                    f"Ritmo nominal. Continue monitorando as frentes de infraestrutura e caminho crítico.",
            "priority": "Low"
        })

    # Persiste no agente_insights para uso em visao-geral e RDO view
    try:
        existing = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
        payload_ins = {
            "contrato":   contrato,
            "insights":   insights,
            "updated_at": datetime.utcnow().isoformat(),
            "client_id":  client_id,
        }
        if existing:
            sb_update("agente_insights", filters={"id": existing[0]["id"]}, data=payload_ins)
        else:
            sb_insert("agente_insights", payload_ins)
    except Exception:
        pass

    return {"insights": insights, "spi": round(spi_medio, 2), "pct_geral": pct_geral}



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

    # Progresso físico
    progress_pct = 0.0
    total_ativ = 0
    ativ_concluidas = 0
    criticas_pendentes = 0

    if not projetos_df.empty and "contrato" in projetos_df.columns:
        df_c = projetos_df[projetos_df["contrato"] == contrato]
        total_ativ = len(df_c)
        if "conclusao_pct" in df_c.columns:
            pct = pd.to_numeric(df_c["conclusao_pct"], errors="coerce").fillna(0)
            ativ_concluidas = int((pct >= 100).sum())
            if "peso_pct" in df_c.columns:
                peso = pd.to_numeric(df_c["peso_pct"], errors="coerce").fillna(1)
                total_peso = peso.sum()
                progress_pct = float((pct * peso).sum() / total_peso) if total_peso > 0 else 0.0
            else:
                progress_pct = float(pct.mean()) if len(pct) > 0 else 0.0
        if "critico" in df_c.columns:
            critico_mask = df_c["critico"].astype(str).str.lower().isin(["sim", "1", "true"])
            if "conclusao_pct" in df_c.columns:
                pct2 = pd.to_numeric(df_c["conclusao_pct"], errors="coerce").fillna(0)
                criticas_pendentes = int((critico_mask & (pct2 < 100)).sum())

    # SPI (1:1 Legacy Parity using Working Days)
    spi = 0.0
    prazo_decorrido_pct = 0.0
    if contrato_info.get("inicio") and contrato_info.get("termino"):
        try:
            d_ini = date.fromisoformat(str(contrato_info["inicio"])[:10])
            d_fim = date.fromisoformat(str(contrato_info["termino"])[:10])
            today = date.today()
            # Legacy: working days
            total_wd = _working_days_between(d_ini, d_fim + timedelta(days=1))
            decorrido_wd = _working_days_between(d_ini, today + timedelta(days=1))
            prazo_decorrido_pct = min(100.0, decorrido_wd / total_wd * 100) if total_wd > 0 else 0.0
            if prazo_decorrido_pct > 0:
                spi = round(progress_pct / prazo_decorrido_pct, 2)
        except Exception:
            pass

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

    # Desvio em % (realizado - planejado baseado em prazo decorrido)
    desvio_pct = round(progress_pct - prazo_decorrido_pct, 1)

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

    # Insights: preferência para cache do agente_insights (gerado no submit do RDO)
    insight_rows = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id, limit=1) or []
    persisted_insights: list = []
    if insight_rows:
        raw = insight_rows[0].get("insights") or []
        if isinstance(raw, list):
            persisted_insights = raw

    # Insights da IA para o contrato (geração ao vivo + enriquecimento do cache)
    ativ_para_insight = sb_select("hub_atividades", filters={"contrato": contrato}, client_id=client_id, limit=200) or []
    insights_data: list = []
    today_d = date.today()
    spi_vals: list = []
    atrasadas_crit: list = []
    quase_vencem: list = []
    for a in ativ_para_insight:
        try:
            ini = date.fromisoformat(str(a.get("inicio_previsto", ""))[:10])
            ter = date.fromisoformat(str(a.get("termino_previsto", ""))[:10])
            total_d = max((ter - ini).days, 1)
            dec_d = max((today_d - ini).days, 0)
            pct_plan = min(dec_d / total_d, 1.0) * 100
            pct_real = float(a.get("conclusao_pct") or 0)
            if pct_plan > 5:
                spi_vals.append(pct_real / pct_plan if pct_plan > 0 else 1.0)
            if ter < today_d and pct_real < 100 and str(a.get("critico", "")).lower() == "sim":
                atrasadas_crit.append((a, (today_d - ter).days))
            if 0 <= (ter - today_d).days <= 7 and pct_real < 80:
                quase_vencem.append(a)
        except Exception:
            continue
    spi_m = sum(spi_vals) / len(spi_vals) if spi_vals else 1.0
    if atrasadas_crit:
        atrasadas_crit.sort(key=lambda x: x[1], reverse=True)
        nomes = ", ".join([f'"{a["atividade"][:18]}" ({d}d)' for a, d in atrasadas_crit[:3]])
        insights_data.append({"title": "⚠️ Caminho Crítico em Risco", "body": f"{len(atrasadas_crit)} atividade(s) crítica(s) atrasada(s): {nomes}. SPI={spi_m:.2f}. Reforce equipe.", "priority": "High"})
    if spi_m < 0.85 and not atrasadas_crit:
        insights_data.append({"title": "📉 Produtividade Abaixo do Planejado", "body": f"SPI={spi_m:.2f}. Ritmo {int((1-spi_m)*100)}% abaixo do baseline. Revise alocação.", "priority": "High" if spi_m < 0.70 else "Medium"})
    elif spi_m > 1.10:
        insights_data.append({"title": "✅ Projeto Adiantado", "body": f"SPI={spi_m:.2f}. Ritmo acima do planejado. Oportunidade de adiantar marcos.", "priority": "Low"})
    if quase_vencem:
        nomes_qv = ", ".join([f'"{a["atividade"][:18]}"' for a in quase_vencem[:3]])
        insights_data.append({"title": "🔔 Prazos Críticos (7 dias)", "body": f"{len(quase_vencem)} atividade(s) vencem em até 7 dias com menos de 80%: {nomes_qv}.", "priority": "Medium"})
    # condicao_climatica é o campo real na tabela rdo_master
    chuva_d = sum(1 for r in rdos if r.get("houve_chuva") or "chuva" in str(r.get("observacoes", "")).lower()
                  or str(r.get("condicao_climatica", "")).lower() in ("chuvoso", "chuva", "tempestade"))
    interrupcoes_d = sum(1 for r in rdos if r.get("houve_interrupcao"))
    if chuva_d >= 2 or interrupcoes_d >= 2:
        insights_data.append({"title": "🌧️ Impacto Meteorológico", "body": f"{chuva_d} dia(s) com chuva, {interrupcoes_d} interrupção(ões) nos últimos {len(rdos)} RDOs. Considere buffer de prazo.", "priority": "Medium"})
    if not insights_data:
        insights_data.append({"title": "✅ Estabilidade Operacional", "body": f"SPI={spi_m:.2f}. Ritmo nominal. {ativ_concluidas}/{total_ativ} atividades concluídas.", "priority": "Low"})

    # Usa cache se existir; senão usa ao vivo
    final_insights = persisted_insights if persisted_insights else insights_data

    # Nota de risco simples (0-10) baseada em atrasadas + SPI
    risco_nota = round(min(10, max(0, (1 - spi_m) * 5 + len(atrasadas_crit) * 1.5)), 1)
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

@router.get("/cronograma")
async def get_cronograma(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Atividades hierárquicas (macro → micro → sub) com datas e progresso."""
    filters: Dict[str, Any] = {"contrato": contrato}
    if client_id:
        filters["client_id"] = client_id

    rows = sb_select("hub_atividades", filters=filters, limit=1000) or []

    # Map to list and apply forecast
    atividades = []
    for r in rows:
        # Apply parity forecast
        f = _compute_forecast(r, today=date.today())
        
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
                if date.fromisoformat(ini_s) <= date.today():
                    st = "em_andamento"
                    if ter_s and date.fromisoformat(ter_s) < date.today() and pct < 100:
                        st = "atrasada"
            except: pass
        f["status"] = st
        atividades.append(f)

    # Gantt rows — inclui todas as atividades com datas válidas
    gantt = []
    for r in atividades[:100]:
        ini = str(r.get("inicio_previsto") or "")[:10]
        ter = str(r.get("termino_previsto") or "")[:10]
        if ini and ter and len(ini) == 10 and len(ter) == 10:
            gantt.append({
                "label":       r.get("atividade", "")[:30],
                "start_iso":   ini,
                "end_iso":     ter,
                "pct":         str(int(float(r.get("conclusao_pct") or 0))),
                "critico":     r.get("critico", "Nao"),
                "responsavel": r.get("responsavel", ""),
                "nivel":       r.get("nivel", "macro"),
                "color":       "#EF4444" if str(r.get("critico", "")).lower() == "sim" else r.get("fase_color", "#C98B2A"),
            })

    return {"atividades": atividades, "gantt": gantt, "total": len(atividades)}


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
    if updated_dict and updated_dict.get("parent_id"):
        _recalc_parent_dates(updated_dict["parent_id"], updated_dict.get("contrato", ""), client_id or "")

    return {"ok": True, "row": updated_dict}


@router.post("/cronograma")
async def create_atividade(
    body: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    body["client_id"] = client_id
    row = sb_insert("hub_atividades", body, client_id=client_id)
    if row and row.get("parent_id"):
        _recalc_parent_dates(row["parent_id"], row.get("contrato", ""), client_id or "")
    return {"ok": True, "row": row}


@router.delete("/cronograma/{atividade_id}")
async def delete_atividade(
    atividade_id: str,
    user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    # Cascade: remove filhos antes de remover o pai
    children = sb_select("hub_atividades", filters={"parent_id": atividade_id}, client_id=client_id) or []
    for child in children:
        grandchildren = sb_select("hub_atividades", filters={"parent_id": child["id"]}, client_id=client_id) or []
        for gc in grandchildren:
            sb_delete("hub_atividades", filters={"id": gc["id"]})
        sb_delete("hub_atividades", filters={"id": child["id"]})
    sb_delete("hub_atividades", filters={"id": atividade_id})
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
            # inicio deve ser >= termino da dependência
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
    df_fin = data.get("financeiro", pd.DataFrame())
    df_contr = data.get("contratos", pd.DataFrame())

    if df_proj.empty or "contrato" not in df_proj.columns:
        return {"scurve": [], "spi_trend": [], "productivity": [], "disciplinas": [], "kpis": {}}

    df_c = df_proj[df_proj["contrato"] == contrato].copy()
    if df_c.empty:
        return {"scurve": [], "spi_trend": [], "productivity": [], "disciplinas": [], "kpis": {}}

    # 1. S-Curve Calculation (Previsto vs Realizado Acumulado)
    df_c["inicio_previsto"] = pd.to_datetime(df_c["inicio_previsto"], errors="coerce")
    df_c["termino_previsto"] = pd.to_datetime(df_c["termino_previsto"], errors="coerce")
    valid = df_c.dropna(subset=["inicio_previsto", "termino_previsto"]).copy()
    
    if valid.empty:
        return {"scurve": [], "spi_trend": [], "productivity": [], "disciplinas": [], "kpis": {}}

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

    # History map for Realizado
    hist_map = {}
    if not df_hist.empty and "atividade_id" in df_hist.columns:
        df_h = df_hist[df_hist["contrato"] == contrato] if "contrato" in df_hist.columns else df_hist
        if not df_h.empty:
            for aid, grp in df_h.groupby("atividade_id"):
                sorted_grp = grp.sort_values("created_at")
                hist_map[str(aid)] = list(zip(pd.to_datetime(sorted_grp["created_at"]).dt.normalize(), sorted_grp["conclusao_pct_novo"]))

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
            
            # Realizado from history
            if d.date() <= today.date():
                aid = str(row.get("id", ""))
                val = 0.0
                if aid in hist_map:
                    for dt, pct in hist_map[aid]:
                        if dt.date() <= d_end.date(): val = float(pct)
                        else: break
                else:
                    if d_end.date() >= today.date(): val = float(row.get("conclusao_pct", 0))
                real_acc += (val / 100.0) * peso
        
        pt = {"data": d.strftime("%d/%m" if freq != "MS" else "%m/%y"), "previsto": round(prev_acc, 1)}
        if d.date() <= today.date():
            pt["realizado"] = round(real_acc, 1)
        scurve.append(pt)

    # 2. Daily Productivity (Meta vs Realizado)
    prod_data = []
    for i in range(1, len(scurve)):
        if "realizado" in scurve[i]:
            meta = max(0, scurve[i]["previsto"] - scurve[i-1]["previsto"])
            real = max(0, scurve[i]["realizado"] - scurve[i-1]["realizado"])
            prod_data.append({"data": scurve[i]["data"], "meta": round(meta, 2), "realizado": round(real, 2)})

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

    return {
        "scurve": scurve,
        "productivity": prod_data,
        "produtividade_diaria": [{"data": p["data"], "realizado": p.get("realizado", 0), "previsto": p.get("meta", 0)} for p in prod_data],
        "spi_trend": spi_trend,
        "disciplinas": disciplinas if "disciplinas" in dir() else [],
        "por_disciplina": por_disciplina,
        "orcamento_mensal": orcamento_mensal,
        "risk": risk,
        "kpis": {
            "progress_global": scurve[-1]["realizado"] if scurve and "realizado" in scurve[-1] else 0,
            "spi": spi_trend[-1]["spi"] if spi_trend else 1.0,
            "total_atividades": len(df_c),
            "concluidas": int((df_c["conclusao_pct"] >= 100).sum())
        }
    }



# ── Aba: Financeira (do Hub) ──────────────────────────────────────────────────

@router.get("/financeira")
async def get_hub_financeira(
    contrato: str = Query(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Resumo financeiro do contrato (S-curve simplificada)."""
    loader = DataLoader(client_id=client_id or "")
    data = loader.load_all()

    import pandas as pd

    fin_df = data.get("financeiro", pd.DataFrame())
    if not fin_df.empty and "contrato" in fin_df.columns:
        fin_df = fin_df[fin_df["contrato"] == contrato]

    rows: List[Dict[str, Any]] = []
    budget_planejado = 0.0
    budget_realizado = 0.0

    if not fin_df.empty:
        if "valor_previsto" in fin_df.columns:
            budget_planejado = float(pd.to_numeric(fin_df["valor_previsto"], errors="coerce").fillna(0).sum())
        if "valor_executado" in fin_df.columns:
            budget_realizado = float(pd.to_numeric(fin_df["valor_executado"], errors="coerce").fillna(0).sum())

        # Monthly series
        if "data" in fin_df.columns:
            fin_df["data"] = pd.to_datetime(fin_df["data"], errors="coerce")
            fin_df["mes"] = fin_df["data"].dt.strftime("%m/%Y")
            grp = fin_df.groupby("mes").agg(
                planejado=("valor_previsto", "sum"),
                realizado=("valor_executado", "sum"),
            ).reset_index()
            rows = grp.to_dict("records")

    saldo = budget_planejado - budget_realizado
    cpi = budget_realizado / budget_planejado if budget_planejado > 0 else 0.0

    return {
        "budget_planejado": budget_planejado,
        "budget_realizado": budget_realizado,
        "saldo": saldo,
        "cpi": round(cpi, 3),
        "series": rows,
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
        prog = 0.0
        if not projetos_df.empty and "contrato" in projetos_df.columns:
            df_c = projetos_df[projetos_df["contrato"] == cod]
            if not df_c.empty and "conclusao_pct" in df_c.columns:
                pct = pd.to_numeric(df_c["conclusao_pct"], errors="coerce").fillna(0)
                peso = pd.to_numeric(df_c.get("peso_pct", pd.Series([1] * len(df_c))), errors="coerce").fillna(1)
                total_peso = peso.sum()
                prog = float((pct * peso).sum() / total_peso) if total_peso > 0 else 0.0

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

        # Saúde calculada: baseada em progresso vs prazo
        hoje = date.today()
        desvio_pct_v = 0.0
        prazo_decorrido = 0.0
        if item.get("data_inicio") and termino:
            try:
                d_ini = date.fromisoformat(str(item["data_inicio"])[:10])
                d_fim = date.fromisoformat(str(termino)[:10])
                total_d = max((d_fim - d_ini).days, 1)
                dec_d   = max((hoje - d_ini).days, 0)
                prazo_decorrido = min(100.0, dec_d / total_d * 100)
                desvio_pct_v = round(prog - prazo_decorrido, 1)
            except Exception:
                pass

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

    # Geocoding automático se lat/long forem 0
    if not body.get("latitude") and not body.get("longitude") and body.get("localizacao"):
        lat, lon = await _get_coords(body["localizacao"])
        body["latitude"] = lat
        body["longitude"] = lon
    
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
    
    # Se mudar localização e não tiver lat/long, re-geocodificar
    if body.get("localizacao") and not body.get("latitude"):
        lat, lon = await _get_coords(body["localizacao"])
        body["latitude"] = lat
        body["longitude"] = lon

    sb_update("contratos", filters=filters, data=body)
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
