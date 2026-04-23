"""
Página de Observabilidade LLM — Token usage, custo estimado, erros de tools.
Rota: /admin/observabilidade — Administrador only.
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.observability_state import ObservabilityState


# ── Stat Card ─────────────────────────────────────────────────────────────────

def _stat_card(icon: str, label: str, value, color: str = S.COPPER, sub: str = "") -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(tag=icon, size=16, color=color),
                    width="34px",
                    height="34px",
                    border_radius="50%",
                    bg=f"rgba({_hex_to_rgb(color)}, 0.12)",
                ),
                rx.text(label, font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_TECH,
                        letter_spacing="0.08em", text_transform="uppercase"),
                spacing="2",
                align="center",
            ),
            rx.text(
                value,
                font_size="28px",
                font_weight="700",
                color=color,
                font_family=S.FONT_DISPLAY,
                letter_spacing="-0.02em",
                line_height="1",
            ),
            rx.cond(
                sub != "",
                rx.text(sub, font_size="11px", color=S.TEXT_MUTED),
            ),
            spacing="2",
            align="start",
        ),
        bg="rgba(255,255,255,0.02)",
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_top=f"2px solid {color}",
        border_radius="12px",
        padding="20px",
        flex="1",
        min_width="160px",
    )


def _hex_to_rgb(hex_color: str) -> str:
    """Convert hex color to RGB string for rgba()."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r}, {g}, {b}"
    return "201, 139, 42"  # fallback copper


# ── Model Breakdown Row ───────────────────────────────────────────────────────

def _model_row(item: dict) -> rx.Component:
    return rx.hstack(
        rx.box(
            width="10px",
            height="10px",
            border_radius="50%",
            bg=item["color"],
            flex_shrink="0",
        ),
        rx.text(item["model"], font_family=S.FONT_MONO, font_size="12px", color=S.TEXT_PRIMARY, flex="1"),
        rx.text(item["calls"], font_size="12px", color=S.TEXT_MUTED, width="60px", text_align="right"),
        rx.text(item["tokens"], font_family=S.FONT_MONO, font_size="12px", color=S.TEXT_SECONDARY, width="90px", text_align="right"),
        rx.text(item["cost"], font_family=S.FONT_MONO, font_size="12px", color=S.COPPER_LIGHT, font_weight="600", width="80px", text_align="right"),
        spacing="3",
        align="center",
        padding_y="8px",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
    )


# ── Log Row ───────────────────────────────────────────────────────────────────

