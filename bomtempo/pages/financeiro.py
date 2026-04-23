import reflex as rx

from bomtempo.components.charts import (
    dark_cartesian_grid,
    kpi_card,
    money_formatter_js,
    pie_chart_donut,
)
from bomtempo.components.tooltips import TOOLTIP_SPLIT
from bomtempo.components.skeletons import page_loading_skeleton
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState


# ── Header ────────────────────────────────────────────────────────────────────

def finance_header() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text("Financeiro", **S.PAGE_TITLE_STYLE),
            rx.text("Visão Agregada · Custos por Contrato e Categoria", **S.PAGE_SUBTITLE_STYLE),
            spacing="1",
        ),
        rx.spacer(),
        rx.hstack(
            rx.icon(tag="filter", size=16, color=S.COPPER),
            rx.el.select(
                rx.foreach(
                    GlobalState.project_filter_options,
                    lambda opt: rx.el.option(
                        opt, value=opt, style={"background": S.BG_ELEVATED, "color": S.COPPER}
                    ),
                ),
                value=GlobalState.fin_project_filter,
                on_change=GlobalState.set_fin_project_filter,
                background="transparent",
                color="white",
                border="none",
                outline="none",
                font_size="14px",
                font_family=S.FONT_MONO,
                padding="8px",
                cursor="pointer",
            ),
            bg=S.COPPER_GLOW,
            padding_x="12px",
            padding_y="6px",
            border_radius="12px",
            border=f"1px solid {S.BORDER_ACCENT}",
            align="center",
        ),
        width="100%",
        align="end",
        class_name="animate-enter",
    )


# ── KPI Grid principal ────────────────────────────────────────────────────────

def finance_kpi_grid() -> rx.Component:
    return rx.grid(
        kpi_card(
            title="Total Previsto",
            value=GlobalState.financeiro_contratado_fmt,
            icon="wallet",
            is_money=True,
            on_click=GlobalState.set_show_kpi_detail("total_contratado"),
        ),
        kpi_card(
            title="Total Executado",
            value=GlobalState.financeiro_realizado_fmt,
            icon="dollar-sign",
            trend="Realizado",
            trend_type="positive",
            is_money=True,
            on_click=GlobalState.set_show_kpi_detail("total_medido"),
        ),
        kpi_card(
            title="Saldo a Executar",
            value=GlobalState.margem_bruta_fmt,
            icon="trending-up",
            trend="Pendente",
            trend_type="negative",
            is_money=True,
            on_click=GlobalState.set_show_kpi_detail("saldo_medir"),
        ),
        kpi_card(
            title="% Executado",
            value=GlobalState.margem_pct_fmt,
            icon="percent",
            trend="do total previsto",
            trend_type="neutral",
        ),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="6",
        width="100%",
    )


# ── KPI Strip secundário ──────────────────────────────────────────────────────

def _fin_mini_kpi(icon_tag: str, label: str, value, color: str = S.TEXT_MUTED) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.icon(tag=icon_tag, size=14, color=color),
            width="30px", height="30px",
            bg="rgba(255,255,255,0.04)", border_radius="4px", flex_shrink="0",
        ),
        rx.vstack(
            rx.text(label, font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                    text_transform="uppercase", letter_spacing="0.08em"),
            rx.text(value, font_size="1rem", font_weight="700", color=color,
                    font_family=S.FONT_TECH, line_height="1"),
            spacing="0",
        ),
        spacing="3", align="center",
        padding="12px 16px",
        border_radius=S.R_CONTROL,
        border=f"1px solid {S.BORDER_SUBTLE}",
        bg="rgba(255,255,255,0.02)",
        flex="1", min_width="140px",
    )


def finance_secondary_kpis() -> rx.Component:
    return rx.flex(
        _fin_mini_kpi("package", "Total de Itens", GlobalState.fin_total_itens.to_string(), color="var(--text-main)"),
        _fin_mini_kpi("check-circle-2", "Concluídos", GlobalState.fin_itens_concluidos.to_string(), color="#22c55e"),
        _fin_mini_kpi("loader", "Em Andamento", GlobalState.fin_itens_andamento.to_string(), color="#3B82F6"),
        _fin_mini_kpi("clock", "Previstos", GlobalState.fin_itens_previstos.to_string(), color=S.COPPER),
        _fin_mini_kpi("pie-chart", "% Concluído", GlobalState.fin_pct_concluido_fmt, color="#22c55e"),
        _fin_mini_kpi("building-2", "Contratos", GlobalState.fin_contratos_com_custo.to_string(), color=S.COPPER),
        _fin_mini_kpi("tag", "Top Categoria", GlobalState.fin_top_categoria, color=S.COPPER),
        gap="8px",
        flex_wrap="wrap",
        width="100%",
    )


# ── Status donut ──────────────────────────────────────────────────────────────

