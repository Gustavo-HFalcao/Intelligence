"""
Dashboard router — GET /api/dashboard/kpis
Equivale às computed @rx.var do GlobalState (visão_geral).

Todas as queries filtram por client_id do tenant — nunca retornam dados de outro tenant.
"""

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query

from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant
from backend.services.data_loader import DataLoader

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_brl(v: float) -> str:
    if v >= 1_000_000:
        s = f"{v/1_000_000:.1f}M"
    elif v >= 1_000:
        s = f"{v/1_000:.1f}k"
    else:
        s = f"{v:.2f}"
    return f"R$ {s}"


def _weighted_progress(ativ: pd.DataFrame, contrato: str) -> float:
    """Média ponderada de conclusao_pct por peso_pct para um contrato."""
    mask = ativ["contrato"] == contrato
    g = ativ[mask]
    if g.empty:
        return 0.0
    if "peso_pct" in g.columns:
        total_peso = pd.to_numeric(g["peso_pct"], errors="coerce").fillna(1).sum()
        if total_peso > 0:
            return float(
                (pd.to_numeric(g["conclusao_pct"], errors="coerce").fillna(0)
                 * pd.to_numeric(g["peso_pct"], errors="coerce").fillna(1)).sum()
                / total_peso
            )
    return float(pd.to_numeric(g["conclusao_pct"], errors="coerce").fillna(0).mean())


# ── KPIs ─────────────────────────────────────────────────────────────────────

