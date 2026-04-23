import reflex as rx

from bomtempo.components.skeletons import page_loading_skeleton
from bomtempo.components.weather_widget import weather_widget
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState

# Compact glass card variants — override GLASS_CARD's default 32px padding
_GLASS_COMPACT = {**S.GLASS_CARD, "padding": "20px 24px"}
_GLASS_INFO = {**S.GLASS_CARD, "padding": "20px 28px"}


# ══════════════════════════════════════════════════════════════
# SHARED HEADER
# ══════════════════════════════════════════════════════════════


def obras_header() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text("SITUAÇÃO DO CAMPO", **S.PAGE_TITLE_STYLE),
            rx.text(
                "Monitoramento Ativo de Obras em Tempo Real",
                **S.PAGE_SUBTITLE_STYLE,
            ),
            spacing="1",
        ),
        rx.spacer(),
        rx.cond(
            GlobalState.obras_selected_contract != "",
            rx.button(
                rx.hstack(rx.icon(tag="arrow-left", size=14), rx.text("Todas as Obras", font_size="13px", font_weight="700"), spacing="2", align="center"),
                color=S.COPPER,
                variant="ghost",
                cursor="pointer",
                on_click=GlobalState.deselect_obra,
                _hover={"opacity": "0.8", "bg": S.COPPER_GLOW},
                padding="8px 16px",
                border=f"1px solid {S.BORDER_ACCENT}",
                border_radius=S.R_CONTROL,
                transition="all 0.2s ease",
            ),
        ),
        width="100%",
        align="center",
        class_name="animate-enter",
    )


# ══════════════════════════════════════════════════════════════
# LIST VIEW
# ══════════════════════════════════════════════════════════════


def _risk_badge(item: dict) -> rx.Component:
    score = item["risco_geral_score"].to(int)
    color = rx.cond(score >= 60, S.DANGER, rx.cond(score >= 30, S.WARNING, S.PATINA))
    bg = rx.cond(score >= 60, S.DANGER_BG, rx.cond(score >= 30, S.WARNING_BG, S.SUCCESS_BG))
    label = rx.cond(score >= 60, "CRÍTICO", rx.cond(score >= 30, "ATENÇÃO", "SAUDÁVEL"))
    return rx.hstack(
        rx.box(width="6px", height="6px", border_radius="50%", bg=color),
        rx.text(label, font_size="9px", font_weight="700", color=color),
        rx.text(score.to_string(), font_size="9px", font_family=S.FONT_MONO, color=color),
        padding="3px 8px",
        border_radius="6px",
        bg=bg,
        border=rx.cond(
            score >= 60,
            "1px solid rgba(239,68,68,0.3)",
            rx.cond(score >= 30, "1px solid rgba(245,158,11,0.3)", "1px solid rgba(42,157,143,0.3)"),
        ),
        align="center",
        spacing="1",
    )


