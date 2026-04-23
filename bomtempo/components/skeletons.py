"""
Skeleton Loading Components — BOMTEMPO Deep Tectonic Theme

Replaces generic rx.spinner with contextual, branded skeleton screens.
All @keyframes are defined in assets/style.css.
Step reveal uses CSS animation-delay (pure CSS, no Python state needed).

Public API:
    page_loading_skeleton()  — Generic full-page skeleton (hero + KPIs + charts)
    rdo_sync_loader()        — Radar-style sync loader for RDO Dashboard
    kpi_row_skeleton(count)  — Row of N KPI card skeletons
    chart_bar_skeleton()     — Bar chart placeholder
    chart_donut_skeleton()   — Donut/pie chart placeholder
    table_skeleton(rows)     — Table rows placeholder
"""

import reflex as rx

from bomtempo.core import styles as S


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _skel(
    width: str = "100%",
    height: str = "12px",
    radius: str = "6px",
    **props,
) -> rx.Component:
    """Minimal skeleton placeholder block (uses .skel-block CSS class)."""
    return rx.box(
        class_name="skel-block",
        width=width,
        height=height,
        border_radius=radius,
        **props,
    )


def _glass_skel_card(**props) -> dict:
    """Base style dict for a glass skeleton card container."""
    return {
        "background": S.BG_GLASS,
        "backdrop_filter": "blur(12px)",
        "border": f"1px solid {S.BORDER_SUBTLE}",
        "border_radius": "20px",
        "box_shadow": "0 4px 30px rgba(0, 0, 0, 0.3)",
        "position": "relative",
        "overflow": "hidden",
        **props,
    }


def _radar_ring(size: str, ring_num: int) -> rx.Component:
    return rx.box(
        class_name=f"radar-ring-{ring_num}",
        position="absolute",
        top="50%", left="50%",
        width=size, height=size,
        border_radius="50%",
        border="1px solid rgba(201,139,42,0.2)",
        style={"transform": "translate(-50%, -50%)"},
    )


def _sync_step(label: str, step_num: int) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.text("↻", class_name="step-icon-spin", font_size="11px", color=S.COPPER),
            width="20px", height="20px",
            border_radius="50%",
            background="rgba(201,139,42,0.12)",
            border="1.5px solid rgba(201,139,42,0.3)",
            flex_shrink="0",
        ),
        rx.text(label, font_size="13px", color=S.TEXT_MUTED),
        class_name=f"sync-step-item sync-step-{step_num}",
        spacing="3",
        align="center",
        background="rgba(255,255,255,0.02)",
        border=f"1px solid rgba(255,255,255,0.05)",
        border_radius="10px",
        padding="9px 14px",
        width="100%",
    )


# ─────────────────────────────────────────────────────────────
# KPI Card Skeleton
# ─────────────────────────────────────────────────────────────

