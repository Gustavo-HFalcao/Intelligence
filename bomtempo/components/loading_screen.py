"""
Loading screen components — BOMTEMPO Enterprise UX
"""

import reflex as rx

from bomtempo.core import styles as S


# ─────────────────────────────────────────────────────────────
# Enterprise Post-Login Loader (replaces old generic spinner)
# ─────────────────────────────────────────────────────────────

def loading_screen() -> rx.Component:
    """
    Full-screen enterprise initialization sequence.
    Shows 5 sequential steps with CSS-driven reveal animations.
    Requires .sync-step-* and .loader-progress-fill in style.css.
    """
    steps = [
        ("shield-check", "Autenticando sessão"),
        ("database", "Conectando ao Supabase"),
        ("layout-grid", "Carregando módulos"),
        ("bar-chart-3", "Preparando dados operacionais"),
        ("zap", "Iniciando plataforma"),
    ]

    return rx.box(
        # Scan line
        rx.box(class_name="sync-scan-line"),
        # Grid background (decorative)
        rx.box(
            position="absolute",
            top="0", left="0", right="0", bottom="0",
            opacity="0.04",
            background_image=(
                "linear-gradient(var(--copper-500) 1px, transparent 1px),"
                " linear-gradient(90deg, var(--copper-500) 1px, transparent 1px)"
            ),
            background_size="48px 48px",
            pointer_events="none",
        ),
        # Copper glow orb
        rx.box(
            position="absolute",
            top="-100px", left="50%",
            width="400px", height="400px",
            border_radius="50%",
            bg="rgba(201, 139, 42, 0.05)",
            filter="blur(100px)",
            pointer_events="none",
            style={"transform": "translateX(-50%)"},
        ),
        # Content
        rx.center(
            rx.vstack(
                # Brand lockup
                rx.vstack(
                    rx.image(
                        src="/banner.png",
                        width="220px",
                        object_fit="contain",
                        class_name="sidebar-logo-img",
                        style={"filter": "drop-shadow(0 0 8px rgba(201,139,42,0.12))"},
                    ),
                    rx.text(
                        "INICIANDO PLATAFORMA",
                        font_family=S.FONT_TECH,
                        font_size="0.65rem",
                        font_weight="700",
                        color=S.COPPER,
                        letter_spacing="0.28em",
                        opacity="0.75",
                    ),
                    spacing="3",
                    align="center",
                ),
                # Progress bar
                rx.box(
                    rx.box(class_name="loader-progress-fill"),
                    width="300px",
                    height="2px",
                    bg="rgba(255,255,255,0.06)",
                    overflow="hidden",
                ),
                # Step list
                rx.vstack(
                    *[
                        rx.hstack(
                            rx.box(
                                rx.text(
                                    str(i + 1),
                                    font_family=S.FONT_MONO,
                                    font_size="9px",
                                    color=S.COPPER,
                                    font_weight="700",
                                ),
                                width="20px", height="20px",
                                border_radius=S.R_CONTROL,
                                bg="rgba(201,139,42,0.1)",
                                border="1px solid rgba(201,139,42,0.3)",
                                display="flex",
                                align_items="center",
                                justify_content="center",
                                flex_shrink="0",
                            ),
                            rx.icon(tag=icon_tag, size=12, color=S.TEXT_MUTED),
                            rx.text(
                                label,
                                font_size="12px",
                                color=S.TEXT_MUTED,
                                font_family=S.FONT_BODY,
                            ),
                            rx.spacer(),
                            rx.box(
                                width="5px", height="5px",
                                border_radius="50%",
                                bg=S.COPPER,
                                opacity="0.6",
                                class_name="animate-pulse",
                            ),
                            class_name=f"sync-step-item sync-step-{i + 1}",
                            spacing="3",
                            align="center",
                            width="100%",
                            padding="9px 14px",
                            bg="rgba(255,255,255,0.02)",
                            border=f"1px solid rgba(255,255,255,0.04)",
                            border_radius=S.R_CONTROL,
                        )
                        for i, (icon_tag, label) in enumerate(steps)
                    ],
                    spacing="2",
                    width="100%",
                    max_width="340px",
                ),
                spacing="5",
                align="center",
                position="relative",
                z_index="1",
                max_width="400px",
            ),
            width="100%",
            height="100%",
            position="relative",
            z_index="1",
        ),
        # Outer wrapper
        position="fixed",
        top="0", left="0",
        width="100vw", height="100vh",
        bg=S.BG_VOID,
        z_index="9999",
        overflow="hidden",
        display="flex",
        align_items="center",
        justify_content="center",
    )


