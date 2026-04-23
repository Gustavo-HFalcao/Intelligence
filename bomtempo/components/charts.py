import reflex as rx

from bomtempo.core import styles as S
from bomtempo.components.tooltips import (
    TOOLTIP_MONEY, TOOLTIP_PIE, TOOLTIP_GENERIC,
)

# ── Shared Chart Helpers ─────────────────────────────────────


def dark_cartesian_grid() -> rx.Component:
    return rx.recharts.cartesian_grid(
        stroke_dasharray="3 3",
        stroke="rgba(255, 255, 255, 0.04)",
        vertical=False,
    )


def chart_tooltip(formatter=None) -> rx.Component:
    if formatter is None:
        return rx.recharts.graphing_tooltip(
            cursor=S.TOOLTIP_CURSOR_PREMIUM,
            content_style=S.TOOLTIP_PREMIUM,
            label_style=S.TOOLTIP_PREMIUM_LABEL,
            item_style=S.TOOLTIP_PREMIUM_ITEM,
        )
    return rx.recharts.graphing_tooltip(
        cursor=S.TOOLTIP_CURSOR_PREMIUM,
        content_style=S.TOOLTIP_PREMIUM,
        label_style=S.TOOLTIP_PREMIUM_LABEL,
        item_style=S.TOOLTIP_PREMIUM_ITEM,
        formatter=formatter,
    )


def chart_tooltip_pct(label_map: dict | None = None) -> rx.Component:
    """Tooltip premium para gráficos de percentual (curva S, disciplinas, SPI).
    label_map: {'data_key': 'Label legível'} — mapeado via formatter JS."""
    # Formatter que adiciona % e traduz nomes
    map_js = "{" + ", ".join(f'"{k}":"{v}"' for k, v in (label_map or {}).items()) + "}"
    formatter = rx.Var(
        f"(value, name) => {{"
        f"  var labels = {map_js};"
        f"  var label = labels[name] || name;"
        f"  var v = parseFloat(value);"
        f"  var fmt = isNaN(v) ? value : v.toFixed(1) + '%';"
        f"  return [fmt, label];"
        f"}}"
    )
    return rx.recharts.graphing_tooltip(
        cursor=S.TOOLTIP_CURSOR_LINE,
        content_style=S.TOOLTIP_PREMIUM,
        label_style=S.TOOLTIP_PREMIUM_LABEL,
        item_style=S.TOOLTIP_PREMIUM_ITEM,
        formatter=formatter,
    )


def chart_tooltip_money() -> rx.Component:
    """Tooltip premium para gráficos monetários — formata em R$ M/k."""
    formatter = rx.Var(
        "(value, name) => {"
        "  var labels = {'valor':'Valor','previsto':'Planejado','realizado':'Realizado',"
        "    'executado':'Executado','previsto_acum':'Planejado Acum.','executado_acum':'Realizado Acum.',"
        "    'total_contratado':'Contratado','total_realizado':'Realizado'};"
        "  var label = labels[name] || name;"
        "  var v = parseFloat(value);"
        "  if (isNaN(v)) return [value, label];"
        "  var fmt;"
        "  if (v >= 1000000) fmt = 'R$ ' + (v/1000000).toFixed(2).replace('.',',') + 'M';"
        "  else if (v >= 1000) fmt = 'R$ ' + (v/1000).toFixed(1).replace('.',',') + 'k';"
        "  else fmt = 'R$ ' + v.toFixed(0);"
        "  return [fmt, label];"
        "}"
    )
    return rx.recharts.graphing_tooltip(
        cursor=S.TOOLTIP_CURSOR_PREMIUM,
        content_style=S.TOOLTIP_PREMIUM,
        label_style=S.TOOLTIP_PREMIUM_LABEL,
        item_style=S.TOOLTIP_PREMIUM_ITEM,
        formatter=formatter,
    )


def chart_tooltip_spi() -> rx.Component:
    """Tooltip premium para gráfico SPI — mostra valor + interpretação."""
    formatter = rx.Var(
        "(value, name) => {"
        "  if (name === 'baseline') return ['1,00 (referência)', 'Linha Base'];"
        "  var v = parseFloat(value);"
        "  if (isNaN(v)) return [value, 'SPI'];"
        "  var interp = v >= 1.05 ? '▲ Adiantado' : v >= 0.95 ? '● No prazo' : '▼ Atrasado';"
        "  return [v.toFixed(2) + '  ' + interp, 'SPI'];"
        "}"
    )
    return rx.recharts.graphing_tooltip(
        cursor=S.TOOLTIP_CURSOR_LINE,
        content_style=S.TOOLTIP_PREMIUM,
        label_style=S.TOOLTIP_PREMIUM_LABEL,
        item_style=S.TOOLTIP_PREMIUM_ITEM,
        formatter=formatter,
    )


