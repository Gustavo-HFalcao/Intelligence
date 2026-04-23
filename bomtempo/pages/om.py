"""
O&M — Gestão de Ativos Energéticos
Rota: /om

Sub-páginas via header-menu:
  - Dashboard  → KPIs + gráfico + tabela resumida (dados existentes do GlobalState)
  - Gestão     → CRUD de registros de geração (om_geracoes)
"""
import reflex as rx

from bomtempo.components.charts import composed_chart_om, kpi_card
from bomtempo.components.skeletons import page_loading_skeleton
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.om_state import OmState

# ── Input style reutilizável ───────────────────────────────────────────────────
_INPUT_STYLE = {
    "background": "rgba(14, 26, 23, 0.8)",
    "border": f"1px solid {S.BORDER_SUBTLE}",
    "borderRadius": S.R_CONTROL,
    "color": "white",
    "padding": "8px 10px",
    "fontSize": "14px",
    "width": "100%",
    "outline": "none",
    "fontFamily": S.FONT_BODY,
    "_focus": {"borderColor": S.COPPER},
    "_placeholder": {"color": S.TEXT_MUTED},
}

_SELECT_STYLE = {
    **_INPUT_STYLE,
    "cursor": "pointer",
}

_LABEL_STYLE = {
    "font_size": "11px",
    "color": S.TEXT_MUTED,
    "font_family": S.FONT_MONO,
    "font_weight": "600",
    "text_transform": "uppercase",
    "letter_spacing": "0.05em",
}


# ══════════════════════════════════════════════════════════════════════════════
# SHARED: Header-Menu nav bar
# ══════════════════════════════════════════════════════════════════════════════


def _om_tab(label: str, value: str, icon_tag: str) -> rx.Component:
    is_active = OmState.om_tab == value
    return rx.box(
        rx.hstack(
            rx.icon(
                tag=icon_tag,
                size=13,
                color=rx.cond(is_active, S.COPPER, S.TEXT_MUTED),
            ),
            rx.text(
                label,
                font_family=S.FONT_MONO,
                font_size="12px",
                font_weight=rx.cond(is_active, "700", "400"),
                color=rx.cond(is_active, S.COPPER, "rgba(218,229,225,0.55)"),
                transition="color 0.2s ease",
                white_space="nowrap",
            ),
            spacing="2",
            align="center",
        ),
        padding_bottom="10px",
        padding_top="2px",
        padding_x="2px",
        border_bottom=rx.cond(
            is_active,
            f"2px solid {S.COPPER}",
            "2px solid transparent",
        ),
        cursor="pointer",
        on_click=OmState.set_om_tab(value),
        _hover={"& > div > p": {"color": "rgba(218,229,225,0.9)"}},
        transition="border-color 0.2s ease",
    )