# ─────────────────────────────────────────────────────────────
# Skeleton helpers (used by default.py layout)
# ─────────────────────────────────────────────────────────────

def page_transition_wrapper(content: rx.Component, page_name: str = "") -> rx.Component:
    return rx.box(content, class_name="page-fade-in", animation_delay="0.1s")


def skeleton_line(width: str = "100%", height: str = "12px", radius: str = "6px") -> rx.Component:
    return rx.box(
        width=width, height=height, border_radius=radius,
        bg="rgba(255, 255, 255, 0.05)",
        class_name="skeleton-shimmer",
    )


def skeleton_block(width: str = "100%", height: str = "60px", radius: str = "8px") -> rx.Component:
    return rx.box(
        width=width, height=height, border_radius=radius,
        bg="rgba(255, 255, 255, 0.05)",
        class_name="skeleton-shimmer",
    )


def skeleton_kpi() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                skeleton_block(width="44px", height="44px", radius="4px"),
                rx.spacer(),
                skeleton_line(width="60px", height="22px"),
                width="100%",
            ),
            skeleton_line(width="80px", height="36px"),
            skeleton_line(width="120px", height="10px"),
            spacing="4", width="100%",
        ),
        background=S.BG_GLASS,
        backdrop_filter="blur(12px)",
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius=S.R_CARD,
        padding="24px",
        min_height="130px",
    )


def skeleton_chart(height: str = "300px") -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                skeleton_line(width="160px", height="18px"),
                rx.spacer(),
                skeleton_line(width="80px", height="12px"),
                width="100%",
            ),
            skeleton_block(width="100%", height=height, radius="4px"),
            spacing="4", width="100%",
        ),
        background=S.BG_GLASS,
        backdrop_filter="blur(12px)",
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius=S.R_CARD,
        padding="32px",
        width="100%",
    )


def skeleton_kpi_grid() -> rx.Component:
    return rx.grid(
        skeleton_kpi(),
        skeleton_kpi(),
        skeleton_kpi(),
        skeleton_kpi(),
        columns=rx.breakpoints(initial="1", sm="2", lg="4"),
        spacing="6",
        width="100%",
    )


def loading_wrapper(is_loading, skeleton_layout: rx.Component, content: rx.Component) -> rx.Component:
    return rx.cond(
        is_loading,
        skeleton_layout,
        rx.box(content, class_name="animate-enter"),
    )


def empty_state(
    title: str = "Nenhum dado encontrado",
    subtitle: str = "Os dados aparecerão aqui quando disponíveis.",
    icon: str = "inbox",
) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.box(rx.icon(tag=icon, size=48, color=S.TEXT_MUTED), class_name="empty-state-icon"),
            rx.text(title, class_name="empty-state-title"),
            rx.text(subtitle, class_name="empty-state-subtitle"),
            class_name="empty-state",
            align="center",
            spacing="2",
        ),
        width="100%",
        min_height="200px",
    )


def inline_spinner(text: str = "Processando...") -> rx.Component:
    return rx.hstack(
        rx.spinner(size="1", color=S.COPPER),
        rx.text(text, font_size="12px", color=S.TEXT_MUTED, font_weight="500"),
        spacing="2",
        align="center",
    )