def finance_status_chart() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="pie-chart", size=14, color=S.COPPER),
                rx.text("Status dos Itens", font_family=S.FONT_TECH, font_size="1.1rem",
                        font_weight="700", color="white"),
                spacing="2", align="center", margin_bottom="20px",
            ),
            rx.box(
                pie_chart_donut(
                    data=GlobalState.fin_status_dist,
                    name_key="name",
                    value_key="value",
                    height=240,
                    use_data_fill=True,
                ),
                width="100%", height="240px",
                display="flex", align_items="center", justify_content="center",
            ),
            rx.vstack(
                rx.foreach(
                    GlobalState.fin_status_dist,
                    lambda item: rx.hstack(
                        rx.hstack(
                            rx.box(width="10px", height="10px", border_radius="2px", bg=item["fill"]),
                            rx.text(item["name"], font_size="0.8rem", font_weight="700",
                                    color=S.TEXT_MUTED, text_transform="uppercase",
                                    letter_spacing="0.05em"),
                            align="center", spacing="3",
                        ),
                        rx.spacer(),
                        rx.text(item["value"].to_string(), font_family=S.FONT_MONO,
                                font_size="0.85rem", color="white", font_weight="700"),
                        width="100%", padding="8px 12px",
                        border_radius="6px", bg="rgba(255,255,255,0.02)",
                        border="1px solid rgba(255,255,255,0.03)",
                    ),
                ),
                spacing="2", width="100%", margin_top="12px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
    )


# ── Bar chart por categoria ───────────────────────────────────────────────────

def finance_cost_chart() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="bar-chart-2", size=14, color=S.COPPER),
                rx.text("Previsto × Executado por Categoria", font_family=S.FONT_TECH,
                        font_size="1.1rem", font_weight="700", color="white"),
                spacing="2", align="center", margin_bottom="20px",
            ),
            rx.box(
                rx.recharts.bar_chart(
                    dark_cartesian_grid(),
                    rx.recharts.x_axis(
                        type_="number",
                        stroke=S.TEXT_MUTED,
                        font_size=10,
                        tick_formatter=money_formatter_js(),
                    ),
                    rx.recharts.y_axis(
                        data_key="cockpit",
                        type_="category",
                        stroke=S.TEXT_PRIMARY,
                        font_size=11,
                        width=110,
                    ),
                    TOOLTIP_SPLIT,
                    rx.recharts.legend(
                        wrapper_style={"fontSize": "11px", "fontFamily": "'JetBrains Mono', monospace", "color": "#889999"},
                    ),
                    rx.recharts.bar(
                        data_key="total_contratado",
                        name="Previsto",
                        fill=S.COPPER,
                        radius=[0, 4, 4, 0],
                    ),
                    rx.recharts.bar(
                        data_key="total_realizado",
                        name="Executado",
                        fill="#22c55e",
                        radius=[0, 4, 4, 0],
                    ),
                    data=GlobalState.financeiro_cockpit_chart,
                    layout="vertical",
                    height=300,
                    margin={"left": 20, "right": 60},
                ),
                width="100%", height="300px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
    )


# ── S-Curve acumulada ─────────────────────────────────────────────────────────

def finance_scurve_chart() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="trending-up", size=14, color=S.COPPER),
                rx.text("Curva S — Avanço Financeiro Acumulado por Categoria",
                        font_family=S.FONT_TECH, font_size="1.1rem", font_weight="700", color="white"),
                spacing="2", align="center", margin_bottom="20px",
            ),
            rx.box(
                rx.recharts.area_chart(
                    dark_cartesian_grid(),
                    rx.recharts.x_axis(
                        data_key="cockpit",
                        stroke=S.TEXT_MUTED,
                        font_size=11,
                    ),
                    rx.recharts.y_axis(
                        stroke=S.TEXT_PRIMARY,
                        font_size=11,
                        tick_formatter=money_formatter_js(),
                    ),
                    TOOLTIP_SPLIT,
                    rx.recharts.legend(
                        wrapper_style={"fontSize": "11px", "fontFamily": "'JetBrains Mono', monospace", "color": "#889999"},
                    ),
                    rx.recharts.area(
                        data_key="cumulative_planned",
                        name="Previsto Acum.",
                        stroke=S.COPPER,
                        fill=f"{S.COPPER}30",
                        stroke_width=2,
                    ),
                    rx.recharts.area(
                        data_key="cumulative_actual",
                        name="Executado Acum.",
                        stroke="#22c55e",
                        fill="rgba(34,197,94,0.15)",
                        stroke_width=3,
                    ),
                    data=GlobalState.financeiro_scurve_chart,
                    height=320,
                ),
                width="100%", height="320px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
        width="100%",
    )


# ── Tabela detalhada por categoria ────────────────────────────────────────────

def finance_table_row(item: dict) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.text(item["cockpit"], font_weight="700", font_size="12px", color="white",
                    font_family=S.FONT_BODY),
            padding="14px 16px",
        ),
        rx.el.td(
            rx.text(
                "R$ " + item["total_contratado"].to_string(),
                font_family=S.FONT_MONO, font_size="12px", color=S.COPPER,
            ),
            padding="14px 16px", text_align="right",
        ),
        rx.el.td(
            rx.text(
                "R$ " + item["total_realizado"].to_string(),
                font_family=S.FONT_MONO, font_size="12px", color="#22c55e",
            ),
            padding="14px 16px", text_align="right",
        ),
        rx.el.td(
            rx.text(
                item["margem_pct"].to_string() + "%",
                font_family=S.FONT_MONO, font_size="12px", font_weight="700",
                color=rx.cond(item["margem_pct"].to(float) >= 0, "#22c55e", S.DANGER),
            ),
            padding="14px 16px", text_align="right",
        ),
        _hover={"bg": "rgba(255,255,255,0.02)"},
        transition="background 0.2s ease",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
    )


