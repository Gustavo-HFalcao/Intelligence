"""
Perfil do Usuário — /perfil
Full user profile page with editing capabilities.
"""
import reflex as rx
from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState


# ── helpers ──────────────────────────────────────────────────────────────────

def _label(text: str) -> rx.Component:
    """Small monospace field label."""
    return rx.text(
        text,
        font_family=S.FONT_MONO,
        font_size="10px",
        color=S.TEXT_MUTED,
        text_transform="uppercase",
        letter_spacing="0.08em",
        margin_bottom="4px",
    )


def _input_field(value: rx.Var, on_change=None, read_only: bool = False) -> rx.Component:
    """Styled borderless input — copper underline on focus."""
    props = dict(
        read_only=read_only,
        background="rgba(255,255,255,0.03)",
        border="none",
        border_bottom=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="0",
        color="white",
        font_family=S.FONT_TECH,
        font_size="14px",
        padding="8px 4px",
        width="100%",
        outline="none",
        _focus={
            "border_bottom_color": S.COPPER,
            "background": "rgba(201,139,42,0.04)",
        },
        _placeholder={"color": S.TEXT_MUTED},
        cursor="default" if read_only else "text",
    )
    if on_change and not read_only:
        # Use default_value + on_blur to avoid per-keystroke round-trips
        props["default_value"] = value
        props["on_blur"] = on_change
    else:
        props["value"] = value
    return rx.el.input(**props)


def _glass_card(*children, **kwargs) -> rx.Component:
    """Standard glass card."""
    defaults = dict(
        background=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="12px",
        padding="24px",
    )
    defaults.update(kwargs)
    return rx.box(*children, **defaults)


def _section_header(icon: str, title: str) -> rx.Component:
    return rx.hstack(
        rx.icon(icon, size=15, color=S.COPPER),
        rx.text(
            title,
            font_family=S.FONT_TECH,
            font_size="14px",
            font_weight="700",
            color="white",
            letter_spacing="0.05em",
        ),
        align="center",
        spacing="2",
    )


# ── LEFT COLUMN ──────────────────────────────────────────────────────────────

def _avatar_display() -> rx.Component:
    """Large avatar with hover camera overlay."""
    icon_box = rx.box(
        rx.icon(GlobalState.effective_avatar_icon, size=40, color=S.COPPER),
        width="96px",
        height="96px",
        border_radius="8px",
        background=f"rgba(201,139,42,0.15)",
        border=f"2px solid {S.COPPER}",
        display="flex",
        align_items="center",
        justify_content="center",
    )
    initials_box = rx.box(
        rx.avatar(
            fallback=GlobalState.avatar_fallback,
            size="6",
            radius="none",
            style={"border_radius": "8px"},
        ),
        width="96px",
        height="96px",
        border_radius="8px",
        border=f"2px solid {S.COPPER}",
        overflow="hidden",
    )
    avatar_inner = rx.cond(
        GlobalState.current_user_avatar_type == "icon",
        icon_box,
        initials_box,
    )
    return rx.box(
        avatar_inner,
        rx.box(
            rx.icon("camera", size=16, color="white"),
            position="absolute",
            bottom="0",
            right="0",
            background="rgba(0,0,0,0.7)",
            border_radius="6px 0 8px 0",
            padding="4px 6px",
            opacity="0",
            _group_hover={"opacity": "1"},
            transition="opacity 0.2s",
            cursor="pointer",
        ),
        position="relative",
        display="inline-block",
        class_name="group",
        cursor="pointer",
        on_click=GlobalState.open_avatar_modal,
    )


def _stat_item(label: str, value: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(
            label,
            font_family=S.FONT_MONO,
            font_size="9px",
            color=S.TEXT_MUTED,
            text_transform="uppercase",
            letter_spacing="0.08em",
        ),
        rx.text(
            value,
            font_family=S.FONT_TECH,
            font_size="14px",
            font_weight="700",
            color="white",
        ),
        spacing="1",
        align="center",
    )


