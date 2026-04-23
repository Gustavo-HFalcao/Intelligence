"""
Chat Suggestion Chips — Premium copper pill buttons.
Clicking auto-fills input AND submits.
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState

_SUGGESTIONS = [
    "Resumir dados",
    "Detectar riscos",
    "Status Financeiro",
    "Gerar insights",
]


def suggestion_chips() -> rx.Component:
    """
    Horizontal scrollable row of copper pill suggestion chips.
    Click: fills input AND triggers send_message.
    """
    return rx.hstack(
        *[
            rx.button(
                suggestion,
                cursor="pointer",
                class_name="suggestion-chip",
                on_click=[
                    GlobalState.set_current_question(suggestion),
                    GlobalState.send_message(),
                ],
                bg="rgba(201, 139, 42, 0.08)",
                color=S.COPPER,
                border="1px solid rgba(201, 139, 42, 0.25)",
                border_radius="999px",
                padding_x="14px",
                padding_y="6px",
                font_size="12px",
                font_weight="600",
                letter_spacing="0.03em",
                font_family=S.FONT_TECH,
                transition="all 0.15s ease",
            )
            for suggestion in _SUGGESTIONS
        ],
        spacing="2",
        margin_bottom="12px",
        overflow_x="auto",
        width="100%",
        padding_bottom="4px",
        class_name="no-scrollbar",
        flex_shrink="0",
    )
