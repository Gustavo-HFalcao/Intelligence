"""
Gestão de Projetos — Unified Hub
Consolidates the former "Projetos" (activity timeline) and "Obras" (field KPIs)
into a single page with Project Pulse Cards list and a tabbed Hub detail view.
"""
import reflex as rx

from bomtempo.components.skeletons import page_loading_skeleton
from bomtempo.components.tooltips import TOOLTIP_SIGNAL
from bomtempo.components.windy_map_widget import windy_map_widget
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState

_GLASS_COMPACT = {**S.GLASS_CARD, "padding": "20px 24px"}


# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════


def _projetos_header() -> rx.Component:
    # ── STITCH ACTION HEADER (List View) ──
    list_header = rx.flex(
        rx.box(
            rx.text(
                "Hub de Projetos",
                font_family=S.FONT_TECH,
                font_size="2.25rem",
                font_weight="700",
                letter_spacing="0.05em",
                text_transform="uppercase",
                color="var(--text-main)",
                line_height="1.2",
            ),
            rx.text(
                "Active Operations Fleet // System 04.2",
                font_family=S.FONT_MONO,
                font_size="12px",
                color="rgba(201,139,42,0.8)", # primary-container/80
                text_transform="uppercase",
                letter_spacing="0.1em",
                margin_top="4px",
            ),
        ),
        rx.spacer(),
        rx.hstack(
            rx.box(
                rx.icon(
                    tag="search",
                    size=15,
                    color=S.TEXT_MUTED,
                    position="absolute",
                    left="12px",
                    top="50%",
                    transform="translateY(-50%)",
                    z_index="2",
                ),
                rx.el.input(
                    value=GlobalState.project_search,
                    on_change=GlobalState.set_project_search,
                    debounce_timeout=300,
                    placeholder="BUSCAR PROJETOS...",
                    style={
                        "background": "rgba(6, 16, 14, 1)", # surface-container-lowest
                        "border": "0",
                        "borderBottom": "2px solid transparent",
                        "color": "var(--text-main)",
                        "padding": "8px 12px 8px 36px",
                        "fontSize": "14px",
                        "fontFamily": S.FONT_TECH,
                        "letterSpacing": "0.05em",
                        "width": "250px",
                        "outline": "none",
                        "transition": "border-color 0.2s ease",
                    },
                    _focus={"border_bottom": f"2px solid {S.COPPER}"},
                ),
                position="relative",
                display=rx.breakpoints(initial="none", lg="block"),
            ),
            rx.button(
                rx.hstack(
                    rx.icon(tag="copy", size=14),
                    rx.text("DUPLICATE", font_family=S.FONT_TECH, font_size="14px", letter_spacing="0.05em"),
                    spacing="2", align="center",
                ),
                bg="rgba(19, 29, 27, 1)", # surface-container-low
                color="var(--text-main)",
                border="1px solid rgba(255,255,255,0.08)",
                padding="8px 16px",
                border_radius="2px",
                _hover={"border_color": "rgba(201,139,42,0.4)"},
                cursor="pointer",
            ),
            rx.button(
                rx.hstack(
                    rx.icon(tag="plus", size=14),
                    rx.text("CREATE NEW PROJECT", font_family=S.FONT_TECH, font_size="14px", font_weight="bold", letter_spacing="0.1em"),
                    spacing="2", align="center",
                ),
                background="linear-gradient(135deg, #C98B2A 0%, #835500 100%)",
                color="#452b00", # on-primary
                border="none",
                padding="8px 24px",
                border_radius="2px",
                box_shadow="0 0 15px rgba(201,139,42,0.3)",
                _hover={"filter": "brightness(1.1)"},
                cursor="pointer",
            ),
            spacing="3",
            align="center",
        ),
        width="100%",
        direction=rx.breakpoints(initial="column", md="row"),
        justify="between",
        align="start",
        margin_bottom="40px",
        gap="1.5rem",
    )

    # ── STITCH NAVBAR (Detail View) ──
    def _stitch_tab(label: str, value: str):
        is_active = GlobalState.project_hub_tab == value
        return rx.box(
            rx.text(
                label,
                font_family=S.FONT_MONO,
                font_size="14px",
                font_weight=rx.cond(is_active, "bold", "normal"),
                color=rx.cond(is_active, S.COPPER, "rgba(218,229,225,0.6)"),
                transition="color 0.2s ease",
            ),
            padding_bottom="8px",
            border_bottom=rx.cond(is_active, f"2px solid {S.COPPER}", "2px solid transparent"),
            cursor="pointer",
            on_click=GlobalState.set_project_hub_tab(value),
            _hover={"& > p": {"color": "rgba(218,229,225,1)"}},
        )

    detail_header = rx.box(
        rx.flex(
            rx.hstack(
                rx.icon_button(
                    rx.icon(tag="chevron-left", size=20, color="var(--text-main)"),
                    variant="ghost",
                    on_click=GlobalState.deselect_project,
                    _hover={"bg": "rgba(255,255,255,0.05)"},
                ),
                rx.text(
                    GlobalState.selected_project,
                    font_family=S.FONT_TECH,
                    font_size="1.25rem",
                    font_weight="700",
                    color="var(--text-main)",
                    letter_spacing="-0.02em",
                ),
                spacing="4",
                align="center",
            ),
            rx.hstack(
                _stitch_tab("Visão Geral", "visao_geral"),
                _stitch_tab("Cronograma (Gantt)", "cronograma"),
                _stitch_tab("Hub de Mídia", "disciplinas"),  # Disciplinas converted to Media Audit logic for now
                _stitch_tab("Registros e RDO", "campo"),
                spacing="6",
                display=rx.breakpoints(initial="none", md="flex"),
            ),
            width="100%",
            justify="between",
            align="end",
        ),
        padding="16px 32px",
        background="rgba(14, 26, 23, 0.6)",
        backdrop_filter="blur(24px)",
        border_bottom="1px solid rgba(255,255,255,0.05)",
        box_shadow="0 20px 40px rgba(0,0,0,0.4), 0 0 10px rgba(42,157,143,0.05)",
        border_radius="8px",
        margin_bottom="24px",
    )

    return rx.cond(
        GlobalState.selected_project == "",
        list_header,
        detail_header,
    )