@router.get("/kpis")
async def get_dashboard_kpis(
    period: str = Query("all", description="7d | 30d | 90d | all"),
    project_filter: str = Query("", description="Contrato ID ou vazio para todos"),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """
    Retorna os KPIs da Visão Geral e dados de gráficos.
    Equivale a: valor_tcv, total_contratos, contratos_ativos, faturamento_por_cliente,
    status_contratos_dist, projetos_em_andamento, atividades_criticas_count, etc.
    """
    loader = DataLoader(client_id=client_id or "")
    data = loader.load_all()

    contratos: pd.DataFrame = data.get("contratos", pd.DataFrame())
    projetos: pd.DataFrame  = data.get("projeto",   pd.DataFrame())
    obras: pd.DataFrame     = data.get("obras",     pd.DataFrame())

    # Apply project filter
    if project_filter and project_filter != "Todos":
        if not contratos.empty and "contrato" in contratos.columns:
            contratos = contratos[contratos["contrato"] == project_filter]
        if not projetos.empty and "contrato" in projetos.columns:
            projetos = projetos[projetos["contrato"] == project_filter]
        if not obras.empty and "contrato" in obras.columns:
            obras = obras[obras["contrato"] == project_filter]

    # ── KPI: carteira ────────────────────────────────────────────────────────
    total_contratos = len(contratos)
    valor_tcv: float = 0.0
    contratos_ativos = 0

    if not contratos.empty:
        if "valor_contratado" in contratos.columns:
            valor_tcv = float(pd.to_numeric(contratos["valor_contratado"], errors="coerce").fillna(0).sum())
        if "status" in contratos.columns:
            contratos_ativos = int((contratos["status"] == "Em Execução").sum())

    # ── KPI: atividades ──────────────────────────────────────────────────────
    total_atividades = len(projetos)
    atividades_concluidas = 0
    atividades_criticas_count = 0
    atividades_criticas_atrasadas = 0

    if not projetos.empty:
        if "conclusao_pct" in projetos.columns:
            pct = pd.to_numeric(projetos["conclusao_pct"], errors="coerce").fillna(0)
            atividades_concluidas = int((pct >= 100).sum())
        if "critico" in projetos.columns:
            critico_mask = projetos["critico"].astype(str).str.lower().isin(["sim", "1", "true", "yes"])
            atividades_criticas_count = int(critico_mask.sum())
            if "conclusao_pct" in projetos.columns:
                pct2 = pd.to_numeric(projetos["conclusao_pct"], errors="coerce").fillna(0)
                atividades_criticas_atrasadas = int((critico_mask & (pct2 < 100)).sum())

    # ── Gráfico: faturamento por cliente ────────────────────────────────────
    faturamento_por_cliente: List[Dict[str, Any]] = []
    if not contratos.empty and "cliente" in contratos.columns and "valor_contratado" in contratos.columns:
        grp = (
            contratos.groupby("cliente")["valor_contratado"]
            .sum()
            .reset_index()
            .sort_values("valor_contratado", ascending=False)
            .head(10)
        )
        for _, row in grp.iterrows():
            v = float(row["valor_contratado"])
            faturamento_por_cliente.append({
                "name": row["cliente"],  # Map to 'name' for Recharts
                "value": round(v, 2),    # Map to 'value' for Recharts
                "formatted_valor": (
                    f"{v/1_000_000:.1f}M" if v >= 1_000_000
                    else (f"{v/1_000:.0f}k" if v >= 1_000 else f"{v:.0f}")
                ),
            })

    # ── Gráfico: status dos contratos ────────────────────────────────────────
    status_dist: List[Dict[str, Any]] = []
    if not contratos.empty and "status" in contratos.columns:
        dist = contratos["status"].value_counts().reset_index()
        dist.columns = ["name", "value"]
        status_dist = dist.to_dict("records")

    # ── Gráfico: projetos em andamento ──────────────────────────────────────
    projetos_em_andamento: List[Dict[str, Any]] = []
    if not projetos.empty and "conclusao_pct" in projetos.columns and "contrato" in projetos.columns:
        agg_dict: Dict[str, Any] = {"conclusao_pct": "mean"}
        if "projeto" in projetos.columns:
            agg_dict["projeto"] = "first"
        grp2 = projetos.groupby("contrato").agg(agg_dict).reset_index()
        grp2 = grp2[grp2["conclusao_pct"] < 100].sort_values("conclusao_pct", ascending=False)
        grp2["conclusao_pct"] = grp2["conclusao_pct"].round(1)
        projetos_em_andamento = grp2.to_dict("records")

    # ── Progress por contrato ────────────────────────────────────────────────
    contratos_progress: List[Dict[str, Any]] = []
    avanco_geral: float = 0.0
    if not contratos.empty and not projetos.empty and "contrato" in projetos.columns:
        total_p = 0.0
        count_p = 0
        for _, row in contratos.iterrows():
            cod = row.get("contrato", "")
            prog = _weighted_progress(projetos, cod) if cod else 0.0
            total_p += prog
            count_p += 1
            contratos_progress.append({
                "contrato": cod,
                "projeto": row.get("projeto", ""),
                "cliente": row.get("cliente", ""),
                "status": row.get("status", ""),
                "valor_contratado": float(row.get("valor_contratado", 0) or 0),
                "pct": round(prog, 1), # Map to 'pct' for Frontend
            })
        if count_p > 0:
            avanco_geral = total_p / count_p

    # ── Filter options ───────────────────────────────────────────────────────
    project_options = ["Todos"]
    if not contratos.empty and "contrato" in contratos.columns:
        project_options += sorted(contratos["contrato"].dropna().unique().tolist())

    return {
        # KPI cards
        "total_contratos":               total_contratos,
        "valor_tcv":                     round(valor_tcv, 2),
        "valor_tcv_fmt":                 _fmt_brl(valor_tcv),
        "contratos_ativos":              contratos_ativos,
        "total_atividades":              total_atividades,
        "atividades_concluidas":         atividades_concluidas,
        "atividades_criticas_count":     atividades_criticas_count,
        "atividades_criticas_atrasadas": atividades_criticas_atrasadas,
        "avanco_geral":                  round(avanco_geral, 1),
        "avanco_geral_fmt":              f"{avanco_geral:.1f}%",
        # Charts
        "faturamento_por_cliente":       faturamento_por_cliente,
        "status_contratos_dist":         status_dist,
        "projetos_em_andamento":         projetos_em_andamento,
        "contratos_progress":            contratos_progress,
        # UI
        "project_filter_options":        project_options,
    }


@router.post("/invalidate-cache")
async def invalidate_cache(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
):
    """Força recarga dos dados do Supabase na próxima requisição."""
    DataLoader.invalidate_cache(client_id or "")
    return {"ok": True}
