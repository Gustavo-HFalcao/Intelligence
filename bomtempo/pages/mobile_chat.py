import time

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.pages.chat_ia import (
    audio_recorder_hidden,
    chat_messages,
    recording_overlay,
)
from bomtempo.state.global_state import GlobalState


def mobile_header() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.icon(tag="sparkles", size=24, color="#C98B2A"),
            rx.vstack(
                rx.text(
                    "PLATAFORMA DE INTELIGÊNCIA OPERACIONAL",
                    font_weight="900",
                    color="white",
                    font_size="13px",
                    line_height="1",
                ),
                rx.text(
                    "MOBILE",
                    font_size="10px",
                    color="#C98B2A",
                    font_weight="bold",
                    letter_spacing="1px",
                ),
                spacing="0",
            ),
            align="center",
            spacing="3",
        ),
        rx.button(
            rx.icon(tag="log-out", size=20, color="#A0A0A0"),
            variant="ghost",
            on_click=GlobalState.logout,
            padding="8px",
        ),
        justify="between",
        align="center",
        width="100%",
        padding="16px",
        padding_top="24px",  # Safe area top
        bg="#0B1E19",
        border_bottom="1px solid rgba(255,255,255,0.1)",
        z_index="100",
    )


def mobile_chat_input() -> rx.Component:
    """Mobile-optimized input area with larger touch targets"""
    return rx.box(
        rx.vstack(
            # Suggestion Chips (Horizontal Scroll)
            rx.hstack(
                *[
                    rx.badge(
                        question,
                        variant="outline",
                        color_scheme="green",
                        cursor="pointer",
                        on_click=lambda _e, q=question: GlobalState.set_current_question(q),
                        padding="10px 16px",  # Larger touch target
                        border_radius="20px",
                        font_size="12px",
                        white_space="nowrap",
                        bg="rgba(11, 30, 25, 0.8)",
                    )
                    for question in ["Resumo Obras", "Status Financeiro", "Riscos", "Cronograma"]
                ],
                spacing="2",
                overflow_x="auto",
                width="100%",
                padding_bottom="12px",
                class_name="no-scrollbar",
            ),
            # Input Row
            rx.hstack(
                rx.input(
                    id="chat_main_input",  # Direct target for Voice JS
                    value=GlobalState.current_question,
                    on_change=GlobalState.set_current_question,
                    on_key_down=lambda key: rx.cond(
                        key == "Enter", GlobalState.send_message(), None
                    ),
                    placeholder="Digite ou fale...",
                    height="56px",  # Taller for mobile
                    bg="#1A3A30",
                    border="none",
                    color="white",
                    border_radius="28px",
                    padding_left="20px",
                    font_size="16px",  # Prevent zoom on focus ios
                    flex="1",
                    _focus={"outline": "none", "boxShadow": f"0 0 0 2px {S.COPPER}"},
                ),
                # Mic Button - Prominent
                rx.button(
                    rx.icon(tag="mic", size=24),
                    # On Safari, the click listener in voice_chat.js handles the start.
                    id="mobile_mic_btn",
                    on_click=lambda: [
                        GlobalState.start_recording,
                        rx.call_script("window.startRecording()"),
                    ],
                    width="56px",
                    height="56px",
                    border_radius="50%",
                    bg=rx.cond(
                        GlobalState.is_talking_mode, S.COPPER, S.BG_SURFACE
                    ),  # Visual feedback
                    border=f"1px solid {S.COPPER}",
                    color=rx.cond(GlobalState.is_talking_mode, "white", S.COPPER),
                    _active={"bg": S.COPPER, "color": "white", "transform": "scale(0.95)"},
                ),
                # Hidden Toggle (Removed per user request)
                # rx.button(...)
                # Send Button
                rx.cond(
                    GlobalState.current_question.strip() != "",
                    rx.button(
                        rx.icon(tag="send", size=24),
                        on_click=GlobalState.send_message,
                        width="56px",
                        height="56px",
                        border_radius="50%",
                        bg=S.COPPER,
                        color="white",
                        box_shadow="0 0 10px rgba(0,0,0,0.5)",
                    ),
                ),
                align="center",
                width="100%",
                spacing="3",
            ),
            width="100%",
            spacing="0",
        ),
        position="fixed",
        bottom="0",
        left="0",
        width="100%",
        padding="16px",
        padding_bottom="24px",  # Safe area bottom
        bg="linear-gradient(to top, #0A1F1A 80%, transparent)",
        z_index="90",
    )