# ══════════════════════════════════════════════════════════════
# LIST VIEW — PROJECT PULSE CARDS
# ══════════════════════════════════════════════════════════════


def pulse_card(item: dict) -> rx.Component:
    """Enterprise project pulse card matched 1:1 with Stitch design."""
    avanco = item["progress"].to(float).to(int)
    
    return rx.box(
        # Top Row: ID + Badge
        rx.hstack(
            rx.text(
                item["contrato"],
                font_family=S.FONT_MONO,
                font_size="12px",
                color="rgba(201,139,42,1)", # primary-container
                font_weight="bold",
            ),
            rx.box(
                item["status"],
                padding="2px 8px",
                background=item["status_bg"],
                color=item["status_color"],
                font_size="10px",
                font_family=S.FONT_MONO,
                text_transform="uppercase",
                letter_spacing="-0.02em",
                border=f"1px solid {item['status_color']}", # Simulated opacity using identical color
                border_radius="2px",
            ),
            justify="between",
            align="start",
            margin_bottom="24px",
            width="100%",
        ),
        # Title (Client/Project Name)
        rx.text(
            item["cliente"],
            font_family=S.FONT_TECH,
            font_size="1.5rem",
            font_weight="bold",
            text_transform="uppercase",
            line_height="1.2",
            margin_bottom="4px",
            color="var(--text-main)",
        ),
        # Location
        rx.hstack(
            rx.icon(tag="map-pin", size=14, color=S.TEXT_MUTED),
            rx.text(
                item["localizacao"],
                font_size="12px",
                font_family=S.FONT_BODY,
                color=S.TEXT_MUTED,
            ),
            spacing="2",
            align="center",
            margin_bottom="24px",
            width="100%",
        ),
        # mt-auto Pushes bottom content down completely
        rx.spacer(),
        rx.box(
            # Progress Pulse Text
            rx.hstack(
                rx.text(
                    "Progress Pulse",
                    font_family=S.FONT_MONO,
                    font_size="10px",
                    color=S.TEXT_MUTED,
                    text_transform="uppercase",
                ),
                rx.spacer(),
                rx.text(
                    avanco.to_string() + "%",
                    font_family=S.FONT_MONO,
                    font_size="14px",
                    color=item["status_color"],
                ),
                width="100%",
                align="end",
                margin_bottom="8px",
            ),
            # Progress Bar Track
            rx.box(
                rx.box(
                    height="100%",
                    bg=item["status_color"],
                    width=avanco.to_string() + "%",
                ),
                height="4px", # h-1
                bg="rgba(44,55,52,1)", # surface-container-highest
                width="100%",
                margin_bottom="24px",
            ),
            # Bottom row: Deadline + Risk
            rx.hstack(
                rx.vstack(
                    rx.text(
                        "Deadline",
                        font_family=S.FONT_MONO,
                        font_size="9px",
                        color=S.TEXT_MUTED,
                        text_transform="uppercase",
                    ),
                    rx.text(
                        item["days_fmt"],
                        font_family=S.FONT_MONO,
                        font_size="12px",
                        color=rx.cond(item["days_to_deadline"].to(int) < 0, S.DANGER, "var(--text-main)"),
                    ),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                # Risk Badge
                rx.hstack(
                    rx.box(
                        width="6px", height="6px",
                        border_radius="50%",
                        bg=item["risco_color"],
                        class_name=rx.cond(item["days_to_deadline"].to(int) < 0, "animate-pulse", ""),
                    ),
                    rx.text(
                        item["risco_label"],
                        font_family=S.FONT_MONO,
                        font_size="9px",
                        text_transform="uppercase",
                        letter_spacing="-0.02em",
                        color=item["risco_color"],
                    ),
                    padding="4px 8px",
                    bg="rgba(255,255,255,0.05)",
                    border="1px solid rgba(255,255,255,0.1)",
                    align="center",
                    spacing="2",
                ),
                width="100%",
                align="center",
            ),
            width="100%",
        ),
        # Full Card Container properties
        background="rgba(14, 26, 23, 0.6)", # glass-panel
        backdrop_filter="blur(12px)",
        border="1px solid rgba(255, 255, 255, 0.08)", # ghost-border
        padding="20px",
        display="flex",
        flex_direction="column",
        height="100%",
        min_height="320px",
        cursor="pointer",
        on_click=GlobalState.select_project(item["contrato"]),
        transition="all 0.2s ease",
        _hover={
            "background": "rgba(14, 26, 23, 1)",
            "border_color": "rgba(201, 139, 42, 0.4)",
        },
    )


def _pulse_list_view() -> rx.Component:
    return rx.cond(
        GlobalState.project_pulse_cards,
        rx.grid(
            rx.foreach(GlobalState.project_pulse_cards, pulse_card),
            columns=rx.breakpoints(initial="1", md="2", lg="3"),
            spacing="6",
            width="100%",
            class_name="animate-enter",
        ),
        rx.center(
            rx.vstack(
                rx.icon(tag="folder-kanban", size=48, color=S.BORDER_SUBTLE),
                rx.text(
                    "Nenhum projeto encontrado",
                    font_size="1rem",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_TECH,
                ),
                rx.text(
                    "Ajuste os filtros ou verifique a conexão com o banco.",
                    font_size="13px",
                    color=S.TEXT_MUTED,
                ),
                spacing="3",
                align="center",
            ),
            height="40vh",
            width="100%",
        ),
    )


# ══════════════════════════════════════════════════════════════
# DETAIL HUB — Reused components from obras
# ══════════════════════════════════════════════════════════════


def _kpi_card_static(icon_tag, label, value, sub, accent, accent_bg, accent_border):
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
                    rx.text(label, font_size="11px", color=S.TEXT_MUTED,
                            text_transform="uppercase", letter_spacing="0.1em", font_weight="700"),
                    rx.text(value, font_family=S.FONT_TECH, font_size="1.75rem",
                            font_weight="700", color="var(--text-main)", line_height="1"),
                    spacing="1", align="start",
                ),
                align="center", spacing="3",
            ),
            rx.text(sub, font_size="12px", color=accent, font_family=S.FONT_MONO, margin_top="4px"),
            spacing="2",
        ),
        **_GLASS_COMPACT, flex="1", min_width="160px",
    )


