"""
O&M State — Gestão de Gerações
CRUD para a tabela om_geracoes no Supabase.
"""
import re
from typing import Any, Dict, List, Optional

import reflex as rx

from bomtempo.core.audit_logger import AuditCategory, audit_log
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_delete, sb_insert, sb_select, sb_update

logger = get_logger(__name__)

# Contratos fixos disponíveis no módulo O&M
OM_CONTRATO_OPTIONS: List[str] = []  # Populated dynamically from GlobalState


def _fmt_brl_input(val: str) -> str:
    """Formata número digitado livremente para BRL.

    Regras de interpretação:
      '1400'       → '1.400,00'   (inteiro puro)
      '1400,5'     → '1.400,50'   (vírgula = decimal, padrão BR)
      '1400,50'    → '1.400,50'
      '1400.5'     → '1.400,50'   (ponto = decimal, aceito também)
      '1.400,50'   → '1.400,50'   (já formatado, apenas reprocessa)
      '1,400.50'   → '1.400,50'   (formato anglo, raro mas tratado)
    """
    if not val:
        return ""
    s = val.strip()

    dot_count   = s.count(".")
    comma_count = s.count(",")

    if comma_count == 1 and dot_count == 0:
        # Caso BR mais comum: "1400,5" ou "1400,50"
        s = s.replace(",", ".")
    elif dot_count == 1 and comma_count == 0:
        # Ponto como decimal: "1400.5" — mantém como está
        pass
    elif comma_count >= 1 and dot_count >= 1:
        # Misto: descobre qual é milhar e qual é decimal pelo último separador
        last_dot   = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            # Vírgula é decimal: "1.400,50" → BR padrão
            s = s.replace(".", "").replace(",", ".")
        else:
            # Ponto é decimal: "1,400.50" → anglo
            s = s.replace(",", "")
    else:
        # Múltiplos pontos ou múltiplas vírgulas — remove tudo, trata como inteiro
        s = re.sub(r"[^\d]", "", s)

    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return ""
    try:
        n = float(s)
        return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return val


def _parse_brl_input(val: str) -> float:
    """Converte valor BRL formatado de volta para float."""
    if not val:
        return 0.0
    s = re.sub(r"[^\d,.]", "", val)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


