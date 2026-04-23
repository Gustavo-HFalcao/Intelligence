"""
RDO Wizard Stepper — Enterprise Mobile-First
Equipe → Equipamentos → Serviços → Ocorrências → Revisão

Usage:
    from bomtempo.components.rdo.stepper import wizard_stepper, wizard_nav_buttons
    wizard_stepper(current_step=RDOState.current_step, labels=[...])
    wizard_nav_buttons(on_back=..., on_next=..., is_last_step=..., is_loading=...)
"""

import reflex as rx

from bomtempo.core import styles as S


def _step_circle(
    step_num: int,
    current_step,
    total: int = 5,
) -> rx.Component:
    """
    Individual step circle with:
    - Active: copper bg + glow pulse
    - Done: patina bg + check icon
    - Pending: subtle bg
    """
    is_active = current_step == step_num
    is_done = current_step > step_num

    return rx.box(
        rx.cond(
            is_done,
            rx.icon(tag="check", size=14, color="white"),
            rx.text(
                str(step_num),
                font_size="11px",
                font_weight="700",
                color=rx.cond(is_active, "#0A1F1A", S.TEXT_MUTED),
            ),
        ),
        width="32px",
        height="32px",
        border_radius="50%",
        display="flex",
        align_items="center",
        justify_content="center",
        bg=rx.cond(
            is_active,
            S.COPPER,
            rx.cond(is_done, S.PATINA, "rgba(255,255,255,0.06)"),
        ),
        border=rx.cond(
            is_active,
            f"2px solid {S.COPPER}",
            rx.cond(is_done, f"2px solid {S.PATINA}", "2px solid rgba(255,255,255,0.12)"),
        ),
        flex_shrink="0",
        transition="all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        class_name=rx.cond(
            is_active, "stepper-dot-active", rx.cond(is_done, "stepper-dot-done", "")
        ),
    )


def _connector_line(step_num: int, current_step) -> rx.Component:
    """Connecting line between step circles."""
    is_complete = current_step > step_num
    return rx.box(
        height="2px",
        flex="1",
        min_width="16px",
        bg=rx.cond(is_complete, S.PATINA, "rgba(255,255,255,0.08)"),
        transition="background 0.4s ease",
        border_radius="1px",
    )


def wizard_stepper(
    current_step,
    labels: list[str],
) -> rx.Component:
    """
    Full stepper bar with circles, connectors and labels.
    Drop this at the top of a wizard form instead of the old _progress_bar().

    Args:
        current_step: Reflex state var (int) — 1-based step index
        labels: List of step label strings
    """
    total = len(labels)
    steps_and_connectors = []
    for i, label in enumerate(labels):
        step_num = i + 1
        steps_and_connectors.append(
            rx.vstack(
                rx.hstack(
                    _step_circle(step_num, current_step, total),
                    _connector_line(step_num, current_step) if i < total - 1 else rx.fragment(),
                    spacing="0",
                    align="center",
                    flex="1" if i < total - 1 else "0",
                    width="100%" if i < total - 1 else "auto",
                ),
                rx.text(
                    label,
                    font_size="9px",
                    font_weight=rx.cond(current_step == step_num, "700", "400"),
                    color=rx.cond(
                        current_step == step_num,
                        S.COPPER,
                        rx.cond(current_step > step_num, S.PATINA, S.TEXT_MUTED),
                    ),
                    text_align="center",
                    white_space="nowrap",
                    overflow="hidden",
                    text_overflow="ellipsis",
                    max_width="64px",
                    transition="color 0.3s ease",
                ),
                align="center",
                spacing="1",
                flex="1" if i < total - 1 else "0",
            )
        )

    return rx.box(
        rx.hstack(
            *steps_and_connectors,
            width="100%",
            align="start",
            spacing="0",
        ),
        width="100%",
        padding_x="4px",
        padding_y="8px",
    )


def wizard_nav_buttons(
    on_back,
    on_next,
    is_last_step,
    is_loading=False,
    back_label: str = "Voltar",
    next_label: str = "Próximo",
    submit_label: str = "Finalizar",
) -> rx.Component:
    """
    Mobile-first navigation buttons.
    - Back: left ghost button
    - Next/Submit: right copper button (min-height 52px for touch)
    Both fixed to bottom on mobile.
    """
    return rx.hstack(
        # Back button
        rx.button(
            rx.hstack(
                rx.icon(tag="arrow-left", size=16),
                rx.text(back_label, font_weight="600"),
                spacing="2",
                align="center",
            ),
            on_click=on_back,
            bg="transparent",
            color=S.TEXT_MUTED,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius="12px",
            height="52px",
            padding_x="20px",
            _hover={"bg": "rgba(255,255,255,0.04)", "border_color": S.COPPER, "color": "white"},
            transition="all 0.15s ease",
        ),
        rx.spacer(),
        # Next / Submit button
        rx.button(
            rx.cond(
                is_loading,
                rx.hstack(
                    rx.spinner(size="1", color="#0A1F1A"),
                    rx.text("Enviando...", font_weight="700"),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.text(
                        rx.cond(is_last_step, submit_label, next_label),
                        font_weight="700",
                    ),
                    rx.icon(
                        tag=rx.cond(is_last_step, "check", "arrow-right"),
                        size=16,
                    ),
                    spacing="2",
                    align="center",
                ),
            ),
            on_click=on_next,
            bg=S.COPPER,
            color="#0A1F1A",
            border_radius="12px",
            height="52px",
            padding_x="24px",
            _hover={"bg": S.COPPER_LIGHT},
            is_loading=is_loading,
            transition="all 0.15s ease",
        ),
        width="100%",
        align="center",
        padding_top="24px",
        padding_bottom=["80px", "80px", "24px"],  # Extra bottom padding on mobile for fixed layout
    )
