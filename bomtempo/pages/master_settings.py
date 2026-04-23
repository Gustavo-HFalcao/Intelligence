"""Master Settings — configurações globais da plataforma."""
import reflex as rx
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState


def _settings_card(icon: str, title: str, value, subtitle: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag=icon, size=14, color=S.COPPER),
                rx.text(
                    title,
                    font_size="10px",
                    font_weight="700",
                    color=S.TEXT_MUTED,
                    letter_spacing="0.1em",
                    text_transform="uppercase",
                ),
                spacing="2",
            ),
            rx.text(value, font_size="18px", font_weight="800", color="white"),
            rx.text(subtitle, font_size="12px", color=S.TEXT_MUTED),
            spacing="2",
            align="start",
        ),
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius=S.R_CONTROL,
        padding="20px",
        flex="1",
        min_width="200px",
    )


def master_settings_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="settings", size=20, color=S.COPPER),
                rx.text(
                    "CONFIGURAÇÕES DA PLATAFORMA",
                    font_size="20px",
                    font_weight="800",
                    color="white",
                    letter_spacing="0.1em",
                    font_family=S.FONT_TECH,
                ),
                spacing="3",
                align="center",
            ),
            rx.text(
                "Configurações globais do BTP Intelligence — em desenvolvimento.",
                font_size="13px",
                color=S.TEXT_MUTED,
            ),
            rx.separator(width="100%", color_scheme="amber", opacity="0.2"),

            rx.hstack(
                _settings_card(
                    "user-check",
                    "SESSÃO MASTER",
                    GlobalState.current_user_name,
                    "BTP MASTER",
                ),
                _settings_card(
                    "server",
                    "AMBIENTE",
                    "PRODUÇÃO",
                    "Supabase + Reflex",
                ),
                spacing="4",
                width="100%",
                wrap="wrap",
            ),
            spacing="5",
            width="100%",
            align="start",
        ),
        padding="32px",
        width="100%",
        min_height="100vh",
    )