def chart_x_axis(data_key: str, **kwargs) -> rx.Component:
    return rx.recharts.x_axis(
        data_key=data_key,
        stroke=S.TEXT_MUTED,
        font_size=12,
        tick_line=False,
        axis_line=False,
        tick=S.AXIS_TICK,
        **kwargs,
    )


def chart_y_axis(**kwargs) -> rx.Component:
    return rx.recharts.y_axis(
        stroke=S.TEXT_MUTED,
        font_size=12,
        tick_line=False,
        axis_line=False,
        tick=S.AXIS_TICK,
        **kwargs,
    )


# ── KPI Card ─────────────────────────────────────────────────


def kpi_card(
    title: str,
    value,
    icon: str,
    trend: str = "",
    trend_type: str = "neutral",
    is_money: bool = False,
    delay: int = 0,
    on_click: rx.EventHandler = None,
) -> rx.Component:
    """KPI Card with glassmorphism, hover glow, and corner decoration"""

    trend_color = rx.match(
        trend_type,
        ("positive", S.PATINA),
        ("negative", S.DANGER),
        ("warning", S.WARNING),
        S.TEXT_MUTED,
    )

    trend_bg = rx.match(
        trend_type,
        ("positive", S.SUCCESS_BG),
        ("negative", S.DANGER_BG),
        ("warning", S.WARNING_BG),
        "rgba(255, 255, 255, 0.03)",
    )

    return rx.box(
        # Content
        rx.vstack(
            rx.hstack(
                # Icon container
                rx.center(
                    rx.icon(
                        tag=icon,
                        size=24,
                        stroke_width=1.5,
                        color=S.COPPER,
                    ),
                    padding="12px",
                    bg="rgba(255, 255, 255, 0.03)",
                    border_radius="12px",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    class_name="kpi-icon",
                ),
                rx.spacer(),
                # Trend badge
                rx.cond(
                    trend != "",
                    rx.box(
                        rx.text(
                            trend,
                            font_size="12px",  # Increased from 10px
                            font_weight="700",
                            letter_spacing="0.05em",
                            color=trend_color,
                        ),
                        bg=trend_bg,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        padding="6px 10px",  # Increased padding
                        border_radius="8px",  # Slightly larger radius
                    ),
                ),
                width="100%",
                align="center",
            ),
            rx.vstack(
                rx.text(
                    title,
                    font_size="12px",  # Increased from 10px
                    font_weight="700",
                    color=S.TEXT_MUTED,
                    text_transform="uppercase",
                    letter_spacing="0.2em",
                ),
                rx.text(
                    value,
                    font_family=S.FONT_TECH,
                    font_size="2.5rem",  # Increased from 1.875rem for better C-level visibility
                    font_weight="700",  # Increased from 600
                    color=S.TEXT_PRIMARY,
                    letter_spacing="-0.02em",
                ),
                spacing="2",  # Increased from 1
                align="center",  # Centered for better presentation
                margin_top="20px",  # Increased from 16px
                width="100%",  # Full width for centering
            ),
            spacing="0",
            align="start",
            width="100%",
            position="relative",
            z_index="10",
        ),
        # Corner decoration SVG
        rx.html(
            '<svg width="20" height="20" viewBox="0 0 20 20" style="position:absolute;top:8px;right:8px;opacity:0.3">'
            '<path d="M0,0 L20,0 L20,20" fill="none" stroke="#C98B2A" stroke-width="1"/>'
            "</svg>"
        ),
        class_name="kpi-card",
        position="relative",
        width="100%",
        height="100%",
        # Interactivity
        on_click=on_click,
        cursor="pointer" if on_click else "default",
        _hover=(
            {
                "transform": "translateY(-4px)",
                "box_shadow": "0 10px 30px -10px rgba(201, 139, 42, 0.2)",
                "border_color": S.COPPER,
            }
            if on_click
            else {}
        ),
        transition="all 0.3s ease",
    )


# ── Chart Formatters ─────────────────────────────────────────


def money_formatter_js() -> rx.Var:
    """JS function to format large numbers as money (M/k) - Robust version"""
    return rx.Var(
        "(value) => {"
        "  if (value == null || value === '' || value === '0') return 'R$ 0';"
        "  var v = parseFloat(value);"
        "  if (isNaN(v)) return value;"
        "  if (v >= 1000000) return 'R$ ' + (v/1000000).toFixed(1).replace('.', ',') + 'M';"
        "  if (v >= 1000) return 'R$ ' + (v/1000).toFixed(1).replace('.', ',') + 'k';"
        "  return 'R$ ' + v.toFixed(0);"
        "}"
    )


