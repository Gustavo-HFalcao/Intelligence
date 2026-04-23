import time

import reflex as rx

from bomtempo.components.chat.chat_bubble import message_bubble
from bomtempo.components.chat.chat_input import chat_input_area
from bomtempo.components.chat.chat_typing import typing_indicator
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState

# ── Chat Header ───────────────────────────────────────────────────────────────


def chat_header() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.center(
                rx.icon(tag="sparkles", size=20, color="#0A1F1A"),
                width="40px",
                height="40px",
                border_radius="50%",
                bg=S.COPPER,
                box_shadow=f"0 4px 16px {S.COPPER_GLOW}",
            ),
            rx.vstack(
                rx.text(
                    "PLATAFORMA DE INTELIGÊNCIA OPERACIONAL",
                    font_weight="900",
                    color="white",
                    font_size="13px",
                    font_family=S.FONT_TECH,
                    letter_spacing="0.05em",
                ),
                rx.hstack(
                    rx.box(
                        width="6px",
                        height="6px",
                        border_radius="50%",
                        bg="#4ADE80",
                        class_name="pulse-slow",
                    ),
                    rx.text(
                        "IA CONECTADA EM TEMPO REAL",
                        font_size="10px",
                        color="#4ADE80",
                        font_weight="700",
                        text_transform="uppercase",
                        letter_spacing="0.15em",
                    ),
                    spacing="2",
                    align="center",
                ),
                spacing="1",
            ),
            align="center",
            spacing="4",
        ),
        rx.hstack(
            rx.tooltip(
                rx.box(
                    rx.icon(tag="square-pen", size=16, color=S.TEXT_MUTED),
                    on_click=GlobalState.new_conversation,
                    cursor="pointer",
                    padding="6px",
                    border_radius="8px",
                    _hover={"background": "rgba(255,255,255,0.08)", "color": "white"},
                ),
                content="Nova Conversa",
            ),
            rx.tooltip(
                rx.icon(tag="info", size=18, color=S.TEXT_MUTED),
                content="Pergunte sobre Contratos, Cronogramas e Financeiro.",
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        padding="20px 24px",
        justify="between",
        align="center",
        class_name="chat-header",
    )


# ── Chat Messages ─────────────────────────────────────────────────────────────


def chat_messages() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.foreach(
                GlobalState.chat_history,
                message_bubble,
            ),
            # Animated 3-dot typing indicator while processing
            rx.cond(
                GlobalState.is_processing_chat,
                typing_indicator(),
            ),
            width="100%",
            spacing="4",
            padding="24px 32px",
            align="start",
        ),
        flex="1",
        overflow_y="auto",
        width="100%",
        id="chat-container",
        class_name="no-scrollbar",
    )


# ── Voice Components ──────────────────────────────────────────────────────────


def audio_recorder_hidden() -> rx.Component:
    """Hidden input to bridge Web Speech API text → Reflex State."""
    return rx.input(
        id="audio_hidden_id",
        opacity="0",
        width="1px",
        height="1px",
        position="absolute",
        z_index="-1",
        on_change=GlobalState.process_voice_input,
    )


def recording_overlay() -> rx.Component:
    """Cinematic glassmorphic voice recording overlay."""
    return rx.cond(
        GlobalState.is_recording,
        rx.box(
            rx.center(
                rx.vstack(
                    # Multi-layered voice orb
                    rx.box(
                        rx.box(class_name="voice-ripple", style={"animation-delay": "0s"}),
                        rx.box(class_name="voice-ripple", style={"animation-delay": "0.6s"}),
                        rx.box(class_name="voice-ripple", style={"animation-delay": "1.2s"}),
                        rx.center(
                            rx.icon(tag="mic", size=32, color="white"),
                            width="80px",
                            height="80px",
                            border_radius="50%",
                            bg=S.COPPER,
                            box_shadow=f"0 0 30px {S.COPPER}",
                            class_name="orb-glow",
                            position="relative",
                            z_index="10",
                        ),
                        position="relative",
                        width="250px",
                        height="250px",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        margin_bottom="24px",
                    ),
                    rx.text(
                        "OUVINDO",
                        color="white",
                        font_weight="bold",
                        font_size="24px",
                        letter_spacing="0.2em",
                        font_family=S.FONT_DISPLAY,
                    ),
                    rx.text(
                        "Fale agora para analisar seus dados",
                        color="rgba(255,255,255,0.6)",
                        font_size="14px",
                        font_family=S.FONT_BODY,
                    ),
                    rx.button(
                        "PARAR",
                        on_click=lambda: [
                            GlobalState.stop_recording,
                            rx.call_script("if(window.stopRecording) window.stopRecording()"),
                        ],
                        variant="ghost",
                        color=S.COPPER,
                        margin_top="40px",
                        _hover={"bg": "rgba(201, 139, 42, 0.1)"},
                    ),
                    spacing="2",
                    align="center",
                    justify="center",
                ),
                width="100%",
                height="100%",
            ),
            position="fixed",
            inset="0",
            bg="rgba(3, 5, 4, 0.75)",
            backdrop_filter="blur(24px)",
            z_index="9999",
            transition="all 0.4s ease-in-out",
        ),
    )


# ── Page ──────────────────────────────────────────────────────────────────────


def chat_ia_page() -> rx.Component:
    return rx.box(
        recording_overlay(),
        rx.vstack(
            audio_recorder_hidden(),
            rx.box(
                rx.vstack(
                    chat_header(),
                    chat_messages(),
                    chat_input_area(),
                    width="100%",
                    height="100%",
                    spacing="0",
                ),
                class_name="chat-container",
                height="calc(100vh - 4rem)",
                width="100%",
                display="flex",
                flex_direction="column",
            ),
            width="100%",
            spacing="0",
            class_name="animate-enter",
        ),
        width="100%",
        on_mount=[
            GlobalState.load_chat_history,
            GlobalState.ensure_data_loaded,
            rx.call_script(f"""
                if (!window.startRecording) {{
                    var script = document.createElement('script');
                    script.src = '/js/voice_chat.js?v={int(time.time())}';
                    document.head.appendChild(script);
                }} else {{
                    if (window.initVoiceChat) window.initVoiceChat();
                }}
            """),
        ],
    )