def _log_row(row: dict) -> rx.Component:
    return rx.hstack(
        # Status dot
        rx.box(
            width="8px",
            height="8px",
            border_radius="50%",
            bg=rx.cond(row["has_error"] == "true", S.DANGER, S.SUCCESS),
            flex_shrink="0",
        ),
        # Timestamp
        rx.text(row["created_at"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                width="130px", flex_shrink="0"),
        # User
        rx.text(row["username"], font_size="12px", color=S.TEXT_SECONDARY, width="100px",
                flex_shrink="0", overflow="hidden", text_overflow="ellipsis", white_space="nowrap"),
        # Model badge
        rx.el.span(
            row["model"],
            style={
                "fontSize": "10px",
                "fontFamily": S.FONT_MONO,
                "color": row["model_color"],
                "background": "rgba(201,139,42,0.08)",
                "border": f"1px solid rgba(201,139,42,0.2)",
                "borderRadius": "4px",
                "padding": "2px 6px",
                "whiteSpace": "nowrap",
                "flexShrink": "0",
            },
        ),
        # Call type
        rx.text(row["call_type"], font_size="11px", color=S.TEXT_MUTED, width="60px", flex_shrink="0"),
        # Tokens
        rx.text(row["total_tokens"], font_family=S.FONT_MONO, font_size="12px",
                color=S.TEXT_SECONDARY, width="70px", text_align="right", flex_shrink="0"),
        # Cost
        rx.text(row["cost_usd"], font_family=S.FONT_MONO, font_size="12px",
                color=S.COPPER_LIGHT, font_weight="600", width="80px", text_align="right", flex_shrink="0"),
        # Duration
        rx.text(
            rx.cond(row["duration_ms"] != "0", row["duration_ms"], "—"),
            font_size="11px", color=S.TEXT_MUTED, width="60px", text_align="right", flex_shrink="0",
        ),
        # Tool names
        rx.text(row["tool_names"], font_size="11px", color=S.TEXT_MUTED, flex="1",
                overflow="hidden", text_overflow="ellipsis", white_space="nowrap"),
        # Error badge
        rx.cond(
            row["has_error"] == "true",
            rx.el.span(
                "ERRO",
                style={
                    "fontSize": "9px",
                    "fontFamily": S.FONT_TECH,
                    "fontWeight": "700",
                    "letterSpacing": "0.08em",
                    "color": S.DANGER,
                    "background": "rgba(239,68,68,0.1)",
                    "border": "1px solid rgba(239,68,68,0.3)",
                    "borderRadius": "4px",
                    "padding": "2px 5px",
                    "flexShrink": "0",
                },
            ),
        ),
        on_click=ObservabilityState.open_detail(row),
        cursor="pointer",
        spacing="3",
        align="center",
        padding_x="16px",
        padding_y="10px",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
        _hover={"bg": "rgba(255,255,255,0.025)"},
        transition="background 0.15s ease",
        width="100%",
    )


# ── Detail Drawer ─────────────────────────────────────────────────────────────

def _detail_drawer() -> rx.Component:
    row = ObservabilityState.selected_row
    return rx.cond(
        ObservabilityState.show_detail,
        rx.box(
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Detalhe", size="3", color=S.COPPER, font_family=S.FONT_TECH),
                        rx.spacer(),
                        rx.icon_button(
                            rx.icon(tag="x", size=14),
                            on_click=ObservabilityState.close_detail,
                            variant="ghost",
                            color=S.TEXT_MUTED,
                        ),
                        width="100%",
                        align="center",
                    ),
                    rx.divider(color_scheme="gray", opacity="0.2"),
                    rx.vstack(
                        _detail_row("Timestamp", row["created_at"]),
                        _detail_row("Usuário", row["username"]),
                        _detail_row("Modelo", row["model"]),
                        _detail_row("Tipo", row["call_type"]),
                        _detail_row("Prompt tokens", row["prompt_tokens"]),
                        _detail_row("Completion tokens", row["completion_tokens"]),
                        _detail_row("Total tokens", row["total_tokens"]),
                        _detail_row("Custo estimado", row["cost_usd"]),
                        _detail_row("Duração", row["duration_ms"]),
                        _detail_row("Tools usadas", row["tool_names"]),
                        rx.cond(
                            row["has_error"] == "true",
                            rx.box(
                                rx.text("Erro:", font_size="11px", color=S.TEXT_MUTED, margin_bottom="4px"),
                                rx.text(row["error"], font_family=S.FONT_MONO, font_size="11px",
                                        color=S.DANGER, word_break="break-all"),
                                bg="rgba(239,68,68,0.06)",
                                border="1px solid rgba(239,68,68,0.2)",
                                border_radius="8px",
                                padding="12px",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    spacing="4",
                    width="100%",
                ),
                bg="rgba(10,31,26,0.98)",
                backdrop_filter="blur(20px)",
                border_left=f"1px solid {S.BORDER_ACCENT}",
                padding="24px",
                width="340px",
                height="100vh",
                overflow_y="auto",
                position="fixed",
                top="0",
                right="0",
                z_index="9999",
            ),
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            bg="rgba(0,0,0,0.4)",
            z_index="9998",
            on_click=ObservabilityState.close_detail,
        ),
    )


def _detail_row(label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label + ":", font_size="11px", color=S.TEXT_MUTED, width="130px", flex_shrink="0"),
        rx.text(value, font_family=S.FONT_MONO, font_size="12px", color=S.TEXT_PRIMARY,
                word_break="break-all"),
        spacing="2",
        align="start",
        width="100%",
    )


# ── Table Header ─────────────────────────────────────────────────────────────