def number_formatter_js() -> rx.Var:
    """JS function to format large numbers (M/k) without currency"""
    return rx.Var(
        "(value) => {"
        "  if (value == null || value === '' || value === '0') return '0';"
        "  var v = parseFloat(value);"
        "  if (isNaN(v)) return value;"
        "  if (v >= 1000000) return (v/1000000).toFixed(1).replace('.', ',') + 'M';"
        "  if (v >= 1000) return (v/1000).toFixed(1).replace('.', ',') + 'k';"
        "  return v.toFixed(0);"
        "}"
    )


# ── Bar Charts ───────────────────────────────────────────────


def bar_chart_horizontal(
    data,
    y_key: str,
    x_key: str,
    label_key: str = None,  # Optional key for custom formatted labels
    fill: str = S.COPPER,
    height: int = 350,
) -> rx.Component:
    return rx.recharts.bar_chart(
        dark_cartesian_grid(),
        rx.recharts.bar(
            rx.recharts.label_list(
                data_key=label_key if label_key else x_key,
                position="right",
                fill=S.TEXT_PRIMARY,
                font_size=13,
            ),
            data_key=x_key,
            fill=fill,
            radius=[0, 4, 4, 0],
            is_animation_active=False,
        ),
        rx.recharts.x_axis(type_="number", hide=True),
        rx.recharts.y_axis(
            data_key=y_key,
            type_="category",
            width=100,
            tick={"fill": S.TEXT_PRIMARY, "fontSize": 14},
            interval=0,
        ),
        TOOLTIP_MONEY,
        data=data,
        layout="vertical",
        height=height,
        margin={"top": 5, "right": 80, "left": 10, "bottom": 5},
    )


# ── Pie / Donut Chart ───────────────────────────────────────


def pie_chart_donut(
    data,
    name_key: str,
    value_key: str,
    height: int = 300,
    colors: list = None,
    use_data_fill: bool = False,
) -> rx.Component:
    if colors is None:
        colors = [S.COPPER, S.PATINA, S.TEXT_PRIMARY, S.ORANGE, S.INFO]

    if use_data_fill:
        return rx.recharts.responsive_container(
            rx.recharts.pie_chart(
                rx.recharts.pie(
                    rx.foreach(
                        data,
                        lambda item: rx.recharts.cell(fill=item["fill"]),
                    ),
                    data=data,
                    data_key=value_key,
                    name_key=name_key,
                    cx="50%",
                    cy="50%",
                    inner_radius="55%",
                    outer_radius="85%",
                    padding_angle=4,
                    stroke="none",
                    is_animation_active=False,
                ),
                TOOLTIP_PIE,
            ),
            width="100%",
            height=height,
        )

    return rx.recharts.responsive_container(
        rx.recharts.pie_chart(
            rx.recharts.pie(
                data=data,
                data_key=value_key,
                name_key=name_key,
                cx="50%",
                cy="50%",
                inner_radius="55%",
                outer_radius="85%",
                padding_angle=4,
                stroke="none",
                is_animation_active=False,
                fill=colors[0] if colors else S.COPPER,
            ),
            chart_tooltip(formatter=money_formatter_js()),
        ),
        width="100%",
        height=height,
    )


# ── Composed Chart (O&M) ────────────────────────────────────