def _status_strip() -> rx.Component:
    fmt = GlobalState.obra_kpi_fmt
    data = GlobalState.obra_enterprise_data
    progress_val = data.get("progress", "0").to(float).to(int).to_string() + "%"

    def _kpi_panel(title, value, subtitle, value_color="var(--text-main)", subtitle_color="var(--text-main)", bar_percent=None):
        return rx.box(
            rx.text(title, font_size="10px", font_family=S.FONT_MONO, color="rgba(218,229,225,0.5)", text_transform="uppercase", margin_bottom="4px"),
            rx.text(value, font_family=S.FONT_TECH, font_size="1.875rem", font_weight="bold", color=value_color, line_height="1.2"),
            rx.cond(
                bar_percent != None,
                rx.box(
                    rx.box(height="100%", bg=value_color, width=bar_percent),
                    width="100%", height="4px", bg="#030504", margin_top="8px", overflow="hidden"
                ),
                rx.text(subtitle, font_size="10px", font_family=S.FONT_MONO, color=subtitle_color, margin_top="4px")
            ),
            **_GLASS_COMPACT, flex_direction="column", min_width="140px", display="flex",
        )

    return rx.flex(
        # Left side: Title + Status
        rx.box(
            rx.hstack(
                rx.text("Location: " + data.get("localizacao", "Unknown").to_string(), font_family=S.FONT_MONO, font_size="12px", letter_spacing="0.1em", text_transform="uppercase", color=S.COPPER),
                rx.box(width="48px", height="1px", bg="rgba(201,139,42,0.3)"),
                rx.text("LIVE_FEED_STABLE", font_family=S.FONT_MONO, font_size="12px", color=S.PATINA),
                align="center", spacing="3", margin_bottom="8px"
            ),
            rx.text(
                data.get("cliente", GlobalState.selected_project),
                font_family=S.FONT_TECH, font_size="3rem", font_weight="bold", text_transform="uppercase", letter_spacing="-0.02em", line_height="1"
            ),
            width="100%",
        ),
        # Right side: 4 Grid Cards
        rx.box(
            rx.grid(
                _kpi_panel(
                    "Total Progress", 
                    progress_val, 
                    "", 
                    value_color=S.PATINA, 
                    bar_percent=progress_val
                ),
                _kpi_panel(
                    "Budget Burn", 
                    fmt["budget_realizado_fmt"], 
                    fmt["budget_variacao_fmt"], 
                    value_color=S.COPPER, 
                    subtitle_color=rx.cond(fmt["budget_over"], S.DANGER, S.PATINA)
                ),
                _kpi_panel(
                    "Workforce", 
                    fmt["equipe_val"], 
                    "Active Now", 
                    value_color="var(--text-main)", 
                    subtitle_color=S.PATINA
                ),
                _kpi_panel(
                    "Safety Index", 
                    rx.cond(fmt["risco_val"].to(int) < 10, "0.0", fmt["risco_val"]), 
                    "LTI Rate", 
                    value_color=S.PATINA, 
                    subtitle_color="rgba(218,229,225,0.5)"
                ),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="4",
                width="100%",
            ),
            width=rx.breakpoints(initial="100%", lg="auto"),
            margin_top=rx.breakpoints(initial="16px", lg="0")
        ),
        direction=rx.breakpoints(initial="column", lg="row"),
        justify="between",
        align=rx.breakpoints(initial="start", lg="end"),
        gap="1.5rem",
        width="100%",
    )


