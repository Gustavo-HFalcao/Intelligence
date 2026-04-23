"""
Logs & Auditoria — Bomtempo Intelligence
=========================================
Página de rastreabilidade total: quem fez o quê, quando e com qual resultado.
- KPI cards de atividade do dia
- Filtros por categoria (chips), status, usuário, busca, data
- Tabela paginada server-side (50 linhas/página)
- Painel lateral de detalhe (metadata JSON)
"""
from __future__ import annotations

import reflex as rx

from bomtempo.components.skeletons import page_centered_loader, table_skeleton
from bomtempo.core import styles as S
from bomtempo.core.audit_logger import (
    ALL_CATEGORIES,
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    AuditCategory,
)
from bomtempo.state.global_state import GlobalState
from bomtempo.state.logs_state import LogsState

# ── Helpers ───────────────────────────────────────────────────────────────────


def _label(text: str) -> rx.Component:
    return rx.text(
        text,
        font_family=S.FONT_TECH,
        font_size="0.62rem",
        font_weight="700",
        color=S.TEXT_MUTED,
        letter_spacing="0.18em",
        text_transform="uppercase",
    )


def _glass_card(*children, **props) -> rx.Component:
    props.setdefault("padding", "20px")
    return rx.box(
        *children,
        bg=S.BG_GLASS,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="16px",
        backdrop_filter="blur(16px)",
        **props,
    )


# ── KPI Stats ─────────────────────────────────────────────────────────────────


def _stat_card(label: str, value: rx.Var, icon: str, color: str, bg: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(tag=icon, size=18, color=color),
                    width="36px",
                    height="36px",
                    border_radius="10px",
                    bg=bg,
                ),
                rx.spacer(),
                spacing="0",
                align="center",
                width="100%",
            ),
            rx.text(
                value,
                font_family=S.FONT_TECH,
                font_size="2rem",
                font_weight="900",
                color=color,
                line_height="1",
                margin_top="12px",
            ),
            rx.text(
                label,
                font_family=S.FONT_BODY,
                font_size="0.8rem",
                color=S.TEXT_MUTED,
                margin_top="4px",
            ),
            spacing="0",
            align="start",
        ),
        bg=S.BG_GLASS,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="16px",
        backdrop_filter="blur(12px)",
        padding="20px",
        flex="1",
    )


def _stats_row() -> rx.Component:
    return rx.hstack(
        _stat_card(
            "Eventos Hoje",
            LogsState.stat_total_today,
            "activity",
            S.COPPER,
            S.COPPER_GLOW,
        ),
        _stat_card(
            "Logins",
            LogsState.stat_logins_today,
            "log-in",
            S.PATINA,
            S.PATINA_GLOW,
        ),
        _stat_card(
            "Edições de Dados",
            LogsState.stat_edits_today,
            "edit-3",
            S.WARNING,
            S.WARNING_BG,
        ),
        _stat_card(
            "Erros Capturados",
            LogsState.stat_errors_today,
            "alert-triangle",
            S.DANGER,
            S.DANGER_BG,
        ),
        spacing="4",
        flex_wrap="wrap",
        width="100%",
    )


# ── Category chip filter ───────────────────────────────────────────────────────


def _cat_chip(cat: str) -> rx.Component:
    color = CATEGORY_COLORS.get(cat, "#889999")
    label = CATEGORY_LABELS.get(cat, cat)
    is_active = LogsState.filter_category == cat

    return rx.box(
        rx.text(
            label,
            font_family=S.FONT_TECH,
            font_size="0.72rem",
            font_weight="700",
            letter_spacing="0.04em",
            white_space="nowrap",
        ),
        padding_x="10px",
        padding_y="5px",
        border_radius="20px",
        cursor="pointer",
        transition="all 0.15s ease",
        color=rx.cond(is_active, "#fff", S.TEXT_MUTED),
        bg=rx.cond(is_active, f"{color}22", "transparent"),
        border=rx.cond(is_active, f"1px solid {color}", f"1px solid {S.BORDER_SUBTLE}"),
        on_click=LogsState.set_filter_category(cat),
        _hover={"border_color": color, "color": "#fff"},
    )