def composed_chart_om(
    data,
    x_key: str,
    bar_key: str,  # Acumulado (Bars) - Right Axis
    line1_key: str,  # Geração Prevista (Line) - Left Axis
    line2_key: str,  # Energia Injetada (Line) - Left Axis
    height: int = 400,
) -> rx.Component:
    """
    Composed chart for O&M Performance - Dual Axis.
    Left Axis: Injetada (Solid Teal) & Prevista (Dashed Yellow)
    Right Axis: Acumulado (Dark Bars)
    """
    return rx.recharts.composed_chart(
        dark_cartesian_grid(),
        rx.recharts.x_axis(
            data_key=x_key,
            stroke=S.TEXT_MUTED,
            font_size=12,
            interval=0,
            angle=-45,
            text_anchor="end",
            height=60,
        ),
        # Left Axis - Generation
        rx.recharts.y_axis(
            y_axis_id="left",
            stroke=S.PATINA,
            font_size=12,
            width=40,
            tick_formatter=rx.Var(
                "(val) => { var v = parseFloat(val); if (v >= 1000) return (v/1000).toFixed(0) + 'k'; return v; }"
            ),
        ),
        # Right Axis - Accumulated
        rx.recharts.y_axis(
            y_axis_id="right",
            orientation="right",
            stroke=S.TEXT_MUTED,
            font_size=12,
            width=40,
            tick_formatter=rx.Var(
                "(val) => { var v = parseFloat(val); if (v >= 1000) return (v/1000).toFixed(0) + 'k'; return v; }"
            ),
        ),
        TOOLTIP_GENERIC,
        rx.recharts.legend(
            wrapper_style={"paddingTop": "20px", "fontSize": "12px"},
        ),
        # Bar: Acumulado (Right Axis, Gray/Dark)
        rx.recharts.bar(
            data_key=bar_key,
            y_axis_id="right",
            name="kWh Acumulado",
            fill="rgba(255, 255, 255, 0.1)",
            radius=[4, 4, 0, 0],
            bar_size=20,
        ),
        # Line 1: Geração Prevista (Left Axis, Yellow Dashed)
        rx.recharts.line(
            data_key=line1_key,
            y_axis_id="left",
            name="Geração Prevista (kWh)",
            stroke=S.COPPER,
            stroke_width=2,
            type_="monotone",
            dot=False,
            stroke_dasharray="5 5",
        ),
        # Line 2: Energia Injetada (Left Axis, Teal Solid)
        rx.recharts.line(
            data_key=line2_key,
            y_axis_id="left",
            name="Energia Injetada (kWh)",
            stroke=S.PATINA,
            stroke_width=3,
            type_="monotone",
            dot={"r": 4, "fill": S.BG_VOID, "strokeWidth": 2, "stroke": S.PATINA},
            active_dot={"r": 6},
        ),
        data=data,
        height=height,
        margin={"top": 10, "right": 30, "left": 20, "bottom": 40},
    )


# ── Dual Area Chart ─────────────────────────────────────────


def dual_area_chart(
    data,
    x_key: str,
    y1_key: str,
    y2_key: str,
    stroke1: str = S.PATINA,
    fill1: str = "rgba(42, 157, 143, 0.15)",
    stroke2: str = S.COPPER_LIGHT,
    fill2: str = "rgba(224, 166, 59, 0.15)",
    height: int = 350,
    name1: str = "Injetado",
    name2: str = "Previsto",
) -> rx.Component:
    return rx.recharts.area_chart(
        dark_cartesian_grid(),
        chart_x_axis(x_key),
        chart_y_axis(),
        TOOLTIP_GENERIC,
        rx.recharts.area(
            data_key=y1_key,
            stroke=stroke1,
            fill=fill1,
            stroke_width=3,
            type_="monotone",
            is_animation_active=False,
            name=name1,
            dot={"r": 4, "fill": S.BG_VOID, "strokeWidth": 2},
        ),
        rx.recharts.area(
            data_key=y2_key,
            stroke=stroke2,
            fill=fill2,
            stroke_width=2,
            stroke_dasharray="5 5",
            type_="monotone",
            is_animation_active=False,
            name=name2,
            dot=False,
        ),
        rx.recharts.legend(
            wrapper_style={"fontSize": "12px", "color": S.TEXT_MUTED},
        ),
        data=data,
        height=height,
        margin={"top": 20, "right": 20, "left": 0, "bottom": 20},
    )


# ── Radar Chart ──────────────────────────────────────────────


def radar_chart_dual(
    data,
    subject_key: str,
    a_key: str,
    b_key: str,
    name_a: str = "BOMTEMPO",
    name_b: str = "Média Mercado",
    height: int = 400,
) -> rx.Component:
    return rx.recharts.radar_chart(
        rx.recharts.polar_grid(stroke="rgba(255, 255, 255, 0.06)"),
        rx.recharts.polar_angle_axis(
            data_key=subject_key,
            stroke=S.TEXT_MUTED,
            font_size=12,
            tick={"fill": S.TEXT_MUTED},
        ),
        rx.recharts.polar_radius_axis(
            angle=30,
            domain=[0, 100],
        ),
        rx.recharts.radar(
            data_key=a_key,
            name=name_a,
            stroke=S.COPPER,
            fill=S.COPPER,
            fill_opacity=0.6,
        ),
        rx.recharts.radar(
            data_key=b_key,
            name=name_b,
            stroke=S.PATINA,
            fill=S.PATINA,
            fill_opacity=0.3,
        ),
        rx.recharts.legend(),
        TOOLTIP_GENERIC,
        data=data,
        cx="50%",
        cy="50%",
        outer_radius="80%",
        height=height,
    )
