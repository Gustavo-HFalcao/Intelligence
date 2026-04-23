"""
Chat Typing Indicator — Animated 3-dot bounce + optional tool status label.
Shown while GlobalState.is_processing_chat is True.
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState


def typing_indicator() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.center(
                rx.icon(tag="bot", size=14, color="#0A1F1A"),
                width="32px",
                height="32px",
                border_radius="50%",
                bg=S.COPPER,
                flex_shrink="0",
                box_shadow=f"0 0 12px {S.COPPER_GLOW}",
            ),
            rx.box(
                rx.hstack(
                    rx.box(class_name="typing-dot"),
                    rx.box(class_name="typing-dot"),
                    rx.box(class_name="typing-dot"),
                    rx.cond(
                        GlobalState.chat_tool_label != "",
                        rx.text(
                            GlobalState.chat_tool_label,
                            font_size="11px",
                            color=S.TEXT_MUTED,
                            font_style="italic",
                            margin_left="8px",
                        ),
                    ),
                    spacing="1",
                    align="center",
                    padding_y="2px",
                ),
                bg="rgba(255, 255, 255, 0.04)",
                backdrop_filter="blur(12px)",
                padding="14px 20px",
                border_radius="18px",
                border_top_left_radius="4px",
                border="1px solid rgba(255, 255, 255, 0.07)",
                box_shadow="0 4px 24px rgba(0, 0, 0, 0.3)",
                width="fit-content",
            ),
            spacing="3",
            align="start",
            justify="start",
            width="100%",
        ),
        width="100%",
        padding_y="6px",
    )