def obra_card(item: dict) -> rx.Component:
    avanco = item["avanco_pct"].to(float).to(int)
    equipe = item["equipe_presente_hoje"].to(int)
    efetivo = item["efetivo_planejado"].to(int)
    bp = item["budget_planejado"].to(float)
    br = item["budget_realizado"].to(float)
    budget_ratio = rx.cond(bp > 0, rx.cond(br / bp * 100 > 100, 100, (br / bp * 100).to(int)), 0)
    budget_over = rx.cond(bp > 0, br > bp, False)

    return rx.box(
        rx.box(rx.icon(tag="arrow-right", size=20, color=S.COPPER), class_name="arrow-icon"),
        rx.vstack(
            # Contract + Risk badge row
            rx.hstack(
                rx.vstack(
                    rx.text(
                        item["contrato"],
                        color=S.COPPER,
                        font_family=S.FONT_TECH,
                        font_weight="700",
                        font_size="0.9rem",
                    ),
                    rx.text(
                        item["cliente"],
                        color="white",
                        font_weight="700",
                        font_size="1.1rem",
                    ),
                    spacing="0",
                ),
                rx.spacer(),
                _risk_badge(item),
                align="start",
                width="100%",
            ),
            # Location
            rx.hstack(
                rx.icon(tag="map-pin", size=12, color=S.TEXT_MUTED, flex_shrink="0"),
                rx.text(
                    item.get("localizacao", "—"),
                    font_size="12px",
                    color=S.TEXT_MUTED,
                    white_space="nowrap",
                    overflow="hidden",
                    text_overflow="ellipsis",
                    min_width="0",
                ),
                align="center",
                spacing="2",
                margin_top="8px",
                overflow="hidden",
                width="100%",
            ),
            # Avanço físico bar
            rx.box(
                rx.hstack(
                    rx.text(
                        "Avanço Físico",
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        font_weight="700",
                    ),
                    rx.spacer(),
                    rx.text(
                        avanco.to_string() + "%",
                        font_family=S.FONT_MONO,
                        font_weight="700",
                        color="white",
                        font_size="11px",
                    ),
                    width="100%",
                    margin_bottom="5px",
                ),
                rx.box(
                    rx.box(
                        width=avanco.to_string() + "%",
                        height="100%",
                        bg=S.PATINA,
                        border_radius="9999px",
                        transition="width 1s ease-out",
                    ),
                    height="4px",
                    bg="rgba(255,255,255,0.06)",
                    border_radius="9999px",
                    overflow="hidden",
                    width="100%",
                ),
                width="100%",
                margin_top="16px",
                padding_top="14px",
                border_top=f"1px solid {S.BORDER_SUBTLE}",
            ),
            # Budget + Equipe row
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.text("Budget", font_size="9px", color=S.TEXT_MUTED, font_weight="700"),
                        rx.spacer(),
                        rx.text(
                            rx.cond(bp > 0, budget_ratio.to_string() + "%", "—"),
                            font_size="9px",
                            font_family=S.FONT_MONO,
                            color=rx.cond(budget_over, S.DANGER, S.TEXT_MUTED),
                            font_weight="700",
                        ),
                        width="100%",
                    ),
                    rx.box(
                        rx.box(
                            width=budget_ratio.to_string() + "%",
                            height="100%",
                            bg=rx.cond(budget_over, S.DANGER, S.PATINA),
                            border_radius="9999px",
                        ),
                        height="3px",
                        bg="rgba(255,255,255,0.05)",
                        border_radius="9999px",
                        overflow="hidden",
                        width="100%",
                    ),
                    spacing="1",
                    flex="1",
                ),
                rx.box(width="1px", height="28px", bg=S.BORDER_SUBTLE),
                rx.hstack(
                    rx.icon(tag="users", size=12, color=S.TEXT_MUTED),
                    rx.text(
                        equipe.to_string() + "/" + efetivo.to_string(),
                        font_size="11px",
                        font_family=S.FONT_MONO,
                        color=S.TEXT_MUTED,
                    ),
                    spacing="1",
                    align="center",
                ),
                spacing="3",
                align="center",
                width="100%",
                margin_top="10px",
            ),
            width="100%",
            spacing="0",
        ),
        class_name="project-card",
        on_click=GlobalState.select_obra_detail(item["label"]),
    )


def obras_list_view() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.cond(
                GlobalState.obras_cards_list,
                rx.grid(
                    rx.foreach(GlobalState.obras_cards_list, obra_card),
                    columns=rx.breakpoints(initial="1", md="2", lg="3"),
                    spacing="6",
                    width="100%",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon(tag="hard-hat", size=48, color=S.BORDER_SUBTLE),
                        rx.text("Nenhuma obra encontrada", font_size="1rem", color=S.TEXT_MUTED),
                        spacing="4",
                        align="center",
                    ),
                    height="40vh",
                    width="100%",
                ),
            ),
            width="100%",
            class_name="animate-enter",
        ),
        width="100%",
    )


# ══════════════════════════════════════════════════════════════
# DETAIL VIEW — Components (storytelling order)
# ══════════════════════════════════════════════════════════════

