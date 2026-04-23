import reflex as rx

from bomtempo.components.charts import (
    dark_cartesian_grid,
    radar_chart_dual,
)
from bomtempo.components.tooltips import TOOLTIP_GENERIC
from bomtempo.components.skeletons import page_loading_skeleton
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState


def analytics_header() -> rx.Component:
    return rx.vstack(
        rx.text("Analytics & Benchmarking", **S.PAGE_TITLE_STYLE),
        rx.text("Análise Comparativa e Indicadores de Maturidade", **S.PAGE_SUBTITLE_STYLE),
        spacing="1",
        class_name="animate-enter",
    )


def analytics_stat_card(label: str, value: str, icon: str) -> rx.Component:
    """Compact stat card matching React reference analytics cards"""
    return rx.box(
        rx.hstack(
            rx.center(
                rx.icon(tag=icon, size=20, color=S.COPPER),
                padding="12px",
                bg="rgba(255, 255, 255, 0.03)",
                border_radius="12px",
                border=f"1px solid {S.BORDER_SUBTLE}",
            ),
            rx.vstack(
                rx.text(
                    label,
                    font_size="10px",
                    font_weight="900",
                    color=S.TEXT_MUTED,
                    text_transform="uppercase",
                ),
                rx.text(
                    value,
                    font_family=S.FONT_MONO,
                    font_size="1.25rem",
                    font_weight="700",
                    color="white",
                ),
                spacing="0",
                align="start",
            ),
            spacing="4",
            align="center",
            width="100%",
        ),
        **{k: v for k, v in S.GLASS_CARD_NO_HOVER.items() if k != "padding"},
        padding="24px",
    )


def analytics_kpi_grid() -> rx.Component:
    return rx.grid(
        analytics_stat_card("Eficiência de Capéx", "94%", "trending-up"),
        analytics_stat_card("OEE Global", "88.2%", "zap"),
        analytics_stat_card("SLA Cumprimento", "98%", "shield-check"),
        analytics_stat_card("Taxa de Retrabalho", "1.2%", "triangle-alert"),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="6",
        width="100%",
    )


def radar_section() -> rx.Component:
    """Radar de Maturidade matching React reference"""
    radar_data = [
        {"subject": "Financeiro", "A": 85, "B": 70},
        {"subject": "Prazo", "A": 70, "B": 65},
        {"subject": "Qualidade", "A": 95, "B": 80},
        {"subject": "Segurança", "A": 100, "B": 90},
        {"subject": "Sustentabilidade", "A": 90, "B": 60},
        {"subject": "Inovação", "A": 80, "B": 50},
    ]

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="target", size=20, color=S.COPPER, margin_right="12px"),
                rx.text(
                    "Radar de Maturidade",
                    font_family=S.FONT_TECH,
                    font_size="1.25rem",
                    font_weight="700",
                    color="white",
                ),
                align="center",
                margin_bottom="24px",
            ),
            rx.box(
                radar_chart_dual(
                    data=radar_data,
                    subject_key="subject",
                    a_key="A",
                    b_key="B",
                    name_a="BOMTEMPO",
                    name_b="Média Mercado",
                    height=400,
                ),
                width="100%",
                height="400px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
    )


def benchmark_section() -> rx.Component:
    """Benchmarking de Mercado - Horizontal grouped bar"""
    benchmark_data = [
        {"metric": "Custo/kWp", "bomtempo": 3200, "market": 3500},
        {"metric": "Prazo Médio (Dias)", "bomtempo": 45, "market": 60},
        {"metric": "Performance Ratio", "bomtempo": 82, "market": 78},
    ]

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="bar-chart-3", size=20, color=S.COPPER, margin_right="12px"),
                rx.text(
                    "Benchmarking de Mercado",
                    font_family=S.FONT_TECH,
                    font_size="1.25rem",
                    font_weight="700",
                    color="white",
                ),
                align="center",
                margin_bottom="24px",
            ),
            rx.box(
                rx.recharts.bar_chart(
                    dark_cartesian_grid(),
                    rx.recharts.x_axis(
                        type_="number", stroke=S.TEXT_MUTED, font_size=10, hide=True
                    ),
                    rx.recharts.y_axis(
                        data_key="metric",
                        type_="category",
                        stroke=S.TEXT_PRIMARY,
                        font_size=12,
                        width=100,
                    ),
                    TOOLTIP_GENERIC,
                    rx.recharts.legend(),
                    rx.recharts.bar(
                        data_key="bomtempo",
                        name="BOMTEMPO",
                        fill=S.COPPER,
                        radius=[0, 4, 4, 0],
                    ),
                    rx.recharts.bar(
                        data_key="market",
                        name="Mercado",
                        fill=S.PATINA,
                        radius=[0, 4, 4, 0],
                    ),
                    data=benchmark_data,
                    layout="vertical",
                    height=400,
                    bar_gap=2,
                    bar_category_gap="20%",
                ),
                width="100%",
                height="400px",
            ),
            width="100%",
        ),
        **S.GLASS_CARD,
    )


def _em_construcao_banner() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.center(
                rx.icon(tag="construction", size=20, color="#F59E0B"),
                width="40px",
                height="40px",
                border_radius="10px",
                bg="rgba(245,158,11,0.12)",
                border="1px solid rgba(245,158,11,0.3)",
                flex_shrink="0",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(
                        "EM CONSTRUÇÃO",
                        font_family="Rajdhani, sans-serif",
                        font_size="0.75rem",
                        font_weight="800",
                        letter_spacing="0.18em",
                        color="#F59E0B",
                    ),
                    rx.badge("DADOS MOCKADOS", color_scheme="amber", variant="soft", size="1"),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    "Esta página exibe dados simulados para fins de demonstração. Os módulos de Analytics e Benchmarking serão integrados com dados reais em breve.",
                    font_size="0.82rem",
                    color="rgba(255,255,255,0.55)",
                    line_height="1.5",
                ),
                spacing="1",
                align="start",
            ),
            spacing="4",
            align="center",
            width="100%",
        ),
        bg="rgba(245,158,11,0.06)",
        border="1px solid rgba(245,158,11,0.25)",
        border_radius="12px",
        padding="16px 20px",
        width="100%",
    )


def analytics_page() -> rx.Component:
    return rx.vstack(
        analytics_header(),
        _em_construcao_banner(),
        rx.cond(
            GlobalState.is_loading,
            page_loading_skeleton(),
            rx.vstack(
                analytics_kpi_grid(),
                rx.grid(
                    radar_section(),
                    benchmark_section(),
                    columns=rx.breakpoints(initial="1", lg="2"),
                    spacing="8",
                    width="100%",
                ),
                width="100%",
                spacing="8",
            ),
        ),
        width="100%",
        spacing="6",
        class_name="animate-enter",
    )