def _compact_info() -> rx.Component:
    data = GlobalState.obra_enterprise_data
    fmt = GlobalState.obra_kpi_fmt

    def chip(icon_tag, label, value, accent=False):
        return rx.vstack(
            rx.icon(tag=icon_tag, size=16, color=S.COPPER if accent else S.TEXT_MUTED),
            rx.text(label, font_size="9px", color=S.TEXT_MUTED,
                    text_transform="uppercase", letter_spacing="0.1em", font_weight="700"),
            rx.text(value, font_size="15px", font_weight="700",
                    color=S.COPPER if accent else "var(--text-main)",
                    font_family=S.FONT_MONO if not accent else S.FONT_TECH,
                    white_space="nowrap", overflow="hidden", text_overflow="ellipsis", max_width="100%"),
            align="center", spacing="1", width="100%",
            border_right=f"1px solid {S.BORDER_SUBTLE}", padding="8px 12px",
        )

    return rx.box(
        rx.box(
            chip("hash", "Contrato", data["contrato"], accent=True),
            chip("building-2", "Cliente", data["cliente"]),
            chip("zap", "Potência", data.get("potencia_kwp", "—"), accent=True),
            chip("map-pin", "Localização", data.get("localizacao", "—")),
            chip("clock", "Prazo", data.get("prazo_dias", "—")),
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="trending-up", size=16, color=S.PATINA),
                    rx.text(fmt["avanco_fmt"], font_family=S.FONT_TECH, font_size="1.5rem",
                            font_weight="700", color="var(--text-main)", white_space="nowrap"),
                    spacing="2", align="center",
                ),
                rx.text("Avanço Médio", font_size="9px", color=S.TEXT_MUTED,
                        text_transform="uppercase", letter_spacing="0.1em", font_weight="700"),
                align="center", spacing="1", padding="16px 12px", width="100%",
            ),
            display="grid",
            grid_template_columns=["repeat(2, minmax(0,1fr))", "repeat(3, minmax(0,1fr))", "repeat(6, minmax(0,1fr))"],
            width="100%", overflow="hidden", align_items="center",
        ),
        **S.GLASS_CARD, flex="2",
    )


