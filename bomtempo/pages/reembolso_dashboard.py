"""
Dashboard Reembolso de Combustível — Admin/Gestor
KPIs financeiros + operacionais + tabela completa de solicitações.
Padrão visual idêntico ao rdo_dashboard.py (benchmark).
"""

import reflex as rx

from bomtempo.components.skeletons import page_centered_loader, page_loading_skeleton, table_skeleton
from bomtempo.components.tooltips import TOOLTIP_MONEY, TOOLTIP_PIE
from bomtempo.core import styles as S
from bomtempo.state.reembolso_state import ReembolsoState

# ── Email Row (foreach) ──────────────────────────────────────────────────────


def _email_row(r: dict) -> rx.Component:
    """Linha da tabela de emails de notificação."""
    return rx.table.row(
        rx.table.cell(
            rx.text(
                r.get("contract", "—"),
                font_size="13px",
                font_weight="600",
                color=S.TEXT_PRIMARY,
                font_family=S.FONT_TECH,
            ),
        ),
        rx.table.cell(
            rx.text(r.get("email", "—"), font_size="13px", color=S.TEXT_PRIMARY),
        ),
        rx.table.cell(
            rx.text(r.get("created_by", "—"), font_size="12px", color=S.TEXT_MUTED),
        ),
        rx.table.cell(
            rx.text(r.get("updated_date", "—"), font_size="11px", color=S.TEXT_MUTED),
        ),
        rx.table.cell(
            rx.button(
                rx.icon(tag="trash-2", size=14),
                on_click=ReembolsoState.delete_email(r.get("contract", ""), r.get("email", "")),
                variant="ghost",
                color_scheme="red",
                size="1",
                cursor="pointer",
                title="Remover email",
            ),
        ),
        _hover={"bg": "rgba(255,255,255,0.02)"},
        transition="background 0.15s",
    )


