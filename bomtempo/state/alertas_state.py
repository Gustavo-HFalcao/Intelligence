"""
AlertasState — Bomtempo Intelligence
State management for the Proactive Alerts module.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import reflex as rx

from bomtempo.core.alert_service import ALERT_TYPES, AlertService
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.audit_logger import audit_log, AuditCategory
from bomtempo.core.executors import (
    get_ai_executor,
    get_db_executor,
    get_heavy_executor,
)

logger = get_logger(__name__)


# ── Typed models (required for rx.foreach over nested lists) ──────────────────

class EmailChip(rx.Base):
    email: str = ""
    id: str = ""


class SubscriptionGroup(rx.Base):
    alert_type: str = ""
    alert_label: str = ""
    alert_color: str = "#C98B2A"
    contract: str = ""
    is_active: bool = True
    key: str = ""
    email_chips: list[EmailChip] = []
    emails_display: str = ""
    count: str = "0"


_BRT = timezone(timedelta(hours=-3))  # Brasília Time (UTC-3)


def _utc_to_brt(ts: str) -> str:
    """Convert UTC ISO timestamp to BRT display string 'DD/MM HH:MM'."""
    if not ts or ts in ("—", ""):
        return ts
    try:
        ts_norm = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_norm[:32])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BRT).strftime("%d/%m %H:%M")
    except Exception:
        return ts[:16].replace("T", " ") if len(ts) >= 16 else ts


# ── Normalizers ───────────────────────────────────────────────────────────────

def _norm_group(g: dict) -> SubscriptionGroup:
    chips = [EmailChip(email=str(c["email"]), id=str(c["id"])) for c in g.get("email_chips", [])]
    return SubscriptionGroup(
        alert_type=str(g.get("alert_type", "")),
        alert_label=str(g.get("alert_label", "")),
        alert_color=str(g.get("alert_color", "#C98B2A")),
        contract=str(g.get("contract", "")),
        is_active=bool(g.get("is_active", True)),
        key=str(g.get("key", "")),
        email_chips=chips,
        emails_display=str(g.get("emails_display", "")),
        count=str(g.get("count", "0")),
    )


def _norm_hist(h: dict) -> dict:
    at = str(h.get("alert_type", "—"))
    ts = str(h.get("timestamp") or h.get("created_at") or "—")
    msg = str(h.get("message", "—"))
    # Contract is embedded in message as "[CT-XXX] ..." by _log_history
    contract = "—"
    if msg.startswith("[") and "]" in msg:
        contract = msg[1:msg.index("]")]
        msg = msg[msg.index("]") + 2:]
    return {
        "id": str(h.get("id", "")),
        "contract": contract,
        "alert_type": at,
        "alert_label": ALERT_TYPES.get(at, {}).get("label", at),
        "alert_color": ALERT_TYPES.get(at, {}).get("color", "#C98B2A"),
        "message": msg[:140],
        "is_read": bool(h.get("is_read", False)),
        "timestamp": _utc_to_brt(ts),
    }


class AlertasState(rx.State):
    # Data
    subscriptions: list[SubscriptionGroup] = []
    history: list[dict] = []
    subscription_counts: dict = {}  # {alert_type: n}

    # ── Tab navigation ────────────────────────────────────────────────────────
    active_tab: str = "regras"  # "regras" | "criar" | "historico"

    def set_active_tab(self, val: str):
        self.active_tab = val

    # ── Alert Rules Enterprise ─────────────────────────────────────────────────
    alert_rules: list[dict] = []        # regras da tabela alert_rules
    is_loading_rules: bool = False
    rule_form_message: str = ""
    rule_form_is_error: bool = False

    # ── Wizard de criação de regra ────────────────────────────────────────────
    wizard_open: bool = False
    wizard_step: int = 1                # 1=O que monitorar 2=Quando 3=Quem
    # Step 1 — O que monitorar
    wizard_category: str = "threshold"  # threshold | event | ai_custom
    wizard_metric: str = "desvio_prazo_pct"
    wizard_operator: str = "gt"
    wizard_threshold: str = "10"
    wizard_event_type: str = "rdo_submitted"
    wizard_natural_language: str = ""   # para ai_custom
    wizard_contracts: str = ""          # vazio = todos
    wizard_name: str = ""
    wizard_description: str = ""
    # Step 2 — Quando
    wizard_frequency: str = "always"    # once | always | daily | weekly | monthly
    wizard_cooldown_hours: str = "24"
    # Step 3 — Quem
    wizard_recipients: list[dict] = []  # [{email, name}]
    wizard_recipient_email: str = ""
    wizard_recipient_name: str = ""
    # IA interpretação da regra em linguagem natural
    ai_rule_interpretation: str = ""
    is_interpreting_rule: bool = False
    # Salvar
    is_saving_rule: bool = False

    # Form — add subscription (legado — mantido para compatibilidade)
    new_alert_type: str = "daily"
    new_contract: str = ""
    new_email: str = ""

    # UI feedback
    is_loading: bool = True
    is_adding: bool = False
    form_message: str = ""
    form_is_error: bool = False

    # Per-alert-type sweep results {alert_type: str}
    sweep_results: dict = {}
    sweep_running: bool = False
    sweep_running_type: str = ""   # which alert_type is currently running

    # Confirmation dialog
    confirm_sweep_type: str = ""   # non-empty = dialog open
    confirm_sweep_label: str = ""  # PT-BR label shown in the dialog

    # History pagination
    history_page: int = 1
    history_total: int = 0
    history_per_page: int = 30

    # ── Explicit setters ──────────────────────────────────────────────────────

    def set_new_alert_type(self, val: str): self.new_alert_type = val
    def set_new_contract(self, val: str): self.new_contract = val
    def set_new_email(self, val: str): self.new_email = val

    # ── Wizard setters ────────────────────────────────────────────────────────
    def set_wizard_category(self, val: str):
        self.wizard_category = val
        self.ai_rule_interpretation = ""
    def set_wizard_metric(self, val: str): self.wizard_metric = val
    def set_wizard_operator(self, val: str): self.wizard_operator = val
    def set_wizard_threshold(self, val: str): self.wizard_threshold = val
    def set_wizard_event_type(self, val: str): self.wizard_event_type = val
    def set_wizard_natural_language(self, val: str): self.wizard_natural_language = val
    def set_wizard_contracts(self, val: str): self.wizard_contracts = val
    def set_wizard_name(self, val: str): self.wizard_name = val
    def set_wizard_description(self, val: str): self.wizard_description = val
    def set_wizard_frequency(self, val: str): self.wizard_frequency = val
    def set_wizard_cooldown_hours(self, val: str): self.wizard_cooldown_hours = val
    def set_wizard_recipient_email(self, val: str): self.wizard_recipient_email = val
    def set_wizard_recipient_name(self, val: str): self.wizard_recipient_name = val

    def open_wizard(self):
        self.wizard_open = True
        self.wizard_step = 1
        self.wizard_name = ""
        self.wizard_description = ""
        self.wizard_natural_language = ""
        self.wizard_recipients = []
        self.wizard_recipient_email = ""
        self.ai_rule_interpretation = ""
        self.rule_form_message = ""

    def close_wizard(self):
        self.wizard_open = False

    def wizard_next(self):
        if self.wizard_step < 3:
            self.wizard_step += 1

    def wizard_prev(self):
        if self.wizard_step > 1:
            self.wizard_step -= 1

    def wizard_add_recipient(self):
        email = self.wizard_recipient_email.strip()
        name = self.wizard_recipient_name.strip()
        if email and "@" in email:
            existing = [r.get("email") for r in self.wizard_recipients]
            if email not in existing:
                self.wizard_recipients = list(self.wizard_recipients) + [
                    {"email": email, "name": name or email}
                ]
            self.wizard_recipient_email = ""
            self.wizard_recipient_name = ""

    def wizard_remove_recipient(self, email: str):
        self.wizard_recipients = [r for r in self.wizard_recipients if r.get("email") != email]

    def toggle_rule_active(self, rule_id: str):
        """Toggle is_active de uma regra localmente (atualiza no banco em bg)."""
        updated = []
        for r in self.alert_rules:
            if str(r.get("id")) == rule_id:
                updated.append({**r, "is_active": not r.get("is_active", True)})
            else:
                updated.append(r)
        self.alert_rules = updated

    # ── History pagination computed vars ──────────────────────────────────────

    @rx.var
    def history_total_pages(self) -> int:
        if self.history_total == 0:
            return 1
        return max(1, (self.history_total + self.history_per_page - 1) // self.history_per_page)

    @rx.var
    def active_rules_count(self) -> int:
        return sum(1 for r in self.alert_rules if r.get("is_active", True))

    @rx.var
    def history_has_prev(self) -> bool:
        return self.history_page > 1

    @rx.var
    def history_has_next(self) -> bool:
        return self.history_page < self.history_total_pages

    @rx.var
    def history_page_info(self) -> str:
        if self.history_total == 0:
            return "Nenhum disparo"
        start = (self.history_page - 1) * self.history_per_page + 1
        end = min(self.history_page * self.history_per_page, self.history_total)
        return f"{start}–{end} de {self.history_total}"

    def clear_type_sweep_result(self, alert_type: str):
        new_r = {**self.sweep_results}
        new_r.pop(alert_type, None)
        self.sweep_results = new_r

    # ── Confirmation dialog ───────────────────────────────────────────────────

    def open_confirm_sweep(self, alert_type: str):
        self.confirm_sweep_type = alert_type
        from bomtempo.core.alert_service import ALERT_TYPES as _AT
        self.confirm_sweep_label = _AT.get(alert_type, {}).get("label", alert_type)

    def cancel_confirm_sweep(self):
        self.confirm_sweep_type = ""
        self.confirm_sweep_label = ""

    # ── Load ─────────────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def load_page(self):
        async with self:
            self.is_loading = True
            self.form_message = ""
            self.sweep_results = {}
            self.history_page = 1

        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        try:
            # Busca subscriptions e histórico em paralelo — 2 requests simultâneas
            raw, (rows, total) = await asyncio.gather(
                loop.run_in_executor(get_db_executor(), lambda: AlertService.get_email_subscriptions(client_id=client_id)),
                loop.run_in_executor(get_db_executor(), lambda: AlertService.get_history(page=1, per_page=30, client_id=client_id)),
            )

            counts: dict = {k: 0 for k in ALERT_TYPES}
            for g in raw:
                at = g.get("alert_type", "")
                if at in counts:
                    counts[at] += len(g.get("email_chips", []))

            async with self:
                self.subscriptions = [_norm_group(g) for g in raw]
                self.subscription_counts = counts
                self.history = [_norm_hist(h) for h in rows]
                self.history_total = total
                self.is_loading = False

        except Exception as exc:
            logger.error(f"[AlertasState.load_page] {exc}")
            async with self:
                self.is_loading = False

    # ── History pagination ────────────────────────────────────────────────────

    @rx.event(background=True)
    async def history_prev(self):
        async with self:
            if self.history_page <= 1:
                return
            self.history_page -= 1
            page = self.history_page
        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass
        loop = asyncio.get_running_loop()
        try:
            rows, total = await loop.run_in_executor(
                get_db_executor(), lambda: AlertService.get_history(page=page, per_page=30, client_id=client_id)
            )
            async with self:
                self.history = [_norm_hist(h) for h in rows]
                self.history_total = total
        except Exception as e:
            logger.error(f"history_prev: {e}")

    @rx.event(background=True)
    async def history_next(self):
        async with self:
            if self.history_page >= self.history_total_pages:
                return
            self.history_page += 1
            page = self.history_page
        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass
        loop = asyncio.get_running_loop()
        try:
            rows, total = await loop.run_in_executor(
                get_db_executor(), lambda: AlertService.get_history(page=page, per_page=30, client_id=client_id)
            )
            async with self:
                self.history = [_norm_hist(h) for h in rows]
                self.history_total = total
        except Exception as e:
            logger.error(f"history_next: {e}")

    # ── Add subscription (async background) ──────────────────────────────────

    @rx.event(background=True)
    async def add_subscription(self):
        async with self:
            self.is_adding = True
            self.form_message = ""
            self.form_is_error = False
            # Snapshot form values before releasing the lock
            alert_type = self.new_alert_type
            contract = self.new_contract.strip()
            email = self.new_email.strip()

        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        try:
            ok, msg = await loop.run_in_executor(
                get_db_executor(),
                lambda: AlertService.add_email_subscription(
                    alert_type=alert_type,
                    contract=contract,
                    email=email,
                    created_by="admin",
                    client_id=client_id,
                ),
            )
        except Exception as e:
            logger.error(f"add_subscription executor: {e}")
            async with self:
                self.form_message = f"Erro ao salvar: {str(e)[:100]}"
                self.form_is_error = True
                self.is_adding = False
            return

        if ok:
            audit_log(
                category=AuditCategory.ALERT_CONFIG,
                action=f"Assinatura de alerta '{alert_type}' adicionada — email '{email}' contrato '{contract}'",
                metadata={"alert_type": alert_type, "email": email, "contract": contract},
                status="success",
                client_id=client_id,
            )

        async with self:
            self.form_message = msg
            self.form_is_error = not ok
            if ok:
                self.new_email = ""
                raw = AlertService.get_email_subscriptions(client_id=client_id)
                self.subscriptions = [_norm_group(g) for g in raw]
                counts: dict = {k: 0 for k in ALERT_TYPES}
                for g in raw:
                    at = g.get("alert_type", "")
                    if at in counts:
                        counts[at] += len(g.get("email_chips", []))
                self.subscription_counts = counts
            self.is_adding = False

    # ── Delete email chip ─────────────────────────────────────────────────────

    @rx.event(background=True)
    async def delete_email_chip(self, row_id: str):
        """Remove assinatura — I/O em executor para não bloquear event loop."""
        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass
        loop = asyncio.get_running_loop()
        try:
            # Delete + reload subscriptions em paralelo (delete primeiro, depois fetch)
            await loop.run_in_executor(get_db_executor(), AlertService.delete_email_subscription, row_id)
            audit_log(
                category=AuditCategory.ALERT_CONFIG,
                action=f"Assinatura de alerta removida — id '{row_id}'",
                entity_type="alert_subscriptions",
                entity_id=row_id,
                status="success",
                client_id=client_id,
            )
            raw = await loop.run_in_executor(get_db_executor(), lambda: AlertService.get_email_subscriptions(client_id=client_id))
            counts: dict = {k: 0 for k in ALERT_TYPES}
            for g in raw:
                at = g.get("alert_type", "")
                if at in counts:
                    counts[at] += len(g.get("email_chips", []))
            async with self:
                self.subscriptions = [_norm_group(g) for g in raw]
                self.subscription_counts = counts
        except Exception as exc:
            logger.error(f"[delete_email_chip] {exc}")

    # ── Manual sweep trigger ──────────────────────────────────────────────────

    @rx.event(background=True)
    async def confirm_and_sweep(self):
        """Called when user confirms the sweep dialog."""
        async with self:
            alert_type = self.confirm_sweep_type
            self.confirm_sweep_type = ""   # close dialog
            self.confirm_sweep_label = ""
            if not alert_type:
                return
            self.sweep_running = True
            self.sweep_running_type = alert_type
            new_r = {**self.sweep_results}
            new_r.pop(alert_type, None)
            self.sweep_results = new_r

        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(get_heavy_executor(), lambda: AlertService.run_sweep(alert_type))

        async with self:
            sent = result.get("sent", 0)
            errors = result.get("errors", 0)
            skipped = result.get("skipped", 0)
            if errors:
                msg = f"{sent} enviados, {errors} com erro, {skipped} sem gatilho."
            elif sent == 0 and skipped > 0:
                msg = f"Nenhum contrato ativou o gatilho ({skipped} verificados)."
            elif sent == 0:
                msg = f"Nenhum destinatário cadastrado para este alerta."
            else:
                msg = f"{sent} email(s) enviado(s) com sucesso."

            self.sweep_results = {**self.sweep_results, alert_type: msg}
            audit_log(
                category=AuditCategory.ALERT_TRIGGER,
                action=f"Alerta '{alert_type}' disparado manualmente — {msg}",
                entity_type="alert_history",
                metadata={"alert_type": alert_type, "sent": sent, "errors": errors, "skipped": skipped},
                status="success" if not errors else "warning",
                client_id=client_id,
            )
            self.history_page = 1
            self.sweep_running = False
            self.sweep_running_type = ""

        # Reload history after releasing state lock
        rows, total = await loop.run_in_executor(
            get_db_executor(), lambda: AlertService.get_history(page=1, per_page=30, client_id=client_id)
        )
        async with self:
            self.history = [_norm_hist(h) for h in rows]
            self.history_total = total

    # ── Load Alert Rules ──────────────────────────────────────────────────────

    @rx.event(background=True)
    async def load_alert_rules(self):
        """Carrega regras enterprise da tabela alert_rules."""
        async with self:
            self.is_loading_rules = True

        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.supabase_client import sb_select
            filters: dict = {"is_active": None}  # não filtrar por is_active — carrega tudo
            if client_id:
                filters = {"client_id": client_id}
            rules = await loop.run_in_executor(
                get_db_executor(), lambda: sb_select("alert_rules", filters={"client_id": client_id} if client_id else {}, limit=100)
            )
            normalized = []
            for r in (rules or []):
                normalized.append({
                    "id": str(r.get("id", "")),
                    "name": str(r.get("name", "—")),
                    "description": str(r.get("description", "")),
                    "category": str(r.get("category", "reativo")),
                    "trigger_type": str(r.get("trigger_type", "threshold")),
                    "trigger_config": r.get("trigger_config") or {},
                    "contracts": r.get("contracts") or [],
                    "recipients": r.get("recipients") or [],
                    "frequency": str(r.get("frequency", "always")),
                    "cooldown_hours": int(r.get("cooldown_hours") or 24),
                    "is_active": bool(r.get("is_active", True)),
                    "fire_count": int(r.get("fire_count") or 0),
                    "last_fired_at": str(r.get("last_fired_at") or "—"),
                    "color": str(r.get("color", "#C98B2A")),
                    "icon": str(r.get("icon", "bell")),
                    "recipients_count": str(len(r.get("recipients") or [])),
                })
            async with self:
                self.alert_rules = normalized
                self.is_loading_rules = False
        except Exception as exc:
            logger.error(f"[AlertasState.load_alert_rules] {exc}")
            async with self:
                self.is_loading_rules = False

    # ── Interpret AI Custom Rule ───────────────────────────────────────────────

    @rx.event(background=True)
    async def interpret_ai_rule(self):
        """
        IA interpreta o texto em linguagem natural e gera a configuração da regra.
        Mostra preview ao usuário (HITL) antes de salvar.
        """
        async with self:
            nl_input = self.wizard_natural_language.strip()
            if not nl_input:
                return
            self.is_interpreting_rule = True
            self.ai_rule_interpretation = ""

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.ai_client import ai_client

            available_metrics = "\n".join([
                "- desvio_prazo_pct: % de desvio do prazo (positivo = atrasado)",
                "- budget_overage_pct: % de estouro orçamentário",
                "- risk_score: score de risco 0-100",
                "- rdo_horas_sem_submit: horas desde o último RDO",
                "- producao_queda_pct: queda % de produção vs média 7 dias",
            ])

            prompt = (
                f"O usuário quer criar um alerta com esta descrição:\n"
                f"\"{nl_input}\"\n\n"
                f"Métricas disponíveis:\n{available_metrics}\n\n"
                f"Responda em JSON com EXATAMENTE esta estrutura (sem markdown, sem explicação):\n"
                f'{{"name": "nome curto do alerta", '
                f'"description": "descrição em 1 frase", '
                f'"metric": "nome_da_metrica", '
                f'"operator": "gt|gte|lt|lte|eq", '
                f'"threshold": numero, '
                f'"frequency": "once|always|daily", '
                f'"interpretation": "explique em 2 frases o que este alerta vai monitorar"}}'
            )

            resp = await loop.run_in_executor(
                get_ai_executor(), lambda: ai_client.query([{"role": "user", "content": prompt}], max_tokens=400)
            )

            import json, re
            json_match = re.search(r'\{[\s\S]*\}', resp or "")
            if json_match:
                parsed = json.loads(json_match.group())
                interpretation = parsed.get("interpretation", "Regra criada com base na sua descrição.")
                # Preenche os campos do wizard automaticamente
                async with self:
                    self.wizard_name = parsed.get("name", self.wizard_name or "Alerta personalizado")
                    self.wizard_description = parsed.get("description", "")
                    self.wizard_metric = parsed.get("metric", "desvio_prazo_pct")
                    self.wizard_operator = parsed.get("operator", "gt")
                    self.wizard_threshold = str(parsed.get("threshold", "10"))
                    self.wizard_frequency = parsed.get("frequency", "always")
                    self.ai_rule_interpretation = interpretation
                    self.is_interpreting_rule = False
            else:
                async with self:
                    self.ai_rule_interpretation = "Não consegui interpretar. Preencha manualmente os campos abaixo."
                    self.is_interpreting_rule = False
        except Exception as exc:
            logger.error(f"[interpret_ai_rule] {exc}")
            async with self:
                self.ai_rule_interpretation = f"Erro: {str(exc)[:100]}. Preencha manualmente."
                self.is_interpreting_rule = False

    # ── Save Alert Rule ────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def save_alert_rule(self):
        """Salva a regra configurada no wizard na tabela alert_rules."""
        async with self:
            self.is_saving_rule = True
            self.rule_form_message = ""
            self.rule_form_is_error = False
            # Snapshot
            category = self.wizard_category
            metric = self.wizard_metric
            operator = self.wizard_operator
            threshold = self.wizard_threshold
            event_type = self.wizard_event_type
            natural_language = self.wizard_natural_language
            contracts_str = self.wizard_contracts.strip()
            name = self.wizard_name.strip() or "Alerta personalizado"
            description = self.wizard_description.strip()
            frequency = self.wizard_frequency
            cooldown_hours = int(self.wizard_cooldown_hours or 24)
            recipients = list(self.wizard_recipients)

        client_id = ""
        current_user = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
            current_user = str(_gs.current_user_name or "admin")
        except Exception:
            pass

        # Monta trigger_config baseado na categoria
        if category == "threshold":
            trigger_type = "threshold"
            trigger_config = {
                "metric": metric,
                "operator": operator,
                "value": float(threshold) if threshold else 10.0,
            }
        elif category == "event":
            trigger_type = "event"
            trigger_config = {"event": event_type}
        else:  # ai_custom
            trigger_type = "ai_custom"
            trigger_config = {
                "metric": metric,
                "operator": operator,
                "value": float(threshold) if threshold else 10.0,
                "natural_language": natural_language,
            }

        contracts = [c.strip() for c in contracts_str.split(",") if c.strip()] if contracts_str else []

        record = {
            "name": name,
            "description": description,
            "category": "ia_personalizado" if category == "ai_custom" else "reativo",
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "contracts": contracts,
            "recipients": recipients,
            "frequency": frequency,
            "cooldown_hours": cooldown_hours,
            "is_active": True,
            "created_by": current_user,
            "natural_language_input": natural_language or None,
        }
        if client_id:
            record["client_id"] = client_id

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.supabase_client import sb_insert
            result = await loop.run_in_executor(get_db_executor(), lambda: sb_insert("alert_rules", record))

            audit_log(
                category=AuditCategory.ALERT_CONFIG,
                action=f"Regra de alerta criada: '{name}'",
                metadata={"trigger_type": trigger_type, "category": category, "recipients_count": len(recipients)},
                status="success",
                client_id=client_id,
            )

            # Recarrega lista de regras
            await self.load_alert_rules()

            async with self:
                self.wizard_open = False
                self.rule_form_message = f"Alerta '{name}' criado com sucesso!"
                self.rule_form_is_error = False
                self.is_saving_rule = False
        except Exception as exc:
            logger.error(f"[save_alert_rule] {exc}")
            async with self:
                self.rule_form_message = f"Erro ao salvar: {str(exc)[:150]}"
                self.rule_form_is_error = True
                self.is_saving_rule = False

    # ── Delete Alert Rule ──────────────────────────────────────────────────────

    @rx.event(background=True)
    async def delete_alert_rule(self, rule_id: str):
        """Remove uma regra da tabela alert_rules."""
        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.supabase_client import sb_delete
            await loop.run_in_executor(get_db_executor(), lambda: sb_delete("alert_rules", filters={"id": rule_id}))
            audit_log(
                category=AuditCategory.ALERT_CONFIG,
                action=f"Regra de alerta removida — id '{rule_id}'",
                entity_type="alert_rules",
                entity_id=rule_id,
                status="success",
                client_id=client_id,
            )
            await self.load_alert_rules()
        except Exception as exc:
            logger.error(f"[delete_alert_rule] {exc}")

    # ── Toggle Rule Active ────────────────────────────────────────────────────

    @rx.event(background=True)
    async def toggle_rule_active_db(self, rule_id: str):
        """Alterna is_active de uma regra no banco."""
        # Encontra o estado atual
        current_active = True
        async with self:
            for r in self.alert_rules:
                if str(r.get("id")) == rule_id:
                    current_active = bool(r.get("is_active", True))
                    break
            # Otimistic update
            self.toggle_rule_active(rule_id)

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.supabase_client import sb_update
            await loop.run_in_executor(
                get_db_executor(),
                lambda: sb_update("alert_rules", filters={"id": rule_id}, data={"is_active": not current_active})
            )
        except Exception as exc:
            logger.error(f"[toggle_rule_active_db] {exc}")
            # Reverte o otimistic update em caso de erro
            async with self:
                self.toggle_rule_active(rule_id)

    # ── Run Rule Sweep ────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def run_rules_sweep(self):
        """Varre todas as regras threshold ativas via AlertEngine."""
        async with self:
            self.sweep_running = True
            self.sweep_running_type = "rules_sweep"

        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        try:
            from bomtempo.core.alert_engine import AlertEngine
            result = await loop.run_in_executor(
                None, lambda: AlertEngine.run_sweep(client_id=client_id)
            )
            sent = result.get("sent", 0)
            errors = result.get("errors", 0)
            skipped = result.get("skipped", 0)
            msg = f"{sent} alerta(s) disparado(s), {skipped} sem gatilho, {errors} erro(s)."
            async with self:
                self.sweep_results = {**self.sweep_results, "rules_sweep": msg}
                self.sweep_running = False
                self.sweep_running_type = ""
        except Exception as exc:
            logger.error(f"[run_rules_sweep] {exc}")
            async with self:
                self.sweep_running = False
                self.sweep_running_type = ""