def _scurve_chart() -> rx.Component:
    """S-Curve: planned vs actual over time with a rich glassmorphism tooltip."""

    # Custom tooltip content — rendered via Recharts customized tooltip component
    # We use a JS inline string via rx.html for full control
    _tooltip_html = """
    <div style="
        background: rgba(8,18,16,0.96);
        border: 1px solid rgba(201,139,42,0.4);
        border-radius: 8px;
        padding: 12px 16px;
        min-width: 200px;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
    ">
        <p style="font-size:9px;font-weight:700;color:#889999;text-transform:uppercase;letter-spacing:.1em;margin:0 0 8px 0;">
            {label}
        </p>
        <div style="display:flex;gap:16px;margin-bottom:8px;">
            <div>
                <p style="font-size:9px;color:#889999;margin:0;">PREVISTO</p>
                <p style="font-size:16px;font-weight:700;color:#E0E0E0;font-family:'Rajdhani';margin:2px 0 0;">{previsto}%</p>
            </div>
            <div>
                <p style="font-size:9px;color:#889999;margin:0;">REALIZADO</p>
                <p style="font-size:16px;font-weight:700;color:#2A9D8F;font-family:'Rajdhani';margin:2px 0 0;">{realizado}%</p>
            </div>
        </div>
    </div>
    """

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="trending-up", size=16, color=S.PATINA, margin_right="8px"),
                rx.text(
                    "Curva S — Evolução Física",
                    font_family=S.FONT_TECH,
                    font_size="1.1rem",
                    font_weight="700",
                    color="var(--text-main)",
                ),
                rx.spacer(),
                # Weather risk inline badge
                rx.cond(
                    GlobalState.weather_risk_level != "Unknown",
                    rx.hstack(
                        rx.box(
                            width="6px", height="6px", border_radius="50%",
                            bg=rx.cond(
                                GlobalState.weather_risk_level == "High", S.DANGER,
                                rx.cond(GlobalState.weather_risk_level == "Medium", S.WARNING, S.PATINA),
                            ),
                        ),
                        rx.text(
                            rx.cond(
                                GlobalState.weather_risk_level == "High", "Clima: Alto Risco",
                                rx.cond(GlobalState.weather_risk_level == "Medium", "Clima: Médio Risco", "Clima: Favorável"),
                            ),
                            font_size="9px",
                            font_weight="700",
                            color=rx.cond(
                                GlobalState.weather_risk_level == "High", S.DANGER,
                                rx.cond(GlobalState.weather_risk_level == "Medium", S.WARNING, S.PATINA),
                            ),
                        ),
                        spacing="1",
                        align="center",
                        padding="3px 8px",
                        border_radius="4px",
                        bg=rx.cond(
                            GlobalState.weather_risk_level == "High", S.DANGER_BG,
                            rx.cond(GlobalState.weather_risk_level == "Medium", S.WARNING_BG, S.SUCCESS_BG),
                        ),
                    ),
                ),
                rx.box(width="12px"),
                # Legend
                rx.hstack(
                    rx.box(width="20px", height="2px", bg=S.TEXT_MUTED,
                           border_radius="2px",
                           style={"borderTop": "2px dashed " + S.TEXT_MUTED, "background": "transparent"}),
                    rx.text("Previsto", font_size="9px", color=S.TEXT_MUTED, font_weight="700"),
                    rx.box(width="8px"),
                    rx.box(width="20px", height="3px", bg=S.PATINA, border_radius="2px"),
                    rx.text("Realizado", font_size="9px", color=S.TEXT_MUTED, font_weight="700"),
                    align="center", spacing="2",
                ),
                align="center", margin_bottom="16px", width="100%",
            ),
            rx.cond(
                GlobalState.project_scurve_chart,
                rx.recharts.area_chart(
                    rx.recharts.area(
                        data_key="previsto",
                        stroke=S.TEXT_MUTED,
                        fill="rgba(136,153,153,0.05)",
                        stroke_dasharray="5 3",
                        dot=False,
                        stroke_width=2,
                    ),
                    rx.recharts.area(
                        data_key="realizado",
                        stroke=S.PATINA,
                        fill="rgba(42,157,143,0.15)",
                        dot={"fill": S.PATINA, "r": 3, "strokeWidth": 0},
                        active_dot={"fill": S.COPPER, "r": 5, "stroke": "rgba(201,139,42,0.4)", "strokeWidth": 3},
                        stroke_width=2,
                    ),
                    rx.recharts.x_axis(
                        data_key="data",
                        tick={"fontSize": 10, "fill": S.TEXT_MUTED, "fontFamily": "JetBrains Mono"},
                    ),
                    rx.recharts.y_axis(
                        unit="%",
                        tick={"fontSize": 10, "fill": S.TEXT_MUTED, "fontFamily": "JetBrains Mono"},
                        domain=[0, 100],
                        width=36,
                    ),
                    rx.recharts.cartesian_grid(
                        stroke_dasharray="3 3",
                        stroke="rgba(255,255,255,0.04)",
                    ),
                    TOOLTIP_SIGNAL,
                    rx.recharts.reference_line(
                        y=GlobalState.obra_kpi_fmt["avanco_pct"],
                        stroke=S.COPPER,
                        stroke_dasharray="4 2",
                        stroke_width=1,
                        label="Hoje",
                    ),
                    data=GlobalState.project_scurve_chart,
                    height=220,
                    width="100%",
                    class_name="chart-enter",
                ),
                rx.center(
                    rx.text("Sem dados de progresso temporal", font_size="13px", color=S.TEXT_MUTED),
                    height="80px",
                ),
            ),
            # AI note footer
            rx.cond(
                GlobalState.obra_insight_text != "",
                rx.hstack(
                    rx.center(
                        rx.icon(tag="brain-circuit", size=12, color=S.COPPER),
                        width="22px", height="22px",
                        bg=S.COPPER_GLOW,
                        border_radius="50%",
                        flex_shrink="0",
                    ),
                    rx.text(
                        GlobalState.obra_insight_text,
                        font_size="11px",
                        color=S.TEXT_MUTED,
                        line_height="1.5",
                        # truncate to 1 line
                        overflow="hidden",
                        white_space="nowrap",
                        text_overflow="ellipsis",
                    ),
                    padding="10px 14px",
                    border_radius=S.R_CONTROL,
                    bg="rgba(201,139,42,0.04)",
                    border=f"1px solid {S.BORDER_ACCENT}",
                    width="100%",
                    align="center",
                    spacing="3",
                    margin_top="12px",
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD, width="100%",
    )



def _ai_insight_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.icon(tag="brain-circuit", size=16, color=S.COPPER),
                    padding="8px", bg=S.COPPER_GLOW, border_radius="8px",
                    border=f"1px solid {S.BORDER_ACCENT}",
                ),
                rx.vstack(
                    rx.text("Inteligência Ativa", font_family=S.FONT_TECH, font_size="1.1rem",
                            font_weight="700", color=S.COPPER),
                    rx.text("Diagnóstico automático por IA", font_size="10px", color=S.TEXT_MUTED),
                    spacing="0",
                ),
                align="center", spacing="3", margin_bottom="16px",
            ),
            rx.cond(
                GlobalState.obra_insight_loading,
                rx.vstack(
                    rx.hstack(
                        rx.spinner(size="2", color=S.COPPER),
                        rx.text("Analisando dados...", font_size="12px", color=S.TEXT_MUTED, font_style="italic"),
                        align="center", spacing="3",
                    ),
                    rx.vstack(
                        rx.box(height="10px", bg="rgba(201,139,42,0.1)", border_radius="4px", width="100%"),
                        rx.box(height="10px", bg="rgba(201,139,42,0.07)", border_radius="4px", width="82%"),
                        rx.box(height="10px", bg="rgba(201,139,42,0.04)", border_radius="4px", width="65%"),
                        spacing="2", width="100%", margin_top="10px",
                    ),
                    spacing="3", width="100%",
                ),
                rx.cond(
                    GlobalState.obra_insight_text != "",
                    rx.box(
                        rx.text(GlobalState.obra_insight_text, font_size="0.875rem",
                                color=S.TEXT_PRIMARY, line_height="1.75"),
                        padding="16px 18px",
                        bg="rgba(201,139,42,0.04)",
                        border_radius="12px",
                        border=f"1px solid {S.BORDER_ACCENT}",
                        border_left=f"3px solid {S.COPPER}",
                        width="100%",
                    ),
                    rx.text("Selecione um projeto para gerar o diagnóstico.",
                            font_size="12px", color=S.TEXT_MUTED, font_style="italic"),
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD, width="100%",
    )


# ── Gauges tab ────────────────────────────────────────────────

def _mini_semi_gauge(item: dict) -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.el.svg(
                rx.el.circle(cx="50", cy="50", r="38",
                             stroke="rgba(255,255,255,0.07)", stroke_width="10",
                             fill="transparent",
                             stroke_dasharray="119.38 238.76",
                             stroke_dashoffset="-119.38",
                             stroke_linecap="round"),
                rx.el.circle(cx="50", cy="50", r="38",
                             stroke=item["color"], stroke_width="10",
                             fill="transparent",
                             stroke_dasharray=item["realizado_dash"],
                             stroke_dashoffset="-119.38",
                             stroke_linecap="round",
                             style={"transition": "stroke-dasharray 1.2s ease-out"}),
                rx.el.circle(cx=item["marker_cx"], cy=item["marker_cy"], r="5",
                             fill="white", stroke="rgba(0,0,0,0.4)", stroke_width="1.5"),
                view_box="7 7 86 47", width="150", height="84", overflow="visible",
            ),
            rx.box(
                rx.text(item["realizado_pct_fmt"], font_family=S.FONT_TECH, font_size="1.4rem",
                        font_weight="700", color="var(--text-main)", text_align="center"),
                position="absolute", bottom="0px", left="0", right="0", text_align="center",
            ),
            position="relative", width="150px", height="100px",
        ),
        rx.text(item["categoria"], font_size="13px", color=S.TEXT_MUTED,
                text_align="center", text_transform="uppercase", letter_spacing="0.05em",
                font_weight="700", max_width="140px", white_space="nowrap",
                overflow="hidden", text_overflow="ellipsis"),
        rx.text(item["pr_label"], font_size="11px", color=item["color"],
                font_family=S.FONT_MONO, text_align="center"),
        spacing="2", align="center",
    )