def _tab_emails() -> rx.Component:
    """Tab de gestão de emails de notificação."""
    return rx.vstack(
        # Formulário de adição
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="mail-plus", size=18, color=S.COPPER),
                    rx.text(
                        "Adicionar Email de Notificação",
                        font_size="14px",
                        font_weight="700",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_TECH,
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    "Emails cadastrados recebem notificação automática a cada nova solicitação de reembolso.",
                    font_size="12px",
                    color=S.TEXT_MUTED,
                    line_height="1.5",
                ),
                rx.grid(
                    rx.vstack(
                        rx.text(
                            "CONTRATO",
                            font_size="11px",
                            font_weight="700",
                            letter_spacing="0.08em",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_TECH,
                            margin_bottom="4px",
                        ),
                        rx.input(
                            placeholder="Ex: BOM-001",
                            default_value=ReembolsoState.email_new_contract,
                            on_blur=ReembolsoState.set_email_new_contract,
                            bg=S.BG_INPUT,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            border_radius="10px",
                            height="44px",
                            font_size="14px",
                            color=S.TEXT_PRIMARY,
                            padding_x="14px",
                            width="100%",
                            _focus={"border_color": S.COPPER},
                            _placeholder={"color": S.TEXT_MUTED},
                        ),
                    ),
                    rx.vstack(
                        rx.text(
                            "EMAIL",
                            font_size="11px",
                            font_weight="700",
                            letter_spacing="0.08em",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_TECH,
                            margin_bottom="4px",
                        ),
                        rx.input(
                            placeholder="responsavel@empresa.com",
                            value=ReembolsoState.email_new_address,
                            on_change=ReembolsoState.set_email_new_address,
                            type="email",
                            bg=S.BG_INPUT,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            border_radius="10px",
                            height="44px",
                            font_size="14px",
                            color=S.TEXT_PRIMARY,
                            padding_x="14px",
                            width="100%",
                            _focus={"border_color": S.COPPER},
                            _placeholder={"color": S.TEXT_MUTED},
                        ),
                    ),
                    columns=rx.breakpoints(initial="1", sm="2"),
                    spacing="3",
                    width="100%",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon(tag="plus", size=16),
                        rx.text("Adicionar", font_family=S.FONT_TECH, font_weight="700"),
                        spacing="2",
                        align="center",
                    ),
                    on_click=ReembolsoState.add_email,
                    bg=S.COPPER,
                    color="white",
                    height="44px",
                    border_radius="10px",
                    cursor="pointer",
                    _hover={"bg": S.COPPER_LIGHT},
                    align_self="flex-start",
                ),
                spacing="4",
                width="100%",
            ),
            **{**S.GLASS_CARD, "padding": "24px"},
            width="100%",
        ),
        # Tabela de emails cadastrados
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="mail", size=18, color=S.COPPER),
                    rx.text(
                        "Emails Cadastrados",
                        font_size="14px",
                        font_weight="700",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_TECH,
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="refresh-cw", size=14),
                        rx.text("Atualizar", font_size="12px", font_family=S.FONT_TECH),
                        on_click=ReembolsoState.load_emails,
                        variant="outline",
                        color_scheme="gray",
                        size="1",
                        cursor="pointer",
                        spacing="1",
                    ),
                    spacing="2",
                    align="center",
                    width="100%",
                ),
                rx.cond(
                    ReembolsoState.email_is_loading,
                    rx.center(
                        rx.hstack(
                            rx.spinner(size="2", color=S.COPPER),
                            rx.text("Carregando...", font_size="12px", color=S.TEXT_MUTED),
                            spacing="2",
                        ),
                        padding_y="24px",
                        width="100%",
                    ),
                    rx.cond(
                        ReembolsoState.email_list,
                        rx.box(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell(
                                            "Contrato",
                                            font_family=S.FONT_TECH,
                                            font_size="11px",
                                            font_weight="700",
                                            color=S.COPPER,
                                            letter_spacing="0.08em",
                                            text_transform="uppercase",
                                        ),
                                        rx.table.column_header_cell(
                                            "Email",
                                            font_family=S.FONT_TECH,
                                            font_size="11px",
                                            font_weight="700",
                                            color=S.COPPER,
                                            letter_spacing="0.08em",
                                            text_transform="uppercase",
                                        ),
                                        rx.table.column_header_cell(
                                            "Adicionado por",
                                            font_family=S.FONT_TECH,
                                            font_size="11px",
                                            font_weight="700",
                                            color=S.COPPER,
                                            letter_spacing="0.08em",
                                            text_transform="uppercase",
                                        ),
                                        rx.table.column_header_cell(
                                            "Data",
                                            font_family=S.FONT_TECH,
                                            font_size="11px",
                                            font_weight="700",
                                            color=S.COPPER,
                                            letter_spacing="0.08em",
                                            text_transform="uppercase",
                                        ),
                                        rx.table.column_header_cell(
                                            "",
                                            width="50px",
                                        ),
                                        bg="rgba(201,139,42,0.06)",
                                    ),
                                ),
                                rx.table.body(
                                    rx.foreach(ReembolsoState.email_list, _email_row),
                                ),
                                variant="ghost",
                                size="2",
                                width="100%",
                            ),
                            overflow_x="auto",
                            width="100%",
                        ),
                        rx.center(
                            rx.vstack(
                                rx.icon(tag="inbox", size=36, color=S.TEXT_MUTED),
                                rx.text(
                                    "Nenhum email cadastrado.",
                                    font_size="13px",
                                    color=S.TEXT_MUTED,
                                ),
                                rx.text(
                                    "Adicione emails acima para receber notificações.",
                                    font_size="12px",
                                    color=S.TEXT_MUTED,
                                    text_align="center",
                                ),
                                spacing="2",
                                align="center",
                            ),
                            padding_y="40px",
                            width="100%",
                        ),
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            **{**S.GLASS_CARD, "padding": "24px"},
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


# ── KPI Card ────────────────────────────────────────────────────────────────


def _kpi(
    label: str, value_component: rx.Component, icon: str, color: str = S.COPPER, subtitle: str = ""
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=20, color=color),
                    bg="rgba(201,139,42,0.12)" if color == S.COPPER else "rgba(42,157,143,0.12)",
                    padding="10px",
                    border_radius="10px",
                ),
                rx.spacer(),
                spacing="0",
                width="100%",
            ),
            value_component,
            rx.text(label, font_size="12px", color=S.TEXT_MUTED, font_weight="600"),
            rx.cond(
                subtitle != "",
                rx.text(subtitle, font_size="11px", color=S.TEXT_MUTED),
            ),
            spacing="2",
            align="start",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        flex="1",
        min_width="160px",
    )