def _table_header() -> rx.Component:
    th_style = {
        "fontSize": "10px",
        "fontFamily": S.FONT_TECH,
        "fontWeight": "700",
        "letterSpacing": "0.1em",
        "textTransform": "uppercase",
        "color": S.COPPER_LIGHT,
        "padding": "10px 0",
        "borderBottom": f"2px solid rgba(201,139,42,0.25)",
        "whiteSpace": "nowrap",
    }
    return rx.hstack(
        rx.box(width="8px", flex_shrink="0"),
        rx.el.span("Status", style={**th_style, "width": "8px"}),
        rx.el.span("Timestamp", style={**th_style, "width": "130px"}),
        rx.el.span("Usuário", style={**th_style, "width": "100px"}),
        rx.el.span("Modelo", style={**th_style, "width": "120px"}),
        rx.el.span("Tipo", style={**th_style, "width": "60px"}),
        rx.el.span("Tokens", style={**th_style, "width": "70px", "textAlign": "right"}),
        rx.el.span("Custo", style={**th_style, "width": "80px", "textAlign": "right"}),
        rx.el.span("Duração", style={**th_style, "width": "60px", "textAlign": "right"}),
        rx.el.span("Tools", style={**th_style, "flex": "1"}),
        padding_x="16px",
        width="100%",
        spacing="3",
        align="center",
    )


# ── Main Page ─────────────────────────────────────────────────────────────────

