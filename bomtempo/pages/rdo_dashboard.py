"""
RDO Dashboard 360° — KPIs e gráficos para Admin/Gestor
"""

import reflex as rx

from bomtempo.components.tooltips import TOOLTIP_GENERIC, TOOLTIP_PIE
from bomtempo.components.skeletons import rdo_sync_loader
from bomtempo.core import styles as S
from bomtempo.state.rdo_dashboard_state import RDODashboardState


# ── KPI Card ────────────────────────────────────────────────
def _kpi(label: str, value, icon: str, color: str = S.COPPER, subtitle: str = "") -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=20, color=color),
                    bg=(
                        f"rgba({','.join(str(int(color.lstrip('#')[i:i+2], 16)) for i in (0, 2, 4))}, 0.12)"
                        if color.startswith("#")
                        else "rgba(201,139,42,0.12)"
                    ),
                    padding="10px",
                    border_radius="10px",
                ),
                rx.spacer(),
                spacing="0",
                width="100%",
            ),
            rx.text(
                value,
                font_size="28px",
                font_weight="700",
                color=color,
                font_family=S.FONT_TECH,
                line_height="1",
            ),
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


# ── Gráfico linha: RDOs por dia ─────────────────────────────
def _chart_por_dia() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="trending-up", size=18, color=S.COPPER),
                rx.text(
                    "RDOs por Dia",
                    font_size="14px",
                    font_weight="700",
                    color=S.TEXT_PRIMARY,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
            ),
            rx.recharts.area_chart(
                rx.recharts.area(
                    data_key="rdos",
                    stroke=S.COPPER,
                    fill="rgba(201,139,42,0.15)",
                    stroke_width=2,
                    is_animation_active=False,
                ),
                rx.recharts.x_axis(
                    data_key="data", tick={"fontSize": 9, "fill": S.TEXT_MUTED}, tick_count=7
                ),
                rx.recharts.y_axis(tick={"fontSize": 9, "fill": S.TEXT_MUTED}, width=25),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.05)"),
                TOOLTIP_GENERIC,
                data=RDODashboardState.grafico_por_dia,
                height=200,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        class_name="chart-enter",
        flex="2",
        min_width="300px",
    )


# ── Gráfico pie: Clima ──────────────────────────────────────
def _chart_clima() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="cloud-sun", size=18, color=S.PATINA),
                rx.text(
                    "Clima nos RDOs",
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
                    data=RDODashboardState.grafico_clima,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    outer_radius=75,
                    inner_radius=40,
                    fill=S.COPPER,
                    label=True,
                    is_animation_active=False,
                ),
                TOOLTIP_PIE,
                height=200,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        flex="1",
        min_width="220px",
    )


# ── Gráfico pie: Atividades por Status ──────────────────────
def _chart_atividades_status() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="clipboard-list", size=18, color="#8B5CF6"),
                rx.text(
                    "Atividades por Status",
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
                    data=RDODashboardState.grafico_atividades_status,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    outer_radius=75,
                    inner_radius=40,
                    fill="#8B5CF6",
                    label=True,
                    is_animation_active=False,
                ),
                TOOLTIP_PIE,
                height=200,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        flex="1",
        min_width="220px",
    )


# ── Gráfico barras: Atividades por Contrato ──────────────────
def _chart_atividades_por_contrato() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="bar-chart-2", size=18, color=S.PATINA),
                rx.text(
                    "Atividades por Contrato",
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
                    data_key="atividades",
                    fill=S.PATINA,
                    radius=[4, 4, 0, 0],
                    is_animation_active=False,
                ),
                rx.recharts.x_axis(data_key="contrato", tick={"fontSize": 9, "fill": S.TEXT_MUTED}),
                rx.recharts.y_axis(tick={"fontSize": 9, "fill": S.TEXT_MUTED}, width=25),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.05)"),
                TOOLTIP_PIE,
                data=RDODashboardState.grafico_atividades_por_contrato,
                height=200,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        flex="1",
        min_width="260px",
    )


# ── Filtros ─────────────────────────────────────────────────
def _filtros() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.icon(tag="filter", size=16, color=S.TEXT_MUTED),
            rx.text("Filtros:", font_size="13px", color=S.TEXT_MUTED, font_weight="600"),
            spacing="1",
            align="center",
        ),
        rx.select(
            RDODashboardState.contratos_disponiveis,
            value=RDODashboardState.filtro_contrato,
            on_change=RDODashboardState.set_filtro_contrato,
            placeholder="Contrato",
            width="160px",
        ),
        rx.select(
            ["7", "14", "30", "60", "90"],
            value=RDODashboardState.filtro_periodo,
            on_change=RDODashboardState.set_filtro_periodo,
            placeholder="Período (dias)",
            width="140px",
        ),
        rx.text(
            RDODashboardState.filtro_periodo + " dias",
            font_size="12px",
            color=S.TEXT_MUTED,
        ),
        spacing="3",
        align="center",
        flex_wrap="wrap",
    )