def _gauges_section() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="gauge", size=16, color=S.COPPER, margin_right="8px"),
                rx.text("Progresso por Disciplina", font_family=S.FONT_TECH, font_size="1.125rem",
                        font_weight="bold", text_transform="uppercase", letter_spacing="0.1em", color="var(--text-main)"),
                rx.spacer(),
                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", bg="rgba(255,255,255,0.4)",
                           border="1.5px solid rgba(0,0,0,0.4)", flex_shrink="0"),
                    rx.text("Meta", font_size="9px", color=S.TEXT_MUTED, font_weight="700"),
                    rx.box(width="8px"),
                    rx.box(width="20px", height="4px", bg=S.PATINA, border_radius="2px", flex_shrink="0"),
                    rx.text("Realizado", font_size="9px", color=S.TEXT_MUTED, font_weight="700"),
                    align="center", spacing="2",
                ),
                align="center", margin_bottom="24px", width="100%",
            ),
            rx.cond(
                GlobalState.disciplina_gauges_list,
                rx.flex(
                    rx.foreach(GlobalState.disciplina_gauges_list, _mini_semi_gauge),
                    gap="40px", flex_wrap="wrap", justify_content="center", width="100%",
                ),
                rx.center(
                    rx.text("Sem dados de disciplinas", font_size="13px", color=S.TEXT_MUTED),
                    height="80px",
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD, width="100%",
    )


def _budget_panel() -> rx.Component:
    fmt = GlobalState.obra_kpi_fmt
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="chart-bar", size=16, color=S.COPPER, margin_right="8px"),
                rx.text("Desempenho Orçamentário", font_family=S.FONT_TECH, font_size="1.125rem",
                        font_weight="bold", text_transform="uppercase", letter_spacing="0.1em", color="var(--text-main)"),
                align="center", margin_bottom="20px",
            ),
            rx.grid(
                rx.vstack(
                    rx.text("PLANEJADO", font_size="11px", color=S.TEXT_MUTED,
                            text_transform="uppercase", letter_spacing="0.1em", font_weight="700"),
                    rx.text(fmt["budget_planejado_fmt"], font_family=S.FONT_TECH, font_size="2rem",
                            font_weight="700", color="var(--text-main)"),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("REALIZADO", font_size="11px", color=S.TEXT_MUTED,
                            text_transform="uppercase", letter_spacing="0.1em", font_weight="700"),
                    rx.text(fmt["budget_realizado_fmt"], font_family=S.FONT_TECH, font_size="2rem",
                            font_weight="700", color="var(--text-main)"),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("EXECUÇÃO", font_size="11px", color=S.TEXT_MUTED,
                            text_transform="uppercase", letter_spacing="0.1em", font_weight="700"),
                    rx.hstack(
                        rx.text(fmt["budget_exec_rate_fmt"], font_family=S.FONT_TECH, font_size="2rem",
                                font_weight="700", color=fmt["budget_color"]),
                        rx.cond(
                            fmt["budget_over"],
                            rx.box(rx.text("OVER", font_size="8px", font_weight="700", color=S.DANGER),
                                   padding="2px 6px", bg=S.DANGER_BG, border_radius="4px",
                                   border="1px solid rgba(239,68,68,0.3)", align_self="center"),
                        ),
                        spacing="2", align="end",
                    ),
                    rx.text(fmt["budget_variacao_fmt"], font_size="12px", color=fmt["budget_color"],
                            font_family=S.FONT_MONO, max_width="220px"),
                    spacing="1",
                ),
                columns=rx.breakpoints(initial="1", sm="2", lg="3"),
                spacing="6", width="100%", margin_bottom="20px",
            ),
            rx.box(
                rx.box(
                    width=fmt["budget_bar_pct"].to_string() + "%",
                    height="100%",
                    bg=rx.cond(fmt["budget_over"],
                               f"linear-gradient(90deg, {S.DANGER}, #B91C1C)",
                               f"linear-gradient(90deg, {S.PATINA}, {S.PATINA_DARK})"),
                    border_radius="9999px",
                    transition="width 1.2s ease-out",
                ),
                height="8px", bg="rgba(255,255,255,0.05)", border_radius="9999px",
                overflow="hidden", width="100%",
            ),
            rx.hstack(
                rx.text("0%", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                rx.spacer(),
                rx.text(fmt["budget_bar_label"], font_size="9px", color=fmt["budget_color"],
                        font_family=S.FONT_MONO, font_weight="700"),
                rx.spacer(),
                rx.text("100%", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                width="100%", margin_top="6px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD, width="100%",
    )


# ── Cronograma tab ────────────────────────────────────────────

def _activity_bar(item: dict) -> rx.Component:
    is_critical = item["critico"] == "Sim"
    return rx.box(
        rx.hstack(
            rx.text(item["atividade"], font_size="13px", font_weight="700",
                    color="var(--text-main)"),
            rx.spacer(),
            rx.text(item["fase"], font_size="12px", color=S.TEXT_MUTED),
            width="100%", margin_bottom="4px",
        ),
        rx.box(
            rx.box(
                width=item["conclusao_pct"].to_string() + "%",
                height="100%",
                border_radius="9999px",
                background=rx.cond(
                    is_critical,
                    f"linear-gradient(90deg, {S.DANGER}, #B91C1C)",
                    f"linear-gradient(90deg, {S.COPPER}, {S.COPPER_LIGHT})",
                ),
                transition="width 1s ease-out",
            ),
            rx.text(
                item["conclusao_pct"].to_string() + "%",
                position="absolute", right="8px", top="50%", transform="translateY(-50%)",
                font_size="9px", font_weight="700", color="white", mix_blend_mode="difference",
            ),
            height="16px", bg="rgba(255,255,255,0.03)", border_radius="9999px",
            overflow="hidden", position="relative", width="100%",
        ),
        rx.cond(
            is_critical,
            rx.hstack(
                rx.icon(tag="circle-alert", size=10, color=S.DANGER),
                rx.text("CAMINHO CRÍTICO", font_size="9px", color=S.DANGER,
                        text_transform="uppercase", letter_spacing="0.05em"),
                spacing="1", margin_top="4px",
            ),
        ),
        width="100%", margin_bottom="16px",
    )


def _cronograma_tab() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="calendar", size=18, color=S.COPPER, margin_right="8px"),
                rx.text("Cronograma de Atividades", font_family=S.FONT_TECH, font_size="1.125rem",
                        font_weight="bold", text_transform="uppercase", letter_spacing="0.1em", color="var(--text-main)"),
                rx.spacer(),
                # Phase filter chips
                rx.hstack(
                    rx.foreach(
                        GlobalState.fases_disponiveis,
                        lambda fase: rx.box(
                            rx.text(
                                fase,
                                font_size="10px",
                                font_weight="700",
                                color=rx.cond(
                                    GlobalState.projetos_fase_filter == fase,
                                    S.BG_VOID,
                                    S.TEXT_MUTED,
                                ),
                            ),
                            padding="4px 10px",
                            border_radius="6px",
                            cursor="pointer",
                            bg=rx.cond(
                                GlobalState.projetos_fase_filter == fase,
                                S.COPPER,
                                "transparent",
                            ),
                            on_click=GlobalState.set_projetos_fase_filter(fase),
                            _hover={"bg": rx.cond(
                                GlobalState.projetos_fase_filter == fase,
                                S.COPPER,
                                "rgba(255,255,255,0.05)",
                            )},
                            transition="all 0.2s ease",
                        ),
                    ),
                    bg="rgba(255,255,255,0.03)",
                    padding="3px",
                    border_radius="10px",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    spacing="1",
                    flex_wrap="wrap",
                ),
                align="center", margin_bottom="24px", width="100%",
            ),
            rx.cond(
                GlobalState.filtered_projetos,
                rx.foreach(GlobalState.filtered_projetos, _activity_bar),
                rx.center(
                    rx.text("Sem atividades para este projeto.", font_size="13px", color=S.TEXT_MUTED),
                    height="60px",
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD, width="100%",
    )


# ── Campo tab ─────────────────────────────────────────────────

def _campo_rdo_row(item: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(
                item["data_rdo"],
                font_size="12px",
                font_family=S.FONT_MONO,
                color=S.COPPER,
                font_weight="700",
            ),
            rx.text(item["responsavel"], font_size="11px", color=S.TEXT_MUTED),
            spacing="0",
            min_width="90px",
        ),
        rx.box(width="1px", height="36px", bg=S.BORDER_SUBTLE, flex_shrink="0"),
        rx.text(
            item["atividade"],
            font_size="13px",
            color="var(--text-main)",
            flex="1",
            min_width="0",
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
        ),
        rx.spacer(),
        rx.cond(
            item["pdf_url"] != "",
            rx.link(
                rx.hstack(
                    rx.icon(tag="file-text", size=13, color=S.PATINA),
                    rx.text("PDF", font_size="10px", color=S.PATINA, font_weight="700"),
                    spacing="1", align="center",
                ),
                href=item["pdf_url"],
                is_external=True,
                _hover={"opacity": "0.8"},
            ),
        ),
        padding="12px 16px",
        border_radius=S.R_CONTROL,
        border=f"1px solid {S.BORDER_SUBTLE}",
        bg="rgba(255,255,255,0.02)",
        _hover={"bg": "rgba(255,255,255,0.04)", "border_color": S.BORDER_ACCENT},
        transition="all 0.15s ease",
        width="100%",
        align="center",
        spacing="3",
    )


