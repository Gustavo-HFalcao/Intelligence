"""
Alert Tasks — Celery tasks para disparar e sweepear alertas.

Dois modos:
  1. check_alert_event  — evento pontual (ex: RDO submetido) → avalia regras do tipo "event"
  2. run_alert_sweep    — sweep periódico (Celery beat) → avalia regras de threshold para todos os contratos

Port de bomtempo/core/alert_engine.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.workers.celery_app import celery_app
from backend.core.logging import get_logger

logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_active_rules(client_id: str, rule_type: Optional[str] = None) -> List[Dict]:
    from backend.integrations.supabase import sb_select
    filters: Dict[str, Any] = {"client_id": client_id, "active": True}
    if rule_type:
        filters["rule_type"] = rule_type
    try:
        return sb_select("alert_rules", filters=filters) or []
    except Exception as e:
        logger.warning(f"alert: failed to load rules: {e}")
        return []


def _in_cooldown(rule: Dict) -> bool:
    cooldown_hours = rule.get("cooldown_hours", 24)
    last_fired = _parse_dt(rule.get("last_fired_at"))
    if not last_fired:
        return False
    return _now() < last_fired + timedelta(hours=cooldown_hours)


def _fire_alert(rule: Dict, contrato: str, message: str, metadata: Optional[Dict] = None) -> None:
    from backend.integrations.supabase import sb_insert, sb_update
    from backend.core.audit import audit_log, AuditCategory

    rule_id    = rule.get("id")
    client_id  = rule.get("client_id", "")
    recipients = rule.get("recipients") or []

    history_row = {
        "rule_id":    rule_id,
        "client_id":  client_id,
        "contrato":   contrato,
        "message":    message[:500],
        "fired_at":   _now().isoformat(),
        "metadata":   metadata or {},
    }
    try:
        sb_insert("alert_rule_history", history_row)
    except Exception as e:
        logger.warning(f"alert: failed to insert history: {e}")

    try:
        sb_update(
            "alert_rules",
            {"id": rule_id},
            {
                "last_fired_at": _now().isoformat(),
                "fire_count":    (rule.get("fire_count") or 0) + 1,
            },
        )
    except Exception as e:
        logger.warning(f"alert: failed to update rule last_fired_at: {e}")

    # Email
    if recipients:
        try:
            from backend.integrations.email import send_alert_email
            for recipient in recipients:
                send_alert_email(to=recipient, subject=f"[ALERTA] {rule.get('name','')}", body=message)
        except Exception as e:
            logger.debug(f"alert: email send failed: {e}")

    audit_log(
        category=AuditCategory.ALERT_TRIGGER,
        action=f"Alerta disparado: {rule.get('name','')} — {contrato}",
        client_id=client_id,
        entity_type="alert_rule",
        entity_id=str(rule_id or ""),
        metadata={"message": message[:200], **(metadata or {})},
    )
    logger.info(f"alert fired: rule={rule.get('name')} contrato={contrato}")


# ── Metric calculators ────────────────────────────────────────────────────────

def _calc_desvio_prazo(contrato: str, client_id: str) -> Optional[float]:
    """% de atividades atrasadas no contrato."""
    from backend.integrations.supabase import sb_select
    rows = sb_select("cronograma", filters={"contrato": contrato, "client_id": client_id}) or []
    if not rows:
        return None
    today = datetime.now(timezone.utc).date()
    total = len(rows)
    atrasadas = sum(
        1 for r in rows
        if r.get("data_fim") and datetime.fromisoformat(str(r["data_fim"])).date() < today
        and (r.get("pct_executado") or 0) < 100
    )
    return round(atrasadas / total * 100, 1) if total else 0.0


def _calc_budget_overage(contrato: str, client_id: str) -> Optional[float]:
    """% de desvio orçamentário (executado/previsto - 1)."""
    from backend.integrations.supabase import sb_select
    rows = sb_select("financeiro", filters={"contrato": contrato, "client_id": client_id}) or []
    if not rows:
        return None
    previsto  = sum(r.get("valor_previsto", 0) or 0 for r in rows)
    executado = sum(r.get("valor_executado", 0) or 0 for r in rows)
    if not previsto:
        return None
    return round((executado / previsto - 1) * 100, 1)


def _calc_rdo_gap_hours(contrato: str, client_id: str) -> Optional[float]:
    """Horas desde o último RDO submetido."""
    from backend.integrations.supabase import sb_select
    rows = sb_select(
        "rdo_master",
        filters={"contrato": contrato, "client_id": client_id, "status": "submitted"},
    ) or []
    if not rows:
        return None
    dates = [_parse_dt(r.get("data_rdo") or r.get("submitted_at")) for r in rows]
    dates = [d for d in dates if d]
    if not dates:
        return None
    latest = max(dates)
    return (_now() - latest).total_seconds() / 3600


# ── Celery Tasks ──────────────────────────────────────────────────────────────

@celery_app.task(
    name="backend.workers.tasks.alert_tasks.check_alert_event",
    bind=True,
    max_retries=0,
    queue="default",
)
def check_alert_event(
    self,
    event_type: str,
    contrato: str = "",
    client_id: str = "",
    metadata: Optional[Dict] = None,
) -> None:
    """Avalia regras de alerta do tipo 'event' para um evento pontual."""
    try:
        rules = _get_active_rules(client_id, rule_type="event")
        for rule in rules:
            if rule.get("event_type") != event_type:
                continue
            if _in_cooldown(rule):
                continue
            msg = rule.get("message_template", f"Evento {event_type} detectado em {contrato}")
            _fire_alert(rule, contrato, msg, metadata)
    except Exception as e:
        logger.error(f"check_alert_event error: {e}")


@celery_app.task(
    name="backend.workers.tasks.alert_tasks.run_alert_sweep",
    bind=True,
    max_retries=0,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def run_alert_sweep(self) -> Dict[str, Any]:
    """
    Sweep periódico: avalia regras de threshold para todos os contratos ativos.
    Agendado via Celery beat — roda a cada hora.
    """
    from backend.integrations.supabase import sb_select

    fired_total = 0
    errors: List[str] = []

    try:
        # Agrupa regras por client_id
        all_rules = sb_select("alert_rules", filters={"active": True}) or []
        by_client: Dict[str, List[Dict]] = {}
        for r in all_rules:
            if r.get("rule_type") != "threshold":
                continue
            cid = str(r.get("client_id", ""))
            by_client.setdefault(cid, []).append(r)

        for client_id, rules in by_client.items():
            contratos = sb_select(
                "contratos",
                filters={"client_id": client_id, "status": "ativo"},
            ) or []

            for contrato_row in contratos:
                contrato = contrato_row.get("contrato") or contrato_row.get("id", "")
                if not contrato:
                    continue

                metrics: Dict[str, Optional[float]] = {}

                for rule in rules:
                    metric_name = rule.get("metric")
                    threshold   = rule.get("threshold_value")
                    operator    = rule.get("operator", "gt")  # gt | lt | gte | lte

                    if _in_cooldown(rule):
                        continue

                    # Lazy-compute metrics per contrato
                    if metric_name not in metrics:
                        try:
                            if metric_name == "desvio_prazo_pct":
                                metrics[metric_name] = _calc_desvio_prazo(contrato, client_id)
                            elif metric_name == "budget_overage_pct":
                                metrics[metric_name] = _calc_budget_overage(contrato, client_id)
                            elif metric_name == "rdo_horas_sem_submit":
                                metrics[metric_name] = _calc_rdo_gap_hours(contrato, client_id)
                            else:
                                metrics[metric_name] = None
                        except Exception as e:
                            metrics[metric_name] = None
                            errors.append(f"{contrato}/{metric_name}: {e}")

                    value = metrics.get(metric_name)
                    if value is None or threshold is None:
                        continue

                    triggered = False
                    if operator == "gt"  and value >  threshold: triggered = True
                    if operator == "gte" and value >= threshold: triggered = True
                    if operator == "lt"  and value <  threshold: triggered = True
                    if operator == "lte" and value <= threshold: triggered = True

                    if triggered:
                        msg = (
                            rule.get("message_template")
                            or f"{metric_name} = {value:.1f} (threshold {operator} {threshold}) — {contrato}"
                        )
                        _fire_alert(rule, contrato, msg, {"metric": metric_name, "value": value})
                        fired_total += 1

    except Exception as e:
        logger.error(f"run_alert_sweep fatal: {e}")
        errors.append(str(e))

    logger.info(f"alert sweep done — fired={fired_total} errors={len(errors)}")
    return {"fired": fired_total, "errors": errors}
