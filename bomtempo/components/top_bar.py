"""
Top Bar — Global fixed header for Bomtempo Dashboard.

Positioned to the right of the sidebar, contains:
  - Left: module title + sub-nav tabs (context-sensitive)
  - Center: global search input
  - Right: notifications, settings, user avatar pill
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.ui_state import UIState


# ─────────────────────────────────────────────────────────────
# Path → display title map
# ─────────────────────────────────────────────────────────────

_PATH_TITLES: dict[str, str] = {
    "/": "Visão Geral",
    "/hub": "Hub de Operações",
    "/hub-operacoes": "Hub de Operações",
    "/financeiro": "Financeiro",
    "/om": "O&M",
    "/analytics": "Analytics",
    "/previsoes": "Previsões",
    "/relatorios": "Relatórios",
    "/chat-ia": "Chat IA",
    "/reembolso": "Reembolso",
    "/reembolso-dash": "Reembolso Dashboard",
    "/rdo-form": "RDO Diário",
    "/rdo-historico": "Meus RDOs",
    "/rdo-dashboard": "RDO Analytics",
    "/alertas": "Alertas",
    "/logs-auditoria": "Logs & Auditoria",
    "/admin/usuarios": "Usuários",
    "/admin/editar_dados": "Editar Dados",
    "/admin/observabilidade": "Observabilidade",
    "/admin/contract-features": "Feature Flags",
    "/perfil": "Meu Perfil",
}

# Tabs for sub-page modules
_HUB_TABS = [
    ("Visão Geral", "visao_geral"),
    ("Dashboard", "dashboard"),
    ("Cronograma", "cronograma"),
    ("Auditoria", "auditoria"),
    ("Timeline", "timeline"),
    ("Financeiro", "financeiro"),
]

_REEMBOLSO_DASH_TABS = [
    ("Visão Geral", "visao_geral"),
    ("E-mails", "emails"),
]


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _tab_item(label: str, value: str, active_var: rx.Var, on_click) -> rx.Component:
    """A single navigation tab button."""
    is_active = active_var == value
    return rx.box(
        rx.text(
            label,
            font_family=S.FONT_MONO,
            font_size="12px",
            font_weight=rx.cond(is_active, "600", "400"),
            color=rx.cond(is_active, S.COPPER, S.TEXT_MUTED),
            white_space="nowrap",
        ),
        on_click=on_click,
        padding_x="12px",
        height="100%",
        display="flex",
        align_items="center",
        border_bottom=rx.cond(
            is_active,
            f"2px solid {S.COPPER}",
            "2px solid transparent",
        ),
        cursor="pointer",
        transition="color 0.15s ease, border-color 0.15s ease",
        _hover={"color": "white"},
    )


def _hub_tabs() -> rx.Component:
    """Sub-nav tabs for /hub — only shown when a project is selected."""
    # uses selected_project (existing var) + hub_tab (newly added var)
    return rx.cond(
        GlobalState.selected_project != "",
        rx.hstack(
            *[
                _tab_item(
                    label,
                    value,
                    GlobalState.hub_tab,
                    GlobalState.set_hub_tab(value),
                )
                for label, value in _HUB_TABS
            ],
            height="100%",
            spacing="0",
            align="center",
        ),
        rx.fragment(),
    )


def _reembolso_dash_tabs() -> rx.Component:
    """Sub-nav tabs for /reembolso-dash — static (no state binding needed)."""
    return rx.hstack(
        *[
            _tab_item(
                label,
                value,
                GlobalState.project_hub_tab,  # reuse existing tab var
                GlobalState.set_project_hub_tab(value),
            )
            for label, value in _REEMBOLSO_DASH_TABS
        ],
        height="100%",
        spacing="0",
        align="center",
    )


def _module_title(title: str) -> rx.Component:
    """Styled uppercase module title text."""
    return rx.text(
        title,
        font_family=S.FONT_TECH,
        font_size="13px",
        font_weight="700",
        letter_spacing="0.08em",
        text_transform="uppercase",
        color="white",
        white_space="nowrap",
    )


def _left_context() -> rx.Component:
    """
    Left section: shows the module title and optional sub-nav tabs.
    Uses rx.State.router.page.path for path detection.
    """
    current = rx.State.router.page.path

    # Build a chain of rx.cond for paths that have sub-tabs, then fall back
    # to a static title derived from the path.  We use a helper to build the
    # title text for every known path via nested rx.cond.

    def _title_for_path(path_var: rx.Var) -> rx.Component:
        """Recursively build nested rx.cond for titles."""
        result = _module_title("Dashboard")  # ultimate fallback
        for path, title in reversed(list(_PATH_TITLES.items())):
            result = rx.cond(
                path_var == path,
                _module_title(title),
                result,
            )
        return result

    # Hub section (title + optional tabs)
    hub_section = rx.hstack(
        _module_title("Hub de Operações"),
        rx.box(
            width="1px",
            height="20px",
            bg=S.BORDER_SUBTLE,
            margin_x="4px",
        ),
        _hub_tabs(),
        height="100%",
        spacing="0",
        align="center",
    )

    # Reembolso-dash section (title + tabs)
    reembolso_dash_section = rx.hstack(
        _module_title("Reembolso Dashboard"),
        rx.box(
            width="1px",
            height="20px",
            bg=S.BORDER_SUBTLE,
            margin_x="4px",
        ),
        _reembolso_dash_tabs(),
        height="100%",
        spacing="0",
        align="center",
    )

    return rx.box(
        rx.cond(
            (current == "/hub") | (current == "/hub-operacoes"),
            hub_section,
            rx.cond(
                current == "/reembolso-dash",
                reembolso_dash_section,
                _title_for_path(current),
            ),
        ),
        height="100%",
        display="flex",
        align_items="center",
        overflow_x="auto",
        overflow_y="hidden",
        class_name="no-scrollbar",
    )


def _search_box() -> rx.Component:
    """Center global search input with an absolutely-positioned search icon."""
    return rx.box(
        rx.icon(
            "search",
            size=13,
            color=S.TEXT_MUTED,
            position="absolute",
            left="8px",
            top="50%",
            transform="translateY(-50%)",
            pointer_events="none",
        ),
        rx.el.input(
            placeholder="BUSCAR NA PLATAFORMA...",
            value=GlobalState.global_search,
            on_change=GlobalState.set_global_search,
            style={
                "background": "transparent",
                "border": "none",
                "border_bottom": f"1px solid rgba(255,255,255,0.1)",
                "color": "white",
                "font_family": S.FONT_TECH,
                "font_size": "13px",
                "letter_spacing": "0.04em",
                "width": "220px",
                "outline": "none",
                "padding": "4px 8px 4px 28px",
                "_focus": {
                    "border_bottom_color": S.COPPER,
                },
                "::placeholder": {
                    "color": S.TEXT_MUTED,
                    "font_size": "11px",
                },
            },
        ),
        position="relative",
        display=["none", "none", "flex"],
        align_items="center",
        flex_shrink="0",
    )


def _labeled_action_button(icon_name: str, label: str, on_click, color: str = S.TEXT_MUTED) -> rx.Component:
    """Ghost icon button with small text label below, for the right action area."""
    return rx.box(
        rx.vstack(
            rx.icon(icon_name, size=18, color=color),
            rx.text(
                label,
                font_family=S.FONT_MONO,
                font_size="9px",
                font_weight="600",
                letter_spacing="0.06em",
                color=color,
                text_transform="uppercase",
                white_space="nowrap",
            ),
            spacing="1",
            align="center",
        ),
        on_click=on_click,
        padding="6px 10px",
        border_radius="6px",
        cursor="pointer",
        transition="all 0.15s ease",
        style={
            "_hover": {
                "background": "rgba(255,255,255,0.05)",
                "& svg": {"color": "white"},
                "& p": {"color": "white"},
            },
        },
    )


def _notif_item(n: dict) -> rx.Component:
    """Single notification row in the popover."""
    is_unread = n["read"] == "0"
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.cond(
                    is_unread,
                    rx.box(width="6px", height="6px", border_radius="50%", bg=S.COPPER, flex_shrink="0", margin_top="3px"),
                    rx.box(width="6px", height="6px", flex_shrink="0"),
                ),
                rx.text(n["message"], font_size="12px", color=rx.cond(is_unread, "white", "rgba(255,255,255,0.55)"), line_height="1.4", flex="1"),
                spacing="2", align="start", width="100%",
            ),
            rx.hstack(
                rx.cond(n["sender"] != "", rx.text("@" + n["sender"], font_size="10px", color=S.COPPER, font_family="var(--font-mono)"), rx.fragment()),
                rx.spacer(),
                rx.text(n["created_at_fmt"], font_size="10px", color="rgba(255,255,255,0.3)", font_family="var(--font-mono)"),
                width="100%",
            ),
            spacing="1", width="100%",
        ),
        padding="8px 10px",
        border_radius="6px",
        bg=rx.cond(is_unread, "rgba(201,139,42,0.07)", "transparent"),
        border=rx.cond(is_unread, "1px solid rgba(201,139,42,0.15)", "1px solid transparent"),
        width="100%",
    )


def _notifications_button() -> rx.Component:
    """Bell icon with unread badge — opens a notifications popover panel."""
    bell_btn = rx.box(
        rx.box(
            rx.hstack(
                rx.icon("bell", size=15, color="rgba(255,255,255,0.7)"),
                rx.text("Notificações", font_size="11px", color="rgba(255,255,255,0.7)", font_family="var(--font-tech)", font_weight="600", letter_spacing="0.04em"),
                spacing="1", align="center",
            ),
            # Unread badge
            rx.cond(
                GlobalState.notif_unread_count > 0,
                rx.box(
                    rx.text(GlobalState.notif_unread_count.to_string(), font_size="8px", font_weight="800", color="white", font_family="var(--font-mono)"),
                    position="absolute",
                    top="-4px",
                    right="-4px",
                    min_width="16px",
                    height="16px",
                    border_radius="8px",
                    bg=S.DANGER,
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    padding_x="3px",
                ),
            ),
            position="relative",
        ),
        padding="6px 10px",
        border_radius="6px",
        cursor="pointer",
        _hover={"background": "rgba(255,255,255,0.06)"},
        transition="background 0.15s ease",
    )

    panel = rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.icon("bell", size=14, color="rgba(201,139,42,1)"),
                rx.text("NOTIFICAÇÕES", font_size="11px", font_weight="700", color="rgba(201,139,42,1)", letter_spacing="0.08em"),
                rx.spacer(),
                rx.cond(
                    GlobalState.notif_unread_count > 0,
                    rx.box(
                        rx.text("Marcar todas lidas", font_size="10px", color=S.TEXT_MUTED, cursor="pointer", _hover={"color": S.COPPER}),
                        on_click=GlobalState.mark_all_notifs_read,
                    ),
                ),
                spacing="2", align="center", width="100%",
            ),
            rx.divider(border_color="rgba(255,255,255,0.06)", margin_y="4px"),
            # Notification list or empty state
            rx.cond(
                GlobalState.notifications_list.length() == 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("inbox", size=13, color="rgba(255,255,255,0.2)"),
                        rx.text("Sem notificações", font_size="12px", color="rgba(255,255,255,0.4)"),
                        spacing="2", align="center",
                    ),
                    rx.text("Mencione @usuario nos registros da Timeline para notificá-lo.", font_size="11px", color="rgba(255,255,255,0.25)", font_style="italic", text_align="center"),
                    spacing="2", align="center", padding="12px",
                ),
                rx.vstack(
                    rx.foreach(GlobalState.notifications_list, _notif_item),
                    spacing="1", width="100%", max_height="320px", overflow_y="auto",
                ),
            ),
            spacing="0", width="100%",
        ),
        padding="14px 16px",
        width="320px",
        bg="rgba(14,26,23,0.98)",
        border="1px solid rgba(255,255,255,0.08)",
        border_radius="10px",
        box_shadow="0 8px 32px rgba(0,0,0,0.4)",
        on_mount=GlobalState.load_notifications,
    )
    return rx.popover.root(
        rx.popover.trigger(bell_btn),
        rx.popover.content(
            panel,
            style={"background": "transparent", "border": "none", "padding": "0", "boxShadow": "none"},
        ),
        side="bottom",
        align="end",
    )


def _settings_button() -> rx.Component:
    """Gear icon — navigates to /admin/usuarios if module is allowed."""
    return rx.cond(
        GlobalState.allowed_modules.contains("gerenciar_usuarios"),
        _labeled_action_button("users", "Usuários", rx.redirect("/admin/usuarios")),
        rx.fragment(),
    )


def _logout_button() -> rx.Component:
    """Logout button with label."""
    return _labeled_action_button("log-out", "Logout", GlobalState.logout, color="#EF4444")


def _user_avatar_pill() -> rx.Component:
    """Clickable user identity pill (avatar + name + role)."""
    icon_avatar = rx.box(
        rx.icon(
            GlobalState.effective_avatar_icon,
            size=14,
            color="white",
        ),
        width="28px",
        height="28px",
        border_radius="6px",
        background=f"linear-gradient(135deg, {S.COPPER}, {S.PATINA})",
        display="flex",
        align_items="center",
        justify_content="center",
        flex_shrink="0",
    )

    initial_avatar = rx.avatar(
        fallback=GlobalState.avatar_fallback,
        size="1",
        style={
            "width": "28px",
            "height": "28px",
            "border_radius": "6px",
            "background": f"linear-gradient(135deg, {S.COPPER}, {S.PATINA})",
            "font_family": S.FONT_TECH,
            "font_weight": "700",
            "font_size": "12px",
        },
    )

    avatar_display = rx.cond(
        GlobalState.current_user_avatar_type == "icon",
        icon_avatar,
        initial_avatar,
    )

    return rx.box(
        rx.hstack(
            avatar_display,
            rx.vstack(
                rx.text(
                    GlobalState.current_user_name,
                    font_family=S.FONT_TECH,
                    font_size="12px",
                    font_weight="600",
                    color="white",
                    white_space="nowrap",
                    line_height="1",
                ),
                rx.text(
                    GlobalState.current_user_role,
                    font_family=S.FONT_BODY,
                    font_size="10px",
                    color=S.TEXT_MUTED,
                    white_space="nowrap",
                    line_height="1",
                ),
                spacing="1",
                align="start",
                display=["none", "none", "flex"],
            ),
            align="center",
            spacing="2",
        ),
        on_click=rx.redirect("/perfil"),
        padding="5px 10px",
        border_radius="8px",
        border=f"1px solid {S.BORDER_SUBTLE}",
        background="rgba(255,255,255,0.03)",
        cursor="pointer",
        transition="all 0.15s ease",
        _hover={
            "background": "rgba(255,255,255,0.06)",
            "border_color": "rgba(201,139,42,0.3)",
        },
        flex_shrink="0",
    )


def _theme_toggle_button() -> rx.Component:
    """Sun/Moon icon — usa rx.toggle_color_mode nativo do Reflex/Radix."""
    return rx.box(
        rx.vstack(
            rx.color_mode_cond(
                # light mode active → show moon (voltar para dark)
                rx.icon("moon", size=18, color=S.TEXT_MUTED),
                # dark mode active → show sun (ir para light)
                rx.icon("sun", size=18, color=S.TEXT_MUTED),
            ),
            rx.color_mode_cond(
                rx.text("Escuro", font_family=S.FONT_MONO, font_size="9px",
                        font_weight="600", letter_spacing="0.06em",
                        color=S.TEXT_MUTED, text_transform="uppercase", white_space="nowrap"),
                rx.text("Claro", font_family=S.FONT_MONO, font_size="9px",
                        font_weight="600", letter_spacing="0.06em",
                        color=S.TEXT_MUTED, text_transform="uppercase", white_space="nowrap"),
            ),
            spacing="1",
            align="center",
        ),
        on_click=rx.toggle_color_mode,
        padding="6px 10px",
        border_radius="6px",
        cursor="pointer",
        transition="all 0.15s ease",
        style={
            "_hover": {
                "background": "rgba(255,255,255,0.05)",
                "& svg": {"color": "white"},
                "& p": {"color": "white"},
            },
        },
    )


def _right_actions() -> rx.Component:
    """Right action cluster: notifications + settings + theme + logout + user pill."""
    return rx.hstack(
        _notifications_button(),
        _settings_button(),
        _theme_toggle_button(),
        _logout_button(),
        rx.box(width="4px", height="32px", bg=S.BORDER_SUBTLE, flex_shrink="0"),
        _user_avatar_pill(),
        spacing="1",
        align="center",
        flex_shrink="0",
    )


# ─────────────────────────────────────────────────────────────
# Public component
# ─────────────────────────────────────────────────────────────

def top_bar() -> rx.Component:
    """
    Fixed global header bar, sitting to the right of the sidebar.

    Layout: [module title / sub-tabs] | [search] | [notifications, settings, avatar]
    """
    return rx.box(
        rx.hstack(
            # Left: context title + optional tabs
            rx.box(
                _left_context(),
                flex="1",
                min_width="0",
                height="100%",
            ),
            # Right: action buttons
            _right_actions(),
            align="center",
            width="100%",
            height="100%",
            padding_x="24px",
            spacing="4",
        ),
        # Fixed positioning — dynamically offset by sidebar width
        position="fixed",
        top="0",
        left=rx.cond(UIState.sidebar_open, "237px", "65px"),
        right="0",
        height="56px",
        background="rgba(14,26,23,0.92)",
        style={
            "backdrop_filter": "blur(20px)",
            "-webkit-backdrop-filter": "blur(20px)",
        },
        border_bottom=f"1px solid rgba(255,255,255,0.06)",
        box_shadow="0 1px 0 rgba(255,255,255,0.02), 0 4px 32px rgba(0,0,0,0.3)",
        z_index="52",
        transition="left 0.25s ease",
        # Desktop only
        display=["none", "none", "flex"],
    )