class OmState(rx.State):
    """Estado dedicado ao módulo O&M — lista de gerações + CRUD."""

    # ── Tab navigation ─────────────────────────────────────────────────────────
    om_tab: str = "dashboard"  # "dashboard" | "gestao"

    # ── List of generation records ─────────────────────────────────────────────
    geracoes_list: List[Dict[str, str]] = []
    geracoes_loading: bool = False

    # ── Edit / New dialog ──────────────────────────────────────────────────────
    show_dialog: bool = False
    edit_id: str = ""           # "" = novo registro

    # Form fields
    edit_contrato: str = ""
    edit_cliente: str = ""
    edit_localizacao: str = ""
    edit_data_referencia: str = ""          # ISO date string "YYYY-MM-DD"
    edit_geracao_prevista: str = ""         # BRL formatted
    edit_energia_injetada: str = ""         # BRL formatted
    edit_compensado: str = ""               # BRL formatted
    edit_valor_faturado: str = ""           # BRL formatted
    edit_gestao: str = ""                   # BRL formatted
    edit_faturamento_liquido: str = ""      # BRL formatted
    edit_observacoes: str = ""

    saving: bool = False
    dialog_error: str = ""

    # ── Delete confirm ─────────────────────────────────────────────────────────
    show_delete: bool = False
    delete_id: str = ""
    delete_label: str = ""

    # ── Contratos dropdown options (populated from GlobalState) ────────────────
    contrato_options: List[str] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Tab navigation
    # ──────────────────────────────────────────────────────────────────────────

    def set_om_tab(self, tab: str):
        self.om_tab = tab

    # ──────────────────────────────────────────────────────────────────────────
    # Load page: pull contrato options + geracoes
    # ──────────────────────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def load_page(self):
        """Carrega opções de contrato e registros de geração."""
        from bomtempo.state.global_state import GlobalState

        client_id = ""
        async with self:
            self.geracoes_loading = True

        # Read client_id from GlobalState
        try:
            gs = await self.get_state(GlobalState)
            client_id = str(gs.current_client_id or "")
        except Exception as e:
            logger.error(f"OmState.load_page get GlobalState: {e}")

        # Fetch contrato options from contratos table
        contrato_opts = [""]
        try:
            if client_id:
                contratos = sb_select("contratos", filters={"client_id": client_id}, order="contrato.asc")
            else:
                contratos = sb_select("contratos", order="contrato.asc")
            seen = set()
            for c in contratos:
                code = str(c.get("contrato", "") or "")
                if code and code not in seen:
                    seen.add(code)
                    contrato_opts.append(code)
        except Exception as e:
            logger.error(f"OmState load contratos: {e}")

        # Fetch geracoes
        rows: List[Dict] = []
        try:
            if client_id:
                rows = sb_select(
                    "om_geracoes",
                    filters={"client_id": client_id},
                    order="data_referencia.desc",
                    limit=500,
                )
            else:
                rows = sb_select("om_geracoes", order="data_referencia.desc", limit=500)
        except Exception as e:
            logger.error(f"OmState load om_geracoes: {e}")

        # Normalize to strings for Reflex foreach
        normalized = []
        for r in rows:
            normalized.append({
                "id": str(r.get("id", "") or ""),
                "contrato": str(r.get("contrato", "") or ""),
                "cliente": str(r.get("cliente", "") or ""),
                "localizacao": str(r.get("localizacao", "") or ""),
                "data_referencia": str(r.get("data_referencia", "") or ""),
                "geracao_prevista_kwh": str(r.get("geracao_prevista_kwh", 0) or 0),
                "energia_injetada_kwh": str(r.get("energia_injetada_kwh", 0) or 0),
                "compensado_kwh": str(r.get("compensado_kwh", 0) or 0),
                "valor_faturado": str(r.get("valor_faturado", 0) or 0),
                "gestao": str(r.get("gestao", 0) or 0),
                "faturamento_liquido": str(r.get("faturamento_liquido", 0) or 0),
                "observacoes": str(r.get("observacoes", "") or ""),
            })

        async with self:
            self.contrato_options = contrato_opts
            self.geracoes_list = normalized
            self.geracoes_loading = False

    # ──────────────────────────────────────────────────────────────────────────
    # Dialog open/close
    # ──────────────────────────────────────────────────────────────────────────

    def open_new(self):
        """Abre dialog para novo registro."""
        self.edit_id = ""
        self.edit_contrato = ""
        self.edit_cliente = ""
        self.edit_localizacao = ""
        self.edit_data_referencia = ""
        self.edit_geracao_prevista = ""
        self.edit_energia_injetada = ""
        self.edit_compensado = ""
        self.edit_valor_faturado = ""
        self.edit_gestao = ""
        self.edit_faturamento_liquido = ""
        self.edit_observacoes = ""
        self.dialog_error = ""
        self.show_dialog = True

    def open_edit(self, row_id: str):
        """Abre dialog preenchido com dados do registro."""
        row = next((r for r in self.geracoes_list if r["id"] == row_id), None)
        if not row:
            return
        self.edit_id = row_id
        self.edit_contrato = row.get("contrato", "")
        self.edit_cliente = row.get("cliente", "")
        self.edit_localizacao = row.get("localizacao", "")
        self.edit_data_referencia = row.get("data_referencia", "")
        # Format numerics back to BRL display
        def _fmt(v: str) -> str:
            try:
                f = float(v or 0)
                return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return v
        self.edit_geracao_prevista = _fmt(row.get("geracao_prevista_kwh", "0"))
        self.edit_energia_injetada = _fmt(row.get("energia_injetada_kwh", "0"))
        self.edit_compensado = _fmt(row.get("compensado_kwh", "0"))
        self.edit_valor_faturado = _fmt(row.get("valor_faturado", "0"))
        self.edit_gestao = _fmt(row.get("gestao", "0"))
        self.edit_faturamento_liquido = _fmt(row.get("faturamento_liquido", "0"))
        self.edit_observacoes = row.get("observacoes", "")
        self.dialog_error = ""
        self.show_dialog = True

    def close_dialog(self):
        self.show_dialog = False

    def set_show_dialog(self, v: bool):
        self.show_dialog = v

    # ── Field setters (on_blur for text to avoid per-keystroke lag) ────────────

    def set_edit_contrato(self, v: str):
        self.edit_contrato = v if v != "__none__" else ""

    def set_edit_cliente(self, v: str):
        self.edit_cliente = v

    def set_edit_localizacao(self, v: str):
        self.edit_localizacao = v

    def set_edit_data_referencia(self, v: str):
        self.edit_data_referencia = v

    def on_blur_geracao_prevista(self, v: str):
        self.edit_geracao_prevista = _fmt_brl_input(v)

    def on_blur_energia_injetada(self, v: str):
        self.edit_energia_injetada = _fmt_brl_input(v)

    def on_blur_compensado(self, v: str):
        self.edit_compensado = _fmt_brl_input(v)

    def on_blur_valor_faturado(self, v: str):
        self.edit_valor_faturado = _fmt_brl_input(v)
        self._recalc_fat_liquido()

    def on_blur_gestao(self, v: str):
        self.edit_gestao = _fmt_brl_input(v)
        self._recalc_fat_liquido()

    def _recalc_fat_liquido(self):
        """Fat. Líquido = Valor Faturado - Gestão (calculado automaticamente)."""
        fat = _parse_brl_input(self.edit_valor_faturado)
        ges = _parse_brl_input(self.edit_gestao)
        liq = fat - ges
        self.edit_faturamento_liquido = _fmt_brl_input(str(liq)) if liq != 0 else ""

    def set_edit_observacoes(self, v: str):
        self.edit_observacoes = v

    # ──────────────────────────────────────────────────────────────────────────
    # Save (INSERT or UPDATE)
    # ──────────────────────────────────────────────────────────────────────────

    @rx.event(background=True)
    async def save_geracao(self):
        """Salva registro de geração (INSERT ou UPDATE)."""
        from bomtempo.state.global_state import GlobalState

        # Step 1: Validate + read state inside lock
        edit_id = ""
        contrato = ""
        cliente = ""
        localizacao = ""
        data_ref = ""
        geracao_prev = 0.0
        energia_inj = 0.0
        compensado = 0.0
        valor_fat = 0.0
        gestao = 0.0
        fat_liq = 0.0
        observacoes = ""
        client_id = ""
        username = ""

        async with self:
            if not self.edit_contrato.strip():
                self.dialog_error = "Contrato é obrigatório."
                return
            if not self.edit_data_referencia.strip():
                self.dialog_error = "Data de referência é obrigatória."
                return

            self.saving = True
            self.dialog_error = ""

            edit_id = self.edit_id
            contrato = self.edit_contrato.strip()
            cliente = self.edit_cliente.strip()
            localizacao = self.edit_localizacao.strip()
            data_ref = self.edit_data_referencia.strip()
            geracao_prev = _parse_brl_input(self.edit_geracao_prevista)
            energia_inj = _parse_brl_input(self.edit_energia_injetada)
            compensado = _parse_brl_input(self.edit_compensado)
            valor_fat = _parse_brl_input(self.edit_valor_faturado)
            gestao = _parse_brl_input(self.edit_gestao)
            fat_liq = _parse_brl_input(self.edit_faturamento_liquido)
            observacoes = self.edit_observacoes.strip()

        # Read GlobalState outside lock to avoid deadlock
        try:
            gs = await self.get_state(GlobalState)
            client_id = str(gs.current_client_id or "")
            username = str(gs.current_user_name or "")
        except Exception as e:
            logger.error(f"OmState.save_geracao get GlobalState: {e}")

        # Step 2: I/O outside lock
        try:
            record: Dict[str, Any] = {
                "contrato": contrato,
                "cliente": cliente,
                "localizacao": localizacao,
                "data_referencia": data_ref,
                "geracao_prevista_kwh": geracao_prev,
                "energia_injetada_kwh": energia_inj,
                "compensado_kwh": compensado,
                "valor_faturado": valor_fat,
                "gestao": gestao,
                "faturamento_liquido": fat_liq,
                "observacoes": observacoes,
            }
            if client_id:
                record["client_id"] = client_id

            if edit_id:
                sb_update("om_geracoes", filters={"id": edit_id}, data=record)
                action = f"Geração O&M atualizada — {contrato} {data_ref}"
            else:
                sb_insert("om_geracoes", record)
                action = f"Geração O&M criada — {contrato} {data_ref}"

            audit_log(
                category=AuditCategory.DATA_EDIT,
                action=action,
                username=username,
                entity_type="om_geracoes",
                entity_id=edit_id or "new",
                metadata={"contrato": contrato, "data_referencia": data_ref},
                client_id=client_id,
            )
        except Exception as e:
            logger.error(f"OmState.save_geracao error: {e}")
            async with self:
                self.dialog_error = f"Erro ao salvar: {str(e)[:120]}"
                self.saving = False
            return

        # Step 3: close dialog + reload
        async with self:
            self.show_dialog = False
            self.saving = False

        yield OmState.load_page

    # ──────────────────────────────────────────────────────────────────────────
    # Delete
    # ──────────────────────────────────────────────────────────────────────────

    def request_delete(self, row_id: str):
        """Solicita confirmação de deleção."""
        row = next((r for r in self.geracoes_list if r["id"] == row_id), None)
        self.delete_id = row_id
        if row:
            label = f"{row.get('contrato','')} — {row.get('data_referencia','')}"
        else:
            label = row_id
        self.delete_label = label
        self.show_delete = True

    def cancel_delete(self):
        self.delete_id = ""
        self.show_delete = False

    @rx.event(background=True)
    async def confirm_delete(self):
        """Executa deleção após confirmação."""
        from bomtempo.state.global_state import GlobalState

        row_id = ""
        label = ""
        client_id = ""
        username = ""

        async with self:
            row_id = str(self.delete_id)
            label = str(self.delete_label)
            self.show_delete = False
            self.delete_id = ""

        try:
            gs = await self.get_state(GlobalState)
            client_id = str(gs.current_client_id or "")
            username = str(gs.current_user_name or "")
        except Exception as e:
            logger.error(f"OmState.confirm_delete get GlobalState: {e}")

        try:
            sb_delete("om_geracoes", filters={"id": row_id})
            audit_log(
                category=AuditCategory.DATA_DELETE,
                action=f"Geração O&M excluída — {label}",
                username=username,
                entity_type="om_geracoes",
                entity_id=row_id,
                client_id=client_id,
            )
        except Exception as e:
            logger.error(f"OmState.confirm_delete error: {e}")

        yield OmState.load_page