def kpi_skeleton() -> rx.Component:
    """Single KPI card skeleton with copper shimmer wave."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                _skel("40px", "40px", "10px"),
                rx.spacer(),
                _skel("55px", "18px", "6px"),
                width="100%",
                align="center",
            ),
            _skel("70%", "10px"),
            _skel("52%", "28px", "8px"),
            _skel("38%", "9px"),
            spacing="3",
            width="100%",
        ),
        class_name="kpi-card skel-shimmer",
        padding="24px",
        flex="1",
        min_width="160px",
    )


def kpi_row_skeleton(count: int = 4) -> rx.Component:
    """Horizontal row of N KPI skeletons."""
    return rx.flex(
        *[kpi_skeleton() for _ in range(count)],
        gap="16px",
        flex_wrap="wrap",
        width="100%",
    )


# ─────────────────────────────────────────────────────────────
# Bar Chart Skeleton
# ─────────────────────────────────────────────────────────────

def _skel_bar(height_pct: str, bar_index: int) -> rx.Component:
    return rx.box(
        class_name=f"skel-bar-{bar_index}",
        flex="1",
        height=height_pct,
        border_radius="4px 4px 0 0",
        background="rgba(201,139,42,0.09)",
        border="1px solid rgba(201,139,42,0.12)",
        align_self="flex-end",
    )


def chart_bar_skeleton(height: str = "220px") -> rx.Component:
    """Bar chart skeleton with pulsing animated bars."""
    bars = [("55%", 1), ("80%", 2), ("42%", 3), ("95%", 4),
            ("65%", 5), ("72%", 6), ("50%", 7), ("88%", 8)]
    return rx.box(
        rx.vstack(
            # Chart header
            rx.hstack(
                _skel("32px", "32px", "10px"),
                rx.vstack(
                    _skel("160px", "12px"),
                    _skel("100px", "9px"),
                    spacing="1",
                    align="start",
                ),
                spacing="3",
                align="center",
                margin_bottom="16px",
            ),
            # Bars
            rx.flex(
                *[_skel_bar(h, i) for h, i in bars],
                height=height,
                gap="10px",
                align_items="flex-end",
                width="100%",
            ),
            # Axis labels
            rx.hstack(
                *[_skel("30px", "8px") for _ in range(4)],
                justify="between",
                width="100%",
                margin_top="8px",
            ),
            spacing="0",
            width="100%",
        ),
        class_name="skel-shimmer",
        padding="24px",
        flex="1",
        min_width="280px",
        **_glass_skel_card(),
    )


# ─────────────────────────────────────────────────────────────
# Donut / Pie Chart Skeleton  (SVG via rx.html)
# ─────────────────────────────────────────────────────────────

def chart_donut_skeleton() -> rx.Component:
    """Donut chart skeleton using inline SVG (rx.html)."""
    svg = rx.html(
        '<svg width="130" height="130" style="transform:rotate(-90deg)">'
        '<circle cx="65" cy="65" r="52" fill="none"'
        ' stroke="rgba(255,255,255,0.05)" stroke-width="16"/>'
        '<circle cx="65" cy="65" r="52" fill="none"'
        ' stroke="rgba(201,139,42,0.15)" stroke-width="16"'
        ' stroke-dasharray="326" stroke-dashoffset="80" class="donut-arc-1"/>'
        '<circle cx="65" cy="65" r="52" fill="none"'
        ' stroke="rgba(42,157,143,0.12)" stroke-width="16"'
        ' stroke-dasharray="326" stroke-dashoffset="210" class="donut-arc-2"/>'
        "</svg>"
    )
    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                _skel("32px", "32px", "10px"),
                rx.vstack(
                    _skel("140px", "12px"),
                    _skel("90px", "9px"),
                    spacing="1",
                    align="start",
                ),
                spacing="3",
                align="center",
                margin_bottom="16px",
            ),
            # Donut
            rx.center(
                rx.vstack(
                    svg,
                    _skel("48px", "16px", "6px"),
                    _skel("32px", "9px", "4px"),
                    spacing="1",
                    align="center",
                ),
            ),
            spacing="0",
            width="100%",
        ),
        class_name="skel-shimmer",
        padding="24px",
        flex="1",
        min_width="220px",
        **_glass_skel_card(),
    )


# ─────────────────────────────────────────────────────────────
# Table Skeleton
# ─────────────────────────────────────────────────────────────

def _table_row_skel(opacity: float = 1.0) -> rx.Component:
    return rx.hstack(
        _skel("28%", "12px"),
        _skel("15%", "12px"),
        # Badge placeholder (copper-tinted)
        rx.box(
            class_name="skel-block",
            width="65px", height="20px", border_radius="6px",
            background="rgba(201,139,42,0.08)",
            border="1px solid rgba(201,139,42,0.12)",
        ),
        _skel("18%", "12px"),
        _skel("10%", "12px"),
        spacing="4",
        width="100%",
        align="center",
        padding="13px 16px",
        border_bottom=f"1px solid rgba(255,255,255,0.04)",
        opacity=str(opacity),
    )


def table_skeleton(rows: int = 5) -> rx.Component:
    """Table skeleton with progressively fading rows."""
    opacities = [1.0, 0.88, 0.72, 0.52, 0.32]
    return rx.box(
        rx.vstack(
            # Header row
            rx.hstack(
                *[_skel("70px", "8px") for _ in range(5)],
                spacing="4",
                width="100%",
                padding="11px 16px",
                background="rgba(255,255,255,0.02)",
                border_bottom=f"1px solid {S.BORDER_SUBTLE}",
            ),
            # Data rows
            *[
                _table_row_skel(opacities[i] if i < len(opacities) else 0.25)
                for i in range(rows)
            ],
            spacing="0",
            width="100%",
        ),
        class_name="skel-shimmer",
        **_glass_skel_card(border_radius="20px"),
    )


# ─────────────────────────────────────────────────────────────
# Hero Banner Skeleton
# ─────────────────────────────────────────────────────────────

def hero_skeleton() -> rx.Component:
    """Page hero banner skeleton."""
    return rx.box(
        rx.vstack(
            _skel("80px", "22px", "4px"),   # badge
            rx.hstack(
                _skel("40px", "40px", "8px"),
                _skel("240px", "36px", "6px"),
                spacing="3",
                align="center",
            ),
            _skel("58%", "13px"),
            _skel("44%", "13px"),
            spacing="4",
            width="100%",
        ),
        class_name="skel-shimmer",
        padding=S.PADDING_HERO,
        width="100%",
        **_glass_skel_card(border_radius="24px"),
    )


# ─────────────────────────────────────────────────────────────
# Full Page Loading Skeleton
# ─────────────────────────────────────────────────────────────

def page_loading_skeleton() -> rx.Component:
    """
    Generic full-page skeleton: hero banner → 4 KPI cards → bar + donut charts.
    Replaces `rx.center(rx.spinner(...), height='50vh')` on all data pages.
    """
    return rx.vstack(
        hero_skeleton(),
        kpi_row_skeleton(4),
        rx.flex(
            chart_bar_skeleton(),
            chart_donut_skeleton(),
            gap="16px",
            flex_wrap="wrap",
            width="100%",
        ),
        width="100%",
        spacing="6",
        class_name="animate-enter",
    )


# ─────────────────────────────────────────────────────────────
# Compact Page Centered Loader (Alertas, Reembolso, Usuários…)
# ─────────────────────────────────────────────────────────────

def page_centered_loader(
    title: str = "CARREGANDO DADOS",
    subtitle: str = "Conectando ao banco de dados operacional…",
    icon: str = "database",
    **props,
) -> rx.Component:
    """
    Compact branded loader — copper radar rings + scan line + title.
    Lighter than rdo_sync_loader: no step list, smaller rings (140px).
    All animations via CSS @keyframes in assets/style.css.
    """
    SIZE = "140px"
    return rx.box(
        rx.box(class_name="sync-scan-line"),
        # ── Background grid (decorative) ──
        rx.box(
            position="absolute",
            top="0", left="0", right="0", bottom="0",
            opacity="0.04",
            background_image=(
                "linear-gradient(var(--copper-500) 1px, transparent 1px),"
                " linear-gradient(90deg, var(--copper-500) 1px, transparent 1px)"
            ),
            background_size="40px 40px",
            pointer_events="none",
        ),
        rx.center(
            rx.vstack(
                # Radar rings
                rx.box(
                    _radar_ring("44px", 1),
                    _radar_ring("80px", 2),
                    _radar_ring("116px", 3),
                    _radar_ring(SIZE, 4),
                    rx.box(
                        class_name="radar-sweep-anim",
                        position="absolute",
                        top="0", left="0", right="0", bottom="0",
                        border_radius="50%",
                        background="conic-gradient(from 0deg, transparent 75%, rgba(201,139,42,0.35) 100%)",
                    ),
                    rx.center(
                        rx.icon(tag=icon, size=16, color=S.COPPER),
                        class_name="radar-center-glow",
                        position="absolute",
                        top="50%", left="50%",
                        width="32px", height="32px",
                        border_radius="50%",
                        background="rgba(201,139,42,0.12)",
                        border="1.5px solid rgba(201,139,42,0.5)",
                        style={"transform": "translate(-50%, -50%)"},
                    ),
                    position="relative",
                    width=SIZE,
                    height=SIZE,
                ),
                rx.text(
                    title,
                    font_family=S.FONT_TECH,
                    font_size="clamp(14px, 2.5vw, 18px)",
                    font_weight="700",
                    letter_spacing="0.06em",
                    color="white",
                    text_align="center",
                ),
                rx.text(
                    subtitle,
                    font_size="13px",
                    color=S.TEXT_MUTED,
                    text_align="center",
                ),
                spacing="4",
                align="center",
                max_width="380px",
                position="relative",
                z_index="1",
            ),
            width="100%",
            height="100%",
            position="relative",
            z_index="1",
        ),
        **{
            "position": "relative",
            "overflow": "hidden",
            "background": S.BG_DEPTH,
            "border": f"1px solid {S.BORDER_SUBTLE}",
            "border_radius": "20px",
            "padding": "clamp(28px, 4vw, 40px) clamp(20px, 4vw, 32px)",
            "width": "100%",
            "min_height": "320px",
            "class_name": "animate-enter",
            **props,
        },
    )


# ─────────────────────────────────────────────────────────────
# RDO Sync Loader — Radar-style (replaces simple spinner on /rdo-dashboard)
# ─────────────────────────────────────────────────────────────

def rdo_sync_loader() -> rx.Component:
    """
    Sophisticated RDO data sync loader.
    Features: rotating radar sweep, concentric rings, scan-line, sequential step reveal.
    All animated purely via CSS (assets/style.css @keyframes).
    """
    RADAR = "200px"
    steps = [
        "Autenticando sessão",
        "Carregando contratos ativos",
        "Processando registros de RDO",
        "Calculando métricas de performance",
        "Montando painel analítico",
    ]

    return rx.box(
        # ── Background scan grid (purely decorative) ──
        rx.box(
            position="absolute",
            top="0", left="0", right="0", bottom="0",
            opacity="0.05",
            background_image=(
                "linear-gradient(var(--copper-500) 1px, transparent 1px),"
                " linear-gradient(90deg, var(--copper-500) 1px, transparent 1px)"
            ),
            background_size="40px 40px",
            pointer_events="none",
        ),
        # ── Scan line (position absolute via CSS) ──
        rx.box(class_name="sync-scan-line"),
        # ── Centred content ──
        rx.center(
            rx.vstack(
                # Radar visual
                rx.box(
                    _radar_ring("60px", 1),
                    _radar_ring("110px", 2),
                    _radar_ring("160px", 3),
                    _radar_ring(RADAR, 4),
                    # Conic sweep
                    rx.box(
                        class_name="radar-sweep-anim",
                        position="absolute",
                        top="0", left="0", right="0", bottom="0",
                        border_radius="50%",
                        background="conic-gradient(from 0deg, transparent 75%, rgba(201,139,42,0.35) 100%)",
                    ),
                    # Centre icon (no blip dots per review)
                    rx.center(
                        rx.icon(tag="zap", size=18, color=S.COPPER),
                        class_name="radar-center-glow",
                        position="absolute",
                        top="50%", left="50%",
                        width="40px", height="40px",
                        border_radius="50%",
                        background="rgba(201,139,42,0.12)",
                        border="1.5px solid rgba(201,139,42,0.5)",
                        style={"transform": "translate(-50%, -50%)"},
                    ),
                    position="relative",
                    width=RADAR,
                    height=RADAR,
                ),
                # Title + subtitle
                rx.text(
                    "SINCRONIZANDO DADOS",
                    font_family=S.FONT_TECH,
                    font_size="clamp(16px, 3vw, 22px)",
                    font_weight="700",
                    letter_spacing="0.06em",
                    color="white",
                    text_align="center",
                ),
                rx.text(
                    "Conectando ao banco de dados operacional…",
                    font_size="13px",
                    color=S.TEXT_MUTED,
                    text_align="center",
                ),
                # Sequential step checklist
                rx.vstack(
                    *[_sync_step(label, i + 1) for i, label in enumerate(steps)],
                    spacing="2",
                    width="100%",
                    max_width="360px",
                ),
                spacing="4",
                align="center",
                width="100%",
                max_width="440px",
                position="relative",
                z_index="1",
            ),
            width="100%",
            height="100%",
            position="relative",
            z_index="1",
        ),
        # Outer container
        position="relative",
        overflow="hidden",
        background=S.BG_DEPTH,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="20px",
        padding="clamp(32px, 5vw, 48px) clamp(20px, 4vw, 32px)",
        width="100%",
        min_height="520px",
    )
