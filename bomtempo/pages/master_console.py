"""
Master Console — BTP MASTER tenant.
Visão global: tenants, usuários cross-tenant, criação de novos tenants.
"""
from __future__ import annotations

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.master_state import MasterState


# ── Helpers ──────────────────────────────────────────────────────────────────


def _kpi_card(label: str, value, icon: str = "info") -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag=icon, size=14, color=S.COPPER),
                rx.text(label, font_size="10px", color=S.TEXT_MUTED,
                        font_weight="600", letter_spacing="0.1em",
                        text_transform="uppercase"),
                spacing="2", align="center",
            ),
            rx.text(value, font_size="22px", font_weight="800", color="white"),
            spacing="2", align="start",
        ),
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius=S.R_CONTROL,
        padding="16px 20px",
        flex="1",
        min_width="160px",
    )


def _tenant_row(t: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.cond(
                    t["is_master"] == "True",
                    rx.icon(tag="shield", size=14, color=S.COPPER),
                    rx.icon(tag="building-2", size=14, color=S.TEXT_MUTED),
                ),
                rx.text(t["client_name"], font_weight="700", color="white", font_size="13px"),
                spacing="2", align="center",
            ),
        ),
        rx.table.cell(
            rx.badge(t["status"],
                     color_scheme=rx.cond(t["status"] == "active", "green", "red"),
                     variant="soft", size="1"),
        ),
        rx.table.cell(rx.text(t["user_count"], color=S.TEXT_MUTED, font_size="13px")),
        rx.table.cell(rx.text(t["session_count"], color=S.TEXT_MUTED, font_size="13px")),
        rx.table.cell(rx.text(t["total_logs"], color=S.TEXT_MUTED, font_size="13px")),
        rx.table.cell(rx.text("R$ ", t["ai_budget"], color=S.COPPER, font_size="13px", font_weight="600")),
    )


def _user_row(u: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.text(u["username"], font_weight="600", color="white", font_size="13px")),
        rx.table.cell(
            rx.badge(u["client_name"], color_scheme="amber", variant="soft", size="1"),
        ),
        rx.table.cell(
            rx.text(u["user_role"], color=S.TEXT_MUTED, font_size="12px",
                    font_family=S.FONT_MONO),
        ),
        rx.table.cell(rx.text(u["email"], color=S.TEXT_MUTED, font_size="12px")),
    )


def _form_field(label: str, component: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, font_size="11px", font_weight="600", color=S.TEXT_MUTED,
                text_transform="uppercase", letter_spacing="0.08em"),
        component,
        spacing="1", width="100%",
    )


def _create_tenant_modal() -> rx.Component:
    input_style = {
        "background": "rgba(255,255,255,0.06)",
        "border": f"1px solid {S.BORDER_SUBTLE}",
        "borderRadius": "6px",
        "color": "white",
        "fontSize": "13px",
        "padding": "8px 10px",
        "width": "100%",
        "outline": "none",
    }
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.icon(tag="plus-circle", size=18, color=S.COPPER),
                    rx.text("Novo Cliente / Tenant", font_family=S.FONT_TECH,
                            font_size="1.05rem", font_weight="700", color="white"),
                    rx.spacer(),
                    rx.icon_button(rx.icon(tag="x", size=16),
                                   on_click=MasterState.close_create_modal,
                                   variant="ghost", color_scheme="amber", size="2"),
                    width="100%", align="center", margin_bottom="4px",
                ),
                rx.text("Cria o tenant e o primeiro usuário administrador.",
                        font_size="12px", color=S.TEXT_MUTED, padding_bottom="8px"),

                # Error
                rx.cond(
                    MasterState.create_error != "",
                    rx.callout.root(
                        rx.callout.icon(rx.icon(tag="triangle-alert", size=14)),
                        rx.callout.text(MasterState.create_error),
                        color_scheme="red", variant="soft", size="1", width="100%",
                    ),
                ),

                rx.separator(width="100%", color_scheme="amber", opacity="0.2"),
                rx.text("DADOS DO CLIENTE", font_size="10px", font_weight="700",
                        color=S.COPPER, letter_spacing="0.15em"),

                _form_field("Nome do cliente / empresa",
                    rx.el.input(
                        placeholder="Ex: Construtora ABC Ltda",
                        default_value=MasterState.new_tenant_name,
                        on_blur=MasterState.set_new_tenant_name,
                        style=input_style,
                    ),
                ),
                _form_field("Budget de IA (R$)",
                    rx.el.input(
                        placeholder="100",
                        type="number",
                        default_value=MasterState.new_tenant_budget,
                        on_blur=MasterState.set_new_tenant_budget,
                        style=input_style,
                    ),
                ),

                rx.separator(width="100%", color_scheme="amber", opacity="0.2"),
                rx.text("USUÁRIO ADMINISTRADOR", font_size="10px", font_weight="700",
                        color=S.COPPER, letter_spacing="0.15em"),

                _form_field("Login do administrador",
                    rx.el.input(
                        placeholder="admin.cliente",
                        default_value=MasterState.new_admin_username,
                        on_blur=MasterState.set_new_admin_username,
                        style=input_style,
                    ),
                ),
                _form_field("Senha inicial",
                    rx.el.input(
                        placeholder="senha",
                        type="password",
                        default_value=MasterState.new_admin_password,
                        on_blur=MasterState.set_new_admin_password,
                        style=input_style,
                    ),
                ),

                # Buttons
                rx.hstack(
                    rx.button("Cancelar", on_click=MasterState.close_create_modal,
                              variant="ghost", color_scheme="gray", size="2"),
                    rx.button(
                        rx.cond(MasterState.is_creating,
                                rx.hstack(rx.spinner(size="2"), rx.text("Criando..."), spacing="2"),
                                rx.text("Criar Tenant")),
                        on_click=MasterState.create_tenant,
                        color_scheme="amber", size="2",
                        disabled=MasterState.is_creating,
                    ),
                    spacing="3", justify="end", width="100%", padding_top="8px",
                ),

                spacing="3", width="100%",
            ),
            max_width="440px",
            style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}"},
        ),
        open=MasterState.show_create_modal,
    )