def finance_table() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.hstack(
                    rx.icon(tag="table-2", size=14, color=S.COPPER),
                    rx.text("Detalhamento por Categoria", font_family=S.FONT_TECH,
                            font_size="1.05rem", font_weight="700", color="white"),
                    spacing="2", align="center",
                ),
                padding="20px 24px",
                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
            ),
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th("CATEGORIA", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", letter_spacing="0.05em",
                                 text_align="left"),
                        rx.el.th("PREVISTO", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        rx.el.th("EXECUTADO", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        rx.el.th("% EXEC.", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        bg="rgba(255,255,255,0.02)",
                    ),
                ),
                rx.el.tbody(
                    rx.foreach(GlobalState.financeiro_cockpit_chart, finance_table_row),
                ),
                width="100%", style={"borderCollapse": "collapse"},
            ),
            overflow_x="auto", width="100%",
            spacing="0",
        ),
        **{k: v for k, v in S.GLASS_CARD_NO_HOVER.items() if k != "padding"},
        padding="0",
        overflow="hidden",
        width="100%",
    )


# ── Tabela por contrato ───────────────────────────────────────────────────────

def _fin_contrato_row(item: dict) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.text(item["contrato"], font_weight="700", font_size="12px",
                    color=S.COPPER, font_family=S.FONT_MONO),
            padding="14px 16px",
        ),
        rx.el.td(
            rx.text(item["total_contratado_fmt"], font_family=S.FONT_MONO,
                    font_size="12px", color="white"),
            padding="14px 16px", text_align="right",
        ),
        rx.el.td(
            rx.text(item["total_realizado_fmt"], font_family=S.FONT_MONO,
                    font_size="12px", color="#22c55e"),
            padding="14px 16px", text_align="right",
        ),
        rx.el.td(
            rx.text(item["saldo_fmt"], font_family=S.FONT_MONO,
                    font_size="12px", color="#3B82F6"),
            padding="14px 16px", text_align="right",
        ),
        rx.el.td(
            rx.text(item["pct_medido"], font_family=S.FONT_MONO,
                    font_size="12px", font_weight="700", color=S.COPPER),
            padding="14px 16px", text_align="right",
        ),
        _hover={"bg": "rgba(255,255,255,0.02)"},
        transition="background 0.2s ease",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
    )


def finance_contrato_table() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.hstack(
                    rx.icon(tag="file-text", size=14, color=S.COPPER),
                    rx.text("Resumo por Contrato", font_family=S.FONT_TECH,
                            font_size="1.05rem", font_weight="700", color="white"),
                    spacing="2", align="center",
                ),
                padding="20px 24px",
                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
            ),
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th("CONTRATO", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", letter_spacing="0.05em",
                                 text_align="left"),
                        rx.el.th("PREVISTO", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        rx.el.th("EXECUTADO", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        rx.el.th("SALDO", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        rx.el.th("% EXEC.", padding="14px 16px", font_size="10px",
                                 font_weight="900", color=S.TEXT_MUTED,
                                 text_transform="uppercase", text_align="right"),
                        bg="rgba(255,255,255,0.02)",
                    ),
                ),
                rx.el.tbody(
                    rx.foreach(GlobalState.fin_contrato_rows, _fin_contrato_row),
                ),
                width="100%", style={"borderCollapse": "collapse"},
            ),
            overflow_x="auto", width="100%",
            spacing="0",
        ),
        **{k: v for k, v in S.GLASS_CARD_NO_HOVER.items() if k != "padding"},
        padding="0",
        overflow="hidden",
        width="100%",
    )


# ── Page ──────────────────────────────────────────────────────────────────────

def financeiro_page() -> rx.Component:
    return rx.vstack(
        finance_header(),
        rx.cond(
            GlobalState.is_loading,
            page_loading_skeleton(),
            rx.vstack(
                # Row 1: 4 KPIs principais
                finance_kpi_grid(),
                # Row 2: 7 mini KPIs secundários
                finance_secondary_kpis(),
                # Row 3: Status donut + Bar chart
                rx.grid(
                    finance_status_chart(),
                    finance_cost_chart(),
                    columns=rx.breakpoints(initial="1", lg="2"),
                    spacing="8",
                    width="100%",
                ),
                # Row 4: S-curve FULL WIDTH
                finance_scurve_chart(),
                # Row 5: Tabela por categoria
                finance_table(),
                # Row 6: Tabela por contrato (nova)
                finance_contrato_table(),
                width="100%",
                spacing="8",
            ),
        ),
        width="100%",
        spacing="8",
        on_mount=lambda: GlobalState.set_current_path("/financeiro"),
        class_name="animate-enter",
    )
