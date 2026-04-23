import reflex as rx

from bomtempo.components.action_ai_popup import action_ai_fab
from bomtempo.components.chat.chat_bubble import chart_init_script
from bomtempo.components.loading_screen import (
    loading_screen,
    skeleton_chart,
    skeleton_kpi_grid,
)
from bomtempo.components.sidebar import mobile_sidebar, sidebar
from bomtempo.components.top_bar import top_bar
from bomtempo.core import styles as S
from bomtempo.pages.login import login_page
from bomtempo.state.global_state import GlobalState
from bomtempo.state.rdo_state import RDOState
from bomtempo.state.usuarios_state import AVATAR_ICONS


def _fab_ai_insight() -> rx.Component:
    """Floating AI Insight pill button — fixed above the chat FAB."""
    return rx.cond(
        GlobalState.is_authenticated,
        rx.button(
            rx.hstack(
                rx.box(
                    width="7px",
                    height="7px",
                    border_radius="50%",
                    bg=S.COPPER,
                    flex_shrink="0",
                    class_name="animate-pulse",
                ),
                rx.icon(tag="sparkles", size=18, color="inherit"),
                rx.text(
                    rx.cond(
                        GlobalState.router.page.path == "/",
                        "Briefing Executivo",
                        "Análise Inteligente",
                    ),
                    font_family=S.FONT_TECH,
                    font_weight="700",
                    font_size="13px",
                    letter_spacing="0.04em",
                    white_space="nowrap",
                    display=["none", "none", "block"],
                ),
                spacing="2",
                align="center",
            ),
            on_click=GlobalState.analyze_current_view,
            is_loading=GlobalState.is_analyzing,
            class_name="fab-ai",
            style={
                "position": "fixed",
                "bottom": "28px",
                "right": "28px",
                "background": "rgba(201, 139, 42, 0.1)",
                "color": S.COPPER,
                "border": "1px solid rgba(201, 139, 42, 0.35)",
                "borderRadius": "999px",
                "paddingLeft": "16px",
                "paddingRight": "16px",
                "paddingTop": "12px",
                "paddingBottom": "12px",
                "zIndex": "998",
            },
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# KPI Detail Popup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _popup_table_header(*cols: str) -> rx.Component:
    """Enterprise table header — copper accent stripe on top."""
    return rx.el.tr(
        *[
            rx.el.th(
                col,
                style={
                    "padding": "10px 16px",
                    "textAlign": "left",
                    "fontWeight": "700",
                    "color": S.COPPER_LIGHT,
                    "backgroundColor": "rgba(201,139,42,0.06)",
                    "borderRight": f"1px solid rgba(255,255,255,0.04)",
                    "borderBottom": f"2px solid rgba(201,139,42,0.25)",
                    "fontSize": "10px",
                    "letterSpacing": "0.14em",
                    "textTransform": "uppercase",
                    "whiteSpace": "nowrap",
                    "fontFamily": "'Rajdhani', sans-serif",
                },
            )
            for col in cols
        ]
    )


def _popup_cell(value, highlight: bool = False, badge_color: str = "") -> rx.Component:
    """Table cell — optionally highlighted (copper) or pill-badged."""
    if badge_color:
        content = rx.el.span(
            value,
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "gap": "5px",
                "padding": "2px 8px",
                "borderRadius": "3px",
                "fontSize": "11px",
                "fontWeight": "700",
                "letterSpacing": "0.05em",
                "background": f"rgba{badge_color}0.1)",
                "border": f"1px solid rgba{badge_color}0.3)",
                "color": f"rgb{badge_color}",
                "fontFamily": S.FONT_TECH,
            },
        )
    else:
        content = value
    return rx.el.td(
        content,
        style={
            "padding": "10px 16px",
            "color": S.COPPER_LIGHT if highlight else S.TEXT_PRIMARY,
            "borderRight": f"1px solid rgba(255,255,255,0.04)",
            "borderBottom": f"1px solid rgba(255,255,255,0.04)",
            "fontSize": "13px",
            "fontFamily": "'JetBrains Mono', monospace" if highlight else "inherit",
            "fontWeight": "600" if highlight else "400",
            "whiteSpace": "nowrap",
            "transition": "background 0.12s ease",
            "background": "transparent",
        },
    )


def _kpi_detail_contrato_table() -> rx.Component:
    """Total Contratado — breakdown per contract."""
    return rx.vstack(
        rx.text(
            "Distribuição por Contrato",
            font_size="11px",
            color=S.TEXT_MUTED,
            font_weight="700",
            text_transform="uppercase",
            letter_spacing="0.1em",
            margin_bottom="8px",
        ),
        rx.el.table(
            rx.el.thead(_popup_table_header("Contrato", "Contratado", "Medido", "Saldo", "% Exec.")),
            rx.el.tbody(
                rx.foreach(
                    GlobalState.fin_contrato_rows,
                    lambda row: rx.el.tr(
                        _popup_cell(row["contrato"]),
                        _popup_cell(row["total_contratado_fmt"], highlight=True),
                        _popup_cell(row["total_realizado_fmt"]),
                        _popup_cell(row["saldo_fmt"]),
                        _popup_cell(row["pct_medido"]),
                    ),
                )
            ),
            class_name="enterprise-kpi-table",
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "border": "1px solid rgba(201,139,42,0.18)",
                "borderRadius": "6px",
                "overflow": "hidden",
            },
        ),
        width="100%",
        spacing="0",
    )


def _kpi_detail_medido_table() -> rx.Component:
    """Total Medido — breakdown per cockpit milestone."""
    return rx.vstack(
        rx.text(
            "Medições por Marco (Cockpit)",
            font_size="11px",
            color=S.TEXT_MUTED,
            font_weight="700",
            text_transform="uppercase",
            letter_spacing="0.1em",
            margin_bottom="8px",
        ),
        rx.el.table(
            rx.el.thead(_popup_table_header("Marco / Cockpit", "Contratado", "Medido", "% Exec.")),
            rx.el.tbody(
                rx.foreach(
                    GlobalState.fin_cockpit_popup_rows,
                    lambda row: rx.el.tr(
                        _popup_cell(row["cockpit"]),
                        _popup_cell(row["total_contratado_fmt"]),
                        _popup_cell(row["total_realizado_fmt"], highlight=True),
                        _popup_cell(row["pct_medido"]),
                    ),
                )
            ),
            class_name="enterprise-kpi-table",
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "border": "1px solid rgba(201,139,42,0.18)",
                "borderRadius": "6px",
                "overflow": "hidden",
            },
        ),
        width="100%",
        spacing="0",
    )


