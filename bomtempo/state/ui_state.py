"""
UIState — Estado exclusivo de UI (modais, abas, loading granular, toasts).
Separado do GlobalState para minimizar o payload serializado por evento.
Qualquer clique que só afeta UI (abrir modal, trocar aba) serializa apenas
este state leve (~10 vars) em vez do GlobalState inteiro (~160 vars).
"""
from __future__ import annotations
import reflex as rx


class UIState(rx.State):
    # ── Modais do GlobalState migrados ───────────────────────────────────────
    show_novo_projeto: bool = False
    show_edit_projeto: bool = False
    show_duplicar_projeto: bool = False
    show_analysis_dialog: bool = False
    show_risk_breakdown: bool = False
    show_alertas_ia_dialog: bool = False
    show_kpi_detail: str = ""          # "" | "total_contratado" | ...
    show_avatar_modal: bool = False
    avatar_modal_tab: str = "avatar"
    show_forgot_password: bool = False

    # ── Loading granular por seção ────────────────────────────────────────────
    # Chave = nome da seção, valor = bool — permite skeleton por área
    loading_sections: dict[str, bool] = {}

    # ── Navegação ────────────────────────────────────────────────────────────
    page_loading: bool = False
    sidebar_open: bool = True

    # ── Toast / feedback inline ───────────────────────────────────────────────
    toast_message: str = ""
    toast_type: str = "info"   # "info" | "success" | "error" | "warning"
    toast_visible: bool = False

    # ── Busca local (não dispara banco) ──────────────────────────────────────
    projetos_search_ui: str = ""
    project_search_ui: str = ""

    # ── Helpers ──────────────────────────────────────────────────────────────
    def open_risk_breakdown(self):
        self.show_risk_breakdown = True

    def close_risk_breakdown(self):
        self.show_risk_breakdown = False

    def set_show_alertas_ia_dialog(self, v: bool):
        self.show_alertas_ia_dialog = v

    def set_loading(self, section: str, value: bool):
        self.loading_sections = {**self.loading_sections, section: value}

    def show_toast(self, msg: str, type_: str = "info"):
        self.toast_message = msg
        self.toast_type = type_
        self.toast_visible = True

    def hide_toast(self):
        self.toast_visible = False

    def close_all_modals(self):
        self.show_novo_projeto = False
        self.show_edit_projeto = False
        self.show_duplicar_projeto = False
        self.show_analysis_dialog = False
        self.show_risk_breakdown = False
        self.show_alertas_ia_dialog = False
        self.show_kpi_detail = ""
        self.show_avatar_modal = False

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