def _om_navbar() -> rx.Component:
    """Header-menu com título + tabs (Dashboard | Gestão)."""
    return rx.box(
        rx.flex(
            # Título + subtítulo
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="zap", size=18, color=S.COPPER),
                    rx.text(
                        "O&M — Gestão de Ativos",
                        font_family=S.FONT_TECH,
                        font_size="1.3rem",
                        font_weight="700",
                        color="var(--text-main)",
                        letter_spacing="-0.01em",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    "Performance Energética e Resultados",
                    font_size="11px",
                    font_family=S.FONT_MONO,
                    color=S.TEXT_MUTED,
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            # Tabs
            rx.hstack(
                _om_tab("Dashboard", "dashboard", "bar-chart-2"),
                _om_tab("Gestão", "gestao", "database"),
                spacing="6",
                align="end",
            ),
            align="end",
            justify="between",
            width="100%",
            flex_wrap="wrap",
            gap="3",
        ),
        width="100%",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
        padding_bottom="16px",
        margin_bottom="4px",
        class_name="animate-enter",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD (conteúdo original preservado)
# ══════════════════════════════════════════════════════════════════════════════


def _dashboard_filters() -> rx.Component:
    """Filtros de projeto e período."""
    return rx.hstack(
        # Project filter
        rx.hstack(
            rx.icon(tag="filter", size=16, color=S.COPPER),
            rx.el.select(
                rx.foreach(
                    GlobalState.project_filter_options,
                    lambda opt: rx.el.option(
                        opt,
                        value=opt,
                        style={"background": S.BG_ELEVATED, "color": S.COPPER},
                    ),
                ),
                value=GlobalState.om_project_filter,
                on_change=GlobalState.set_om_project_filter,
                background="transparent",
                color="white",
                border="none",
                outline="none",
                font_size="14px",
                font_family=S.FONT_MONO,
                padding="8px",
                cursor="pointer",
            ),
            bg=S.PATINA_GLOW,
            padding_x="12px",
            padding_y="6px",
            border_radius="12px",
            border=f"1px solid {S.PATINA}",
            align="center",
        ),
        # Time filter
        rx.hstack(
            rx.foreach(
                ["Mês", "Trimestre", "Ano"],
                lambda t: rx.box(
                    rx.text(
                        t,
                        font_size="12px",
                        font_weight="700",
                        color=rx.cond(
                            GlobalState.om_time_filter == t,
                            S.BG_VOID,
                            S.TEXT_MUTED,
                        ),
                    ),
                    padding="8px 16px",
                    border_radius="8px",
                    cursor="pointer",
                    bg=rx.cond(GlobalState.om_time_filter == t, S.COPPER, "transparent"),
                    on_click=lambda: GlobalState.set_om_time_filter(t),
                    _hover={"color": "white"},
                    transition="all 0.2s ease",
                ),
            ),
            bg="rgba(255, 255, 255, 0.03)",
            padding="4px",
            border_radius="12px",
            border="1px solid rgba(255, 255, 255, 0.06)",
            spacing="1",
        ),
        spacing="4",
        flex_wrap="wrap",
        align="center",
        width="100%",
        justify="end",
    )


def _kpi_grid() -> rx.Component:
    return rx.grid(
        kpi_card(title="Energia Injetada (Total)", value=GlobalState.om_energia_injetada_fmt, icon="zap"),
        kpi_card(title="Acumulado", value=GlobalState.om_acumulado_fmt, icon="zap", trend="Total", trend_type="neutral"),
        kpi_card(title="Performance", value=GlobalState.om_performance_fmt, icon="arrow-down-to-dot", trend_type="positive"),
        kpi_card(title="Fat. Líquido", value=GlobalState.om_fat_liquido_fmt, icon="calendar", is_money=True),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="6",
        width="100%",
    )


def _chart_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(
                "Performance de Geração",
                font_family=S.FONT_TECH,
                font_size="1.25rem",
                font_weight="700",
                color="white",
                margin_bottom="24px",
            ),
            rx.box(
                composed_chart_om(
                    data=GlobalState.om_geracao_chart,
                    x_key="mes_ano",
                    bar_key="acumulado_kwh",
                    line1_key="geracao_prevista_kwh",
                    line2_key="energia_injetada_kwh",
                    height=400,
                ),
                width="100%",
                height="400px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
        width="100%",
    )


def _table_row(item: dict) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.text(item["mes_ano"], font_family=S.FONT_MONO, font_size="12px", color="white"),
            padding="16px",
        ),
        rx.el.td(
            rx.text(item["energia_injetada_kwh"].to_string(), font_family=S.FONT_MONO, font_size="12px", color=S.PATINA, font_weight="700"),
            padding="16px", text_align="right",
        ),
        rx.el.td(
            rx.text(item["compensado_kwh"].to_string(), font_family=S.FONT_MONO, font_size="12px", color=S.TEXT_MUTED),
            padding="16px", text_align="right",
        ),
        rx.el.td(
            rx.text(item["acumulado_kwh"].to_string(), font_family=S.FONT_MONO, font_size="12px", color="white"),
            padding="16px", text_align="right",
        ),
        rx.el.td(
            rx.text("R$ " + item["valor_faturado"].to_string(), font_family=S.FONT_MONO, font_size="12px", color="white"),
            padding="16px", text_align="right",
        ),
        rx.el.td(
            rx.text("R$ " + item["gestao"].to_string(), font_family=S.FONT_MONO, font_size="12px", color=S.DANGER),
            padding="16px", text_align="right",
        ),
        rx.el.td(
            rx.text("R$ " + item["faturamento_liquido"].to_string(), font_family=S.FONT_MONO, font_size="12px", color=S.COPPER, font_weight="700"),
            padding="16px", text_align="right",
        ),
        _hover={"bg": "rgba(255, 255, 255, 0.02)"},
        transition="background 0.2s ease",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
    )


