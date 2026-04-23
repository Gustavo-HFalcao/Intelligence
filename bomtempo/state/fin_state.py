"""
FinState — State for Financeiro por Projeto tab (Feature #21)
Manages CRUD for fin_custos, KPI cards, S-curve and categoria chart.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

import reflex as rx

from bomtempo.core.fin_service import FinService
from bomtempo.core.supabase_client import sb_select

logger = logging.getLogger(__name__)


def _fmt_brl_input(v: Any) -> str:
    """Format a value as BRL for display inside an input field (no R$ prefix).
    Output: 1234.56 → '1.234,56'
    """
    from bomtempo.core.fin_service import _parse_float
    num = _parse_float(v)
    if num == 0:
        return ""
    # Use TEMP placeholder to avoid double-replacement of separators
    s = f"{num:_.2f}"          # "1_234.56"
    s = s.replace(".", "DECPT")  # "1_234DECPT56"
    s = s.replace("_", ".")      # "1.234DECPT56"
    s = s.replace("DECPT", ",")  # "1.234,56"
    return s


# Status options for custo
FIN_STATUS_OPTIONS = ["previsto", "em_andamento", "parcial", "concluido", "executado", "cancelado"]
FIN_STATUS_LABELS = {
    "previsto":     "Previsto",
    "em_andamento": "Em Andamento",
    "parcial":      "Parcial",
    "concluido":    "Concluído",
    "executado":    "Executado",
    "cancelado":    "Cancelado",
}


class FinState(rx.State):
    """State for the Financeiro tab inside Hub de Operações."""

    # ── Loading ───────────────────────────────────────────────────────────────
    fin_loading: bool = False
    fin_saving: bool = False
    fin_error: str = ""

    # ── Data ─────────────────────────────────────────────────────────────────
    fin_contrato: str = ""          # current contract (set when tab activates)
    fin_custos: List[Dict[str, str]] = []
    fin_categorias: List[Dict[str, str]] = []

    # ── KPIs ─────────────────────────────────────────────────────────────────
    fin_kpis: Dict[str, str] = {
        "total_previsto":  "R$ 0,00",
        "total_executado": "R$ 0,00",
        "saldo":           "R$ 0,00",
        "pct_executado":   "0.0",
        "total_itens":     "0",
        "concluidos":      "0",
    }

    # ── Charts ───────────────────────────────────────────────────────────────
    fin_scurve: List[Dict[str, str]] = []
    fin_by_cat: List[Dict[str, str]] = []

    # ── Filter ───────────────────────────────────────────────────────────────
    fin_filter_status: str = ""
    fin_filter_categoria: str = ""
    fin_search: str = ""
    fin_search_input: str = ""

    # ── New/Edit dialog ───────────────────────────────────────────────────────
    fin_show_dialog: bool = False
    fin_edit_id: str = ""           # empty = new
    fin_edit_categoria_id: str = ""
    fin_edit_categoria_nome: str = ""
    fin_edit_empresa: str = ""
    fin_edit_descricao: str = ""
    fin_edit_valor_previsto: str = ""
    fin_edit_valor_executado: str = ""
    fin_edit_status: str = "previsto"
    fin_edit_data: str = ""
    fin_edit_atividade_id: str = ""
    fin_edit_observacoes: str = ""

    # ── EVM Forecast ──────────────────────────────────────────────────────────
    fin_forecast: Dict[str, str] = {}
    fin_avg_activity_pct: float = 0.0

    # ── Delete confirm ────────────────────────────────────────────────────────
    fin_show_delete: bool = False
    fin_delete_id: str = ""
    fin_delete_desc: str = ""

    # ── Activity options (from hub_atividades for this contract) ─────────────
    fin_atividade_options: List[Dict[str, str]] = []

    # ── Tenant context (cached at load time to avoid cross-state reads in save) ─
    _fin_client_id: str = ""

    # ═════════════════════════════════════════════════════════════════════════
    # Computed vars
    # ═════════════════════════════════════════════════════════════════════════

    @rx.var
    def filtered_custos(self) -> List[Dict[str, str]]:
        rows = self.fin_custos
        if self.fin_filter_status:
            rows = [r for r in rows if r.get("status") == self.fin_filter_status]
        if self.fin_filter_categoria:
            rows = [r for r in rows if r.get("categoria_nome") == self.fin_filter_categoria]
        if self.fin_search:
            q = self.fin_search.lower()
            rows = [
                r for r in rows
                if q in r.get("descricao", "").lower()
                or q in r.get("categoria_nome", "").lower()
            ]
        return rows

    @rx.var
    def fin_categoria_options(self) -> List[str]:
        """Unique categoria names for filter dropdown."""
        seen = []
        for r in self.fin_custos:
            n = r.get("categoria_nome", "")
            if n and n not in seen:
                seen.append(n)
        return seen

    @rx.var
    def fin_dialog_title(self) -> str:
        return "Editar Custo" if self.fin_edit_id else "Novo Custo"

    # ═════════════════════════════════════════════════════════════════════════
    # Load
    # ═════════════════════════════════════════════════════════════════════════

    @rx.event(background=True)
    async def load_financeiro(self, contrato: str):
        async with self:
            self.fin_loading = True
            self.fin_custos = []
            self.fin_kpis = {}
            self.fin_scurve = []
            self.fin_by_cat = []
            self.fin_contrato = contrato
            self.fin_filter_status = ""
            self.fin_filter_categoria = ""
            self.fin_search = ""
            self.fin_search_input = ""
            # Cache client_id at load time so save_fin_custo doesn't need cross-state reads
            try:
                from bomtempo.state.global_state import GlobalState
                gs = await self.get_state(GlobalState)
                self._fin_client_id = str(gs.current_client_id or "")
            except Exception:
                pass

        try:
            # Load categorias (once, small table)
            cats = FinService.load_categorias()
            # Load custos for this contract
            custos = FinService.load_custos(contrato)
            # Load atividades for dropdown + avg completion
            avg_pct = 0.0
            try:
                ativ_rows = sb_select(
                    "hub_atividades",
                    filters={"contrato": contrato},
                    order="fase_macro.asc,atividade.asc",
                    limit=300,
                )
                ativ_opts = [
                    {"id": str(r.get("id", "")), "label": str(r.get("atividade", ""))}
                    for r in (ativ_rows or [])
                ]
                if ativ_rows:
                    pcts = [float(r.get("conclusao_pct", 0) or 0) for r in ativ_rows]
                    avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
            except Exception:
                ativ_opts = []

            kpis = FinService.compute_kpis(custos)
            scurve = FinService.compute_scurve(custos)
            by_cat = FinService.compute_by_categoria(custos)
            forecast = FinService.compute_evm(custos, avg_pct)

        except Exception as e:
            logger.error(f"load_financeiro error: {e}")
            cats, custos, ativ_opts, kpis, scurve, by_cat, forecast, avg_pct = [], [], [], {}, [], [], {}, 0.0

        async with self:
            self.fin_categorias = cats
            self.fin_custos = custos
            self.fin_atividade_options = ativ_opts
            self.fin_kpis = kpis
            self.fin_scurve = scurve
            self.fin_by_cat = by_cat
            self.fin_forecast = forecast
            self.fin_avg_activity_pct = avg_pct
            self.fin_loading = False

    def _refresh_charts(self):
        """Recompute KPIs + charts + forecast from current fin_custos. Call after mutations."""
        self.fin_kpis = FinService.compute_kpis(self.fin_custos)
        self.fin_scurve = FinService.compute_scurve(self.fin_custos)
        self.fin_by_cat = FinService.compute_by_categoria(self.fin_custos)
        self.fin_forecast = FinService.compute_evm(self.fin_custos, self.fin_avg_activity_pct)

    # ═════════════════════════════════════════════════════════════════════════
    # Dialog open/close
    # ═════════════════════════════════════════════════════════════════════════

    def open_fin_new(self):
        self.fin_edit_id = ""
        self.fin_edit_categoria_id = ""
        self.fin_edit_categoria_nome = ""
        self.fin_edit_empresa = ""
        self.fin_edit_descricao = ""
        self.fin_edit_valor_previsto = ""
        self.fin_edit_valor_executado = ""
        self.fin_edit_status = "previsto"
        self.fin_edit_data = ""
        self.fin_edit_atividade_id = ""
        self.fin_edit_observacoes = ""
        self.fin_error = ""
        self.fin_show_dialog = True

    def open_fin_edit(self, custo_id: str):
        row = next((r for r in self.fin_custos if r.get("id") == custo_id), None)
        if not row:
            return
        self.fin_edit_id = custo_id
        self.fin_edit_categoria_id = row.get("categoria_id", "")
        self.fin_edit_categoria_nome = row.get("categoria_nome", "")
        self.fin_edit_empresa = row.get("empresa", "")
        self.fin_edit_descricao = row.get("descricao", "")
        self.fin_edit_valor_previsto = _fmt_brl_input(row.get("valor_previsto", "0"))
        self.fin_edit_valor_executado = _fmt_brl_input(row.get("valor_executado", "0"))
        self.fin_edit_status = row.get("status", "previsto")
        self.fin_edit_data = row.get("data_custo", "")
        self.fin_edit_atividade_id = row.get("atividade_id", "")
        self.fin_edit_observacoes = row.get("observacoes", "")
        self.fin_error = ""
        self.fin_show_dialog = True

    def close_fin_dialog(self):
        self.fin_show_dialog = False

    def set_fin_show_dialog(self, v: bool):
        self.fin_show_dialog = v

    # ═════════════════════════════════════════════════════════════════════════
    # Field setters for dialog
    # ═════════════════════════════════════════════════════════════════════════

    def set_fin_edit_categoria_by_name(self, v: str):
        """Called when user types/selects a category name (combobox).
        Resolves the ID if an existing category matches; otherwise leaves ID empty
        so save_fin_custo will create the category automatically."""
        self.fin_edit_categoria_nome = v
        cat = next(
            (c for c in self.fin_categorias if c.get("nome", "").lower() == v.strip().lower()),
            None,
        )
        self.fin_edit_categoria_id = cat["id"] if cat else ""

    def set_fin_edit_empresa(self, v: str):
        self.fin_edit_empresa = v

    def set_fin_edit_descricao(self, v: str):
        self.fin_edit_descricao = v

    def set_fin_edit_valor_previsto(self, v: str):
        """Allow digits, comma, dot only (raw typing)."""
        self.fin_edit_valor_previsto = re.sub(r"[^\d,.]", "", v)

    def on_blur_fin_valor_previsto(self):
        """Format as BRL on blur."""
        self.fin_edit_valor_previsto = _fmt_brl_input(self.fin_edit_valor_previsto)

    def set_fin_edit_valor_executado(self, v: str):
        """Allow digits, comma, dot only (raw typing)."""
        self.fin_edit_valor_executado = re.sub(r"[^\d,.]", "", v)

    def on_blur_fin_valor_executado(self):
        """Format as BRL on blur."""
        self.fin_edit_valor_executado = _fmt_brl_input(self.fin_edit_valor_executado)

    def set_fin_edit_status(self, v: str):
        self.fin_edit_status = v

    def set_fin_edit_data(self, v: str):
        self.fin_edit_data = v

    def set_fin_edit_atividade(self, v: str):
        self.fin_edit_atividade_id = v if v != "__none__" else ""

    def set_fin_edit_observacoes(self, v: str):
        self.fin_edit_observacoes = v

    # ═════════════════════════════════════════════════════════════════════════
    # Filter setters
    # ═════════════════════════════════════════════════════════════════════════

    def set_fin_filter_status(self, v: str):
        self.fin_filter_status = "" if v == "__none__" else v

    def set_fin_filter_categoria(self, v: str):
        self.fin_filter_categoria = "" if v == "__none__" else v

    def set_fin_search_input(self, v: str):
        self.fin_search_input = v

    def commit_fin_search(self, _v: str = ""):
        self.fin_search = self.fin_search_input

    def handle_fin_search_key(self, key: str):
        if key == "Enter":
            self.fin_search = self.fin_search_input

    # ═════════════════════════════════════════════════════════════════════════
    # Save
    # ═════════════════════════════════════════════════════════════════════════

    @rx.event(background=True)
    async def save_fin_custo(self):
        async with self:
            # Validate
            if not self.fin_edit_descricao.strip():
                self.fin_error = "Descrição é obrigatória."
                return
            prev_str = self.fin_edit_valor_previsto.strip() or "0"
            exec_str = self.fin_edit_valor_executado.strip() or "0"
            self.fin_saving = True
            self.fin_error = ""
            contrato = self.fin_contrato
            custo_id = self.fin_edit_id
            cat_id = self.fin_edit_categoria_id
            cat_nome = self.fin_edit_categoria_nome
            empresa = self.fin_edit_empresa.strip()
            descricao = self.fin_edit_descricao.strip()
            status = self.fin_edit_status
            data = self.fin_edit_data
            atividade_id = self.fin_edit_atividade_id
            obs = self.fin_edit_observacoes
            avg_pct = self.fin_avg_activity_pct

        from bomtempo.core.fin_service import _parse_float as _pf
        prev_val = _pf(prev_str)
        exec_val = _pf(exec_str)

        # Get username + client_id — uma única cross-state read, atualiza cache se necessário
        client_id = ""
        username = ""
        try:
            async with self:
                client_id = self._fin_client_id
            from bomtempo.state.global_state import GlobalState
            gs = await self.get_state(GlobalState)
            username = str(gs.current_user_name or "")
            if not client_id:
                client_id = str(gs.current_client_id or "")
                async with self:
                    self._fin_client_id = client_id
        except Exception:
            pass

        if not client_id:
            async with self:
                self.fin_error = "Erro: tenant não identificado. Faça logout e login novamente."
                self.fin_saving = False
            return

        # Resolve/create categoria if needed
        if cat_nome.strip() and not cat_id:
            cat_id, cat_nome = FinService.get_or_create_categoria(cat_nome)
            # Reload categorias so the new one appears in the dropdown
            try:
                updated_cats = FinService.load_categorias()
                async with self:
                    self.fin_categorias = updated_cats
            except Exception:
                pass

        try:
            ok, result = FinService.save_custo(
                contrato=contrato,
                categoria_id=cat_id,
                categoria_nome=cat_nome,
                empresa=empresa,
                descricao=descricao,
                valor_previsto=prev_val,
                valor_executado=exec_val,
                status=status,
                data_custo=data,
                atividade_id=atividade_id,
                custo_id=custo_id,
                client_id=client_id,
            )

            if not ok:
                async with self:
                    self.fin_error = f"Erro ao salvar: {result[:120]}"
                    self.fin_saving = False
                return

            # Reload custos list + recompute all charts
            custos = FinService.load_custos(contrato)
            scurve = FinService.compute_scurve(custos)
            by_cat = FinService.compute_by_categoria(custos)
            kpis = FinService.compute_kpis(custos)
            forecast = FinService.compute_evm(custos, avg_pct)

            async with self:
                self.fin_custos = custos
                self.fin_scurve = scurve
                self.fin_by_cat = by_cat
                self.fin_kpis = kpis
                self.fin_forecast = forecast
                self.fin_saving = False
                self.fin_show_dialog = False

            # Sync GlobalState financeiro_list for sidebar dashboard
            try:
                from bomtempo.state.global_state import GlobalState
                yield GlobalState.sync_financeiro_list
            except Exception as e:
                logger.warning(f"sync_financeiro_list skipped: {e}")
        except Exception as e:
            logger.error(f"save_fin_custo error: {e}", exc_info=True)
            async with self:
                self.fin_saving = False
                self.fin_error = f"Erro inesperado: {str(e)[:120]}"

    # ═════════════════════════════════════════════════════════════════════════
    # Delete
    # ═════════════════════════════════════════════════════════════════════════

    def request_fin_delete(self, custo_id: str):
        row = next((r for r in self.fin_custos if r.get("id") == custo_id), None)
        self.fin_delete_id = custo_id
        self.fin_delete_desc = row.get("descricao", custo_id[:8]) if row else custo_id[:8]
        self.fin_show_delete = True

    def cancel_fin_delete(self):
        self.fin_show_delete = False
        self.fin_delete_id = ""
        self.fin_delete_desc = ""

    @rx.event(background=True)
    async def confirm_fin_delete(self):
        async with self:
            custo_id = self.fin_delete_id
            contrato = self.fin_contrato
            avg_pct = self.fin_avg_activity_pct
            self.fin_show_delete = False

        ok = FinService.delete_custo(custo_id)
        if not ok:
            async with self:
                self.fin_error = "Erro ao excluir custo."
            return

        custos = FinService.load_custos(contrato)
        scurve = FinService.compute_scurve(custos)
        by_cat = FinService.compute_by_categoria(custos)
        kpis = FinService.compute_kpis(custos)
        forecast = FinService.compute_evm(custos, avg_pct)

        async with self:
            self.fin_custos = custos
            self.fin_scurve = scurve
            self.fin_by_cat = by_cat
            self.fin_kpis = kpis
            self.fin_forecast = forecast
            self.fin_delete_id = ""
            self.fin_delete_desc = ""

        # Sync GlobalState financeiro_list for sidebar dashboard
        try:
            from bomtempo.state.global_state import GlobalState
            yield GlobalState.sync_financeiro_list
        except Exception as e:
            logger.warning(f"sync_financeiro_list skipped: {e}")