def _kpi_text(val, color: str = S.COPPER) -> rx.Component:
    return rx.text(
        val,
        font_size="28px",
        font_weight="700",
        color=color,
        font_family=S.FONT_TECH,
        line_height="1",
    )


# ── Tabela de Solicitações ───────────────────────────────────────────────────


def _table_header_cell(text: str, width: str = "auto") -> rx.Component:
    return rx.table.column_header_cell(
        text,
        font_family=S.FONT_TECH,
        font_size="11px",
        font_weight="700",
        color=S.COPPER,
        letter_spacing="0.08em",
        text_transform="uppercase",
        width=width,
    )


def _fuel_badge(fuel: str) -> rx.Component:
    return rx.badge(
        fuel,
        color_scheme=rx.match(
            fuel,
            ("Gasolina", "yellow"),
            ("Etanol", "teal"),
            ("Diesel", "blue"),
            ("GNV", "violet"),
            "gray",
        ),
        variant="solid",
        high_contrast=True,
        radius="full",
        font_size="10px",
        font_weight="600",
    )


def _row(r: dict) -> rx.Component:
    """Linha da tabela de reembolsos."""
    return rx.table.row(
        # ID
        rx.table.cell(
            rx.text(
                rx.el.span("#", color=S.TEXT_MUTED, font_size="10px"),
                rx.el.span(r.get("id", "—"), font_weight="600"),
                font_family=S.FONT_TECH,
                font_size="12px",
                color=S.TEXT_PRIMARY,
            ),
        ),
        # Finalidade
        rx.table.cell(
            rx.text(
                r.get("purpose", "—"),
                font_size="12px",
                color=S.TEXT_PRIMARY,
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
                max_width="160px",
            ),
        ),
        # Combustível
        rx.table.cell(_fuel_badge(r.get("fuel_type", "—"))),
        # Valor Total
        rx.table.cell(
            rx.text(
                rx.el.span("R$ ", color=S.TEXT_MUTED, font_size="10px"),
                rx.el.span(r.get("total_value", "—"), font_weight="700", color=S.COPPER),
                font_family=S.FONT_TECH,
                font_size="13px",
            ),
        ),
        # km/L
        rx.table.cell(
            rx.text(
                rx.el.span(r.get("km_per_liter", "—"), font_weight="600"),
                rx.el.span(" km/L", color=S.TEXT_MUTED, font_size="10px"),
                font_family=S.FONT_TECH,
                font_size="12px",
                color=S.TEXT_PRIMARY,
            ),
        ),
        # Cidade
        rx.table.cell(
            rx.text(r.get("city", "—"), font_size="12px", color=S.TEXT_MUTED),
        ),
        # IA Verified + Score
        rx.table.cell(
            rx.hstack(
                rx.cond(
                    r.get("ai_verified", False),
                    rx.badge("IA ✓", color_scheme="teal", variant="solid", high_contrast=True, radius="full", font_size="10px"),
                    rx.badge("Manual", color_scheme="gray", variant="solid", high_contrast=True, radius="full", font_size="10px"),
                ),
                rx.cond(
                    ReembolsoState.dash_active_features.contains("ai_score"),
                    rx.cond(
                        r.get("ai_score", "—") != "—",
                        rx.badge(
                            r.get("ai_score", ""),
                            color_scheme=rx.match(
                                r.get("ai_score", "0"),
                                ("100", "teal"), ("99", "teal"), ("98", "teal"), ("97", "teal"),
                                ("96", "teal"), ("95", "teal"), ("90", "teal"), ("80", "teal"),
                                "amber",
                            ),
                            variant="soft",
                            radius="full",
                            font_size="10px",
                            title="Score IA",
                        ),
                        rx.fragment(),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    ReembolsoState.dash_active_features.contains("gps_validation"),
                    rx.cond(
                        r.get("has_gps", "false") == "true",
                        rx.icon(tag="map-pin", size=12, color=S.PATINA, title="GPS registrado"),
                        rx.fragment(),
                    ),
                    rx.fragment(),
                ),
                spacing="1",
                align="center",
            ),
        ),
        # Data (pré-formatada no state como date_short)
        rx.table.cell(
            rx.text(
                r.get("date_short", "—"),
                font_size="11px",
                color=S.TEXT_MUTED,
                font_family=S.FONT_TECH,
            ),
        ),
        # PDF Download
        rx.table.cell(
            rx.cond(
                r.get("pdf_report_url", "") != "",
                rx.link(
                    rx.icon(tag="file-down", size=16, color=S.PATINA),
                    href=r.get("pdf_report_url", "#"),
                    is_external=True,
                    title="Baixar PDF",
                ),
                rx.icon(tag="file-x", size=16, color=S.TEXT_MUTED),
            ),
        ),
        _hover={"bg": "rgba(255,255,255,0.02)"},
        transition="background 0.15s",
    )


def _tabela_reembolsos() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Cabeçalho da seção
            rx.hstack(
                rx.icon(tag="receipt", size=18, color=S.COPPER),
                rx.text(
                    "Solicitações de Reembolso",
                    font_size="14px",
                    font_weight="700",
                    color=S.TEXT_PRIMARY,
                    font_family=S.FONT_TECH,
                ),
                rx.spacer(),
                rx.text(
                    ReembolsoState.dash_total_registros.to_string(),
                    font_size="12px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_TECH,
                ),
                rx.text("registros", font_size="12px", color=S.TEXT_MUTED),
                spacing="2",
                align="center",
                width="100%",
            ),
            # Loading / Empty / Table
        rx.cond(
            ReembolsoState.dash_is_loading,
            table_skeleton(rows=5),
                rx.cond(
                    ReembolsoState.reembolsos_list,
                    rx.box(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    _table_header_cell("ID", "60px"),
                                    _table_header_cell("Finalidade"),
                                    _table_header_cell("Combustível", "110px"),
                                    _table_header_cell("Total", "110px"),
                                    _table_header_cell("km/L", "90px"),
                                    _table_header_cell("Cidade", "100px"),
                                    _table_header_cell("IA", "70px"),
                                    _table_header_cell("Data", "95px"),
                                    _table_header_cell("PDF", "50px"),
                                    bg="rgba(201,139,42,0.06)",
                                ),
                            ),
                            rx.table.body(
                                rx.foreach(ReembolsoState.reembolsos_list, _row),
                            ),
                            variant="ghost",
                            size="2",
                            width="100%",
                        ),
                        overflow_x="auto",
                        width="100%",
                    ),
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="inbox", size=40, color=S.TEXT_MUTED),
                            rx.text(
                                "Nenhum reembolso cadastrado.",
                                font_size="14px",
                                color=S.TEXT_MUTED,
                            ),
                            spacing="3",
                            align="center",
                        ),
                        padding_y="48px",
                        width="100%",
                    ),
                ),
            ),
            spacing="4",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "24px"},
        width="100%",
    )


