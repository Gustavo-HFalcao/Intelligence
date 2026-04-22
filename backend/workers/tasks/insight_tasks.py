"""
Insight Tasks — geração assíncrona de insights de IA pós-submit de RDO.

Roda na fila 'default' via Celery. Fire-and-forget: o submit do RDO retorna
imediatamente, sem esperar pelo cálculo de insights.

Lógica portada de rdo.py::_trigger_insights() — agora isolada e testável.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from backend.workers.celery_app import celery_app
from backend.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="backend.workers.tasks.insight_tasks.generate_insights",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=60,
    time_limit=90,
)
def generate_insights(self, contrato: str, rdo_id: str, client_id: str = "") -> Dict[str, Any]:
    """
    Calcula insights SPI/caminho crítico para o contrato e persiste em agente_insights.
    Chamado após submit de RDO — nunca bloqueia o response ao usuário.
    """
    from backend.integrations.supabase import sb_insert, sb_select, sb_update

    try:
        today = date.today()

        atividades = sb_select(
            "hub_atividades",
            filters={"contrato": contrato},
            client_id=client_id or None,
            limit=500,
        ) or []

        insights: List[Dict[str, Any]] = []

        if atividades:
            total = len(atividades)
            atrasadas: List[Dict] = []
            criticas_baixo_pct: List[Dict] = []
            prazo_7dias: List[Dict] = []

            for a in atividades:
                pct     = int(a.get("conclusao_pct") or 0)
                ter     = a.get("termino_previsto", "")
                ini     = a.get("inicio_previsto", "")
                nome    = a.get("atividade", "Atividade")
                critico = str(a.get("critico", "")).lower() in ("sim", "true", "1")

                if pct >= 100 or not ter:
                    continue

                try:
                    d_ter = date.fromisoformat(ter[:10])
                    d_ini = date.fromisoformat(ini[:10]) if ini else today
                except Exception:
                    continue

                dias_total   = max(1, (d_ter - d_ini).days)
                dias_dec     = max(0, (today - d_ini).days)
                pct_esperado = min(100, int(dias_dec / dias_total * 100))

                if d_ter < today:
                    atrasadas.append({"nome": nome, "ter": ter[:10], "pct": pct, "critico": critico})

                if critico and pct < 80 and pct_esperado > 70:
                    criticas_baixo_pct.append({"nome": nome, "pct": pct, "esperado": pct_esperado})

                dias_restantes = (d_ter - today).days
                if 0 <= dias_restantes <= 7 and pct < 90:
                    prazo_7dias.append({"nome": nome, "dias": dias_restantes, "pct": pct})

            if atrasadas:
                mais_critica = next((a for a in atrasadas if a["critico"]), atrasadas[0])
                insights.append({
                    "priority": "High",
                    "title":    f"{len(atrasadas)} atividade(s) com prazo vencido",
                    "body":     (
                        f"'{mais_critica['nome'][:50]}' deveria ter sido concluída em "
                        f"{mais_critica['ter']} e está em {mais_critica['pct']}%. "
                        "Prioridade máxima de ação."
                    ),
                })

            if criticas_baixo_pct:
                a = criticas_baixo_pct[0]
                insights.append({
                    "priority": "High",
                    "title":    "Atividade crítica com progresso insuficiente",
                    "body":     (
                        f"'{a['nome'][:50]}' está em {a['pct']}% quando o esperado é "
                        f"{a['esperado']}%. Risco de desvio no caminho crítico."
                    ),
                })

            if prazo_7dias:
                a = prazo_7dias[0]
                insights.append({
                    "priority": "Medium",
                    "title":    f"{len(prazo_7dias)} atividade(s) vencem em até 7 dias",
                    "body":     (
                        f"'{a['nome'][:50]}' vence em {a['dias']} dia(s) com "
                        f"{a['pct']}% de conclusão. Requer atenção imediata."
                    ),
                })

            concluidas = sum(1 for a in atividades if int(a.get("conclusao_pct") or 0) >= 100)
            pct_medio  = int(sum(int(a.get("conclusao_pct") or 0) for a in atividades) / max(1, total))

            if pct_medio >= 80:
                insights.append({
                    "priority": "Low",
                    "title":    f"Projeto em fase avançada — {pct_medio}% de progresso médio",
                    "body":     f"{concluidas} de {total} atividades concluídas. Mantenha o ritmo para entrega dentro do prazo.",
                })
            elif not insights:
                insights.append({
                    "priority": "Low",
                    "title":    f"Cronograma em andamento — {pct_medio}% progresso médio",
                    "body":     f"{concluidas} de {total} atividades concluídas. Acompanhe as atividades previstas para os próximos dias.",
                })

        payload: Dict[str, Any] = {
            "contrato":    contrato,
            "insights":    insights,
            "last_rdo_id": rdo_id,
            "updated_at":  datetime.now(timezone.utc).isoformat(),
            "client_id":   client_id or None,
        }

        existing = sb_select("agente_insights", filters={"contrato": contrato}, client_id=client_id or None, limit=1) or []
        if existing:
            sb_update("agente_insights", filters={"id": existing[0]["id"]}, data=payload)
        else:
            sb_insert("agente_insights", payload)

        logger.info(f"insights gerados: contrato={contrato} n={len(insights)} rdo={rdo_id[:8]}")
        return {"ok": True, "insights": len(insights)}

    except Exception as e:
        logger.error(f"generate_insights error: contrato={contrato} {e}")
        return {"ok": False, "error": str(e)}