def _summary_table() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.text("Registros de O&M", font_family=S.FONT_TECH, font_size="1.125rem", font_weight="700", color="white"),
                padding="24px",
                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
            ),
            rx.box(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            *[
                                rx.el.th(h, padding="16px", font_size="10px", font_weight="900", color=S.TEXT_MUTED, text_transform="uppercase", text_align=align)
                                for h, align in [
                                    ("Data", "left"),
                                    ("Injetada (kWh)", "right"),
                                    ("Compensada (kWh)", "right"),
                                    ("Acumulada (kWh)", "right"),
                                    ("Valor Faturado", "right"),
                                    ("Gestão", "right"),
                                    ("Fat. Líquido", "right"),
                                ]
                            ],
                            bg="rgba(255, 255, 255, 0.02)",
                        ),
                    ),
                    rx.el.tbody(rx.foreach(GlobalState.om_table_data, _table_row)),
                    width="100%",
                    style={"borderCollapse": "collapse"},
                ),
                overflow_x="auto",
                width="100%",
            ),
            spacing="0",
            width="100%",
        ),
        **{k: v for k, v in S.GLASS_CARD_NO_HOVER.items() if k != "padding"},
        padding="0",
        overflow="hidden",
        width="100%",
    )


def _tab_dashboard() -> rx.Component:
    return rx.vstack(
        _dashboard_filters(),
        rx.cond(
            GlobalState.is_loading,
            page_loading_skeleton(),
            rx.vstack(
                _kpi_grid(),
                _chart_panel(),
                _summary_table(),
                width="100%",
                spacing="8",
            ),
        ),
        width="100%",
        spacing="6",
        class_name="animate-fade-in",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — GESTÃO (CRUD)
# ══════════════════════════════════════════════════════════════════════════════


def _gestao_row(row: dict) -> rx.Component:
    """Linha na tabela de gestão."""
    return rx.el.tr(
        rx.el.td(
            rx.text(row["contrato"], font_family=S.FONT_MONO, font_size="12px", color=S.COPPER, font_weight="700"),
            padding="14px 16px",
        ),
        rx.el.td(
            rx.text(row["data_referencia"], font_family=S.FONT_MONO, font_size="12px", color="white"),
            padding="14px 16px",
        ),
        rx.el.td(
            rx.text(row["cliente"], font_family=S.FONT_BODY, font_size="13px", color=S.TEXT_MUTED),
            padding="14px 16px",
        ),
        rx.el.td(
            rx.text(row["energia_injetada_kwh"] + " kWh", font_family=S.FONT_MONO, font_size="12px", color=S.PATINA),
            padding="14px 16px",
            text_align="right",
        ),
        rx.el.td(
            rx.text("R$ " + row["faturamento_liquido"], font_family=S.FONT_MONO, font_size="12px", color=S.COPPER),
            padding="14px 16px",
            text_align="right",
        ),
        rx.el.td(
            rx.hstack(
                rx.icon_button(
                    rx.icon(tag="pencil", size=13),
                    size="1",
                    variant="ghost",
                    cursor="pointer",
                    color=S.TEXT_MUTED,
                    on_click=OmState.open_edit(row["id"]),
                    _hover={"color": S.COPPER, "bg": S.COPPER_GLOW},
                ),
                rx.icon_button(
                    rx.icon(tag="trash-2", size=13),
                    size="1",
                    variant="ghost",
                    cursor="pointer",
                    color=S.TEXT_MUTED,
                    on_click=OmState.request_delete(row["id"]),
                    _hover={"color": S.DANGER, "bg": "rgba(239,68,68,0.1)"},
                ),
                spacing="1",
                justify="end",
            ),
            padding="14px 16px",
            text_align="right",
        ),
        _hover={"bg": "rgba(255, 255, 255, 0.02)"},
        transition="background 0.2s ease",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
    )


def _gestao_empty() -> rx.Component:
    return rx.vstack(
        rx.icon(tag="zap-off", size=40, color=S.TEXT_MUTED),
        rx.text("Nenhum registro de geração", font_size="14px", color=S.TEXT_MUTED, font_family=S.FONT_BODY),
        rx.text("Clique em '+ Nova Geração' para começar.", font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
        spacing="2",
        align="center",
        padding="60px",
        width="100%",
    )


def _tab_gestao() -> rx.Component:
    return rx.vstack(
        # Header da seção
        rx.hstack(
            rx.vstack(
                rx.text("Registros de Geração", font_family=S.FONT_TECH, font_size="1.1rem", font_weight="700", color="white"),
                rx.text("Cadastre e gerencie as gerações de energia por contrato.", font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_BODY),
                spacing="1",
            ),
            rx.spacer(),
            rx.button(
                rx.hstack(
                    rx.icon(tag="plus", size=14),
                    rx.text("Nova Geração", font_family=S.FONT_TECH, font_weight="700"),
                    spacing="2",
                    align="center",
                ),
                on_click=OmState.open_new,
                size="2",
                cursor="pointer",
                style={
                    "background": S.COPPER,
                    "color": S.BG_VOID,
                    "fontFamily": S.FONT_TECH,
                    "fontWeight": "700",
                    "borderRadius": S.R_CONTROL,
                    "cursor": "pointer",
                },
            ),
            width="100%",
            align="center",
        ),
        # Tabela
        rx.box(
            rx.cond(
                OmState.geracoes_loading,
                rx.vstack(
                    rx.spinner(size="3", color=S.COPPER),
                    rx.text("Carregando registros...", font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="2",
                    align="center",
                    padding="40px",
                    width="100%",
                ),
                rx.cond(
                    OmState.geracoes_list.length() == 0,
                    _gestao_empty(),
                    rx.box(
                        rx.el.table(
                            rx.el.thead(
                                rx.el.tr(
                                    *[
                                        rx.el.th(h, padding="14px 16px", font_size="10px", font_weight="900", color=S.TEXT_MUTED, text_transform="uppercase", text_align=align)
                                        for h, align in [
                                            ("Contrato", "left"),
                                            ("Data Ref.", "left"),
                                            ("Cliente", "left"),
                                            ("Energia Injetada", "right"),
                                            ("Fat. Líquido", "right"),
                                            ("Ações", "right"),
                                        ]
                                    ],
                                    bg="rgba(255, 255, 255, 0.02)",
                                ),
                            ),
                            rx.el.tbody(rx.foreach(OmState.geracoes_list, _gestao_row)),
                            width="100%",
                            style={"borderCollapse": "collapse"},
                        ),
                        overflow_x="auto",
                        width="100%",
                    ),
                ),
            ),
            **{k: v for k, v in S.GLASS_CARD_NO_HOVER.items() if k != "padding"},
            padding="0",
            overflow="hidden",
            width="100%",
        ),
        width="100%",
        spacing="5",
        class_name="animate-fade-in",
    )


# ══════════════════════════════════════════════════════════════════════════════
# CRUD DIALOGS
# ══════════════════════════════════════════════════════════════════════════════


def _field(label: str, component: rx.Component) -> rx.Component:
    """Wrapper de campo com label padronizado."""
    return rx.vstack(
        rx.text(label, **_LABEL_STYLE),
        component,
        spacing="1",
        width="100%",
    )


def _kwh_field(label: str, value_var, on_blur) -> rx.Component:
    return _field(
        label,
        rx.hstack(
            rx.el.input(
                default_value=value_var,
                on_blur=on_blur,
                placeholder="0,00",
                style={**_INPUT_STYLE, "borderRadius": f"{S.R_CONTROL} 0 0 {S.R_CONTROL}"},
            ),
            rx.box(
                rx.text("kWh", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                padding="8px 10px",
                bg="rgba(255,255,255,0.03)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_left="none",
                border_radius=f"0 {S.R_CONTROL} {S.R_CONTROL} 0",
            ),
            spacing="0",
            width="100%",
        ),
    )


def _brl_field(label: str, value_var, on_blur) -> rx.Component:
    return _field(
        label,
        rx.hstack(
            rx.box(
                rx.text("R$", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                padding="8px 10px",
                bg="rgba(255,255,255,0.03)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_right="none",
                border_radius=f"{S.R_CONTROL} 0 0 {S.R_CONTROL}",
            ),
            rx.el.input(
                default_value=value_var,
                on_blur=on_blur,
                placeholder="0,00",
                style={**_INPUT_STYLE, "borderRadius": f"0 {S.R_CONTROL} {S.R_CONTROL} 0"},
            ),
            spacing="0",
            width="100%",
        ),
    )


def _brl_readonly(label: str, value_var) -> rx.Component:
    """Campo somente leitura — exibe valor calculado automaticamente."""
    return _field(
        label + " (auto)",
        rx.hstack(
            rx.box(
                rx.text("R$", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                padding="8px 10px",
                bg="rgba(255,255,255,0.02)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_right="none",
                border_radius=f"{S.R_CONTROL} 0 0 {S.R_CONTROL}",
            ),
            rx.box(
                rx.text(
                    value_var,
                    font_family=S.FONT_MONO,
                    font_size="14px",
                    color=S.COPPER,
                    font_weight="700",
                ),
                flex="1",
                padding="8px 10px",
                bg="rgba(255,255,255,0.02)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_left="none",
                border_radius=f"0 {S.R_CONTROL} {S.R_CONTROL} 0",
            ),
            spacing="0",
            width="100%",
        ),
    )


def _om_edit_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # ── Header ────────────────────────────────────────────────────
                rx.hstack(
                    rx.icon(
                        tag=rx.cond(OmState.edit_id == "", "circle-plus", "pencil"),
                        size=16,
                        color=S.COPPER,
                    ),
                    rx.dialog.title(
                        rx.cond(OmState.edit_id == "", "Nova Geração", "Editar Geração"),
                        font_family=S.FONT_TECH,
                        font_size="1rem",
                        font_weight="700",
                        color="var(--text-main)",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.icon_button(
                            rx.icon(tag="x", size=14),
                            size="1",
                            variant="ghost",
                            cursor="pointer",
                            on_click=OmState.close_dialog,
                        )
                    ),
                    align="center",
                    width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),

                # ── Seção: Identificação ───────────────────────────────────────
                rx.text("Identificação", font_size="10px", font_weight="900", color=S.COPPER, font_family=S.FONT_MONO, text_transform="uppercase", letter_spacing="0.08em"),
                rx.flex(
                    # Contrato — select
                    _field(
                        "Contrato *",
                        rx.select.root(
                            rx.select.trigger(
                                placeholder="Selecione o contrato",
                                style={**_SELECT_STYLE, "width": "100%"},
                            ),
                            rx.select.content(
                                rx.foreach(
                                    OmState.contrato_options,
                                    lambda c: rx.select.item(
                                        rx.cond(c == "", "— Selecione —", c),
                                        value=rx.cond(c == "", "__none__", c),
                                    ),
                                ),
                                style={
                                    "background": S.BG_ELEVATED,
                                    "border": f"1px solid {S.BORDER_SUBTLE}",
                                    "zIndex": "9999",
                                },
                                position="popper",
                            ),
                            value=rx.cond(OmState.edit_contrato == "", "__none__", OmState.edit_contrato),
                            on_change=OmState.set_edit_contrato,
                        ),
                    ),
                    # Data de referência
                    _field(
                        "Data de Referência *",
                        rx.el.input(
                            type="date",
                            value=OmState.edit_data_referencia,
                            on_change=OmState.set_edit_data_referencia,
                            style=_INPUT_STYLE,
                        ),
                    ),
                    gap="12px",
                    flex_wrap="wrap",
                    width="100%",
                    style={"& > *": {"flex": "1", "minWidth": "200px"}},
                ),
                rx.flex(
                    # Cliente
                    _field(
                        "Cliente",
                        rx.el.input(
                            default_value=OmState.edit_cliente,
                            on_blur=OmState.set_edit_cliente,
                            placeholder="Nome do cliente",
                            style=_INPUT_STYLE,
                        ),
                    ),
                    # Localização
                    _field(
                        "Localização",
                        rx.el.input(
                            default_value=OmState.edit_localizacao,
                            on_blur=OmState.set_edit_localizacao,
                            placeholder="Cidade / UF",
                            style=_INPUT_STYLE,
                        ),
                    ),
                    gap="12px",
                    flex_wrap="wrap",
                    width="100%",
                    style={"& > *": {"flex": "1", "minWidth": "200px"}},
                ),

                # ── Seção: Energia (kWh) ───────────────────────────────────────
                rx.text("Energia (kWh)", font_size="10px", font_weight="900", color=S.PATINA, font_family=S.FONT_MONO, text_transform="uppercase", letter_spacing="0.08em"),
                rx.flex(
                    _kwh_field("Geração Prevista", OmState.edit_geracao_prevista, OmState.on_blur_geracao_prevista),
                    _kwh_field("Energia Injetada", OmState.edit_energia_injetada, OmState.on_blur_energia_injetada),
                    _kwh_field("Compensado", OmState.edit_compensado, OmState.on_blur_compensado),
                    gap="12px",
                    flex_wrap="wrap",
                    width="100%",
                    style={"& > *": {"flex": "1", "minWidth": "180px"}},
                ),

                # ── Seção: Financeiro ──────────────────────────────────────────
                rx.text("Financeiro", font_size="10px", font_weight="900", color=S.COPPER, font_family=S.FONT_MONO, text_transform="uppercase", letter_spacing="0.08em"),
                rx.flex(
                    _brl_field("Valor Faturado", OmState.edit_valor_faturado, OmState.on_blur_valor_faturado),
                    _brl_field("Gestão", OmState.edit_gestao, OmState.on_blur_gestao),
                    _brl_readonly("Fat. Líquido", OmState.edit_faturamento_liquido),
                    gap="12px",
                    flex_wrap="wrap",
                    width="100%",
                    style={"& > *": {"flex": "1", "minWidth": "180px"}},
                ),

                # ── Observações ────────────────────────────────────────────────
                _field(
                    "Observações",
                    rx.el.textarea(
                        default_value=OmState.edit_observacoes,
                        on_blur=OmState.set_edit_observacoes,
                        placeholder="Anotações técnicas, ocorrências, etc.",
                        rows="3",
                        style=_INPUT_STYLE,
                    ),
                ),

                # ── Erro ───────────────────────────────────────────────────────
                rx.cond(
                    OmState.dialog_error != "",
                    rx.hstack(
                        rx.icon(tag="alert-circle", size=13, color=S.DANGER),
                        rx.text(OmState.dialog_error, font_size="12px", color=S.DANGER, font_family=S.FONT_MONO),
                        spacing="2",
                        align="center",
                        padding="8px 12px",
                        bg="rgba(239,68,68,0.08)",
                        border=f"1px solid rgba(239,68,68,0.2)",
                        border_radius=S.R_CONTROL,
                    ),
                ),

                # ── Footer ─────────────────────────────────────────────────────
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancelar",
                            variant="ghost",
                            size="2",
                            color=S.TEXT_MUTED,
                            cursor="pointer",
                            on_click=OmState.close_dialog,
                        )
                    ),
                    rx.button(
                        rx.cond(
                            OmState.saving,
                            rx.hstack(rx.spinner(size="2"), rx.text("Salvando..."), spacing="2", align="center"),
                            rx.hstack(rx.icon(tag="save", size=13), rx.text("Salvar"), spacing="1", align="center"),
                        ),
                        on_click=OmState.save_geracao,
                        size="2",
                        disabled=OmState.saving,
                        style={
                            "background": S.COPPER,
                            "color": S.BG_VOID,
                            "fontFamily": S.FONT_TECH,
                            "fontWeight": "700",
                            "cursor": "pointer",
                            "opacity": rx.cond(OmState.saving, "0.7", "1"),
                        },
                    ),
                    justify="end",
                    spacing="2",
                    width="100%",
                    padding_top="8px",
                ),
                spacing="4",
                width="100%",
            ),
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius=S.R_CARD,
            max_width="680px",
            width="95vw",
            max_height="90vh",
            overflow_y="auto",
        ),
        open=OmState.show_dialog,
        on_open_change=OmState.set_show_dialog,
    )


