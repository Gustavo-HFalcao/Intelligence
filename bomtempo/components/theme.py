"""
Design Token Reference — BOMTEMPO Enterprise UX System
Maps Upgrade_UX_UI.md tokens to the existing Deep Tectonic palette.
Import this instead of core/styles.py where you need structured token access.
"""

from bomtempo.core import styles as S


# ── Colors ────────────────────────────────────────────────────────────────────
class Colors:
    primary = S.COPPER  # #C98B2A  — brand copper
    primary_hover = S.COPPER_LIGHT  # #E0A63B
    primary_glow = S.COPPER_GLOW  # rgba(201,139,42,0.15)

    secondary = S.PATINA  # #2A9D8F
    secondary_glow = S.PATINA_GLOW

    background_main = S.BG_VOID  # #030504  — page background
    background_card = S.BG_ELEVATED  # #142420  — card/panel
    background_soft = S.BG_SURFACE  # #0e1a17
    background_glass = S.BG_GLASS  # rgba(14,26,23,0.7)
    background_input = S.BG_INPUT  # rgba(255,255,255,0.03)

    border_subtle = S.BORDER_SUBTLE  # rgba(255,255,255,0.08)
    border_accent = S.BORDER_ACCENT  # rgba(201,139,42,0.3)
    border_highlight = S.BORDER_HIGHLIGHT

    text_primary = S.TEXT_PRIMARY  # #E0E0E0
    text_secondary = S.TEXT_SECONDARY  # #889999
    text_muted = S.TEXT_MUTED
    text_white = S.TEXT_WHITE

    success = S.SUCCESS  # #2A9D8F
    success_bg = S.SUCCESS_BG
    warning = S.WARNING  # #F59E0B
    warning_bg = S.WARNING_BG
    danger = S.DANGER  # #EF4444
    danger_bg = S.DANGER_BG
    info = S.INFO  # #3B82F6
    info_bg = S.INFO_BG


# ── Radius ────────────────────────────────────────────────────────────────────
class Radius:
    sm = "8px"
    md = "14px"
    lg = "20px"
    xl = "24px"
    full = "9999px"


# ── Spacing ───────────────────────────────────────────────────────────────────
class Spacing:
    xs = "4px"
    sm = "8px"
    md = "12px"
    lg = "16px"
    xl = "24px"
    xxl = "32px"
    xxxl = "48px"


# ── Typography ────────────────────────────────────────────────────────────────
class Typography:
    family_display = S.FONT_DISPLAY  # Rajdhani
    family_body = S.FONT_BODY  # Outfit
    family_mono = S.FONT_MONO  # JetBrains Mono

    # Sizes
    h1 = "28px"
    h2 = "22px"
    h3 = "18px"
    body = "15px"
    caption = "13px"
    small = "11px"

    # Weights
    regular = "400"
    medium = "500"
    semibold = "600"
    bold = "700"
    black = "900"


# ── Shadows ───────────────────────────────────────────────────────────────────
class Shadows:
    card = "0 4px 30px rgba(0, 0, 0, 0.3)"
    card_hover = "0 16px 48px rgba(0, 0, 0, 0.5), 0 0 1px rgba(201, 139, 42, 0.3)"
    glow_copper = f"0 0 20px {S.COPPER_GLOW}"
    glow_patina = f"0 0 20px {S.PATINA_GLOW}"
    dialog = "0 25px 50px -12px rgba(0, 0, 0, 0.5)"


# ── Breakpoints ───────────────────────────────────────────────────────────────
class Breakpoints:
    sm = "640px"
    md = "768px"
    lg = "1024px"
    xl = "1280px"
    xxl = "1600px"


# ── Transitions ───────────────────────────────────────────────────────────────
class Transitions:
    fast = "all 0.12s ease"
    normal = "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)"
    slow = "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)"


# ── Pre-built Style Dicts ─────────────────────────────────────────────────────
# These can be spread directly into Reflex component props via **T.CARD_STYLE

CARD_STYLE = {
    "background": Colors.background_glass,
    "backdrop_filter": "blur(12px)",
    "border": f"1px solid {Colors.border_subtle}",
    "border_radius": Radius.xl,
    "padding": Spacing.xxl,
    "box_shadow": Shadows.card,
    "transition": Transitions.slow,
    "_hover": {
        "border_color": Colors.border_highlight,
        "transform": "translateY(-2px)",
        "box_shadow": Shadows.card_hover,
    },
}

SECTION_TITLE_STYLE = {
    "font_family": Typography.family_display,
    "font_size": Typography.h2,
    "font_weight": Typography.bold,
    "color": Colors.text_primary,
    "margin_bottom": Spacing.lg,
    "text_transform": "uppercase",
    "letter_spacing": "0.02em",
}

SECTION_CAPTION_STYLE = {
    "font_size": Typography.caption,
    "color": Colors.text_muted,
    "text_transform": "uppercase",
    "letter_spacing": "0.15em",
    "font_weight": Typography.bold,
}

INPUT_STYLE = {
    "bg": Colors.background_input,
    "border": f"1px solid {Colors.border_subtle}",
    "border_radius": Radius.sm,
    "height": "48px",
    "font_size": Typography.body,
    "color": Colors.text_primary,
    "padding_x": Spacing.lg,
    "_focus": {
        "border_color": Colors.primary,
        "box_shadow": f"0 0 0 3px {Colors.primary_glow}",
        "outline": "none",
    },
    "_placeholder": {"color": Colors.text_muted},
}

BUTTON_PRIMARY_STYLE = {
    "bg": Colors.primary,
    "color": "#0A1F1A",
    "border_radius": Radius.sm,
    "font_weight": Typography.bold,
    "padding_x": Spacing.xl,
    "height": "44px",
    "_hover": {"bg": Colors.primary_hover},
    "transition": Transitions.fast,
}

BUTTON_GHOST_STYLE = {
    "bg": "transparent",
    "color": Colors.primary,
    "border": f"1px solid {Colors.border_accent}",
    "border_radius": Radius.sm,
    "font_weight": Typography.semibold,
    "_hover": {
        "bg": Colors.primary_glow,
        "border_color": Colors.primary,
    },
    "transition": Transitions.fast,
}


# Quick export aliases
C = Colors
R = Radius
Sp = Spacing
Ty = Typography
Sh = Shadows
Tr = Transitions
