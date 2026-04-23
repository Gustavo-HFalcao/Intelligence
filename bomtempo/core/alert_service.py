"""
AlertService — Bomtempo Intelligence
Manages alert subscriptions, sweep execution, email dispatch, and
background scheduling for the Proactive Alerts module.

Tables used (zero schema migrations required):
  • email_sender       — one row per (contract, email, module='alertas_ALERT_TYPE')
  • alert_subscriptions — one row per alert_type (global on/off toggle)
                          user_email = 'scheduler@bomtempo.com.br' (sentinel)
  • alert_history      — one row per sweep execution (project_code, alert_type, message)
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_delete, sb_insert, sb_select, sb_update

logger = get_logger(__name__)

# ── Alert type registry ────────────────────────────────────────────────────────

ALERT_TYPES: Dict[str, Dict[str, str]] = {
    "daily": {
        "label": "Resumo Diário",
        "category": "cronologico",
        "icon": "sun",
        "color": "#2A9D8F",
        "description": "Resumo automático enviado diariamente às 18h com avanço físico, risco e efetivo de campo.",
        "schedule": "Todos os dias às 18h",
    },
    "weekly": {
        "label": "Resumo Semanal",
        "category": "cronologico",
        "icon": "calendar-days",
        "color": "#3B82F6",
        "description": "Consolidado semanal enviado toda segunda-feira às 8h com comparativo da semana anterior.",
        "schedule": "Toda segunda-feira às 8h",
    },
    "monthly": {
        "label": "Fechamento de Medição",
        "category": "cronologico",
        "icon": "file-text",
        "color": "#C98B2A",
        "description": "Balanço financeiro enviado todo dia 25 com execução vs planejado do ciclo.",
        "schedule": "Todo dia 25 às 9h",
    },
    "risk_high": {
        "label": "Risco Alto (≥70)",
        "category": "reativo",
        "icon": "alert-triangle",
        "color": "#EF4444",
        "description": "Disparado quando o score de risco geral do contrato atinge ou ultrapassa 70.",
        "schedule": "Verificado diariamente às 18h",
    },
    "budget_overage": {
        "label": "Budget Estourado >5%",
        "category": "reativo",
        "icon": "trending-up",
        "color": "#F59E0B",
        "description": "Disparado quando o valor realizado ultrapassa o planejado em mais de 5%.",
        "schedule": "Verificado diariamente às 18h",
    },
    "rdo_pending": {
        "label": "RDO Pendente (48h)",
        "category": "reativo",
        "icon": "clock",
        "color": "#8B5CF6",
        "description": "Disparado quando nenhum RDO foi submetido para um contrato há mais de 48 horas.",
        "schedule": "Verificado diariamente às 18h",
    },
}

_BRT = timezone(timedelta(hours=-3))  # Brasília Time (UTC-3)

_SENTINEL_EMAIL = "scheduler@bomtempo.com.br"
_TABLE_SUBS = "alert_subscriptions"   # global toggle per alert_type
_TABLE_EMAIL = "email_sender"          # per-contract email recipients
_TABLE_HIST = "alert_history"

# ── Module name helpers ───────────────────────────────────────────────────────

def _module_name(alert_type: str) -> str:
    return f"alertas_{alert_type}"

def _alert_type_from_module(module: str) -> str:
    return module.replace("alertas_", "", 1)


class AlertService:

    # ────────────────────────────────────────────────────────────────────────
    # Toggle state — alert_subscriptions table (global on/off per alert_type)
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_toggle_row(alert_type: str, client_id: str = "") -> Optional[Dict]:
        """Ensure a toggle row exists for the given alert_type. Creates if missing."""
        filters: Dict = {"alert_type": alert_type, "user_email": _SENTINEL_EMAIL}
        if client_id:
            filters["client_id"] = client_id
        rows = sb_select(_TABLE_SUBS, filters=filters)
        if rows:
            return rows[0]
        try:
            record: Dict = {"user_email": _SENTINEL_EMAIL, "alert_type": alert_type, "is_active": True}
            if client_id:
                record["client_id"] = client_id
            return sb_insert(_TABLE_SUBS, record)
        except Exception as exc:
            logger.warning(f"[AlertService._ensure_toggle_row] {exc}")
            return None

    @staticmethod
    def get_toggle_states(client_id: str = "") -> Dict[str, bool]:
        """Returns {alert_type: is_active} for all alert types."""
        filters: Dict = {"user_email": _SENTINEL_EMAIL}
        if client_id:
            filters["client_id"] = client_id
        rows = sb_select(_TABLE_SUBS, filters=filters) or []
        state: Dict[str, bool] = {k: True for k in ALERT_TYPES}  # default all active
        for row in rows:
            at = str(row.get("alert_type", ""))
            if at in state:
                state[at] = bool(row.get("is_active", True))
        return state

    @staticmethod
    def set_toggle(alert_type: str, is_active: bool, client_id: str = "") -> bool:
        """Toggle a global alert type on or off."""
        row = AlertService._ensure_toggle_row(alert_type, client_id=client_id)
        if not row:
            return False
        try:
            sb_update(_TABLE_SUBS, {"id": row["id"]}, {"is_active": is_active})
            return True
        except Exception as exc:
            logger.error(f"[AlertService.set_toggle] {exc}")
            return False

    # ────────────────────────────────────────────────────────────────────────
    # Subscription CRUD — email_sender table
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_email_subscriptions(client_id: str = "") -> List[Dict]:
        """All alertas subscriptions from email_sender, grouped by (alert_type, contract)."""
        all_rows: List[Dict] = []
        for at in ALERT_TYPES:
            filters: Dict = {"module": _module_name(at)}
            if client_id:
                filters["client_id"] = client_id
            rows = sb_select(_TABLE_EMAIL, filters=filters) or []
            all_rows.extend(rows)

        groups: Dict[Tuple[str, str], Dict] = {}
        for row in all_rows:
            module = str(row.get("module", ""))
            at = _alert_type_from_module(module)
            ct = str(row.get("contract", "")).strip()
            key = (at, ct)
            if key not in groups:
                meta = ALERT_TYPES.get(at, {})
                groups[key] = {
                    "alert_type": at,
                    "alert_label": meta.get("label", at),
                    "alert_color": meta.get("color", "#C98B2A"),
                    "contract": ct,
                    "email_chips": [],
                    "key": f"{at}|{ct}",
                }
            email = str(row.get("email", "")).strip()
            row_id = str(row.get("id", ""))
            if email:
                groups[key]["email_chips"].append({"email": email, "id": row_id})

        result = list(groups.values())
        for g in result:
            g["count"] = str(len(g["email_chips"]))
            g["emails_display"] = ", ".join(c["email"] for c in g["email_chips"])
        return result

    @staticmethod
    def email_exists(alert_type: str, contract: str, email: str, client_id: str = "") -> bool:
        filters: Dict = {"module": _module_name(alert_type), "contract": contract, "email": email.lower().strip()}
        if client_id:
            filters["client_id"] = client_id
        rows = sb_select(_TABLE_EMAIL, filters=filters) or []
        return len(rows) > 0

    @staticmethod
    def contract_has_subscription(alert_type: str, contract: str, client_id: str = "") -> bool:
        filters: Dict = {"module": _module_name(alert_type), "contract": contract}
        if client_id:
            filters["client_id"] = client_id
        rows = sb_select(_TABLE_EMAIL, filters=filters) or []
        return len(rows) > 0

    @staticmethod
    def add_email_subscription(
        alert_type: str, contract: str, email: str, created_by: str = "admin", client_id: str = ""
    ) -> Tuple[bool, str]:
        """
        Adds an email recipient for an alert+contract pair.
        Returns (success, message).
        """
        email = email.strip().lower()
        contract = contract.strip()

        if not email or "@" not in email or "." not in email:
            return False, "E-mail inválido."
        if not alert_type or alert_type not in ALERT_TYPES:
            return False, "Tipo de alerta inválido."
        if not contract:
            return False, "Contrato é obrigatório."
        if AlertService.email_exists(alert_type, contract, email, client_id=client_id):
            return False, f"'{email}' já está cadastrado para este alerta neste contrato."

        existing = AlertService.contract_has_subscription(alert_type, contract, client_id=client_id)
        try:
            record: Dict = {
                "contract": contract,
                "email": email,
                "module": _module_name(alert_type),
                "created_by": created_by,
                "updated_date": datetime.now().isoformat(),
            }
            if client_id:
                record["client_id"] = client_id
            sb_insert(_TABLE_EMAIL, record)
            if existing:
                return True, f"E-mail adicionado ao grupo de '{ALERT_TYPES[alert_type]['label']}' — {contract}."
            return True, f"Novo alerta configurado: '{ALERT_TYPES[alert_type]['label']}' para {contract}."
        except Exception as exc:
            logger.error(f"[AlertService.add_email_subscription] {exc}")
            return False, "Erro ao salvar. Tente novamente."

    @staticmethod
    def delete_email_subscription(row_id: str) -> bool:
        """Delete a single email subscription row by its ID."""
        return sb_delete(_TABLE_EMAIL, {"id": row_id})

    @staticmethod
    def get_recipients(alert_type: str, contract: str) -> List[str]:
        """Return list of recipient emails for a given alert_type + contract."""
        rows = sb_select(
            _TABLE_EMAIL,
            filters={"module": _module_name(alert_type), "contract": contract},
        ) or []
        return [str(r.get("email", "")).strip() for r in rows if r.get("email")]

    # ────────────────────────────────────────────────────────────────────────
    # Alert History
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_history(page: int = 1, per_page: int = 30, client_id: str = "") -> tuple:
        """Returns (rows: List[Dict], total_count: int) — paginated.
        Requires client_id — returns empty if not provided (prevents cross-tenant leakage)."""
        if not client_id:
            return [], 0
        from bomtempo.core.supabase_client import sb_select_paginated
        rows, total = sb_select_paginated(
            _TABLE_HIST,
            page=page,
            limit=per_page,
            order="timestamp.desc",
            filters={"client_id": client_id},
        )
        return rows or [], total

    @staticmethod
    def _log_history(contract: str, alert_type: str, message: str, client_id: str = "") -> None:
        # project_code has FK to contratos — leave NULL, contract info is in message
        try:
            record: Dict = {
                "alert_type": alert_type,
                "message": f"[{contract}] {message}"[:500],
                "is_read": False,
            }
            if client_id:
                record["client_id"] = client_id
            sb_insert(_TABLE_HIST, record)
        except Exception as exc:
            logger.warning(f"[AlertService._log_history] {exc}")

    # ────────────────────────────────────────────────────────────────────────
    # Sweep logic
    # ────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_obras_map() -> Dict[str, Dict]:
        """Build contract_code → obra dict from contratos table."""
        obras = sb_select("contratos", limit=500) or []
        result: Dict[str, Dict] = {}
        for obra in obras:
            cid = str(
                obra.get("Contrato") or obra.get("contrato") or
                obra.get("ID") or obra.get("id") or ""
            ).strip()
            if cid:
                result[cid] = obra
        return result

    @staticmethod
    def _build_message(contract: str, obra: Dict, alert_type: str) -> str:
        meta = ALERT_TYPES.get(alert_type, {})
        label = meta.get("label", alert_type)
        avanco = (obra.get("avanco_realizado_pct") or obra.get("realizado_pct") or
                  obra.get("Realizado (%)") or obra.get("avanco_fisico") or "—")
        risco = obra.get("risco_geral_score") or "—"
        budget_p = obra.get("budget_planejado") or "—"
        budget_r = obra.get("budget_realizado") or "—"
        projeto = obra.get("projeto") or "—"
        return (
            f"[{label}] {contract} | {projeto} | "
            f"Avanço: {avanco}% | Risco: {risco} | Exec: {budget_r}/{budget_p}"
        )

    @staticmethod
    def run_sweep(alert_type: str) -> Dict[str, int]:
        """
        Execute a sweep for the given alert_type.
        - Checks global toggle in alert_subscriptions.
        - Fetches recipients from email_sender.
        - Applies reactive conditions (risk_high, budget_overage).
        - Sends emails and logs to alert_history.
        Returns {"sent": n, "errors": n, "skipped": n}.
        """
        from bomtempo.core.email_service import EmailService

        # Check global toggle
        toggle_states = AlertService.get_toggle_states()
        if not toggle_states.get(alert_type, True):
            logger.info(f"[AlertService.sweep] '{alert_type}' is globally disabled — skip.")
            return {"sent": 0, "errors": 0, "skipped": 1}

        # Get all subscriptions for this alert_type
        all_rows = sb_select(_TABLE_EMAIL, filters={"module": _module_name(alert_type)}) or []
        if not all_rows:
            logger.info(f"[AlertService.sweep] No subscribers for '{alert_type}'.")
            return {"sent": 0, "errors": 0, "skipped": 0}

        # Group by contract
        contract_emails: Dict[str, List[str]] = {}
        for row in all_rows:
            ct = str(row.get("contract", "")).strip()
            em = str(row.get("email", "")).strip()
            if ct and em:
                contract_emails.setdefault(ct, []).append(em)

        obras_map = AlertService._get_obras_map()
        sent = errors = skipped = 0

        for contract, emails in contract_emails.items():
            obra = obras_map.get(contract, {})

            # Reactive filters — only send if condition is met
            if alert_type == "risk_high":
                try:
                    score = float(obra.get("risco_geral_score") or 0)
                    if score < 70:
                        skipped += 1
                        continue
                except (ValueError, TypeError):
                    skipped += 1
                    continue
            elif alert_type == "budget_overage":
                try:
                    bp = float(obra.get("budget_planejado") or 0)
                    br = float(obra.get("budget_realizado") or 0)
                    if bp <= 0 or br <= bp * 1.05:
                        skipped += 1
                        continue
                except (ValueError, TypeError):
                    skipped += 1
                    continue
            elif alert_type == "rdo_pending":
                # Fire only if no RDO was submitted for this contract in the last 48h
                from datetime import timedelta
                rdo_rows = sb_select(
                    "rdo_cabecalho",
                    filters={"Contrato": contract},
                    order="Data.desc",
                    limit=1,
                ) or []
                if rdo_rows:
                    last_date_str = str(rdo_rows[0].get("Data", ""))
                    try:
                        last_dt = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
                        if datetime.now() - last_dt < timedelta(hours=48):
                            skipped += 1
                            continue
                    except (ValueError, TypeError):
                        pass  # can't parse date — send the alert anyway

            msg = AlertService._build_message(contract, obra, alert_type)
            try:
                EmailService.send_alert_email(
                    recipients=emails,
                    contract=contract,
                    alert_label=ALERT_TYPES[alert_type]["label"],
                    alert_color=ALERT_TYPES[alert_type]["color"],
                    obra_data=obra,
                )
                AlertService._log_history(contract, alert_type, msg)
                sent += 1
            except Exception as exc:
                logger.error(f"[AlertService.sweep] {alert_type}/{contract}: {exc}")
                errors += 1

        logger.info(f"[AlertService] Sweep '{alert_type}': sent={sent}, errors={errors}, skipped={skipped}")
        return {"sent": sent, "errors": errors, "skipped": skipped}


# ── Custom Alert Runner ────────────────────────────────────────────────────────

class CustomAlertRunner:
    """
    Executa alertas criados dinamicamente pelo Action AI (tabela custom_alerts).
    Chamado pelo scheduler a cada ciclo de sweep diário/horário.
    """

    @staticmethod
    def run_due(schedule: str = "daily", now: "datetime | None" = None) -> None:
        """
        Busca todos os custom_alerts ativos com o schedule informado e avalia cada condição.
        Se a condição for atendida, envia e-mail e loga no alert_history.
        """
        from bomtempo.core.email_service import EmailService

        if now is None:
            now = datetime.now(_BRT)

        try:
            rows = sb_select("custom_alerts", filters={"is_active": True, "schedule": schedule}) or []
        except Exception as exc:
            logger.error(f"[CustomAlertRunner] Erro ao buscar custom_alerts: {exc}")
            return

        for alert in rows:
            alert_id = str(alert.get("id", ""))
            alert_name = str(alert.get("alert_name", "Alerta"))
            alert_type = str(alert.get("alert_type", "custom"))
            contrato = alert.get("contrato")  # None = todos
            alert_client_id = str(alert.get("client_id") or "")  # tenant isolation
            condition_field = alert.get("condition_field") or ""
            condition_op = str(alert.get("condition_op", "missing"))
            condition_value = str(alert.get("condition_value") or "")
            notify_emails = alert.get("notify_emails") or []
            description = str(alert.get("description", ""))

            # Skip if no contrato AND no client_id — would evaluate across all tenants
            if not contrato and not alert_client_id:
                logger.warning(f"[CustomAlertRunner] Alerta '{alert_name}' sem contrato nem client_id — ignorado por segurança")
                continue

            # Dedup: skip if already fired within the cooldown window
            last_fired_raw = alert.get("last_fired_at")
            if last_fired_raw:
                try:
                    last_fired = datetime.fromisoformat(
                        str(last_fired_raw).replace("Z", "+00:00")
                    ).astimezone(_BRT).replace(tzinfo=None)
                    cooldown_h = 1 if schedule == "hourly" else 23
                    if (now.replace(tzinfo=None) - last_fired).total_seconds() < cooldown_h * 3600:
                        continue
                except Exception:
                    pass

            try:
                fired = CustomAlertRunner._evaluate(
                    alert_type, contrato, condition_field, condition_op, condition_value, now
                )
            except Exception as exc:
                logger.error(f"[CustomAlertRunner] Erro ao avaliar '{alert_name}': {exc}")
                continue

            if not fired:
                continue

            # Notifica
            if notify_emails:
                try:
                    _color = "#C98B2A"
                    EmailService.send_alert_email(
                        recipients=list(notify_emails),
                        contract=contrato or "Todos",
                        alert_label=alert_name,
                        alert_color=_color,
                        obra_data={"projeto": description},
                    )
                except Exception as exc:
                    logger.error(f"[CustomAlertRunner] Erro ao enviar e-mail '{alert_name}': {exc}")

            # Loga no alert_history
            try:
                sb_insert(_TABLE_HIST, {
                    "alert_type": f"custom_{alert_type}",
                    "message": f"[{contrato or 'Todos'}] {alert_name}: {description}"[:500],
                    "is_read": False,
                })
            except Exception as exc:
                logger.warning(f"[CustomAlertRunner] Erro ao logar histórico '{alert_name}': {exc}")

            # Atualiza last_fired_at
            try:
                sb_update("custom_alerts", {"id": alert_id}, {"last_fired_at": now.isoformat()})
            except Exception:
                pass

        logger.info(f"[CustomAlertRunner] Ciclo '{schedule}' concluído ({len(rows)} alertas avaliados).")

    @staticmethod
    def _evaluate(
        alert_type: str,
        contrato: "str | None",
        condition_field: str,
        condition_op: str,
        condition_value: str,
        now: "datetime",
    ) -> bool:
        """
        Avalia se a condição do alerta foi atendida.
        Retorna True se deve disparar.
        """
        # ── rdo_ausente: nenhum RDO para o contrato nas últimas N horas ──────
        if alert_type == "rdo_ausente":
            hours = int(condition_value) if condition_value.isdigit() else 24
            filters: dict = {}
            if contrato:
                filters["contrato"] = contrato
            rows = sb_select("rdo_master", filters=filters, order="data.desc", limit=1) or []
            if not rows:
                return True  # nunca teve RDO → dispara
            last_str = str(rows[0].get("data", "") or rows[0].get("created_at", ""))
            try:
                if "T" in last_str:
                    last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00")).astimezone(_BRT)
                    last_dt = last_dt.replace(tzinfo=None)
                else:
                    last_dt = datetime.strptime(last_str[:10], "%Y-%m-%d")
                return (now.replace(tzinfo=None) - last_dt).total_seconds() > hours * 3600
            except Exception:
                return True

        # ── prazo_contrato: contrato vence em N dias ou menos ────────────────
        elif alert_type == "prazo_contrato":
            days_warn = int(condition_value) if condition_value.isdigit() else 7
            filters = {}
            if contrato:
                filters["contrato"] = contrato
            # condition_field indica a coluna de data (ex: 'data_fim', 'termino')
            col = condition_field or "termino"
            rows = sb_select("contratos", filters=filters, limit=200) or []
            for row in rows:
                val = str(row.get(col) or row.get("termino") or row.get("data_fim") or "")
                if not val:
                    continue
                try:
                    end_dt = datetime.strptime(val[:10], "%Y-%m-%d")
                    delta = (end_dt - now.replace(tzinfo=None)).days
                    if 0 <= delta <= days_warn:
                        return True
                except Exception:
                    continue
            return False

        # ── saldo_baixo: saldo orçamentário abaixo de N% ─────────────────────
        elif alert_type == "saldo_baixo":
            threshold = float(condition_value) if condition_value else 10.0
            filters = {}
            if contrato:
                filters["contrato"] = contrato
            col = condition_field or "saldo_percentual"
            rows = sb_select("fin_custos", filters=filters, limit=200) or []
            for row in rows:
                try:
                    val_str = str(row.get(col) or "").replace("%", "").replace(",", ".").strip()
                    if val_str and float(val_str) < threshold:
                        return True
                except Exception:
                    continue
            return False

        # ── medicao_pendente: última medição há mais de N dias ───────────────
        elif alert_type == "medicao_pendente":
            days = int(condition_value) if condition_value.isdigit() else 30
            filters = {}
            if contrato:
                filters["contrato"] = contrato
            col = condition_field or "data"
            rows = sb_select("fin_custos", filters=filters, order=f"{col}.desc", limit=1) or []
            if not rows:
                return True
            val = str(rows[0].get(col) or "")
            try:
                last_dt = datetime.strptime(val[:10], "%Y-%m-%d")
                return (now.replace(tzinfo=None) - last_dt).days >= days
            except Exception:
                return True

        # ── custom: avalia campo genérico com operador ───────────────────────
        elif alert_type == "custom" and condition_field and condition_op:
            table = "contratos"  # default — pode ser expandido
            filters = {}
            if contrato:
                filters["contrato"] = contrato
            rows = sb_select(table, filters=filters, limit=200) or []
            for row in rows:
                raw = str(row.get(condition_field) or "").replace("%", "").replace(",", ".").strip()
                if not raw:
                    if condition_op == "missing":
                        return True
                    continue
                try:
                    v = float(raw)
                    t = float(condition_value) if condition_value else 0.0
                    if condition_op == ">" and v > t:
                        return True
                    if condition_op == "<" and v < t:
                        return True
                    if condition_op == "=" and v == t:
                        return True
                    if condition_op == "overdue":
                        # condition_field é uma coluna de data — verifica se passou
                        end_dt = datetime.strptime(raw[:10], "%Y-%m-%d")
                        if now.replace(tzinfo=None) > end_dt:
                            return True
                except Exception:
                    pass
            return False

        # ── Tipo desconhecido — não dispara ──────────────────────────────────
        logger.warning(f"[CustomAlertRunner] Tipo desconhecido: {alert_type}")
        return False


# ── Background Scheduler ───────────────────────────────────────────────────────

_scheduler_started = False
_scheduler_lock = threading.Lock()
_last_daily: Any = None
_last_weekly: Any = None
_last_monthly: Any = None


def _already_fired_today(alert_type: str, brt_date_str: str) -> bool:
    """
    DB-level dedup: returns True if this alert_type already has an entry
    in alert_history for today (BRT). Prevents multi-worker duplicate fires.
    brt_date_str: YYYY-MM-DD in BRT.
    """
    try:
        import httpx
        from bomtempo.core.supabase_client import REST_BASE, _headers
        # BRT 00:00 = UTC 03:00 (BRT is UTC-3, so add 3h)
        brt_midnight_utc = f"{brt_date_str}T03:00:00"
        h = _headers()
        h["Prefer"] = "count=exact"
        h["Range"] = "0-0"
        resp = httpx.get(
            f"{REST_BASE}/{_TABLE_HIST}",
            headers=h,
            params={
                "select": "id",
                "alert_type": f"eq.{alert_type}",
                "timestamp": f"gte.{brt_midnight_utc}",
            },
            timeout=10,
        )
        cr = resp.headers.get("Content-Range", "")
        if "/" in cr:
            return int(cr.split("/")[1]) > 0
    except Exception as e:
        logger.warning(f"[_already_fired_today] {e}")
    return False


def _scheduler_loop() -> None:
    global _last_daily, _last_weekly, _last_monthly
    logger.info("[AlertScheduler] Background scheduler started — checking every 60s.")
    while True:
        try:
            now = datetime.now(_BRT)  # Always use explicit BRT timezone
            today = now.date()
            today_str = today.isoformat()
            this_week = now.isocalendar()[1]

            # Daily at 18h BRT — includes reactive checks + custom alerts
            if now.hour == 18 and now.minute < 5 and _last_daily != today:
                if not _already_fired_today("daily", today_str):
                    logger.info("[AlertScheduler] Firing daily+reactive sweeps.")
                    for at in ("daily", "risk_high", "budget_overage", "rdo_pending"):
                        AlertService.run_sweep(at)
                    CustomAlertRunner.run_due(schedule="daily", now=now)
                else:
                    logger.info("[AlertScheduler] Daily already fired today (DB check) — skip.")
                _last_daily = today  # Update in-process guard regardless

            # Custom alerts with hourly schedule — runs every loop iteration (60s)
            # We throttle by checking last_fired_at in the DB inside CustomAlertRunner
            if now.minute < 2:  # Only fire near the top of each hour
                CustomAlertRunner.run_due(schedule="hourly", now=now)

            # Weekly on Monday at 8h BRT
            if now.weekday() == 0 and now.hour == 8 and now.minute < 5 and _last_weekly != this_week:
                if not _already_fired_today("weekly", today_str):
                    logger.info("[AlertScheduler] Firing weekly sweep.")
                    AlertService.run_sweep("weekly")
                else:
                    logger.info("[AlertScheduler] Weekly already fired today (DB check) — skip.")
                _last_weekly = this_week

            # Monthly on day 25 at 9h BRT
            if now.day == 25 and now.hour == 9 and now.minute < 5:
                month_key = (now.year, now.month)
                if _last_monthly != month_key:
                    if not _already_fired_today("monthly", today_str):
                        logger.info("[AlertScheduler] Firing monthly sweep.")
                        AlertService.run_sweep("monthly")
                    else:
                        logger.info("[AlertScheduler] Monthly already fired today (DB check) — skip.")
                    _last_monthly = month_key

        except Exception as exc:
            logger.error(f"[AlertScheduler] Loop error: {exc}")
        time.sleep(60)


def start_alert_scheduler() -> None:
    """Start the background scheduler thread (idempotent)."""
    global _scheduler_started
    with _scheduler_lock:
        if not _scheduler_started:
            t = threading.Thread(target=_scheduler_loop, daemon=True, name="alert-scheduler")
            t.start()
            _scheduler_started = True
            logger.info("[AlertScheduler] Thread launched.")