def hands_free_overlay() -> rx.Component:
    """Overlay para modo conversa (hands-free) com UI Fluida 'JARVIS'"""

    # Determinar estado visual
    # Prioridade: Falando > Processando > Ouvindo > Idle

    current_color = rx.cond(
        GlobalState.is_speaking,
        "#10B981",  # Emerald (Speaking)
        rx.cond(
            GlobalState.is_processing_chat,
            "#A855F7",  # Purple (Thinking)
            rx.cond(
                GlobalState.is_recording_voice,
                "#EF4444",  # Red (Listening)
                "#3B82F6",  # Blue (Idle)
            ),
        ),
    )

    current_icon = rx.cond(
        GlobalState.is_speaking,
        "volume-2",
        rx.cond(GlobalState.is_processing_chat, "sparkles", "mic"),
    )

    status_text = rx.cond(
        GlobalState.is_speaking,
        "Falando...",
        rx.cond(
            GlobalState.is_processing_chat,
            "Pensando...",
            rx.cond(GlobalState.is_recording_voice, "Ouvindo...", "Toque para Falar"),
        ),
    )

    return rx.cond(
        GlobalState.is_talking_mode,
        rx.box(
            # Overlay fundo escuro
            rx.box(
                position="absolute",
                top="0",
                left="0",
                right="0",
                bottom="0",
                bg="rgba(0,0,0,0.9)",
                z_index="1000",
            ),
            # Conteúdo Centralizado
            rx.vstack(
                # Audio components moved to root to ensure persistence
                # 1. Indicador Visual Pulsante
                rx.box(
                    rx.icon(
                        tag=current_icon,
                        size=60,
                        color="white",
                    ),
                    bg=current_color,
                    width="120px",
                    height="120px",
                    border_radius="50%",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    box_shadow=f"0 0 40px {current_color}",
                    class_name="pulse-ring",  # Animation defined in mobile_chat_page style
                    on_click=[
                        rx.call_script("if(window.unlockAudio) window.unlockAudio()"),
                        GlobalState.toggle_voice_recording,
                    ],
                    _hover={"cursor": "pointer", "transform": "scale(1.05)"},
                    transition="all 0.3s ease",
                ),
                # 2. Status Text
                rx.text(
                    status_text,
                    color="white",
                    font_size="24px",
                    font_weight="bold",
                    margin_top="32px",
                    opacity="0.9",
                ),
                # 3. Legenda (Subtitles)
                rx.cond(
                    GlobalState.last_spoken_response != "",
                    rx.box(
                        rx.text(
                            GlobalState.last_spoken_response,
                            color="#E5E7EB",
                            font_size="16px",
                            text_align="center",
                            line_height="1.5",
                        ),
                        bg="rgba(255,255,255,0.05)",
                        padding="20px",
                        border_radius="16px",
                        max_width="90%",
                        max_height="30vh",
                        overflow_y="auto",
                        margin_top="24px",
                        border="1px solid rgba(255,255,255,0.1)",
                    ),
                ),
                # 4. Botão Fechar Discreto
                rx.button(
                    rx.icon("x", size=24),
                    on_click=GlobalState.disable_talking_mode,
                    variant="ghost",
                    color="white",
                    position="absolute",
                    top="20px",
                    right="20px",
                    padding="12px",
                    border_radius="50%",
                    bg="rgba(255,255,255,0.1)",
                ),
                justify="center",
                align="center",
                height="100vh",
                width="100%",
                position="relative",
                z_index="1001",
            ),
            position="fixed",
            top="0",
            left="0",
            right="0",
            bottom="0",
            z_index="999",
        ),
    )


def mobile_chat_page() -> rx.Component:
    return rx.box(
        # CSS Animations
        rx.html("""
        <style>
            @keyframes pulse-ring {
                0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); }
                70% { transform: scale(1); box-shadow: 0 0 0 20px rgba(255, 255, 255, 0); }
                100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
            }
            .pulse-ring {
                animation: pulse-ring 2s infinite;
            }
        </style>
        """),
        # Force script loading
        # rx.script(src=f"/assets/js/voice_autoplay.js?v={int(time.time()) + 5}"), # Removed to fix SyntaxError
        rx.script(src=f"/js/voice_chat.js?v={int(time.time()) + 5}"),
        # Audio Recorder Component (Hidden)
        audio_recorder_hidden(),
        # Hidden Input for JSON response from Voice API
        rx.input(
            id="voice_api_response_hidden",
            on_change=GlobalState.inject_conversation_json,
            display="none",
        ),
        # Dedicated Audio Player (Root Level Persistence)
        rx.box(
            rx.audio(
                id="reflex-audio-player",  # UPDATED ID as per guide
                url=GlobalState.latest_audio_src,
                controls=True,
                auto_play=False,
                on_play=lambda: GlobalState.set_is_speaking(True),
                on_ended=GlobalState.audio_ended,
                on_error=GlobalState.audio_error,
                width="1px",
                height="1px",
                opacity="0.01",
            ),
            overflow="hidden",
            width="1px",
            height="1px",
            position="absolute",
            top="-10px",
        ),
        # Hidden Trigger for JS Loop (Fallback)
        rx.button(
            id="hidden_loop_trigger",
            on_click=GlobalState.audio_ended,
            display="none",
        ),
        # Overlays
        recording_overlay(),
        # hands_free_overlay(), # Removed per user request
        rx.vstack(
            mobile_header(),
            # Chat Area
            rx.box(
                chat_messages(),
                width="100%",
                flex="1",
                padding_bottom="140px",
                overflow_y="auto",
                bg="#0A1F1A",
            ),
            mobile_chat_input(),
            height="100vh",
            width="100%",
            bg="#0A1F1A",
            spacing="0",
        ),
        # Security check + Init JS
        on_mount=[
            GlobalState.check_mobile_access,
            GlobalState.ensure_data_loaded,
            rx.call_script("""
                if (!window.startRecording) {
                    var script = document.createElement('script');
                    script.src = '/js/voice_chat.js?v=' + new Date().getTime();
                    document.head.appendChild(script);
                } else {
                    if (window.initVoiceChat) window.initVoiceChat();
                }
            """),
        ],
    )
