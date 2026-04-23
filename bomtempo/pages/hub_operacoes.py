"""
Hub de Operações — Unified Operations Hub
Merges former Obras (field ops) + Projetos (project portfolio) into one module.
Route: /hub

Replaces obras.py + projetos.py with a single, richer unified view:
  - Landing: Project Pulse Cards grid
  - Detail: 5-tab hub (Visão Geral, Dashboard, Cronograma, Auditoria, Timeline)
"""
import reflex as rx

from bomtempo.components.skeletons import page_loading_skeleton
from bomtempo.components.windy_map_widget import windy_map_widget
from bomtempo.components.tooltips import (
    gantt_hover_content,
    TOOLTIP_SPLIT,
    TOOLTIP_SIGNAL,
    TOOLTIP_SPI_RING,
    TOOLTIP_PILL,
    TOOLTIP_STACK_DISC,
)
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.ui_state import UIState
from bomtempo.state.hub_state import HubState, AUDIT_CATEGORIES, ENTRY_TYPES
from bomtempo.state.fin_state import FinState, FIN_STATUS_LABELS, FIN_STATUS_OPTIONS

# ── Local glass card variants ──────────────────────────────────────────────────
_GLASS_COMPACT = {**S.GLASS_CARD, "padding": "16px 20px"}
_GLASS_PANEL   = {**S.GLASS_CARD, "padding": "20px 24px"}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — LANDING PAGE: PROJECT PULSE CARDS
# ══════════════════════════════════════════════════════════════════════════════