def _kpi_detail_saldo_table() -> rx.Component:
    """Saldo à Medir — pending balance per contract."""
    return rx.vstack(
        rx.text(
            "Saldo Pendente por Contrato",
            font_size="11px",
            color=S.TEXT_MUTED,
            font_weight="700",
            text_transform="uppercase",
            letter_spacing="0.1em",
            margin_bottom="8px",
        ),
        rx.el.table(
            rx.el.thead(_popup_table_header("Contrato", "Total Cont.", "Total Med.", "Saldo a Medir", "% Restante")),
            rx.el.tbody(
                rx.foreach(
                    GlobalState.fin_contrato_rows,
                    lambda row: rx.el.tr(
                        _popup_cell(row["contrato"]),
                        _popup_cell(row["total_contratado_fmt"]),
                        _popup_cell(row["total_realizado_fmt"]),
                        _popup_cell(row["saldo_fmt"], highlight=True),
                        _popup_cell(row["pct_medido"]),
                    ),
                )
            ),
            class_name="enterprise-kpi-table",
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "border": "1px solid rgba(201,139,42,0.18)",
                "borderRadius": "6px",
                "overflow": "hidden",
            },
        ),
        width="100%",
        spacing="0",
    )


def _kpi_detail_contratos_ativos_table() -> rx.Component:
    """Contratos Ativos — list of active contracts."""
    return rx.vstack(
        rx.text(
            "Contratos em Execução",
            font_size="11px",
            color=S.TEXT_MUTED,
            font_weight="700",
            text_transform="uppercase",
            letter_spacing="0.1em",
            margin_bottom="8px",
        ),
        rx.el.table(
            rx.el.thead(_popup_table_header("Contrato", "Cliente", "Status", "Valor Contratado")),
            rx.el.tbody(
                rx.foreach(
                    GlobalState.contratos_ativos_rows,
                    lambda row: rx.el.tr(
                        _popup_cell(row["contrato"]),
                        _popup_cell(row["cliente"]),
                        # Status cell — green dot pill
                        rx.el.td(
                            rx.el.span(
                                rx.el.span(
                                    style={
                                        "display": "inline-block",
                                        "width": "6px",
                                        "height": "6px",
                                        "borderRadius": "50%",
                                        "background": "#2A9D8F",
                                        "marginRight": "6px",
                                        "verticalAlign": "middle",
                                    }
                                ),
                                row["status"],
                                style={
                                    "display": "inline-flex",
                                    "alignItems": "center",
                                    "padding": "2px 8px",
                                    "borderRadius": "3px",
                                    "fontSize": "11px",
                                    "fontWeight": "600",
                                    "background": "rgba(42,157,143,0.08)",
                                    "border": "1px solid rgba(42,157,143,0.25)",
                                    "color": "#2A9D8F",
                                    "fontFamily": "'Rajdhani', sans-serif",
                                    "letterSpacing": "0.04em",
                                    "whiteSpace": "nowrap",
                                },
                            ),
                            style={
                                "padding": "10px 16px",
                                "borderRight": "1px solid rgba(255,255,255,0.04)",
                                "borderBottom": "1px solid rgba(255,255,255,0.04)",
                            },
                        ),
                        _popup_cell(row["valor_fmt"], highlight=True),
                    ),
                )
            ),
            class_name="enterprise-kpi-table",
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "border": "1px solid rgba(201,139,42,0.18)",
                "borderRadius": "6px",
                "overflow": "hidden",
            },
        ),
        width="100%",
        spacing="0",
    )


# Icon + title mapping for popup header
_POPUP_META = {
    "total_contratado": ("wallet", "Total Contratado", "Valor total dos contratos firmados"),
    "receita_total": ("wallet", "Receita Total", "Valor total da carteira de contratos"),
    "total_medido": ("dollar-sign", "Total Medido", "Execução financeira acumulada por marco"),
    "saldo_medir": ("trending-up", "Saldo à Medir", "Saldo pendente de medição por contrato"),
    "contratos_ativos": ("hard-hat", "Contratos Ativos", "Contratos em status de execução"),
}


def _avatar_icon_btn(item: tuple) -> rx.Component:
    slug = item[0]
    label = item[1]
    is_sel = GlobalState.avatar_edit_icon == slug
    return rx.tooltip(
        rx.box(
            rx.icon(tag=slug, size=15, color=rx.cond(is_sel, S.COPPER, S.TEXT_MUTED)),
            width="34px",
            height="34px",
            border_radius="8px",
            bg=rx.cond(is_sel, "rgba(201,139,42,0.15)", "rgba(255,255,255,0.04)"),
            border=rx.cond(is_sel, f"1.5px solid {S.COPPER}", "1.5px solid transparent"),
            display="flex",
            align_items="center",
            justify_content="center",
            cursor="pointer",
            on_click=GlobalState.set_avatar_edit_icon(slug),
            transition="all 0.12s ease",
            _hover={"bg": "rgba(201,139,42,0.1)"},
        ),
        content=label,
    )