# ── Alertas de Anomalia ──────────────────────────────────────────────────────


def _alerta_row(r: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.icon(tag="alert-triangle", size=16, color=S.WARNING),
            rx.vstack(
                rx.text(
                    rx.el.span("Desvio: ", color=S.WARNING, font_weight="700"),
                    rx.el.span(r.get("purpose", "—"), color=S.TEXT_PRIMARY),
                    font_size="12px",
                ),
                rx.text(
                    rx.el.span("km/L: ", color=S.TEXT_MUTED),
                    rx.el.span(r.get("km_per_liter", "—"), font_weight="700", color=S.TEXT_PRIMARY),
                    rx.el.span("  |  Desvio frota: ", color=S.TEXT_MUTED),
                    rx.el.span(
                        r.get("deviation_from_fleet_avg", "—"), font_weight="700", color=S.DANGER
                    ),
                    rx.el.span("%", color=S.TEXT_MUTED),
                    font_size="11px",
                    font_family=S.FONT_TECH,
                ),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        bg=S.WARNING_BG,
        border=f"1px solid {S.WARNING}",
        border_radius="10px",
        padding="12px",
        width="100%",
    )


def _painel_alertas() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="alert-circle", size=18, color=S.WARNING),
                rx.text(
                    "Alertas de Eficiência",
                    font_size="14px",
                    font_weight="700",
                    color=S.TEXT_PRIMARY,
                    font_family=S.FONT_TECH,
                ),
                rx.badge(
                    "ANOMALIAS",
                    color_scheme="yellow",
                    variant="soft",
                    radius="full",
                    font_size="10px",
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.text(
                "Registros com consumo km/L com desvio > 30% da média da frota.",
                font_size="11px",
                color=S.TEXT_MUTED,
            ),
            rx.cond(
                ReembolsoState.dash_alertas,
                rx.vstack(
                    rx.foreach(ReembolsoState.dash_alertas, _alerta_row),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.icon(tag="check-circle", size=16, color=S.SUCCESS),
                    rx.text(
                        "Sem anomalias detectadas.",
                        font_size="12px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="2",
                    align="center",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "24px"},
        width="100%",
    )


# ── Gráfico: Gasto Mensal ────────────────────────────────────────────────────


def _grafico_mensal() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="trending-up", size=18, color=S.COPPER),
                rx.text(
                    "Gasto Mensal (R$)",
                    font_size="14px",
                    font_weight="700",
                    color=S.TEXT_PRIMARY,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
            ),
            rx.recharts.bar_chart(
                rx.recharts.bar(
                    data_key="total",
                    fill=S.COPPER,
                    radius=[6, 6, 0, 0],
                    max_bar_size=48,
                ),
                rx.recharts.x_axis(
                    data_key="mes",
                    tick={"fontSize": 9, "fill": S.TEXT_MUTED},
                ),
                rx.recharts.y_axis(
                    tick={"fontSize": 9, "fill": S.TEXT_MUTED},
                    width=55,
                ),
                rx.recharts.cartesian_grid(
                    stroke_dasharray="3 3",
                    stroke="rgba(255,255,255,0.05)",
                ),
                TOOLTIP_MONEY,
                data=ReembolsoState.dash_chart_mensal,
                height=220,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        flex="1",
        min_width="300px",
    )


# ── Gráfico: Combustível ─────────────────────────────────────────────────────


def _grafico_combustivel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="pie-chart", size=18, color=S.PATINA),
                rx.text(
                    "Por Combustível",
                    font_size="14px",
                    font_weight="700",
                    color=S.TEXT_PRIMARY,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
            ),
            rx.recharts.pie_chart(
                rx.recharts.pie(
                    data=ReembolsoState.dash_chart_combustivel,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    inner_radius=45,
                    outer_radius=85,
                    padding_angle=3,
                ),
                rx.recharts.legend(icon_type="circle"),
                TOOLTIP_PIE,
                height=250,
                width="100%",
            ),
            spacing="3",
            width="100%",
            align="center",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        flex="1",
        min_width="260px",
    )