# ── Page ─────────────────────────────────────────────────────────────────────


def master_console_page() -> rx.Component:
    return rx.box(
        _create_tenant_modal(),

        # Header
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="shield-check", size=20, color=S.COPPER),
                    rx.text("MASTER CONSOLE", font_size="20px", font_weight="800",
                            color="white", letter_spacing="0.1em", font_family=S.FONT_TECH),
                    spacing="3", align="center",
                ),
                rx.text("Visão global multi-tenant — BTP MASTER", font_size="13px", color=S.TEXT_MUTED),
                spacing="1", align="start",
            ),
            rx.spacer(),
            rx.button(
                rx.hstack(rx.icon(tag="plus", size=14), rx.text("Novo Cliente"), spacing="2"),
                on_click=MasterState.open_create_modal,
                color_scheme="amber", variant="solid", size="2",
            ),
            width="100%", align="center", padding_bottom="24px",
        ),

        # KPI Row
        rx.hstack(
            _kpi_card("Tenants", MasterState.tenants.length().to_string(), "building-2"),
            _kpi_card("Usuários totais", MasterState.all_users.length().to_string(), "users"),
            _kpi_card("Logado como", GlobalState.current_user_name, "shield-check"),
            spacing="4", width="100%", wrap="wrap", padding_bottom="28px",
        ),

        # ── Tenants ───────────────────────────────────────────────
        rx.cond(
            MasterState.is_loading,
            rx.center(rx.spinner(size="3", color=S.COPPER), padding="40px"),
            rx.box(
                rx.hstack(
                    rx.text("CLIENTES ATIVOS", font_size="11px", font_weight="700",
                            color=S.TEXT_MUTED, letter_spacing="0.15em", text_transform="uppercase"),
                    rx.spacer(),
                    rx.text(MasterState.tenants.length().to_string(), " tenants",
                            font_size="11px", color=S.TEXT_MUTED),
                    width="100%", align="center", padding_bottom="12px",
                ),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("CLIENTE"),
                            rx.table.column_header_cell("STATUS"),
                            rx.table.column_header_cell("USUÁRIOS"),
                            rx.table.column_header_cell("SESSÕES IA"),
                            rx.table.column_header_cell("LOGS"),
                            rx.table.column_header_cell("BUDGET IA"),
                        )
                    ),
                    rx.table.body(rx.foreach(MasterState.tenants, _tenant_row)),
                    width="100%", variant="surface",
                ),
                bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius=S.R_CONTROL, padding="20px", width="100%",
                margin_bottom="24px",
            ),
        ),

        # ── Todos os usuários ─────────────────────────────────────
        rx.cond(
            MasterState.users_loading,
            rx.center(rx.spinner(size="2", color=S.COPPER), padding="32px"),
            rx.box(
                rx.text("TODOS OS USUÁRIOS", font_size="11px", font_weight="700",
                        color=S.TEXT_MUTED, letter_spacing="0.15em",
                        text_transform="uppercase", padding_bottom="12px"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("LOGIN"),
                            rx.table.column_header_cell("TENANT"),
                            rx.table.column_header_cell("PERFIL"),
                            rx.table.column_header_cell("E-MAIL"),
                        )
                    ),
                    rx.table.body(rx.foreach(MasterState.all_users, _user_row)),
                    width="100%", variant="surface",
                ),
                bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius=S.R_CONTROL, padding="20px", width="100%",
            ),
        ),

        padding="32px", width="100%", min_height="100vh",
    )