def _avatar_modal() -> rx.Component:
    """Meu Perfil modal — Avatar tab + Senha tab."""
    preview_icon = rx.cond(
        GlobalState.avatar_edit_icon != "",
        GlobalState.avatar_edit_icon,
        GlobalState.current_user_role_icon,
    )

    def _tab_btn(label: str, icon_tag: str, tab_key: str) -> rx.Component:
        active = GlobalState.avatar_modal_tab == tab_key
        return rx.box(
            rx.hstack(
                rx.icon(tag=icon_tag, size=13, color=rx.cond(active, S.COPPER, S.TEXT_MUTED)),
                rx.text(label, font_size="13px", color=rx.cond(active, "white", S.TEXT_MUTED)),
                spacing="2",
                align="center",
            ),
            padding="6px 14px",
            border_radius="8px",
            border=rx.cond(active, f"1.5px solid {S.COPPER}", "1.5px solid transparent"),
            bg=rx.cond(active, "rgba(201,139,42,0.1)", "rgba(255,255,255,0.04)"),
            cursor="pointer",
            on_click=GlobalState.set_avatar_modal_tab(tab_key),
        )

    # ── Avatar tab content ────────────────────────────────────────────────────
    avatar_tab = rx.vstack(
        # Preview
        rx.hstack(
            rx.text("Prévia:", font_size="12px", color=S.TEXT_MUTED, font_weight="600"),
            rx.cond(
                GlobalState.avatar_edit_type == "icon",
                rx.box(
                    rx.icon(tag=preview_icon, size=20, color=S.COPPER),
                    width="40px", height="40px", border_radius="full",
                    bg="rgba(201,139,42,0.15)", border=f"1.5px solid {S.COPPER}",
                    display="flex", align_items="center", justify_content="center",
                ),
                rx.avatar(
                    fallback=GlobalState.avatar_fallback,
                    size="3", radius="full", variant="soft", color_scheme="bronze",
                ),
            ),
            rx.vstack(
                rx.text(GlobalState.current_user_name, font_weight="600", color="white", font_size="14px"),
                rx.text(GlobalState.current_user_role, font_size="11px", color=S.TEXT_MUTED),
                spacing="0", align="start",
            ),
            spacing="3", align="center",
            padding="10px 14px", bg="rgba(255,255,255,0.03)",
            border_radius="10px", width="100%",
            border=f"1px solid {S.BORDER_SUBTLE}",
        ),
        # Type toggle
        rx.vstack(
            rx.text("Tipo de Avatar", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
            rx.hstack(
                rx.box(
                    rx.hstack(
                        rx.icon(tag="type", size=13, color=rx.cond(GlobalState.avatar_edit_type == "initial", S.COPPER, S.TEXT_MUTED)),
                        rx.text("Inicial", font_size="13px", color=rx.cond(GlobalState.avatar_edit_type == "initial", "white", S.TEXT_MUTED)),
                        spacing="2", align="center",
                    ),
                    padding="7px 16px", border_radius="8px",
                    border=rx.cond(GlobalState.avatar_edit_type == "initial", f"1.5px solid {S.COPPER}", "1.5px solid transparent"),
                    bg=rx.cond(GlobalState.avatar_edit_type == "initial", "rgba(201,139,42,0.1)", "rgba(255,255,255,0.04)"),
                    cursor="pointer", on_click=GlobalState.set_avatar_edit_type("initial"),
                ),
                rx.box(
                    rx.hstack(
                        rx.icon(tag="smile", size=13, color=rx.cond(GlobalState.avatar_edit_type == "icon", S.COPPER, S.TEXT_MUTED)),
                        rx.text("Ícone", font_size="13px", color=rx.cond(GlobalState.avatar_edit_type == "icon", "white", S.TEXT_MUTED)),
                        spacing="2", align="center",
                    ),
                    padding="7px 16px", border_radius="8px",
                    border=rx.cond(GlobalState.avatar_edit_type == "icon", f"1.5px solid {S.COPPER}", "1.5px solid transparent"),
                    bg=rx.cond(GlobalState.avatar_edit_type == "icon", "rgba(201,139,42,0.1)", "rgba(255,255,255,0.04)"),
                    cursor="pointer", on_click=GlobalState.set_avatar_edit_type("icon"),
                ),
                spacing="2",
            ),
            spacing="2", width="100%",
        ),
        # Icon grid
        rx.cond(
            GlobalState.avatar_edit_type == "icon",
            rx.vstack(
                rx.text("Escolha um ícone", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
                rx.flex(*[_avatar_icon_btn(item) for item in AVATAR_ICONS], wrap="wrap", gap="5px", width="100%"),
                spacing="2", width="100%",
            ),
        ),
        # Save
        rx.hstack(
            rx.button("Cancelar", on_click=GlobalState.close_avatar_modal, variant="soft", color_scheme="gray", style={"color": "rgba(255,255,255,0.75)"}),
            rx.button("Salvar Avatar", on_click=GlobalState.save_avatar_pref, color_scheme="amber"),
            spacing="3", justify="end", width="100%",
        ),
        spacing="4", width="100%",
    )

    # ── Senha tab content ─────────────────────────────────────────────────────
    senha_tab = rx.vstack(
        rx.cond(
            GlobalState.pw_error != "",
            rx.callout.root(
                rx.callout.icon(rx.icon(tag="triangle-alert", size=14)),
                rx.callout.text(GlobalState.pw_error),
                color_scheme="red", variant="soft", size="1", width="100%",
            ),
        ),
        rx.cond(
            GlobalState.pw_success,
            rx.callout.root(
                rx.callout.icon(rx.icon(tag="check", size=14)),
                rx.callout.text("Senha alterada com sucesso!"),
                color_scheme="green", variant="soft", size="1", width="100%",
            ),
        ),
        rx.cond(
            ~GlobalState.pw_success,
            rx.vstack(
                rx.vstack(
                    rx.text("Senha Atual", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
                    rx.input(type="password", placeholder="••••••••", value=GlobalState.pw_current, on_change=GlobalState.set_pw_current, width="100%", color_scheme="amber"),
                    spacing="1", width="100%",
                ),
                rx.vstack(
                    rx.text("Nova Senha", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
                    rx.input(type="password", placeholder="••••••••", value=GlobalState.pw_new, on_change=GlobalState.set_pw_new, width="100%", color_scheme="amber"),
                    spacing="1", width="100%",
                ),
                rx.vstack(
                    rx.text("Confirmar Nova Senha", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
                    rx.input(type="password", placeholder="••••••••", value=GlobalState.pw_confirm, on_change=GlobalState.set_pw_confirm, width="100%", color_scheme="amber"),
                    spacing="1", width="100%",
                ),
                spacing="3", width="100%",
            ),
        ),
        rx.hstack(
            rx.cond(
                GlobalState.pw_success,
                rx.button("Fechar", on_click=GlobalState.close_avatar_modal, color_scheme="amber"),
                rx.hstack(
                    rx.button("Cancelar", on_click=GlobalState.close_avatar_modal, variant="soft", color_scheme="gray", style={"color": "rgba(255,255,255,0.75)"}),
                    rx.button("Salvar Senha", on_click=GlobalState.save_password, color_scheme="amber"),
                    spacing="3",
                ),
            ),
            justify="end", width="100%",
        ),
        spacing="4", width="100%",
    )

    # ── Contato tab content ───────────────────────────────────────────────────
    contato_tab = rx.vstack(
        rx.cond(
            GlobalState.contact_error != "",
            rx.callout.root(
                rx.callout.icon(rx.icon(tag="triangle-alert", size=14)),
                rx.callout.text(GlobalState.contact_error),
                color_scheme="red", variant="soft", size="1", width="100%",
            ),
        ),
        rx.cond(
            GlobalState.contact_success,
            rx.callout.root(
                rx.callout.icon(rx.icon(tag="check", size=14)),
                rx.callout.text("Contato salvo com sucesso!"),
                color_scheme="green", variant="soft", size="1", width="100%",
            ),
        ),
        rx.vstack(
            rx.text("E-mail", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
            rx.input(
                type="email",
                placeholder="seu@email.com",
                value=GlobalState.contact_edit_email,
                on_change=GlobalState.set_contact_edit_email,
                width="100%",
                color_scheme="amber",
            ),
            spacing="1", width="100%",
        ),
        rx.vstack(
            rx.text("WhatsApp", font_size="12px", font_weight="600", color=S.TEXT_MUTED),
            rx.input(
                type="tel",
                placeholder="+55 11 99999-9999",
                value=GlobalState.contact_edit_whatsapp,
                on_change=GlobalState.set_contact_edit_whatsapp,
                width="100%",
                color_scheme="amber",
            ),
            spacing="1", width="100%",
        ),
        rx.text(
            "Usado para alertas e envio de documentos via Action AI.",
            font_size="11px", color=S.TEXT_MUTED, opacity="0.7",
        ),
        rx.hstack(
            rx.cond(
                GlobalState.contact_success,
                rx.button("Fechar", on_click=GlobalState.close_avatar_modal, color_scheme="amber"),
                rx.hstack(
                    rx.button("Cancelar", on_click=GlobalState.close_avatar_modal, variant="soft", color_scheme="gray", style={"color": "rgba(255,255,255,0.75)"}),
                    rx.button("Salvar Contato", on_click=GlobalState.save_contact, color_scheme="amber"),
                    spacing="3",
                ),
            ),
            justify="end", width="100%",
        ),
        spacing="4", width="100%",
    )

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.icon(tag="user", size=18, color=S.COPPER),
                    rx.text(
                        "Meu Perfil",
                        font_family=S.FONT_TECH,
                        font_size="1.05rem",
                        font_weight="700",
                        color="white",
                    ),
                    rx.spacer(),
                    rx.icon_button(
                        rx.icon(tag="x", size=16),
                        on_click=GlobalState.close_avatar_modal,
                        variant="ghost",
                        color_scheme="amber",
                        size="2",
                    ),
                    width="100%",
                    align="center",
                ),
                # Tab switcher
                rx.hstack(
                    _tab_btn("Avatar", "user", "avatar"),
                    _tab_btn("Contato", "mail", "contato"),
                    _tab_btn("Senha", "key-round", "senha"),
                    spacing="2",
                ),
                rx.separator(width="100%"),
                # Tab content
                rx.cond(
                    GlobalState.avatar_modal_tab == "avatar",
                    avatar_tab,
                    rx.cond(GlobalState.avatar_modal_tab == "contato", contato_tab, senha_tab),
                ),
                spacing="4",
                width="100%",
            ),
            max_width="460px",
            background="var(--bg-elevated)",
            border=f"1px solid {S.BORDER_SUBTLE}",
        ),
        open=GlobalState.show_avatar_modal,
    )


def _kpi_detail_dialog() -> rx.Component:
    """Premium KPI detail popup — glassmorphic, copper-themed data matrix."""

    def _dialog_header() -> rx.Component:
        return rx.hstack(
            # Copper glow orb decoration
            rx.box(
                position="absolute",
                top="-40px",
                right="-40px",
                width="200px",
                height="200px",
                border_radius="50%",
                bg="rgba(201, 139, 42, 0.06)",
                filter="blur(60px)",
                pointer_events="none",
            ),
            rx.center(
                rx.icon(tag="table-2", size=22, color=S.COPPER),
                width="44px",
                height="44px",
                border_radius=S.R_CONTROL,
                bg="rgba(201, 139, 42, 0.1)",
                border=f"1px solid {S.BORDER_ACCENT}",
                flex_shrink="0",
            ),
            rx.vstack(
                rx.dialog.title(
                    rx.cond(
                        GlobalState.show_kpi_detail == "total_contratado",
                        "Total Contratado",
                        rx.cond(
                            GlobalState.show_kpi_detail == "total_medido",
                            "Total Medido",
                            rx.cond(
                                GlobalState.show_kpi_detail == "saldo_medir",
                                "Saldo à Medir",
                                rx.cond(
                                    GlobalState.show_kpi_detail == "contratos_ativos",
                                    "Contratos Ativos",
                                    "Receita Total",
                                ),
                            ),
                        ),
                    ),
                    color=S.COPPER,
                    font_family=S.FONT_TECH,
                    font_size="1.1rem",
                    letter_spacing="0.03em",
                    margin="0",
                ),
                rx.text(
                    rx.cond(
                        GlobalState.show_kpi_detail == "total_contratado",
                        "Valor total dos contratos firmados",
                        rx.cond(
                            GlobalState.show_kpi_detail == "total_medido",
                            "Execução financeira acumulada por marco",
                            rx.cond(
                                GlobalState.show_kpi_detail == "saldo_medir",
                                "Saldo pendente de medição por contrato",
                                rx.cond(
                                    GlobalState.show_kpi_detail == "contratos_ativos",
                                    "Contratos em status de execução",
                                    "Carteira financeira consolidada",
                                ),
                            ),
                        ),
                    ),
                    color=S.TEXT_MUTED,
                    font_size="12px",
                    margin="0",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.dialog.close(
                rx.icon_button(
                    rx.icon(tag="x", size=18),
                    variant="ghost",
                    color_scheme="amber",
                    on_click=GlobalState.set_show_kpi_detail(""),
                )
            ),
            width="100%",
            align="center",
            spacing="4",
            position="relative",
            overflow="hidden",
            margin_bottom="24px",
        )

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                _dialog_header(),
                rx.scroll_area(
                    rx.cond(
                        GlobalState.show_kpi_detail == "total_medido",
                        _kpi_detail_medido_table(),
                        rx.cond(
                            GlobalState.show_kpi_detail == "contratos_ativos",
                            _kpi_detail_contratos_ativos_table(),
                            rx.cond(
                                GlobalState.show_kpi_detail == "saldo_medir",
                                _kpi_detail_saldo_table(),
                                _kpi_detail_contrato_table(),  # total_contratado + receita_total
                            ),
                        ),
                    ),
                    max_height="65vh",
                    type="hover",
                    scrollbars="vertical",
                    width="100%",
                ),
                width="100%",
                spacing="0",
            ),
            bg="rgba(10, 31, 26, 0.98)",
            backdrop_filter="blur(24px)",
            border=f"1px solid {S.BORDER_ACCENT}",
            max_width="860px",
            width="95vw",
            border_radius=S.R_CARD,
            padding="32px",
            box_shadow="0 32px 72px -12px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(201,139,42,0.12)",
        ),
        open=GlobalState.show_kpi_detail != "",
        on_open_change=GlobalState.handle_detail_open_change,
    )


_MUTED_OVERLAY = "rgba(255,255,255,0.45)"
_COPPER_OVERLAY = "#C98B2A"


def _rdo_submit_overlay() -> rx.Component:
    """Full-screen RDO submit overlay — rendered at root level so position:fixed covers full viewport."""
    steps = [
        ("[save]", "Salvando RDO no banco de dados…"),
        ("[doc]", "Gerando PDF…"),
        ("☁️", "Enviando PDF para a nuvem…"),
        ("✅", "Finalizando e enviando e-mails…"),
    ]

    def _step_row(icon: str, label: str) -> rx.Component:
        active = RDOState.submit_status.contains(icon)
        return rx.hstack(
            rx.text(icon, font_size="18px"),
            rx.text(
                label, size="2",
                color=rx.cond(active, "white", _MUTED_OVERLAY),
                font_weight=rx.cond(active, "600", "400"),
            ),
            spacing="3",
            align="center",
            opacity=rx.cond(active, "1", "0.45"),
            style={"transition": "opacity 0.3s"},
        )

    return rx.cond(
        RDOState.is_submitting,
        rx.box(
            rx.vstack(
                rx.spinner(size="3", color=_COPPER_OVERLAY),
                rx.text(
                    "Processando seu RDO",
                    size="4", weight="bold", color="white",
                    font_family="'Rajdhani', sans-serif",
                    letter_spacing="0.5px",
                ),
                rx.vstack(
                    *[_step_row(icon, label) for icon, label in steps],
                    spacing="3",
                    padding="16px 20px",
                    background="rgba(255,255,255,0.05)",
                    border="1px solid rgba(255,255,255,0.1)",
                    border_radius="10px",
                    width="100%",
                ),
                rx.text("Não feche esta tela", size="1", color=_MUTED_OVERLAY, opacity="0.6"),
                spacing="4",
                align="center",
                padding="32px 28px",
                background="#0d2219",
                border="1px solid rgba(201,139,42,0.35)",
                border_radius="16px",
                max_width="340px",
                width="90vw",
                box_shadow="0 32px 80px rgba(0,0,0,0.8)",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            display="flex",
            align_items="center",
            justify_content="center",
            background="rgba(0,0,0,0.75)",
            z_index="9999",
            style={"backdropFilter": "blur(4px)"},
        ),
    )


def default_layout(content: rx.Component) -> rx.Component:
    """Default layout matching React reference: sidebar + content (Mobile Responsive)"""

    return rx.box(
        # ── Signature canvas binding (global — persists across SPA navigation) ──
        rx.script(src="/js/sig_canvas.js"),
        # ── Chart.js global initializer (MutationObserver para gráficos do chat IA) ──
        chart_init_script(),
        # ── Light theme: propagate Radix color-mode class to <html> and <body> ──
        # CAUSA RAIZ: body está FORA de [data-is-root-theme], então CSS vars
        # declaradas nesse seletor nunca chegam ao body via herança.
        # SOLUÇÃO: copiar a classe light/dark para html e body explicitamente.
        rx.script("""
(function() {
  if (window.__lightThemePatchInstalled) return;
  window.__lightThemePatchInstalled = true;

  function applyTheme(themeName) {
    var html = document.documentElement;
    var body = document.body;

    // Propaga a classe para html e body — onde as CSS vars precisam estar
    html.classList.remove('light', 'dark');
    body.classList.remove('light', 'dark');
    html.classList.add(themeName);
    body.classList.add(themeName);

    if (themeName === 'light') {
      // Remove inline backgrounds que sobrescrevem o CSS
      body.style.removeProperty('background');
      body.style.removeProperty('background-color');
      var radixRoot = document.querySelector('[data-is-root-theme]');
      if (radixRoot) {
        radixRoot.style.removeProperty('background');
        radixRoot.style.removeProperty('background-color');
      }
      // Remove inline bg do main-layout-flex se existir
      document.querySelectorAll('.main-layout-flex').forEach(function(el) {
        el.style.removeProperty('background');
        el.style.removeProperty('background-color');
      });
    } else {
      // No dark: também limpar inline para deixar as vars do :root agirem
      body.style.removeProperty('background');
      body.style.removeProperty('background-color');
    }
  }

  function checkMode() {
    var root = document.querySelector('[data-is-root-theme]');
    if (!root) return;
    var themeName = root.classList.contains('light') ? 'light' : 'dark';
    applyTheme(themeName);
  }

  function init() {
    var radixRoot = document.querySelector('[data-is-root-theme]');
    if (!radixRoot) {
      setTimeout(init, 100);
      return;
    }
    // Aplica o tema atual imediatamente
    checkMode();
    // Observa mudanças de classe no elemento Radix
    var observer = new MutationObserver(function(mutations) {
      for (var i = 0; i < mutations.length; i++) {
        if (mutations[i].attributeName === 'class') {
          checkMode();
          break;
        }
      }
    });
    observer.observe(radixRoot, { attributes: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Belt-and-suspenders: re-check após qualquer click (toggle button)
  document.addEventListener('click', function() {
    setTimeout(checkMode, 50);
  }, false);
})();
"""),
        # ── Sticky/Pinned Recharts tooltip — clique para fixar, clique novamente para soltar ──
        rx.script("""
(function() {
  if (window.__tooltipPinInstalled) return;
  window.__tooltipPinInstalled = true;
  var pinned = null;
  document.addEventListener("click", function(e) {
    var wrapper = e.target.closest ? e.target.closest(".recharts-wrapper") : null;
    if (!wrapper) {
      // Click fora de qualquer chart — desafixa tooltip ativo
      if (pinned) {
        pinned.style.visibility = "";
        pinned.style.pointerEvents = "";
        pinned.classList.remove("tooltip-pinned");
        pinned = null;
      }
      return;
    }
    var tooltip = wrapper.querySelector(".recharts-tooltip-wrapper");
    if (!tooltip) return;
    if (pinned === tooltip) {
      // Segundo clique no mesmo chart — desafixa
      tooltip.style.visibility = "";
      tooltip.style.pointerEvents = "";
      tooltip.classList.remove("tooltip-pinned");
      pinned = null;
    } else {
      // Primeiro clique — afixa este tooltip
      if (pinned) {
        pinned.style.visibility = "";
        pinned.style.pointerEvents = "";
        pinned.classList.remove("tooltip-pinned");
      }
      // Garantir que está visível
      tooltip.style.visibility = "visible";
      tooltip.style.pointerEvents = "none";
      tooltip.classList.add("tooltip-pinned");
      pinned = tooltip;
    }
  }, false);
})();
"""),
        # ── PWA Init (manifest + SW + install prompt + viewport fix + favicon + iOS) ──
        rx.script("""
(function () {
  // Viewport: viewport-fit=cover para notch iOS; zoom permitido (inputs ≥ 16px previnem auto-zoom)
  (function() {
    var vp = document.querySelector('meta[name="viewport"]');
    var c = 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes, viewport-fit=cover';
    if (vp) { vp.content = c; }
    else {
      var m = document.createElement('meta');
      m.name = 'viewport'; m.content = c;
      document.head.insertBefore(m, document.head.firstChild);
    }
  })();
  // Favicon
  if (!document.querySelector('link[rel="icon"]')) {
    var fav = document.createElement('link');
    fav.rel = 'icon'; fav.href = '/pwa-icon.png'; fav.type = 'image/png';
    document.head.appendChild(fav);
  }
  // Manifest
  if (!document.querySelector('link[rel="manifest"]')) {
    var link = document.createElement('link');
    link.rel = 'manifest'; link.href = '/manifest.json';
    document.head.appendChild(link);
  }
  // Theme color
  if (!document.querySelector('meta[name="theme-color"]')) {
    var meta = document.createElement('meta');
    meta.name = 'theme-color'; meta.content = '#030504';
    document.head.appendChild(meta);
  }
  // Android PWA capable
  if (!document.querySelector('meta[name="mobile-web-app-capable"]')) {
    var m = document.createElement('meta');
    m.name = 'mobile-web-app-capable'; m.content = 'yes';
    document.head.appendChild(m);
  }
  // iOS — standalone mode + status bar translucente
  if (!document.querySelector('meta[name="apple-mobile-web-app-capable"]')) {
    var m = document.createElement('meta');
    m.name = 'apple-mobile-web-app-capable'; m.content = 'yes';
    document.head.appendChild(m);
  }
  if (!document.querySelector('meta[name="apple-mobile-web-app-title"]')) {
    var m = document.createElement('meta');
    m.name = 'apple-mobile-web-app-title'; m.content = 'Bomtempo';
    document.head.appendChild(m);
  }
  if (!document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')) {
    var m = document.createElement('meta');
    m.name = 'apple-mobile-web-app-status-bar-style'; m.content = 'black-translucent';
    document.head.appendChild(m);
  }
  // Apple touch icon
  if (!document.querySelector('link[rel="apple-touch-icon"]')) {
    var l = document.createElement('link');
    l.rel = 'apple-touch-icon'; l.href = '/pwa-icon.png';
    document.head.appendChild(l);
  }
  // Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(function () {});
  }
  // Install prompt
  window._btpDeferredPrompt = window._btpDeferredPrompt || null;
  if (!window._btpInstallListenerAdded) {
    window._btpInstallListenerAdded = true;
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      window._btpDeferredPrompt = e;
      window.dispatchEvent(new Event('_btpPromptReady'));
    });
    window._btpInstall = async function () {
      if (!window._btpDeferredPrompt) return;
      window._btpDeferredPrompt.prompt();
      await window._btpDeferredPrompt.userChoice;
      window._btpDeferredPrompt = null;
    };
  }
})();
"""),
        # ── Banner de reconexão WebSocket ─────────────────────────────────────
        # Só aparece se ~is_hydrated persistir >2.5s (WebSocket realmente caiu).
        # Navegações SPA normais hidratam em <500ms — o banner some antes de aparecer.
        # CSS animation-delay garante invisibilidade durante o flash inicial.
        rx.cond(
            ~rx.State.is_hydrated,
            rx.box(
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("Reconectando...", size="1", weight="medium"),
                    spacing="2",
                    align="center",
                ),
                background="var(--amber-3)",
                color="var(--amber-11)",
                border_bottom="1px solid var(--amber-6)",
                padding="6px 16px",
                width="100%",
                text_align="center",
                position="fixed",
                top="0",
                left="0",
                z_index="10000",
                opacity="0",
                style={
                    "animation": "reconnect-banner-appear 0s 2.5s forwards",
                },
            ),
            rx.fragment(),
        ),
        # ── Top progress bar — sempre no DOM; classe controla visibilidade ──
        rx.box(
            class_name=rx.cond(
                GlobalState.show_progress_bar,
                "top-loading-bar top-bar-active",
                "top-loading-bar top-bar-idle",
            )
        ),
        # ── Loading overlay GLOBAL ──────────────────────────────────────────────
        # Fora do rx.cond(is_authenticated): cobre login → redirect → página destino
        # sem flash. check_login faz yield antes de autenticar, então o overlay
        # já está visível enquanto is_authenticated ainda é False.
        rx.cond(
            GlobalState.show_loading_screen,
            loading_screen(),
        ),
        # ── Conteúdo condicional por autenticação ───────────────────────────────
        rx.cond(
            GlobalState.is_authenticated,
            # ── Authenticated view ──────────────────────────────────────────────
            rx.box(
                # ── Fixed top bar — desktop (outside flex so position:fixed works) ──
                rx.cond(~GlobalState.is_fullscreen_page, top_bar()),
                # ── Fixed mobile top bar ─────────────────────────────────────────
                rx.cond(~GlobalState.is_fullscreen_page, rx.box(
                    rx.hstack(
                        rx.cond(
                            (GlobalState.current_user_role == "Administrador")
                            | (GlobalState.current_user_role == "Engenheiro")
                            | (GlobalState.current_user_role == "Gestão-Mobile")
                            | (GlobalState.current_user_role == "engenheiro")
                            | (GlobalState.current_user_role == ""),
                            mobile_sidebar(),
                            rx.box(width="24px"),
                        ),
                        rx.spacer(),
                        rx.image(src="/icon.png", width="28px", height="28px", border_radius="4px", object_fit="cover"),
                        rx.spacer(),
                        rx.hstack(
                            rx.cond(
                                GlobalState.allowed_modules.contains("alertas"),
                                rx.box(rx.icon("bell", size=18, color=S.TEXT_MUTED), on_click=rx.redirect("/alertas"), padding="6px", cursor="pointer", border_radius="6px", _hover={"bg": "rgba(255,255,255,0.05)"}),
                                rx.fragment(),
                            ),
                            rx.box(
                                rx.cond(
                                    GlobalState.current_user_avatar_type == "icon",
                                    rx.box(rx.icon(tag=GlobalState.effective_avatar_icon, size=13, color="white"), width="28px", height="28px", border_radius="6px", background=f"linear-gradient(135deg, {S.COPPER}, {S.PATINA})", display="flex", align_items="center", justify_content="center"),
                                    rx.avatar(fallback=GlobalState.avatar_fallback, size="1", style={"width": "28px", "height": "28px", "border_radius": "6px", "background": f"linear-gradient(135deg, {S.COPPER}, {S.PATINA})", "font_family": S.FONT_TECH, "font_weight": "700", "font_size": "12px"}),
                                ),
                                on_click=rx.redirect("/perfil"), cursor="pointer", border_radius="6px", border=f"1px solid {S.BORDER_SUBTLE}", padding="2px",
                            ),
                            spacing="1", align="center",
                        ),
                        align="center", width="100%", padding_x="12px",
                    ),
                    position="fixed", top="0", left="0", right="0",
                    height="calc(52px + env(safe-area-inset-top, 0px))",
                    padding_top="env(safe-area-inset-top, 0px)",
                    background="rgba(14,26,23,0.95)",
                    style={"backdrop_filter": "blur(20px)", "-webkit-backdrop-filter": "blur(20px)"},
                    border_bottom=f"1px solid rgba(255,255,255,0.06)",
                    box_shadow="0 1px 0 rgba(255,255,255,0.02), 0 4px 24px rgba(0,0,0,0.3)",
                    z_index="100",
                    display=["flex", "flex", "none"],
                )),
                # ── Mobile hub tabs strip — shown below top bar when on hub with project ──
                rx.cond(
                    ~GlobalState.is_fullscreen_page
                    & (GlobalState.selected_project != "")
                    & (
                        (rx.State.router.page.path == "/hub")
                        | (rx.State.router.page.path == "/hub-operacoes")
                    ),
                    rx.box(
                        rx.hstack(
                            *[
                                rx.box(
                                    rx.text(
                                        label,
                                        font_family=S.FONT_MONO,
                                        font_size="11px",
                                        font_weight=rx.cond(GlobalState.hub_tab == value, "700", "400"),
                                        color=rx.cond(GlobalState.hub_tab == value, S.COPPER, S.TEXT_MUTED),
                                        white_space="nowrap",
                                    ),
                                    on_click=GlobalState.set_hub_tab(value),
                                    padding_x="12px",
                                    height="100%",
                                    display="flex",
                                    align_items="center",
                                    border_bottom=rx.cond(
                                        GlobalState.hub_tab == value,
                                        f"2px solid {S.COPPER}",
                                        "2px solid transparent",
                                    ),
                                    cursor="pointer",
                                    flex_shrink="0",
                                )
                                for label, value in [
                                    ("Visão", "visao_geral"),
                                    ("Dashboard", "dashboard"),
                                    ("Cronograma", "cronograma"),
                                    ("Auditoria", "auditoria"),
                                    ("Timeline", "timeline"),
                                    ("Financeiro", "financeiro"),
                                ]
                            ],
                            height="100%",
                            spacing="0",
                            align="center",
                            overflow_x="auto",
                            class_name="no-scrollbar",
                            width="100%",
                        ),
                        position="fixed",
                        top="calc(52px + env(safe-area-inset-top, 0px))",
                        left="0",
                        right="0",
                        height="40px",
                        background="rgba(14,26,23,0.97)",
                        style={"backdrop_filter": "blur(20px)", "-webkit-backdrop-filter": "blur(20px)"},
                        border_bottom=f"1px solid rgba(255,255,255,0.06)",
                        z_index="99",
                        display=["flex", "flex", "none"],
                        padding_x="4px",
                    ),
                ),
                rx.flex(
                    # Desktop Sidebar
                    rx.cond(
                        ~GlobalState.is_fullscreen_page
                        & (
                            (GlobalState.current_user_role == "Administrador")
                            | (GlobalState.current_user_role == "Engenheiro")
                            | (GlobalState.current_user_role == "Gestão-Mobile")
                            | (GlobalState.current_user_role == "engenheiro")
                            | (GlobalState.current_user_role == "")
                        ),
                        sidebar(),
                    ),
                    # Main Content Area — no fixed elements inside
                    rx.box(
                        rx.cond(
                            GlobalState.is_loading,
                            rx.vstack(
                                skeleton_kpi_grid(),
                                skeleton_chart(height="260px"),
                                skeleton_chart(height="200px"),
                                spacing="6", width="100%", padding_y="8px",
                            ),
                            rx.box(content, class_name="animate-enter"),
                        ),
                        max_width="1600px",
                        margin_x="auto",
                        width="100%",
                        overflow_x="hidden",
                        transition="all 0.3s ease-in-out",
                        padding_x=rx.cond(GlobalState.is_fullscreen_page, "0px", ["16px", "16px", "32px"]),
                        padding_top=rx.cond(
                            GlobalState.is_fullscreen_page,
                            "0px",
                            rx.cond(
                                (GlobalState.selected_project != "")
                                & (
                                    (rx.State.router.page.path == "/hub")
                                    | (rx.State.router.page.path == "/hub-operacoes")
                                ),
                                ["calc(52px + env(safe-area-inset-top,0px) + 40px + 1.5rem)", "calc(52px + env(safe-area-inset-top,0px) + 40px + 1.5rem)", "calc(56px + 2rem)"],
                                ["calc(52px + env(safe-area-inset-top,0px) + 1.5rem)", "calc(52px + env(safe-area-inset-top,0px) + 1.5rem)", "calc(56px + 2rem)"],
                            ),
                        ),
                        padding_bottom="2rem",
                        flex="1",
                        min_width="0",
                        min_height="100vh",
                    ),
                    # Analysis Dialog
                    rx.dialog.root(
                        rx.dialog.content(
                            rx.vstack(
                                rx.hstack(
                                    rx.box(
                                        rx.icon(tag="brain-circuit", size=24, color=S.COPPER),
                                        bg="rgba(212, 175, 55, 0.1)",
                                        padding="10px",
                                        border_radius="12px",
                                    ),
                                    rx.vstack(
                                        rx.dialog.title(
                                            "PLATAFORMA DE INTELIGÊNCIA OPERACIONAL",
                                            color=S.COPPER,
                                            font_family=S.FONT_TECH,
                                            font_size="0.85rem",
                                            margin="0",
                                        ),
                                        rx.text(
                                            "Análise Estratégica em Tempo Real",
                                            color=S.TEXT_MUTED,
                                            font_size="12px",
                                            margin="0",
                                        ),
                                        spacing="0",
                                        align="start",
                                    ),
                                    rx.spacer(),
                                    rx.dialog.close(
                                        rx.icon_button(
                                            rx.icon(tag="x", size=20),
                                            variant="ghost",
                                            color_scheme="amber",
                                            on_click=GlobalState.close_analysis_dialog,
                                        )
                                    ),
                                    width="100%",
                                    align="center",
                                    margin_bottom="24px",
                                ),
                                rx.scroll_area(
                                    rx.cond(
                                        GlobalState.is_analyzing,
                                        # ── Premium AI Loading Screen ──────────────────────────
                                        rx.box(
                                            # Background copper glow orbs
                                            rx.box(
                                                position="absolute",
                                                top="-60px",
                                                right="-60px",
                                                width="280px",
                                                height="280px",
                                                border_radius="50%",
                                                bg="rgba(201, 139, 42, 0.07)",
                                                filter="blur(80px)",
                                                pointer_events="none",
                                            ),
                                            rx.box(
                                                position="absolute",
                                                bottom="-40px",
                                                left="-40px",
                                                width="180px",
                                                height="180px",
                                                border_radius="50%",
                                                bg="rgba(201, 139, 42, 0.05)",
                                                filter="blur(60px)",
                                                pointer_events="none",
                                            ),
                                            # Scanner line
                                            rx.box(class_name="ai-scan-line"),
                                            # Center content
                                            rx.center(
                                                rx.vstack(
                                                    # Concentric rings with brain icon
                                                    rx.box(
                                                        rx.box(
                                                            rx.box(
                                                                rx.center(
                                                                    rx.icon(
                                                                        tag="brain-circuit",
                                                                        size=36,
                                                                        color=S.COPPER,
                                                                    ),
                                                                    width="64px",
                                                                    height="64px",
                                                                    border_radius="50%",
                                                                    bg="rgba(201, 139, 42, 0.12)",
                                                                    border=f"1px solid {S.COPPER}",
                                                                    box_shadow="0 0 30px rgba(201, 139, 42, 0.5), 0 0 60px rgba(201, 139, 42, 0.2)",
                                                                    class_name="orb-glow",
                                                                ),
                                                                width="84px",
                                                                height="84px",
                                                                border_radius="50%",
                                                                border="1px solid rgba(201, 139, 42, 0.4)",
                                                                class_name="ai-ring-1",
                                                                display="flex",
                                                                align_items="center",
                                                                justify_content="center",
                                                            ),
                                                            width="120px",
                                                            height="120px",
                                                            border_radius="50%",
                                                            border="1px solid rgba(201, 139, 42, 0.25)",
                                                            class_name="ai-ring-2",
                                                            display="flex",
                                                            align_items="center",
                                                            justify_content="center",
                                                        ),
                                                        width="160px",
                                                        height="160px",
                                                        border_radius="50%",
                                                        border="1px solid rgba(201, 139, 42, 0.15)",
                                                        class_name="ai-ring-3",
                                                        display="flex",
                                                        align_items="center",
                                                        justify_content="center",
                                                    ),
                                                    rx.text(
                                                        "A IA está processando os vetores de dados desta página...",
                                                        font_family=S.FONT_TECH,
                                                        color=S.COPPER,
                                                        font_size="18px",
                                                        font_weight="bold",
                                                        text_align="center",
                                                        margin_top="32px",
                                                    ),
                                                    rx.text(
                                                        "Cruzando indicadores e projetando recomendações táticas...",
                                                        color=S.TEXT_MUTED,
                                                        font_size="14px",
                                                        text_align="center",
                                                        class_name="fade-in-out",
                                                    ),
                                                    justify="center",
                                                    align="center",
                                                    spacing="4",
                                                ),
                                                width="100%",
                                                height="100%",
                                            ),
                                            position="relative",
                                            overflow="hidden",
                                            height="400px",
                                            width="100%",
                                        ),
                                        rx.cond(
                                            GlobalState.is_streaming,
                                            # ── Raw text while streaming — no expensive markdown re-parse ──
                                            rx.box(
                                                rx.text(
                                                    GlobalState.analysis_result,
                                                    white_space="pre-wrap",
                                                    font_family=S.FONT_BODY,
                                                    font_size="14px",
                                                    color=S.TEXT_PRIMARY,
                                                    line_height="1.9",
                                                    letter_spacing="0.01em",
                                                ),
                                                min_height="480px",
                                                padding_right="20px",
                                            ),
                                            # ── Final rendered markdown — single render after streaming ──
                                            rx.box(
                                            rx.markdown(
                                                GlobalState.analysis_result,
                                                class_name="analysis-markdown",
                                                color=S.TEXT_PRIMARY,
                                                component_map={
                                                    "h1": lambda *children, **props: rx.heading(
                                                        *children,
                                                        size="6",
                                                        color=S.COPPER,
                                                        font_family=S.FONT_TECH,
                                                        margin_top="1.2em",
                                                        margin_bottom="0.4em",
                                                        **props,
                                                    ),
                                                    "h2": lambda *children, **props: rx.heading(
                                                        *children,
                                                        size="5",
                                                        color=S.COPPER,
                                                        font_family=S.FONT_TECH,
                                                        margin_top="1.2em",
                                                        margin_bottom="0.4em",
                                                        **props,
                                                    ),
                                                    "h3": lambda *children, **props: rx.heading(
                                                        *children,
                                                        size="4",
                                                        color=S.COPPER_LIGHT,
                                                        font_family=S.FONT_TECH,
                                                        margin_top="0.8em",
                                                        margin_bottom="0.3em",
                                                        **props,
                                                    ),
                                                    "p": lambda *children, **props: rx.el.p(
                                                        *children,
                                                        style={
                                                            "color": S.TEXT_PRIMARY,
                                                            "lineHeight": "1.75",
                                                            "marginBottom": "0.6em",
                                                            "wordSpacing": "0.02em",
                                                        },
                                                    ),
                                                    "em": lambda *children, **props: rx.el.em(
                                                        *children,
                                                        style={
                                                            "color": S.TEXT_MUTED,
                                                            "fontStyle": "normal",
                                                            "fontSize": "0.92em",
                                                        },
                                                        **props,
                                                    ),
                                                    "code": lambda *children, **props: rx.el.code(
                                                        *children,
                                                        style={
                                                            "background": "rgba(212, 175, 55, 0.1)",
                                                            "color": S.COPPER_LIGHT,
                                                            "padding": "1px 6px",
                                                            "borderRadius": "4px",
                                                            "fontFamily": S.FONT_MONO,
                                                            "fontSize": "0.85em",
                                                        },
                                                        **props,
                                                    ),
                                                    "li": lambda *children, **props: rx.el.li(
                                                        *children,
                                                        style={
                                                            "color": S.TEXT_PRIMARY,
                                                            "marginBottom": "4px",
                                                            "lineHeight": "1.6",
                                                        },
                                                        **props,
                                                    ),
                                                    "strong": lambda *children, **props: rx.el.strong(
                                                        *children,
                                                        style={"color": S.COPPER_LIGHT, "fontWeight": "700"},
                                                        **props,
                                                    ),
                                                    "table": lambda *children, **props: rx.el.table(
                                                        *children,
                                                        style={
                                                            "width": "100%",
                                                            "borderCollapse": "collapse",
                                                            "marginTop": "12px",
                                                            "marginBottom": "12px",
                                                            "fontSize": "13px",
                                                            "border": f"1px solid {S.BORDER_ACCENT}",
                                                        },
                                                        **props,
                                                    ),
                                                    "thead": lambda *children, **props: rx.el.thead(
                                                        *children,
                                                        style={"backgroundColor": S.BG_ELEVATED},
                                                        **props,
                                                    ),
                                                    "tbody": lambda *children, **props: rx.el.tbody(
                                                        *children, **props
                                                    ),
                                                    "tr": lambda *children, **props: rx.el.tr(
                                                        *children,
                                                        style={"borderBottom": f"1px solid {S.BORDER_SUBTLE}"},
                                                        **props,
                                                    ),
                                                    "th": lambda *children, **props: rx.el.th(
                                                        *children,
                                                        style={
                                                            "padding": "10px 14px",
                                                            "textAlign": "left",
                                                            "fontWeight": "700",
                                                            "color": S.COPPER_LIGHT,
                                                            "backgroundColor": S.BG_ELEVATED,
                                                            "borderRight": f"1px solid {S.BORDER_SUBTLE}",
                                                            "fontSize": "12px",
                                                            "letterSpacing": "0.04em",
                                                        },
                                                        **props,
                                                    ),
                                                    "td": lambda *children, **props: rx.el.td(
                                                        *children,
                                                        style={
                                                            "padding": "9px 14px",
                                                            "color": S.TEXT_PRIMARY,
                                                            "borderRight": f"1px solid {S.BORDER_SUBTLE}",
                                                            "fontSize": "13px",
                                                            "lineHeight": "1.5",
                                                        },
                                                        **props,
                                                    ),
                                                },
                                            ),
                                                color=S.TEXT_PRIMARY,
                                                padding_right="20px",
                                            ),
                                        ),  # closes inner rx.cond (is_streaming)
                                    ),  # closes outer rx.cond (is_analyzing)
                                    max_height="70vh",
                                    type="hover",
                                    scrollbars="vertical",
                                    width="100%",
                                ),
                                width="100%",
                                spacing="0",
                            ),
                            bg="rgba(10, 31, 26, 0.95)",
                            backdrop_filter="blur(16px)",
                            border=f"1px solid {S.BORDER_ACCENT}",
                            max_width="1200px",
                            border_radius="24px",
                            padding="32px",
                            box_shadow="0 25px 50px -12px rgba(0, 0, 0, 0.5)",
                        ),
                        open=GlobalState.show_analysis_dialog,
                        on_open_change=GlobalState.set_analysis_dialog_open,
                    ),
                    direction="row",
                    width="100%",
                    min_height="100vh",
                    background="var(--bg-void)",
                    class_name="main-layout-flex",
                ),  # End rx.flex
                position="relative",
                width="100%",
                min_height="100vh",
            ),  # End authenticated rx.box
            # ── Unauthenticated view ────────────────────────────────────────────
            login_page(),
        ),  # End rx.cond(is_authenticated)
        # ── RDO Submit overlay (global — position:fixed must be at root level) ─
        _rdo_submit_overlay(),
        # ── KPI Detail Popup (global, accessible from all pages) ─────────────
        _kpi_detail_dialog(),
        # ── Meu Perfil Modal (avatar + senha) ────────────────────────────────
        _avatar_modal(),
        # ── Action AI FAB — oculto em páginas de preenchimento ───────────────
        rx.cond(
            ~GlobalState.router.page.path.contains("editar_dados")
            & ~GlobalState.router.page.path.contains("editar-dados")
            & ~GlobalState.router.page.path.contains("rdo-form")
            & ~GlobalState.router.page.path.contains("rdo_form")
            & ~GlobalState.router.page.path.contains("reembolso"),
            action_ai_fab(),
        ),
        # Outer box props
        position="relative",
        width="100%",
        min_height="100vh",
    )  # End outer rx.box
