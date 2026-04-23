"""
Chat Input Area — Premium enterprise input bar.
Desktop: max-width 760px, centered.
Mobile: 100% width, 12px lateral padding.
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState

from .chat_suggestions import suggestion_chips


def chat_input_area() -> rx.Component:
    """
    Full chat input section:
    - Suggestion chips (auto-submit on click)
    - Text input with voice + send buttons
    - Disclaimer footer
    """
    return rx.box(
        rx.box(
            suggestion_chips(),
            # ── Input Row ────────────────────────────────────────────────
            rx.hstack(
                rx.input(
                    id="chat_main_input",
                    value=GlobalState.current_question,
                    on_change=GlobalState.set_current_question,
                    placeholder="Pergunte sobre rentabilidade, prazos críticos ou performance...",
                    width="100%",
                    height="56px",
                    bg="rgba(0, 0, 0, 0.4)",
                    border="1px solid rgba(255, 255, 255, 0.09)",
                    color="white",
                    border_radius="999px",
                    padding_left="24px",
                    padding_right="106px",
                    font_size="14px",
                    _focus={
                        "border_color": S.COPPER,
                        "outline": "none",
                        "box_shadow": f"0 0 0 3px rgba(201, 139, 42, 0.15)",
                    },
                    transition="border-color 0.2s ease, box-shadow 0.2s ease",
                    on_key_down=lambda key: rx.cond(
                        key == "Enter",
                        GlobalState.send_message(),
                        None,
                    ),
                    debounce_timeout=300,
                ),
                # Mic button
                rx.button(
                    rx.icon(tag="mic", size=18),
                    on_click=lambda: [
                        GlobalState.start_recording,
                        rx.call_script("if(window.startRecording) window.startRecording()"),
                    ],
                    position="absolute",
                    right="54px",
                    top="8px",
                    width="40px",
                    height="40px",
                    bg="rgba(255, 255, 255, 0.05)",
                    border="1px solid rgba(255, 255, 255, 0.09)",
                    color=S.COPPER,
                    border_radius="50%",
                    padding="0",
                    _hover={
                        "bg": "rgba(201, 139, 42, 0.12)",
                        "border_color": S.COPPER,
                    },
                    transition="all 0.2s ease",
                    disabled=GlobalState.is_processing_chat,
                ),
                # Send button
                rx.button(
                    rx.cond(
                        GlobalState.is_processing_chat,
                        rx.spinner(size="1", color="#0A1F1A"),
                        rx.icon(tag="send", size=18),
                    ),
                    on_click=GlobalState.send_message,
                    position="absolute",
                    right="8px",
                    top="8px",
                    width="40px",
                    height="40px",
                    bg=f"linear-gradient(135deg, {S.COPPER}, {S.COPPER_LIGHT})",
                    color="#0A1F1A",
                    border_radius="50%",
                    padding="0",
                    _hover={
                        "bg": f"linear-gradient(135deg, {S.COPPER_LIGHT}, {S.COPPER})",
                        "box_shadow": "0 0 16px rgba(201, 139, 42, 0.5)",
                        "transform": "scale(1.05)",
                    },
                    transition="all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
                    disabled=GlobalState.is_processing_chat,
                ),
                position="relative",
                width="100%",
            ),
            width="100%",
        ),
        rx.text(
            "Insights gerados por IA | Utilize para apoio à decisão estratégica",
            font_size="10px",
            color="#A0A0A0",
            font_weight="700",
            text_transform="uppercase",
            letter_spacing="0.15em",
            text_align="center",
            margin_top="16px",
        ),
        padding="24px",
        width="100%",
        class_name="chat-input-area",
    )