# ── Gráfico: AI Score (feature: ai_score) ───────────────────────────────────


def _grafico_score() -> rx.Component:
    """Distribuição de Score de Confiabilidade IA — só aparece se feature ativa."""
    return rx.cond(
        ReembolsoState.dash_active_features.contains("ai_score"),
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="shield-check", size=18, color=S.SUCCESS),
                    rx.text(
                        "Score de Confiabilidade",
                        font_size="14px",
                        font_weight="700",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_TECH,
                    ),
                    rx.badge("AI SCORE", color_scheme="teal", variant="soft", radius="full", font_size="10px"),
                    spacing="2",
                    align="center",
                ),
                rx.recharts.pie_chart(
                    rx.recharts.pie(
                        data=ReembolsoState.dash_chart_score,
                        data_key="value",
                        name_key="name",
                        cx="50%",
                        cy="50%",
                        inner_radius=40,
                        outer_radius=80,
                        padding_angle=3,
                    ),
                    rx.recharts.legend(icon_type="circle"),
                    TOOLTIP_PIE,
                    height=230,
                    width="100%",
                ),
                spacing="3",
                width="100%",
                align="center",
            ),
            **{**S.GLASS_CARD, "padding": "20px"},
            flex="1",
            min_width="240px",
        ),
        rx.fragment(),
    )