def _identity_card() -> rx.Component:
    return _glass_card(
        # VERIFICADO badge
        rx.box(
            rx.hstack(
                rx.icon("shield-check", size=10, color=S.COPPER),
                rx.text(
                    "VERIFICADO / IDENTIDADE",
                    font_family=S.FONT_MONO,
                    font_size="9px",
                    color=S.COPPER,
                    letter_spacing="0.1em",
                ),
                spacing="1",
                align="center",
            ),
            background=f"rgba(201,139,42,0.1)",
            border=f"1px solid rgba(201,139,42,0.3)",
            border_radius="20px",
            padding="3px 10px",
            display="inline-flex",
            margin_bottom="20px",
        ),
        # Avatar centered
        rx.vstack(
            _avatar_display(),
            # Name
            rx.text(
                GlobalState.current_user_name,
                font_family=S.FONT_TECH,
                font_size="1.15rem",
                font_weight="700",
                color="white",
                text_transform="uppercase",
                letter_spacing="0.05em",
                text_align="center",
            ),
            # Role
            rx.text(
                GlobalState.current_user_role,
                font_family=S.FONT_MONO,
                font_size="12px",
                color=S.COPPER,
                text_align="center",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        # Divider
        rx.divider(color=S.BORDER_SUBTLE, margin_y="16px"),
        # Stats row
        rx.hstack(
            _stat_item("Nível de Acesso", GlobalState.current_user_role),
            rx.divider(orientation="vertical", height="32px", color=S.BORDER_SUBTLE),
            _stat_item("Projetos Ativos", GlobalState.total_contratos.to_string()),
            justify="center",
            spacing="6",
            width="100%",
        ),
        padding="24px",
        width="100%",
    )


def _mobile_card() -> rx.Component:
    return _glass_card(
        rx.hstack(
            # Phone icon box
            rx.box(
                rx.icon("smartphone", size=20, color=S.PATINA),
                width="44px",
                height="44px",
                background=f"rgba(42,157,143,0.12)",
                border=f"1px solid rgba(42,157,143,0.25)",
                border_radius="8px",
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink="0",
            ),
            rx.vstack(
                rx.text(
                    "APP MOBILE",
                    font_family=S.FONT_TECH,
                    font_size="13px",
                    font_weight="700",
                    color=S.COPPER,
                    letter_spacing="0.08em",
                ),
                rx.text(
                    "Leve a inteligência Bomtempo para o canteiro de obras. Acesse o app mobile para RDO, fotos e relatórios em campo.",
                    font_family=S.FONT_BODY,
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    line_height="1.5",
                ),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        # CTA button
        rx.box(
            rx.hstack(
                rx.icon("smartphone", size=14, color=S.PATINA),
                rx.text(
                    "ABRIR APP MOBILE",
                    font_family=S.FONT_MONO,
                    font_size="11px",
                    font_weight="700",
                    letter_spacing="0.06em",
                    color=S.PATINA,
                ),
                spacing="2",
                align="center",
            ),
            on_click=rx.redirect("/app-mobile"),
            margin_top="14px",
            padding="8px 16px",
            border_radius="6px",
            border=f"1px solid rgba(42,157,143,0.35)",
            background=f"rgba(42,157,143,0.08)",
            cursor="pointer",
            display="inline-flex",
            align_items="center",
            transition="all 0.15s ease",
            _hover={
                "background": "rgba(42,157,143,0.18)",
                "border_color": S.PATINA,
            },
        ),
        padding="16px",
        margin_top="12px",
        width="100%",
    )


def _left_column() -> rx.Component:
    return rx.vstack(
        _identity_card(),
        _mobile_card(),
        spacing="0",
        min_width="260px",
        max_width="300px",
        width="100%",
    )


# ── RIGHT COLUMN ─────────────────────────────────────────────────────────────

def _dados_pessoais_card() -> rx.Component:
    return _glass_card(
        # Header
        rx.hstack(
            _section_header("user", "DADOS PESSOAIS"),
            rx.spacer(),
            rx.button(
                rx.icon("pencil", size=13),
                rx.text("EDITAR MODO", font_family=S.FONT_MONO, font_size="10px"),
                size="1",
                variant="ghost",
                color=S.TEXT_MUTED,
                _hover={"color": S.COPPER},
                spacing="1",
            ),
            align="center",
            width="100%",
        ),
        rx.divider(color=S.BORDER_SUBTLE, margin_y="16px"),
        # 2-column grid
        rx.grid(
            # NOME COMPLETO
            rx.vstack(
                _label("Nome Completo"),
                _input_field(GlobalState.current_user_name, read_only=True),
                spacing="0",
                align="start",
                width="100%",
            ),
            # E-MAIL CORPORATIVO
            rx.vstack(
                _label("E-mail Corporativo"),
                _input_field(
                    GlobalState.contact_edit_email,
                    on_change=GlobalState.set_contact_edit_email,
                    read_only=False,
                ),
                spacing="0",
                align="start",
                width="100%",
            ),
            # EMPRESA / UNIDADE
            rx.vstack(
                _label("Empresa / Unidade"),
                rx.el.input(
                    value="Bomtempo Engenharia",
                    read_only=True,
                    background="rgba(255,255,255,0.03)",
                    border="none",
                    border_bottom=f"1px solid {S.BORDER_SUBTLE}",
                    border_radius="0",
                    color="white",
                    font_family=S.FONT_TECH,
                    font_size="14px",
                    padding="8px 4px",
                    width="100%",
                    outline="none",
                    cursor="default",
                ),
                spacing="0",
                align="start",
                width="100%",
            ),
            # CARGO ATUAL
            rx.vstack(
                _label("Cargo Atual"),
                _input_field(GlobalState.current_user_role, read_only=True),
                spacing="0",
                align="start",
                width="100%",
            ),
            columns="2",
            gap="16px",
            width="100%",
        ),
        # Error / success feedback
        rx.cond(
            GlobalState.contact_error != "",
            rx.text(
                GlobalState.contact_error,
                color=S.DANGER,
                font_family=S.FONT_MONO,
                font_size="11px",
                margin_top="8px",
            ),
        ),
        rx.cond(
            GlobalState.contact_success,
            rx.text(
                "✓ Alterações salvas com sucesso.",
                color=S.PATINA,
                font_family=S.FONT_MONO,
                font_size="11px",
                margin_top="8px",
            ),
        ),
        # Save button
        rx.hstack(
            rx.spacer(),
            rx.button(
                rx.icon("save", size=14),
                rx.text("SALVAR ALTERAÇÕES", font_family=S.FONT_MONO, font_size="11px"),
                on_click=GlobalState.save_contact,
                background=f"rgba(201,139,42,0.15)",
                border=f"1px solid rgba(201,139,42,0.4)",
                color=S.COPPER,
                border_radius="6px",
                padding="8px 16px",
                _hover={
                    "background": f"rgba(201,139,42,0.25)",
                    "border_color": S.COPPER,
                },
                cursor="pointer",
                spacing="2",
            ),
            margin_top="20px",
            width="100%",
        ),
        padding="28px",
        width="100%",
    )


def _seguranca_card() -> rx.Component:
    return _glass_card(
        _section_header("lock", "SEGURANÇA"),
        rx.divider(color=S.BORDER_SUBTLE, margin_y="16px"),
        # Password row
        rx.hstack(
            rx.vstack(
                rx.text(
                    "SENHA DE ACESSO",
                    font_family=S.FONT_MONO,
                    font_size="12px",
                    font_weight="600",
                    color="white",
                ),
                rx.text(
                    "Atualizada há 2 meses",
                    font_family=S.FONT_BODY,
                    font_size="11px",
                    color=S.TEXT_MUTED,
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.button(
                "ALTERAR",
                on_click=GlobalState.open_avatar_modal,
                variant="outline",
                font_family=S.FONT_MONO,
                font_size="11px",
                color=S.COPPER,
                border_color=f"rgba(201,139,42,0.4)",
                background="transparent",
                border_radius="6px",
                _hover={"border_color": S.COPPER, "background": "rgba(201,139,42,0.1)"},
                cursor="pointer",
            ),
            align="center",
            width="100%",
        ),
        rx.divider(color=S.BORDER_SUBTLE, margin_y="14px"),
        # 2FA row
        rx.hstack(
            rx.vstack(
                rx.text(
                    "AUTENTICAÇÃO 2FA",
                    font_family=S.FONT_MONO,
                    font_size="12px",
                    font_weight="600",
                    color="white",
                ),
                rx.box(
                    rx.text(
                        "ATIVADO / SMS-AUTH",
                        font_family=S.FONT_MONO,
                        font_size="10px",
                        color=S.PATINA,
                    ),
                    background=f"rgba(42,157,143,0.1)",
                    border=f"1px solid rgba(42,157,143,0.3)",
                    border_radius="20px",
                    padding="2px 10px",
                    display="inline-block",
                ),
                spacing="2",
                align="start",
            ),
            rx.spacer(),
            rx.switch(
                checked=True,
                color_scheme="teal",
                cursor="pointer",
            ),
            align="center",
            width="100%",
        ),
        padding="28px",
        margin_top="16px",
        width="100%",
    )


def _notificacoes_card() -> rx.Component:
    check_items = [
        ("Alertas via Push Mobile", True),
        ("Relatórios diários por E-mail", True),
        ("Alertas críticos via SMS", False),
        ("Atualizações da Plataforma", True),
    ]

    def _check_row(label: str, default_checked: bool) -> rx.Component:
        return rx.hstack(
            rx.checkbox(
                label,
                default_checked=default_checked,
                color_scheme="amber",
                font_family=S.FONT_BODY,
                font_size="13px",
                color="white",
                cursor="pointer",
            ),
            width="100%",
            padding_y="6px",
        )

    return _glass_card(
        _section_header("bell", "NOTIFICAÇÕES"),
        rx.divider(color=S.BORDER_SUBTLE, margin_y="16px"),
        rx.vstack(
            *[_check_row(lbl, chk) for lbl, chk in check_items],
            spacing="1",
            width="100%",
        ),
        padding="28px",
        margin_top="16px",
        width="100%",
    )


def _zona_risco_card() -> rx.Component:
    return _glass_card(
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.icon("triangle-alert", size=14, color=S.DANGER),
                    rx.text(
                        "ZONA DE RISCO",
                        font_family=S.FONT_TECH,
                        font_size="13px",
                        font_weight="700",
                        color=S.DANGER,
                        letter_spacing="0.06em",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.text(
                    "O encerramento da sessão ou exclusão de conta são permanentes.",
                    font_family=S.FONT_BODY,
                    font_size="12px",
                    color=S.TEXT_MUTED,
                ),
                spacing="2",
                align="start",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("log-out", size=13),
                rx.text("LOGOUT_SESSION", font_family=S.FONT_MONO, font_size="12px"),
                on_click=GlobalState.logout,
                background="rgba(239,68,68,0.1)",
                border="1px solid rgba(239,68,68,0.3)",
                color=S.DANGER,
                border_radius="6px",
                padding="8px 16px",
                _hover={
                    "background": "rgba(239,68,68,0.2)",
                    "border_color": S.DANGER,
                },
                cursor="pointer",
                spacing="2",
                flex_shrink="0",
            ),
            align="center",
            width="100%",
            spacing="4",
        ),
        padding="20px 24px",
        margin_top="16px",
        border_left=f"3px solid {S.DANGER}",
        width="100%",
    )


def _right_column() -> rx.Component:
    return rx.vstack(
        _dados_pessoais_card(),
        _seguranca_card(),
        _notificacoes_card(),
        _zona_risco_card(),
        spacing="0",
        flex="1",
        min_width="0",
        width="100%",
    )


# ── PAGE ROOT ─────────────────────────────────────────────────────────────────

def perfil_page() -> rx.Component:
    """Full user profile page — /perfil."""
    return rx.vstack(
        # ── Page Header ──────────────────────────────────────────────────────
        rx.vstack(
            rx.text(
                "PERFIL DO USUÁRIO",
                font_family=S.FONT_TECH,
                font_size="2rem",
                font_weight="700",
                color=S.COPPER,
                text_transform="uppercase",
                letter_spacing="0.08em",
            ),
            rx.hstack(
                rx.text(
                    "UID: ",
                    font_family=S.FONT_MONO,
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    letter_spacing="0.05em",
                ),
                rx.text(
                    GlobalState.current_user_contrato,
                    font_family=S.FONT_MONO,
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    letter_spacing="0.05em",
                ),
                rx.text(
                    " / LAST_LOGIN: Sessão atual",
                    font_family=S.FONT_MONO,
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    letter_spacing="0.05em",
                ),
                spacing="0",
                align="center",
                wrap="wrap",
            ),
            spacing="1",
            align="start",
            width="100%",
        ),
        # ── Two-column layout ─────────────────────────────────────────────
        rx.flex(
            _left_column(),
            _right_column(),
            direction=rx.breakpoints(initial="column", md="row"),
            gap="24px",
            margin_top="28px",
            width="100%",
            align="start",
        ),
        max_width="1200px",
        margin="0 auto",
        width="100%",
        spacing="0",
        padding_bottom="40px",
        padding_x="4px",
        align="start",
    )