def _campo_tab() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="hard-hat", size=18, color=S.COPPER, margin_right="8px"),
                rx.text("Registros de Campo (RDO)", font_family=S.FONT_TECH, font_size="1.125rem",
                        font_weight="bold", text_transform="uppercase", letter_spacing="0.1em", color="var(--text-main)"),
                rx.spacer(),
                rx.cond(
                    GlobalState.project_campo_loading,
                    rx.spinner(size="2", color=S.COPPER),
                ),
                align="center", margin_bottom="20px", width="100%",
            ),
            rx.cond(
                GlobalState.project_campo_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3", color=S.COPPER),
                        rx.text("Carregando RDOs...", font_size="13px", color=S.TEXT_MUTED),
                        spacing="3", align="center",
                    ),
                    height="120px",
                ),
                rx.cond(
                    GlobalState.project_campo_rdos_display,
                    rx.vstack(
                        rx.foreach(GlobalState.project_campo_rdos_display, _campo_rdo_row),
                        spacing="2",
                        width="100%",
                    ),
                    rx.center(
                        rx.vstack(
                            rx.icon(tag="file-x-2", size=40, color=S.BORDER_SUBTLE),
                            rx.text("Nenhum RDO encontrado para este contrato.",
                                    font_size="13px", color=S.TEXT_MUTED),
                            rx.button(
                                rx.hstack(
                                    rx.icon(tag="refresh-cw", size=13),
                                    rx.text("Carregar RDOs", font_size="12px"),
                                    spacing="2", align="center",
                                ),
                                on_click=GlobalState.load_project_campo_rdos,
                                variant="outline",
                                color=S.COPPER,
                                border_color=S.BORDER_ACCENT,
                                size="2",
                            ),
                            spacing="3", align="center",
                        ),
                        height="140px",
                    ),
                ),
            ),
            width="100%",
        ),
        **S.GLASS_CARD, width="100%",
    )