def _filter_bar() -> rx.Component:
    return _glass_card(
        rx.vstack(
            # Row 1: category chips
            rx.vstack(
                _label("Categoria"),
                rx.hstack(
                    # "Todos" chip
                    rx.box(
                        rx.text(
                            "Todos",
                            font_family=S.FONT_TECH,
                            font_size="0.72rem",
                            font_weight="700",
                            letter_spacing="0.04em",
                            white_space="nowrap",
                        ),
                        padding_x="10px",
                        padding_y="5px",
                        border_radius="20px",
                        cursor="pointer",
                        color=rx.cond(LogsState.filter_category == "", "#fff", S.TEXT_MUTED),
                        bg=rx.cond(LogsState.filter_category == "", f"{S.COPPER}22", "transparent"),
                        border=rx.cond(
                            LogsState.filter_category == "",
                            f"1px solid {S.COPPER}",
                            f"1px solid {S.BORDER_SUBTLE}",
                        ),
                        on_click=LogsState.set_filter_category(""),
                        _hover={"border_color": S.COPPER, "color": "#fff"},
                        transition="all 0.15s ease",
                    ),
                    *[_cat_chip(c) for c in ALL_CATEGORIES],
                    wrap="wrap",
                    spacing="2",
                ),
                spacing="2",
                align="start",
            ),
            # Row 2: text inputs + status + date
            rx.hstack(
                rx.vstack(
                    _label("Usuário"),
                    rx.input(
                        placeholder="Filtrar por usuário...",
                        value=LogsState.filter_username,
                        on_change=LogsState.set_filter_username,
                        debounce_timeout=400,
                        bg=S.BG_INPUT,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="10px",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_BODY,
                        font_size="0.85rem",
                        padding_x="12px",
                        height="38px",
                        _focus={"border_color": S.COPPER, "outline": "none"},
                    ),
                    spacing="2",
                    flex="1",
                ),
                rx.vstack(
                    _label("Buscar ação"),
                    rx.input(
                        placeholder="Pesquisar na descrição...",
                        value=LogsState.filter_search,
                        on_change=LogsState.set_filter_search,
                        debounce_timeout=400,
                        bg=S.BG_INPUT,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="10px",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_BODY,
                        font_size="0.85rem",
                        padding_x="12px",
                        height="38px",
                        _focus={"border_color": S.COPPER, "outline": "none"},
                    ),
                    spacing="2",
                    flex="2",
                ),
                rx.vstack(
                    _label("Status"),
                    rx.select(
                        ["Todos", "success", "error", "warning"],
                        value=rx.cond(LogsState.filter_status == "", "Todos", LogsState.filter_status),
                        on_change=lambda v: LogsState.set_filter_status(
                            rx.cond(v == "Todos", "", v)
                        ),
                        bg=S.BG_INPUT,
                        color=S.TEXT_PRIMARY,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="10px",
                        height="38px",
                        font_family=S.FONT_BODY,
                        font_size="0.85rem",
                    ),
                    spacing="2",
                    flex="1",
                ),
                rx.vstack(
                    _label("A partir de"),
                    rx.input(
                        type="date",
                        value=LogsState.filter_date_from,
                        on_change=LogsState.set_filter_date_from,
                        bg=S.BG_INPUT,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="10px",
                        color=S.TEXT_PRIMARY,
                        font_family=S.FONT_BODY,
                        font_size="0.85rem",
                        padding_x="12px",
                        height="38px",
                        _focus={"border_color": S.COPPER, "outline": "none"},
                    ),
                    spacing="2",
                    flex="1",
                ),
                # Action buttons
                rx.vstack(
                    rx.text(" ", font_size="0.62rem"),  # spacer for alignment
                    rx.hstack(
                        rx.button(
                            rx.icon(tag="search", size=16),
                            "Buscar",
                            on_click=LogsState.apply_filters,
                            bg=S.COPPER,
                            color="#000",
                            border_radius="10px",
                            height="38px",
                            padding_x="14px",
                            font_family=S.FONT_TECH,
                            font_weight="700",
                            font_size="0.8rem",
                            cursor="pointer",
                            _hover={"bg": S.COPPER_LIGHT},
                        ),
                        rx.cond(
                            LogsState.active_filter_count > 0,
                            rx.button(
                                rx.icon(tag="x", size=16),
                                on_click=LogsState.clear_filters,
                                bg="transparent",
                                color=S.TEXT_MUTED,
                                border=f"1px solid {S.BORDER_SUBTLE}",
                                border_radius="10px",
                                height="38px",
                                padding_x="12px",
                                cursor="pointer",
                                _hover={"border_color": S.DANGER, "color": S.DANGER},
                            ),
                        ),
                        spacing="2",
                    ),
                    spacing="2",
                ),
                spacing="4",
                align="end",
                flex_wrap="wrap",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        width="100%",
        margin_bottom="0",
    )


# ── Status badge ───────────────────────────────────────────────────────────────


def _status_badge(status: rx.Var) -> rx.Component:
    color = rx.cond(
        status == "success",
        S.SUCCESS,
        rx.cond(status == "error", S.DANGER, S.WARNING),
    )
    bg = rx.cond(
        status == "success",
        S.SUCCESS_BG,
        rx.cond(status == "error", S.DANGER_BG, S.WARNING_BG),
    )
    icon = rx.cond(
        status == "success",
        "check-circle",
        rx.cond(status == "error", "x-circle", "alert-circle"),
    )
    return rx.hstack(
        rx.icon(tag=icon, size=12, color=color),
        rx.text(status, font_family=S.FONT_TECH, font_size="0.72rem", font_weight="700", color=color),
        bg=bg,
        border=rx.cond(
            status == "success",
            f"1px solid {S.SUCCESS}44",
            rx.cond(status == "error", f"1px solid {S.DANGER}44", f"1px solid {S.WARNING}44"),
        ),
        border_radius="20px",
        padding_x="8px",
        padding_y="3px",
        align="center",
        spacing="1",
    )


# ── Log row ───────────────────────────────────────────────────────────────────


def _log_row(row: dict) -> rx.Component:
    cat_color = row["category_color"]
    return rx.box(
        rx.hstack(
            # Timestamp
            rx.text(
                row["created_at"],
                font_family=S.FONT_MONO,
                font_size="0.78rem",
                color=S.TEXT_MUTED,
                min_width="90px",
                white_space="nowrap",
            ),
            # Category badge
            rx.box(
                rx.text(
                    row["category_label"],
                    font_family=S.FONT_TECH,
                    font_size="0.7rem",
                    font_weight="700",
                    color=cat_color,
                    white_space="nowrap",
                ),
                bg=f"{cat_color}18",
                border=f"1px solid {cat_color}44",
                border_radius="20px",
                padding_x="8px",
                padding_y="3px",
                min_width="130px",
                text_align="center",
            ),
            # Username
            rx.hstack(
                rx.icon(tag="user", size=13, color=S.TEXT_MUTED),
                rx.text(
                    row["username"],
                    font_family=S.FONT_BODY,
                    font_size="0.82rem",
                    color=S.TEXT_SECONDARY,
                    white_space="nowrap",
                    max_width="100px",
                    overflow="hidden",
                    text_overflow="ellipsis",
                ),
                spacing="1",
                align="center",
                min_width="110px",
            ),
            # Action description
            rx.text(
                row["action"],
                font_family=S.FONT_BODY,
                font_size="0.85rem",
                color=S.TEXT_PRIMARY,
                flex="1",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            # Entity
            rx.cond(
                row["entity_type"] != "",
                rx.hstack(
                    rx.icon(tag="database", size=12, color=S.TEXT_MUTED),
                    rx.text(
                        row["entity_type"],
                        font_family=S.FONT_MONO,
                        font_size="0.72rem",
                        color=S.TEXT_MUTED,
                        white_space="nowrap",
                    ),
                    spacing="1",
                    align="center",
                    min_width="90px",
                ),
            ),
            # Status
            _status_badge(row["status"]),
            # Detail button
            rx.icon(
                tag="chevron-right",
                size=16,
                color=S.TEXT_MUTED,
                cursor="pointer",
                opacity="0.4",
                _group_hover={"opacity": "1", "color": S.COPPER},
                transition="all 0.15s ease",
                on_click=LogsState.open_detail(row),
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        padding_x="16px",
        padding_y="12px",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
        _hover={"bg": "rgba(255,255,255,0.02)", "cursor": "pointer"},
        transition="background 0.15s ease",
        width="100%",
        role="group",
        on_click=LogsState.open_detail(row),
    )


# ── Table ─────────────────────────────────────────────────────────────────────


def _table_header() -> rx.Component:
    def _th(text: str, min_w: str = "") -> rx.Component:
        return rx.text(
            text,
            font_family=S.FONT_TECH,
            font_size="0.65rem",
            font_weight="700",
            color=S.TEXT_MUTED,
            letter_spacing="0.15em",
            text_transform="uppercase",
            white_space="nowrap",
            min_width=min_w if min_w else "auto",
        )

    return rx.hstack(
        _th("Horário", "90px"),
        _th("Categoria", "130px"),
        _th("Usuário", "110px"),
        _th("Ação", ""),
        _th("Entidade", "90px"),
        _th("Status"),
        rx.spacer(),
        spacing="3",
        align="center",
        padding_x="16px",
        padding_y="10px",
        border_bottom=f"1px solid {S.BORDER_ACCENT}",
        width="100%",
    )


def _logs_table() -> rx.Component:
    return _glass_card(
        rx.vstack(
            # Table header
            _table_header(),
            # Rows
            rx.cond(
                LogsState.is_loading,
                page_centered_loader(
                    "CARREGANDO LOGS",
                    "Verificando registros e eventos de auditoria...",
                    "shield-check",
                    border="none",
                    border_radius="0",
                    background="transparent",
                    min_height="280px",
                ),
                rx.cond(
                    LogsState.logs.length() == 0,
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="search-x", size=48, color=S.TEXT_MUTED, opacity="0.3"),
                            rx.text(
                                "Nenhum log encontrado",
                                font_family=S.FONT_TECH,
                                font_size="1rem",
                                font_weight="700",
                                color=S.TEXT_MUTED,
                                letter_spacing="0.05em",
                            ),
                            rx.text(
                                "Ajuste os filtros ou aguarde novos eventos ser registrados.",
                                font_family=S.FONT_BODY,
                                font_size="0.85rem",
                                color=S.TEXT_MUTED,
                                opacity="0.6",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        padding_y="60px",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.foreach(LogsState.logs, _log_row),
                        spacing="0",
                        width="100%",
                    ),
                ),
            ),
            spacing="0",
            width="100%",
            min_width="600px",
        ),
        padding="0",
        overflow_x="auto",
        overflow_y="hidden",
        width="100%",
    )


# ── Pagination ─────────────────────────────────────────────────────────────────


def _pagination() -> rx.Component:
    return rx.hstack(
        rx.text(
            LogsState.page_info,
            font_family=S.FONT_BODY,
            font_size="0.85rem",
            color=S.TEXT_MUTED,
        ),
        rx.spacer(),
        rx.hstack(
            rx.button(
                rx.icon(tag="chevron-left", size=16),
                on_click=LogsState.go_prev,
                disabled=~LogsState.has_prev,
                bg="transparent",
                color=rx.cond(LogsState.has_prev, S.TEXT_PRIMARY, S.TEXT_MUTED),
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius="8px",
                width="36px",
                height="36px",
                cursor=rx.cond(LogsState.has_prev, "pointer", "default"),
                _hover=rx.cond(
                    LogsState.has_prev,
                    {"border_color": S.COPPER, "color": S.COPPER},
                    {},
                ),
            ),
            rx.text(
                LogsState.page.to_string() + " / " + LogsState.total_pages.to_string(),
                font_family=S.FONT_MONO,
                font_size="0.85rem",
                color=S.TEXT_SECONDARY,
                padding_x="8px",
            ),
            rx.button(
                rx.icon(tag="chevron-right", size=16),
                on_click=LogsState.go_next,
                disabled=~LogsState.has_next,
                bg="transparent",
                color=rx.cond(LogsState.has_next, S.TEXT_PRIMARY, S.TEXT_MUTED),
                border=f"1px solid {S.BORDER_SUBTLE}",
                border_radius="8px",
                width="36px",
                height="36px",
                cursor=rx.cond(LogsState.has_next, "pointer", "default"),
                _hover=rx.cond(
                    LogsState.has_next,
                    {"border_color": S.COPPER, "color": S.COPPER},
                    {},
                ),
            ),
            spacing="2",
            align="center",
        ),
        align="center",
        width="100%",
        padding_y="8px",
    )


# ── Detail side panel ─────────────────────────────────────────────────────────


def _detail_panel() -> rx.Component:
    row = LogsState.detail_row
    return rx.cond(
        LogsState.detail_open,
        rx.box(
            rx.box(
                # Backdrop
                position="fixed",
                top="calc(52px + env(safe-area-inset-top, 0px))",
                left="0",
                width="100vw",
                height="calc(100vh - 52px - env(safe-area-inset-top, 0px))",
                bg="rgba(0,0,0,0.5)",
                z_index="100",
                on_click=LogsState.close_detail,
            ),
            # Panel
            rx.box(
                rx.vstack(
                    # Header
                    rx.hstack(
                        rx.hstack(
                            rx.icon(tag="file-search", size=20, color=S.COPPER),
                            rx.text(
                                "Detalhes do Evento",
                                font_family=S.FONT_TECH,
                                font_size="1.1rem",
                                font_weight="700",
                                color=S.TEXT_PRIMARY,
                                letter_spacing="0.05em",
                            ),
                            spacing="3",
                            align="center",
                        ),
                        rx.spacer(),
                        rx.icon(
                            tag="x",
                            size=20,
                            color=S.TEXT_MUTED,
                            cursor="pointer",
                            on_click=LogsState.close_detail,
                            _hover={"color": S.DANGER},
                        ),
                        align="center",
                        width="100%",
                    ),
                    rx.divider(border_color=S.BORDER_SUBTLE, margin_y="4px"),
                    # Fields
                    rx.vstack(
                        _detail_field("Horário", row.get("created_at_raw", ""), "clock"),
                        _detail_field("Categoria", row.get("category_label", ""), "tag"),
                        _detail_field("Usuário", row.get("username", ""), "user"),
                        _detail_field("Status", row.get("status", ""), "activity"),
                        _detail_field("Entidade", row.get("entity_type", ""), "database"),
                        _detail_field("ID da Entidade", row.get("entity_id", ""), "hash"),
                        _detail_field("IP", row.get("ip_address", ""), "globe"),
                        spacing="3",
                        align="start",
                        width="100%",
                    ),
                    # Action
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="align-left", size=14, color=S.TEXT_MUTED),
                            _label("Descrição"),
                            spacing="2",
                            align="center",
                        ),
                        rx.box(
                            rx.text(
                                row.get("action", ""),
                                font_family=S.FONT_BODY,
                                font_size="0.9rem",
                                color=S.TEXT_PRIMARY,
                                white_space="pre-wrap",
                                word_break="break-word",
                            ),
                            bg=S.BG_INPUT,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            border_radius="10px",
                            padding="12px",
                            width="100%",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    # Metadata JSON
                    rx.cond(
                        row.get("metadata_str", "") != "",
                        rx.vstack(
                            rx.hstack(
                                rx.icon(tag="braces", size=14, color=S.TEXT_MUTED),
                                _label("Metadata (JSON)"),
                                spacing="2",
                                align="center",
                            ),
                            rx.box(
                                rx.text(
                                    row.get("metadata_str", ""),
                                    font_family=S.FONT_MONO,
                                    font_size="0.78rem",
                                    color=S.PATINA,
                                    white_space="pre-wrap",
                                    word_break="break-all",
                                ),
                                bg="rgba(42,157,143,0.05)",
                                border=f"1px solid {S.PATINA}33",
                                border_radius="10px",
                                padding="12px",
                                width="100%",
                                max_height="300px",
                                overflow_y="auto",
                            ),
                            spacing="2",
                            align="start",
                            width="100%",
                        ),
                    ),
                    spacing="4",
                    align="start",
                    width="100%",
                    padding="24px",
                    overflow_y="auto",
                    height="100%",
                ),
                position="fixed",
                top="calc(52px + env(safe-area-inset-top, 0px))",
                right="0",
                width="420px",
                height="calc(100vh - 52px - env(safe-area-inset-top, 0px))",
                bg=S.BG_ELEVATED,
                border_left=f"1px solid {S.BORDER_ACCENT}",
                border_top=f"1px solid {S.BORDER_SUBTLE}",
                z_index="101",
                box_shadow=f"-20px 0 60px rgba(0,0,0,0.5)",
            ),
        ),
    )


def _detail_field(label: str, value: rx.Var, icon: str) -> rx.Component:
    return rx.cond(
        value != "",
        rx.hstack(
            rx.center(
                rx.icon(tag=icon, size=14, color=S.TEXT_MUTED),
                width="28px",
                height="28px",
                border_radius="8px",
                bg=S.BG_INPUT,
                flex_shrink="0",
            ),
            rx.vstack(
                rx.text(
                    label,
                    font_family=S.FONT_TECH,
                    font_size="0.6rem",
                    font_weight="700",
                    color=S.TEXT_MUTED,
                    letter_spacing="0.15em",
                    text_transform="uppercase",
                ),
                rx.text(
                    value,
                    font_family=S.FONT_MONO,
                    font_size="0.82rem",
                    color=S.TEXT_PRIMARY,
                    word_break="break-all",
                ),
                spacing="0",
                align="start",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
    )


# ── Page ─────────────────────────────────────────────────────────────────────


def logs_auditoria_page() -> rx.Component:
    return rx.cond(
        GlobalState.is_authenticated,
        rx.box(
            # Detail panel (overlay)
            _detail_panel(),
            # Main content
            rx.vstack(
                # ── Header ──────────────────────────────────────────────────
                rx.hstack(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="shield-check", size=28, color=S.COPPER),
                            rx.text(
                                "LOGS & AUDITORIA",
                                font_family=S.FONT_TECH,
                                font_size="1.8rem",
                                font_weight="900",
                                color=S.TEXT_PRIMARY,
                                letter_spacing="0.08em",
                            ),
                            spacing="3",
                            align="center",
                        ),
                        rx.text(
                            "Rastreabilidade total de ações, acessos e eventos do sistema.",
                            font_family=S.FONT_BODY,
                            font_size="0.9rem",
                            color=S.TEXT_MUTED,
                        ),
                        spacing="1",
                        align="start",
                    ),
                    rx.spacer(),
                    # Refresh button
                    rx.button(
                        rx.icon(tag="refresh-cw", size=16),
                        "Atualizar",
                        on_click=LogsState.refresh,
                        bg="transparent",
                        color=S.TEXT_MUTED,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="10px",
                        height="38px",
                        padding_x="14px",
                        font_family=S.FONT_TECH,
                        font_size="0.8rem",
                        cursor="pointer",
                        _hover={"border_color": S.PATINA, "color": S.PATINA},
                        transition="all 0.15s ease",
                    ),
                    align="end",
                    width="100%",
                ),
                # ── Stats ────────────────────────────────────────────────────
                _stats_row(),
                # ── Filter bar ───────────────────────────────────────────────
                _filter_bar(),
                # ── Table ────────────────────────────────────────────────────
                _logs_table(),
                # ── Pagination ───────────────────────────────────────────────
                _pagination(),
                spacing="5",
                padding="24px",
                width="100%",
                min_height="100vh",
            ),
        ),
        rx.fragment(),
    )