# ── Gráfico: GPS Coverage (feature: gps_validation) ─────────────────────────


def _grafico_gps() -> rx.Component:
    """Cobertura de GPS nos reembolsos — só aparece se feature ativa."""
    return rx.cond(
        ReembolsoState.dash_active_features.contains("gps_validation"),
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="map-pin", size=18, color=S.PATINA),
                    rx.text(
                        "Cobertura GPS",
                        font_size="14px",
                        font_weight="700",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_TECH,
                    ),
                    rx.badge("GPS", color_scheme="teal", variant="soft", radius="full", font_size="10px"),
                    spacing="2",
                    align="center",
                ),
                rx.recharts.pie_chart(
                    rx.recharts.pie(
                        data=ReembolsoState.dash_chart_gps,
                        data_key="value",
                        name_key="name",
                        cx="50%",
                        cy="50%",
                        inner_radius=40,
                        outer_radius=80,
                        padding_angle=3,
                    ),
                    rx.recharts.legend(icon_type="circle"),
                    TOOLTIP_PIE,
                    height=230,
                    width="100%",
                ),
                spacing="3",
                width="100%",
                align="center",
            ),
            **{**S.GLASS_CARD, "padding": "20px"},
            flex="1",
            min_width="240px",
        ),
        rx.fragment(),
    )


# ── Tab: Visão Geral ─────────────────────────────────────────────────────────


def _tab_visao_geral() -> rx.Component:
    return rx.cond(
        ReembolsoState.dash_is_loading,
        page_loading_skeleton(),
        rx.vstack(
            # ── KPI Cards ───────────────────────────────────────────────────────
            rx.flex(
                _kpi(
                    "Total Reembolsado",
                    rx.hstack(
                        rx.text(
                            "R$",
                            font_size="14px",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_TECH,
                            margin_top="6px",
                        ),
                        _kpi_text(ReembolsoState.dash_total_gasto.to_string(), S.COPPER),
                        spacing="1",
                        align="end",
                    ),
                    "dollar-sign",
                    color=S.COPPER,
                ),
                _kpi(
                    "Média km/L",
                    rx.hstack(
                        _kpi_text(ReembolsoState.dash_media_kml.to_string(), S.PATINA),
                        rx.text("km/L", font_size="12px", color=S.TEXT_MUTED, margin_top="10px"),
                        spacing="1",
                        align="end",
                    ),
                    "gauge",
                    color=S.PATINA,
                    subtitle="Eficiência média da frota",
                ),
                _kpi(
                    "Custo médio/km",
                    rx.hstack(
                        rx.text(
                            "R$",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_TECH,
                            margin_top="10px",
                        ),
                        _kpi_text(ReembolsoState.dash_media_custo_km.to_string(), S.COPPER_LIGHT),
                        spacing="1",
                        align="end",
                    ),
                    "map-pin",
                    color=S.COPPER_LIGHT,
                    subtitle="Custo por km rodado",
                ),
                _kpi(
                    "Total de Solicitações",
                    _kpi_text(ReembolsoState.dash_total_registros.to_string(), S.PATINA),
                    "receipt",
                    color=S.PATINA,
                ),
                gap="16px",
                flex_wrap="wrap",
                width="100%",
            ),
            # ── Gráficos principais ─────────────────────────────────────────────
            rx.flex(
                _grafico_mensal(),
                _grafico_combustivel(),
                gap="16px",
                flex_wrap="wrap",
                width="100%",
            ),
            # ── Gráficos feature-gated ──────────────────────────────────────────
            rx.cond(
                ReembolsoState.dash_active_features.contains("ai_score")
                | ReembolsoState.dash_active_features.contains("gps_validation"),
                rx.flex(
                    _grafico_score(),
                    _grafico_gps(),
                    gap="16px",
                    flex_wrap="wrap",
                    width="100%",
                ),
                rx.fragment(),
            ),
            # ── Alertas + Tabela ─────────────────────────────────────────────────
            _painel_alertas(),
            _tabela_reembolsos(),
            spacing="6",
            width="100%",
            align="start",
        ),
    )