# ── Tabela de últimos RDOs ───────────────────────────────────
def _rdo_row(rdo: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(rdo["id_rdo"], font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_TECH),
        ),
        rx.table.cell(
            rx.badge(rdo["contrato"], color_scheme="yellow", variant="soft", size="1"),
        ),
        rx.table.cell(
            rx.text(rdo["data"], font_size="12px", color=S.TEXT_PRIMARY),
        ),
        rx.table.cell(
            rx.text(rdo["turno"], font_size="12px", color=S.TEXT_MUTED),
        ),
        rx.table.cell(
            rx.cond(
                rdo["pdf_url"],
                rx.link(
                    rx.button(
                        rx.icon(tag="download", size=14),
                        "PDF",
                        size="1",
                        variant="soft",
                        color_scheme="yellow",
                    ),
                    href=rdo["pdf_url"],
                    is_external=True,
                ),
                rx.text("—", font_size="12px", color=S.TEXT_MUTED),
            ),
        ),
        style={"border_bottom": f"1px solid {S.BORDER_SUBTLE}"},
        _hover={"background": "rgba(255,255,255,0.02)"},
    )


def _tabela_rdos() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="table", size=18, color=S.COPPER),
                rx.text(
                    "Últimos Relatórios",
                    font_size="14px",
                    font_weight="700",
                    color=S.TEXT_PRIMARY,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            rx.scroll_area(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            *[
                                rx.table.column_header_cell(
                                    label,
                                    style={
                                        "font_size": "11px",
                                        "color": S.TEXT_MUTED,
                                        "text_transform": "uppercase",
                                        "letter_spacing": "0.06em",
                                        "padding": "10px 12px",
                                        "font_weight": "600",
                                        "background": "rgba(255,255,255,0.02)",
                                    },
                                )
                                for label in ["ID RDO", "Contrato", "Data", "Turno", "Ação"]
                            ],
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(RDODashboardState.rdos, _rdo_row),
                    ),
                    width="100%",
                    style={"border_collapse": "collapse"},
                ),
                type="hover",
                scrollbars="horizontal",
                max_height="320px",
            ),
            spacing="3",
            width="100%",
        ),
        **{**S.GLASS_CARD, "padding": "20px"},
        width="100%",
    )


# ── PÁGINA PRINCIPAL ─────────────────────────────────────────
def rdo_dashboard_page() -> rx.Component:
    return rx.box(
        rx.cond(
            RDODashboardState.is_loading,
            rdo_sync_loader(),
            rx.vstack(

                # Header
                rx.hstack(
                    rx.box(
                        rx.icon(tag="chart-bar", size=28, color=S.COPPER),
                        bg=S.COPPER_GLOW,
                        padding="10px",
                        border_radius="12px",
                    ),
                    rx.vstack(
                        rx.text("RDO ANALYTICS", **S.PAGE_TITLE_STYLE),
                        rx.text(
                            "Dashboard 360° · Relatórios Diários de Obra", **S.PAGE_SUBTITLE_STYLE
                        ),
                        spacing="0",
                        align="start",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="refresh-cw", size=16),
                        "Atualizar",
                        on_click=RDODashboardState.load_dashboard,
                        variant="outline",
                        color_scheme="yellow",
                        size="2",
                        is_loading=RDODashboardState.is_loading,
                    ),
                    spacing="4",
                    width="100%",
                    align="center",
                    margin_bottom="16px",
                ),

                # Filtros
                _filtros(),

                # KPI Row 1 — Cabeçalho
                rx.flex(
                    _kpi("Total de RDOs", RDODashboardState.kpi_total, "file-text", S.COPPER),
                    _kpi("Obras com RDO", RDODashboardState.kpi_obras_ativas, "building", S.PATINA),
                    _kpi("RDOs Hoje", RDODashboardState.kpi_hoje, "calendar-check", "#3B82F6"),
                    _kpi(
                        "Última Data",
                        RDODashboardState.kpi_ultima_data,
                        "clock",
                        S.COPPER_LIGHT,
                        subtitle="Mais recente",
                    ),
                    gap="16px",
                    flex_wrap="wrap",
                    width="100%",
                ),

                # KPI Row 2 — Detalhes (atividades, fotos, checkins)
                rx.flex(
                    _kpi(
                        "Atividades",
                        RDODashboardState.kpi_atividades,
                        "clipboard-list",
                        "#8B5CF6",
                        subtitle="Serviços registrados",
                    ),
                    _kpi(
                        "Fotos",
                        RDODashboardState.kpi_fotos,
                        "camera",
                        S.COPPER,
                        subtitle="Registros fotográficos",
                    ),
                    _kpi(
                        "Check-ins GPS",
                        RDODashboardState.kpi_checkins,
                        "map-pin",
                        S.PATINA,
                        subtitle="RDOs com localização",
                    ),
                    gap="16px",
                    flex_wrap="wrap",
                    width="100%",
                ),

                # Gráficos row 1: Timeline + Clima
                rx.flex(
                    _chart_por_dia(),
                    _chart_clima(),
                    gap="16px",
                    flex_wrap="wrap",
                    width="100%",
                    align="start",
                ),

                # Gráficos row 2: Atividades Status + Atividades por Contrato
                rx.flex(
                    _chart_atividades_status(),
                    _chart_atividades_por_contrato(),
                    gap="16px",
                    flex_wrap="wrap",
                    width="100%",
                    align="start",
                ),

                # Tabela
                _tabela_rdos(),

                width="100%",
                padding=["16px", "24px", "32px"],
                spacing="4",
            ),
        ),
        width="100%",
    )