# ── 1. STATUS STRIP (4 KPI cards) ────────────────────────────


def _kpi_card_static(
    icon_tag: str,
    label: str,
    value: str,
    sub: str,
    accent: str,
    accent_bg: str,
    accent_border: str,
) -> rx.Component:
    """Static-string KPI card — values pre-formatted server-side."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(tag=icon_tag, size=16, color=accent),
                    padding="8px",
                    bg=accent_bg,
                    border_radius="8px",
                    border=f"1px solid {accent_border}",
                ),
                rx.vstack(
                    rx.text(
                        label,
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.1em",
                        font_weight="700",
                    ),
                    rx.text(
                        value,
                        font_family=S.FONT_TECH,
                        font_size="1.75rem",
                        font_weight="700",
                        color="white",
                        line_height="1",
                    ),
                    spacing="1",
                    align="start",
                ),
                align="center",
                spacing="3",
            ),
            rx.text(sub, font_size="12px", color=accent, font_family=S.FONT_MONO, margin_top="4px"),
            spacing="2",
        ),
        **_GLASS_COMPACT,
        flex="1",
        min_width="160px",
    )


def _obra_status_strip() -> rx.Component:
    """4-card KPI strip using pre-formatted server-side strings."""
    fmt = GlobalState.obra_kpi_fmt

    return rx.flex(
        # Budget
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.center(
                        rx.icon(
                            tag="wallet",
                            size=16,
                            color=fmt["budget_color"],
                        ),
                        padding="8px",
                        bg=rx.cond(
                            fmt["budget_over"],
                            S.DANGER_BG,
                            S.PATINA_GLOW,
                        ),
                        border_radius="8px",
                        border=rx.cond(
                            fmt["budget_over"],
                            "1px solid rgba(239,68,68,0.3)",
                            "1px solid rgba(42,157,143,0.3)",
                        ),
                    ),
                    rx.vstack(
                        rx.text(
                            "Budget Realizado",
                            font_size="11px",
                            color=S.TEXT_MUTED,
                            text_transform="uppercase",
                            letter_spacing="0.1em",
                            font_weight="700",
                        ),
                        rx.text(
                            fmt["budget_realizado_fmt"],
                            font_family=S.FONT_TECH,
                            font_size="1.75rem",
                            font_weight="700",
                            color="white",
                            line_height="1",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.text(
                    fmt["budget_variacao_fmt"],
                    font_size="12px",
                    color=fmt["budget_color"],
                    font_family=S.FONT_MONO,
                    margin_top="4px",
                ),
                spacing="2",
            ),
            **_GLASS_COMPACT,
            flex="1",
            min_width="160px",
        ),
        # Equipe
        _kpi_card_static(
            "users",
            "Equipe em Campo",
            fmt["equipe_val"],
            fmt["equipe_sub"],
            S.COPPER,
            S.COPPER_GLOW,
            S.BORDER_ACCENT,
        ),
        # Disciplinas em risco
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="layout-grid", size=16, color=fmt["disc_icon_color"]),
                        padding="8px",
                        bg="rgba(42,157,143,0.08)",
                        border_radius="8px",
                        border="1px solid rgba(42,157,143,0.2)",
                    ),
                    rx.vstack(
                        rx.text(
                            "Disciplinas em Risco",
                            font_size="11px",
                            color=S.TEXT_MUTED,
                            text_transform="uppercase",
                            letter_spacing="0.1em",
                            font_weight="700",
                        ),
                        rx.text(
                            fmt["disc_val"],
                            font_family=S.FONT_TECH,
                            font_size="1.75rem",
                            font_weight="700",
                            color="white",
                            line_height="1",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.text(
                    fmt["disc_sub"],
                    font_size="12px",
                    color=fmt["disc_icon_color"],
                    font_family=S.FONT_MONO,
                    margin_top="4px",
                ),
                spacing="2",
            ),
            **_GLASS_COMPACT,
            flex="1",
            min_width="160px",
        ),
        # Risco
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="shield-alert", size=16, color=fmt["risco_color"]),
                        padding="8px",
                        bg=fmt["risco_bg"],
                        border_radius="8px",
                        border=rx.cond(
                            fmt["risco_val"].to(int) >= 60,
                            "1px solid rgba(239,68,68,0.3)",
                            rx.cond(
                                fmt["risco_val"].to(int) >= 30,
                                "1px solid rgba(245,158,11,0.3)",
                                "1px solid rgba(42,157,143,0.3)",
                            ),
                        ),
                    ),
                    rx.vstack(
                        rx.text(
                            "Score de Risco",
                            font_size="11px",
                            color=S.TEXT_MUTED,
                            text_transform="uppercase",
                            letter_spacing="0.1em",
                            font_weight="700",
                        ),
                        rx.hstack(
                            rx.text(
                                fmt["risco_val"],
                                font_family=S.FONT_TECH,
                                font_size="1.75rem",
                                font_weight="700",
                                color="white",
                            ),
                            rx.text(
                                "/100",
                                font_size="0.875rem",
                                color=S.TEXT_MUTED,
                                align_self="flex-end",
                                padding_bottom="3px",
                            ),
                            spacing="1",
                            align="end",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.text(
                    fmt["risco_label"],
                    font_size="12px",
                    color=fmt["risco_color"],
                    font_family=S.FONT_MONO,
                    font_weight="700",
                    margin_top="4px",
                ),
                spacing="2",
            ),
            **_GLASS_COMPACT,
            flex="1",
            min_width="160px",
        ),
        gap="16px",
        flex_wrap=rx.breakpoints(initial="wrap", lg="nowrap"),
        width="100%",
    )


# ── 2. COMPACT DETAIL INFO ────────────────────────────────────


def _obra_compact_info() -> rx.Component:
    """Horizontal info bar — 6 equal columns via CSS grid (guaranteed equal width)."""
    data = GlobalState.obra_enterprise_data
    fmt = GlobalState.obra_kpi_fmt

    def chip(icon_tag: str, label: str, value, accent: bool = False) -> rx.Component:
        """Vertically stacked chip: icon · label · value — centered in its grid cell."""
        return rx.vstack(
            rx.icon(
                tag=icon_tag,
                size=16,
                color=S.COPPER if accent else S.TEXT_MUTED,
            ),
            rx.text(
                label,
                font_size="9px",
                color=S.TEXT_MUTED,
                text_transform="uppercase",
                letter_spacing="0.1em",
                font_weight="700",
            ),
            rx.text(
                value,
                font_size="15px",
                font_weight="700",
                color=S.COPPER if accent else "white",
                font_family=S.FONT_MONO if not accent else S.FONT_TECH,
                white_space="nowrap",
                overflow="hidden",
                text_overflow="ellipsis",
                max_width="100%",
            ),
            align="center",
            spacing="1",
            width="100%",
            border_right=f"1px solid {S.BORDER_SUBTLE}",
            padding="8px 12px",
        )

    return rx.box(
        rx.box(
            # 6 equal columns — each chip gets exactly 1/6 of the width
            chip("hash", "Contrato", data["contrato"], accent=True),
            chip("building-2", "Cliente", data["cliente"]),
            chip("zap", "Potência", data.get("potencia_kwp", "—"), accent=True),
            chip("map-pin", "Localização", data.get("localizacao", "—")),
            chip("clock", "Prazo", data.get("prazo_dias", "—")),
            # Avanço badge — last cell, no right border
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="trending-up", size=16, color=S.PATINA),
                    rx.text(
                        fmt["avanco_fmt"],
                        font_family=S.FONT_TECH,
                        font_size="1.5rem",
                        font_weight="700",
                        color="white",
                        white_space="nowrap",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    "Avanço Médio",
                    font_size="9px",
                    color=S.TEXT_MUTED,
                    text_transform="uppercase",
                    letter_spacing="0.1em",
                    font_weight="700",
                ),
                align="center",
                spacing="1",
                padding="16px 12px",
                width="100%",
            ),
            display="grid",
            grid_template_columns=["repeat(2, minmax(0,1fr))", "repeat(3, minmax(0,1fr))", "repeat(6, minmax(0,1fr))"],
            width="100%",
            overflow="hidden",
            align_items="center",
        ),
        **S.GLASS_CARD,
        flex="2",
    )


# ── 3. DISCIPLINE SEMI-CIRCLE GAUGES ─────────────────────────


def _mini_semi_gauge(item: dict) -> rx.Component:
    """Semi-circular SVG gauge per discipline.
    SVG math: r=38, C≈238.76, SEMI≈119.38
    stroke-dashoffset=-119.38 starts arc at 9-o'clock (left side).
    viewBox clips the bottom half, showing only the top arc.
    Previsto shown as white dot marker on the arc edge.
    """
    return rx.vstack(
        rx.box(
            rx.el.svg(
                # Background track
                rx.el.circle(
                    cx="50",
                    cy="50",
                    r="38",
                    stroke="rgba(255,255,255,0.07)",
                    stroke_width="10",
                    fill="transparent",
                    stroke_dasharray="119.38 238.76",
                    stroke_dashoffset="-119.38",
                    stroke_linecap="round",
                ),
                # Realizado filled arc
                rx.el.circle(
                    cx="50",
                    cy="50",
                    r="38",
                    stroke=item["color"],
                    stroke_width="10",
                    fill="transparent",
                    stroke_dasharray=item["realizado_dash"],
                    stroke_dashoffset="-119.38",
                    stroke_linecap="round",
                    style={"transition": "stroke-dasharray 1.2s ease-out"},
                ),
                # Previsto dot marker at the target position
                rx.el.circle(
                    cx=item["marker_cx"],
                    cy=item["marker_cy"],
                    r="5",
                    fill="white",
                    stroke="rgba(0,0,0,0.4)",
                    stroke_width="1.5",
                ),
                view_box="7 7 86 47",
                width="150",
                height="84",
                overflow="visible",
            ),
            # Percentage text centered at the arc base
            rx.box(
                rx.text(
                    item["realizado_pct_fmt"],
                    font_family=S.FONT_TECH,
                    font_size="1.4rem",
                    font_weight="700",
                    color="white",
                    text_align="center",
                ),
                position="absolute",
                bottom="0px",
                left="0",
                right="0",
                text_align="center",
            ),
            position="relative",
            width="150px",
            height="100px",
        ),
        rx.text(
            item["categoria"],
            font_size="13px",
            color=S.TEXT_MUTED,
            text_align="center",
            text_transform="uppercase",
            letter_spacing="0.05em",
            font_weight="700",
            max_width="140px",
            white_space="nowrap",
            overflow="hidden",
            text_overflow="ellipsis",
        ),
        rx.text(
            item["pr_label"],
            font_size="11px",
            color=item["color"],
            font_family=S.FONT_MONO,
            text_align="center",
        ),
        spacing="2",
        align="center",
    )


def _discipline_gauges_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="gauge", size=16, color=S.COPPER, margin_right="8px"),
                rx.text(
                    "Progresso por Disciplina",
                    font_family=S.FONT_TECH,
                    font_size="1.25rem",
                    font_weight="700",
                    color="white",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.box(
                        width="8px",
                        height="8px",
                        border_radius="50%",
                        bg="rgba(255, 255, 255, 0.4)",
                        border="1.5px solid rgba(0,0,0,0.4)",
                        flex_shrink="0",
                    ),
                    rx.text(
                        "Meta",
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        font_weight="700",
                    ),
                    rx.box(width="8px"),
                    rx.box(
                        width="20px",
                        height="4px",
                        bg=S.PATINA,
                        border_radius="2px",
                        flex_shrink="0",
                    ),
                    rx.text(
                        "Realizado",
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        font_weight="700",
                    ),
                    align="center",
                    spacing="2",
                ),
                align="center",
                margin_bottom="24px",
                width="100%",
            ),
            rx.cond(
                GlobalState.disciplina_gauges_list,
                rx.flex(
                    rx.foreach(GlobalState.disciplina_gauges_list, _mini_semi_gauge),
                    gap="40px",
                    flex_wrap="wrap",
                    justify_content="center",
                    width="100%",
                ),
                rx.center(
                    rx.text("Sem dados de disciplinas", font_size="13px", color=S.TEXT_MUTED),
                    height="80px",
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
        width="100%",
    )


# ── 4. BUDGET PANEL ────────────────────────────────────────────


def _obra_budget_panel() -> rx.Component:
    fmt = GlobalState.obra_kpi_fmt

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="chart-bar", size=16, color=S.COPPER, margin_right="8px"),
                rx.text(
                    "Desempenho Orçamentário",
                    font_family=S.FONT_TECH,
                    font_size="1.25rem",
                    font_weight="700",
                    color="white",
                ),
                align="center",
                margin_bottom="20px",
            ),
            # Values row
            rx.grid(
                rx.vstack(
                    rx.text(
                        "PLANEJADO",
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.1em",
                        font_weight="700",
                    ),
                    rx.text(
                        fmt["budget_planejado_fmt"],
                        font_family=S.FONT_TECH,
                        font_size="2rem",
                        font_weight="700",
                        color="white",
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text(
                        "REALIZADO",
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.1em",
                        font_weight="700",
                    ),
                    rx.text(
                        fmt["budget_realizado_fmt"],
                        font_family=S.FONT_TECH,
                        font_size="2rem",
                        font_weight="700",
                        color="white",
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text(
                        "EXECUÇÃO",
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.1em",
                        font_weight="700",
                    ),
                    rx.hstack(
                        rx.text(
                            fmt["budget_exec_rate_fmt"],
                            font_family=S.FONT_TECH,
                            font_size="2rem",
                            font_weight="700",
                            color=fmt["budget_color"],
                        ),
                        rx.cond(
                            fmt["budget_over"],
                            rx.box(
                                rx.text(
                                    "OVER",
                                    font_size="8px",
                                    font_weight="700",
                                    color=S.DANGER,
                                ),
                                padding="2px 6px",
                                bg=S.DANGER_BG,
                                border_radius="4px",
                                border="1px solid rgba(239,68,68,0.3)",
                                align_self="center",
                            ),
                        ),
                        spacing="2",
                        align="end",
                    ),
                    rx.text(
                        fmt["budget_variacao_fmt"],
                        font_size="12px",
                        color=fmt["budget_color"],
                        font_family=S.FONT_MONO,
                        max_width="220px",
                    ),
                    spacing="1",
                ),
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="6",
                width="100%",
                margin_bottom="20px",
            ),
            # Progress bar (capped at 100% visually, real % shown above)
            rx.box(
                rx.box(
                    width=fmt["budget_bar_pct"].to_string() + "%",
                    height="100%",
                    bg=rx.cond(
                        fmt["budget_over"],
                        f"linear-gradient(90deg, {S.DANGER}, #B91C1C)",
                        f"linear-gradient(90deg, {S.PATINA}, {S.PATINA_DARK})",
                    ),
                    border_radius="9999px",
                    transition="width 1.2s ease-out",
                ),
                height="8px",
                bg="rgba(255,255,255,0.05)",
                border_radius="9999px",
                overflow="hidden",
                width="100%",
            ),
            rx.hstack(
                rx.text("0%", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                rx.spacer(),
                rx.text(
                    fmt["budget_bar_label"],
                    font_size="9px",
                    color=fmt["budget_color"],
                    font_family=S.FONT_MONO,
                    font_weight="700",
                ),
                rx.spacer(),
                rx.text("100%", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                width="100%",
                margin_top="6px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
        width="100%",
    )


# ── 5. AI INSIGHT PANEL ────────────────────────────────────────


def _obra_ai_insight_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(tag="brain-circuit", size=16, color=S.COPPER),
                    padding="8px",
                    bg=S.COPPER_GLOW,
                    border_radius="8px",
                    border=f"1px solid {S.BORDER_ACCENT}",
                ),
                rx.vstack(
                    rx.text(
                        "Inteligência Ativa",
                        font_family=S.FONT_TECH,
                        font_size="1.1rem",
                        font_weight="700",
                        color=S.COPPER,
                    ),
                    rx.text(
                        "Diagnóstico automático por IA",
                        font_size="10px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="0",
                ),
                align="center",
                spacing="3",
                margin_bottom="16px",
            ),
            rx.cond(
                GlobalState.obra_insight_loading,
                rx.vstack(
                    rx.hstack(
                        rx.spinner(size="2", color=S.COPPER),
                        rx.text(
                            "Analisando dados da obra...",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            font_style="italic",
                        ),
                        align="center",
                        spacing="3",
                    ),
                    rx.vstack(
                        rx.box(
                            height="10px",
                            bg="rgba(201,139,42,0.1)",
                            border_radius="4px",
                            width="100%",
                        ),
                        rx.box(
                            height="10px",
                            bg="rgba(201,139,42,0.07)",
                            border_radius="4px",
                            width="82%",
                        ),
                        rx.box(
                            height="10px",
                            bg="rgba(201,139,42,0.04)",
                            border_radius="4px",
                            width="65%",
                        ),
                        spacing="2",
                        width="100%",
                        margin_top="10px",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.cond(
                    GlobalState.obra_insight_text != "",
                    rx.box(
                        rx.text(
                            GlobalState.obra_insight_text,
                            font_size="0.875rem",
                            color=S.TEXT_PRIMARY,
                            line_height="1.75",
                        ),
                        padding="16px 18px",
                        bg="rgba(201,139,42,0.04)",
                        border_radius="12px",
                        border=f"1px solid {S.BORDER_ACCENT}",
                        border_left=f"3px solid {S.COPPER}",
                        width="100%",
                    ),
                    rx.text(
                        "Selecione uma obra para gerar o diagnóstico.",
                        font_size="12px",
                        color=S.TEXT_MUTED,
                        font_style="italic",
                    ),
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
        width="100%",
    )


# ── 6. CRITICAL ALERTS ────────────────────────────────────────



# ── DETAIL VIEW ASSEMBLY ──────────────────────────────────────


def obra_detail_view() -> rx.Component:
    """Full detail view — storytelling order:
    1. Status strip (4 KPI cards)
    2. [Info bar + AI Insight stacked] | Weather (side by side)
    3. Discipline semi-gauges (full width)
    4. Budget (full width, alone)
    """
    return rx.vstack(
        # 1 — Status strip
        _obra_status_strip(),
        # 2 — Left: info bar + AI insight | Right: weather
        rx.flex(
            rx.vstack(
                _obra_compact_info(),
                _obra_ai_insight_panel(),
                flex=rx.breakpoints(initial="0 0 100%", lg="2"),
                spacing="6",
                width="100%",
                min_width="280px",
            ),
            rx.box(
                weather_widget(),
                flex=rx.breakpoints(initial="0 0 100%", lg="1"),
                min_width="200px",
            ),
            width="100%",
            gap="1.5rem",
            flex_wrap=rx.breakpoints(initial="wrap", lg="nowrap"),
            align_items="stretch",
        ),
        # 3 — Discipline gauges (full width)
        _discipline_gauges_section(),
        # 4 — Budget (full width, solo)
        _obra_budget_panel(),
        width="100%",
        spacing="6",
        class_name="animate-enter",
    )


# ══════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════


def obras_page() -> rx.Component:
    return rx.vstack(
        obras_header(),
        rx.cond(
            GlobalState.is_loading,
            page_loading_skeleton(),
            rx.cond(
                GlobalState.obras_selected_contract != "",
                obra_detail_view(),
                obras_list_view(),
            ),
        ),
        width="100%",
        spacing="8",
        class_name="animate-enter",
        on_mount=lambda: GlobalState.set_current_path("/obras"),
    )
