"""
AlertEngine — Bomtempo Intelligence
Motor de alertas reativo e configurável.

Substitui o sweep manual/agendado simples por:
- Regras dinâmicas em alert_rules (threshold, schedule, event, ai_custom)
- check_event(): chamado em hooks do sistema (RDO, cronograma, financeiro, documentos)
- run_sweep(): varre todas as regras ativas e verifica condições
- _evaluate_rule(): avalia uma regra contra os dados atuais do tenant

LGPD: client_id obrigatório em todas as queries.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_insert, sb_select, sb_update

logger = get_logger(__name__)

_BRT = timezone(timedelta(hours=-3))

# ── Métricas de desempenho ─────────────────────────────────────────────────────
_STATS: Dict[str, int] = {"events_checked": 0, "rules_fired": 0, "errors": 0}

# ─────────────────────────────────────────────────────────────────────────────
# Métricas disponíveis para regras threshold
# Cada métrica é uma função (contrato, client_id) → float | None
# ─────────────────────────────────────────────────────────────────────────────

def _metric_desvio_prazo_pct(contrato: str, client_id: str) -> Optional[float]:
    """SPI como desvio percentual: (1 - SPI) * 100. Positivo = atrasado."""
    try:
        rows = sb_select("hub_atividades", filters={"contrato": contrato}, limit=200)
        if not rows:
            return None
        total_peso = sum(float(r.get("peso_pct") or 0) for r in rows)
        if total_peso == 0:
            return None
        exec_peso = sum(
            float(r.get("peso_pct") or 0) * float(r.get("conclusao_pct") or 0) / 100
            for r in rows
        )
        plan_peso = sum(
            float(r.get("peso_pct") or 0) * float(r.get("planejado_pct") or r.get("conclusao_pct") or 0) / 100
            for r in rows
        )
        if plan_peso == 0:
            return None
        spi = exec_peso / plan_peso
        return round((1 - spi) * 100, 2)  # positivo = atrasado
    except Exception as exc:
        logger.warning(f"[AlertEngine] metric_desvio_prazo_pct error: {exc}")
        return None


def _metric_budget_overage_pct(contrato: str, client_id: str) -> Optional[float]:
    """Percentual de estouro orçamentário: (realizado - planejado) / planejado * 100."""
    try:
        rows = sb_select("fin_custos", filters={"contrato": contrato}, limit=500)
        if not rows:
            return None
        planejado = sum(float(r.get("valor_previsto") or 0) for r in rows)
        realizado = sum(float(r.get("valor_executado") or 0) for r in rows)
        if planejado == 0:
            return None
        return round((realizado - planejado) / planejado * 100, 2)
    except Exception as exc:
        logger.warning(f"[AlertEngine] metric_budget_overage_pct error: {exc}")
        return None


def _metric_risk_score(contrato: str, client_id: str) -> Optional[float]:
    """Risk score do hub_intelligence (cache de insights)."""
    try:
        rows = sb_select(
            "hub_intelligence",
            filters={"contrato": contrato, "tipo": "risk_score"},
            limit=1,
        )
        if rows:
            val = rows[0].get("valor") or rows[0].get("score")
            if val is not None:
                return float(val)
    except Exception as exc:
        logger.warning(f"[AlertEngine] metric_risk_score error: {exc}")
    return None


def _metric_rdo_horas_sem_submit(contrato: str, client_id: str) -> Optional[float]:
    """Horas desde o último RDO submetido."""
    try:
        rows = sb_select("rdo_master", filters={"contrato": contrato}, limit=1)
        # Supõe que está ordenado por created_at desc
        if not rows:
            return 999.0  # nunca teve RDO
        last_rdo = rows[0]
        ts_str = last_rdo.get("created_at") or last_rdo.get("data_rdo") or ""
        if not ts_str:
            return None
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return round(delta.total_seconds() / 3600, 1)
    except Exception as exc:
        logger.warning(f"[AlertEngine] metric_rdo_horas error: {exc}")
    return None


def _metric_producao_queda_pct(contrato: str, client_id: str) -> Optional[float]:
    """Queda de produção em atividades críticas vs média 7 dias."""
    try:
        rows = sb_select(
            "hub_atividade_historico",
            filters={"contrato": contrato},
            limit=100,
        )
        if not rows:
            return None
        # Pega as últimas entradas e calcula queda
        from collections import defaultdict
        by_ativ: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            aid = str(r.get("atividade_id") or r.get("id") or "")
            prod = r.get("producao_dia") or r.get("exec_qty_novo")
            if aid and prod is not None:
                by_ativ[aid].append(float(prod))

        quedas = []
        for aid, vals in by_ativ.items():
            if len(vals) < 4:
                continue
            media_7d = sum(vals[:-1]) / len(vals[:-1])
            ultimo = vals[-1]
            if media_7d > 0:
                queda = (media_7d - ultimo) / media_7d * 100
                quedas.append(queda)

        return round(max(quedas), 2) if quedas else None
    except Exception as exc:
        logger.warning(f"[AlertEngine] metric_producao_queda_pct error: {exc}")
    return None


_METRICS: Dict[str, Any] = {
    "desvio_prazo_pct": _metric_desvio_prazo_pct,
    "budget_overage_pct": _metric_budget_overage_pct,
    "risk_score": _metric_risk_score,
    "rdo_horas_sem_submit": _metric_rdo_horas_sem_submit,
    "producao_queda_pct": _metric_producao_queda_pct,
}

_OPERATORS: Dict[str, Any] = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: abs(a - b) < 0.001,
}


# ─────────────────────────────────────────────────────────────────────────────
# Avaliação de regras
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_threshold_rule(rule: Dict, contrato: str, client_id: str) -> Optional[str]:
    """
    Avalia regra de threshold. Retorna string de trigger_value ou None se não disparou.
    """
    cfg = rule.get("trigger_config") or {}
    metric_name = cfg.get("metric")
    operator = cfg.get("operator", "gt")
    threshold = cfg.get("value")

    if not metric_name or threshold is None:
        return None

    metric_fn = _METRICS.get(metric_name)
    if not metric_fn:
        logger.warning(f"[AlertEngine] Métrica desconhecida: {metric_name}")
        return None

    value = metric_fn(contrato, client_id)
    if value is None:
        return None

    op_fn = _OPERATORS.get(operator)
    if not op_fn:
        return None

    if op_fn(value, float(threshold)):
        return str(round(value, 2))
    return None


def _check_cooldown(rule: Dict, contrato: str) -> bool:
    """
    Retorna True se a regra está em cooldown (não deve disparar agora).
    """
    last_fired = rule.get("last_fired_at")
    if not last_fired:
        return False
    cooldown_h = int(rule.get("cooldown_hours") or 24)
    try:
        ts = datetime.fromisoformat(str(last_fired).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return delta.total_seconds() < cooldown_h * 3600
    except Exception:
        return False


def _fire_rule(rule: Dict, contrato: str, client_id: str, trigger_value: str, metadata: Dict = None) -> None:
    """
    Dispara email de alerta para uma regra + registra no histórico.
    """
    from bomtempo.core.alert_email_service import AlertEmailService

    rule_id = str(rule.get("id", ""))
    recipients = rule.get("recipients") or []
    if not recipients:
        # Busca emails da tabela legada como fallback
        try:
            subs = sb_select(
                "email_sender",
                filters={"module": f"alertas_{rule.get('trigger_type', 'custom')}"},
                limit=50,
            )
            recipients = [{"email": s.get("user_email", ""), "name": ""} for s in (subs or [])]
        except Exception:
            pass

    if not recipients:
        logger.info(f"[AlertEngine] Regra '{rule.get('name')}' disparada mas sem destinatários")
        return

    # Monta payload do email
    email_data = {
        "rule_name": rule.get("name", "Alerta"),
        "rule_description": rule.get("description", ""),
        "contrato": contrato,
        "trigger_value": trigger_value,
        "trigger_config": rule.get("trigger_config") or {},
        "category": rule.get("category", "reativo"),
        "color": rule.get("color", "#C98B2A"),
        "icon": rule.get("icon", "bell"),
        "metadata": metadata or {},
        "generated_at": datetime.now(_BRT).strftime("%d/%m/%Y %H:%M BRT"),
    }

    try:
        AlertEmailService.send_alert_email(
            recipients=[r.get("email") for r in recipients if r.get("email")],
            data=email_data,
        )
        status = "sent"
    except Exception as exc:
        logger.error(f"[AlertEngine] Email error para regra '{rule.get('name')}': {exc}")
        status = "error"

    # Registra no histórico
    try:
        sb_insert("alert_rule_history", {
            "rule_id": rule_id or None,
            "client_id": client_id or None,
            "contrato": contrato,
            "trigger_value": trigger_value,
            "recipients_sent": [r.get("email") for r in recipients],
            "email_subject": f"[Bomtempo] {rule.get('name', 'Alerta')} — {contrato}",
            "status": status,
        })
        # Atualiza last_fired_at e fire_count na regra
        if rule_id:
            sb_update("alert_rules", filters={"id": rule_id}, data={
                "last_fired_at": datetime.now(timezone.utc).isoformat(),
                "fire_count": int(rule.get("fire_count") or 0) + 1,
            })
        _STATS["rules_fired"] += 1
        logger.info(f"[AlertEngine] ✅ Alerta disparado: '{rule.get('name')}' — {contrato} — {trigger_value}")
    except Exception as exc:
        logger.error(f"[AlertEngine] Histórico error: {exc}")

    # Também registra no alert_history legado para compatibilidade
    try:
        from bomtempo.core.audit_logger import audit_log, AuditCategory
        audit_log(
            category=AuditCategory.ALERT_TRIGGER,
            action=f"[{contrato}] {rule.get('name', 'Alerta')} disparado — valor: {trigger_value}",
            metadata={"rule_id": rule_id, "trigger_value": trigger_value, "contrato": contrato},
            status=status,
            client_id=client_id,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

class AlertEngine:
    """
    Motor central de alertas reativos.

    Dois modos de operação:
    1. check_event(): chamado de hooks do sistema — rápido, filtra por event_type
    2. run_sweep(): varre todas as regras ativas — chamado pelo scheduler
    """

    @staticmethod
    def check_event(
        event_type: str,
        contrato: str,
        client_id: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Verifica regras do tipo 'event' que correspondem ao event_type.
        Fire-and-forget em thread daemon.
        """
        t = threading.Thread(
            target=AlertEngine._check_event_sync,
            args=(event_type, contrato, client_id, metadata or {}),
            daemon=True,
            name=f"alert-event-{event_type[:20]}",
        )
        t.start()

    @staticmethod
    def _check_event_sync(
        event_type: str, contrato: str, client_id: str, metadata: Dict
    ) -> None:
        _STATS["events_checked"] += 1
        try:
            filters: Dict = {"is_active": True, "trigger_type": "event"}
            if client_id:
                filters["client_id"] = client_id
            rules = sb_select("alert_rules", filters=filters, limit=100) or []

            for rule in rules:
                cfg = rule.get("trigger_config") or {}
                if cfg.get("event") != event_type:
                    continue
                # Verifica contratos alvo
                contracts = rule.get("contracts") or []
                if contracts and contrato not in contracts:
                    continue
                if _check_cooldown(rule, contrato):
                    continue
                _fire_rule(rule, contrato, client_id, event_type, metadata)
        except Exception as exc:
            _STATS["errors"] += 1
            logger.error(f"[AlertEngine] check_event_sync error: {exc}")

    @staticmethod
    def run_sweep(client_id: str = "", contrato: str = "") -> Dict[str, int]:
        """
        Varre todas as regras threshold ativas e verifica condições.
        Pode ser chamado pelo scheduler ou manualmente.
        Retorna: {sent, skipped, errors}
        """
        result = {"sent": 0, "skipped": 0, "errors": 0}
        try:
            filters: Dict = {"is_active": True, "trigger_type": "threshold"}
            if client_id:
                filters["client_id"] = client_id
            rules = sb_select("alert_rules", filters=filters, limit=200) or []

            # Busca contratos ativos se não especificado
            contratos_ativos: List[str] = []
            if contrato:
                contratos_ativos = [contrato]
            else:
                try:
                    ct_filters: Dict = {}
                    if client_id:
                        ct_filters["client_id"] = client_id
                    ct_rows = sb_select("contratos", filters=ct_filters, limit=100) or []
                    contratos_ativos = [r.get("contrato") or r.get("id") for r in ct_rows if r.get("contrato") or r.get("id")]
                except Exception:
                    pass

            for rule in rules:
                target_contracts = rule.get("contracts") or contratos_ativos
                for ct in target_contracts:
                    if not ct:
                        continue
                    if _check_cooldown(rule, ct):
                        result["skipped"] += 1
                        continue
                    try:
                        trigger_value = _evaluate_threshold_rule(rule, ct, client_id)
                        if trigger_value is not None:
                            _fire_rule(rule, ct, client_id, trigger_value)
                            result["sent"] += 1
                        else:
                            result["skipped"] += 1
                    except Exception as exc:
                        result["errors"] += 1
                        logger.error(f"[AlertEngine] evaluate_rule error [{ct}]: {exc}")
        except Exception as exc:
            result["errors"] += 1
            logger.error(f"[AlertEngine] run_sweep error: {exc}")
        return result

    @staticmethod
    def run_sweep_for_event_type(alert_type: str, client_id: str = "") -> Dict[str, int]:
        """
        Compatibilidade com o AlertService legado.
        Mapeia tipos antigos para o novo motor.
        """
        # Mapa de tipos legados para métricas
        legacy_map: Dict[str, str] = {
            "risk_high": "risk_score",
            "budget_overage": "budget_overage_pct",
            "rdo_pending": "rdo_horas_sem_submit",
        }
        metric = legacy_map.get(alert_type)
        if not metric:
            # Para tipos cronológicos (daily, weekly, monthly), usa sweep normal
            return AlertEngine.run_sweep(client_id=client_id)

        # Cria filtro específico para a métrica
        result = {"sent": 0, "skipped": 0, "errors": 0}
        try:
            filters: Dict = {"is_active": True, "trigger_type": "threshold"}
            if client_id:
                filters["client_id"] = client_id
            rules = sb_select("alert_rules", filters=filters, limit=200) or []
            rules = [r for r in rules if (r.get("trigger_config") or {}).get("metric") == metric]

            if not rules:
                result["skipped"] = 1
                return result

            ct_rows = sb_select("contratos", filters={"client_id": client_id} if client_id else {}, limit=100) or []
            contratos_ativos = [r.get("contrato") or r.get("id") for r in ct_rows]

            for rule in rules:
                for ct in (rule.get("contracts") or contratos_ativos):
                    if not ct:
                        continue
                    trigger_value = _evaluate_threshold_rule(rule, ct, client_id)
                    if trigger_value:
                        _fire_rule(rule, ct, client_id, trigger_value)
                        result["sent"] += 1
                    else:
                        result["skipped"] += 1
        except Exception as exc:
            result["errors"] += 1
            logger.error(f"[AlertEngine] run_sweep_for_event_type error: {exc}")
        return result

    @staticmethod
    def get_stats() -> Dict[str, int]:
        return dict(_STATS)
