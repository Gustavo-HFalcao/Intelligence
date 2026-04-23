import reflex as rx

from bomtempo.components.sidebar import typewriter
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState


# ─────────────────────────────────────────────────────────────
# Left Brand Panel — matches enterprise-preview.html
# (Desktop only — hidden on mobile via display prop)
# ─────────────────────────────────────────────────────────────

def _stat_item(label: str, value: str, color: str) -> rx.Component:
    """Single stat cell in the 2×2 grid."""
    return rx.vstack(
        rx.text(
            label,
            font_size="clamp(8px, 0.7vw, 9px)",
            font_weight="700",
            letter_spacing="0.15em",
            color=S.TEXT_MUTED,
            text_transform="uppercase",
            font_family=S.FONT_MONO,
        ),
        rx.text(
            value,
            font_family=S.FONT_TECH,
            font_size="clamp(1.1rem, 2vw, 1.75rem)",
            font_weight="900",
            color=color,
            line_height="1",
        ),
        spacing="1",
        padding="clamp(10px, 1.2vw, 16px)",
        bg="rgba(255,255,255,0.02)",
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius=S.R_CONTROL,
        align="start",
        width="100%",
    )


def _brand_panel() -> rx.Component:
    """Left decorative brand + stats panel (hidden on mobile)."""
    return rx.box(
        # Grid background (decorative)
        rx.box(
            position="absolute",
            top="0", left="0", right="0", bottom="0",
            opacity="0.04",
            background_image=(
                "linear-gradient(rgba(201,139,42,0.6) 1px, transparent 1px),"
                " linear-gradient(90deg, rgba(201,139,42,0.6) 1px, transparent 1px)"
            ),
            background_size="48px 48px",
            pointer_events="none",
        ),
        # Copper glow orb — top left
        rx.box(
            position="absolute",
            top="-80px", left="-80px",
            width="320px", height="320px",
            border_radius="50%",
            bg="rgba(201, 139, 42, 0.06)",
            filter="blur(80px)",
            pointer_events="none",
        ),
        # Patina glow orb — bottom right
        rx.box(
            position="absolute",
            bottom="-60px", right="-60px",
            width="250px", height="250px",
            border_radius="50%",
            bg="rgba(42, 157, 143, 0.05)",
            filter="blur(70px)",
            pointer_events="none",
        ),
        # Right border accent
        rx.box(
            position="absolute",
            top="0", right="0",
            width="1px", height="100%",
            bg="linear-gradient(180deg, transparent, rgba(201,139,42,0.3) 30%, rgba(201,139,42,0.3) 70%, transparent)",
        ),
        # ── Panel content — vertically centered block ───────────
        rx.vstack(
            # Section label
            rx.hstack(
                rx.box(width="24px", height="1px", bg=S.PATINA),
                rx.text(
                    "PLATAFORMA OPERACIONAL",
                    font_size="9px",
                    font_weight="700",
                    letter_spacing="0.22em",
                    color=S.PATINA,
                    text_transform="uppercase",
                    font_family=S.FONT_MONO,
                ),
                spacing="3",
                align="center",
            ),
            # Brand hero image — width-driven (image is square 640×640)
            rx.image(
                src="/banner.png",
                width="clamp(260px, 45%, 480px)",
                height="auto",
                object_fit="contain",
                opacity="0.95",
                class_name="sidebar-logo-img",
            ),
            # Subtitle
            rx.text(
                "Intelligence Platform v2.0",
                font_size="clamp(0.6rem, 1vw, 0.72rem)",
                letter_spacing="0.18em",
                color=S.TEXT_MUTED,
                font_family=S.FONT_MONO,
            ),
            # Description
            rx.text(
                "Plataforma centralizada de dados operacionais, controle financeiro e analytics preditivo para gestão de obras e contratos de engenharia.",
                font_size="clamp(0.75rem, 1.1vw, 0.85rem)",
                color="rgba(255,255,255,0.45)",
                line_height="1.6",
                width="100%",
            ),
            # Typewriter tagline
            rx.hstack(
                rx.text(
                    "Transformando dados em",
                    font_size="0.8rem",
                    color="rgba(255, 255, 255, 0.3)",
                    font_family=S.FONT_BODY,
                ),
                rx.box(
                    typewriter(
                        options={
                            "strings": [
                                "resultados.",
                                "inovação.",
                                "previsibilidade.",
                                "engenharia pura.",
                                "excelência.",
                            ],
                            "autoStart": True,
                            "loop": True,
                            "delay": 50,
                            "deleteSpeed": 30,
                            "cursor": "|",
                        }
                    ),
                    font_size="0.9rem",
                    font_weight="700",
                    color=S.COPPER,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
            ),
            # Stats grid 2×2
            rx.grid(
                _stat_item("CONTRATOS ATIVOS", "147", S.COPPER),
                _stat_item("RDOS PROCESSADOS", "8.4k", S.PATINA),
                _stat_item("VOLUME GERENCIADO", "R$ 2.1B", S.COPPER),
                _stat_item("UPTIME", "99.97%", S.PATINA),
                columns="2",
                spacing="3",
                width="100%",
            ),
            spacing="5",
            padding=["24px 20px", "28px 24px", "32px 28px", "48px 40px"],
            padding_bottom="60px",
            position="relative",
            z_index="1",
            align="start",
            justify="center",
            height="100%",
            class_name="login-brand-inner",
        ),
        # Bottom status ticker — pinned to bottom
        rx.hstack(
            rx.box(
                width="6px", height="6px",
                border_radius="50%",
                bg=S.PATINA,
                flex_shrink="0",
                class_name="animate-pulse",
            ),
            rx.text(
                "SISTEMAS OPERACIONAIS  ·  INFRAESTRUTURA OK  ·  UTC-3 BRT",
                font_size="10px",
                color=S.TEXT_MUTED,
                font_family=S.FONT_MONO,
                letter_spacing="0.08em",
                opacity="0.55",
            ),
            spacing="2",
            align="center",
            position="absolute",
            bottom="0",
            left="0",
            padding=["16px 20px", "20px 24px", "24px 28px", "24px 40px"],
            z_index="2",
        ),
        position="relative",
        overflow="hidden",
        bg=S.BG_DEPTH,
        width="50%",
        height="100%",
        display=["none", "none", "none", "flex"],
        flex_direction="column",
    )


# ─────────────────────────────────────────────────────────────
# Shared Auth Form — used by both desktop and mobile layouts
# ─────────────────────────────────────────────────────────────

def _auth_form() -> rx.Component:
    """The actual login form: inputs, button, error, footer."""
    return rx.vstack(
        # Username input
        rx.vstack(
            rx.text(
                "USUÁRIO",
                font_size="9px",
                font_weight="700",
                letter_spacing="0.18em",
                color=S.TEXT_MUTED,
                text_transform="uppercase",
                font_family=S.FONT_MONO,
            ),
            rx.input(
                placeholder="Digite seu usuário",
                value=GlobalState.username_input,
                on_change=GlobalState.set_username_input,
                debounce_timeout=300,
                custom_attrs={
                    "autocomplete": "username",
                    "autocorrect": "off",
                    "autocapitalize": "none",
                    "spellcheck": "false",
                },
                bg="#06100e", # surface-container-lowest
                border=f"1px solid {S.BORDER_SUBTLE}",
                color="white",
                width="100%",
                height="48px",
                padding_x="14px",
                border_radius="4px", # Industrial sm
                font_family=S.FONT_MONO,
                font_size="16px",
                transition="border-color 0.15s ease",
                is_disabled=GlobalState.is_authenticating,
                _focus={
                    "border": f"1px solid {S.BORDER_SUBTLE}",
                    "border_bottom": f"2px solid {S.COPPER}",
                    "outline": "none"
                }
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        # Password input
        rx.vstack(
            rx.text(
                "SENHA",
                font_size="9px",
                font_weight="700",
                letter_spacing="0.18em",
                color=S.TEXT_MUTED,
                text_transform="uppercase",
                font_family=S.FONT_MONO,
            ),
            rx.input(
                placeholder="••••••••",
                type="password",
                value=GlobalState.password_input,
                on_change=GlobalState.set_password_input,
                debounce_timeout=300,
                custom_attrs={"autocomplete": "current-password"},
                bg="#06100e", # surface-container-lowest
                border=rx.cond(
                    GlobalState.login_error != "",
                    "1px solid rgba(239, 68, 68, 0.5)",
                    f"1px solid {S.BORDER_SUBTLE}",
                ),
                color="white",
                width="100%",
                height="48px",
                padding_x="14px",
                border_radius="4px", # Industrial sm
                font_family=S.FONT_MONO,
                font_size="16px",
                on_key_down=GlobalState.check_login_on_enter,
                transition="border-color 0.15s ease",
                is_disabled=GlobalState.is_authenticating,
                _focus={
                    "border": f"1px solid {S.BORDER_SUBTLE}",
                    "border_bottom": f"2px solid {S.COPPER}",
                    "outline": "none"
                }
            ),
            rx.hstack(
                rx.spacer(),
                rx.link(
                    "Esqueci minha senha?",
                    on_click=GlobalState.toggle_forgot_password,
                    font_size="10px",
                    color=S.PATINA,
                    opacity="0.7",
                    _hover={"opacity": "1", "text_decoration": "underline"},
                ),
                width="100%",
                margin_top="1"
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        # Forgot Password Modal
        rx.dialog.root(
            rx.dialog.content(
                rx.vstack(
                    rx.dialog.title("Recuperar Acesso", color="white", font_family=S.FONT_TECH),
                    rx.text(
                        "Digite seu email para receber um link de redefinição de senha.",
                        color=S.TEXT_MUTED,
                        font_size="14px",
                    ),
                    rx.input(
                        placeholder="seu@email.com",
                        default_value=GlobalState.forgot_password_email,
                        on_blur=GlobalState.set_forgot_password_email,
                        width="100%",
                        bg="rgba(255,255,255,0.05)",
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        color="white",
                    ),
                    rx.cond(
                        GlobalState.forgot_password_error != "",
                        rx.text(GlobalState.forgot_password_error, color="#F87171", font_size="12px"),
                    ),
                    rx.cond(
                        GlobalState.forgot_password_success,
                        rx.box(
                            rx.text("✅ Link enviado com sucesso! Verifique sua caixa de entrada.", color=S.PATINA, font_size="13px", font_weight="600"),
                            padding="12px",
                            bg="rgba(42,157,143,0.1)",
                            border_radius="8px",
                            width="100%",
                        ),
                        rx.button(
                            "Enviar Link de Redefinição",
                            on_click=GlobalState.send_reset_link,
                            is_loading=GlobalState.is_sending_reset,
                            bg=S.COPPER,
                            color="#0A1F1A",
                            width="100%",
                        ),
                    ),
                    rx.hstack(
                        rx.spacer(),
                        rx.dialog.close(
                            rx.button("Fechar", variant="soft", color_scheme="gray", on_click=GlobalState.toggle_forgot_password)
                        ),
                        width="100%",
                        margin_top="12px",
                    ),
                    spacing="4",
                    align="start",
                ),
                bg=S.BG_SURFACE,
                border=f"1px solid {S.BORDER_SUBTLE}",
                max_width="450px",
            ),
            open=GlobalState.show_forgot_password,
        ),
        # Login button + progress bar
        rx.vstack(
            rx.button(
                rx.hstack(
                    rx.cond(
                        GlobalState.is_authenticating,
                        rx.spinner(size="1", color="inherit"),
                        rx.icon(tag="log-in", size=16),
                    ),
                    rx.text(
                        rx.cond(
                            GlobalState.login_error != "",
                            "TENTAR NOVAMENTE",
                            "ENTRAR",
                        ),
                        font_family=S.FONT_TECH,
                        font_weight="700",
                        font_size="14px",
                        letter_spacing="0.1em",
                    ),
                    spacing="3",
                    align="center",
                    justify="center",
                ),
                on_click=GlobalState.check_login,
                bg=rx.cond(
                    GlobalState.is_authenticating,
                    "rgba(201, 139, 42, 0.15)",
                    f"linear-gradient(135deg, {S.COPPER}, {S.COPPER_LIGHT})",
                ),
                color=rx.cond(GlobalState.is_authenticating, S.COPPER, "#0A1F1A"),
                border=rx.cond(
                    GlobalState.is_authenticating,
                    f"1px solid {S.COPPER}",
                    "1px solid transparent",
                ),
                width="100%",
                height="48px",
                border_radius=S.R_CONTROL,
                cursor=rx.cond(GlobalState.is_authenticating, "not-allowed", "pointer"),
                is_disabled=GlobalState.is_authenticating,
                transition="all 0.2s ease",
                _hover=rx.cond(
                    GlobalState.is_authenticating,
                    {},
                    {"opacity": "0.92", "transform": "translateY(-1px)"},
                ),
            ),
            # Auth progress bar — visible only while authenticating
            rx.cond(
                GlobalState.is_authenticating,
                rx.box(
                    rx.box(class_name="auth-progress-fill"),
                    width="100%",
                    height="2px",
                    bg="rgba(255,255,255,0.05)",
                    border_radius="0",
                    overflow="hidden",
                ),
                rx.box(height="2px"),
            ),
            spacing="0",
            width="100%",
            gap="6px",
        ),
        # Error message
        rx.cond(
            GlobalState.login_error != "",
            rx.hstack(
                rx.icon(tag="circle-alert", size=13, color="#EF4444"),
                rx.text(
                    GlobalState.login_error,
                    color="#EF4444",
                    font_size="12px",
                    font_weight="500",
                    font_family=S.FONT_MONO,
                ),
                spacing="2",
                align="center",
                padding="10px 14px",
                bg="rgba(239, 68, 68, 0.06)",
                border=f"1px solid rgba(239, 68, 68, 0.25)",
                border_radius=S.R_CONTROL,
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )


# ─────────────────────────────────────────────────────────────
# Desktop Right Auth Panel (hidden on mobile)
# ─────────────────────────────────────────────────────────────

def _auth_panel() -> rx.Component:
    """Right side authentication form panel — desktop only."""
    return rx.box(
        rx.center(
            rx.vstack(
                # Mobile-only logo badge (hidden since whole panel is desktop-only)
                rx.box(
                    rx.hstack(
                        rx.box(width="20px", height="1px", bg=S.PATINA),
                        rx.text(
                            "PLATAFORMA OPERACIONAL",
                            font_size="8px",
                            font_weight="700",
                            letter_spacing="0.2em",
                            color=S.PATINA,
                            text_transform="uppercase",
                            font_family=S.FONT_MONO,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    display="none",
                    margin_bottom="32px",
                ),
                # Section label
                rx.text(
                    "ACESSO SEGURO",
                    font_size="9px",
                    font_weight="700",
                    letter_spacing="0.22em",
                    color=S.PATINA,
                    text_transform="uppercase",
                    font_family=S.FONT_MONO,
                ),
                # Title
                rx.text(
                    "Autentique-se",
                    font_family=S.FONT_BODY,
                    font_size="2rem",
                    font_weight="700",
                    color="white",
                    line_height="1.1",
                    margin_top="-4px",
                ),
                # Auth form
                _auth_form(),
                # Footer note
                rx.text(
                    "BOMTEMPO INTELLIGENCE  ·  PLATAFORMA RESTRITA  ·  ACESSO MONITORADO",
                    font_size="9px",
                    color=S.TEXT_MUTED,
                    text_align="center",
                    font_family=S.FONT_MONO,
                    letter_spacing="0.1em",
                    opacity="0.4",
                    margin_top="8px",
                ),
                spacing="5",
                width="100%",
                max_width="460px",
                class_name="glass-reveal",
            ),
            width="100%",
            height="100%",
            padding="48px 40px",
        ),
        flex="1",
        bg=S.BG_ELEVATED,
        height="100%",
        border_left=f"1px solid {S.BORDER_SUBTLE}",
        display="flex",
        align_items="center",
        justify_content="center",
    )


# ─────────────────────────────────────────────────────────────
# Mobile Login — Combined brand + auth (hidden on desktop)
# ─────────────────────────────────────────────────────────────

def _mobile_login() -> rx.Component:
    """Full-screen mobile login — brand elements + auth in one view."""
    return rx.box(
        # ── Background decorations ────────────────────────────────
        # Grid pattern
        rx.box(
            position="absolute",
            top="0", left="0", right="0", bottom="0",
            opacity="0.03",
            background_image=(
                "linear-gradient(rgba(201,139,42,0.6) 1px, transparent 1px),"
                " linear-gradient(90deg, rgba(201,139,42,0.6) 1px, transparent 1px)"
            ),
            background_size="40px 40px",
            pointer_events="none",
        ),
        # Copper glow orb — top
        rx.box(
            position="absolute",
            top="-60px", left="50%",
            transform="translateX(-50%)",
            width="300px", height="300px",
            border_radius="50%",
            bg="rgba(201, 139, 42, 0.08)",
            filter="blur(80px)",
            pointer_events="none",
        ),
        # Patina glow orb — bottom
        rx.box(
            position="absolute",
            bottom="-40px", right="-40px",
            width="200px", height="200px",
            border_radius="50%",
            bg="rgba(42, 157, 143, 0.06)",
            filter="blur(60px)",
            pointer_events="none",
        ),
        # ── Scrollable content ────────────────────────────────────
        rx.vstack(
            # Top safe-area spacer (respects notch)
            rx.box(
                height="env(safe-area-inset-top, 0px)",
                flex_shrink="0",
            ),
            # ── Brand section ─────────────────────────────────────
            # Section label
            rx.hstack(
                rx.box(width="16px", height="1px", bg=S.PATINA),
                rx.text(
                    "PLATAFORMA OPERACIONAL",
                    font_size="8px",
                    font_weight="700",
                    letter_spacing="0.2em",
                    color=S.PATINA,
                    text_transform="uppercase",
                    font_family=S.FONT_MONO,
                ),
                spacing="2",
                align="center",
            ),
            # Banner image
            rx.image(
                src="/banner.png",
                width="clamp(240px, 60vw, 360px)",
                height="auto",
                object_fit="contain",
                opacity="0.95",
                class_name="sidebar-logo-img",
            ),
            # Subtitle
            rx.text(
                "Intelligence Platform v2.0",
                font_size="0.6rem",
                letter_spacing="0.18em",
                color=S.TEXT_MUTED,
                font_family=S.FONT_MONO,
                margin_top="-4px",
            ),
            # Typewriter tagline
            rx.hstack(
                rx.text(
                    "Transformando dados em",
                    font_size="0.75rem",
                    color="rgba(255, 255, 255, 0.3)",
                    font_family=S.FONT_BODY,
                ),
                rx.box(
                    typewriter(
                        options={
                            "strings": [
                                "resultados.",
                                "inovação.",
                                "previsibilidade.",
                                "engenharia pura.",
                                "excelência.",
                            ],
                            "autoStart": True,
                            "loop": True,
                            "delay": 50,
                            "deleteSpeed": 30,
                            "cursor": "|",
                        }
                    ),
                    font_size="0.85rem",
                    font_weight="700",
                    color=S.COPPER,
                    font_family=S.FONT_TECH,
                ),
                spacing="2",
                align="center",
            ),
            # ── Divider ──────────────────────────────────────────
            rx.box(
                width="60px",
                height="1px",
                bg=f"linear-gradient(90deg, transparent, {S.COPPER}, transparent)",
                margin_y="4px",
            ),
            # ── Auth section ──────────────────────────────────────
            rx.text(
                "ACESSO SEGURO",
                font_size="8px",
                font_weight="700",
                letter_spacing="0.22em",
                color=S.PATINA,
                text_transform="uppercase",
                font_family=S.FONT_MONO,
            ),
            rx.text(
                "Autentique-se",
                font_family=S.FONT_BODY,
                font_size="1.5rem",
                font_weight="700",
                color="white",
                line_height="1.1",
                margin_top="-4px",
            ),
            # Auth form
            _auth_form(),
            # ── Mini stats row ────────────────────────────────────
            rx.hstack(
                rx.vstack(
                    rx.text("147", font_family=S.FONT_TECH, font_weight="900", font_size="1rem", color=S.COPPER, line_height="1"),
                    rx.text("CONTRATOS", font_size="7px", font_weight="700", letter_spacing="0.12em", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="0", align="center",
                ),
                rx.box(width="1px", height="24px", bg=S.BORDER_SUBTLE),
                rx.vstack(
                    rx.text("R$ 2.1B", font_family=S.FONT_TECH, font_weight="900", font_size="1rem", color=S.COPPER, line_height="1"),
                    rx.text("VOLUME", font_size="7px", font_weight="700", letter_spacing="0.12em", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="0", align="center",
                ),
                rx.box(width="1px", height="24px", bg=S.BORDER_SUBTLE),
                rx.vstack(
                    rx.text("99.97%", font_family=S.FONT_TECH, font_weight="900", font_size="1rem", color=S.PATINA, line_height="1"),
                    rx.text("UPTIME", font_size="7px", font_weight="700", letter_spacing="0.12em", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                    spacing="0", align="center",
                ),
                spacing="5",
                justify="center",
                width="100%",
                padding_y="8px",
            ),
            # Footer note
            rx.text(
                "BOMTEMPO INTELLIGENCE  ·  PLATAFORMA RESTRITA",
                font_size="8px",
                color=S.TEXT_MUTED,
                text_align="center",
                font_family=S.FONT_MONO,
                letter_spacing="0.1em",
                opacity="0.35",
            ),
            # Bottom safe-area spacer
            rx.box(
                height="env(safe-area-inset-bottom, 0px)",
                flex_shrink="0",
            ),
            # Vstack props
            spacing="4",
            width="100%",
            max_width="400px",
            padding_x="24px",
            padding_y="16px",
            align="center",
            class_name="glass-reveal",
        ),
        # ── Container ─────────────────────────────────────────────
        position="relative",
        width="100%",
        height="100%",
        bg=S.BG_DEPTH,
        overflow_y="auto",
        overflow_x="hidden",
        display=["flex", "flex", "flex", "none"],
        align_items="center",
        justify_content="center",
    )


# ─────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────

def login_page() -> rx.Component:
    """Enterprise login — split-screen desktop, combined mobile."""
    return rx.box(
        # Desktop: split-screen (brand left + auth right)
        rx.flex(
            _brand_panel(),
            _auth_panel(),
            direction="row",
            width="100%",
            height="100vh",
            display=["none", "none", "none", "flex"],
        ),
        # Mobile: combined brand + auth
        _mobile_login(),
        # ── Outer wrapper ─────────────────────────────────────────
        # position:fixed + inset:0 bypasses body safe-area padding
        # so the login fills the entire screen with zero margins.
        position="fixed",
        top="0",
        left="0",
        right="0",
        bottom="0",
        z_index="10",
        bg=S.BG_VOID,
        overflow="hidden",
    )