def hub_pulse_card(item: dict) -> rx.Component:
    """Enterprise project pulse card — matched to Deep Tectonic design system."""
    avanco = item["progress"].to(float).to(int)

    return rx.box(
        # ── The clickable card ────────────────────────────────────────────────
        rx.box(
        # ── Top row: contract code + status badge ─────────────────────────────
        rx.hstack(
            rx.text(
                item["contrato"],
                font_family=S.FONT_MONO,
                font_size="11px",
                font_weight="700",
                color=S.COPPER,
                letter_spacing="0.05em",
            ),
            rx.box(
                item["status"],
                padding="2px 8px",
                background=item["status_bg"],
                color=item["status_color"],
                font_size="10px",
                font_family=S.FONT_MONO,
                text_transform="uppercase",
                letter_spacing="-0.01em",
                border=f"1px solid {item['status_color']}",
                border_radius="2px",
            ),
            justify="between",
            align="start",
            margin_bottom="20px",
            width="100%",
        ),
        # ── Client / project name ─────────────────────────────────────────────
        rx.text(
            item["cliente"],
            font_family=S.FONT_TECH,
            font_size="1.4rem",
            font_weight="700",
            text_transform="uppercase",
            line_height="1.2",
            margin_bottom="4px",
            color="var(--text-main)",
        ),
        # ── Location row ──────────────────────────────────────────────────────
        rx.hstack(
            rx.icon(tag="map-pin", size=13, color=S.TEXT_MUTED),
            rx.text(
                item["localizacao"],
                font_size="12px",
                font_family=S.FONT_BODY,
                color=S.TEXT_MUTED,
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            spacing="2",
            align="center",
            margin_bottom="20px",
            width="100%",
        ),
        rx.spacer(),
        # ── Progress + deadline ───────────────────────────────────────────────
        rx.box(
            # Label row
            rx.hstack(
                rx.text(
                    "PROGRESS PULSE",
                    font_family=S.FONT_MONO,
                    font_size="9px",
                    color=S.TEXT_MUTED,
                    text_transform="uppercase",
                    letter_spacing="0.1em",
                ),
                rx.spacer(),
                rx.text(
                    avanco.to_string() + "%",
                    font_family=S.FONT_MONO,
                    font_size="14px",
                    font_weight="700",
                    color=item["status_color"],
                ),
                width="100%",
                align="center",
                margin_bottom="6px",
            ),
            # Progress track
            rx.box(
                rx.box(
                    height="100%",
                    bg=item["status_color"],
                    width=avanco.to_string() + "%",
                    border_radius="2px",
                    transition="width 1.1s ease-out",
                ),
                height="3px",
                bg="rgba(44,55,52,1)",
                width="100%",
                margin_bottom="20px",
                border_radius="2px",
            ),
            # Deadline + risk row
            rx.hstack(
                rx.vstack(
                    rx.text(
                        "DEADLINE",
                        font_family=S.FONT_MONO,
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                    ),
                    rx.text(
                        item["days_fmt"],
                        font_family=S.FONT_MONO,
                        font_size="12px",
                        font_weight="600",
                        color=rx.cond(
                            item["days_to_deadline"].to(int) < 0,
                            S.DANGER,
                            "var(--text-main)",
                        ),
                    ),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                # Risk badge pill
                rx.hstack(
                    rx.box(
                        width="6px",
                        height="6px",
                        border_radius="50%",
                        bg=item["risco_color"],
                        class_name=rx.cond(
                            item["days_to_deadline"].to(int) < 0,
                            "animate-pulse",
                            "",
                        ),
                    ),
                    rx.text(
                        item["risco_label"],
                        font_family=S.FONT_MONO,
                        font_size="9px",
                        text_transform="uppercase",
                        letter_spacing="0.05em",
                        font_weight="700",
                        color=item["risco_color"],
                    ),
                    padding="4px 8px",
                    bg="rgba(255,255,255,0.05)",
                    border="1px solid rgba(255,255,255,0.1)",
                    border_radius="4px",
                    align="center",
                    spacing="2",
                ),
                width="100%",
                align="center",
            ),
            width="100%",
        ),
        # ── Card container ────────────────────────────────────────────────────
        background="rgba(14,26,23,0.6)",
        backdrop_filter="blur(12px)",
        border="1px solid rgba(255,255,255,0.08)",
        border_radius=S.R_CARD,
        padding="20px",
        display="flex",
        flex_direction="column",
        height="100%",
        min_height="280px",
        cursor="pointer",
        on_click=GlobalState.select_project(item["contrato"]),
        transition="all 0.25s cubic-bezier(0.4,0,0.2,1)",
        _hover={
            "background": "rgba(14,26,23,0.95)",
            "border_color": "rgba(201,139,42,0.5)",
            "box_shadow": (
                "0 0 0 1px rgba(201,139,42,0.15),"
                "0 12px 40px rgba(0,0,0,0.5),"
                "0 0 50px rgba(201,139,42,0.07)"
            ),
            "transform": "translateY(-3px)",
        },
        ),
        # ── Edit button (absolute, does not bubble to card click) ─────────────
        rx.box(
            rx.icon_button(
                rx.icon(tag="pencil", size=11),
                size="1",
                variant="ghost",
                on_click=GlobalState.open_edit_projeto(item["contrato"]),
                color=S.TEXT_MUTED,
                cursor="pointer",
                _hover={"color": S.COPPER, "background": "rgba(201,139,42,0.1)"},
            ),
            position="absolute",
            top="10px",
            right="10px",
            z_index="10",
        ),
        position="relative",
        height="100%",
    )


def hub_landing_page() -> rx.Component:
    """Landing view — header + search + project pulse cards grid."""
    return rx.vstack(
        # ── Header row ─────────────────────────────────────────────────────────
        rx.flex(
            # Left: title block
            rx.vstack(
                rx.text(
                    "HUB DE OPERAÇÕES",
                    font_family=S.FONT_TECH,
                    font_size="clamp(1.5rem,4vw,2.5rem)",
                    font_weight="700",
                    text_transform="uppercase",
                    letter_spacing="0.05em",
                    color="var(--text-main)",
                    line_height="1.1",
                ),
                rx.text(
                    "Gestão centralizada de frentes de obra, orçamentos e "
                    "cronogramas críticos em tempo real.",
                    font_family=S.FONT_BODY,
                    font_size="14px",
                    color=S.TEXT_MUTED,
                    margin_top="4px",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            # Right: action buttons
            rx.hstack(
                # FILTRAR
                rx.button(
                    rx.hstack(
                        rx.icon(tag="filter", size=14),
                        rx.text(
                            "FILTRAR",
                            font_family=S.FONT_TECH,
                            font_size="13px",
                            font_weight="700",
                            letter_spacing="0.08em",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    on_click=GlobalState.toggle_hub_filters,
                    bg=rx.cond(GlobalState.hub_show_filters, "rgba(201,139,42,0.15)", "rgba(19,29,27,1)"),
                    color="var(--text-main)",
                    border=rx.cond(GlobalState.hub_show_filters, f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
                    padding="8px 16px",
                    border_radius=S.R_CONTROL,
                    _hover={"border_color": "rgba(201,139,42,0.4)", "bg": "rgba(30,52,48,1)"},
                    cursor="pointer",
                    transition="all 0.2s ease",
                ),
                # DUPLICAR
                rx.button(
                    rx.hstack(
                        rx.icon(tag="copy", size=14),
                        rx.text(
                            "DUPLICAR",
                            font_family=S.FONT_TECH,
                            font_size="13px",
                            font_weight="700",
                            letter_spacing="0.08em",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    on_click=GlobalState.open_duplicar_projeto,
                    bg="rgba(19,29,27,1)",
                    color="var(--text-main)",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    padding="8px 16px",
                    border_radius=S.R_CONTROL,
                    _hover={"border_color": "rgba(201,139,42,0.4)", "bg": "rgba(30,52,48,1)"},
                    cursor="pointer",
                    transition="all 0.2s ease",
                ),
                # NOVO PROJETO
                rx.button(
                    rx.hstack(
                        rx.icon(tag="plus", size=14),
                        rx.text(
                            "NOVO PROJETO",
                            font_family=S.FONT_TECH,
                            font_size="13px",
                            font_weight="700",
                            letter_spacing="0.08em",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    on_click=GlobalState.open_novo_projeto,
                    background="linear-gradient(135deg, #C98B2A 0%, #835500 100%)",
                    color="#3d2500",
                    border="none",
                    padding="8px 20px",
                    border_radius=S.R_CONTROL,
                    box_shadow="0 0 18px rgba(201,139,42,0.28)",
                    _hover={"filter": "brightness(1.1)", "box_shadow": "0 0 24px rgba(201,139,42,0.4)"},
                    cursor="pointer",
                    transition="all 0.2s ease",
                ),
                spacing="3",
                align="center",
                flex_wrap="wrap",
            ),
            width="100%",
            direction=rx.breakpoints(initial="column", md="row"),
            justify="between",
            align=rx.breakpoints(initial="start", md="center"),
            gap="1.25rem",
            margin_bottom="28px",
        ),
        # ── Filter panel ───────────────────────────────────────────────────────
        rx.cond(
            GlobalState.hub_show_filters,
            rx.box(
                rx.vstack(
                    # Row: Tipo
                    rx.hstack(
                        rx.text("TIPO", font_size="10px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, letter_spacing="0.08em", min_width="60px"),
                        *[
                            rx.button(
                                label,
                                on_click=GlobalState.set_hub_filter_tipo(value),
                                size="1",
                                font_family=S.FONT_MONO,
                                font_size="11px",
                                cursor="pointer",
                                bg=rx.cond(GlobalState.hub_filter_tipo == value, S.COPPER, "rgba(14,26,23,0.8)"),
                                color=rx.cond(GlobalState.hub_filter_tipo == value, S.BG_VOID, "var(--text-main)"),
                                border=rx.cond(GlobalState.hub_filter_tipo == value, f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
                                border_radius="2px",
                                _hover={"border_color": S.COPPER},
                                transition="all 0.15s ease",
                            )
                            for label, value in [("EPC", "EPC"), ("O&M", "O&M"), ("Fornecimento", "Fornecimento"), ("Consultoria", "Consultoria")]
                        ],
                        spacing="2",
                        align="center",
                        flex_wrap="wrap",
                    ),
                    # Row: Status
                    rx.hstack(
                        rx.text("STATUS", font_size="10px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, letter_spacing="0.08em", min_width="60px"),
                        *[
                            rx.button(
                                label,
                                on_click=GlobalState.set_project_status_filter(value),
                                size="1",
                                font_family=S.FONT_MONO,
                                font_size="11px",
                                cursor="pointer",
                                bg=rx.cond(GlobalState.project_status_filter == value, S.PATINA, "rgba(14,26,23,0.8)"),
                                color=rx.cond(GlobalState.project_status_filter == value, "white", "var(--text-main)"),
                                border=rx.cond(GlobalState.project_status_filter == value, f"1px solid {S.PATINA}", f"1px solid {S.BORDER_SUBTLE}"),
                                border_radius="2px",
                                _hover={"border_color": S.PATINA},
                                transition="all 0.15s ease",
                            )
                            for label, value in [("Em Execução", "Em Execução"), ("Concluído", "Concluído"), ("Paralisado", "Paralisado"), ("Planejado", "Planejado")]
                        ],
                        spacing="2",
                        align="center",
                        flex_wrap="wrap",
                    ),
                    # Row: Prioridade
                    rx.hstack(
                        rx.text("PRIORIDADE", font_size="10px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, letter_spacing="0.08em", min_width="60px"),
                        *[
                            rx.button(
                                label,
                                on_click=GlobalState.set_hub_filter_priority(value),
                                size="1",
                                font_family=S.FONT_MONO,
                                font_size="11px",
                                cursor="pointer",
                                bg=rx.cond(GlobalState.hub_filter_priority == value, color_on, "rgba(14,26,23,0.8)"),
                                color=rx.cond(GlobalState.hub_filter_priority == value, "white", "var(--text-main)"),
                                border=rx.cond(GlobalState.hub_filter_priority == value, f"1px solid {color_on}", f"1px solid {S.BORDER_SUBTLE}"),
                                border_radius="2px",
                                _hover={"border_color": color_on},
                                transition="all 0.15s ease",
                            )
                            for label, value, color_on in [("Alta", "Alta", S.DANGER), ("Média", "Média", S.WARNING), ("Baixa", "Baixa", S.PATINA)]
                        ],
                        spacing="2",
                        align="center",
                        flex_wrap="wrap",
                    ),
                    # Clear filters
                    rx.button(
                        rx.hstack(rx.icon(tag="x", size=11), rx.text("LIMPAR FILTROS", font_size="10px"), spacing="1"),
                        on_click=GlobalState.clear_hub_filters,
                        size="1",
                        variant="ghost",
                        color=S.TEXT_MUTED,
                        cursor="pointer",
                        _hover={"color": S.COPPER},
                        font_family=S.FONT_MONO,
                    ),
                    spacing="3",
                    align="start",
                    width="100%",
                ),
                bg="rgba(14,26,23,0.7)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius=S.R_CARD,
                padding="16px 20px",
                margin_bottom="20px",
                width="100%",
            ),
        ),
        # ── Cards grid ─────────────────────────────────────────────────────────
        rx.cond(
            GlobalState.project_pulse_cards,
            rx.grid(
                rx.foreach(GlobalState.project_pulse_cards, hub_pulse_card),
                columns=rx.breakpoints(initial="1", md="2", lg="3"),
                gap="20px",
                width="100%",
                class_name="animate-enter",
            ),
            rx.center(
                rx.vstack(
                    rx.icon(
                        tag="folder-kanban",
                        size=48,
                        color=S.BORDER_SUBTLE,
                    ),
                    rx.text(
                        "Nenhum projeto encontrado",
                        font_size="1rem",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_TECH,
                        font_weight="700",
                        text_transform="uppercase",
                    ),
                    rx.text(
                        "Ajuste os filtros ou verifique a conexão com o banco de dados.",
                        font_size="13px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_BODY,
                    ),
                    spacing="3",
                    align="center",
                ),
                height="40vh",
                width="100%",
            ),
        ),
        width="100%",
        spacing="0",
        align="start",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SHARED NAV BAR — appears at top of detail view
# ══════════════════════════════════════════════════════════════════════════════


def _hub_navbar() -> rx.Component:
    """Sticky nav bar with back button + tab list for the detail hub."""

    def _tab(label: str, value: str, icon_tag: str) -> rx.Component:
        is_active = GlobalState.project_hub_tab == value
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
            on_click=GlobalState.set_project_hub_tab(value),
            _hover={"& > div > p": {"color": "rgba(218,229,225,0.9)"}},
            transition="border-color 0.2s ease",
        )

    return rx.box(
        rx.flex(
            # Back button + project code
            rx.hstack(
                rx.icon_button(
                    rx.icon(tag="chevron-left", size=18, color="var(--text-main)"),
                    variant="ghost",
                    on_click=GlobalState.deselect_project,
                    _hover={"bg": "rgba(255,255,255,0.06)"},
                    cursor="pointer",
                    border_radius="4px",
                    size="2",
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text(
                        GlobalState.selected_project,
                        font_family=S.FONT_TECH,
                        font_size="1.2rem",
                        font_weight="700",
                        color="var(--text-main)",
                        letter_spacing="-0.01em",
                    ),
                    rx.text(
                        "HUB DE OPERAÇÕES",
                        font_family=S.FONT_MONO,
                        font_size="9px",
                        color=S.COPPER,
                        text_transform="uppercase",
                        letter_spacing="0.12em",
                    ),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
            ),
            # Tab strip — horizontal scroll on all screen sizes
            rx.box(
                rx.hstack(
                    _tab("Visão Geral",  "visao_geral",  "layout-dashboard"),
                    _tab("Dashboard",    "dashboard",     "bar-chart-3"),
                    _tab("Cronograma",   "cronograma",    "calendar-range"),
                    _tab("Auditoria",    "auditoria",     "scan-eye"),
                    _tab("Timeline",     "timeline",      "git-branch"),
                    _tab("Financeiro",   "financeiro",    "wallet"),
                    spacing="4",
                    align="end",
                    flex_shrink="0",
                ),
                overflow_x="auto",
                # Subtle fade at right edge when scrollable
                _after={
                    "content": "''",
                    "position": "absolute",
                    "right": "0",
                    "top": "0",
                    "bottom": "0",
                    "width": "24px",
                    "pointerEvents": "none",
                },
                position="relative",
                style={"scrollbar-width": "none", "-ms-overflow-style": "none"},
                class_name="hide-scrollbar",
                flex="1",
                min_width="0",
            ),
            width="100%",
            justify="between",
            align="end",
            gap="12px",
            flex_wrap="wrap",
        ),
        padding="14px 20px",
        background="rgba(14,26,23,0.7)",
        backdrop_filter="blur(24px)",
        border="1px solid rgba(255,255,255,0.06)",
        border_radius="8px",
        box_shadow="0 16px 40px rgba(0,0,0,0.35), 0 0 8px rgba(42,157,143,0.04)",
        margin_bottom="24px",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VISÃO GERAL
# ══════════════════════════════════════════════════════════════════════════════


def _vg_kpi_card(
    icon_tag: str,
    label: str,
    value,
    subtitle,
    value_color: str = "var(--text-main)",
    bar_pct=None,
) -> rx.Component:
    """Compact KPI tile for the visão geral strip."""
    return rx.box(
        rx.text(
            label,
            font_size="9px",
            font_family=S.FONT_MONO,
            color="rgba(218,229,225,0.5)",
            text_transform="uppercase",
            letter_spacing="0.1em",
            margin_bottom="6px",
        ),
        rx.hstack(
            rx.center(
                rx.icon(tag=icon_tag, size=14, color=value_color),
                width="28px",
                height="28px",
                bg="rgba(255,255,255,0.04)",
                border_radius="4px",
                flex_shrink="0",
            ),
            rx.text(
                value,
                font_family=S.FONT_TECH,
                font_size="2rem",
                font_weight="700",
                color=value_color,
                line_height="1",
            ),
            spacing="3",
            align="center",
            margin_bottom="4px",
        ),
        rx.cond(
            bar_pct != None,
            rx.box(
                rx.box(
                    height="100%",
                    bg=value_color,
                    width=bar_pct,
                    border_radius="2px",
                    transition="width 1.2s ease-out",
                ),
                height="3px",
                bg="rgba(255,255,255,0.06)",
                border_radius="2px",
                overflow="hidden",
                width="100%",
                margin_top="6px",
            ),
            rx.text(
                subtitle,
                font_size="10px",
                font_family=S.FONT_MONO,
                color=S.TEXT_MUTED,
            ),
        ),
        **_GLASS_COMPACT,
        flex="1",
        min_width="150px",
        flex_direction="column",
        display="flex",
    )


def _vg_weather_card() -> rx.Component:
    """Compact weather KPI tile — shows temp + condition + wind."""
    wd = GlobalState.weather_data
    return rx.box(
        rx.text(
            "TELEMETRIA AMBIENTAL",
            font_size="9px",
            font_family=S.FONT_MONO,
            color="rgba(218,229,225,0.5)",
            text_transform="uppercase",
            letter_spacing="0.1em",
            margin_bottom="6px",
        ),
        rx.cond(
            GlobalState.weather_loading,
            rx.hstack(
                rx.spinner(size="2", color=S.PATINA),
                rx.text("Carregando...", font_size="12px", color=S.TEXT_MUTED),
                spacing="3",
                align="center",
            ),
            rx.cond(
                GlobalState.weather_data != {},
                rx.hstack(
                    rx.center(
                        rx.icon(tag="thermometer", size=14, color=S.PATINA),
                        width="28px",
                        height="28px",
                        bg="rgba(42,157,143,0.1)",
                        border_radius="4px",
                        flex_shrink="0",
                    ),
                    rx.vstack(
                        rx.text(
                            wd["temp"].to_string() + "°C",
                            font_family=S.FONT_TECH,
                            font_size="2rem",
                            font_weight="700",
                            color=S.PATINA,
                            line_height="1",
                        ),
                        rx.hstack(
                            rx.text(
                                wd.get("condition", "—"),
                                font_size="10px",
                                color=S.TEXT_MUTED,
                                font_family=S.FONT_MONO,
                            ),
                            rx.text("·", font_size="10px", color=S.TEXT_MUTED),
                            rx.text(
                                wd.get("wind_speed", "—").to_string() + " km/h",
                                font_size="10px",
                                color=S.TEXT_MUTED,
                                font_family=S.FONT_MONO,
                            ),
                            spacing="1",
                            align="center",
                        ),
                        spacing="0",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.text(
                    "Sem dados climáticos",
                    font_size="12px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_MONO,
                    font_style="italic",
                ),
            ),
        ),
        **_GLASS_COMPACT,
        flex="1",
        min_width="160px",
        flex_direction="column",
        display="flex",
    )


def _vg_ai_feed() -> rx.Component:
    """AI Intelligence feed panel with LIVE badge."""
    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="brain-circuit", size=14, color=S.COPPER),
                        width="28px",
                        height="28px",
                        bg=S.COPPER_GLOW,
                        border_radius="4px",
                        border=f"1px solid {S.BORDER_ACCENT}",
                        flex_shrink="0",
                    ),
                    rx.text(
                        "FEED DE INTELIGÊNCIA IA",
                        font_family=S.FONT_TECH,
                        font_size="1rem",
                        font_weight="700",
                        text_transform="uppercase",
                        color="var(--text-main)",
                        letter_spacing="0.04em",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.spacer(),
                # Cache badge — shows time or loading state
                rx.cond(
                    GlobalState.obra_insight_loading,
                    rx.hstack(
                        rx.spinner(size="1", color=S.COPPER),
                        rx.text("analisando...", font_size="9px", color=S.COPPER, font_family=S.FONT_MONO),
                        spacing="1", align="center",
                        padding="3px 8px", border_radius="4px",
                        bg=S.COPPER_GLOW, border=f"1px solid {S.BORDER_ACCENT}",
                    ),
                    rx.cond(
                        GlobalState.obra_insight_generated_at != "",
                        rx.hstack(
                            rx.icon(tag="clock", size=10, color=S.TEXT_MUTED),
                            rx.text(GlobalState.obra_insight_generated_at, font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            spacing="1", align="center",
                        ),
                        rx.fragment(),
                    ),
                ),
                width="100%",
                align="center",
                margin_bottom="16px",
            ),
            # Feed content — AI insight from state or placeholder entries
            rx.cond(
                GlobalState.obra_insight_loading,
                rx.vstack(
                    rx.hstack(
                        rx.spinner(size="2", color=S.COPPER),
                        rx.text(
                            "Analisando dados do projeto...",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            font_style="italic",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    rx.vstack(
                        rx.box(
                            height="10px",
                            bg="rgba(201,139,42,0.09)",
                            border_radius="4px",
                            width="100%",
                        ),
                        rx.box(
                            height="10px",
                            bg="rgba(201,139,42,0.06)",
                            border_radius="4px",
                            width="80%",
                        ),
                        rx.box(
                            height="10px",
                            bg="rgba(201,139,42,0.04)",
                            border_radius="4px",
                            width="60%",
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
                        # Priority badge
                        rx.hstack(
                            rx.box(
                                "ANÁLISE IA",
                                padding="2px 8px",
                                border_radius="3px",
                                bg="rgba(201,139,42,0.12)",
                                border=f"1px solid {S.BORDER_ACCENT}",
                                font_size="9px",
                                font_family=S.FONT_MONO,
                                font_weight="700",
                                color=S.COPPER,
                                text_transform="uppercase",
                            ),
                            rx.spacer(),
                            rx.icon_button(
                                rx.icon(tag="refresh-cw", size=11),
                                size="1", variant="ghost",
                                color=S.TEXT_MUTED, cursor="pointer",
                                on_click=GlobalState.force_refresh_insight,
                                _hover={"color": S.COPPER},
                                title="Forçar nova análise",
                            ),
                            width="100%",
                            align="center",
                            margin_bottom="8px",
                        ),
                        rx.text(
                            GlobalState.obra_insight_text,
                            font_size="0.8125rem",
                            color=S.TEXT_PRIMARY,
                            line_height="1.7",
                            font_family=S.FONT_BODY,
                        ),
                        padding="14px 16px",
                        bg="rgba(201,139,42,0.04)",
                        border_radius="6px",
                        border=f"1px solid {S.BORDER_ACCENT}",
                        border_left=f"3px solid {S.COPPER}",
                        width="100%",
                    ),
                    # Static placeholder feed items when no insight yet
                    rx.vstack(
                        _static_feed_item(
                            "ALTA",
                            S.DANGER,
                            "rgba(239,68,68,0.12)",
                            "Desvio de cronograma detectado",
                            "Atividade Estrutura Metálica com atraso acumulado de 4 dias.",
                            "Ver detalhes",
                        ),
                        _static_feed_item(
                            "OTIMIZAÇÃO",
                            S.PATINA,
                            "rgba(42,157,143,0.12)",
                            "Oportunidade de aceleração",
                            "Equipe civil disponível para realocar para frente elétrica.",
                            "Ver recomendação",
                        ),
                        _static_feed_item(
                            "RELATÓRIO",
                            S.COPPER,
                            S.COPPER_GLOW,
                            "Relatório semanal gerado",
                            "Semana 14 — todas as métricas dentro do SLA contratual.",
                            "Abrir relatório",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
            ),
            width="100%",
        ),
        **_GLASS_PANEL,
        height="100%",
    )


def _static_feed_item(
    badge_label: str,
    badge_color: str,
    badge_bg: str,
    title: str,
    description: str,
    action: str,
) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.box(
                badge_label,
                padding="2px 7px",
                border_radius="3px",
                bg=badge_bg,
                border=f"1px solid {badge_color}",
                font_size="9px",
                font_family=S.FONT_MONO,
                font_weight="700",
                color=badge_color,
                text_transform="uppercase",
            ),
            rx.spacer(),
            rx.text(
                "agora",
                font_size="9px",
                color=S.TEXT_MUTED,
                font_family=S.FONT_MONO,
            ),
            width="100%",
            align="center",
            margin_bottom="5px",
        ),
        rx.text(
            title,
            font_size="13px",
            font_weight="700",
            color="var(--text-main)",
            margin_bottom="3px",
        ),
        rx.text(
            description,
            font_size="11px",
            color=S.TEXT_MUTED,
            line_height="1.5",
            margin_bottom="6px",
        ),
        rx.text(
            action + " →",
            font_size="10px",
            color=S.COPPER,
            font_family=S.FONT_MONO,
            cursor="pointer",
            _hover={"opacity": "0.75"},
        ),
        padding="12px 14px",
        border_radius="4px",
        bg="rgba(255,255,255,0.02)",
        border=f"1px solid {S.BORDER_SUBTLE}",
        _hover={"border_color": "rgba(255,255,255,0.14)", "bg": "rgba(255,255,255,0.03)"},
        transition="all 0.15s ease",
        width="100%",
    )


def _vg_site_telemetry() -> rx.Component:
    """Left column — compact site info panel."""
    data = GlobalState.obra_enterprise_data
    fmt = GlobalState.obra_kpi_fmt
    progress_pct = data.get("avanco_pct", "0").to(float).to(int).to_string() + "%"

    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.icon(tag="radio-tower", size=15, color=S.PATINA, margin_right="6px"),
                rx.text(
                    "TELEMETRIA DO SITE",
                    font_family=S.FONT_TECH,
                    font_size="1rem",
                    font_weight="700",
                    text_transform="uppercase",
                    color="var(--text-main)",
                    letter_spacing="0.04em",
                ),
                align="center",
                margin_bottom="16px",
                width="100%",
            ),
            # Location row
            rx.hstack(
                rx.icon(tag="map-pin", size=13, color=S.TEXT_MUTED),
                rx.text(
                    data.get("localizacao", "—"),
                    font_size="12px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_MONO,
                    overflow="hidden",
                    text_overflow="ellipsis",
                    white_space="nowrap",
                ),
                spacing="2",
                align="center",
                margin_bottom="16px",
                width="100%",
            ),
            # Progress physical
            rx.vstack(
                rx.hstack(
                    rx.text(
                        "PROGRESSO FÍSICO",
                        font_size="9px",
                        font_family=S.FONT_MONO,
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.1em",
                    ),
                    rx.spacer(),
                    rx.text(
                        progress_pct,
                        font_size="12px",
                        font_weight="700",
                        color=S.PATINA,
                        font_family=S.FONT_MONO,
                    ),
                    width="100%",
                    align="center",
                    margin_bottom="5px",
                ),
                rx.box(
                    rx.box(
                        height="100%",
                        bg=S.PATINA,
                        width=progress_pct,
                        transition="width 1.2s ease-out",
                        border_radius="2px",
                    ),
                    height="4px",
                    bg="rgba(255,255,255,0.05)",
                    border_radius="2px",
                    overflow="hidden",
                    width="100%",
                    margin_bottom="16px",
                ),
                spacing="0",
                width="100%",
            ),
            # Uptime metric
            rx.vstack(
                rx.hstack(
                    rx.text(
                        "UPTIME / FREQUÊNCIA AUDIT",
                        font_size="9px",
                        font_family=S.FONT_MONO,
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                        letter_spacing="0.1em",
                    ),
                    rx.spacer(),
                    rx.text(
                        "99.2%",
                        font_size="12px",
                        font_weight="700",
                        color=S.COPPER,
                        font_family=S.FONT_MONO,
                    ),
                    width="100%",
                    align="center",
                    margin_bottom="5px",
                ),
                rx.box(
                    rx.box(
                        height="100%",
                        bg=S.COPPER,
                        width="99.2%",
                        transition="width 1.2s ease-out",
                        border_radius="2px",
                    ),
                    height="4px",
                    bg="rgba(255,255,255,0.05)",
                    border_radius="2px",
                    overflow="hidden",
                    width="100%",
                ),
                spacing="0",
                width="100%",
            ),
            rx.spacer(),
            # Divider
            rx.box(height="1px", bg=S.BORDER_SUBTLE, width="100%", margin_y="12px"),
            # Contract + Client mini chips
            rx.vstack(
                rx.hstack(
                    rx.text(
                        "CONTRATO",
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_MONO,
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        min_width="80px",
                    ),
                    rx.text(
                        data.get("contrato", GlobalState.selected_project),
                        font_size="12px",
                        color=S.COPPER,
                        font_family=S.FONT_MONO,
                        font_weight="700",
                    ),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                rx.hstack(
                    rx.text(
                        "CLIENTE",
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_MONO,
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        min_width="80px",
                    ),
                    rx.text(
                        data.get("cliente", "—"),
                        font_size="12px",
                        color="var(--text-main)",
                        font_family=S.FONT_MONO,
                        overflow="hidden",
                        text_overflow="ellipsis",
                        white_space="nowrap",
                    ),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                rx.hstack(
                    rx.text(
                        "PRAZO",
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_MONO,
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        min_width="80px",
                    ),
                    rx.text(
                        data.get("prazo_dias", "—").to_string() + " dias",
                        font_size="12px",
                        color="var(--text-main)",
                        font_family=S.FONT_MONO,
                    ),
                    spacing="3",
                    align="center",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
        **_GLASS_PANEL,
        height="100%",
    )


def _risk_factor_row(fator: dict) -> rx.Component:
    """Single factor row in the Nota de Risco breakdown popup."""
    score_val = fator["score"].to(float)
    bar_pct = (score_val * 10).to_string() + "%"
    score_color = rx.cond(
        score_val >= 7, "#EF4444",
        rx.cond(score_val >= 4, "#F59E0B", "#22c55e"),
    )
    return rx.hstack(
        rx.center(
            rx.icon(tag=fator["icon"], size=13, color=score_color),
            width="28px", height="28px", border_radius="6px",
            bg=rx.cond(
                score_val >= 7, "rgba(239,68,68,0.1)",
                rx.cond(score_val >= 4, "rgba(245,158,11,0.1)", "rgba(34,197,94,0.1)"),
            ),
            flex_shrink="0",
        ),
        rx.vstack(
            rx.hstack(
                rx.text(fator["nome"], font_size="12px", font_weight="600", color="var(--text-main)", flex="1"),
                rx.text(fator["peso"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                rx.text(fator["score"], font_size="14px", font_weight="700", color=score_color, font_family=S.FONT_TECH, min_width="28px", text_align="right"),
                width="100%", align="center", spacing="2",
            ),
            rx.box(
                rx.box(height="100%", bg=score_color, width=bar_pct, border_radius="2px", transition="width 0.6s ease-out"),
                height="3px", bg="rgba(255,255,255,0.06)", border_radius="2px", overflow="hidden", width="100%",
            ),
            rx.text(fator["desc"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_BODY, line_height="1.4"),
            spacing="1", width="100%", align="start",
        ),
        spacing="3", align="start", width="100%",
        padding="12px 14px",
        border_radius="8px",
        bg="rgba(255,255,255,0.02)",
        border=f"1px solid {S.BORDER_SUBTLE}",
    )


def _risk_breakdown_dialog() -> rx.Component:
    """Popup modal — breakdown da Nota de Risco por fator."""
    rsd = GlobalState.risk_score_data
    nota = rsd.get("nota", "—")
    label = rsd.get("label", "—")
    color = rsd.get("color", S.COPPER)

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.center(
                        rx.icon(tag="shield-alert", size=22, color=color),
                        width="44px", height="44px", border_radius="10px",
                        bg=rsd.get("bg", S.COPPER_GLOW),
                        border=f"1px solid {S.BORDER_ACCENT}",
                        flex_shrink="0",
                    ),
                    rx.vstack(
                        rx.dialog.title(
                            "NOTA DE RISCO DO PROJETO",
                            color=color,
                            font_family=S.FONT_TECH,
                            font_size="1.1rem",
                            letter_spacing="0.04em",
                            margin="0",
                        ),
                        rx.text(
                            "Composição dos fatores que determinam o índice de risco",
                            color=S.TEXT_MUTED, font_size="12px", margin="0",
                        ),
                        spacing="0", align="start",
                    ),
                    rx.spacer(),
                    # Big score
                    rx.vstack(
                        rx.text(nota, font_family=S.FONT_TECH, font_size="2.2rem", font_weight="700", color=color, line_height="1"),
                        rx.box(
                            label,
                            padding="2px 8px", border_radius="3px", font_size="9px",
                            font_family=S.FONT_MONO, font_weight="700",
                            color=color, bg=rsd.get("bg", S.COPPER_GLOW),
                            border=f"1px solid {color}",
                        ),
                        spacing="1", align="center",
                    ),
                    rx.dialog.close(
                        rx.icon_button(rx.icon(tag="x", size=18), variant="ghost", color_scheme="amber", on_click=UIState.close_risk_breakdown),
                    ),
                    width="100%", align="center", spacing="4", margin_bottom="24px",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE, margin_bottom="16px"),
                # Factor rows
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(GlobalState.risk_score_fatores, _risk_factor_row),
                        spacing="3", width="100%",
                    ),
                    max_height="55vh",
                    type="hover",
                    scrollbars="vertical",
                    width="100%",
                ),
                # Footer summary
                rx.box(
                    rx.hstack(
                        rx.icon(tag="info", size=13, color=S.TEXT_MUTED),
                        rx.text(
                            "Nota calculada automaticamente. Fatores com maior peso têm maior impacto no score final.",
                            font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_BODY, line_height="1.5",
                        ),
                        spacing="2", align="start",
                    ),
                    padding="10px 14px", border_radius="8px",
                    bg="rgba(255,255,255,0.02)", border=f"1px solid {S.BORDER_SUBTLE}",
                    margin_top="16px",
                ),
                spacing="0", width="100%",
            ),
            bg="rgba(10, 31, 26, 0.98)",
            backdrop_filter="blur(24px)",
            border=f"1px solid {S.BORDER_ACCENT}",
            max_width="560px",
            width="95vw",
            border_radius=S.R_CARD,
            padding="28px",
            box_shadow="0 32px 72px -12px rgba(0,0,0,0.75)",
        ),
        open=UIState.show_risk_breakdown,
        on_open_change=UIState.close_risk_breakdown,
    )


def _alerta_row(alerta: dict) -> rx.Component:
    """Single alert row in the alertas IA popup."""
    sev_color = rx.cond(
        alerta["severity"] == "critical", "#EF4444",
        rx.cond(alerta["severity"] == "high", "#F59E0B", S.COPPER),
    )
    return rx.hstack(
        rx.center(
            rx.icon(tag=alerta["icon"], size=14, color=sev_color),
            width="32px", height="32px", border_radius="6px",
            bg=rx.cond(
                alerta["severity"] == "critical", "rgba(239,68,68,0.1)",
                rx.cond(alerta["severity"] == "high", "rgba(245,158,11,0.1)", "rgba(201,139,42,0.1)"),
            ),
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(alerta["title"], font_size="12px", font_weight="600", color="var(--text-main)"),
            rx.text(alerta["desc"], font_size="11px", color=S.TEXT_MUTED, line_height="1.4"),
            spacing="0", align="start", flex="1",
        ),
        rx.button(
            rx.icon(tag="arrow-right", size=12),
            variant="ghost", size="1", color_scheme="amber",
            on_click=GlobalState.set_hub_tab(alerta["modulo"]),
        ),
        spacing="3", align="center", width="100%",
        padding="12px 14px", border_radius="8px",
        bg="rgba(255,255,255,0.02)", border=f"1px solid {S.BORDER_SUBTLE}",
    )


def _alertas_ia_dialog() -> rx.Component:
    """Popup modal — alertas IA detalhados."""
    alertas = GlobalState.ia_alertas_list
    count = alertas.length()

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="brain-circuit", size=20, color=S.COPPER),
                        width="40px", height="40px", border_radius="8px",
                        bg=S.COPPER_GLOW, border=f"1px solid {S.BORDER_ACCENT}", flex_shrink="0",
                    ),
                    rx.vstack(
                        rx.dialog.title(
                            "ALERTAS DE INTELIGÊNCIA IA",
                            color=S.COPPER, font_family=S.FONT_TECH, font_size="1.05rem",
                            letter_spacing="0.04em", margin="0",
                        ),
                        rx.text(
                            count.to_string() + " alertas detectados automaticamente",
                            color=S.TEXT_MUTED, font_size="12px", margin="0",
                        ),
                        spacing="0", align="start",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.icon_button(rx.icon(tag="x", size=18), variant="ghost", color_scheme="amber"),
                    ),
                    width="100%", align="center", spacing="4", margin_bottom="20px",
                ),
                rx.cond(
                    alertas.length() == 0,
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="check-circle", size=32, color="#22c55e"),
                            rx.text("Nenhum alerta ativo", font_size="14px", color=S.TEXT_MUTED),
                            rx.text("Todos os indicadores dentro do esperado.", font_size="12px", color="rgba(255,255,255,0.3)"),
                            spacing="2", align="center",
                        ),
                        padding_y="24px",
                    ),
                    rx.vstack(
                        rx.foreach(alertas, _alerta_row),
                        spacing="2", width="100%",
                    ),
                ),
                spacing="0", width="100%",
            ),
            bg="rgba(10,31,26,0.98)", backdrop_filter="blur(24px)",
            border=f"1px solid {S.BORDER_ACCENT}",
            max_width="520px", width="95vw",
            border_radius=S.R_CARD, padding="28px",
            box_shadow="0 32px 72px -12px rgba(0,0,0,0.75)",
        ),
        open=UIState.show_alertas_ia_dialog,
        on_open_change=UIState.set_show_alertas_ia_dialog,
    )


def _vg_risk_kpi_card() -> rx.Component:
    """Nota de risco card — clicável, abre popup de breakdown."""
    rsd = GlobalState.risk_score_data
    nota = rsd.get("nota", "—")
    label = rsd.get("label", "—")
    color = rsd.get("color", S.COPPER)
    bg = rsd.get("bg", S.COPPER_GLOW)

    return rx.box(
        rx.vstack(
            rx.text(
                "NOTA DE RISCO",
                font_size="9px", font_family=S.FONT_MONO,
                color="rgba(218,229,225,0.5)",
                text_transform="uppercase", letter_spacing="0.1em",
            ),
            rx.hstack(
                rx.center(
                    rx.icon(tag="shield-alert", size=14, color=color),
                    width="28px", height="28px",
                    bg="rgba(255,255,255,0.04)", border_radius="4px", flex_shrink="0",
                ),
                rx.text(
                    nota,
                    font_family=S.FONT_TECH, font_size="2rem",
                    font_weight="700", color=color, line_height="1",
                ),
                spacing="3", align="center",
            ),
            rx.hstack(
                rx.box(
                    label,
                    padding="2px 7px", border_radius="3px",
                    font_size="9px", font_family=S.FONT_MONO, font_weight="700",
                    color=color, bg=bg, border=f"1px solid {color}",
                ),
                rx.icon(tag="chevron-right", size=12, color=S.TEXT_MUTED),
                spacing="1", align="center",
            ),
            spacing="1", align="start",
        ),
        on_click=UIState.open_risk_breakdown,
        cursor="pointer",
        **{**_GLASS_COMPACT, "transition": "all 0.15s ease", "border_radius": "8px",
           "_hover": {"border_color": color, "background": "rgba(255,255,255,0.06)"}},
        flex="1",
        min_width="150px",
        flex_direction="column",
        display="flex",
    )


def _vg_alertas_kpi_card() -> rx.Component:
    """Alertas IA card — mostra count, clicável p/ detalhe."""
    alertas = GlobalState.ia_alertas_list
    count = alertas.length()
    critical_count = alertas.length()  # proxy — todos contam

    card_color = rx.cond(
        count >= 3, "#EF4444",
        rx.cond(count >= 1, "#F59E0B", "#22c55e"),
    )
    label = rx.cond(
        count == 0, "Tudo em ordem",
        rx.cond(count == 1, "1 alerta ativo", count.to_string() + " alertas ativos"),
    )

    return rx.box(
        rx.vstack(
            rx.text(
                "ALERTAS IA",
                font_size="9px", font_family=S.FONT_MONO,
                color="rgba(218,229,225,0.5)",
                text_transform="uppercase", letter_spacing="0.1em",
            ),
            rx.hstack(
                rx.center(
                    rx.icon(tag="brain-circuit", size=14, color=card_color),
                    width="28px", height="28px",
                    bg="rgba(255,255,255,0.04)", border_radius="4px", flex_shrink="0",
                ),
                rx.text(
                    count.to_string(),
                    font_family=S.FONT_TECH, font_size="2rem",
                    font_weight="700", color=card_color, line_height="1",
                ),
                spacing="3", align="center",
            ),
            rx.hstack(
                rx.text(label, font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                rx.icon(tag="chevron-right", size=12, color=S.TEXT_MUTED),
                spacing="1", align="center",
            ),
            spacing="1", align="start",
        ),
        on_click=UIState.set_show_alertas_ia_dialog(True),
        cursor="pointer",
        **{**_GLASS_COMPACT, "transition": "all 0.15s ease", "border_radius": "8px",
           "_hover": {"border_color": card_color}},
        flex="1",
        min_width="150px",
        flex_direction="column",
        display="flex",
    )


def _tab_visao_geral() -> rx.Component:
    """
    Visão Geral do projeto — triagem rápida para tomada de decisão.
    Layout:
      - KPI Strip: Progresso | Nota de Risco | Alertas IA | Desvio | Clima
      - Row 2: Agente de Atividades (8) | Feed Inteligência IA (4)
      - Row 3: Mapa Meteorológico (12)
    """
    fmt = GlobalState.obra_kpi_fmt
    data = GlobalState.obra_enterprise_data
    progress_val = data.get("avanco_pct", "0").to(float).to(int).to_string() + "%"

    # Desvio prazo/custo combinado card
    desvio_prazo = GlobalState.risk_score_data.get("desvio_pp", "—")
    desvio_color = rx.cond(
        GlobalState.risk_desvio_is_negative,
        S.DANGER,
        rx.cond(desvio_prazo == "+0.0", S.TEXT_MUTED, S.PATINA),
    )

    return rx.vstack(
        # ── Popups (hidden until triggered) ───────────────────────────────────
        _risk_breakdown_dialog(),
        _alertas_ia_dialog(),

        # ── KPI Strip ─────────────────────────────────────────────────────────
        rx.flex(
            # 1 — Progresso Físico
            _vg_kpi_card(
                "trending-up",
                "PROGRESSO FÍSICO",
                progress_val,
                "",
                value_color=S.PATINA,
                bar_pct=progress_val,
            ),
            # 2 — Nota de Risco (clicável)
            _vg_risk_kpi_card(),
            # 3 — Alertas IA (clicável)
            _vg_alertas_kpi_card(),
            # 4 — Desvio de Prazo
            _vg_kpi_card(
                "calendar-x",
                "DESVIO DE PRAZO",
                desvio_prazo,
                "vs planejado (%)",
                value_color=desvio_color,
            ),
            # 5 — Clima
            _vg_weather_card(),
            gap="12px",
            flex_wrap="wrap",
            width="100%",
            align_items="stretch",
        ),

        # ── Row 2: Agente de Atividades + Feed IA ────────────────────────────
        rx.grid(
            rx.box(
                _agente_panel(),
                grid_column=rx.breakpoints(initial="span 12", lg="span 8"),
                height="100%",
            ),
            rx.box(
                _vg_ai_feed(),
                grid_column=rx.breakpoints(initial="span 12", lg="span 4"),
                height="100%",
            ),
            columns="12",
            gap="24px",
            width="100%",
            align_items="stretch",
            class_name="animate-fade-in",
        ),

        # ── Row 3: Mapa meteorológico (full width) ────────────────────────────
        rx.box(
            windy_map_widget(),
            width="100%",
            min_height="380px",
            border_radius="8px",
            overflow="hidden",
        ),

        width="100%",
        spacing="6",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# AGENTE DE ATIVIDADES — AI insight cards
# ══════════════════════════════════════════════════════════════════════════════

_AGENTE_TYPE_COLORS = {
    "delay":    ("#EF4444", "rgba(239,68,68,0.12)"),
    "ahead":    ("#22c55e", "rgba(34,197,94,0.12)"),
    "crew":     ("#E89845", "rgba(232,152,69,0.12)"),
    "weather":  ("#3B82F6", "rgba(59,130,246,0.12)"),
    "optimize": (S.PATINA, "rgba(42,157,143,0.12)"),
    "alert":    (S.COPPER, S.COPPER_GLOW),
}

_AGENTE_PRIORITY_BORDER = {
    "high":   "#EF4444",
    "medium": S.COPPER,
    "low":    S.BORDER_SUBTLE,
}


def _agente_insight_card(card: dict) -> rx.Component:
    """Single AI insight card for the Agente de Atividades panel."""
    # We can't do dict lookup dynamically in Reflex frontend — use rx.cond chains
    card_type = card["type"]
    color = rx.cond(
        card_type == "delay", "#EF4444",
        rx.cond(card_type == "ahead", "#22c55e",
        rx.cond(card_type == "crew", "#E89845",
        rx.cond(card_type == "weather", "#3B82F6",
        rx.cond(card_type == "optimize", S.PATINA, S.COPPER)))),
    )
    bg_color = rx.cond(
        card_type == "delay", "rgba(239,68,68,0.08)",
        rx.cond(card_type == "ahead", "rgba(34,197,94,0.08)",
        rx.cond(card_type == "crew", "rgba(232,152,69,0.08)",
        rx.cond(card_type == "weather", "rgba(59,130,246,0.08)",
        rx.cond(card_type == "optimize", "rgba(42,157,143,0.08)", "rgba(201,139,42,0.08)")))),
    )
    border_color = rx.cond(
        card["priority"] == "high", "#EF4444",
        rx.cond(card["priority"] == "medium", S.COPPER, S.BORDER_SUBTLE),
    )

    return rx.box(
        rx.vstack(
            # Header: icon + type badge + priority dot
            rx.hstack(
                rx.center(
                    rx.icon(tag=card["icon"], size=16, color=color),
                    width="32px",
                    height="32px",
                    border_radius="6px",
                    bg=bg_color,
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text(
                        card["title"],
                        font_family=S.FONT_TECH,
                        font_size="0.875rem",
                        font_weight="700",
                        color="var(--text-main)",
                        line_height="1.2",
                    ),
                    rx.cond(
                        card["atividade"] != "",
                        rx.text(
                            card["atividade"],
                            font_size="10px",
                            color=color,
                            font_family=S.FONT_MONO,
                            font_weight="600",
                            letter_spacing="0.03em",
                        ),
                        rx.fragment(),
                    ),
                    spacing="0",
                    align="start",
                    flex="1",
                    min_width="0",
                ),
                # Priority badge
                rx.box(
                    rx.cond(card["priority"] == "high", "CRÍTICO",
                    rx.cond(card["priority"] == "medium", "MÉDIO", "BAIXO")),
                    padding="2px 6px",
                    border_radius="3px",
                    font_size="9px",
                    font_family=S.FONT_MONO,
                    font_weight="700",
                    letter_spacing="0.06em",
                    color=border_color,
                    style={"border": "1px solid", "border_color": border_color},
                    bg=rx.cond(
                        card["priority"] == "high", "rgba(239,68,68,0.08)",
                        rx.cond(card["priority"] == "medium", "rgba(201,139,42,0.08)", "rgba(255,255,255,0.04)"),
                    ),
                    white_space="nowrap",
                    flex_shrink="0",
                ),
                spacing="3",
                align="start",
                width="100%",
                margin_bottom="10px",
            ),
            # Body text
            rx.text(
                card["body"],
                font_size="12px",
                color="rgba(255,255,255,0.75)",
                font_family=S.FONT_BODY,
                line_height="1.6",
            ),
            spacing="0",
            width="100%",
        ),
        padding="16px",
        border_radius="10px",
        background=S.BG_GLASS,
        style={
            "backdropFilter": "blur(8px)",
            "border": "1px solid",
            "border_color": border_color,
            "transition": "border-color 0.15s ease",
        },
        _hover={"border_color": color},
    )


def _agente_panel() -> rx.Component:
    """Agente de Atividades — AI insight panel in the Dashboard tab."""
    contrato_var = GlobalState.selected_project

    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.hstack(
                    rx.box(
                        rx.box(
                            width="8px",
                            height="8px",
                            border_radius="50%",
                            bg=S.COPPER,
                            class_name="animate-pulse",
                        ),
                        position="absolute",
                        top="-3px",
                        right="-3px",
                    ),
                    rx.center(
                        rx.icon(tag="brain-circuit", size=18, color=S.COPPER),
                        width="36px",
                        height="36px",
                        border_radius="8px",
                        bg=S.COPPER_GLOW,
                        border=f"1px solid rgba(201,139,42,0.3)",
                        position="relative",
                    ),
                    rx.vstack(
                        rx.text(
                            "AGENTE DE INTELIGÊNCIA ARTIFICIAL",
                            font_family=S.FONT_TECH,
                            font_size="1rem",
                            font_weight="700",
                            text_transform="uppercase",
                            letter_spacing="0.06em",
                            color=S.COPPER,
                        ),
                        rx.text(
                            "Insights inteligentes baseados em cronograma + RDO",
                            font_size="11px",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_BODY,
                        ),
                        spacing="0",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.spacer(),
                rx.hstack(
                    # Last updated timestamp
                    rx.cond(
                        HubState.agente_last_updated != "",
                        rx.text(
                            "Atualizado: " + HubState.agente_last_updated,
                            font_size="10px",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO,
                        ),
                        rx.fragment(),
                    ),
                    # Regenerate button
                    rx.button(
                        rx.cond(
                            HubState.agente_loading,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Analisando…", font_size="12px"),
                                spacing="2",
                                align="center",
                            ),
                            rx.hstack(
                                rx.icon(tag="sparkles", size=13),
                                rx.text("Gerar Insights", font_size="12px"),
                                spacing="2",
                                align="center",
                            ),
                        ),
                        on_click=HubState.force_run_agente(contrato_var),
                        is_loading=HubState.agente_loading,
                        variant="outline",
                        color_scheme="amber",
                        size="1",
                        cursor="pointer",
                        style={
                            "border": f"1px solid rgba(201,139,42,0.4)",
                            "color": S.COPPER,
                            "background": "rgba(201,139,42,0.06)",
                            "_hover": {"background": "rgba(201,139,42,0.12)"},
                        },
                    ),
                    spacing="3",
                    align="center",
                ),
                width="100%",
                align="center",
                flex_wrap="wrap",
                gap="12px",
            ),
            # Error state
            rx.cond(
                HubState.agente_error != "",
                rx.hstack(
                    rx.icon(tag="alert-triangle", size=14, color="#EF4444"),
                    rx.text(HubState.agente_error, font_size="12px", color="#EF4444"),
                    spacing="2",
                    align="center",
                    padding="10px 14px",
                    border_radius="8px",
                    bg="rgba(239,68,68,0.06)",
                    border="1px solid rgba(239,68,68,0.2)",
                    width="100%",
                ),
                rx.fragment(),
            ),
            # Loading skeleton
            rx.cond(
                HubState.agente_loading & (HubState.agente_insights.length() == 0),
                rx.grid(
                    *[
                        rx.box(
                            height="110px",
                            border_radius="10px",
                            bg="rgba(255,255,255,0.04)",
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            class_name="animate-pulse",
                        )
                        for _ in range(4)
                    ],
                    columns=rx.breakpoints(initial="1", md="2"),
                    gap="14px",
                    width="100%",
                ),
                rx.fragment(),
            ),
            # Empty state — no insights yet
            rx.cond(
                ~HubState.agente_loading & (HubState.agente_insights.length() == 0) & (HubState.agente_error == ""),
                rx.center(
                    rx.vstack(
                        rx.icon(tag="brain-circuit", size=36, color=S.BORDER_SUBTLE),
                        rx.text(
                            "Nenhum insight gerado ainda",
                            font_size="14px",
                            font_weight="600",
                            color=S.TEXT_MUTED,
                        ),
                        rx.text(
                            'Clique em "Gerar Insights" para analisar as atividades do cronograma.',
                            font_size="12px",
                            color="rgba(255,255,255,0.3)",
                            text_align="center",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    padding_y="32px",
                    width="100%",
                ),
                rx.fragment(),
            ),
            # Insight cards grid
            rx.cond(
                HubState.agente_insights.length() > 0,
                rx.grid(
                    rx.foreach(HubState.agente_insights, _agente_insight_card),
                    columns=rx.breakpoints(initial="1", md="2"),
                    gap="14px",
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing="4",
            width="100%",
        ),
        **_GLASS_PANEL,
        width="100%",
    )


def _dashboard_chart_card(
    title: str,
    subtitle: str,
    icon_tag: str,
    icon_color: str,
    children,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(tag=icon_tag, size=14, color=icon_color),
                    width="28px",
                    height="28px",
                    bg=f"rgba({','.join(str(int(icon_color.lstrip('#')[i:i+2],16)) for i in (0,2,4))}, 0.12)"
                    if icon_color.startswith("#") else "rgba(255,255,255,0.06)",
                    border_radius="4px",
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text(
                        title,
                        font_family=S.FONT_TECH,
                        font_size="0.875rem",
                        font_weight="700",
                        text_transform="uppercase",
                        color="var(--text-main)",
                        letter_spacing="0.04em",
                    ),
                    rx.text(
                        subtitle,
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_MONO,
                    ),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
                margin_bottom="20px",
            ),
            children,
            width="100%",
        ),
        **_GLASS_PANEL,
        height="100%",
        min_height="300px",
    )


def _dash_empty(icon: str, msg: str, height: str = "180px") -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.icon(tag=icon, size=28, color=S.BORDER_SUBTLE),
            rx.text(msg, font_size="11px", color=S.TEXT_MUTED),
            spacing="2", align="center",
        ),
        height=height,
    )


def _dash_filter_pill(label: str, value: str, current_var, on_click) -> rx.Component:
    is_active = current_var == value
    return rx.box(
        label,
        on_click=on_click,
        padding="4px 12px",
        border_radius="999px",
        font_size="11px",
        font_family=S.FONT_MONO,
        font_weight=rx.cond(is_active, "700", "400"),
        color=rx.cond(is_active, S.COPPER, S.TEXT_MUTED),
        bg=rx.cond(is_active, S.COPPER_GLOW, "rgba(255,255,255,0.03)"),
        border=rx.cond(is_active, f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
        cursor="pointer",
        transition="all 0.12s ease",
        white_space="nowrap",
    )


_TOOLTIP_STYLE = {
    "background": "rgba(8,18,16,0.97)",
    "border": f"1px solid rgba(201,139,42,0.3)",
    "borderRadius": "6px",
    "fontSize": "11px",
}
_TICK_STYLE = {"fontSize": 9, "fill": "#889999", "fontFamily": "JetBrains Mono"}


def _tab_dashboard() -> rx.Component:
    """
    Dashboard analítico — evolução temporal, SPI, produtividade, disciplinas.
    Filtros: período | disciplina
    Gráficos: Curva S | SPI trend | Produtividade diária | Disciplinas planned vs actual
    """
    return rx.vstack(
        # ── Header + filtros ──────────────────────────────────────────────────
        rx.hstack(
            rx.vstack(
                rx.text(
                    "DASHBOARD ANALÍTICO",
                    font_family=S.FONT_TECH, font_size="1.15rem", font_weight="700",
                    text_transform="uppercase", color="var(--text-main)", letter_spacing="0.04em",
                ),
                rx.text(
                    "Evolução temporal, performance de prazo e produtividade do projeto.",
                    font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_BODY,
                ),
                spacing="0", align="start",
            ),
            rx.spacer(),
            # Period filter pills
            rx.hstack(
                _dash_filter_pill("7D",  "7d",  GlobalState.dash_filter_period, GlobalState.set_dash_filter_period("7d")),
                _dash_filter_pill("30D", "30d", GlobalState.dash_filter_period, GlobalState.set_dash_filter_period("30d")),
                _dash_filter_pill("90D", "90d", GlobalState.dash_filter_period, GlobalState.set_dash_filter_period("90d")),
                _dash_filter_pill("Tudo","all", GlobalState.dash_filter_period, GlobalState.set_dash_filter_period("all")),
                spacing="2", align="center", flex_wrap="wrap",
            ),
            align="end",
            width="100%",
            flex_wrap="wrap",
            gap="12px",
            margin_bottom="4px",
        ),

        # ── Row 1: Curva S (span 2) + SPI Trend (span 1) ─────────────────────
        rx.grid(
            # Curva S integrada
            rx.box(
                _dashboard_chart_card(
                    "Curva S — Planejado vs Realizado",
                    "Avanço físico acumulado no tempo",
                    "trending-up",
                    S.PATINA,
                    rx.cond(
                        GlobalState.dash_scurve_chart,
                        rx.recharts.area_chart(
                            rx.recharts.area(
                                data_key="previsto", stroke=S.TEXT_MUTED,
                                fill="rgba(136,153,153,0.05)", stroke_dasharray="5 3",
                                dot=False, stroke_width=1.5, name="Planejado",
                            ),
                            rx.recharts.area(
                                data_key="realizado", stroke=S.PATINA,
                                fill="rgba(42,157,143,0.12)",
                                dot=False, stroke_width=2, name="Realizado",
                            ),
                            rx.recharts.x_axis(data_key="data", tick=_TICK_STYLE),
                            rx.recharts.y_axis(unit="%", tick=_TICK_STYLE, width=32),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.04)"),
                            TOOLTIP_SIGNAL,
                            rx.recharts.legend(
                                icon_type="line",
                                wrapper_style={"fontSize": "10px", "color": S.TEXT_MUTED, "paddingTop": "8px"},
                            ),
                            rx.recharts.reference_line(
                                x=GlobalState.dash_today_str,
                                stroke=S.COPPER, stroke_dasharray="4 2", stroke_width=1.5,
                                label="Hoje",
                            ),
                            data=GlobalState.dash_scurve_chart,
                            height=200, width="100%",
                        ),
                        _dash_empty("line-chart", "Sem dados de progresso"),
                    ),
                ),
                grid_column=rx.breakpoints(initial="span 3", md="span 2"),
            ),
            # SPI Trend
            rx.box(
                _dashboard_chart_card(
                    "Índice de Desempenho de Prazo (SPI)",
                    "Eficiência de prazo — 1,0 = no prazo, >1,0 = adiantado",
                    "gauge",
                    "#3B82F6",
                    rx.cond(
                        GlobalState.dash_spi_trend_chart,
                        rx.recharts.line_chart(
                            rx.recharts.line(
                                data_key="spi", stroke="#3B82F6", dot=False, stroke_width=2,
                                name="SPI",
                            ),
                            rx.recharts.line(
                                data_key="baseline", stroke=S.BORDER_SUBTLE,
                                stroke_dasharray="4 3", dot=False, stroke_width=1,
                                name="Linha base",
                            ),
                            rx.recharts.x_axis(data_key="data", tick=_TICK_STYLE),
                            rx.recharts.y_axis(
                                tick=_TICK_STYLE, width=36,
                                domain=[0.5, 1.5],
                            ),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.04)"),
                            TOOLTIP_SPI_RING,
                            rx.recharts.reference_line(y=1, stroke=S.COPPER, stroke_dasharray="4 2", stroke_width=1),
                            data=GlobalState.dash_spi_trend_chart,
                            height=200, width="100%",
                        ),
                        _dash_empty("gauge", "Sem dados de SPI"),
                    ),
                ),
                grid_column=rx.breakpoints(initial="span 3", md="span 1"),
            ),
            columns="3",
            gap="20px",
            width="100%",
        ),

        # ── Row 2: Produtividade diária (span 2) + Disciplinas (span 1) ───────
        rx.grid(
            # Produtividade diária
            rx.box(
                _dashboard_chart_card(
                    "Produtividade Diária",
                    "Avanço realizado vs meta por dia",
                    "activity",
                    "#E89845",
                    rx.cond(
                        GlobalState.dash_producao_diaria_chart,
                        rx.recharts.bar_chart(
                            rx.recharts.bar(
                                data_key="meta", fill=S.TEXT_MUTED, fill_opacity=0.3,
                                radius=2, name="Meta do dia",
                            ),
                            rx.recharts.bar(
                                data_key="realizado", fill="#E89845", fill_opacity=0.85,
                                radius=2, name="Realizado no dia",
                                label={"position": "top", "fontSize": 9, "fill": "#E89845", "formatter": "v => v > 0 ? v.toFixed(1)+'%' : ''"},
                            ),
                            rx.recharts.x_axis(data_key="data", tick=_TICK_STYLE),
                            rx.recharts.y_axis(unit="%", tick=_TICK_STYLE, width=36),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.04)"),
                            TOOLTIP_PILL,
                            rx.recharts.legend(
                                wrapper_style={"fontSize": "10px", "color": S.TEXT_MUTED, "paddingTop": "8px"},
                            ),
                            data=GlobalState.dash_producao_diaria_chart,
                            height=200, width="100%", bar_size=14,
                        ),
                        _dash_empty("activity", "Sem dados de produtividade"),
                    ),
                ),
                grid_column=rx.breakpoints(initial="span 3", md="span 2"),
            ),
            # Disciplinas planned vs actual
            rx.box(
                _dashboard_chart_card(
                    "Disciplinas",
                    "Progresso planejado vs realizado",
                    "layers",
                    S.COPPER,
                    rx.cond(
                        GlobalState.dash_disciplinas_chart,
                        rx.recharts.bar_chart(
                            rx.recharts.bar(
                                data_key="previsto_pct", fill=S.TEXT_MUTED, fill_opacity=0.3,
                                radius=2, name="Planejado",
                            ),
                            rx.recharts.bar(
                                data_key="realizado_pct", fill=S.PATINA, fill_opacity=0.85,
                                radius=2, name="Realizado",
                            ),
                            rx.recharts.x_axis(
                                data_key="label",
                                tick={**_TICK_STYLE, "fontSize": 8},
                                angle=-30, text_anchor="end", height=50,
                            ),
                            rx.recharts.y_axis(unit="%", tick=_TICK_STYLE, width=32),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.04)"),
                            TOOLTIP_STACK_DISC,
                            rx.recharts.legend(
                                wrapper_style={"fontSize": "10px", "color": S.TEXT_MUTED, "paddingTop": "8px", "display": "flex", "flexWrap": "wrap", "justifyContent": "center"},
                            ),
                            data=GlobalState.dash_disciplinas_chart,
                            height=200, width="100%", bar_size=12,
                        ),
                        _dash_empty("layers", "Sem dados de disciplinas"),
                    ),
                ),
                grid_column=rx.breakpoints(initial="span 3", md="span 1"),
            ),
            columns="3",
            gap="20px",
            width="100%",
        ),

        # ── Row 3: Orçamento (full width half) + KPI cards ────────────────────
        rx.grid(
            # Orçamento planejado vs realizado
            rx.box(
                _dashboard_chart_card(
                    "Orçamento Executado",
                    "Planejado vs realizado em R$",
                    "dollar-sign",
                    S.COPPER,
                    rx.cond(
                        GlobalState.obra_budget_chart,
                        rx.recharts.bar_chart(
                            rx.recharts.bar(
                                data_key="planejado", fill="#3B82F6", fill_opacity=0.8,
                                radius=4, name="Orçamento Previsto",
                            ),
                            rx.recharts.bar(
                                data_key="realizado", fill=S.PATINA, fill_opacity=0.85,
                                radius=4, name="Valor Executado",
                            ),
                            rx.recharts.x_axis(data_key="categoria", tick=_TICK_STYLE),
                            rx.recharts.y_axis(tick=_TICK_STYLE, width=64,
                                tick_formatter="(v) => v >= 1000000 ? 'R$' + (v/1000000).toFixed(1) + 'M' : v >= 1000 ? 'R$' + (v/1000).toFixed(0) + 'k' : 'R$' + v"),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.04)"),
                            TOOLTIP_SPLIT,
                            rx.recharts.legend(
                                wrapper_style={"fontSize": "10px", "color": S.TEXT_MUTED, "paddingTop": "8px"},
                            ),
                            data=GlobalState.obra_budget_chart,
                            height=200, width="100%", bar_size=40,
                        ),
                        _dash_empty("dollar-sign", "Orçamento não configurado"),
                    ),
                ),
                grid_column=rx.breakpoints(initial="span 2", md="span 1"),
            ),
            # KPI summary box
            rx.box(
                rx.vstack(
                    rx.text("KPIs DO PROJETO", font_family=S.FONT_TECH, font_size="0.85rem", font_weight="700",
                            text_transform="uppercase", letter_spacing="0.06em", color=S.COPPER),
                    rx.divider(border_color=S.BORDER_SUBTLE, margin_y="10px"),
                    *[
                        rx.hstack(
                            rx.text(label, font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, flex="1"),
                            rx.text(val, font_size="13px", font_weight="700", color=color, font_family=S.FONT_TECH),
                            width="100%", justify="between",
                            padding_y="6px",
                            border_bottom=f"1px solid {S.BORDER_SUBTLE}",
                        )
                        for label, val, color in [
                            ("Progresso Físico",   GlobalState.obra_kpi_fmt.get("avanco_fmt", "—"),               S.PATINA),
                            ("Orçamento Exec.",     GlobalState.obra_kpi_fmt.get("budget_exec_rate_fmt", "—"),     rx.cond(GlobalState.obra_kpi_fmt.get("budget_over", False), S.DANGER, S.PATINA)),
                            ("Equipe/Planejado",    GlobalState.obra_kpi_fmt.get("equipe_val", "—"),               "#E89845"),
                            ("Nota de Risco",       GlobalState.risk_score_data.get("nota", "—"),                  GlobalState.risk_score_data.get("color", S.COPPER)),
                            ("Alertas Ativos",      GlobalState.ia_alertas_list.length().to_string(),              rx.cond(GlobalState.ia_alertas_list.length() > 2, S.DANGER, rx.cond(GlobalState.ia_alertas_list.length() > 0, "#F59E0B", S.PATINA))),
                        ]
                    ],
                    spacing="0", width="100%",
                ),
                **_GLASS_PANEL,
                height="100%",
                grid_column=rx.breakpoints(initial="span 2", md="span 1"),
            ),
            columns="2",
            gap="20px",
            width="100%",
        ),

        width="100%",
        spacing="6",
        class_name="animate-fade-in",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CRONOGRAMA
# ══════════════════════════════════════════════════════════════════════════════


def _activity_row(item: dict) -> rx.Component:
    """Single row in the activity management table."""
    type_colors = {
        "Elétrica": ("#3B82F6", "rgba(59,130,246,0.12)"),
        "Civil": (S.COPPER, S.COPPER_GLOW),
        "Hidráulica": (S.PATINA, S.PATINA_GLOW),
        "Estrutural": ("#E89845", "rgba(232,152,69,0.12)"),
        "Outros": (S.TEXT_MUTED, "rgba(136,153,153,0.1)"),
    }
    # We use a fixed-color pill approach (can't do dict lookup dynamically in Reflex frontend)
    fase = item["fase"]
    pct = item["conclusao_pct"].to(float).to(int)

    indent_left = rx.cond(
        item["nivel"] == "sub", "32px",
        rx.cond(item["nivel"] == "micro", "16px", "0px"),
    )
    nivel_badge_text = rx.cond(
        item["nivel"] == "sub", "SUB",
        rx.cond(item["nivel"] == "micro", "MICRO", "MACRO"),
    )
    nivel_badge_color = rx.cond(
        item["nivel"] == "sub", "#8B5CF6",
        rx.cond(item["nivel"] == "micro", S.PATINA, S.COPPER),
    )

    return rx.hstack(
        # Indent spacer for hierarchy
        rx.box(width=indent_left, flex_shrink="0"),
        # Nivel badge (MACRO / MICRO / SUB)
        rx.box(
            nivel_badge_text,
            padding="1px 5px",
            border_radius="3px",
            bg="rgba(255,255,255,0.04)",
            border=rx.cond(
                item["nivel"] == "sub", "1px solid rgba(139,92,246,0.4)",
                rx.cond(item["nivel"] == "micro", f"1px solid rgba(42,157,143,0.4)", "1px solid rgba(201,139,42,0.4)"),
            ),
            font_size="8px",
            font_family=S.FONT_MONO,
            font_weight="700",
            color=nivel_badge_color,
            white_space="nowrap",
            flex_shrink="0",
        ),
        # Phase badge
        rx.box(
            fase,
            padding="2px 8px",
            border_radius="3px",
            bg="rgba(255,255,255,0.06)",
            border=f"1px solid {S.BORDER_SUBTLE}",
            font_size="9px",
            font_family=S.FONT_MONO,
            font_weight="700",
            color="var(--text-main)",
            text_transform="uppercase",
            white_space="nowrap",
            min_width="70px",
            text_align="center",
        ),
        # Activity name
        rx.text(
            item["atividade"],
            font_size="13px",
            font_weight="600",
            color="var(--text-main)",
            flex="1",
            min_width="0",
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
        ),
        # Phase
        rx.text(
            item.get("responsavel", item.get("fase", "—")),
            font_size="11px",
            color=S.TEXT_MUTED,
            font_family=S.FONT_MONO,
            display=rx.breakpoints(initial="none", md="block"),
            min_width="80px",
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
        ),
        # Mini progress bar + %
        rx.hstack(
            rx.box(
                rx.box(
                    height="100%",
                    bg=rx.cond(
                        item["critico"] == "Sim",
                        S.DANGER,
                        S.COPPER,
                    ),
                    width=pct.to_string() + "%",
                    border_radius="2px",
                    transition="width 1s ease-out",
                ),
                height="4px",
                bg="rgba(255,255,255,0.05)",
                border_radius="2px",
                overflow="hidden",
                width="60px",
                flex_shrink="0",
            ),
            rx.text(
                pct.to_string() + "%",
                font_size="10px",
                font_weight="700",
                color=rx.cond(item["critico"] == "Sim", S.DANGER, S.COPPER),
                font_family=S.FONT_MONO,
                min_width="32px",
                text_align="right",
            ),
            align="center",
            spacing="2",
        ),
        # Critical badge
        rx.cond(
            item["critico"] == "Sim",
            rx.hstack(
                rx.icon(tag="circle-alert", size=11, color=S.DANGER),
                rx.text(
                    "CRÍTICO",
                    font_size="9px",
                    color=S.DANGER,
                    font_family=S.FONT_MONO,
                    font_weight="700",
                    display=rx.breakpoints(initial="none", md="block"),
                ),
                spacing="1",
                align="center",
            ),
        ),
        padding="10px 14px",
        border_radius=S.R_CONTROL,
        border=f"1px solid {S.BORDER_SUBTLE}",
        bg="rgba(255,255,255,0.02)",
        _hover={"bg": "rgba(255,255,255,0.04)", "border_color": S.BORDER_ACCENT},
        transition="all 0.15s ease",
        width="100%",
        align="center",
        spacing="3",
        flex_wrap="wrap",
    )


def _gantt_real_row(item: dict) -> rx.Component:
    """
    Real Gantt row driven by GlobalState.gantt_rows data.
    Displays a horizontal progress bar sized by start/end dates relative to
    the project span. Falls back to a simple bar if dates are missing.
    Each row: label | date range | progress bar | % | responsavel
    """
    pct_val = item["pct"].to(int)
    is_critical = item["critico"] == "1"

    bar_color = rx.cond(is_critical, S.DANGER, item["color"])

    return rx.hstack(
        # Activity label
        rx.text(
            item["label"],
            font_size="11px",
            font_family=S.FONT_MONO,
            color="var(--text-main)",
            white_space="nowrap",
            overflow="hidden",
            text_overflow="ellipsis",
            width="180px",
            flex_shrink="0",
        ),
        # Phase badge
        rx.box(
            item["fase"],
            padding="1px 6px",
            border_radius="2px",
            bg="rgba(255,255,255,0.05)",
            border=f"1px solid {S.BORDER_SUBTLE}",
            font_size="9px",
            font_family=S.FONT_MONO,
            color=S.TEXT_MUTED,
            text_transform="uppercase",
            white_space="nowrap",
            width="80px",
            text_align="center",
            flex_shrink="0",
            overflow="hidden",
            text_overflow="ellipsis",
        ),
        # Date range
        rx.text(
            rx.cond(
                item["start_iso"] != "",
                item["start_iso"] + " → " + item["end_iso"],
                "—",
            ),
            font_size="10px",
            font_family=S.FONT_MONO,
            color=S.TEXT_MUTED,
            white_space="nowrap",
            width="140px",
            flex_shrink="0",
        ),
        # Progress bar + %
        rx.box(
            rx.box(
                height="100%",
                bg=bar_color,
                width=pct_val.to_string() + "%",
                border_radius="2px",
                transition="width 1s ease-out",
                position="relative",
            ),
            height="8px",
            bg="rgba(255,255,255,0.06)",
            border_radius="3px",
            overflow="hidden",
            flex="1",
            min_width="80px",
        ),
        rx.text(
            pct_val.to_string() + "%",
            font_size="10px",
            font_weight="700",
            font_family=S.FONT_MONO,
            color=rx.cond(is_critical, S.DANGER, S.COPPER),
            width="36px",
            text_align="right",
            flex_shrink="0",
        ),
        # Responsável
        rx.text(
            item["responsavel"],
            font_size="10px",
            font_family=S.FONT_MONO,
            color=S.TEXT_MUTED,
            white_space="nowrap",
            overflow="hidden",
            text_overflow="ellipsis",
            width="100px",
            flex_shrink="0",
            display=rx.breakpoints(initial="none", lg="block"),
        ),
        # Critical badge
        rx.cond(
            is_critical,
            rx.hstack(
                rx.icon(tag="circle-alert", size=11, color=S.DANGER),
                rx.text("CRÍTICO", font_size="9px", color=S.DANGER, font_family=S.FONT_MONO, font_weight="700"),
                spacing="1",
                align="center",
            ),
        ),
        padding="8px 12px",
        border_radius=S.R_CONTROL,
        border=f"1px solid {S.BORDER_SUBTLE}",
        bg="rgba(255,255,255,0.02)",
        _hover={"bg": "rgba(255,255,255,0.04)", "border_color": S.BORDER_ACCENT},
        transition="all 0.15s ease",
        width="100%",
        align="center",
        spacing="3",
        overflow="hidden",
    )


def _fase_filter_pill(fase: str) -> rx.Component:
    """Dynamic filter pill for a single fase_macro value."""
    is_active = GlobalState.projetos_fase_filter == fase
    return rx.box(
        rx.text(
            fase,
            font_size="11px",
            font_weight="700",
            color=rx.cond(is_active, S.BG_VOID, S.TEXT_MUTED),
        ),
        padding="4px 12px",
        border_radius="4px",
        cursor="pointer",
        bg=rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.04)"),
        border=rx.cond(
            is_active,
            f"1px solid {S.COPPER}",
            f"1px solid {S.BORDER_SUBTLE}",
        ),
        on_click=GlobalState.set_projetos_fase_filter(fase),
        _hover={"bg": rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.07)")},
        transition="all 0.18s ease",
        white_space="nowrap",
    )


def _cron_stat_badge(label: str, value, color: str) -> rx.Component:
    return rx.vstack(
        rx.text(value, font_family=S.FONT_TECH, font_size="1.4rem", font_weight="700", color=color),
        rx.text(label, font_size="9px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.08em"),
        spacing="0", align="center",
    )


def _cron_fase_pill(fase: str) -> rx.Component:
    is_active = HubState.cron_fase_filter == fase
    return rx.box(
        rx.text(fase, font_size="10px", font_weight="700", color=rx.cond(is_active, S.BG_VOID, S.TEXT_MUTED), white_space="nowrap"),
        padding="3px 10px", border_radius="4px", cursor="pointer",
        bg=rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.04)"),
        border=rx.cond(is_active, f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
        on_click=HubState.set_cron_fase_filter(fase),
        _hover={"bg": rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.07)")},
        transition="all 0.15s ease",
    )


def _cron_display_row(item: dict) -> rx.Component:
    """Unified row renderer for macro / micro / sub activities (uses _display_mode field)."""
    is_critical = item["critico"] == "1"
    is_macro = item["_display_mode"] == "macro"
    is_micro = item["_display_mode"] == "micro"
    is_sub   = item["_display_mode"] == "sub"
    has_micros = item["_has_micros"] == "1"
    is_expanded = item["_is_expanded"] == "1"
    pct = item["_computed_pct"]
    is_pending = item["pendente_aprovacao"] == "1"

    # Indent: macro=0, micro=20px, sub=40px
    indent = rx.cond(
        is_sub,  rx.box(width="40px", flex_shrink="0"),
        rx.cond(is_micro, rx.box(width="20px", flex_shrink="0"), rx.fragment()),
    )

    # Color stripe — thicker for macro, thin for micro/sub
    stripe_w = rx.cond(is_macro, "3px", "2px")
    stripe_color = rx.cond(is_sub, "#8B5CF6", item["color"])
    stripe = rx.box(width=stripe_w, height="100%", bg=stripe_color, border_radius="2px", flex_shrink="0", align_self="stretch", min_height="32px")

    # Expand toggle (only for macros with micros)
    expand_btn = rx.cond(
        is_macro & has_micros,
        rx.icon_button(
            rx.icon(tag=rx.cond(is_expanded, "chevron-down", "chevron-right"), size=11),
            size="1", variant="ghost", cursor="pointer",
            on_click=HubState.toggle_macro_expanded(item["id"]),
            color=S.TEXT_MUTED,
            _hover={"color": S.COPPER},
            flex_shrink="0",
        ),
        rx.box(width="20px", flex_shrink="0"),  # spacer to keep alignment
    )

    # Peso badge for micros and subs
    peso_badge = rx.cond(
        is_micro | is_sub,
        rx.box(
            rx.text(item["peso_pct"] + "%", font_size="8px", font_weight="700", color=rx.cond(is_sub, "#8B5CF6", item["color"]), font_family=S.FONT_MONO),
            padding="1px 5px", border_radius="3px", bg="rgba(255,255,255,0.05)",
            border=rx.cond(is_sub, "1px solid rgba(139,92,246,0.3)", "1px solid rgba(255,255,255,0.1)"), flex_shrink="0",
        ),
        rx.fragment(),
    )

    # Pending badge
    pending_badge = rx.cond(
        is_pending,
        rx.box(
            rx.text("PENDENTE", font_size="7px", font_weight="800", color="#E89845", font_family=S.FONT_TECH, letter_spacing="0.06em"),
            padding="1px 5px", border_radius="3px",
            border="1px solid rgba(232,152,69,0.5)", bg="rgba(232,152,69,0.08)", flex_shrink="0",
        ),
        rx.fragment(),
    )

    # Status badge (micros and subs, only when not 'nao_iniciada')
    _status_label = rx.cond(
        item["status_atividade"] == "em_execucao", "EM EXEC.",
        rx.cond(item["status_atividade"] == "concluida", "CONCLUÍDA",
        rx.cond(item["status_atividade"] == "paralisada", "PARALIS.",
        rx.cond(item["status_atividade"] == "bloqueada", "BLOQ.",
        rx.cond(item["status_atividade"] == "cancelada", "CANCEL.", ""))))
    )
    _status_color = rx.cond(
        item["status_atividade"] == "em_execucao", "#3B82F6",
        rx.cond(item["status_atividade"] == "concluida", S.PATINA,
        rx.cond(item["status_atividade"] == "paralisada", "#F97316",
        rx.cond(item["status_atividade"] == "bloqueada", S.DANGER,
        rx.cond(item["status_atividade"] == "cancelada", S.TEXT_MUTED, S.TEXT_MUTED))))
    )
    status_badge = rx.cond(
        (is_micro | is_sub) & (item["status_atividade"] != "nao_iniciada") & (item["status_atividade"] != "pronta_iniciar"),
        rx.box(
            rx.text(_status_label, font_size="7px", font_weight="800", color=_status_color,
                    font_family=S.FONT_TECH, letter_spacing="0.06em"),
            padding="1px 5px", border_radius="3px",
            border=rx.cond(item["status_atividade"] == "em_execucao", "1px solid rgba(59,130,246,0.4)", f"1px solid rgba(255,255,255,0.1)"),
            bg=rx.cond(item["status_atividade"] == "em_execucao", "rgba(59,130,246,0.08)", "rgba(255,255,255,0.04)"),
            flex_shrink="0",
        ),
        rx.fragment(),
    )

    # Child-count badge: macros show "N sub", micros show "N sub" if they have subs
    micro_count_badge = rx.cond(
        has_micros,
        rx.box(
            rx.text(item["_micro_count"] + " sub", font_size="8px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
            padding="1px 5px", border_radius="3px", bg="rgba(255,255,255,0.04)",
            border=f"1px solid {S.BORDER_SUBTLE}", flex_shrink="0",
        ),
        rx.fragment(),
    )

    # Add micro button (only for macros)
    add_micro_btn = rx.cond(
        is_macro,
        rx.icon_button(
            rx.icon(tag="plus", size=10),
            size="1", variant="ghost", cursor="pointer",
            on_click=lambda: HubState.open_cron_new(item["id"]),
            title="Adicionar micro-atividade",
            color=S.TEXT_MUTED,
            _hover={"color": S.COPPER, "bg": "rgba(201,139,42,0.1)"},
            flex_shrink="0",
        ),
        rx.fragment(),
    )

    # Add sub button (only for micros)
    add_sub_btn = rx.cond(
        is_micro,
        rx.icon_button(
            rx.icon(tag="plus", size=10),
            size="1", variant="ghost", cursor="pointer",
            on_click=lambda: HubState.open_cron_new(item["id"]),
            title="Adicionar sub-atividade",
            color="#8B5CF6",
            _hover={"color": "#A78BFA", "bg": "rgba(139,92,246,0.12)"},
            flex_shrink="0",
        ),
        rx.fragment(),
    )

    font_sz = rx.cond(is_macro, "15px", rx.cond(is_micro, "14px", "13px"))
    font_w  = rx.cond(is_macro, "600",  rx.cond(is_micro, "500",  "400"))
    row_padding = rx.cond(is_macro, "10px 14px", rx.cond(is_micro, "7px 14px 7px 4px", "5px 14px 5px 4px"))
    row_border  = rx.cond(is_sub, "1px solid rgba(139,92,246,0.08)",
                  rx.cond(is_micro, "1px solid rgba(255,255,255,0.04)", f"1px solid {S.BORDER_SUBTLE}"))
    row_bg = rx.cond(
        is_critical, "rgba(239,68,68,0.04)",
        rx.cond(is_sub, "rgba(139,92,246,0.04)",
        rx.cond(is_micro, "rgba(255,255,255,0.015)", "rgba(255,255,255,0.02)")),
    )
    row_margin = rx.cond(is_sub, "24px", rx.cond(is_micro, "12px", "0px"))

    return rx.hstack(
        indent,
        expand_btn,
        stripe,
        # Name + fase
        rx.vstack(
            rx.hstack(
                rx.cond(is_critical, rx.icon(tag="circle-alert", size=11, color=S.DANGER)),
                rx.text(item["atividade"], font_size=font_sz, font_weight=font_w, color="var(--text-main)", font_family=S.FONT_TECH, letter_spacing="0.01em"),
                peso_badge,
                status_badge,
                pending_badge,
                micro_count_badge,
                # Dependency badge — small orange label when this activity has a predecessor
                rx.cond(
                    item["_dep_fase"] != "",
                    rx.hstack(
                        rx.icon(tag="arrow-right", size=9, color="#F97316"),
                        rx.text(item["_dep_fase"], font_size="8px", color="#F97316", font_family=S.FONT_MONO, font_weight="700"),
                        spacing="0", align="center",
                        padding="1px 5px", border_radius="3px",
                        bg="rgba(249,115,22,0.08)", border="1px solid rgba(249,115,22,0.25)",
                        flex_shrink="0",
                    ),
                    rx.fragment(),
                ),
                spacing="1", align="center",
            ),
            rx.hstack(
                rx.text(item["fase_macro"], font_size="11px", color=rx.cond(is_sub, "#8B5CF6", item["color"]), font_family=S.FONT_MONO, font_weight="700"),
                rx.text("·", font_size="11px", color=S.TEXT_MUTED),
                rx.text(item["fase"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                spacing="1", align="center",
            ),
            spacing="0", flex="1", min_width="0",
        ),
        # Responsável
        rx.text(item["responsavel"], font_size="11px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, white_space="nowrap", overflow="hidden", text_overflow="ellipsis", width="100px", flex_shrink="0", display=rx.breakpoints(initial="none", lg="block")),
        # Datas
        rx.vstack(
            rx.text(item["inicio_previsto"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, white_space="nowrap"),
            rx.text(item["termino_previsto"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, white_space="nowrap"),
            spacing="0", flex_shrink="0", display=rx.breakpoints(initial="none", md="block"),
        ),
        # Progress bar + pct
        rx.vstack(
            rx.box(
                rx.box(width=pct + "%", height="100%", bg=rx.cond(is_critical, S.DANGER, rx.cond(is_sub, "#8B5CF6", S.COPPER)), border_radius="2px", transition="width 0.4s ease"),
                width="80px", height="5px", bg="rgba(255,255,255,0.08)", border_radius="2px", overflow="hidden",
            ),
            rx.text(pct + "%", font_size="12px", color=rx.cond(is_critical, S.DANGER, rx.cond(is_sub, "#8B5CF6", S.COPPER)), font_family=S.FONT_MONO, font_weight="700", text_align="center"),
            spacing="1", align="center", flex_shrink="0",
        ),
        # Actions
        rx.hstack(
            add_micro_btn,
            add_sub_btn,
            rx.icon_button(rx.icon(tag="pencil", size=12), size="1", variant="ghost", on_click=HubState.open_cron_edit(item["id"]), cursor="pointer", _hover={"bg": "rgba(201,139,42,0.15)"}),
            rx.icon_button(rx.icon(tag="trash-2", size=12, color=S.DANGER), size="1", variant="ghost", on_click=HubState.request_cron_delete(item["id"]), cursor="pointer", _hover={"bg": "rgba(239,68,68,0.12)"}),
            spacing="1", flex_shrink="0",
        ),
        padding=row_padding,
        border_radius=S.R_CONTROL,
        border=row_border,
        bg=row_bg,
        _hover={"bg": rx.cond(is_critical, "rgba(239,68,68,0.07)", rx.cond(is_sub, "rgba(139,92,246,0.08)", "rgba(255,255,255,0.04)")), "border_color": S.BORDER_ACCENT},
        transition="all 0.15s ease",
        width="100%", align="center", spacing="2", overflow="hidden",
        margin_left=row_margin,
    )


def _kpi_badge(label: str, value, color: str, icon_tag: str = "bar-chart-2", sub: str = "") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon(tag=icon_tag, size=13, color=color),
            rx.text(label, font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.04em"),
            spacing="1", align="center",
        ),
        rx.text(value, font_size="22px", color=color, font_family=S.FONT_TECH, font_weight="700", line_height="1"),
        rx.text(sub, font_size="10px", color=S.TEXT_MUTED) if sub else rx.fragment(),
        spacing="1", align="start",
        padding="12px 16px",
        border_radius=S.R_CONTROL,
        bg="rgba(255,255,255,0.02)",
        border=f"1px solid rgba(255,255,255,0.06)",
        min_width="110px",
        flex="1",
    )


def _kpi_popup_row(row: dict) -> rx.Component:
    """Enterprise activity card no popup de detalhe do KPI."""
    pct_int = row["conclusao_pct"].to(int)
    is_late = row["saldo"].contains("atraso")
    is_risk = row["desvio"].startswith("+")
    pct_color = rx.cond(
        row["conclusao_pct"] == "100", S.PATINA,
        rx.cond(
            is_late | is_risk,
            S.DANGER,
            rx.cond(pct_int >= 70, S.COPPER, "rgba(255,255,255,0.85)"),
        ),
    )
    bar_color = rx.cond(
        row["conclusao_pct"] == "100", S.PATINA,
        rx.cond(
            is_late | is_risk,
            S.DANGER,
            rx.cond(pct_int >= 70, S.COPPER, "#5282DC"),
        ),
    )
    border_left_color = rx.cond(
        row["conclusao_pct"] == "100",
        S.PATINA,
        rx.cond(is_late | is_risk, S.DANGER, S.COPPER),
    )
    has_desvio = row["desvio"] != ""
    has_saldo  = row["saldo"] != ""
    has_dep    = row["dependencia"] != ""

    return rx.box(
        rx.vstack(
            # ── Row 1: fase + % ───────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.box(width="6px", height="6px", border_radius="50%", bg=S.COPPER, flex_shrink="0"),
                    rx.text(row["fase_macro"], font_size="10px", color=S.COPPER,
                            font_weight="700", letter_spacing="0.04em", text_transform="uppercase"),
                    spacing="1", align="center",
                ),
                rx.spacer(),
                rx.text(
                    row["conclusao_pct"] + "%",
                    font_size="18px", font_weight="700",
                    color=pct_color, font_family=S.FONT_TECH, line_height="1",
                ),
                width="100%", align="center",
            ),
            # ── Row 2: activity name ──────────────────────────────
            rx.text(
                row["atividade"],
                font_size="13px", color="rgba(255,255,255,0.92)", font_weight="600",
                white_space="normal", word_break="break-word", line_height="1.35",
            ),
            # ── Row 3: progress bar ───────────────────────────────
            rx.box(
                rx.box(
                    width=row["conclusao_pct"] + "%",
                    height="100%",
                    bg=bar_color,
                    border_radius="2px",
                    transition="width 0.3s ease",
                ),
                width="100%", height="4px",
                bg="rgba(255,255,255,0.07)",
                border_radius="2px",
                overflow="hidden",
            ),
            # ── Row 4: responsible + badges ───────────────────────
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="user", size=11, color=S.TEXT_MUTED),
                    rx.text(row["responsavel"], font_size="11px", color=S.TEXT_MUTED),
                    spacing="1", align="center",
                ),
                rx.spacer(),
                # Desvio badge (produtividade)
                rx.cond(
                    has_desvio,
                    rx.box(
                        rx.text(row["desvio"], font_size="10px", color=S.DANGER,
                                font_family=S.FONT_MONO, font_weight="700"),
                        padding="2px 7px",
                        border_radius="4px",
                        bg="rgba(239,68,68,0.12)",
                        border="1px solid rgba(239,68,68,0.25)",
                    ),
                ),
                # Saldo badge (qty restante ou dias atraso)
                rx.cond(
                    has_saldo,
                    rx.box(
                        rx.text(row["saldo"], font_size="10px",
                                color=rx.cond(is_late, S.DANGER, S.TEXT_MUTED),
                                font_family=S.FONT_MONO),
                        padding="2px 7px",
                        border_radius="4px",
                        bg=rx.cond(is_late, "rgba(239,68,68,0.08)", "rgba(255,255,255,0.05)"),
                        border=rx.cond(
                            is_late,
                            "1px solid rgba(239,68,68,0.2)",
                            f"1px solid {S.BORDER_SUBTLE}",
                        ),
                    ),
                ),
                width="100%", align="center", spacing="2",
            ),
            # ── Row 5: blocking dependency (if any) ───────────────
            rx.cond(
                has_dep,
                rx.hstack(
                    rx.icon(tag="link", size=10, color="#F97316"),
                    rx.text(
                        "Depende de: ",
                        font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                    ),
                    rx.text(
                        row["dependencia"],
                        font_size="10px", color="#F97316", font_family=S.FONT_MONO,
                        font_weight="600", white_space="normal", word_break="break-word",
                    ),
                    spacing="1", align="start",
                    padding="5px 8px",
                    border_radius="5px",
                    bg="rgba(249,115,22,0.07)",
                    border="1px solid rgba(249,115,22,0.2)",
                    width="100%",
                ),
            ),
            spacing="2", width="100%",
        ),
        padding="14px 16px",
        bg="rgba(255,255,255,0.025)",
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_left=rx.cond(
            row["conclusao_pct"] == "100",
            f"3px solid {S.PATINA}",
            rx.cond(is_late | is_risk, f"3px solid {S.DANGER}", f"3px solid {S.COPPER}"),
        ),
        border_radius="8px",
        width="100%",
        transition="background 0.15s",
        _hover={"bg": "rgba(255,255,255,0.045)"},
    )


_POPUP_TITLES = {
    "programado": ("calendar-check", "Programado para Hoje + Atraso Acumulado", "#94A3B8"),
    "realizado":  ("trending-up",    "Realizadas (com progresso registrado)",    S.PATINA),
    "atrasadas":  ("clock",          "Atividades com Término Vencido",           "#F97316"),
    "em_risco":   ("alert-triangle", "Atividades em Risco (prod. abaixo -10%)",  S.DANGER),
    "adiantadas": ("zap",            "Atividades Adiantadas (prod. acima +10%)", S.PATINA),
}


def _cron_kpi_detail_dialog() -> rx.Component:
    """Enterprise KPI detail dialog — activity breakdown by mode."""
    mode = HubState.cron_kpi_popup
    icon_tag = rx.cond(mode == "programado", "calendar-check",
               rx.cond(mode == "realizado",  "trending-up",
               rx.cond(mode == "atrasadas",  "clock",
               rx.cond(mode == "em_risco",   "alert-triangle", "zap"))))
    title_text = rx.cond(mode == "programado", "Agenda de Hoje",
                 rx.cond(mode == "realizado",  "Progresso Registrado",
                 rx.cond(mode == "atrasadas",  "Atividades Vencidas",
                 rx.cond(mode == "em_risco",   "Em Risco — Produtividade Baixa",
                                               "Adiantadas — Acima do Ritmo"))))
    subtitle_text = rx.cond(mode == "programado",
                        "Atividades em execução hoje + pendências acumuladas",
                    rx.cond(mode == "realizado",
                        "Micro-atividades com avanço físico lançado",
                    rx.cond(mode == "atrasadas",
                        "Prazo vencido e execução incompleta — requer ação imediata",
                    rx.cond(mode == "em_risco",
                        "Ritmo atual projeta conclusão além do prazo previsto",
                        "Ritmo acima do planejado — possibilidade de antecipar entrega"))))
    icon_color = rx.cond(mode == "atrasadas", "#F97316",
                 rx.cond(mode == "em_risco",  S.DANGER,
                 rx.cond(mode == "programado", "#94A3B8", S.PATINA)))
    accent_bg = rx.cond(mode == "atrasadas", "rgba(249,115,22,0.07)",
                rx.cond(mode == "em_risco",  "rgba(239,68,68,0.07)",
                rx.cond(mode == "programado", "rgba(148,163,184,0.07)", "rgba(42,157,143,0.07)")))
    count = HubState.cron_kpi_popup_rows.length()

    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # ── Header strip ──────────────────────────────────
                rx.box(
                    rx.hstack(
                        rx.box(
                            rx.icon(tag=icon_tag, size=18, color=icon_color),
                            padding="10px",
                            border_radius="10px",
                            bg=accent_bg,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            flex_shrink="0",
                        ),
                        rx.vstack(
                            rx.text(title_text, font_size="16px", font_weight="700",
                                    color="rgba(255,255,255,0.95)", font_family=S.FONT_TECH,
                                    letter_spacing="-0.01em"),
                            rx.text(subtitle_text, font_size="11px", color=S.TEXT_MUTED,
                                    line_height="1.4"),
                            spacing="0", align="start", flex="1", min_width="0",
                        ),
                        rx.vstack(
                            rx.text(count.to_string(), font_size="28px", font_weight="800",
                                    color=icon_color, font_family=S.FONT_TECH, line_height="1"),
                            rx.text("atividade(s)", font_size="9px", color=S.TEXT_MUTED,
                                    font_family=S.FONT_MONO, letter_spacing="0.06em",
                                    text_transform="uppercase"),
                            spacing="0", align="end", flex_shrink="0",
                        ),
                        rx.icon_button(
                            rx.icon(tag="x", size=16),
                            on_click=HubState.set_cron_kpi_popup(""),
                            variant="ghost", size="2", color_scheme="gray",
                            flex_shrink="0", margin_left="8px",
                        ),
                        width="100%", align="center", spacing="3",
                    ),
                    padding="20px 20px 16px 20px",
                    border_bottom=f"1px solid {S.BORDER_SUBTLE}",
                    bg="rgba(255,255,255,0.015)",
                    width="100%",
                ),
                # ── Activity list ─────────────────────────────────
                rx.box(
                    rx.cond(
                        count > 0,
                        rx.vstack(
                            rx.foreach(HubState.cron_kpi_popup_rows, _kpi_popup_row),
                            spacing="2", width="100%",
                            padding="16px",
                        ),
                        rx.vstack(
                            rx.icon(tag="check-circle", size=36, color=S.PATINA),
                            rx.text("Tudo em ordem!", font_size="15px", font_weight="700",
                                    color="rgba(255,255,255,0.85)"),
                            rx.text("Nenhuma atividade nesta categoria no momento.",
                                    font_size="12px", color=S.TEXT_MUTED, text_align="center"),
                            spacing="2", align="center", padding="40px 24px",
                        ),
                    ),
                    width="100%",
                    max_height="62vh",
                    overflow_y="auto",
                ),
                spacing="0", width="100%",
            ),
            style={
                "background": "#0A1712",
                "border": f"1px solid {S.BORDER_SUBTLE}",
                "borderRadius": "16px",
                "backdropFilter": "blur(24px)",
                "maxWidth": "720px",
                "width": "95vw",
                "padding": "0",
                "overflow": "hidden",
                "boxShadow": "0 24px 80px rgba(0,0,0,0.7)",
            },
        ),
        open=HubState.cron_kpi_popup != "",
    )


def _cron_kpi_panel() -> rx.Component:
    """Dashboard previsto vs realizado — KPIs clicáveis com popup de detalhe."""
    kpi = HubState.cron_kpi_dashboard
    desvio_color = rx.cond(
        HubState.cron_kpi_dashboard["desvio_pp"].startswith("+"),
        S.PATINA,
        rx.cond(HubState.cron_kpi_dashboard["desvio_pp"] == "0.0", S.TEXT_MUTED, S.DANGER),
    )
    return rx.cond(
        HubState.cron_kpi_dashboard["total_micros"] != "0",
        rx.vstack(
            # Header
            rx.hstack(
                rx.icon(tag="activity", size=14, color=S.COPPER),
                rx.text("PREVISTO vs REALIZADO", font_size="11px", font_family=S.FONT_MONO,
                        font_weight="700", color=S.COPPER, letter_spacing="0.08em"),
                rx.spacer(),
                rx.text(kpi["total_micros"] + " micro-atividades", font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                width="100%", align="center",
            ),
            # KPI grid — 6 cards iguais em linha
            rx.grid(
                # Card 1: Programado Hoje — clicável
                rx.vstack(
                    rx.hstack(rx.icon(tag="calendar-check", size=12, color="#64748B"), rx.text("PROGRAMADO HOJE", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"), spacing="1", align="center"),
                    rx.text(kpi["pct_fisico_programado_hoje"] + "%", font_size="20px", color="#94A3B8", font_family=S.FONT_TECH, font_weight="700", line_height="1.1"),
                    rx.text("clique p/ ver atividades", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="start", padding="12px", border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%", height="90px", justify="start",
                    cursor="pointer", on_click=HubState.set_cron_kpi_popup("programado"),
                    _hover={"border": "1px solid rgba(148,163,184,0.4)", "bg": "rgba(255,255,255,0.06)"},
                    transition="all 0.15s",
                ),
                # Card 2: Realizado
                rx.vstack(
                    rx.hstack(rx.icon(tag="trending-up", size=12, color=S.PATINA), rx.text("REALIZADO", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"), spacing="1", align="center"),
                    rx.text(kpi["pct_fisico_realizado"] + "%", font_size="20px", color=S.PATINA, font_family=S.FONT_TECH, font_weight="700", line_height="1.1"),
                    rx.text("clique p/ ver atividades", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="start", padding="12px", border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%", height="90px", justify="start",
                    cursor="pointer", on_click=HubState.set_cron_kpi_popup("realizado"),
                    _hover={"border": f"1px solid {S.PATINA}44", "bg": "rgba(42,157,143,0.05)"},
                    transition="all 0.15s",
                ),
                # Card 3: Desvio — informativo
                rx.vstack(
                    rx.hstack(rx.icon(tag="minus-circle", size=12, color=desvio_color), rx.text("DESVIO", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"), spacing="1", align="center"),
                    rx.text(kpi["desvio_pp"] + "%", font_size="20px", color=desvio_color, font_family=S.FONT_TECH, font_weight="700", line_height="1.1"),
                    rx.text("realizado vs programado", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="start", padding="12px", border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%", height="90px", justify="start",
                ),
                # Card 4: Em Risco — clicável
                rx.vstack(
                    rx.hstack(rx.icon(tag="alert-triangle", size=12, color=S.DANGER), rx.text("EM RISCO", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"), spacing="1", align="center"),
                    rx.text(kpi["atividades_em_risco"], font_size="20px", color=S.DANGER, font_family=S.FONT_TECH, font_weight="700", line_height="1.1"),
                    rx.text("clique p/ ver detalhes", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="start", padding="12px", border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%", height="90px", justify="start",
                    cursor="pointer", on_click=HubState.set_cron_kpi_popup("em_risco"),
                    _hover={"border": f"1px solid {S.DANGER}55", "bg": "rgba(239,68,68,0.05)"},
                    transition="all 0.15s",
                ),
                # Card 5: Atrasadas — clicável
                rx.vstack(
                    rx.hstack(rx.icon(tag="clock", size=12, color="#F97316"), rx.text("ATRASADAS", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"), spacing="1", align="center"),
                    rx.text(kpi["atividades_atrasadas"], font_size="20px", color="#F97316", font_family=S.FONT_TECH, font_weight="700", line_height="1.1"),
                    rx.text("clique p/ ver detalhes", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="start", padding="12px", border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%", height="90px", justify="start",
                    cursor="pointer", on_click=HubState.set_cron_kpi_popup("atrasadas"),
                    _hover={"border": "1px solid rgba(249,115,22,0.4)", "bg": "rgba(249,115,22,0.05)"},
                    transition="all 0.15s",
                ),
                # Card 6: Adiantadas — clicável
                rx.vstack(
                    rx.hstack(rx.icon(tag="zap", size=12, color=S.PATINA), rx.text("ADIANTADAS", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"), spacing="1", align="center"),
                    rx.text(kpi["atividades_adiantadas"], font_size="20px", color=S.PATINA, font_family=S.FONT_TECH, font_weight="700", line_height="1.1"),
                    rx.text("clique p/ ver detalhes", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="start", padding="12px", border_radius=S.R_CONTROL,
                    bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
                    width="100%", height="90px", justify="start",
                    cursor="pointer", on_click=HubState.set_cron_kpi_popup("adiantadas"),
                    _hover={"border": f"1px solid {S.PATINA}44", "bg": "rgba(42,157,143,0.05)"},
                    transition="all 0.15s",
                ),
                columns="6", gap="8px", width="100%",
            ),
            # Produção física total — linha compacta
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="package", size=13, color=S.TEXT_MUTED),
                    rx.text("QTD PLANEJADA:", font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.text(kpi["producao_total_prevista"], font_size="13px", color="white", font_family=S.FONT_TECH, font_weight="600"),
                    spacing="2", align="center",
                ),
                rx.icon(tag="arrow-right", size=12, color=S.BORDER_SUBTLE),
                rx.hstack(
                    rx.text("QTD REALIZADA:", font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.text(kpi["producao_total_realizada"], font_size="13px", color=S.PATINA, font_family=S.FONT_TECH, font_weight="600"),
                    spacing="2", align="center",
                ),
                spacing="3", align="center",
                padding="8px 12px",
                bg="rgba(255,255,255,0.02)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius=S.R_CONTROL,
                width="fit-content",
            ),
            spacing="3", width="100%",
            padding="16px",
            bg="rgba(14,26,23,0.6)",
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius=S.R_CARD,
        ),
    )


def _forecast_row(row: dict) -> rx.Component:
    """One <tr> in the forecast table. Handles both micro rows and sub rows."""
    is_sub    = row["_is_sub"] == "1"
    tendencia = row["_tendencia"]

    tend_color = rx.cond(
        tendencia == "acima",     S.PATINA,
        rx.cond(tendencia == "abaixo",    S.DANGER,
        rx.cond(tendencia == "concluida", "#A855F7", S.TEXT_MUTED))
    )
    tend_icon = rx.cond(
        tendencia == "acima",     "trending-up",
        rx.cond(tendencia == "abaixo",    "trending-down",
        rx.cond(tendencia == "concluida", "check-circle", "minus"))
    )
    tend_label = rx.cond(
        tendencia == "acima",     "Acima",
        rx.cond(tendencia == "abaixo",    "Abaixo",
        rx.cond(tendencia == "concluida", "Concluída",
        rx.cond(tendencia == "dentro",    "No ritmo", "Aguardando")))
    )
    bar_color = rx.cond(
        tendencia == "concluida", "#A855F7",
        rx.cond(tendencia == "acima",  S.PATINA,
        rx.cond(tendencia == "abaixo", S.DANGER,
        rx.cond(tendencia == "dentro", S.COPPER, S.TEXT_MUTED)))
    )
    desvio_color = rx.cond(
        row["_desvio_dias"].startswith("-"), S.PATINA,
        rx.cond(row["_desvio_dias"] == "0", S.TEXT_MUTED, S.DANGER)
    )
    prod_real_f = row["_prod_real"].to(float)
    prod_plan_f = row["_prod_planejada"].to(float)
    prod_color = rx.cond(
        prod_plan_f == 0, S.TEXT_MUTED,
        rx.cond(prod_real_f >= prod_plan_f, S.PATINA,
        rx.cond(prod_real_f >= prod_plan_f * 0.8, S.COPPER, S.DANGER))
    )
    has_day_ctx = (row["_dia_atual"] != "0") & (row["_total_dias"] != "0")
    has_eac     = row["_data_fim_prevista"] != "—"
    show_esp    = has_day_ctx & (row["_pct_esperado"] != "0")
    has_subs    = row["_has_subs"] == "1"
    prazo_est   = row["_prazo_estourado"] == "1"

    # ── SUB ROW: visual compacto, indentado ───────────────────────────────
    sub_pct_f = row["conclusao_pct"].to(float)

    td_sub = {
        "padding": "7px 10px",
        "vertical_align": "middle",
        "border_bottom": f"1px solid rgba(255,255,255,0.04)",
        "background": "rgba(255,255,255,0.012)",
    }
    sub_row = rx.el.tr(
        rx.el.td(
            rx.hstack(
                # Indent indicator
                rx.box(width="2px", height="28px", bg="rgba(255,255,255,0.1)",
                       border_radius="1px", flex_shrink="0"),
                rx.box(width="12px", height="1px", bg="rgba(255,255,255,0.1)", flex_shrink="0"),
                rx.vstack(
                    rx.text(row["atividade"],
                            font_size="11px", color="rgba(255,255,255,0.65)",
                            font_weight="500", line_height="1.2"),
                    rx.hstack(
                        rx.icon(tag="user", size=9, color="rgba(255,255,255,0.3)"),
                        rx.text(row["responsavel"], font_size="9px",
                                color="rgba(255,255,255,0.3)"),
                        rx.cond(
                            row["_sub_peso"] != "0",
                            rx.text("· peso " + row["_sub_peso"] + "%",
                                    font_size="9px", color="rgba(255,255,255,0.25)",
                                    font_family=S.FONT_MONO),
                        ),
                        spacing="1", align="center",
                    ),
                    spacing="1",
                ),
                spacing="0", align="center",
            ),
            **td_sub,
            border_left="3px solid rgba(255,255,255,0.06)",
            padding_left="12px",
        ),
        # Sub progresso
        rx.el.td(
            rx.box(
                rx.hstack(
                    rx.spacer(),
                    rx.text(row["conclusao_pct"] + "%",
                            font_size="12px", color=bar_color,
                            font_family=S.FONT_MONO, font_weight="700"),
                    width="100%", align="center",
                ),
                rx.box(
                    rx.box(width=row["conclusao_pct"] + "%", height="100%",
                           bg=bar_color, border_radius="2px"),
                    width="100%", height="3px", bg="rgba(255,255,255,0.05)",
                    border_radius="2px", overflow="hidden", margin_top="4px",
                ),
                rx.hstack(
                    rx.text("Esperado", font_size="9px",
                            color=rx.cond(show_esp, "rgba(255,255,255,0.2)", "transparent")),
                    rx.spacer(),
                    rx.text(rx.cond(show_esp, row["_pct_esperado"] + "%", ""),
                            font_size="9px", font_family=S.FONT_MONO,
                            color=rx.cond(show_esp, "rgba(255,255,255,0.3)", "transparent")),
                    width="100%", align="center", margin_top="4px",
                ),
            ),
            **td_sub,
        ),
        # Sub produtividade — vazio (subs não têm qty própria)
        rx.el.td(rx.box(), **td_sub),
        # Sub tendência
        rx.el.td(
            rx.hstack(
                rx.icon(tag=tend_icon, size=11, color=tend_color),
                rx.text(tend_label, font_size="10px", color=tend_color, font_weight="600"),
                spacing="1", align="center",
                padding="3px 8px", border_radius="5px",
                display="inline-flex",
                bg=rx.cond(
                    tendencia == "acima",  "rgba(42,157,143,0.08)",
                    rx.cond(tendencia == "abaixo", "rgba(239,68,68,0.08)",
                    rx.cond(tendencia == "concluida", "rgba(168,85,247,0.08)",
                            "rgba(255,255,255,0.03)"))
                ),
            ),
            **td_sub,
        ),
        # Sub EAC — vazio
        rx.el.td(rx.box(), **td_sub, padding_right="20px"),
        style={"transition": "background 0.1s"},
    )

    # ── MICRO ROW ─────────────────────────────────────────────────────────
    td_style = {
        "padding": "14px 10px",
        "vertical_align": "middle",
        "border_bottom": f"1px solid {S.BORDER_SUBTLE}",
    }
    micro_row = rx.el.tr(
        # TD 1: atividade
        rx.el.td(
            rx.box(
                rx.hstack(
                    rx.box(
                        rx.text(row["fase_macro"],
                                font_size="9px", color=S.COPPER,
                                font_weight="700", letter_spacing="0.05em",
                                text_transform="uppercase"),
                        padding="1px 6px", border_radius="3px",
                        bg="rgba(201,139,42,0.12)", border="1px solid rgba(201,139,42,0.25)",
                        white_space="nowrap",
                    ),
                    rx.cond(
                        has_day_ctx,
                        rx.text("Dia " + row["_dia_atual"] + " de " + row["_total_dias"],
                                font_size="9px", color=S.TEXT_MUTED,
                                font_family=S.FONT_MONO, white_space="nowrap"),
                    ),
                    spacing="2", align="center",
                ),
                rx.hstack(
                    rx.text(row["atividade"],
                            font_size="13px", color="rgba(255,255,255,0.92)",
                            font_weight="600", line_height="1.35",
                            margin_top="5px"),
                    rx.cond(
                        has_subs,
                        rx.box(
                            rx.text(row["_sub_count"] + " subs",
                                    font_size="8px", color="rgba(255,255,255,0.35)",
                                    font_family=S.FONT_MONO),
                            padding="1px 5px", border_radius="3px",
                            bg="rgba(255,255,255,0.05)",
                            border="1px solid rgba(255,255,255,0.08)",
                            margin_top="6px", flex_shrink="0",
                        ),
                    ),
                    spacing="2", align="start",
                ),
                rx.hstack(
                    rx.icon(tag="user", size=10, color=S.TEXT_MUTED),
                    rx.text(row["responsavel"], font_size="10px", color=S.TEXT_MUTED),
                    spacing="1", align="center", margin_top="4px",
                ),
            ),
            padding="14px 16px",
            vertical_align="middle",
            border_bottom=f"1px solid {S.BORDER_SUBTLE}",
            border_left=rx.cond(
                tendencia == "concluida", "3px solid #A855F7",
                rx.cond(tendencia == "acima",  f"3px solid {S.PATINA}",
                rx.cond(tendencia == "abaixo", f"3px solid {S.DANGER}",
                rx.cond(tendencia == "dentro", f"3px solid {S.COPPER}",
                        "3px solid rgba(255,255,255,0.08)")))
            ),
        ),
        # TD 2: progresso
        rx.el.td(
            rx.box(
                rx.hstack(
                    rx.text("Realizado", font_size="9px", color=S.TEXT_MUTED),
                    rx.spacer(),
                    rx.text(row["conclusao_pct"] + "%",
                            font_size="15px", color=bar_color,
                            font_family=S.FONT_MONO, font_weight="700", line_height="1"),
                    width="100%", align="center",
                ),
                rx.box(
                    rx.box(width=row["conclusao_pct"] + "%", height="100%",
                           bg=bar_color, border_radius="2px",
                           transition="width 0.4s ease"),
                    width="100%", height="5px", bg="rgba(255,255,255,0.07)",
                    border_radius="2px", overflow="hidden", margin_top="5px",
                ),
                rx.hstack(
                    rx.text("Esperado", font_size="9px",
                            color=rx.cond(show_esp, "rgba(255,255,255,0.3)", "transparent")),
                    rx.spacer(),
                    rx.text(rx.cond(show_esp, row["_pct_esperado"] + "%", ""),
                            font_size="9px", font_family=S.FONT_MONO,
                            color=rx.cond(show_esp, "rgba(255,255,255,0.4)", "transparent")),
                    width="100%", align="center", margin_top="6px",
                ),
                rx.box(
                    rx.box(
                        width=rx.cond(show_esp, row["_pct_esperado"] + "%", "0%"),
                        height="100%", bg="rgba(255,255,255,0.18)", border_radius="1px",
                    ),
                    width="100%", height="2px",
                    bg=rx.cond(show_esp, "rgba(255,255,255,0.04)", "transparent"),
                    border_radius="1px", overflow="hidden", margin_top="3px",
                ),
            ),
            **td_style,
            padding_right="16px",
        ),
        # TD 3: produtividade / dia
        rx.el.td(
            rx.box(
                rx.hstack(
                    rx.text(row["_prod_real"],
                            font_size="17px", color=prod_color,
                            font_family=S.FONT_MONO, font_weight="700", line_height="1"),
                    rx.text("/", font_size="12px", color=S.TEXT_MUTED, line_height="1"),
                    rx.text(row["_prod_planejada"],
                            font_size="13px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, line_height="1"),
                    spacing="1", align="baseline",
                ),
                rx.text(row["unidade"] + "/dia · realizado / planejado",
                        font_size="9px", color=S.TEXT_MUTED, margin_top="4px"),
                rx.text(
                    rx.cond(row["_exec_label"] != "", row["_exec_label"], ""),
                    font_size="10px", font_family=S.FONT_MONO, margin_top="2px",
                    color=rx.cond(row["_exec_label"] != "",
                                  "rgba(255,255,255,0.55)", "transparent"),
                ),
            ),
            **td_style,
            padding_right="16px",
        ),
        # TD 4: tendência + magnitude
        rx.el.td(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag=tend_icon, size=13, color=tend_color),
                    rx.text(tend_label, font_size="11px", color=tend_color,
                            font_weight="700", white_space="nowrap"),
                    spacing="1", align="center",
                    padding="5px 10px", border_radius="6px",
                    display="inline-flex",
                    bg=rx.cond(
                        tendencia == "acima",     "rgba(42,157,143,0.1)",
                        rx.cond(tendencia == "abaixo",    "rgba(239,68,68,0.1)",
                        rx.cond(tendencia == "concluida", "rgba(168,85,247,0.1)",
                                "rgba(255,255,255,0.04)"))
                    ),
                    border=rx.cond(
                        tendencia == "acima",     f"1px solid {S.PATINA}44",
                        rx.cond(tendencia == "abaixo",    f"1px solid {S.DANGER}44",
                        rx.cond(tendencia == "concluida", "1px solid rgba(168,85,247,0.3)",
                                f"1px solid {S.BORDER_SUBTLE}"))
                    ),
                ),
                # Magnitude do desvio — só quando tem dado real
                rx.cond(
                    (tendencia != "sem_dados") & (tendencia != "concluida"),
                    rx.text(row["_desvio_label"],
                            font_size="9px", font_family=S.FONT_MONO,
                            color=rx.cond(
                                tendencia == "acima",  f"{S.PATINA}99",
                                rx.cond(tendencia == "abaixo", f"{S.DANGER}99", S.TEXT_MUTED)
                            ),
                            margin_top="3px"),
                ),
                spacing="0", align_items="flex-start",
            ),
            **td_style,
            padding_right="16px",
        ),
        # TD 5: EAC
        rx.el.td(
            rx.box(
                rx.text(
                    rx.cond(has_eac, row["_data_fim_prevista"], row["termino_previsto"]),
                    font_size="14px", font_family=S.FONT_MONO, font_weight="600",
                    color=rx.cond(has_eac, "rgba(255,255,255,0.88)", S.TEXT_MUTED),
                    white_space="nowrap",
                ),
                rx.text(
                    rx.cond(row["_desvio_dias"] == "0", "no prazo",
                        rx.cond(row["_desvio_dias"].startswith("-"),
                            row["_desvio_dias"] + "du adiantado",
                            "+" + row["_desvio_dias"] + "du atraso")),
                    font_size="10px", font_family=S.FONT_MONO, font_weight="600",
                    color=rx.cond(has_eac, desvio_color, "transparent"),
                    margin_top="2px", white_space="nowrap",
                ),
                rx.text("término previsto", font_size="9px", color=S.TEXT_MUTED,
                        margin_top="1px"),
            ),
            **td_style,
            padding_right="20px",
            text_align="right",
        ),
        _hover={"background": "rgba(255,255,255,0.022)"},
        style={"transition": "background 0.15s"},
    )

    return rx.cond(is_sub, sub_row, micro_row)


# Keep old name as alias
_forecast_card = _forecast_row


def _forecast_filter_btn(label: str, value: str, count_key: str) -> rx.Component:
    """Botão de filtro de status do painel forecast."""
    is_active = HubState.cron_forecast_filter == value
    count = HubState.cron_forecast_kpis[count_key]
    return rx.button(
        rx.hstack(
            rx.text(label, font_size="11px", font_weight="600", white_space="nowrap"),
            rx.box(
                rx.text(count, font_size="9px", font_family=S.FONT_MONO, font_weight="700"),
                padding="1px 6px", border_radius="10px",
                bg=rx.cond(is_active, "rgba(255,255,255,0.15)", "rgba(255,255,255,0.06)"),
            ),
            spacing="2", align="center",
        ),
        variant="ghost",
        cursor="pointer",
        on_click=HubState.set_cron_forecast_filter(value),
        padding="5px 12px",
        border_radius="6px",
        border=rx.cond(is_active, "1px solid rgba(168,85,247,0.5)", f"1px solid transparent"),
        bg=rx.cond(is_active, "rgba(168,85,247,0.1)", "transparent"),
        color=rx.cond(is_active, "#A855F7", S.TEXT_MUTED),
        _hover={"bg": "rgba(255,255,255,0.04)", "color": "white"},
    )


def _cron_forecast_panel() -> rx.Component:
    """Produtividade & Forecast — HTML table garante alinhamento perfeito de colunas."""
    kpis = HubState.cron_forecast_kpis
    desvio_positivo = kpis["desvio_positivo"] == "1"

    th_style_base = {
        "font_size": "9px", "color": S.TEXT_MUTED,
        "font_family": S.FONT_MONO, "letter_spacing": "0.08em",
        "font_weight": "600", "background": "rgba(255,255,255,0.02)",
        "border_bottom": f"1px solid {S.BORDER_SUBTLE}",
    }

    return rx.cond(
        HubState.cron_forecast_rows.length() > 0,
        rx.box(
            # ── Header: título + legenda ──────────────────────────────────
            rx.hstack(
                rx.box(
                    rx.icon(tag="radar", size=14, color="#A855F7"),
                    padding="7px", border_radius="8px",
                    bg="rgba(168,85,247,0.1)", border="1px solid rgba(168,85,247,0.2)",
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text("PRODUTIVIDADE & FORECAST",
                            font_size="11px", font_family=S.FONT_MONO,
                            font_weight="700", color="#A855F7", letter_spacing="0.09em"),
                    rx.text("Ritmo de execução · Dia atual do plano · Projeção EAC",
                            font_size="9px", color=S.TEXT_MUTED),
                    spacing="0", align="start",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.hstack(rx.box(width="7px", height="7px", border_radius="50%", bg=S.PATINA),
                              rx.text("Acima",    font_size="9px", color=S.TEXT_MUTED),
                              spacing="1", align="center"),
                    rx.hstack(rx.box(width="7px", height="7px", border_radius="50%", bg=S.COPPER),
                              rx.text("No ritmo", font_size="9px", color=S.TEXT_MUTED),
                              spacing="1", align="center"),
                    rx.hstack(rx.box(width="7px", height="7px", border_radius="50%", bg=S.DANGER),
                              rx.text("Abaixo",   font_size="9px", color=S.TEXT_MUTED),
                              spacing="1", align="center"),
                    rx.hstack(rx.box(width="7px", height="7px", border_radius="50%", bg="#A855F7"),
                              rx.text("Concluída", font_size="9px", color=S.TEXT_MUTED),
                              spacing="1", align="center"),
                    spacing="4", align="center",
                ),
                width="100%", align="center", spacing="3",
                padding="13px 20px 11px 16px",
                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
            ),
            # ── KPI summary bar ───────────────────────────────────────────
            rx.hstack(
                # Em execução
                rx.hstack(
                    rx.box(
                        rx.icon(tag="activity", size=13, color=S.COPPER),
                        padding="5px", border_radius="6px",
                        bg="rgba(201,139,42,0.1)", border=f"1px solid rgba(201,139,42,0.2)",
                    ),
                    rx.vstack(
                        rx.text(kpis["em_exec"],
                                font_size="16px", font_family=S.FONT_MONO, font_weight="700",
                                color="rgba(255,255,255,0.9)", line_height="1"),
                        rx.text("em execução", font_size="9px", color=S.TEXT_MUTED),
                        spacing="0",
                    ),
                    spacing="2", align="center",
                ),
                rx.box(width="1px", height="28px", bg=S.BORDER_SUBTLE),
                # Em risco
                rx.hstack(
                    rx.box(
                        rx.icon(tag="alert-triangle", size=13, color=S.DANGER),
                        padding="5px", border_radius="6px",
                        bg="rgba(239,68,68,0.1)", border="1px solid rgba(239,68,68,0.2)",
                    ),
                    rx.vstack(
                        rx.text(kpis["em_risco"],
                                font_size="16px", font_family=S.FONT_MONO, font_weight="700",
                                color=rx.cond(kpis["em_risco"] == "0",
                                              "rgba(255,255,255,0.9)", S.DANGER),
                                line_height="1"),
                        rx.text("em risco", font_size="9px", color=S.TEXT_MUTED),
                        spacing="0",
                    ),
                    spacing="2", align="center",
                ),
                rx.box(width="1px", height="28px", bg=S.BORDER_SUBTLE),
                # Desvio médio
                rx.hstack(
                    rx.box(
                        rx.icon(tag="trending-up", size=13,
                                color=rx.cond(desvio_positivo, S.PATINA, S.DANGER)),
                        padding="5px", border_radius="6px",
                        bg=rx.cond(desvio_positivo,
                                   "rgba(42,157,143,0.1)", "rgba(239,68,68,0.1)"),
                        border=rx.cond(desvio_positivo,
                                       f"1px solid {S.PATINA}44", "1px solid rgba(239,68,68,0.2)"),
                    ),
                    rx.vstack(
                        rx.text(kpis["desvio_medio"],
                                font_size="16px", font_family=S.FONT_MONO, font_weight="700",
                                color=rx.cond(desvio_positivo, S.PATINA, S.DANGER),
                                line_height="1"),
                        rx.text("desvio médio prod.", font_size="9px", color=S.TEXT_MUTED),
                        spacing="0",
                    ),
                    spacing="2", align="center",
                ),
                rx.box(width="1px", height="28px", bg=S.BORDER_SUBTLE),
                # Concluídas
                rx.hstack(
                    rx.box(
                        rx.icon(tag="check-circle", size=13, color="#A855F7"),
                        padding="5px", border_radius="6px",
                        bg="rgba(168,85,247,0.1)", border="1px solid rgba(168,85,247,0.2)",
                    ),
                    rx.vstack(
                        rx.text(kpis["concluidas"],
                                font_size="16px", font_family=S.FONT_MONO, font_weight="700",
                                color="rgba(255,255,255,0.9)", line_height="1"),
                        rx.text("concluídas", font_size="9px", color=S.TEXT_MUTED),
                        spacing="0",
                    ),
                    spacing="2", align="center",
                ),
                rx.spacer(),
                # ── Filtros de status ─────────────────────────────────────
                rx.hstack(
                    _forecast_filter_btn("Em execução", "execucao", "em_exec"),
                    _forecast_filter_btn("Concluídas",  "concluida", "concluidas"),
                    _forecast_filter_btn("Previstas",   "prevista",  "previstas"),
                    _forecast_filter_btn("Todas",       "todas",     "em_exec"),
                    spacing="2", flex_shrink="0",
                ),
                spacing="4", align="center", width="100%",
                padding="10px 20px",
                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
                bg="rgba(255,255,255,0.015)",
            ),
            # ── Empty state quando filtro não tem resultados ───────────────
            rx.cond(
                HubState.cron_forecast_filtered.length() == 0,
                rx.hstack(
                    rx.icon(tag="inbox", size=16, color=S.TEXT_MUTED),
                    rx.text(
                        rx.cond(HubState.cron_forecast_filter == "concluida",
                                "Nenhuma atividade concluída ainda.",
                        rx.cond(HubState.cron_forecast_filter == "prevista",
                                "Sem atividades previstas com dados de quantidade.",
                                "Nenhuma atividade em execução no momento.")),
                        font_size="13px", color=S.TEXT_MUTED,
                    ),
                    spacing="2", align="center",
                    padding="24px 20px", justify="center", width="100%",
                ),
                # ── HTML table ────────────────────────────────────────────
                rx.el.table(
                    rx.el.colgroup(
                        rx.el.col(style={"width": "26%"}),
                        rx.el.col(style={"width": "23%"}),
                        rx.el.col(style={"width": "22%"}),
                        rx.el.col(style={"width": "16%"}),
                        rx.el.col(style={"width": "13%"}),
                    ),
                    rx.el.thead(
                        rx.el.tr(
                            rx.el.th("ATIVIDADE", style={**th_style_base,
                                     "text_align": "left", "padding": "7px 16px", "white_space": "nowrap"}),
                            rx.el.th("PROGRESSO", style={**th_style_base,
                                     "text_align": "left", "padding": "7px 16px 7px 10px"}),
                            rx.el.th("PRODUTIVIDADE / DIA", style={**th_style_base,
                                     "text_align": "left", "padding": "7px 16px 7px 10px"}),
                            rx.el.th("TENDÊNCIA", style={**th_style_base,
                                     "text_align": "left", "padding": "7px 16px 7px 10px"}),
                            rx.el.th("EAC", style={**th_style_base,
                                     "text_align": "right", "padding": "7px 20px 7px 10px"}),
                        )
                    ),
                    rx.el.tbody(
                        rx.foreach(HubState.cron_forecast_filtered, _forecast_row),
                    ),
                    width="100%",
                    border_collapse="collapse",
                    style={"table_layout": "fixed"},
                ),
            ),
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius=S.R_CARD,
            overflow="hidden",
            bg="rgba(14,26,23,0.4)",
            width="100%",
        ),
    )


def _cron_import_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.icon(tag="sparkles", size=16, color="#A855F7"),
                    rx.dialog.title("Importar Cronograma via IA", font_family=S.FONT_TECH, font_size="1rem", font_weight="700", color="var(--text-main)"),
                    rx.spacer(),
                    rx.dialog.close(rx.icon_button(rx.icon(tag="x", size=14), size="1", variant="ghost", cursor="pointer", on_click=HubState.close_import_preview)),
                    align="center", width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                # Error banner
                rx.cond(
                    HubState.cron_import_error != "",
                    rx.callout.root(
                        rx.callout.icon(rx.icon(tag="alert-triangle", size=16)),
                        rx.callout.text(HubState.cron_import_error),
                        color="red", variant="soft",
                    ),
                ),
                # Info + confidence badge
                rx.hstack(
                    rx.text(
                        "Revise as atividades propostas pela IA. Selecione quais deseja importar e clique em Confirmar.",
                        font_size="12px", color=S.TEXT_MUTED,
                    ),
                    rx.spacer(),
                    rx.cond(
                        HubState.cron_import_confidence_label != "",
                        rx.badge(
                            rx.hstack(rx.icon(tag="shield-check", size=10), rx.text("Confiança: " + HubState.cron_import_confidence_label, font_size="10px"), spacing="1", align="center"),
                            color_scheme=rx.cond(
                                HubState.cron_import_confidence_label.contains("Alta"),
                                "green",
                                rx.cond(HubState.cron_import_confidence_label.contains("Média"), "amber", "red"),
                            ),
                            variant="soft",
                        ),
                    ),
                    align="center", width="100%",
                ),
                # Select all / deselect all
                rx.hstack(
                    rx.text(HubState.cron_import_preview.length().to_string() + " atividades propostas", font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.spacer(),
                    rx.button("Selecionar todas", variant="ghost", size="1", color=S.COPPER, cursor="pointer", on_click=HubState.select_all_import),
                    rx.button("Desmarcar todas", variant="ghost", size="1", color=S.TEXT_MUTED, cursor="pointer", on_click=HubState.deselect_all_import),
                    align="center", width="100%",
                ),
                # Preview table
                rx.box(
                    rx.vstack(
                        rx.foreach(
                            HubState.cron_import_preview,
                            lambda row: rx.hstack(
                                rx.checkbox(
                                    checked=HubState.cron_import_selected.contains(row["_tmp_id"]),
                                    on_change=lambda checked: HubState.toggle_import_activity(row["_tmp_id"]),
                                    color_scheme="amber",
                                ),
                                rx.vstack(
                                    rx.hstack(
                                        rx.box(
                                            rx.text(rx.cond(row["nivel"] == "macro", "MACRO", "MICRO"), font_size="9px", font_family=S.FONT_MONO, font_weight="700"),
                                            padding="1px 5px",
                                            background=rx.cond(row["nivel"] == "macro", "rgba(232,152,69,0.15)", "rgba(74,222,128,0.1)"),
                                            color=rx.cond(row["nivel"] == "macro", S.COPPER, S.PATINA),
                                            border=rx.cond(row["nivel"] == "macro", f"1px solid rgba(232,152,69,0.4)", "1px solid rgba(74,222,128,0.3)"),
                                            border_radius="3px",
                                        ),
                                        rx.text(row["atividade"], font_size="13px", color="white", font_weight="600"),
                                        spacing="2", align="center",
                                    ),
                                    rx.hstack(
                                        rx.text(row["fase_macro"], font_size="11px", color=S.TEXT_MUTED),
                                        rx.text("·", color=S.BORDER_SUBTLE),
                                        rx.text(row["inicio_previsto"] + " → " + row["termino_previsto"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                        rx.text("·", color=S.BORDER_SUBTLE),
                                        rx.text(row["dias_planejados"] + " dias", font_size="11px", color=S.COPPER, font_family=S.FONT_MONO),
                                        spacing="1", align="center", flex_wrap="wrap",
                                    ),
                                    spacing="1",
                                ),
                                align="start", spacing="3", padding="10px 12px",
                                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
                                _hover={"bg": "rgba(255,255,255,0.02)"},
                                width="100%",
                            ),
                        ),
                        spacing="0",
                    ),
                    max_height="360px",
                    overflow_y="auto",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    border_radius=S.R_CONTROL,
                ),
                # Footer
                rx.hstack(
                    rx.dialog.close(rx.button("Cancelar", variant="ghost", size="2", color=S.TEXT_MUTED, cursor="pointer", on_click=HubState.close_import_preview)),
                    rx.button(
                        rx.cond(
                            HubState.cron_import_loading,
                            rx.hstack(rx.spinner(size="2"), rx.text("Importando..."), spacing="1"),
                            rx.hstack(rx.icon(tag="download", size=13), rx.text("Confirmar Importação"), spacing="1", align="center"),
                        ),
                        on_click=HubState.confirm_import_cronograma,
                        size="2",
                        disabled=HubState.cron_import_loading,
                        style={"background": "#A855F7", "color": "white", "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                    ),
                    justify="end", spacing="2", width="100%", padding_top="8px",
                ),
                spacing="4", width="100%",
            ),
            bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}", border_radius=S.R_CARD,
            max_width="680px", width="95vw",
        ),
        open=HubState.cron_import_show,
    )


def _cron_edit_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(
                        tag=rx.cond(HubState.cron_edit_id == "", "circle-plus", rx.cond(HubState.cron_pending_review_id != "", "clipboard-pen", "pencil")),
                        size=16,
                        color=rx.cond(HubState.cron_pending_review_id != "", "#E89845", S.COPPER),
                    ),
                    rx.dialog.title(
                        rx.cond(
                            HubState.cron_pending_review_id != "",
                            rx.hstack(
                                rx.text("Revisar Atividade", font_family=S.FONT_TECH, font_size="1rem", font_weight="700", color="var(--text-main)"),
                                rx.box("APROVAÇÃO PENDENTE", padding="2px 6px", background="rgba(232,152,69,0.15)", color="#E89845", font_size="9px", font_family=S.FONT_MONO, border="1px solid rgba(232,152,69,0.4)", border_radius="3px", letter_spacing="0.05em"),
                                spacing="2", align="center",
                            ),
                            rx.cond(HubState.cron_edit_id == "", "Nova Atividade", "Editar Atividade"),
                        ),
                        font_family=S.FONT_TECH, font_size="1rem", font_weight="700", color="var(--text-main)",
                    ),
                    rx.spacer(),
                    rx.dialog.close(rx.icon_button(rx.icon(tag="x", size=14), size="1", variant="ghost", cursor="pointer")),
                    align="center", width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                # Row 1: Fase Macro + Fase
                # Note: text inputs use default_value + on_blur (uncontrolled) to avoid
                # per-keystroke round-trips to the server that cause input lag.
                # Date/number inputs keep on_change (they don't have the lag problem).
                rx.flex(
                    # Fase Macro: editável apenas para macros; somente leitura para micro/sub
                    # (micro e sub herdam a fase_macro da macro pai — não pode ser alterado manualmente)
                    rx.cond(
                        HubState.cron_edit_nivel == "macro",
                        rx.vstack(
                            rx.text("Fase Macro", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(default_value=HubState.cron_edit_fase_macro, on_blur=HubState.set_cron_edit_fase_macro, placeholder="Ex: Elétrica", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"14px","width":"100%","outline":"none"}),
                            spacing="1", flex="1",
                        ),
                        rx.vstack(
                            rx.hstack(
                                rx.text("Fase Macro", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                rx.icon("lock", size=12, color=S.TEXT_MUTED),
                                spacing="1", align="center",
                            ),
                            rx.box(
                                rx.text(HubState.cron_edit_fase_macro, font_size="14px", color="rgba(255,255,255,0.5)"),
                                style={"background":"rgba(14,26,23,0.4)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"padding":"8px 10px","width":"100%"},
                                title="Fase Macro é herdada da atividade pai e não pode ser alterada aqui.",
                            ),
                            spacing="1", flex="1",
                        ),
                    ),
                    rx.vstack(rx.text("Fase", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                              rx.el.input(default_value=HubState.cron_edit_fase, on_blur=HubState.set_cron_edit_fase, placeholder="Ex: SPDA", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"14px","width":"100%","outline":"none"}), spacing="1", flex="1"),
                    gap="12px", flex_wrap="wrap",
                ),
                # Row 2: Atividade (oculto se macro — preenchido automaticamente) + Responsável
                rx.cond(
                    (HubState.cron_edit_nivel == "micro") | (HubState.cron_edit_nivel == "sub"),
                    rx.flex(
                        rx.vstack(rx.text("Atividade *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                  rx.el.input(default_value=HubState.cron_edit_atividade, on_blur=HubState.set_cron_edit_atividade, placeholder="Nome da atividade", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"14px","width":"100%","outline":"none"}), spacing="1", flex="1"),
                        rx.vstack(rx.text("Responsável", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                  rx.el.input(default_value=HubState.cron_edit_responsavel, on_blur=HubState.set_cron_edit_responsavel, placeholder="Ex: Engenheiro A", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"14px","width":"100%","outline":"none"}), spacing="1", flex="1"),
                        gap="12px", flex_wrap="wrap",
                    ),
                    rx.flex(
                        rx.vstack(rx.text("Responsável", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                  rx.el.input(default_value=HubState.cron_edit_responsavel, on_blur=HubState.set_cron_edit_responsavel, placeholder="Ex: Engenheiro A", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"14px","width":"100%","outline":"none"}), spacing="1", flex="1"),
                        gap="12px", flex_wrap="wrap",
                    ),
                ),
                # Row 3: Datas + Dias Planejados
                rx.flex(
                    rx.vstack(rx.text("Início Previsto", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                              rx.el.input(type="date", value=HubState.cron_edit_inicio, on_change=HubState.set_cron_edit_inicio, style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"100%","outline":"none","colorScheme":"dark"}), spacing="1", flex="1"),
                    rx.vstack(rx.text("Término Previsto", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                              rx.el.input(type="date", value=HubState.cron_edit_termino, on_change=HubState.set_cron_edit_termino, style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"100%","outline":"none","colorScheme":"dark"}), spacing="1", flex="1"),
                    rx.vstack(
                        rx.hstack(
                            rx.text("Dias Planejados", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.text("(úteis)", font_size="10px", color=S.TEXT_MUTED, font_style="italic"),
                            spacing="1", align="center",
                        ),
                        rx.el.input(
                            type="number",
                            default_value=HubState.cron_edit_dias_planejados,
                            on_blur=HubState.set_cron_edit_dias_planejados,
                            placeholder="Ex: 10",
                            min="0",
                            style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"120px","outline":"none"},
                        ),
                        spacing="1",
                    ),
                    gap="12px", flex_wrap="wrap",
                ),
                # Row 4a: Tipo (readonly badge) + Hierarquia pai (info) + Peso
                rx.flex(
                    # Tipo — sempre readonly (determinado pela ação de criação)
                    rx.vstack(
                        rx.text("Tipo", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.box(
                            rx.text(
                                HubState.cron_edit_nivel_label,
                                font_size="13px",
                                color=S.COPPER,
                                font_family=S.FONT_MONO,
                                font_weight="600",
                            ),
                            style={
                                "background": "rgba(201,139,42,0.1)",
                                "border": f"1px solid {S.COPPER}55",
                                "borderRadius": S.R_CONTROL,
                                "padding": "8px 12px",
                                "width": "180px",
                            },
                        ),
                        spacing="1",
                    ),
                    # Hierarquia pai — exibição informativa (não editável quando parent_id já definido)
                    rx.cond(
                        HubState.cron_edit_nivel == "macro",
                        rx.fragment(),  # macro não tem pai
                        rx.cond(
                            HubState.cron_edit_nivel == "micro",
                            # micro: mostra macro pai como info se parent_id setado, senão select
                            rx.cond(
                                HubState.cron_edit_parent_id != "",
                                rx.vstack(
                                    rx.text("Macro Pai", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                    rx.hstack(
                                        rx.icon(tag="layers", size=13, color="#2A9D8F"),
                                        rx.text(HubState.cron_edit_parent_name, font_size="13px", color="#2A9D8F", font_weight="600"),
                                        spacing="2", align="center",
                                        style={"background": "rgba(42,157,143,0.1)", "border": "1px solid #2A9D8F55", "borderRadius": S.R_CONTROL, "padding": "8px 12px"},
                                    ),
                                    spacing="1", flex="1",
                                ),
                                # sem parent_id definido: dropdown de seleção
                                rx.vstack(
                                    rx.text("Macro Pai *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                    rx.cond(
                                        HubState.cron_parent_options.length() > 0,
                                        rx.select.root(
                                            rx.select.trigger(placeholder="Selecionar macro...", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","fontSize":"13px","width":"200px","outline":"none"}),
                                            rx.select.content(
                                                rx.foreach(HubState.cron_parent_options, lambda opt: rx.select.item(opt["label"], value=opt["id"])),
                                                style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}", "zIndex": "9999"},
                                                position="popper",
                                            ),
                                            value=HubState.cron_edit_parent_id,
                                            on_change=HubState.set_cron_edit_parent_id,
                                        ),
                                        rx.text("Crie uma atividade macro primeiro", font_size="11px", color=S.TEXT_MUTED, font_style="italic"),
                                    ),
                                    spacing="1", flex="1",
                                ),
                            ),
                            # sub: mostra macro + micro pai como info
                            rx.vstack(
                                rx.text("Hierarquia", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                rx.cond(
                                    HubState.cron_edit_parent_id != "",
                                    rx.hstack(
                                        rx.cond(
                                            HubState.cron_edit_macro_name != "",
                                            rx.hstack(
                                                rx.icon(tag="layers", size=12, color=S.TEXT_MUTED),
                                                rx.text(HubState.cron_edit_macro_name, font_size="12px", color=S.TEXT_MUTED),
                                                spacing="1", align="center",
                                            ),
                                            rx.fragment(),
                                        ),
                                        rx.icon(tag="chevron-right", size=12, color=S.TEXT_MUTED),
                                        rx.icon(tag="git-branch", size=12, color="#2A9D8F"),
                                        rx.text(HubState.cron_edit_parent_name, font_size="12px", color="#2A9D8F", font_weight="600"),
                                        spacing="2", align="center",
                                        style={"background": "rgba(42,157,143,0.08)", "border": "1px solid #2A9D8F33", "borderRadius": S.R_CONTROL, "padding": "8px 12px"},
                                    ),
                                    # sem parent: dropdown de micro
                                    rx.cond(
                                        HubState.cron_micro_options.length() > 0,
                                        rx.select.root(
                                            rx.select.trigger(placeholder="Selecionar micro pai...", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","fontSize":"13px","width":"220px","outline":"none"}),
                                            rx.select.content(
                                                rx.foreach(HubState.cron_micro_options, lambda opt: rx.select.item(opt["label"], value=opt["id"])),
                                                style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}", "zIndex": "9999"},
                                                position="popper",
                                            ),
                                            value=HubState.cron_edit_parent_id,
                                            on_change=HubState.set_cron_edit_parent_id,
                                        ),
                                        rx.text("Crie uma micro-atividade primeiro", font_size="11px", color=S.TEXT_MUTED, font_style="italic"),
                                    ),
                                ),
                                spacing="1", flex="1",
                            ),
                        ),
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.text("Peso %", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.text("(importância relativa)", font_size="10px", color=S.TEXT_MUTED, font_style="italic"),
                            spacing="1", align="center",
                        ),
                        rx.el.input(
                            type="number",
                            default_value=HubState.cron_edit_peso,
                            on_blur=HubState.set_cron_edit_peso,
                            min="1", max="100", step="1",
                            style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":S.COPPER,"padding":"8px 10px","fontSize":"14px","width":"90px","outline":"none","fontWeight":"700","fontFamily":S.FONT_MONO},
                        ),
                        spacing="1",
                        min_width="120px",
                    ),
                    gap="12px", flex_wrap="wrap", align="start",
                ),
                # Row 4b: Progresso + Status + Tipo Medição + Crítico
                rx.flex(
                    rx.vstack(rx.text("Conclusão %", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                              rx.el.input(type="number", value=HubState.cron_edit_pct, on_change=HubState.set_cron_edit_pct, min="0", max="100", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"100px","outline":"none"}), spacing="1"),
                    rx.vstack(
                        rx.text("Status", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.select.root(
                            rx.select.trigger(style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","fontSize":"13px","width":"160px","outline":"none"}),
                            rx.select.content(
                                rx.select.item("Não iniciada", value="nao_iniciada"),
                                rx.select.item("Pronta para iniciar", value="pronta_iniciar"),
                                rx.select.item("Em execução", value="em_execucao"),
                                rx.select.item("Concluída", value="concluida"),
                                rx.select.item("Atrasada", value="atrasada"),
                                rx.select.item("Paralisada", value="paralisada"),
                                rx.select.item("Bloqueada", value="bloqueada"),
                                rx.select.item("Cancelada", value="cancelada"),
                                style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}", "zIndex": "9999"},
                                position="popper",
                            ),
                            value=HubState.cron_edit_status_atividade,
                            on_change=HubState.set_cron_edit_status_atividade,
                        ),
                        spacing="1",
                    ),
                    rx.vstack(
                        rx.text("Tipo Medição", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.select.root(
                            rx.select.trigger(style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","fontSize":"13px","width":"140px","outline":"none"}),
                            rx.select.content(
                                rx.select.item("Quantidade", value="quantidade"),
                                rx.select.item("Percentual", value="percentual"),
                                rx.select.item("Marco", value="marco"),
                                style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}", "zIndex": "9999"},
                                position="popper",
                            ),
                            value=HubState.cron_edit_tipo_medicao,
                            on_change=HubState.set_cron_edit_tipo_medicao,
                        ),
                        spacing="1",
                    ),
                    rx.hstack(
                        rx.checkbox(checked=HubState.cron_edit_critico, on_change=HubState.toggle_cron_edit_critico, color_scheme="red"),
                        rx.text("Crítico", font_size="12px", color=rx.cond(HubState.cron_edit_critico, S.DANGER, S.TEXT_MUTED)),
                        spacing="2", align="center", margin_top="18px",
                    ),
                    gap="12px", flex_wrap="wrap", align="end",
                ),
                # Row 5: Tipo de Dependência — 3 modos de negócio
                rx.vstack(
                    rx.text("Tipo de Dependência", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    # Mode selector — 3 pill buttons
                    rx.hstack(
                        rx.box(
                            rx.text("Sem dependência", font_size="11px", font_weight="600"),
                            padding="6px 12px",
                            border_radius=S.R_CONTROL,
                            cursor="pointer",
                            bg=rx.cond(HubState.cron_edit_dep_tipo == "sem_dep", S.COPPER, "rgba(255,255,255,0.04)"),
                            border=rx.cond(HubState.cron_edit_dep_tipo == "sem_dep", f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
                            color=rx.cond(HubState.cron_edit_dep_tipo == "sem_dep", S.BG_VOID, S.TEXT_MUTED),
                            on_click=HubState.set_cron_edit_dep_tipo("sem_dep"),
                            transition="all 0.15s ease",
                        ),
                        rx.box(
                            rx.text("Depende de data", font_size="11px", font_weight="600"),
                            padding="6px 12px",
                            border_radius=S.R_CONTROL,
                            cursor="pointer",
                            bg=rx.cond(HubState.cron_edit_dep_tipo == "tradicional", S.PATINA, "rgba(255,255,255,0.04)"),
                            border=rx.cond(HubState.cron_edit_dep_tipo == "tradicional", f"1px solid {S.PATINA}", f"1px solid {S.BORDER_SUBTLE}"),
                            color=rx.cond(HubState.cron_edit_dep_tipo == "tradicional", "white", S.TEXT_MUTED),
                            on_click=HubState.set_cron_edit_dep_tipo("tradicional"),
                            transition="all 0.15s ease",
                        ),
                        rx.box(
                            rx.text("Depende de progresso", font_size="11px", font_weight="600"),
                            padding="6px 12px",
                            border_radius=S.R_CONTROL,
                            cursor="pointer",
                            bg=rx.cond(HubState.cron_edit_dep_tipo == "progresso", S.WARNING, "rgba(255,255,255,0.04)"),
                            border=rx.cond(HubState.cron_edit_dep_tipo == "progresso", f"1px solid {S.WARNING}", f"1px solid {S.BORDER_SUBTLE}"),
                            color=rx.cond(HubState.cron_edit_dep_tipo == "progresso", S.BG_VOID, S.TEXT_MUTED),
                            on_click=HubState.set_cron_edit_dep_tipo("progresso"),
                            transition="all 0.15s ease",
                        ),
                        spacing="2", flex_wrap="wrap",
                    ),
                    # Predecessor selector — shown only when not sem_dep
                    rx.cond(
                        HubState.cron_edit_dep_tipo != "sem_dep",
                        rx.vstack(
                            rx.cond(
                                HubState.cron_edit_dep_tipo == "tradicional",
                                rx.text(
                                    "A data de início desta atividade será definida com base no término da predecessora.",
                                    font_size="10px", color=S.TEXT_MUTED, font_style="italic",
                                ),
                                rx.text(
                                    "O avanço desta atividade ficará limitado ao percentual concluído da predecessora (regra 1:1).",
                                    font_size="10px", color=S.WARNING, font_style="italic",
                                ),
                            ),
                            rx.cond(
                                HubState.cron_dep_options.length() > 0,
                                rx.select.root(
                                    rx.select.trigger(
                                        placeholder="— Selecionar atividade predecessora —",
                                        style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "padding": "8px 10px", "fontSize": "13px", "width": "100%", "outline": "none"},
                                    ),
                                    rx.select.content(
                                        rx.select.item("— Sem predecessora —", value="__none__"),
                                        rx.foreach(
                                            HubState.cron_dep_options,
                                            lambda opt: rx.select.item(opt["label"], value=opt["id"]),
                                        ),
                                        style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}", "zIndex": "9999"},
                                        position="popper",
                                    ),
                                    value=rx.cond(HubState.cron_edit_dependencia_id == "", "__none__", HubState.cron_edit_dependencia_id),
                                    on_change=HubState.set_cron_edit_dependencia_id,
                                ),
                                rx.text("Nenhuma atividade criada ainda", font_size="11px", color=S.TEXT_MUTED, font_style="italic"),
                            ),
                            spacing="2", width="100%",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2", width="100%",
                ),
                # Row 6: Qtd Total + Unidade — adaptive by tipo_medicao
                # Marco: "Feito / Não feito" toggle (total_qty=1, unidade="marco")
                # Percentual: total_qty hidden (conclusao_pct is the measure), unidade hidden
                # Quantidade: number input + unit dropdown
                rx.cond(
                    HubState.cron_edit_tipo_medicao == "marco",
                    rx.box(
                        rx.text(
                            "Marco — esta atividade é verificada como concluída (Sim/Não). Use Conclusão % acima para marcar 100% quando feita.",
                            font_size="11px", color=S.TEXT_MUTED, font_style="italic",
                        ),
                        padding="8px 12px",
                        border_radius=S.R_CONTROL,
                        bg="rgba(201,139,42,0.06)",
                        border=f"1px solid rgba(201,139,42,0.2)",
                        width="100%",
                    ),
                    rx.cond(
                        HubState.cron_edit_tipo_medicao == "percentual",
                        rx.box(
                            rx.text(
                                "Percentual — o avanço é medido diretamente em % de 0 a 100. Use o campo Conclusão % acima.",
                                font_size="11px", color=S.TEXT_MUTED, font_style="italic",
                            ),
                            padding="8px 12px",
                            border_radius=S.R_CONTROL,
                            bg="rgba(42,157,143,0.06)",
                            border=f"1px solid rgba(42,157,143,0.2)",
                            width="100%",
                        ),
                        # quantidade (default)
                        rx.flex(
                            rx.vstack(
                                rx.hstack(
                                    rx.text("Qtd Total", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                    rx.text("(0 = sem rastreio)", font_size="10px", color=S.TEXT_MUTED, font_style="italic"),
                                    spacing="1", align="center",
                                ),
                                rx.el.input(
                                    type="number",
                                    default_value=HubState.cron_edit_total_qty,
                                    on_blur=HubState.set_cron_edit_total_qty,
                                    placeholder="Ex: 1456",
                                    min="0",
                                    style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"120px","outline":"none"},
                                ),
                                spacing="1",
                            ),
                            rx.vstack(
                                rx.text("Unidade", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                rx.select.root(
                                    rx.select.trigger(
                                        placeholder="Selecionar...",
                                        style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "fontSize": "13px", "width": "140px", "outline": "none"},
                                    ),
                                    rx.select.content(
                                        rx.select.item("und", value="und"),
                                        rx.select.item("m",   value="m"),
                                        rx.select.item("m²",  value="m²"),
                                        rx.select.item("m³",  value="m³"),
                                        rx.select.item("kg",  value="kg"),
                                        rx.select.item("kWh", value="kWh"),
                                        rx.select.item("kW",  value="kW"),
                                        rx.select.item("kWp", value="kWp"),
                                        style={"background": S.BG_ELEVATED, "border": f"1px solid {S.BORDER_SUBTLE}", "zIndex": "9999"},
                                        position="popper",
                                    ),
                                    value=HubState.cron_edit_unidade,
                                    on_change=HubState.set_cron_edit_unidade,
                                ),
                                spacing="1",
                            ),
                            gap="12px", flex_wrap="wrap", align="start",
                        ),
                    ),
                ),
                # Row 7: Efetivo alocado planejado
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="users", size=13, color=S.COPPER),
                        rx.text("Efetivo Alocado (planejado)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.text("pessoas designadas para esta atividade", font_size="10px", color=S.TEXT_MUTED, font_style="italic"),
                        spacing="2", align="center",
                    ),
                    rx.el.input(
                        type="number",
                        default_value=HubState.cron_edit_efetivo_alocado,
                        on_blur=HubState.set_cron_edit_efetivo_alocado,
                        placeholder="Ex: 4",
                        min="0",
                        style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":S.COPPER,"padding":"8px 10px","fontSize":"14px","width":"120px","outline":"none","fontWeight":"700","fontFamily":S.FONT_MONO},
                    ),
                    spacing="1",
                ),
                rx.vstack(rx.text("Observações", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                          rx.el.textarea(default_value=HubState.cron_edit_observacoes, on_blur=HubState.set_cron_edit_observacoes, placeholder="Notas técnicas, impedimentos, contexto...", rows="3", style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"100%","outline":"none","resize":"vertical","fontFamily":S.FONT_BODY}), spacing="1", width="100%"),
                # Error
                rx.cond(HubState.cron_error != "", rx.text(HubState.cron_error, font_size="12px", color=S.DANGER)),
                # Footer
                rx.hstack(
                    rx.dialog.close(rx.button("Cancelar", variant="ghost", size="2", color=S.TEXT_MUTED, cursor="pointer", on_click=HubState.close_cron_dialog)),
                    rx.button(
                        rx.cond(
                            HubState.cron_saving,
                            rx.spinner(size="2"),
                            rx.cond(
                                HubState.cron_pending_review_id != "",
                                rx.hstack(rx.icon(tag="check-circle", size=13), rx.text("Aprovar"), spacing="1", align="center"),
                                rx.hstack(rx.icon(tag="save", size=13), rx.text("Salvar"), spacing="1", align="center"),
                            ),
                        ),
                        on_click=HubState.save_cron_activity, size="2", disabled=HubState.cron_saving,
                        style=rx.cond(
                            HubState.cron_pending_review_id != "",
                            {"background": "#22c55e", "color": "white", "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                            {"background": S.COPPER, "color": S.BG_VOID, "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                        ),
                    ),
                    justify="end", spacing="2", width="100%", padding_top="8px",
                ),
                spacing="4", width="100%",
            ),
            bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}", border_radius=S.R_CARD,
            max_width="600px", width="95vw",
            key=HubState.cron_edit_id,
        ),
        open=HubState.cron_show_dialog,
        on_open_change=HubState.set_cron_show_dialog,
    )


def _cron_delete_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="trash-2", size=16, color=S.DANGER),
                    rx.dialog.title("Excluir Atividade", font_family=S.FONT_TECH, font_weight="700", color="var(--text-main)"),
                    spacing="2", align="center",
                ),
                rx.text("Tem certeza que deseja excluir a atividade:", font_size="13px", color=S.TEXT_MUTED),
                rx.text(HubState.cron_delete_name, font_size="13px", font_weight="700", color=S.DANGER),
                rx.text("Esta ação não pode ser desfeita.", font_size="11px", color=S.TEXT_MUTED),
                rx.hstack(
                    rx.button("Cancelar", variant="ghost", size="2", cursor="pointer", on_click=HubState.cancel_cron_delete),
                    rx.button(rx.hstack(rx.icon(tag="trash-2", size=13), rx.text("Excluir"), spacing="1"), on_click=HubState.confirm_cron_delete, size="2", style={"background": S.DANGER, "color": "white", "cursor": "pointer"}),
                    justify="end", spacing="2", width="100%",
                ),
                spacing="3", width="100%",
            ),
            bg=S.BG_ELEVATED, border=f"1px solid rgba(239,68,68,0.3)", border_radius=S.R_CARD, max_width="420px", width="90vw",
        ),
        open=HubState.cron_show_delete,
    )


def _gantt_bar(item: dict) -> rx.Component:
    """Single Gantt row: label + date-positioned bar with progress fill + badges."""
    # Hierarchy indent: sub = 24px, micro = 12px, macro = 0
    row_indent = rx.cond(
        item["nivel"] == "sub", "24px",
        rx.cond(item["nivel"] == "micro", "12px", "0px"),
    )
    # Nivel badge: only for micro and sub
    nivel_badge = rx.cond(
        item["nivel"] == "sub",
        rx.box(
            rx.text("SUB", font_size="7px", font_weight="800", color="#8B5CF6", font_family=S.FONT_TECH, letter_spacing="0.06em"),
            padding="1px 4px", border_radius="2px",
            border="1px solid rgba(139,92,246,0.5)", bg="rgba(139,92,246,0.08)",
            flex_shrink="0",
        ),
        rx.cond(
            item["nivel"] == "micro",
            rx.box(
                rx.text("MICRO", font_size="7px", font_weight="800", color=S.PATINA, font_family=S.FONT_TECH, letter_spacing="0.06em"),
                padding="1px 4px", border_radius="2px",
                border="1px solid rgba(42,157,143,0.5)", bg="rgba(42,157,143,0.08)",
                flex_shrink="0",
            ),
            rx.fragment(),
        ),
    )
    # Bar color: overdue → red, else activity color; sub → purple tint
    bar_color = rx.cond(
        item["gantt_overdue"] == "1", "#EF4444",
        rx.cond(item["nivel"] == "sub", "#8B5CF6", item["color"]),
    )
    progress_fill = rx.cond(
        item["conclusao_pct"] == "0",
        rx.fragment(),
        rx.box(
            height="100%",
            width=item["conclusao_pct"] + "%",
            bg=bar_color,
            border_radius="3px 0 0 3px",
            opacity="0.85",
        ),
    )
    overdue_badge = rx.cond(
        item["gantt_overdue"] == "1",
        rx.box(
            rx.text("ATRASADA", font_size="7px", font_weight="800", color="#EF4444", font_family=S.FONT_TECH, letter_spacing="0.06em"),
            padding="1px 4px", border_radius="2px",
            border="1px solid rgba(239,68,68,0.5)", bg="rgba(239,68,68,0.08)",
            flex_shrink="0",
        ),
        rx.fragment(),
    )
    critical_badge = rx.cond(
        item["critico"] == "1",
        rx.box(
            rx.text("CRÍTICO", font_size="7px", font_weight="800", color="#E89845", font_family=S.FONT_TECH, letter_spacing="0.06em"),
            padding="1px 4px", border_radius="2px",
            border="1px solid rgba(232,152,69,0.5)", bg="rgba(232,152,69,0.08)",
            flex_shrink="0",
        ),
        rx.fragment(),
    )
    dep_text = rx.cond(
        item["dependencia"] != "",
        rx.hstack(
            rx.icon(tag="link-2", size=10, color="#F97316"),
            rx.text(
                "após: ",
                font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
            ),
            rx.text(
                item["dependencia"],
                font_size="9px", color="#F97316", font_family=S.FONT_MONO, font_weight="600",
            ),
            spacing="1", align="center",
            padding="2px 6px",
            border_radius="4px",
            style={"background": "rgba(249,115,22,0.08)", "border": "1px solid rgba(249,115,22,0.2)"},
        ),
        rx.fragment(),
    )
    bar_box = rx.box(
        rx.hstack(
            # Hierarchy indent spacer
            rx.box(width=row_indent, flex_shrink="0"),
            # Label column
            rx.vstack(
                rx.hstack(
                    nivel_badge,
                    rx.text(
                        item["atividade"],
                        font_size="11px", color="rgba(255,255,255,0.85)",
                        white_space="nowrap", overflow="hidden", text_overflow="ellipsis",
                        max_width="100%",
                    ),
                    rx.hstack(overdue_badge, critical_badge, spacing="1"),
                    spacing="2", align="center", width="100%",
                ),
                rx.hstack(
                    rx.text(item["fase_macro"], font_size="9px", color=item["color"], font_weight="600"),
                    rx.text("·", font_size="9px", color=S.TEXT_MUTED),
                    rx.text(item["responsavel"], font_size="9px", color=S.TEXT_MUTED),
                    dep_text,
                    spacing="1", align="center",
                ),
                spacing="0", align_items="flex-start", width="240px", flex_shrink="0",
            ),
            # Timeline track
            rx.box(
                # Outer track
                rx.box(
                    # Positioned bar container
                    rx.box(
                        # Background track
                        rx.box(
                            # Progress fill
                            progress_fill,
                            height="100%",
                            bg="rgba(255,255,255,0.06)",
                            border_radius="3px",
                            overflow="hidden",
                            position="relative",
                        ),
                        position="absolute",
                        left=item["gantt_left_pct"] + "%",
                        width=item["gantt_width_pct"] + "%",
                        height="22px",
                        top="0",
                        border=rx.cond(
                            item["gantt_overdue"] == "1",
                            "1px solid rgba(239,68,68,0.4)",
                            f"1px solid {item['color']}44",
                        ),
                        border_radius="3px",
                        min_width="8px",
                    ),
                    # Forecast bar (EAC) — purple dashed, only when gantt_forecast_width is set
                    rx.cond(
                        item["gantt_forecast_width"] != "",
                        rx.box(
                            position="absolute",
                            left=item["gantt_forecast_left"] + "%",
                            width=item["gantt_forecast_width"] + "%",
                            height="4px",
                            top="28px",
                            bg="transparent",
                            border="1px dashed rgba(168,85,247,0.6)",
                            border_radius="2px",
                            min_width="4px",
                        ),
                    ),
                    # Today line — gold vertical line
                    rx.cond(
                        (item["gantt_today_pct"] != "") & (item["gantt_today_pct"] != "0") & (item["gantt_today_pct"] != "100"),
                        rx.box(
                            position="absolute",
                            left=item["gantt_today_pct"] + "%",
                            top="-4px",
                            height="30px",
                            width="2px",
                            bg="#C98A2A",
                            border_radius="1px",
                            z_index="10",
                            box_shadow="0 0 6px rgba(201,138,42,0.6)",
                        ),
                    ),
                    position="relative", height="22px", width="100%",
                ),
                flex="1", overflow="hidden",
            ),
            # End date
            rx.text(
                item["termino_previsto"],
                font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                white_space="nowrap", flex_shrink="0", width="65px", text_align="right",
            ),
            spacing="3", align="center", width="100%",
        ),
        padding="6px 0",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}22",
        _last={"borderBottom": "none"},
        _hover={"background": "rgba(255,255,255,0.02)", "borderRadius": "4px"},
        cursor="default",
    )
    return rx.hover_card.root(
        rx.hover_card.trigger(bar_box, as_child=True),
        gantt_hover_content(item),
        open_delay=200,
        close_delay=100,
    )


def _gantt_premium() -> rx.Component:
    """Premium scrollable Gantt chart with date-positioned bars, weather badges, IA button."""
    return rx.box(
        rx.vstack(
            # ── Header ─────────────────────────────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="gantt-chart", size=14, color=S.COPPER),
                    rx.text("GANTT", font_family=S.FONT_TECH, font_size="11px", font_weight="700", color=S.COPPER, letter_spacing="0.10em"),
                    rx.box(width="1px", height="14px", bg=S.BORDER_SUBTLE),
                    rx.text(HubState.gantt_date_range["start"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.icon(tag="arrow-right", size=10, color=S.TEXT_MUTED),
                    rx.text(HubState.gantt_date_range["end"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="2", align="center",
                ),
                # Legend
                rx.hstack(
                    rx.box(width="16px", height="4px", bg=S.COPPER, border_radius="2px"),
                    rx.text("Programado", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.box(width="16px", height="4px", bg="transparent",
                           border="1px dashed rgba(168,85,247,0.7)", border_radius="2px"),
                    rx.text("Previsto (EAC)", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.box(width="8px", height="8px", bg="#EF4444", border_radius="50%"),
                    rx.text("Atrasada", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="2", align="center",
                    display=rx.breakpoints(initial="none", md="flex"),
                ),
                rx.spacer(),
                # IA Climate Analysis button
                rx.cond(
                    HubState.cron_climate_loading,
                    rx.hstack(
                        rx.spinner(size="1"),
                        rx.text("Analisando...", font_size="11px", color=S.TEXT_MUTED),
                        spacing="2", align="center",
                    ),
                    rx.button(
                        rx.hstack(
                            rx.icon(tag="cloud-rain", size=12),
                            rx.text("Analisar Impacto Climático", font_size="11px"),
                            spacing="1", align="center",
                        ),
                        on_click=HubState.analyze_climate_impact,
                        size="1", variant="soft",
                        style={
                            "background": "rgba(42,157,143,0.12)",
                            "border": "1px solid rgba(42,157,143,0.3)",
                            "color": S.PATINA,
                            "cursor": "pointer",
                            "fontFamily": S.FONT_TECH,
                            "fontWeight": "600",
                        },
                    ),
                ),
                width="100%", align="center",
            ),
            # ── Legend ─────────────────────────────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.box(width="24px", height="8px", bg=S.COPPER, border_radius="2px", opacity="0.7"),
                    rx.text("Progresso", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="center",
                ),
                rx.hstack(
                    rx.box(width="24px", height="8px", bg="#EF4444", border_radius="2px", opacity="0.7"),
                    rx.text("Atrasada", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="center",
                ),
                rx.hstack(
                    rx.box(width="24px", height="8px", bg="rgba(255,255,255,0.06)", border="1px solid rgba(255,255,255,0.15)", border_radius="2px"),
                    rx.text("Planejado", font_size="9px", color=S.TEXT_MUTED),
                    spacing="1", align="center",
                ),
                spacing="4", flex_wrap="wrap",
            ),
            # ── Bars ───────────────────────────────────────────────────────────
            rx.box(
                rx.foreach(HubState.gantt_rows, _gantt_bar),
                width="100%",
            ),
            spacing="3", width="100%",
        ),
        padding="16px 20px", border_radius=S.R_CARD,
        border=f"1px solid {S.BORDER_SUBTLE}", bg="rgba(255,255,255,0.02)",
        width="100%",
    )


def _climate_analysis_panel() -> rx.Component:
    """Displays the IA climate impact analysis result."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="cloud-rain", size=14, color=S.PATINA),
                rx.text("ANÁLISE DE IMPACTO CLIMÁTICO", font_family=S.FONT_TECH, font_size="11px", font_weight="700", color=S.PATINA, letter_spacing="0.08em"),
                rx.spacer(),
                rx.icon(
                    tag="x", size=14, color=S.TEXT_MUTED, cursor="pointer",
                    on_click=HubState.clear_climate_analysis,
                    _hover={"color": "white"},
                ),
                width="100%", align="center",
            ),
            rx.box(
                rx.text(
                    HubState.cron_climate_analysis,
                    font_size="13px", color="rgba(255,255,255,0.85)",
                    line_height="1.65", white_space="pre-wrap",
                ),
                padding="12px 16px",
                border_radius=S.R_CONTROL,
                bg="rgba(42,157,143,0.06)",
                border=f"1px solid rgba(42,157,143,0.15)",
                width="100%",
            ),
            rx.hstack(
                rx.icon(tag="bot", size=10, color=S.TEXT_MUTED),
                rx.text("Gerado por Bomtempo Intelligence · baseado na previsão atual do tempo", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                spacing="1", align="center",
            ),
            spacing="3", width="100%",
        ),
        padding="16px 20px", border_radius=S.R_CARD,
        border=f"1px solid rgba(42,157,143,0.2)", bg="rgba(42,157,143,0.04)",
        width="100%",
        id="climate-analysis-panel",
    )


def _tab_cronograma() -> rx.Component:
    return rx.vstack(
        _cron_import_dialog(),
        _cron_edit_dialog(),
        _cron_delete_dialog(),
        # ── Stats strip ──────────────────────────────────────────────────────────
        rx.hstack(
            _cron_stat_badge("Total", HubState.cron_stats["total"], S.COPPER),
            rx.box(width="1px", height="40px", bg=S.BORDER_SUBTLE),
            _cron_stat_badge("Concluídas", HubState.cron_stats["done"], S.PATINA),
            rx.box(width="1px", height="40px", bg=S.BORDER_SUBTLE),
            _cron_stat_badge("Críticas", HubState.cron_stats["critical"], S.DANGER),
            rx.box(width="1px", height="40px", bg=S.BORDER_SUBTLE),
            _cron_stat_badge("Progresso", HubState.cron_stats["pct"] + "%", "#A855F7"),
            rx.spacer(),
            rx.upload(
                rx.button(
                    rx.hstack(
                        rx.cond(HubState.cron_import_loading, rx.spinner(size="1"), rx.icon(tag="sparkles", size=13)),
                        rx.text("Importar via IA"),
                        spacing="1", align="center",
                    ),
                    size="2",
                    style={"background": "rgba(168,85,247,0.15)", "color": "#A855F7", "border": "1px solid rgba(168,85,247,0.4)", "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                    disabled=HubState.cron_import_loading,
                ),
                id="cron_import_upload",
                accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xls": "application/vnd.ms-excel", ".csv": "text/csv", ".pdf": "application/pdf"},
                max_files=1,
                on_drop=HubState.import_cronograma_ia(rx.upload_files(upload_id="cron_import_upload")),
                border="0",
                padding="0",
            ),
            rx.button(
                rx.hstack(rx.icon(tag="refresh-cw", size=13), rx.text("Recalcular Datas"), spacing="1", align="center"),
                on_click=HubState.recalculate_cron_dates,
                size="2",
                title="Recalcula as datas de término com base nos dias úteis configurados no projeto",
                style={"background": "rgba(42,157,143,0.15)", "color": S.PATINA, "border": f"1px solid rgba(42,157,143,0.4)", "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
            ),
            rx.button(
                rx.hstack(rx.icon(tag="plus", size=13), rx.text("Nova Atividade"), spacing="1", align="center"),
                on_click=HubState.open_cron_new_root, size="2",
                style={"background": S.COPPER, "color": S.BG_VOID, "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
            ),
            padding="14px 20px", border_radius=S.R_CARD,
            bg="rgba(255,255,255,0.03)", border=f"1px solid {S.BORDER_SUBTLE}",
            width="100%", align="center",
        ),
        # ── Toolbar: search + filters ─────────────────────────────────────────
        rx.hstack(
            rx.hstack(
                rx.icon(tag="search", size=14, color=S.TEXT_MUTED),
                rx.el.input(
                    default_value=HubState.cron_search,
                    on_change=HubState.set_cron_search_input,
                    on_blur=HubState.commit_cron_search,
                    on_key_down=HubState.handle_cron_search_key,
                    placeholder="Buscar atividade, responsável, fase...",
                    style={"background": "transparent", "border": "none", "color": "white", "fontSize": "13px", "outline": "none", "flex": "1", "minWidth": "180px"},
                ),
                padding="8px 12px", border_radius=S.R_CONTROL,
                border=f"1px solid {S.BORDER_SUBTLE}",
                bg="rgba(255,255,255,0.02)", flex="1", align="center",
            ),
            rx.hstack(
                rx.box(
                    rx.text("Todos", font_size="10px", font_weight="700", color=rx.cond(HubState.cron_fase_filter == "", S.BG_VOID, S.TEXT_MUTED), white_space="nowrap"),
                    padding="3px 10px", border_radius="4px", cursor="pointer",
                    bg=rx.cond(HubState.cron_fase_filter == "", S.COPPER, "rgba(255,255,255,0.04)"),
                    border=rx.cond(HubState.cron_fase_filter == "", f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
                    on_click=HubState.set_cron_fase_filter(""),
                    _hover={"bg": rx.cond(HubState.cron_fase_filter == "", S.COPPER, "rgba(255,255,255,0.07)")},
                    transition="all 0.15s ease",
                ),
                rx.foreach(HubState.cron_unique_fases, _cron_fase_pill),
                spacing="1", flex_wrap="wrap", align="center",
            ),
            rx.hstack(
                rx.checkbox(checked=HubState.cron_show_only_critical, on_change=lambda _: HubState.toggle_cron_critical(), color_scheme="red"),
                rx.text("Só críticas", font_size="11px", color=rx.cond(HubState.cron_show_only_critical, S.DANGER, S.TEXT_MUTED)),
                spacing="2", align="center",
            ),
            width="100%", align="center", flex_wrap="wrap", gap="10px",
        ),
        # ── Pending approval panel (gestor only) ─────────────────────────────
        rx.cond(
            HubState.cron_pending_rows.length() > 0,
            rx.box(
                rx.hstack(
                    rx.icon(tag="clock", size=14, color="#E89845"),
                    rx.text("ATIVIDADES PENDENTES DE APROVAÇÃO", font_size="11px", font_weight="700", color="#E89845", font_family=S.FONT_TECH, letter_spacing="0.06em"),
                    rx.text(HubState.cron_pending_rows.length(), font_size="10px", color="#E89845", font_family=S.FONT_MONO),
                    spacing="2", align="center",
                ),
                rx.vstack(
                    rx.foreach(
                        HubState.cron_pending_rows,
                        lambda row: rx.hstack(
                            rx.box(width="3px", height="100%", bg="#E89845", border_radius="2px", align_self="stretch", flex_shrink="0"),
                            rx.vstack(
                                rx.text(row["atividade"], font_size="12px", font_weight="600", color="white", font_family=S.FONT_TECH),
                                rx.text(row["responsavel"] + " · " + row["fase_macro"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                spacing="0",
                                flex="1",
                                min_width="0",
                            ),
                            rx.spacer(),
                            rx.hstack(
                                rx.button(
                                    rx.hstack(rx.icon(tag="clipboard-pen", size=11), rx.text("Revisar"), spacing="1"),
                                    on_click=HubState.open_pending_review(row["id"]),
                                    size="1", style={"background": "#E89845", "color": "#0e1a17", "cursor": "pointer", "fontWeight": "700"},
                                    disabled=HubState.cron_approve_loading,
                                ),
                                rx.button(
                                    rx.hstack(rx.icon(tag="x", size=11), rx.text("Reprovar"), spacing="1"),
                                    on_click=HubState.reject_pending_activity(row["id"]),
                                    size="1", variant="ghost", style={"color": S.DANGER, "cursor": "pointer", "border": f"1px solid {S.DANGER}"},
                                    disabled=HubState.cron_approve_loading,
                                ),
                                spacing="2",
                                flex_shrink="0",
                            ),
                            padding="8px 12px", border_radius=S.R_CONTROL,
                            bg="rgba(232,152,69,0.05)", border="1px solid rgba(232,152,69,0.2)",
                            width="100%", align="center", spacing="3",
                        ),
                    ),
                    spacing="2", width="100%", padding_top="8px",
                ),
                padding="14px 16px", border_radius=S.R_CARD,
                border="1px solid rgba(232,152,69,0.3)", bg="rgba(232,152,69,0.04)",
                width="100%",
            ),
        ),
        # ── Activity list ─────────────────────────────────────────────────────
        rx.cond(
            HubState.cron_loading,
            rx.center(rx.vstack(rx.spinner(size="3"), rx.text("Carregando atividades...", font_size="12px", color=S.TEXT_MUTED), spacing="2", align="center"), padding="60px", width="100%", min_height="200px"),
                rx.cond(
                HubState.cron_display_rows.length() == 0,
                rx.box(
                    rx.vstack(
                        rx.icon(tag="calendar-off", size=48, color=S.BORDER_SUBTLE),
                        rx.text("Nenhuma atividade encontrada", font_size="15px", font_weight="600", color=S.TEXT_MUTED),
                        rx.text("Importe via IA ou crie manualmente para comecar", font_size="12px", color=S.TEXT_MUTED, opacity="0.7", text_align="center"),
                        rx.hstack(
                            rx.upload(
                                rx.button(
                                    rx.hstack(rx.icon(tag="sparkles", size=13), rx.text("Importar via IA"), spacing="1"),
                                    size="2",
                                    style={"cursor": "pointer", "background": "rgba(168,85,247,0.12)", "color": "#a855f7", "border": "1px solid rgba(168,85,247,0.3)"},
                                ),
                                id="cron_import_upload_empty",
                                accept={".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xls": "application/vnd.ms-excel", ".csv": "text/csv", ".pdf": "application/pdf"},
                                max_files=1,
                                on_drop=HubState.import_cronograma_ia(rx.upload_files(upload_id="cron_import_upload_empty")),
                                border="0", padding="0",
                            ),
                            rx.button(
                                rx.hstack(rx.icon(tag="plus", size=13), rx.text("Nova Atividade"), spacing="1"),
                                on_click=HubState.open_cron_new_root, size="2", variant="soft",
                                style={"cursor": "pointer"},
                            ),
                            spacing="3",
                        ),
                        spacing="4", align="center",
                    ),
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    width="100%",
                    min_height="400px",
                ),
                rx.vstack(
                    rx.foreach(HubState.cron_display_rows, _cron_display_row),
                    spacing="1", width="100%",
                    class_name="cron-activity-list",
                ),
            ),
        ),
        # ── KPI Dashboard: Previsto vs Realizado ──────────────────────────────
        _cron_kpi_detail_dialog(),
        _cron_kpi_panel(),
        # ── Forecast / Produtividade por atividade ────────────────────────────
        _cron_forecast_panel(),
        # ── Gantt Premium ─────────────────────────────────────────────────────
        rx.cond(
            HubState.cron_rows.length() > 0,
            _gantt_premium(),
        ),
        # ── IA Climate Analysis Panel ─────────────────────────────────────────
        rx.cond(
            HubState.cron_climate_analysis != "",
            _climate_analysis_panel(),
        ),
        spacing="4", width="100%", class_name="animate-fade-in",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — AUDITORIA DE IMAGENS
# ══════════════════════════════════════════════════════════════════════════════


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to 'R, G, B' string for rgba()."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r}, {g}, {b}"
    return "255, 255, 255"


def _audit_thumb(img: dict) -> rx.Component:
    return rx.box(
        rx.box(
            rx.image(src=img["url"], width="100%", height="100%", object_fit="cover", border_radius="4px"),
            position="absolute", inset="0", overflow="hidden", border_radius="6px",
        ),
        rx.box(
            rx.vstack(
                rx.text(img["legenda"], font_size="10px", color="white", font_family=S.FONT_BODY, line_height="1.3", overflow="hidden", text_overflow="ellipsis", display="-webkit-box", style={"WebkitLineClamp": "2", "WebkitBoxOrient": "vertical"}),
                rx.hstack(
                    rx.icon(tag="calendar", size=9, color="rgba(255,255,255,0.6)"),
                    rx.text(img["data_captura"], font_size="9px", color="rgba(255,255,255,0.6)", font_family=S.FONT_MONO),
                    spacing="1", align="center",
                ),
                spacing="1",
            ),
            position="absolute", bottom="0", left="0", right="0",
            background="linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 100%)",
            padding="8px", border_radius="0 0 6px 6px",
        ),
        # Delete button (top-right)
        rx.box(
            rx.icon(tag="trash-2", size=11, color="white"),
            position="absolute", top="6px", right="6px",
            bg="rgba(239,68,68,0.7)", border_radius="4px", padding="3px",
            cursor="pointer", opacity="0",
            on_click=HubState.delete_audit_image(img["id"]),
            class_name="audit-thumb-delete",
        ),
        position="relative", width="140px", height="105px", flex_shrink="0",
        border_radius="6px", overflow="hidden", cursor="pointer",
        border=f"1px solid {S.BORDER_SUBTLE}",
        on_click=HubState.open_lightbox(img["id"]),
        _hover={"border_color": "rgba(255,255,255,0.25)", "& .audit-thumb-delete": {"opacity": "1"}},
        transition="all 0.2s ease",
    )


def _audit_lightbox() -> rx.Component:
    return rx.cond(
        HubState.audit_lightbox_open,
        rx.box(
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.spacer(),
                        rx.box(
                            rx.icon(tag="x", size=18, color="white"),
                            on_click=HubState.close_lightbox,
                            cursor="pointer", padding="6px",
                            bg="rgba(255,255,255,0.1)", border_radius="6px",
                            _hover={"bg": "rgba(255,255,255,0.2)"},
                        ),
                        width="100%",
                    ),
                    rx.image(
                        src=HubState.audit_lightbox_url,
                        max_height="60vh", max_width="100%", object_fit="contain", border_radius="8px",
                    ),
                    rx.vstack(
                        rx.text(HubState.audit_lightbox_legenda, font_size="14px", color="white", font_family=S.FONT_BODY, text_align="center"),
                        rx.hstack(
                            rx.icon(tag="calendar", size=12, color="rgba(255,255,255,0.5)"),
                            rx.text(HubState.audit_lightbox_data, font_size="11px", color="rgba(255,255,255,0.5)", font_family=S.FONT_MONO),
                            rx.text("·", font_size="11px", color="rgba(255,255,255,0.3)"),
                            rx.icon(tag="user", size=12, color="rgba(255,255,255,0.5)"),
                            rx.text(HubState.audit_lightbox_autor, font_size="11px", color="rgba(255,255,255,0.5)", font_family=S.FONT_MONO),
                            spacing="2", align="center", justify="center",
                        ),
                        spacing="2", align="center",
                    ),
                    spacing="4", align="center", padding="20px", max_width="800px", width="90vw",
                ),
                bg="rgba(10,18,16,0.97)", border=f"1px solid {S.BORDER_SUBTLE}", border_radius=S.R_CARD,
            ),
            position="fixed", inset="0", bg="rgba(0,0,0,0.85)", display="flex",
            align_items="center", justify_content="center", z_index="99999",
            padding_top="64px",
            on_click=HubState.close_lightbox,
        ),
    )


def _audit_upload_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="upload", size=14, color=S.COPPER),
                    rx.dialog.title("Adicionar Imagem", font_family=S.FONT_TECH, font_weight="700", color="var(--text-main)"),
                    rx.spacer(),
                    rx.dialog.close(rx.icon_button(rx.icon(tag="x", size=12), size="1", variant="ghost", cursor="pointer")),
                    align="center", width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                rx.vstack(
                    rx.text("URL da Imagem *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.el.input(
                        default_value=HubState.audit_upload_url, on_blur=HubState.set_audit_upload_url,
                        placeholder="https://... ou URL do Supabase Storage",
                        style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"100%","outline":"none"},
                    ),
                    spacing="1", width="100%",
                ),
                rx.vstack(
                    rx.text("Legenda", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.el.input(
                        default_value=HubState.audit_upload_legenda, on_blur=HubState.set_audit_upload_legenda,
                        placeholder="Descrição da imagem...",
                        style={"background":"rgba(14,26,23,0.8)","border":f"1px solid {S.BORDER_SUBTLE}","borderRadius":S.R_CONTROL,"color":"white","padding":"8px 10px","fontSize":"13px","width":"100%","outline":"none"},
                    ),
                    spacing="1", width="100%",
                ),
                rx.cond(HubState.audit_upload_error != "", rx.text(HubState.audit_upload_error, font_size="12px", color=S.DANGER)),
                rx.hstack(
                    rx.dialog.close(rx.button("Cancelar", variant="ghost", size="2", cursor="pointer", on_click=HubState.close_audit_upload)),
                    rx.button(
                        rx.cond(HubState.audit_uploading, rx.spinner(size="2"), rx.hstack(rx.icon(tag="upload", size=13), rx.text("Salvar"), spacing="1")),
                        on_click=HubState.save_audit_image, size="2", disabled=HubState.audit_uploading,
                        style={"background": S.COPPER, "color": S.BG_VOID, "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                    ),
                    justify="end", spacing="2", width="100%",
                ),
                spacing="4", width="100%",
            ),
            bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}", border_radius=S.R_CARD, max_width="480px", width="90vw",
        ),
        open=HubState.audit_show_upload,
    )


def _audit_bolsao_card(cat: dict) -> rx.Component:
    slug = cat["slug"]
    label = cat["label"]
    icon_tag = cat["icon"]
    color = cat["color"]
    count = HubState.audit_category_counts[slug]
    is_open = HubState.audit_open_category == slug
    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon_tag, size=18, color=color),
                    width="36px", height="36px", border_radius="8px",
                    bg="rgba(255,255,255,0.06)",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    display="flex", align_items="center", justify_content="center", flex_shrink="0",
                ),
                rx.vstack(
                    rx.text(label, font_family=S.FONT_TECH, font_size="13px", font_weight="700", color="var(--text-main)", letter_spacing="0.02em"),
                    rx.hstack(
                        rx.text(count, font_size="11px", font_weight="700", color=color),
                        rx.text("imagens", font_size="11px", color=S.TEXT_MUTED),
                        spacing="1", align="center",
                    ),
                    spacing="0", align="start",
                ),
                rx.spacer(),
                rx.icon(tag=rx.cond(is_open, "chevron-up", "chevron-down"), size=14, color=S.TEXT_MUTED),
                align="center", width="100%",
            ),
            # Image grid (visible when open)
            rx.cond(
                is_open,
                rx.vstack(
                    rx.divider(border_color=S.BORDER_SUBTLE),
                    rx.cond(
                        HubState.audit_open_images.length() == 0,
                        rx.center(
                            rx.vstack(
                                rx.icon(tag="image-off", size=24, color=S.BORDER_SUBTLE),
                                rx.text("Nenhuma imagem neste bolsão", font_size="12px", color=S.TEXT_MUTED),
                                spacing="2", align="center",
                            ), padding="20px",
                        ),
                        rx.box(
                            rx.foreach(HubState.audit_open_images, _audit_thumb),
                            display="flex", flex_wrap="wrap", gap="10px",
                        ),
                    ),
                    rx.button(
                        rx.hstack(rx.icon(tag="plus", size=12), rx.text("Adicionar Imagem"), spacing="1"),
                        on_click=HubState.open_audit_upload(slug), size="1", variant="ghost",
                        style={"color": color, "cursor": "pointer", "border": f"1px solid {S.BORDER_SUBTLE}"},
                    ),
                    spacing="3", width="100%",
                ),
            ),
            spacing="3", width="100%",
        ),
        padding="16px 20px", border_radius=S.R_CARD,
        border=rx.cond(is_open, f"1px solid {S.BORDER_ACCENT}", f"1px solid {S.BORDER_SUBTLE}"),
        bg=rx.cond(is_open, "rgba(255,255,255,0.03)", "rgba(255,255,255,0.02)"),
        cursor="pointer", on_click=HubState.open_audit_category(slug),
        _hover={"border_color": S.BORDER_ACCENT, "bg": "rgba(255,255,255,0.03)"},
        transition="all 0.2s ease", width="100%",
    )


def _tab_auditoria() -> rx.Component:
    return rx.vstack(
        _audit_lightbox(),
        _audit_upload_dialog(),
        # Header
        rx.hstack(
            rx.hstack(
                rx.icon(tag="folder-open", size=16, color=S.COPPER),
                rx.text("GALERIA DE CAMPO", font_family=S.FONT_TECH, font_size="1rem", font_weight="700", color="var(--text-main)", letter_spacing="0.04em"),
                spacing="2", align="center",
            ),
            rx.spacer(),
            rx.hstack(
                rx.icon(tag="images", size=13, color=S.TEXT_MUTED),
                rx.text(HubState.audit_images.length().to_string() + " imagens total", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                spacing="1", align="center",
            ),
            width="100%", align="center",
        ),
        rx.text("Fotos de campo integradas dos RDOs + uploads manuais, organizadas por categoria. Clique para expandir.", font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_BODY),
        rx.cond(
            HubState.audit_loading,
            rx.center(rx.vstack(rx.spinner(size="3"), rx.text("Carregando imagens...", font_size="12px", color=S.TEXT_MUTED), spacing="2", align="center"), padding="40px"),
            rx.vstack(
                rx.foreach(AUDIT_CATEGORIES, _audit_bolsao_card),
                spacing="3", width="100%",
            ),
        ),
        spacing="4", width="100%", class_name="animate-fade-in",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — TIMELINE
# ══════════════════════════════════════════════════════════════════════════════


def _tl_type_badge(tipo: str) -> rx.Component:
    return rx.match(
        tipo,
        ("Reunião",     rx.badge("Reunião",     color_scheme="blue",   variant="soft", font_family=S.FONT_MONO, font_size="9px")),
        ("Marco",       rx.badge("Marco",       color_scheme="gold",   variant="soft", font_family=S.FONT_MONO, font_size="9px")),
        ("Falha",       rx.badge("Falha",       color_scheme="red",    variant="solid", font_family=S.FONT_MONO, font_size="9px")),
        ("Atualização", rx.badge("Atualização", color_scheme="green",  variant="soft", font_family=S.FONT_MONO, font_size="9px")),
        ("Alerta",      rx.badge("Alerta",      color_scheme="orange", variant="soft", font_family=S.FONT_MONO, font_size="9px")),
        ("Decisão",     rx.badge("Decisão",     color_scheme="purple", variant="soft", font_family=S.FONT_MONO, font_size="9px")),
        rx.badge(tipo,  color_scheme="gray",   variant="soft", font_family=S.FONT_MONO, font_size="9px"),
    )


def _tl_entry_row(entry: dict) -> rx.Component:
    return rx.hstack(
        # Timeline dot + line
        rx.vstack(
            rx.box(
                width="10px", height="10px", border_radius="50%",
                bg=rx.cond(entry["is_document"] == "1", S.PATINA, rx.cond(entry["is_cost"] == "1", S.COPPER, S.COPPER)),
                border=f"2px solid {S.BG_ELEVATED}", flex_shrink="0",
            ),
            rx.box(width="1px", flex="1", bg=S.BORDER_SUBTLE, margin_x="auto"),
            spacing="0", align="center", flex_shrink="0",
        ),
        # Content
        rx.box(
            rx.vstack(
                rx.hstack(
                    _tl_type_badge(entry["tipo"]),
                    # Document badge
                    rx.cond(
                        entry["is_document"] == "1",
                        rx.badge("DOC", color_scheme="teal", variant="solid", font_family=S.FONT_MONO, font_size="9px"),
                        rx.fragment(),
                    ),
                    # Cost badge
                    rx.cond(
                        entry["is_cost"] == "1",
                        rx.badge(
                            rx.hstack(rx.icon(tag="circle-dollar-sign", size=9), rx.text(entry["custo_categoria"]), spacing="1"),
                            color_scheme="amber", variant="soft", font_family=S.FONT_MONO, font_size="9px",
                        ),
                        rx.fragment(),
                    ),
                    rx.text(entry["titulo"], font_size="13px", font_weight="600", color="var(--text-main)", font_family=S.FONT_TECH, letter_spacing="0.01em"),
                    rx.spacer(),
                    rx.hstack(
                        rx.icon(tag="clock", size=11, color=S.TEXT_MUTED),
                        rx.text(entry["created_at"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        spacing="1", align="center",
                    ),
                    rx.icon_button(rx.icon(tag="trash-2", size=11, color=S.DANGER), size="1", variant="ghost", on_click=HubState.delete_timeline_entry(entry["id"]), cursor="pointer", _hover={"bg": "rgba(239,68,68,0.1)"}),
                    spacing="2", align="center", width="100%", flex_wrap="wrap",
                ),
                rx.cond(
                    entry["descricao"] != "",
                    rx.text(entry["descricao"], font_size="12px", color=S.TEXT_MUTED, font_family=S.FONT_BODY, line_height="1.5"),
                ),
                # Cost value row
                rx.cond(
                    entry["is_cost"] == "1",
                    rx.hstack(
                        rx.icon(tag="banknote", size=11, color=S.COPPER),
                        rx.text("R$ " + entry["custo_valor"], font_size="12px", color=S.COPPER, font_family=S.FONT_MONO, font_weight="700"),
                        spacing="1", align="center",
                    ),
                    rx.fragment(),
                ),
                # Attachment
                rx.cond(
                    entry["anexo_url"] != "",
                    rx.el.a(
                        rx.hstack(
                            rx.icon(tag="paperclip", size=11, color=S.PATINA),
                            rx.text(entry["anexo_nome"], font_size="11px", color=S.PATINA, font_family=S.FONT_MONO,
                                    max_width="200px", overflow="hidden", text_overflow="ellipsis", white_space="nowrap"),
                            spacing="1", align="center",
                        ),
                        href=entry["anexo_url"], target="_blank",
                        style={"textDecoration": "none", "display": "inline-flex"},
                        _hover={"opacity": "0.8"},
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.icon(tag="user", size=10, color=S.TEXT_MUTED),
                    rx.text(entry["autor"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="1", align="center",
                ),
                spacing="2", width="100%",
            ),
            padding="12px 16px", border_radius=S.R_CONTROL,
            border=rx.cond(
                entry["is_document"] == "1",
                f"1px solid rgba(42,157,143,0.3)",
                rx.cond(entry["is_cost"] == "1", f"1px solid rgba(201,139,42,0.3)", f"1px solid {S.BORDER_SUBTLE}"),
            ),
            bg="rgba(255,255,255,0.02)",
            _hover={"border_color": S.BORDER_ACCENT, "bg": "rgba(255,255,255,0.035)"},
            transition="all 0.15s ease", flex="1",
        ),
        spacing="3", align="start", width="100%",
    )


def _tl_filter_pill(tipo: str) -> rx.Component:
    is_active = HubState.tl_filter_tipo == tipo
    return rx.box(
        rx.text(tipo, font_size="10px", font_weight="700", color=rx.cond(is_active, S.BG_VOID, S.TEXT_MUTED), white_space="nowrap"),
        padding="3px 10px", border_radius="4px", cursor="pointer",
        bg=rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.04)"),
        border=rx.cond(is_active, f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
        on_click=HubState.set_tl_filter_tipo(tipo),
        _hover={"bg": rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.07)")},
        transition="all 0.15s ease",
    )


def _tab_timeline() -> rx.Component:
    return rx.flex(
        # ── LEFT: New entry form ──────────────────────────────────────────────
        rx.vstack(
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="circle-plus", size=14, color=S.COPPER),
                        rx.text("NOVO REGISTRO", font_family=S.FONT_TECH, font_size="0.85rem", font_weight="700", color="var(--text-main)", letter_spacing="0.06em"),
                        spacing="2", align="center",
                    ),
                    # Type selector
                    rx.vstack(
                        rx.text("Tipo", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.select.root(
                            rx.select.trigger(placeholder="Tipo de registro...", style={"width": "100%", "background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "cursor": "pointer"}),
                            rx.select.content(
                                *[rx.select.item(t, value=t) for t in ENTRY_TYPES],
                                bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                            ),
                            value=HubState.tl_entry_type,
                            on_change=HubState.set_tl_entry_type,
                        ),
                        spacing="1", width="100%",
                    ),
                    # Título
                    rx.vstack(
                        rx.text("Título *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            default_value=HubState.tl_titulo, on_blur=HubState.set_tl_titulo,
                            placeholder="Título do registro...",
                            style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "padding": "8px 10px", "fontSize": "14px", "width": "100%", "outline": "none"},
                        ),
                        spacing="1", width="100%",
                    ),
                    # Descrição
                    rx.vstack(
                        rx.hstack(
                            rx.text("Descrição", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.text("Use @username para mencionar", font_size="10px", color="rgba(201,139,42,0.6)", font_family=S.FONT_MONO),
                            justify="between", width="100%",
                        ),
                        rx.el.textarea(
                            default_value=HubState.tl_descricao, on_blur=HubState.set_tl_descricao,
                            placeholder="Detalhes, observações... Use @username para mencionar.",
                            rows="3",
                            style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "padding": "8px 10px", "fontSize": "13px", "width": "100%", "outline": "none", "resize": "vertical", "fontFamily": S.FONT_BODY},
                        ),
                        # Chips de usuários disponíveis para @mention
                        rx.cond(
                            HubState.tl_mention_users.length() > 0,
                            rx.hstack(
                                rx.text("Mencionar:", font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, flex_shrink="0"),
                                rx.flex(
                                    rx.foreach(
                                        HubState.tl_mention_users,
                                        lambda u: rx.box(
                                            rx.text("@" + u, font_size="10px", font_family=S.FONT_MONO, color=S.COPPER),
                                            padding="2px 8px",
                                            border_radius="12px",
                                            border=f"1px solid rgba(201,139,42,0.3)",
                                            bg="rgba(201,139,42,0.07)",
                                            cursor="pointer",
                                            _hover={"bg": "rgba(201,139,42,0.18)"},
                                        ),
                                    ),
                                    gap="4px",
                                    flex_wrap="wrap",
                                ),
                                spacing="2", align="start", width="100%",
                            ),
                        ),
                        spacing="1", width="100%",
                    ),
                    # ── Campos de custo (visíveis só se tipo == Custo) ────
                    rx.cond(
                        HubState.tl_entry_type == "Custo",
                        rx.hstack(
                            rx.vstack(
                                rx.text("Valor (R$)", font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                rx.el.input(
                                    default_value=HubState.tl_custo_valor,
                                    on_blur=HubState.set_tl_custo_valor,
                                    placeholder="0,00",
                                    style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "padding": "6px 8px", "fontSize": "13px", "width": "100%", "outline": "none"},
                                ),
                                spacing="1", flex="1",
                            ),
                            rx.vstack(
                                rx.text("Categoria", font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                rx.select.root(
                                    rx.select.trigger(style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "fontSize": "12px", "cursor": "pointer", "width": "100%"}),
                                    rx.select.content(
                                        *[rx.select.item(c, value=c) for c in ["Operacional", "Comercial", "Marketing", "Logística", "Administrativo", "Outro"]],
                                        bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                                    ),
                                    value=HubState.tl_custo_categoria,
                                    on_change=HubState.set_tl_custo_categoria,
                                ),
                                spacing="1", flex="1",
                            ),
                            spacing="2", width="100%",
                        ),
                    ),
                    # ── Anexo ─────────────────────────────────────────────
                    rx.vstack(
                        rx.text("Anexo", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.cond(
                            HubState.tl_anexo_nome != "",
                            rx.hstack(
                                rx.icon(tag="paperclip", size=12, color=S.PATINA),
                                rx.text(HubState.tl_anexo_nome, font_size="11px", color=S.PATINA, font_family=S.FONT_MONO, max_width="160px", overflow="hidden", text_overflow="ellipsis", white_space="nowrap"),
                                rx.icon_button(rx.icon(tag="x", size=10, color=S.DANGER), size="1", variant="ghost", on_click=HubState.set_tl_anexo_nome(""), cursor="pointer"),
                                spacing="1", align="center",
                            ),
                            rx.upload(
                                rx.hstack(
                                    rx.cond(
                                        HubState.tl_uploading_anexo,
                                        rx.spinner(size="1"),
                                        rx.icon(tag="upload", size=12, color=S.TEXT_MUTED),
                                    ),
                                    rx.text(rx.cond(HubState.tl_uploading_anexo, "Enviando...", "Clique ou arraste um arquivo"), font_size="11px", color=S.TEXT_MUTED),
                                    spacing="1", align="center",
                                ),
                                on_drop=HubState.upload_tl_anexo(rx.upload_files(upload_id="tl_file")),
                                id="tl_file",
                                border=f"1px dashed {S.BORDER_SUBTLE}",
                                border_radius="6px",
                                padding="8px 12px",
                                width="100%",
                                cursor="pointer",
                                _hover={"border_color": S.COPPER},
                                accept={"application/pdf": [".pdf"], "image/*": [".jpg", ".jpeg", ".png"], "application/vnd.openxmlformats-officedocument.*": [".xlsx", ".docx"]},
                            ),
                        ),
                        spacing="1", width="100%",
                    ),
                    rx.cond(HubState.tl_error != "", rx.text(HubState.tl_error, font_size="12px", color=S.DANGER)),
                    # Submit
                    rx.button(
                        rx.cond(
                            HubState.tl_submitting,
                            rx.spinner(size="2"),
                            rx.hstack(rx.icon(tag="send", size=13), rx.text("Registrar"), spacing="1", align="center"),
                        ),
                        on_click=HubState.submit_timeline_entry,
                        disabled=HubState.tl_submitting,
                        width="100%", size="2",
                        style={"background": S.COPPER, "color": S.BG_VOID, "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                    ),
                    spacing="3", width="100%",
                ),
                **_GLASS_PANEL, width="100%",
            ),
            width=rx.breakpoints(initial="100%", lg="280px"),
            flex_shrink="0",
        ),
        # ── RIGHT: Timeline feed ──────────────────────────────────────────────
        rx.vstack(
            # Search bar
            rx.box(
                rx.icon(tag="search", size=13, color=S.TEXT_MUTED, position="absolute", left="10px", top="50%", transform="translateY(-50%)", pointer_events="none"),
                rx.el.input(
                    placeholder="Pesquisar registros...",
                    on_change=HubState.set_tl_search_input,
                    on_blur=HubState.commit_tl_search,
                    on_key_down=HubState.handle_tl_search_key,
                    style={"background": "rgba(14,26,23,0.6)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "padding": "7px 10px 7px 30px", "fontSize": "13px", "width": "100%", "outline": "none"},
                ),
                position="relative", width="100%",
            ),
            # Filter pills
            rx.hstack(
                rx.box(
                    rx.text("Todos", font_size="10px", font_weight="700", color=rx.cond(HubState.tl_filter_tipo == "", S.BG_VOID, S.TEXT_MUTED), white_space="nowrap"),
                    padding="3px 10px", border_radius="4px", cursor="pointer",
                    bg=rx.cond(HubState.tl_filter_tipo == "", S.COPPER, "rgba(255,255,255,0.04)"),
                    border=rx.cond(HubState.tl_filter_tipo == "", f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
                    on_click=HubState.set_tl_filter_tipo(""),
                    _hover={"bg": rx.cond(HubState.tl_filter_tipo == "", S.COPPER, "rgba(255,255,255,0.07)")},
                    transition="all 0.15s ease",
                ),
                rx.foreach(rx.Var.create(ENTRY_TYPES), _tl_filter_pill),
                spacing="1", flex_wrap="wrap", align="center",
            ),
            # Feed
            rx.cond(
                HubState.timeline_loading,
                rx.center(rx.vstack(rx.spinner(size="3"), rx.text("Carregando registros...", font_size="12px", color=S.TEXT_MUTED), spacing="2", align="center"), padding="40px"),
                rx.cond(
                    HubState.filtered_timeline.length() == 0,
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="scroll-text", size=32, color=S.BORDER_SUBTLE),
                            rx.text("Nenhum registro encontrado", font_size="13px", color=S.TEXT_MUTED),
                            rx.text("Use o formulário ao lado para criar o primeiro registro", font_size="11px", color=S.TEXT_MUTED, opacity="0.7"),
                            spacing="2", align="center",
                        ), padding="40px",
                    ),
                    rx.vstack(
                        rx.foreach(HubState.filtered_timeline, _tl_entry_row),
                        spacing="0", width="100%",
                    ),
                ),
            ),
            spacing="3", flex="1", width="100%",
        ),
        gap="20px",
        flex_wrap=rx.breakpoints(initial="wrap", lg="nowrap"),
        width="100%", align="start",
        class_name="animate-fade-in",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PROJECT DETAIL: TAB ROUTER
# ══════════════════════════════════════════════════════════════════════════════


def _project_breadcrumb() -> rx.Component:
    """Minimal breadcrumb bar: back button + project code. Tabs are in the global top bar."""
    return rx.hstack(
        rx.button(
            rx.icon(tag="chevron-left", size=16),
            "Projetos",
            variant="ghost",
            on_click=GlobalState.deselect_project,
            cursor="pointer",
            color=S.TEXT_MUTED,
            font_family=S.FONT_MONO,
            font_size="12px",
            _hover={"color": "white", "bg": "rgba(255,255,255,0.06)"},
            padding_x="10px",
            padding_y="6px",
            border_radius="4px",
        ),
        rx.text("/", color=S.BORDER_SUBTLE, font_size="14px"),
        rx.text(
            GlobalState.selected_project,
            font_family=S.FONT_TECH,
            font_size="14px",
            font_weight="600",
            color="var(--text-main)",
        ),
        spacing="2",
        align="center",
        padding_y="8px",
        margin_bottom="12px",
        width="100%",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — FINANCEIRO POR PROJETO
# ══════════════════════════════════════════════════════════════════════════════

_FIN_STATUS_COLORS = {
    "previsto":     ("#C98B2A", "rgba(201,139,42,0.12)"),
    "em_andamento": ("#3B82F6", "rgba(59,130,246,0.12)"),
    "parcial":      ("#A78BFA", "rgba(167,139,250,0.12)"),
    "executado":    ("#06B6D4", "rgba(6,182,212,0.12)"),
    "concluido":    ("#22c55e", "rgba(34,197,94,0.12)"),
    "cancelado":    ("#EF4444", "rgba(239,68,68,0.12)"),
}

_INPUT_STYLE = {
    "background": "rgba(14,26,23,0.8)",
    "border": f"1px solid rgba(255,255,255,0.08)",
    "borderRadius": "3px",
    "color": "white",
    "padding": "8px 10px",
    "fontSize": "13px",
    "width": "100%",
    "outline": "none",
}


def _fin_kpi_card(icon_tag: str, label: str, value, subtitle: str = "", color: str = "var(--text-main)") -> rx.Component:
    return rx.box(
        rx.text(label, font_size="9px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="6px"),
        rx.hstack(
            rx.center(rx.icon(tag=icon_tag, size=14, color=color), width="28px", height="28px", bg="rgba(255,255,255,0.04)", border_radius="4px", flex_shrink="0"),
            rx.text(value, font_family=S.FONT_TECH, font_size="1.4rem", font_weight="700", color=color, line_height="1"),
            spacing="2", align="center", margin_bottom="4px",
        ),
        rx.cond(subtitle != "", rx.text(subtitle, font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_BODY)),
        **_GLASS_COMPACT,
        flex="1",
        min_width="160px",
    )


def _fin_status_badge(status: str) -> rx.Component:
    label = rx.match(
        status,
        ("previsto",     rx.text("Previsto",     font_size="10px", font_weight="700", font_family=S.FONT_MONO)),
        ("em_andamento", rx.text("Em Andamento", font_size="10px", font_weight="700", font_family=S.FONT_MONO)),
        ("concluido",    rx.text("Concluído",    font_size="10px", font_weight="700", font_family=S.FONT_MONO)),
        ("cancelado",    rx.text("Cancelado",    font_size="10px", font_weight="700", font_family=S.FONT_MONO)),
        rx.text(status, font_size="10px", font_family=S.FONT_MONO),
    )
    color = rx.match(
        status,
        ("previsto",     S.COPPER),
        ("em_andamento", "#3B82F6"),
        ("concluido",    "#22c55e"),
        ("cancelado",    S.DANGER),
        S.TEXT_MUTED,
    )
    bg = rx.match(
        status,
        ("previsto",     "rgba(201,139,42,0.12)"),
        ("em_andamento", "rgba(59,130,246,0.12)"),
        ("concluido",    "rgba(34,197,94,0.12)"),
        ("cancelado",    "rgba(239,68,68,0.12)"),
        "rgba(255,255,255,0.05)",
    )
    return rx.box(
        label,
        color=color, bg=bg,
        padding="2px 8px", border_radius="3px",
        border=rx.cond(status == "previsto", f"1px solid rgba(201,139,42,0.3)",
               rx.cond(status == "em_andamento", "1px solid rgba(59,130,246,0.3)",
               rx.cond(status == "concluido", "1px solid rgba(34,197,94,0.3)",
               rx.cond(status == "cancelado", "1px solid rgba(239,68,68,0.3)",
               f"1px solid {S.BORDER_SUBTLE}")))),
    )


def _fin_custo_row(item: dict) -> rx.Component:
    return rx.hstack(
        # Categoria badge
        rx.box(
            rx.text(item["categoria_nome"], font_size="10px", font_weight="700", font_family=S.FONT_MONO, color=S.COPPER, white_space="nowrap"),
            padding="2px 8px", border_radius="3px",
            bg=S.COPPER_GLOW, border=f"1px solid rgba(201,139,42,0.2)",
            flex_shrink="0", max_width="130px", overflow="hidden", text_overflow="ellipsis",
        ),
        # Empresa badge (shown only if filled)
        rx.cond(
            item["empresa"] != "",
            rx.box(
                rx.text(item["empresa"], font_size="10px", font_weight="600", font_family=S.FONT_MONO, color="#2A9D8F", white_space="nowrap"),
                padding="2px 8px", border_radius="3px",
                bg="rgba(42,157,143,0.10)", border="1px solid rgba(42,157,143,0.25)",
                flex_shrink="0", max_width="130px", overflow="hidden", text_overflow="ellipsis",
                display=rx.breakpoints(initial="none", md="block"),
            ),
        ),
        # Description
        rx.text(item["descricao"], font_size="13px", color="var(--text-main)", font_family=S.FONT_BODY, flex="1", overflow="hidden", text_overflow="ellipsis", white_space="nowrap", min_width="0"),
        # Date
        rx.text(item["data_custo"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, white_space="nowrap", display=rx.breakpoints(initial="none", md="block")),
        # Previsto
        rx.vstack(
            rx.text("PREV", font_size="8px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"),
            rx.text(item["valor_previsto_fmt"], font_size="12px", font_weight="700", color=S.COPPER, font_family=S.FONT_MONO, white_space="nowrap"),
            spacing="0", align="end", flex_shrink="0",
        ),
        # Executado
        rx.vstack(
            rx.text("EXEC", font_size="8px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"),
            rx.text(item["valor_executado_fmt"], font_size="12px", font_weight="700", color="#22c55e", font_family=S.FONT_MONO, white_space="nowrap"),
            spacing="0", align="end", flex_shrink="0",
        ),
        # Status
        _fin_status_badge(item["status"]),
        # Actions
        rx.hstack(
            rx.icon_button(rx.icon(tag="pencil", size=12), size="1", variant="ghost", on_click=FinState.open_fin_edit(item["id"]), cursor="pointer", _hover={"bg": "rgba(201,139,42,0.15)"}),
            rx.icon_button(rx.icon(tag="trash-2", size=12, color=S.DANGER), size="1", variant="ghost", on_click=FinState.request_fin_delete(item["id"]), cursor="pointer", _hover={"bg": "rgba(239,68,68,0.12)"}),
            spacing="1", flex_shrink="0",
        ),
        padding="10px 14px",
        border_radius=S.R_CONTROL,
        border=f"1px solid {S.BORDER_SUBTLE}",
        bg="rgba(255,255,255,0.02)",
        _hover={"bg": "rgba(255,255,255,0.04)", "border_color": S.BORDER_ACCENT},
        transition="all 0.15s ease",
        width="100%", align="center", spacing="3", overflow="hidden",
    )


def _fin_custo_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag=rx.cond(FinState.fin_edit_id == "", "circle-plus", "pencil"), size=16, color=S.COPPER),
                    rx.dialog.title(FinState.fin_dialog_title, font_family=S.FONT_TECH, font_size="1rem", font_weight="700", color="var(--text-main)"),
                    rx.spacer(),
                    rx.dialog.close(rx.icon_button(rx.icon(tag="x", size=14), size="1", variant="ghost", cursor="pointer")),
                    align="center", width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                # Row 1: Categoria (combobox) + Status
                rx.flex(
                    rx.vstack(
                        rx.hstack(
                            rx.text("Categoria", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.text("(selecione ou crie nova)", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, opacity="0.6"),
                            spacing="2", align="center",
                        ),
                        rx.box(
                            rx.el.input(
                                value=FinState.fin_edit_categoria_nome,
                                on_change=FinState.set_fin_edit_categoria_by_name,
                                list="fin-categoria-datalist",
                                placeholder="Ex: Civil, Elétrica, Equipamentos...",
                                style={**_INPUT_STYLE, "width": "100%"},
                            ),
                            rx.el.datalist(
                                rx.foreach(
                                    FinState.fin_categorias,
                                    lambda c: rx.el.option(value=c["nome"]),
                                ),
                                id="fin-categoria-datalist",
                            ),
                            width="100%",
                        ),
                        spacing="1", flex="1",
                    ),
                    rx.vstack(
                        rx.text("Status", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.select.root(
                            rx.select.trigger(style={"width": "100%", "background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "cursor": "pointer"}),
                            rx.select.content(
                                rx.select.item("Previsto",     value="previsto"),
                                rx.select.item("Em Andamento", value="em_andamento"),
                                rx.select.item("Parcial",      value="parcial"),
                                rx.select.item("Executado",    value="executado"),
                                rx.select.item("Concluído",    value="concluido"),
                                rx.select.item("Cancelado",    value="cancelado"),
                                bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                                z_index="9999",
                                position="popper",
                            ),
                            value=FinState.fin_edit_status,
                            on_change=FinState.set_fin_edit_status,
                        ),
                        spacing="1", flex="1",
                    ),
                    gap="12px", flex_wrap="wrap", width="100%",
                ),
                # Row 2: Empresa + Descrição
                rx.flex(
                    rx.vstack(
                        rx.text("Empresa / Fornecedor", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            default_value=FinState.fin_edit_empresa,
                            on_blur=FinState.set_fin_edit_empresa,
                            placeholder="Ex: Construtora ABC, Locadora XYZ...",
                            style=_INPUT_STYLE,
                        ),
                        spacing="1", flex="1",
                    ),
                    rx.vstack(
                        rx.text("Descrição *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            default_value=FinState.fin_edit_descricao,
                            on_blur=FinState.set_fin_edit_descricao,
                            placeholder="Ex: Concreto para fundações...",
                            style=_INPUT_STYLE,
                        ),
                        spacing="1", flex="1",
                    ),
                    gap="12px", flex_wrap="wrap", width="100%",
                ),
                # Row 3: Valor Previsto + Valor Executado (currency-formatted)
                rx.flex(
                    rx.vstack(
                        rx.text("Valor Previsto (R$)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            value=FinState.fin_edit_valor_previsto,
                            on_change=FinState.set_fin_edit_valor_previsto,
                            on_blur=FinState.on_blur_fin_valor_previsto,
                            placeholder="0,00",
                            type="text",
                            input_mode="decimal",
                            style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)", "fontWeight": "600"},
                        ),
                        spacing="1", flex="1",
                    ),
                    rx.vstack(
                        rx.text("Valor Executado (R$)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            value=FinState.fin_edit_valor_executado,
                            on_change=FinState.set_fin_edit_valor_executado,
                            on_blur=FinState.on_blur_fin_valor_executado,
                            placeholder="0,00",
                            type="text",
                            input_mode="decimal",
                            style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)", "fontWeight": "600"},
                        ),
                        spacing="1", flex="1",
                    ),
                    gap="12px", flex_wrap="wrap", width="100%",
                ),
                # Row 4: Data + Atividade vinculada
                rx.flex(
                    rx.vstack(
                        rx.text("Data do Custo", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            value=FinState.fin_edit_data,
                            on_change=FinState.set_fin_edit_data,
                            type="date",
                            style={**_INPUT_STYLE, "colorScheme": "dark"},
                        ),
                        spacing="1", flex="1",
                    ),
                    rx.vstack(
                        rx.text("Atividade Vinculada", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.select.root(
                            rx.select.trigger(placeholder="Nenhuma...", style={"width": "100%", "background": "rgba(14,26,23,0.8)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "cursor": "pointer"}),
                            rx.select.content(
                                rx.select.item("Nenhuma", value="__none__"),
                                rx.foreach(
                                    FinState.fin_atividade_options,
                                    lambda a: rx.select.item(a["label"], value=a["id"]),
                                ),
                                bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                                z_index="9999", position="popper",
                            ),
                            value=rx.cond(FinState.fin_edit_atividade_id == "", "__none__", FinState.fin_edit_atividade_id),
                            on_change=FinState.set_fin_edit_atividade,
                        ),
                        spacing="1", flex="1",
                    ),
                    gap="12px", flex_wrap="wrap", width="100%",
                ),
                # Row 5: Observações
                rx.vstack(
                    rx.text("Observações", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.el.textarea(
                        default_value=FinState.fin_edit_observacoes,
                        on_blur=FinState.set_fin_edit_observacoes,
                        placeholder="Notas adicionais...",
                        rows="2",
                        style={**_INPUT_STYLE, "resize": "vertical", "fontFamily": S.FONT_BODY},
                    ),
                    spacing="1", width="100%",
                ),
                # Error
                rx.cond(FinState.fin_error != "", rx.text(FinState.fin_error, font_size="12px", color=S.DANGER)),
                # Actions
                rx.hstack(
                    rx.dialog.close(rx.button("Cancelar", variant="ghost", size="2", cursor="pointer", on_click=FinState.close_fin_dialog)),
                    rx.button(
                        rx.cond(FinState.fin_saving, rx.spinner(size="2"), rx.hstack(rx.icon(tag="save", size=13), rx.text("Salvar"), spacing="1")),
                        on_click=FinState.save_fin_custo,
                        size="2",
                        disabled=FinState.fin_saving,
                        style={"background": S.COPPER, "color": S.BG_VOID, "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                    ),
                    justify="end", spacing="2", width="100%",
                ),
                spacing="4", width="100%",
            ),
            bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}", border_radius=S.R_CARD,
            max_width="560px", width="95vw",
        ),
        open=FinState.fin_show_dialog,
        on_open_change=FinState.set_fin_show_dialog,
    )


def _fin_delete_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="trash-2", size=16, color=S.DANGER),
                    rx.dialog.title("Excluir Custo", font_family=S.FONT_TECH, font_weight="700", color="var(--text-main)"),
                    spacing="2", align="center",
                ),
                rx.text("Tem certeza que deseja excluir o custo:", font_size="13px", color=S.TEXT_MUTED),
                rx.text(FinState.fin_delete_desc, font_size="13px", font_weight="700", color=S.DANGER),
                rx.text("Esta ação não pode ser desfeita.", font_size="11px", color=S.TEXT_MUTED),
                rx.hstack(
                    rx.button("Cancelar", variant="ghost", size="2", cursor="pointer", on_click=FinState.cancel_fin_delete),
                    rx.button(
                        rx.hstack(rx.icon(tag="trash-2", size=13), rx.text("Excluir"), spacing="1"),
                        on_click=FinState.confirm_fin_delete, size="2",
                        style={"background": S.DANGER, "color": "white", "cursor": "pointer"},
                    ),
                    justify="end", spacing="2", width="100%",
                ),
                spacing="3", width="100%",
            ),
            bg=S.BG_ELEVATED, border=f"1px solid rgba(239,68,68,0.3)", border_radius=S.R_CARD, max_width="420px", width="90vw",
        ),
        open=FinState.fin_show_delete,
    )


def _fin_scurve_chart() -> rx.Component:
    """S-Curve chart: cumulative previsto vs executado over time."""
    return rx.box(
        rx.hstack(
            rx.icon(tag="trending-up", size=14, color=S.COPPER),
            rx.text("CURVA S — EVOLUÇÃO ACUMULADA", font_family=S.FONT_TECH, font_size="0.8rem", font_weight="700", color="var(--text-main)", letter_spacing="0.06em"),
            spacing="2", align="center", margin_bottom="16px",
        ),
        rx.recharts.responsive_container(
            rx.recharts.area_chart(
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.05)"),
                rx.recharts.x_axis(
                    data_key="data",
                    tick={"fill": "#889999", "fontSize": 10, "fontFamily": "'JetBrains Mono', monospace"},
                    axisLine=False, tickLine=False,
                ),
                rx.recharts.y_axis(
                    tick={"fill": "#889999", "fontSize": 10, "fontFamily": "'JetBrains Mono', monospace"},
                    axisLine=False, tickLine=False,
                    width=65,
                ),
                TOOLTIP_SPLIT,
                rx.recharts.legend(
                    wrapper_style={"fontSize": "11px", "fontFamily": "'JetBrains Mono', monospace", "color": "#889999"},
                ),
                rx.recharts.area(
                    data_key="previsto_acum",
                    name="Previsto Acum.",
                    stroke=S.COPPER, fill="rgba(201,139,42,0.12)",
                    stroke_width=2, type="monotone",
                ),
                rx.recharts.area(
                    data_key="executado_acum",
                    name="Executado Acum.",
                    stroke="#22c55e", fill="rgba(34,197,94,0.08)",
                    stroke_width=2, type="monotone",
                ),
                data=FinState.fin_scurve,
            ),
            width="100%", height=220,
        ),
        **_GLASS_PANEL,
        width="100%",
    )


def _fin_by_cat_chart() -> rx.Component:
    """Bar chart: previsto vs executado per categoria."""
    return rx.box(
        rx.hstack(
            rx.icon(tag="bar-chart-2", size=14, color=S.COPPER),
            rx.text("PREVISTO × EXECUTADO POR CATEGORIA", font_family=S.FONT_TECH, font_size="0.8rem", font_weight="700", color="var(--text-main)", letter_spacing="0.06em"),
            spacing="2", align="center", margin_bottom="16px",
        ),
        rx.recharts.responsive_container(
            rx.recharts.bar_chart(
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.05)"),
                rx.recharts.x_axis(
                    data_key="categoria",
                    tick={"fill": "#889999", "fontSize": 10, "fontFamily": "'JetBrains Mono', monospace"},
                    axisLine=False, tickLine=False,
                ),
                rx.recharts.y_axis(
                    tick={"fill": "#889999", "fontSize": 10, "fontFamily": "'JetBrains Mono', monospace"},
                    axisLine=False, tickLine=False,
                    width=65,
                ),
                TOOLTIP_SPLIT,
                rx.recharts.legend(
                    wrapper_style={"fontSize": "11px", "fontFamily": "'JetBrains Mono', monospace", "color": "#889999"},
                ),
                rx.recharts.bar(data_key="previsto", name="Previsto", fill=S.COPPER, radius=[3, 3, 0, 0]),
                rx.recharts.bar(data_key="executado", name="Executado", fill="#22c55e", radius=[3, 3, 0, 0]),
                data=FinState.fin_by_cat,
                bar_category_gap="30%",
            ),
            width="100%", height=200,
        ),
        **_GLASS_PANEL,
        width="100%",
    )


def _fin_evm_indicator(label: str, value, good_condition, icon_tag: str = "activity") -> rx.Component:
    """Compact EVM metric card with color-coded health indicator."""
    return rx.box(
        rx.text(label, font_size="9px", font_family=S.FONT_MONO, color=S.TEXT_MUTED,
                text_transform="uppercase", letter_spacing="0.1em", margin_bottom="4px"),
        rx.hstack(
            rx.icon(tag=icon_tag, size=13,
                    color=rx.cond(good_condition, "#22c55e", S.DANGER)),
            rx.text(value, font_family=S.FONT_TECH, font_size="1.1rem", font_weight="700",
                    color=rx.cond(good_condition, "#22c55e", S.DANGER), line_height="1"),
            spacing="2", align="center",
        ),
        **_GLASS_COMPACT, flex="1", min_width="140px",
    )


def _fin_forecast_panel() -> rx.Component:
    """
    EVM (Earned Value Management) forecast panel.
    Exibe projeções de custo e prazo baseadas no método EVM — padrão PMBOK/PMI para obras.

    Métricas exibidas:
      CPI  > 1 = abaixo do orçamento (verde)  |  < 1 = estouro (vermelho)
      SPI  > 1 = adiantado (verde)             |  < 1 = atrasado (vermelho)
      EAC  = estimativa de custo final ao término
      VAC  = variação ao término (quanto vai sobrar ou faltar)
      TCPI = taxa de desempenho necessária para terminar no orçamento
    """
    f = FinState.fin_forecast
    has_data = FinState.fin_forecast.length() > 0

    return rx.cond(
        has_data,
        rx.box(
            # Header
            rx.hstack(
                rx.icon(tag="radar", size=15, color=S.COPPER),
                rx.text("EVM — PROJEÇÃO FINANCEIRA", font_family=S.FONT_TECH, font_size="0.85rem",
                        font_weight="700", color="var(--text-main)", letter_spacing="0.06em"),
                rx.spacer(),
                rx.box(
                    rx.text("EARNED VALUE MANAGEMENT · PMBOK", font_size="9px",
                            color=S.TEXT_MUTED, font_family=S.FONT_MONO, letter_spacing="0.06em"),
                    padding="3px 8px", border_radius="3px",
                    bg="rgba(255,255,255,0.04)", border=f"1px solid {S.BORDER_SUBTLE}",
                ),
                spacing="2", align="center", margin_bottom="16px", width="100%",
            ),

            # Progress physical vs cost
            rx.hstack(
                rx.vstack(
                    rx.text("AVANÇO FÍSICO", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.hstack(
                        rx.text(f["physical_pct"] + "%", font_family=S.FONT_TECH, font_size="1.6rem",
                                font_weight="700", color="#3B82F6"),
                        rx.text("atividades", font_size="10px", color=S.TEXT_MUTED,
                                font_family=S.FONT_MONO, align_self="end", padding_bottom="4px"),
                        spacing="2", align="end",
                    ),
                    spacing="0",
                ),
                rx.box(width="1px", height="40px", bg=S.BORDER_SUBTLE, flex_shrink="0"),
                rx.vstack(
                    rx.text("AVANÇO FINANCEIRO", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.hstack(
                        rx.text(f["cost_pct"] + "%", font_family=S.FONT_TECH, font_size="1.6rem",
                                font_weight="700", color=S.COPPER),
                        rx.text("executado", font_size="10px", color=S.TEXT_MUTED,
                                font_family=S.FONT_MONO, align_self="end", padding_bottom="4px"),
                        spacing="2", align="end",
                    ),
                    spacing="0",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text("BURN RATE", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.text(f["burn_rate_fmt"], font_family=S.FONT_TECH, font_size="0.95rem",
                            font_weight="700", color="var(--text-main)"),
                    spacing="0", align="end",
                ),
                width="100%", align="center", spacing="5",
                padding="12px 16px", border_radius=S.R_CONTROL,
                bg="rgba(255,255,255,0.02)", border=f"1px solid {S.BORDER_SUBTLE}",
                margin_bottom="12px",
            ),

            # EVM indicators row
            rx.flex(
                # CPI — Cost Performance Index
                rx.box(
                    rx.text("CPI — DESEMPENHO DE CUSTO", font_size="9px", font_family=S.FONT_MONO,
                            color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="4px"),
                    rx.hstack(
                        rx.icon(tag="trending-up", size=13,
                                color=rx.cond(f["CPI"].to(float) >= 1.0, "#22c55e", S.DANGER)),
                        rx.text(f["CPI"], font_family=S.FONT_TECH, font_size="1.3rem", font_weight="700",
                                color=rx.cond(f["CPI"].to(float) >= 1.0, "#22c55e", S.DANGER)),
                        rx.text(
                            rx.cond(f["CPI"].to(float) >= 1.0, "abaixo orçamento", "estouro previsto"),
                            font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                            align_self="end", padding_bottom="2px",
                        ),
                        spacing="2", align="center",
                    ),
                    **_GLASS_COMPACT, flex="1", min_width="160px",
                ),
                # SPI — Schedule Performance Index
                rx.box(
                    rx.text("SPI — DESEMPENHO DE PRAZO", font_size="9px", font_family=S.FONT_MONO,
                            color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="4px"),
                    rx.hstack(
                        rx.icon(tag="calendar-check", size=13,
                                color=rx.cond(f["SPI"].to(float) >= 1.0, "#22c55e", "#F59E0B")),
                        rx.text(f["SPI"], font_family=S.FONT_TECH, font_size="1.3rem", font_weight="700",
                                color=rx.cond(f["SPI"].to(float) >= 1.0, "#22c55e", "#F59E0B")),
                        rx.text(
                            rx.cond(f["SPI"].to(float) >= 1.0, "no prazo / adiantado", "atrasado"),
                            font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                            align_self="end", padding_bottom="2px",
                        ),
                        spacing="2", align="center",
                    ),
                    **_GLASS_COMPACT, flex="1", min_width="160px",
                ),
                # EAC — Estimate at Completion
                rx.box(
                    rx.text("EAC — ESTIMATIVA FINAL", font_size="9px", font_family=S.FONT_MONO,
                            color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="4px"),
                    rx.text(f["EAC_fmt"], font_family=S.FONT_TECH, font_size="1.1rem", font_weight="700",
                            color="var(--text-main)"),
                    rx.text("projeção ao término", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    **_GLASS_COMPACT, flex="1", min_width="160px",
                ),
                # VAC — Variance at Completion
                rx.box(
                    rx.text("VAC — VARIAÇÃO AO TÉRMINO", font_size="9px", font_family=S.FONT_MONO,
                            color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="4px"),
                    rx.hstack(
                        rx.icon(
                            tag=rx.cond(f["vac_positive"] == "True", "circle-check", "circle-alert"),
                            size=13,
                            color=rx.cond(f["vac_positive"] == "True", "#22c55e", S.DANGER),
                        ),
                        rx.text(f["VAC_fmt"], font_family=S.FONT_TECH, font_size="1.1rem", font_weight="700",
                                color=rx.cond(f["vac_positive"] == "True", "#22c55e", S.DANGER)),
                        spacing="2", align="center",
                    ),
                    rx.text(
                        rx.cond(f["vac_positive"] == "True", "sobra prevista", "estouro previsto"),
                        font_size="9px",
                        color=rx.cond(f["vac_positive"] == "True", "#22c55e", S.DANGER),
                        font_family=S.FONT_MONO,
                    ),
                    **_GLASS_COMPACT, flex="1", min_width="160px",
                ),
                # TCPI — To-Complete Performance Index
                rx.box(
                    rx.text("TCPI — EFICIÊNCIA NECESSÁRIA", font_size="9px", font_family=S.FONT_MONO,
                            color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="4px"),
                    rx.hstack(
                        rx.icon(tag="target", size=13,
                                color=rx.cond(f["TCPI"].to(float) <= 1.1, "#22c55e", S.DANGER)),
                        rx.text(f["TCPI"], font_family=S.FONT_TECH, font_size="1.3rem", font_weight="700",
                                color=rx.cond(f["TCPI"].to(float) <= 1.1, "#22c55e", S.DANGER)),
                        rx.text(
                            rx.cond(f["TCPI"].to(float) <= 1.1, "alcançável", "desafio alto"),
                            font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                            align_self="end", padding_bottom="2px",
                        ),
                        spacing="2", align="center",
                    ),
                    **_GLASS_COMPACT, flex="1", min_width="160px",
                ),
                gap="10px", flex_wrap="wrap", width="100%",
            ),

            # EV / PV / AC triad
            rx.hstack(
                rx.vstack(
                    rx.text("VALOR PLANEJADO (PV)", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.text(f["PV_fmt"], font_family=S.FONT_MONO, font_size="12px",
                            font_weight="700", color=S.COPPER),
                    spacing="0",
                ),
                rx.vstack(
                    rx.text("VALOR AGREGADO (EV)", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.text(f["EV_fmt"], font_family=S.FONT_MONO, font_size="12px",
                            font_weight="700", color="#3B82F6"),
                    spacing="0",
                ),
                rx.vstack(
                    rx.text("CUSTO REAL (AC)", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.text(f["AC_fmt"], font_family=S.FONT_MONO, font_size="12px",
                            font_weight="700", color="#22c55e"),
                    spacing="0",
                ),
                rx.vstack(
                    rx.text("VARIAÇÃO DE CUSTO (CV)", font_size="9px", color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO, letter_spacing="0.08em"),
                    rx.text(
                        rx.cond(f["sv_positive"] == "True", "+", "-") + f["CV_fmt"],
                        font_family=S.FONT_MONO, font_size="12px", font_weight="700",
                        color=rx.cond(f["sv_positive"] == "True", "#22c55e", S.DANGER),
                    ),
                    spacing="0",
                ),
                flex_wrap="wrap", gap="20px",
                padding="12px 16px", border_radius=S.R_CONTROL,
                bg="rgba(255,255,255,0.02)", border=f"1px solid {S.BORDER_SUBTLE}",
                margin_top="10px", width="100%",
            ),

            **_GLASS_PANEL, width="100%",
        ),
    )


def _tab_financeiro() -> rx.Component:
    return rx.vstack(
        # Dialogs
        _fin_custo_dialog(),
        _fin_delete_dialog(),

        # ── KPI Strip ─────────────────────────────────────────────────────────
        rx.cond(
            FinState.fin_loading,
            rx.center(rx.vstack(rx.spinner(size="3"), rx.text("Carregando dados financeiros...", font_size="12px", color=S.TEXT_MUTED), spacing="2", align="center"), padding="60px", width="100%"),
            rx.vstack(
                # KPI cards row
                rx.flex(
                    _fin_kpi_card("trending-up", "Total Previsto",  FinState.fin_kpis["total_previsto"],  color=S.COPPER),
                    _fin_kpi_card("check-circle", "Total Executado", FinState.fin_kpis["total_executado"], color="#22c55e"),
                    _fin_kpi_card("minus-circle", "Saldo a Executar", FinState.fin_kpis["saldo"],          color="#3B82F6"),
                    rx.box(
                        rx.text("% EXECUTADO", font_size="9px", font_family=S.FONT_MONO, color=S.TEXT_MUTED, text_transform="uppercase", letter_spacing="0.1em", margin_bottom="6px"),
                        rx.text(FinState.fin_kpis["pct_executado"] + "%", font_family=S.FONT_TECH, font_size="1.4rem", font_weight="700", color=S.COPPER, line_height="1", margin_bottom="4px"),
                        rx.box(
                            rx.box(
                                width=FinState.fin_kpis["pct_executado"] + "%",
                                height="100%",
                                bg=S.COPPER,
                                border_radius="2px",
                                transition="width 1s ease-out",
                                max_width="100%",
                            ),
                            height="4px", bg="rgba(255,255,255,0.06)", border_radius="2px", overflow="hidden", width="100%",
                        ),
                        **_GLASS_COMPACT, flex="1", min_width="140px",
                    ),
                    gap="12px", flex_wrap="wrap", width="100%",
                ),

                # ── Toolbar ───────────────────────────────────────────────────
                rx.hstack(
                    # Search
                    rx.hstack(
                        rx.icon(tag="search", size=14, color=S.TEXT_MUTED),
                        rx.el.input(
                            default_value=FinState.fin_search,
                            on_change=FinState.set_fin_search_input,
                            on_blur=FinState.commit_fin_search,
                            on_key_down=FinState.handle_fin_search_key,
                            placeholder="Buscar descrição, categoria...",
                            style={"background": "transparent", "border": "none", "color": "white", "fontSize": "13px", "outline": "none", "flex": "1", "minWidth": "150px"},
                        ),
                        padding="8px 12px", border_radius=S.R_CONTROL,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        bg="rgba(255,255,255,0.02)", flex="1", align="center",
                    ),
                    # Status filter
                    rx.select.root(
                        rx.select.trigger(placeholder="Todos os status", style={"background": "rgba(14,26,23,0.7)", "border": f"1px solid {S.BORDER_SUBTLE}", "borderRadius": S.R_CONTROL, "color": "white", "cursor": "pointer", "minWidth": "150px"}),
                        rx.select.content(
                            rx.select.item("Todos",        value="__none__"),
                            rx.select.item("Previsto",     value="previsto"),
                            rx.select.item("Em Andamento", value="em_andamento"),
                            rx.select.item("Parcial",      value="parcial"),
                            rx.select.item("Executado",    value="executado"),
                            rx.select.item("Concluído",    value="concluido"),
                            rx.select.item("Cancelado",    value="cancelado"),
                            bg=S.BG_ELEVATED, border=f"1px solid {S.BORDER_SUBTLE}",
                        ),
                        value=rx.cond(FinState.fin_filter_status == "", "__none__", FinState.fin_filter_status),
                        on_change=FinState.set_fin_filter_status,
                    ),
                    # Nova button
                    rx.button(
                        rx.hstack(rx.icon(tag="plus", size=13), rx.text("Novo Custo"), spacing="1"),
                        on_click=FinState.open_fin_new,
                        size="2",
                        style={"background": S.COPPER, "color": S.BG_VOID, "fontFamily": S.FONT_TECH, "fontWeight": "700", "cursor": "pointer"},
                    ),
                    width="100%", align="center", flex_wrap="wrap", gap="10px",
                ),

                # ── Cost list ─────────────────────────────────────────────────
                rx.cond(
                    FinState.filtered_custos.length() == 0,
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="wallet", size=40, color=S.BORDER_SUBTLE),
                            rx.text("Nenhum custo encontrado", font_size="14px", color=S.TEXT_MUTED, font_family=S.FONT_TECH, font_weight="700", text_transform="uppercase", letter_spacing="0.06em"),
                            rx.text("Clique em 'Novo Custo' para registrar despesas deste projeto", font_size="12px", color=S.TEXT_MUTED, opacity="0.7"),
                            rx.button(
                                rx.hstack(rx.icon(tag="plus", size=13), rx.text("Criar Primeiro Custo"), spacing="1"),
                                on_click=FinState.open_fin_new, size="2", variant="soft",
                                style={"cursor": "pointer", "marginTop": "8px"},
                            ),
                            spacing="3", align="center",
                        ),
                        width="100%",
                        min_height="40vh",
                    ),
                    rx.vstack(
                        rx.foreach(FinState.filtered_custos, _fin_custo_row),
                        spacing="1", width="100%",
                    ),
                ),

                # ── Charts ────────────────────────────────────────────────────
                rx.cond(
                    FinState.fin_scurve.length() > 0,
                    _fin_scurve_chart(),
                ),
                rx.cond(
                    FinState.fin_by_cat.length() > 0,
                    _fin_by_cat_chart(),
                ),

                # ── EVM Forecast Panel ─────────────────────────────────────
                _fin_forecast_panel(),

                spacing="4", width="100%", class_name="animate-fade-in",
            ),
        ),
        spacing="0", width="100%",
    )


def hub_project_detail() -> rx.Component:
    """Renders the correct sub-page tab based on GlobalState.project_hub_tab."""
    return rx.vstack(
        _project_breadcrumb(),
        rx.match(
            GlobalState.project_hub_tab,
            ("visao_geral", rx.box(_tab_visao_geral(),   width="100%", class_name="animate-fade-in")),
            ("dashboard",   rx.box(_tab_dashboard(),     width="100%", class_name="animate-fade-in")),
            ("cronograma",  rx.box(_tab_cronograma(),    width="100%", class_name="animate-fade-in")),
            ("auditoria",   rx.box(_tab_auditoria(),     width="100%", class_name="animate-fade-in")),
            ("timeline",    rx.box(_tab_timeline(),      width="100%", class_name="animate-fade-in")),
            ("financeiro",  rx.box(_tab_financeiro(),    width="100%", class_name="animate-fade-in")),
            # Default
            rx.box(_tab_visao_geral(), width="100%"),
        ),
        width="100%",
        spacing="0",
    )


# ══════════════════════════════════════════════════════════════════════════════
# DUPLICAR PROJETO DIALOG
# ══════════════════════════════════════════════════════════════════════════════


def _duplicar_projeto_dialog() -> rx.Component:
    """Select a source project to duplicate — pre-fills the Novo Projeto form."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="copy", size=16, color=S.COPPER),
                    rx.dialog.title(
                        "DUPLICAR PROJETO",
                        font_family=S.FONT_TECH,
                        font_size="1rem",
                        font_weight="700",
                        color="var(--text-main)",
                        letter_spacing="0.06em",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.icon_button(
                            rx.icon(tag="x", size=14),
                            size="1",
                            variant="ghost",
                            cursor="pointer",
                            on_click=GlobalState.close_duplicar_projeto,
                        )
                    ),
                    align="center",
                    width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                rx.text(
                    "Selecione o projeto de origem. Os dados serão copiados para o formulário — altere o código e o que for diferente.",
                    font_size="13px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_BODY,
                ),
                rx.vstack(
                    rx.text("Projeto de Origem", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.select.root(
                        rx.select.trigger(
                            placeholder="Selecione um projeto...",
                            style={
                                "width": "100%",
                                "background": "rgba(14,26,23,0.8)",
                                "border": f"1px solid {S.BORDER_SUBTLE}",
                                "borderRadius": S.R_CONTROL,
                                "color": "white",
                                "cursor": "pointer",
                            },
                        ),
                        rx.select.content(
                            rx.foreach(
                                GlobalState.contratos_list,
                                lambda c: rx.select.item(
                                    f"{c['contrato']} — {c['cliente']}",
                                    value=c["contrato"],
                                ),
                            ),
                            bg=S.BG_ELEVATED,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            z_index="9999",
                            position="popper",
                        ),
                        value=GlobalState.dup_source_contrato,
                        on_change=GlobalState.set_dup_source_contrato,
                    ),
                    spacing="1",
                    width="100%",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancelar",
                            variant="ghost",
                            size="2",
                            cursor="pointer",
                            on_click=GlobalState.close_duplicar_projeto,
                        )
                    ),
                    rx.button(
                        rx.hstack(rx.icon(tag="copy", size=13), rx.text("Duplicar e Editar"), spacing="1"),
                        on_click=GlobalState.confirm_duplicar_projeto,
                        size="2",
                        disabled=GlobalState.dup_source_contrato == "",
                        style={
                            "background": S.COPPER,
                            "color": S.BG_VOID,
                            "fontFamily": S.FONT_TECH,
                            "fontWeight": "700",
                            "cursor": "pointer",
                        },
                    ),
                    justify="end",
                    spacing="2",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius=S.R_CARD,
            max_width="480px",
            width="90vw",
        ),
        open=GlobalState.show_duplicar_projeto,
        on_open_change=GlobalState.set_show_duplicar_projeto,
    )


# ══════════════════════════════════════════════════════════════════════════════
# NOVO PROJETO DIALOG
# ══════════════════════════════════════════════════════════════════════════════

_SELECT_TRIGGER_STYLE = {
    "width": "100%",
    "background": "rgba(14,26,23,0.8)",
    "border": f"1px solid rgba(255,255,255,0.08)",
    "borderRadius": "3px",
    "color": "white",
    "cursor": "pointer",
}


_DIAS_SEMANA = [
    ("Seg", "seg"),
    ("Ter", "ter"),
    ("Qua", "qua"),
    ("Qui", "qui"),
    ("Sex", "sex"),
    ("Sáb", "sab"),
    ("Dom", "dom"),
]


def _dia_chip(label: str, value: str, dias_var, toggle_event) -> rx.Component:
    """Single day toggle chip for the working days picker."""
    is_active = dias_var.contains(value)
    return rx.box(
        rx.text(
            label,
            font_family=S.FONT_MONO,
            font_size="11px",
            font_weight="700",
            color=rx.cond(is_active, S.BG_VOID, S.TEXT_MUTED),
            line_height="1",
        ),
        on_click=toggle_event(value),
        padding="5px 10px",
        border_radius="4px",
        cursor="pointer",
        background=rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.04)"),
        border=rx.cond(
            is_active,
            f"1px solid {S.COPPER}",
            f"1px solid rgba(255,255,255,0.08)",
        ),
        transition="all 0.12s ease",
        _hover={"opacity": "0.85"},
        flex_shrink="0",
    )


def _dias_uteis_picker(dias_var, toggle_event) -> rx.Component:
    """Reusable working days picker row — Seg Ter Qua Qui Sex Sáb Dom chips."""
    return rx.vstack(
        rx.hstack(
            rx.text("Dias Úteis da Obra", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
            rx.text("(mín. 1 dia)", font_size="10px", color=S.TEXT_MUTED, opacity="0.5"),
            spacing="2",
            align="center",
        ),
        rx.hstack(
            *[_dia_chip(label, value, dias_var, toggle_event) for label, value in _DIAS_SEMANA],
            spacing="1",
            flex_wrap="wrap",
        ),
        spacing="1",
        width="100%",
    )


def _novo_projeto_dialog() -> rx.Component:
    """Dialog for creating a new project / contract in contratos table."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.icon(tag="folder-plus", size=16, color=S.COPPER),
                    rx.dialog.title(
                        "NOVO PROJETO",
                        font_family=S.FONT_TECH,
                        font_size="1rem",
                        font_weight="700",
                        color="var(--text-main)",
                        letter_spacing="0.06em",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.icon_button(
                            rx.icon(tag="x", size=14),
                            size="1",
                            variant="ghost",
                            cursor="pointer",
                            on_click=GlobalState.close_novo_projeto,
                        )
                    ),
                    align="center",
                    width="100%",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                # ── Inputs — key força remount ao abrir (fix: typing não perde chars) ──
                rx.vstack(
                    # Row 1: Código do contrato + Tipo
                    rx.flex(
                        rx.vstack(
                            rx.text("Código do Contrato *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_contrato,
                                on_blur=GlobalState.set_np_contrato,
                                placeholder="Ex: SOL-2026-001",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)", "fontWeight": "700", "textTransform": "uppercase"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Tipo", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.select.root(
                                rx.select.trigger(style=_SELECT_TRIGGER_STYLE),
                                rx.select.content(
                                    rx.select.item("EPC", value="EPC"),
                                    rx.select.item("O&M", value="O&M"),
                                    rx.select.item("Fornecimento", value="Fornecimento"),
                                    rx.select.item("Consultoria", value="Consultoria"),
                                    bg=S.BG_ELEVATED,
                                    border=f"1px solid {S.BORDER_SUBTLE}",
                                    z_index="9999",
                                    position="popper",
                                ),
                                value=GlobalState.np_tipo,
                                on_change=GlobalState.set_np_tipo,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 2: Nome do projeto + Cliente
                    rx.flex(
                        rx.vstack(
                            rx.text("Nome do Projeto *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_projeto,
                                on_blur=GlobalState.set_np_projeto,
                                placeholder="Ex: Usina Solar Fazenda Boa Vista",
                                style=_INPUT_STYLE,
                            ),
                            spacing="1",
                            flex="2",
                        ),
                        rx.vstack(
                            rx.text("Cliente *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_cliente,
                                on_blur=GlobalState.set_np_cliente,
                                placeholder="Ex: Agropecuária Silva",
                                style=_INPUT_STYLE,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 3: Localização com HITL de geocoding
                    rx.vstack(
                        rx.hstack(
                            rx.text("Localização / Endereço", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.cond(
                                GlobalState.np_loc_confirmed,
                                rx.hstack(
                                    rx.icon(tag="check-circle", size=12, color="#2A9D8F"),
                                    rx.text("Localidade confirmada", font_size="9px", color="#2A9D8F"),
                                    spacing="1", align="center",
                                ),
                                rx.text("(valide antes de salvar)", font_size="9px", color=S.TEXT_MUTED, opacity="0.6"),
                            ),
                            spacing="2",
                            align="center",
                        ),
                        # HITL: confirmed → mostra banner + botão Alterar; senão → input + Validar
                        rx.cond(
                            GlobalState.np_loc_confirmed,
                            # ── Estado confirmado ──────────────────────────────
                            rx.hstack(
                                rx.icon(tag="check-circle", size=14, color=S.PATINA),
                                rx.text(
                                    GlobalState.np_localizacao,
                                    font_size="13px", font_weight="600", color="white",
                                    flex="1",
                                ),
                                rx.button(
                                    rx.icon(tag="pencil", size=12), "Alterar",
                                    on_click=GlobalState.reject_np_localizacao,
                                    size="1", variant="soft", color_scheme="gray", cursor="pointer",
                                ),
                                spacing="2", align="center",
                                style={"background": "rgba(74,222,128,0.06)", "border": f"1px solid {S.PATINA}55", "borderRadius": S.R_CONTROL, "padding": "10px 14px"},
                                width="100%",
                            ),
                            # ── Estado não confirmado ──────────────────────────
                            rx.vstack(
                                rx.hstack(
                                    rx.el.input(
                                        default_value=GlobalState.np_localizacao,
                                        on_blur=GlobalState.set_np_localizacao,
                                        placeholder="Ex: Guaiúba, Ceará",
                                        key=GlobalState.np_loc_input_key,
                                        style={**_INPUT_STYLE, "flex": "1"},
                                    ),
                                    rx.button(
                                        rx.cond(GlobalState.np_loc_validating, rx.spinner(size="1"), rx.icon(tag="map-pin", size=13)),
                                        rx.text("Validar", font_size="12px"),
                                        on_click=GlobalState.validate_np_localizacao,
                                        disabled=GlobalState.np_loc_validating,
                                        size="2", variant="soft", color_scheme="teal", cursor="pointer",
                                    ),
                                    spacing="2", width="100%",
                                ),
                                # Resultado geocoding aguardando confirmação
                                rx.cond(
                                    GlobalState.np_loc_geocoded_name != "",
                                    rx.hstack(
                                        rx.icon(tag="map-pin", size=13, color=S.COPPER),
                                        rx.text(
                                            "Encontrado: ",
                                            rx.text.span(GlobalState.np_loc_geocoded_name, font_weight="700", color="white"),
                                            font_size="12px", color=S.TEXT_MUTED, flex="1",
                                        ),
                                        rx.button(
                                            rx.icon(tag="check", size=12), "Confirmar",
                                            on_click=GlobalState.confirm_np_localizacao,
                                            size="1", variant="solid", color_scheme="teal", cursor="pointer",
                                        ),
                                        rx.button(
                                            rx.icon(tag="x", size=12), "Reescrever",
                                            on_click=GlobalState.reject_np_localizacao,
                                            size="1", variant="soft", color_scheme="gray", cursor="pointer",
                                        ),
                                        spacing="2", align="center",
                                        style={"background": "rgba(201,139,42,0.08)", "border": f"1px solid {S.COPPER}44", "borderRadius": S.R_CONTROL, "padding": "8px 12px"},
                                        width="100%",
                                    ),
                                    rx.fragment(),
                                ),
                                # Erro
                                rx.cond(
                                    GlobalState.np_loc_error != "",
                                    rx.hstack(
                                        rx.icon(tag="alert-circle", size=13, color="#EF4444"),
                                        rx.text(GlobalState.np_loc_error, font_size="11px", color="#EF4444"),
                                        spacing="2", align="center",
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1", width="100%",
                            ),
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    # Row 4: Terceirizado + Potência
                    rx.flex(
                        rx.vstack(
                            rx.text("Terceirizado / Parceiro", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_terceirizado,
                                on_blur=GlobalState.set_np_terceirizado,
                                placeholder="Ex: Construtora ABC Ltda",
                                style=_INPUT_STYLE,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Potência (kWp)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_potencia_kwp,
                                on_blur=GlobalState.set_np_potencia_kwp,
                                placeholder="Ex: 142,5",
                                type="text",
                                input_mode="decimal",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 5: Datas + Prazo
                    rx.flex(
                        rx.vstack(
                            rx.text("Data de Início", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                value=GlobalState.np_data_inicio,
                                on_change=GlobalState.set_np_data_inicio,
                                type="date",
                                style={**_INPUT_STYLE, "colorScheme": "dark"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Prazo Contratual (dias)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_prazo_dias,
                                on_blur=GlobalState.set_np_prazo_dias,
                                placeholder="Ex: 90",
                                type="text",
                                input_mode="numeric",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.hstack(
                                rx.text("Data de Término", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                                rx.text("(auto)", font_size="10px", color=S.TEXT_MUTED, font_style="italic"),
                                spacing="1", align="center",
                            ),
                            rx.el.input(
                                value=GlobalState.np_data_termino,
                                on_change=GlobalState.set_np_data_termino,
                                type="date",
                                style={**_INPUT_STYLE, "colorScheme": "dark"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 6: Prioridade + Efetivo
                    rx.flex(
                        rx.vstack(
                            rx.text("Prioridade", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.select.root(
                                rx.select.trigger(style=_SELECT_TRIGGER_STYLE),
                                rx.select.content(
                                    rx.select.item("Alta",   value="Alta"),
                                    rx.select.item("Média",  value="Média"),
                                    rx.select.item("Baixa",  value="Baixa"),
                                    bg=S.BG_ELEVATED,
                                    border=f"1px solid {S.BORDER_SUBTLE}",
                                    z_index="9999",
                                    position="popper",
                                ),
                                value=GlobalState.np_priority,
                                on_change=GlobalState.set_np_priority,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Efetivo Planejado (pessoas)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.np_efetivo_planejado,
                                on_blur=GlobalState.set_np_efetivo_planejado,
                                placeholder="Ex: 12",
                                type="text",
                                input_mode="numeric",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 7: Valor Contratado
                    rx.vstack(
                        rx.text("Valor Contratado (R$)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.el.input(
                            default_value=GlobalState.np_valor_contratado,
                            on_blur=GlobalState.set_np_valor_contratado,
                            placeholder="Ex: 1.250.000,00",
                            type="text",
                            style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    # Row 8: Dias úteis da obra
                    _dias_uteis_picker(GlobalState.np_dias_uteis, GlobalState.toggle_np_dia),
                    spacing="4",
                    width="100%",
                    key=GlobalState.np_form_key.to_string(),
                ),
                # Error
                rx.cond(
                    GlobalState.np_error != "",
                    rx.text(GlobalState.np_error, font_size="12px", color=S.DANGER),
                ),
                # Actions
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancelar",
                            variant="ghost",
                            size="2",
                            cursor="pointer",
                            on_click=GlobalState.close_novo_projeto,
                        )
                    ),
                    rx.button(
                        rx.cond(
                            GlobalState.np_saving,
                            rx.spinner(size="2"),
                            rx.hstack(rx.icon(tag="folder-plus", size=13), rx.text("Criar Projeto"), spacing="1"),
                        ),
                        on_click=GlobalState.save_novo_projeto,
                        size="2",
                        disabled=GlobalState.np_saving,
                        style={
                            "background": S.COPPER,
                            "color": S.BG_VOID,
                            "fontFamily": S.FONT_TECH,
                            "fontWeight": "700",
                            "cursor": "pointer",
                        },
                    ),
                    justify="end",
                    spacing="2",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius=S.R_CARD,
            max_width="620px",
            width="95vw",
        ),
        open=GlobalState.show_novo_projeto,
        on_open_change=GlobalState.set_show_novo_projeto,
    )


def _edit_projeto_dialog() -> rx.Component:
    """Dialog for editing / deleting an existing project."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.icon(tag="pencil", size=16, color=S.COPPER),
                    rx.dialog.title(
                        "EDITAR PROJETO",
                        font_family=S.FONT_TECH,
                        font_size="1rem",
                        font_weight="700",
                        color="var(--text-main)",
                        letter_spacing="0.06em",
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.icon_button(
                            rx.icon(tag="x", size=14),
                            size="1",
                            variant="ghost",
                            cursor="pointer",
                            on_click=GlobalState.close_edit_projeto,
                        )
                    ),
                    align="center",
                    width="100%",
                ),
                # Contract code (read-only label)
                rx.hstack(
                    rx.text("Contrato:", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    rx.text(GlobalState.ep_contrato, font_size="12px", font_weight="700",
                            color=S.COPPER, font_family=S.FONT_MONO),
                    spacing="2",
                    align="center",
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                # ── Inputs — key forces remount on each open ──────────────────
                rx.vstack(
                    # Row 1: Tipo
                    rx.vstack(
                        rx.text("Tipo", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        rx.select.root(
                            rx.select.trigger(style=_SELECT_TRIGGER_STYLE),
                            rx.select.content(
                                rx.select.item("EPC", value="EPC"),
                                rx.select.item("O&M", value="O&M"),
                                rx.select.item("Fornecimento", value="Fornecimento"),
                                rx.select.item("Consultoria", value="Consultoria"),
                                bg=S.BG_ELEVATED,
                                border=f"1px solid {S.BORDER_SUBTLE}",
                                z_index="9999",
                                position="popper",
                            ),
                            value=GlobalState.ep_tipo,
                            on_change=GlobalState.set_ep_tipo,
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    # Row 2: Nome do projeto + Cliente
                    rx.flex(
                        rx.vstack(
                            rx.text("Nome do Projeto *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_projeto,
                                on_blur=GlobalState.set_ep_projeto,
                                placeholder="Ex: Usina Solar Fazenda Boa Vista",
                                style=_INPUT_STYLE,
                            ),
                            spacing="1",
                            flex="2",
                        ),
                        rx.vstack(
                            rx.text("Cliente *", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_cliente,
                                on_blur=GlobalState.set_ep_cliente,
                                placeholder="Ex: Agropecuária Silva",
                                style=_INPUT_STYLE,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 3: Localização com HITL de geocoding
                    rx.vstack(
                        rx.hstack(
                            rx.text("Localização / Endereço", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.cond(
                                GlobalState.ep_loc_confirmed,
                                rx.hstack(
                                    rx.icon(tag="check-circle", size=12, color="#2A9D8F"),
                                    rx.text("Localidade confirmada", font_size="9px", color="#2A9D8F"),
                                    spacing="1", align="center",
                                ),
                                rx.text("(valide antes de salvar)", font_size="9px", color=S.TEXT_MUTED, opacity="0.6"),
                            ),
                            spacing="2", align="center",
                        ),
                        # HITL: confirmed → banner + Alterar; senão → input + Validar
                        rx.cond(
                            GlobalState.ep_loc_confirmed,
                            rx.hstack(
                                rx.icon(tag="check-circle", size=14, color=S.PATINA),
                                rx.text(GlobalState.ep_localizacao, font_size="13px", font_weight="600", color="white", flex="1"),
                                rx.button(
                                    rx.icon(tag="pencil", size=12), "Alterar",
                                    on_click=GlobalState.reject_ep_localizacao,
                                    size="1", variant="soft", color_scheme="gray", cursor="pointer",
                                ),
                                spacing="2", align="center",
                                style={"background": "rgba(74,222,128,0.06)", "border": f"1px solid {S.PATINA}55", "borderRadius": S.R_CONTROL, "padding": "10px 14px"},
                                width="100%",
                            ),
                            rx.vstack(
                                rx.hstack(
                                    rx.el.input(
                                        default_value=GlobalState.ep_localizacao,
                                        on_blur=GlobalState.set_ep_localizacao,
                                        placeholder="Ex: Guaiúba, Ceará",
                                        key=GlobalState.ep_loc_input_key,
                                        style={**_INPUT_STYLE, "flex": "1"},
                                    ),
                                    rx.button(
                                        rx.cond(GlobalState.ep_loc_validating, rx.spinner(size="1"), rx.icon(tag="map-pin", size=13)),
                                        rx.text("Validar", font_size="12px"),
                                        on_click=GlobalState.validate_ep_localizacao,
                                        disabled=GlobalState.ep_loc_validating,
                                        size="2", variant="soft", color_scheme="teal", cursor="pointer",
                                    ),
                                    spacing="2", width="100%",
                                ),
                                rx.cond(
                                    GlobalState.ep_loc_geocoded_name != "",
                                    rx.hstack(
                                        rx.icon(tag="map-pin", size=13, color=S.COPPER),
                                        rx.text("Encontrado: ", rx.text.span(GlobalState.ep_loc_geocoded_name, font_weight="700", color="white"), font_size="12px", color=S.TEXT_MUTED, flex="1"),
                                        rx.button(rx.icon(tag="check", size=12), "Confirmar", on_click=GlobalState.confirm_ep_localizacao, size="1", variant="solid", color_scheme="teal", cursor="pointer"),
                                        rx.button(rx.icon(tag="x", size=12), "Reescrever", on_click=GlobalState.reject_ep_localizacao, size="1", variant="soft", color_scheme="gray", cursor="pointer"),
                                        spacing="2", align="center",
                                        style={"background": "rgba(201,139,42,0.08)", "border": f"1px solid {S.COPPER}44", "borderRadius": S.R_CONTROL, "padding": "8px 12px"},
                                        width="100%",
                                    ),
                                    rx.fragment(),
                                ),
                                rx.cond(
                                    GlobalState.ep_loc_error != "",
                                    rx.hstack(rx.icon(tag="alert-circle", size=13, color="#EF4444"), rx.text(GlobalState.ep_loc_error, font_size="11px", color="#EF4444"), spacing="2", align="center"),
                                    rx.fragment(),
                                ),
                                spacing="1", width="100%",
                            ),
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    # Row 4: Terceirizado + Potência
                    rx.flex(
                        rx.vstack(
                            rx.text("Terceirizado / Parceiro", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_terceirizado,
                                on_blur=GlobalState.set_ep_terceirizado,
                                placeholder="Ex: Construtora ABC Ltda",
                                style=_INPUT_STYLE,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Potência (kWp)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_potencia_kwp,
                                on_blur=GlobalState.set_ep_potencia_kwp,
                                placeholder="Ex: 142,5",
                                type="text",
                                input_mode="decimal",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 5: Datas + Prazo
                    rx.flex(
                        rx.vstack(
                            rx.text("Data de Início", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_data_inicio,
                                on_change=GlobalState.set_ep_data_inicio,
                                type="date",
                                style={**_INPUT_STYLE, "colorScheme": "dark"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Data de Término", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_data_termino,
                                on_change=GlobalState.set_ep_data_termino,
                                type="date",
                                style={**_INPUT_STYLE, "colorScheme": "dark"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Prazo Contratual (dias)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_prazo_dias,
                                on_blur=GlobalState.set_ep_prazo_dias,
                                placeholder="Ex: 90",
                                type="text",
                                input_mode="numeric",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 6: Prioridade + Efetivo
                    rx.flex(
                        rx.vstack(
                            rx.text("Prioridade", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.select.root(
                                rx.select.trigger(style=_SELECT_TRIGGER_STYLE),
                                rx.select.content(
                                    rx.select.item("Alta",  value="Alta"),
                                    rx.select.item("Média", value="Média"),
                                    rx.select.item("Baixa", value="Baixa"),
                                    bg=S.BG_ELEVATED,
                                    border=f"1px solid {S.BORDER_SUBTLE}",
                                    z_index="9999",
                                    position="popper",
                                ),
                                value=GlobalState.ep_priority,
                                on_change=GlobalState.set_ep_priority,
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Efetivo Planejado (pessoas)", font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                            rx.el.input(
                                default_value=GlobalState.ep_efetivo_planejado,
                                on_blur=GlobalState.set_ep_efetivo_planejado,
                                placeholder="Ex: 12",
                                type="text",
                                input_mode="numeric",
                                style={**_INPUT_STYLE, "fontFamily": "var(--font-mono)"},
                            ),
                            spacing="1",
                            flex="1",
                        ),
                        gap="12px",
                        flex_wrap="wrap",
                        width="100%",
                    ),
                    # Row 7: Dias úteis da obra
                    _dias_uteis_picker(GlobalState.ep_dias_uteis, GlobalState.toggle_ep_dia),
                    spacing="4",
                    width="100%",
                    key=GlobalState.ep_form_key.to_string(),
                ),
                # Error
                rx.cond(
                    GlobalState.ep_error != "",
                    rx.text(GlobalState.ep_error, font_size="12px", color=S.DANGER),
                ),
                rx.divider(border_color=S.BORDER_SUBTLE),
                # ── Actions row: delete (left) + save (right) ─────────────────
                rx.hstack(
                    # Delete section
                    rx.cond(
                        GlobalState.ep_confirm_delete,
                        # Confirmation state
                        rx.hstack(
                            rx.text("Confirmar exclusão?", font_size="12px", color=S.DANGER, font_family=S.FONT_MONO),
                            rx.button(
                                rx.cond(
                                    GlobalState.ep_deleting,
                                    rx.spinner(size="2"),
                                    rx.text("Sim, excluir"),
                                ),
                                on_click=GlobalState.delete_projeto,
                                size="2",
                                disabled=GlobalState.ep_deleting,
                                style={
                                    "background": S.DANGER,
                                    "color": "#fff",
                                    "fontFamily": S.FONT_TECH,
                                    "fontWeight": "700",
                                    "cursor": "pointer",
                                },
                            ),
                            rx.button(
                                "Cancelar",
                                variant="ghost",
                                size="2",
                                cursor="pointer",
                                on_click=GlobalState.toggle_ep_confirm_delete,
                            ),
                            spacing="2",
                            align="center",
                        ),
                        # Normal state — show delete button
                        rx.icon_button(
                            rx.icon(tag="trash-2", size=14),
                            size="2",
                            variant="ghost",
                            on_click=GlobalState.toggle_ep_confirm_delete,
                            cursor="pointer",
                            color=S.DANGER,
                            _hover={"background": "rgba(239,68,68,0.1)"},
                        ),
                    ),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button(
                            "Cancelar",
                            variant="ghost",
                            size="2",
                            cursor="pointer",
                            on_click=GlobalState.close_edit_projeto,
                        )
                    ),
                    rx.button(
                        rx.cond(
                            GlobalState.ep_saving,
                            rx.spinner(size="2"),
                            rx.hstack(rx.icon(tag="save", size=13), rx.text("Salvar"), spacing="1"),
                        ),
                        on_click=GlobalState.save_edit_projeto,
                        size="2",
                        disabled=GlobalState.ep_saving,
                        style={
                            "background": S.COPPER,
                            "color": S.BG_VOID,
                            "fontFamily": S.FONT_TECH,
                            "fontWeight": "700",
                            "cursor": "pointer",
                        },
                    ),
                    justify="start",
                    spacing="2",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius=S.R_CARD,
            max_width="640px",
            width="95vw",
        ),
        open=GlobalState.show_edit_projeto,
        on_open_change=GlobalState.set_show_edit_projeto,
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════


def hub_operacoes_page() -> rx.Component:
    """
    Hub de Operações — unified project operations page.
    Route: /hub
    """
    return rx.box(
        _duplicar_projeto_dialog(),
        _novo_projeto_dialog(),
        _edit_projeto_dialog(),
        rx.cond(
            GlobalState.is_loading,
            page_loading_skeleton(),
            rx.cond(
                GlobalState.selected_project != "",
                # Detail view — project selected
                rx.vstack(
                    hub_project_detail(),
                    width="100%",
                    spacing="6",
                    class_name="animate-enter",
                    on_mount=lambda: GlobalState.set_current_path("/hub"),
                ),
                # Landing — pulse card grid
                rx.vstack(
                    hub_landing_page(),
                    width="100%",
                    spacing="6",
                    class_name="animate-enter",
                    on_mount=lambda: GlobalState.set_current_path("/hub"),
                ),
            ),
        ),
        width="100%",
        class_name="hub-content",
    )