# ══════════════════════════════════════════════════════════════
# PROJECT HUB — Tabbed detail view
# ══════════════════════════════════════════════════════════════


def _project_hub() -> rx.Component:
    # Match statement is cleaner than deeply nested rx.cond for routing
    return rx.vstack(
        # KPI strip
        _status_strip(),
        # Custom Router for Tabs without rx.tabs.root forcing DOM structure
        rx.match(
            GlobalState.project_hub_tab,
            ("visao_geral", rx.box(
                rx.grid(
                    rx.box(
                        _scurve_chart(),
                        grid_column=rx.breakpoints(initial="span 12", lg="span 8"),
                        height="100%",
                    ),
                    rx.box(
                        _ai_insight_panel(),
                        grid_column=rx.breakpoints(initial="span 12", lg="span 4"),
                        height="100%",
                    ),
                    rx.box(
                        _compact_info(),
                        grid_column=rx.breakpoints(initial="span 12", lg="span 4"),
                        height="100%",
                    ),
                    rx.box(
                        windy_map_widget(),
                        grid_column=rx.breakpoints(initial="span 12", lg="span 8"),
                        min_height="400px",
                        height="100%",
                        border_radius="8px",
                        border="1px solid rgba(255, 255, 255, 0.08)",
                        overflow="hidden",
                    ),
                    columns="12",
                    gap="1.5rem",
                    width="100%",
                    align_items="stretch",
                ),
                width="100%",
                class_name="animate-fade-in",
            )),
            ("cronograma", rx.box(
                _cronograma_tab(),
                class_name="animate-fade-in", width="100%",
            )),
            ("disciplinas", rx.vstack(
                _gauges_section(),
                _budget_panel(),
                spacing="6", width="100%",
                class_name="animate-fade-in",
            )),
            ("campo", rx.box(
                _campo_tab(),
                class_name="animate-fade-in", width="100%",
            )),
            # Default fallback
            rx.box(width="100%")
        ),
        width="100%",
        spacing="6",
        class_name="animate-enter",
    )


# ══════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════


def projetos_page() -> rx.Component:
    return rx.vstack(
        _projetos_header(),
        rx.cond(
            GlobalState.is_loading,
            page_loading_skeleton(),
            rx.cond(
                GlobalState.selected_project != "",
                _project_hub(),
                _pulse_list_view(),
            ),
        ),
        width="100%",
        spacing="6",
        class_name="animate-enter",
        on_mount=lambda: GlobalState.set_current_path("/projetos"),
    )
