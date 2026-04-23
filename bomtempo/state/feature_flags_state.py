"""
Feature Flags Admin State — gerencia features por contrato.
Página: /admin/contract-features
"""

import asyncio
from typing import Dict, List

import reflex as rx

from bomtempo.core.feature_flags import (
    FEATURE_LABELS,
    FEATURE_MODULES,
    FEATURE_ORDER,
    FeatureFlagsService,
)
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


class FeatureFlagsState(rx.State):
    """Estado para a página de gerenciamento de Feature Flags por Contrato."""

    # ── UI state ──────────────────────────────────────────────────────────────
    is_loading: bool = False
    selected_contract: str = ""
    save_status: str = ""  # mensagem de feedback

    # ── Dados ─────────────────────────────────────────────────────────────────
    # Lista de contratos disponíveis (carregada do GlobalState)
    contracts_options: List[str] = []

    # Features do contrato selecionado: [{key, label, module, enabled}]
    feature_rows: List[Dict[str, str]] = []

    # ── Computed ──────────────────────────────────────────────────────────────

    @rx.var
    def has_contract_selected(self) -> bool:
        return bool(self.selected_contract.strip())

    # ── Loaders ───────────────────────────────────────────────────────────────

    async def load_page(self):
        """Carrega lista de contratos ao entrar na página."""
        self.is_loading = True
        self.save_status = ""
        yield
        try:
            from bomtempo.state.global_state import GlobalState
            gs = await self.get_state(GlobalState)
            contracts = [str(c.get("contrato", "")) for c in (gs.contratos_list or []) if c.get("contrato")]
            self.contracts_options = sorted(set(contracts))
            if self.contracts_options and not self.selected_contract:
                self.selected_contract = self.contracts_options[0]
        except Exception as e:
            logger.error(f"FeatureFlagsState.load_page: {e}")
        finally:
            self.is_loading = False
        if self.selected_contract:
            yield FeatureFlagsState.load_contract_features

    @rx.event(background=True)
    async def load_contract_features(self):
        """Carrega as features do contrato selecionado."""
        async with self:
            self.is_loading = True
            contract_id = str(self.selected_contract)

        loop = asyncio.get_running_loop()
        try:
            enabled_keys = await loop.run_in_executor(
                None,
                lambda: FeatureFlagsService.get_features_for_contract(contract_id),
            )
        except Exception as e:
            logger.error(f"load_contract_features: {e}")
            enabled_keys = []

        rows = []
        for fk in FEATURE_ORDER:
            # Se enabled_keys == FEATURE_ORDER (nenhum registro no BD), tudo "true"
            rows.append({
                "key":     fk,
                "label":   FEATURE_LABELS.get(fk, fk),
                "module":  FEATURE_MODULES.get(fk, ""),
                "enabled": "true" if fk in enabled_keys else "false",
            })
        # sort: enabled first

        async with self:
            self.feature_rows = rows
            self.is_loading = False

    # ── Actions ───────────────────────────────────────────────────────────────

    def set_selected_contract(self, contract: str):
        self.selected_contract = contract
        self.save_status = ""
        return FeatureFlagsState.load_contract_features

    @rx.event(background=True)
    async def toggle_feature(self, feature_key: str):
        """Inverte o estado de uma feature para o contrato selecionado."""
        async with self:
            contract_id = str(self.selected_contract)
            # Encontrar estado atual
            current_enabled = False
            new_rows = []
            for row in self.feature_rows:
                if row["key"] == feature_key:
                    current_enabled = row["enabled"] == "true"
                    new_rows.append({**row, "enabled": "false" if current_enabled else "true"})
                else:
                    new_rows.append(dict(row))
            self.feature_rows = new_rows
            gs = await self.get_state(__import__("bomtempo.state.global_state", fromlist=["GlobalState"]).GlobalState)
            updated_by = str(gs.current_user_name)

        new_value = not current_enabled
        loop = asyncio.get_running_loop()
        ok = await loop.run_in_executor(
            None,
            lambda: FeatureFlagsService.set_feature(contract_id, feature_key, new_value, updated_by),
        )

        status_msg = (
            f"✅ '{FEATURE_LABELS.get(feature_key, feature_key)}' {'ativada' if new_value else 'desativada'}"
            if ok else
            f"❌ Erro ao salvar '{FEATURE_LABELS.get(feature_key, feature_key)}'"
        )
        async with self:
            self.save_status = status_msg

        yield rx.toast(status_msg, position="top-right")