# ── Page ────────────────────────────────────────────────────────────────────


def reembolso_dashboard_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            # ── Header ──────────────────────────────────────────────────────
            rx.hstack(
                rx.vstack(
                    rx.text(
                        "REEMBOLSO DE COMBUSTÍVEL",
                        font_size="22px",
                        font_weight="700",
                        font_family=S.FONT_TECH,
                        color=S.COPPER,
                        letter_spacing="0.08em",
                    ),
                    rx.text(
                        "Dashboard Financeiro & Operacional",
                        font_size="13px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.select(
                    ["Todos os Contratos", "BOM-001", "BOM-002", "BOM-003", "BOM-004"],
                    value=ReembolsoState.dash_filtro_contrato,
                    on_change=lambda v: [
                        ReembolsoState.set_dash_filtro_contrato(v),
                        ReembolsoState.load_dashboard(),
                    ],
                    variant="surface",
                    color_scheme="gray",
                    size="2",
                    radius="large",
                ),
                rx.select(
                    [
                        "Todos os Motivos",
                        "Supervisão de campo",
                        "Emergência",
                        "Reunião externa",
                        "Deslocamento para obra",
                        "Visita a cliente",
                    ],
                    value=ReembolsoState.dash_filtro_projeto,
                    on_change=lambda v: [
                        ReembolsoState.set_dash_filtro_projeto(v),
                        ReembolsoState.load_dashboard(),
                    ],
                    variant="surface",
                    color_scheme="gray",
                    size="2",
                    radius="large",
                ),
                rx.button(
                    rx.icon(tag="refresh-cw", size=16),
                    rx.text("Atualizar", font_size="13px", font_family=S.FONT_TECH),
                    on_click=ReembolsoState.load_dashboard,
                    variant="outline",
                    color_scheme="yellow",
                    size="2",
                    cursor="pointer",
                    spacing="2",
                ),
                align="center",
                width="100%",
            ),
            # ── Tabs ────────────────────────────────────────────────────────
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon(tag="bar-chart-3", size=14, color=S.TEXT_PRIMARY),
                            rx.text(
                                "Visão Geral",
                                font_family=S.FONT_TECH,
                                font_size="13px",
                                font_weight="600",
                                color=S.TEXT_PRIMARY,
                            ),
                            spacing="2",
                            align="center",
                        ),
                        value="geral",
                        cursor="pointer",
                        style={"color": S.TEXT_PRIMARY},
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon(tag="mail", size=14, color=S.TEXT_PRIMARY),
                            rx.text(
                                "E-mails de Notificação",
                                font_family=S.FONT_TECH,
                                font_size="13px",
                                font_weight="600",
                                color=S.TEXT_PRIMARY,
                            ),
                            spacing="2",
                            align="center",
                        ),
                        value="emails",
                        cursor="pointer",
                        style={"color": S.TEXT_PRIMARY},
                        on_click=ReembolsoState.load_emails,
                    ),
                    bg=S.BG_ELEVATED,
                    border_radius="12px",
                    padding="4px",
                    margin_bottom="24px",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    style={
                        "--tabs-trigger-active-color": S.COPPER,
                        "--tabs-trigger-color": S.TEXT_MUTED,
                    },
                ),
                rx.tabs.content(
                    rx.cond(
                        ReembolsoState.dash_is_loading,
                        page_centered_loader(
                            "CARREGANDO REEMBOLSOS",
                            "Verificando solicitações e status financeiro...",
                            "receipt",
                        ),
                        _tab_visao_geral(),
                    ),
                    value="geral",
                ),
                rx.tabs.content(_tab_emails(), value="emails"),
                default_value="geral",
                width="100%",
            ),
            spacing="6",
            width="100%",
            align="start",
        ),
        padding=["16px", "20px", "32px"],
        width="100%",
        max_width="1400px",
        margin="0 auto",
    )