def _om_delete_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="trash-2", size=16, color=S.DANGER),
                    rx.dialog.title(
                        "Excluir Registro",
                        font_family=S.FONT_TECH,
                        font_weight="700",
                        color="var(--text-main)",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text("Tem certeza que deseja excluir o registro:", font_size="13px", color=S.TEXT_MUTED),
                rx.text(OmState.delete_label, font_size="13px", font_weight="700", color=S.DANGER, font_family=S.FONT_MONO),
                rx.text("Esta ação não pode ser desfeita.", font_size="11px", color=S.TEXT_MUTED),
                rx.hstack(
                    rx.button(
                        "Cancelar",
                        variant="ghost",
                        size="2",
                        cursor="pointer",
                        on_click=OmState.cancel_delete,
                    ),
                    rx.button(
                        rx.hstack(rx.icon(tag="trash-2", size=13), rx.text("Excluir"), spacing="1"),
                        on_click=OmState.confirm_delete,
                        size="2",
                        cursor="pointer",
                        style={"background": S.DANGER, "color": "white", "cursor": "pointer"},
                    ),
                    justify="end",
                    spacing="2",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            bg=S.BG_ELEVATED,
            border="1px solid rgba(239,68,68,0.3)",
            border_radius=S.R_CARD,
            max_width="420px",
            width="90vw",
        ),
        open=OmState.show_delete,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ROOT
# ══════════════════════════════════════════════════════════════════════════════


def om_page() -> rx.Component:
    return rx.box(
        # Dialogs (renderizados fora do fluxo principal)
        _om_edit_dialog(),
        _om_delete_dialog(),
        # Conteúdo principal
        rx.vstack(
            _om_navbar(),
            rx.cond(
                OmState.om_tab == "dashboard",
                _tab_dashboard(),
                _tab_gestao(),
            ),
            width="100%",
            spacing="5",
            class_name="animate-enter",
        ),
        on_mount=lambda: GlobalState.set_current_path("/om"),
        width="100%",
    )