def observabilidade_page() -> rx.Component:
    return rx.box(
        _detail_drawer(),
        rx.vstack(
            # ── Page Header ───────────────────────────────────────────────
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="activity", size=20, color=S.COPPER),
                        rx.heading(
                            "OBSERVABILIDADE LLM",
                            size="6",
                            font_family=S.FONT_TECH,
                            color=S.TEXT_PRIMARY,
                            letter_spacing="0.06em",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(
                        "Tokens consumidos · Custo estimado · Erros de tools · Latência",
                        font_size="13px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="refresh-cw", size=14),
                    rx.text("Atualizar", font_size="13px"),
                    on_click=ObservabilityState.load_page,
                    variant="ghost",
                    color=S.COPPER,
                    border=f"1px solid {S.BORDER_ACCENT}",
                    border_radius="8px",
                    padding_x="14px",
                    padding_y="8px",
                    cursor="pointer",
                    spacing="2",
                ),
                width="100%",
                align="center",
            ),

            # ── KPI Stats Row ─────────────────────────────────────────────
            rx.flex(
                _stat_card("zap", "Total de Chamadas", ObservabilityState.stat_total_calls, S.COPPER),
                _stat_card("coins", "Custo Total Est.", ObservabilityState.stat_total_cost, S.PATINA),
                _stat_card("hash", "Tokens Totais", ObservabilityState.stat_total_tokens, S.INFO),
                _stat_card("alert-triangle", "Erros", ObservabilityState.stat_errors, S.DANGER),
                _stat_card("timer", "Latência Média", ObservabilityState.stat_avg_duration, S.WARNING, sub="ms avg"),
                gap="16px",
                flex_wrap="wrap",
                width="100%",
            ),

            # ── Model Breakdown + Filters ────────────────────────────────
            rx.flex(
                # Model breakdown card
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="pie-chart", size=14, color=S.COPPER),
                            rx.text("Por Modelo", font_size="13px", font_family=S.FONT_TECH,
                                    color=S.TEXT_SECONDARY, letter_spacing="0.06em", text_transform="uppercase"),
                            spacing="2",
                            align="center",
                        ),
                        rx.box(
                            rx.hstack(
                                rx.text("Modelo", font_size="10px", color=S.COPPER_LIGHT, flex="1"),
                                rx.text("Calls", font_size="10px", color=S.COPPER_LIGHT, width="60px", text_align="right"),
                                rx.text("Tokens", font_size="10px", color=S.COPPER_LIGHT, width="90px", text_align="right"),
                                rx.text("Custo", font_size="10px", color=S.COPPER_LIGHT, width="80px", text_align="right"),
                                padding_y="6px",
                                border_bottom=f"1px solid {S.BORDER_ACCENT}",
                                spacing="3",
                                align="center",
                            ),
                        ),
                        rx.foreach(
                            ObservabilityState.model_breakdown,
                            _model_row,
                        ),
                        spacing="0",
                        width="100%",
                    ),
                    bg="rgba(255,255,255,0.02)",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    border_radius="12px",
                    padding="20px",
                    min_width="380px",
                    flex="0 0 380px",
                ),

                # Filters card
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="filter", size=14, color=S.COPPER),
                            rx.text("Filtros", font_size="13px", font_family=S.FONT_TECH,
                                    color=S.TEXT_SECONDARY, letter_spacing="0.06em", text_transform="uppercase"),
                            spacing="2",
                            align="center",
                        ),
                        rx.vstack(
                            rx.text("Modelo", font_size="11px", color=S.TEXT_MUTED),
                            rx.select.root(
                                rx.select.trigger(
                                    placeholder="Todos",
                                    style=_select_style(),
                                ),
                                rx.select.content(
                                    rx.select.item("Todos", value="__all__"),
                                    rx.select.item("gpt-4o", value="gpt-4o"),
                                    rx.select.item("gpt-4o-mini", value="gpt-4o-mini"),
                                    rx.select.item("gpt-4-turbo", value="gpt-4-turbo"),
                                    rx.select.item("gpt-3.5-turbo", value="gpt-3.5-turbo"),
                                    rx.select.item("whisper-1", value="whisper-1"),
                                    rx.select.item("tts-1", value="tts-1"),
                                    bg=S.BG_DEPTH,
                                ),
                                on_change=ObservabilityState.set_filter_model,
                                value=ObservabilityState.filter_model,
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text("Tipo de Chamada", font_size="11px", color=S.TEXT_MUTED),
                            rx.select.root(
                                rx.select.trigger(
                                    placeholder="Todos",
                                    style=_select_style(),
                                ),
                                rx.select.content(
                                    rx.select.item("Todos", value="__all__"),
                                    rx.select.item("agentic", value="agentic"),
                                    rx.select.item("stream", value="stream"),
                                    rx.select.item("query", value="query"),
                                    bg=S.BG_DEPTH,
                                ),
                                on_change=ObservabilityState.set_filter_call_type,
                                value=ObservabilityState.filter_call_type,
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.switch(
                                checked=ObservabilityState.filter_errors_only,
                                on_change=lambda _: ObservabilityState.toggle_errors_only(),
                                color_scheme="red",
                            ),
                            rx.text("Apenas Erros", font_size="12px", color=S.TEXT_SECONDARY),
                            spacing="2",
                            align="center",
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    bg="rgba(255,255,255,0.02)",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    border_radius="12px",
                    padding="20px",
                    flex="1",
                ),
                gap="16px",
                width="100%",
                flex_wrap="wrap",
                align="start",
            ),

            # ── Log Table ────────────────────────────────────────────────
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="table", size=14, color=S.COPPER),
                        rx.text("Log de Chamadas", font_size="13px", font_family=S.FONT_TECH,
                                color=S.TEXT_SECONDARY, letter_spacing="0.06em", text_transform="uppercase"),
                        rx.spacer(),
                        rx.text(ObservabilityState.page_info, font_size="12px", color=S.TEXT_MUTED),
                        spacing="2",
                        align="center",
                        width="100%",
                    ),
                    _table_header(),
                    rx.cond(
                        ObservabilityState.is_loading,
                        rx.center(
                            rx.spinner(color=S.COPPER, size="3"),
                            padding_y="40px",
                            width="100%",
                        ),
                        rx.scroll_area(
                            rx.foreach(
                                ObservabilityState.rows,
                                _log_row,
                            ),
                            max_height="500px",
                            type="hover",
                            scrollbars="vertical",
                            width="100%",
                        ),
                    ),
                    # Pagination
                    rx.hstack(
                        rx.button(
                            rx.icon(tag="chevron-left", size=14),
                            on_click=ObservabilityState.prev_page,
                            is_disabled=~ObservabilityState.has_prev,
                            variant="ghost",
                            color=S.TEXT_MUTED,
                        ),
                        rx.text(ObservabilityState.page_info, font_size="12px", color=S.TEXT_MUTED),
                        rx.button(
                            rx.icon(tag="chevron-right", size=14),
                            on_click=ObservabilityState.next_page,
                            is_disabled=~ObservabilityState.has_next,
                            variant="ghost",
                            color=S.TEXT_MUTED,
                        ),
                        justify="center",
                        spacing="4",
                        width="100%",
                        padding_top="12px",
                    ),
                    spacing="0",
                    width="100%",
                ),
                bg="rgba(255,255,255,0.02)",
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius="12px",
                padding="20px",
                width="100%",
                overflow_x="auto",
            ),

            spacing="6",
            width="100%",
            padding="28px",
            max_width="1400px",
            margin="0 auto",
        ),
    )


def _select_style() -> dict:
    return {
        "background": "rgba(255,255,255,0.04)",
        "border": f"1px solid {S.BORDER_SUBTLE}",
        "borderRadius": "8px",
        "color": S.TEXT_PRIMARY,
        "fontSize": "13px",
        "width": "100%",
    }
