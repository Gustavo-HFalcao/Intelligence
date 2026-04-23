# ============================================================
#  DEEP TECTONIC — Design System for BOMTEMPO Dashboard
#  Migrated pixel-perfect from React+TS reference
# ============================================================
# Typography: Rajdhani (display/tech) · Outfit (body) · JetBrains Mono (data)
# Theme: Dark atmospheric — void/depth/surface + copper/patina accents
# ============================================================

FONT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Rajdhani:wght@500;600;700"
    "&family=Outfit:wght@300;400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500;600"
    "&display=swap"
)

# ── Background ───────────────────────────────────────────────
BG_VOID = "#030504"
BG_DEPTH = "#081210"
BG_SURFACE = "#0e1a17"
BG_GLASS = "rgba(14, 26, 23, 0.7)"
BG_ELEVATED = "#142420"
BG_INPUT = "rgba(255, 255, 255, 0.03)"

# ── Text ─────────────────────────────────────────────────────
TEXT_PRIMARY = "#E0E0E0"
TEXT_SECONDARY = "#889999"
TEXT_MUTED = "#889999"
TEXT_WHITE = "#FFFFFF"

# ── Border ───────────────────────────────────────────────────
BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
BORDER_ACCENT = "rgba(201, 139, 42, 0.3)"
BORDER_HIGHLIGHT = "rgba(201, 139, 42, 0.5)"

# ── Brand Colors (Copper + Patina) ──────────────────────────
COPPER = "#C98B2A"
COPPER_500 = COPPER
COPPER_LIGHT = "#E0A63B"
COPPER_GLOW = "rgba(201, 139, 42, 0.15)"
PATINA = "#2A9D8F"
PATINA_DARK = "#1d7066"
PATINA_GLOW = "rgba(42, 157, 143, 0.15)"

ORANGE = "#E89845"

# ── Status ───────────────────────────────────────────────────
SUCCESS = "#2A9D8F"
SUCCESS_BG = "rgba(42, 157, 143, 0.1)"
WARNING = "#F59E0B"
WARNING_BG = "rgba(245, 158, 11, 0.12)"
DANGER = "#EF4444"
DANGER_BG = "rgba(239, 68, 68, 0.1)"
INFO = "#3B82F6"
INFO_BG = "rgba(59, 130, 246, 0.12)"

# ── Typography ───────────────────────────────────────────────
FONT_DISPLAY = "'Rajdhani', sans-serif"
FONT_TECH = "'Rajdhani', sans-serif"
FONT_BODY = "'Outfit', sans-serif"
FONT_MONO = "'JetBrains Mono', monospace"

# ── Global Style ─────────────────────────────────────────────
GLOBAL_STYLE = {
    "font_family": FONT_BODY,
    "background": "var(--bg-void, " + BG_VOID + ")",
    "color": "var(--text-main, " + TEXT_PRIMARY + ")",
    "::selection": {
        "background": "rgba(201, 139, 42, 0.35)",
        "color": "#fff",
    },
}

# ── Sidebar ──────────────────────────────────────────────────
SIDEBAR_WIDTH = "288px"

SIDEBAR_STYLE = {
    "width": SIDEBAR_WIDTH,
    "min_width": SIDEBAR_WIDTH,
    "height": "100vh",
    "position": "sticky",
    "top": "0",
    "z_index": "50",
    "overflow": "hidden",
    "display": "flex",
    "flex_direction": "column",
}

# ── Main content ─────────────────────────────────────────────
MAIN_CONTENT_STYLE = {
    "flex": "1",
    "min_width": "0",
    "overflow_x": "hidden",
    # Horizontal padding lives in the inner content box (padding_x),
    # keeping it here caused double-padding and asymmetric black edges.
    "padding_top": "1.5rem",
    "padding_bottom": "1.5rem",
}

# ── Border Radius (Enterprise Sharp System) ──────────────────
R_CARD = "6px"      # panels, cards, modals
R_CONTROL = "3px"   # inputs, buttons, badges

# ── Glass Card ───────────────────────────────────────────────
GLASS_CARD = {
    "background": BG_GLASS,
    "backdrop_filter": "blur(12px)",
    "border": f"1px solid {BORDER_SUBTLE}",
    "border_radius": R_CARD,
    "padding": "32px",
    "box_shadow": "0 4px 30px rgba(0, 0, 0, 0.3)",
    "transition": "all 0.5s ease",
    "_hover": {
        "border_color": BORDER_HIGHLIGHT,
    },
}

GLASS_CARD_NO_HOVER = {
    "background": BG_GLASS,
    "backdrop_filter": "blur(12px)",
    "border": f"1px solid {BORDER_SUBTLE}",
    "border_radius": R_CARD,
    "padding": "32px",
    "box_shadow": "0 4px 30px rgba(0, 0, 0, 0.3)",
}

# ── Section title ────────────────────────────────────────────
SECTION_TITLE_STYLE = {
    "font_family": FONT_TECH,
    # clamp(min, fluid, max) — max matches previous desktop value
    "font_size": "clamp(1rem, 3.5vw, 1.25rem)",
    "font_weight": "700",
    "color": TEXT_PRIMARY,
    "margin_bottom": "24px",
    "text_transform": "uppercase",
    "letter_spacing": "0.02em",
}

SECTION_SUBTITLE_STYLE = {
    "font_size": "clamp(0.65rem, 2vw, 0.75rem)",
    "color": TEXT_MUTED,
    "text_transform": "uppercase",
    "letter_spacing": "0.15em",
    "font_weight": "700",
}

# ── Page title ───────────────────────────────────────────────
PAGE_TITLE_STYLE = {
    "font_family": FONT_TECH,
    # clamp: mobile 22px → desktop 30px (1.875rem)
    "font_size": "clamp(1.375rem, 4.5vw, 1.875rem)",
    "font_weight": "700",
    "color": TEXT_WHITE,
    "text_transform": "uppercase",
    "letter_spacing": "-0.02em",
}

PAGE_SUBTITLE_STYLE = {
    # clamp: mobile ~13px → desktop 14px (0.875rem)
    "font_size": "clamp(0.8rem, 2.5vw, 0.875rem)",
    "color": TEXT_MUTED,
    "margin_top": "4px",
}

# ── Responsive padding helper ─────────────────────────────────
# clamp(mobile, fluid, desktop) — use for padding props
PADDING_HERO = "clamp(20px, 5vw, 48px)"   # hero header panels: 48px desktop
PADDING_CARD = "clamp(16px, 3vw, 32px)"   # glass cards: 32px desktop

# ── Recharts ─────────────────────────────────────────────────
TOOLTIP_STYLE = {
    "backgroundColor": BG_DEPTH,
    "borderColor": BORDER_ACCENT,
    "borderRadius": "8px",
    "boxShadow": "0 10px 40px rgba(0, 0, 0, 0.5)",
    "fontSize": "12px",
    "color": TEXT_PRIMARY,
}

# Premium tooltip — Deep Tectonic glass, sharp, monospace
TOOLTIP_PREMIUM = {
    "background": "rgba(6,14,12,0.97)",
    "border": f"1px solid {COPPER_500}",
    "borderRadius": "6px",
    "boxShadow": f"0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(201,139,42,0.08)",
    "padding": "10px 14px",
    "fontFamily": "JetBrains Mono, monospace",
    "fontSize": "11px",
    "color": TEXT_PRIMARY,
    "backdropFilter": "blur(16px)",
    "minWidth": "160px",
}
TOOLTIP_PREMIUM_LABEL = {
    "color": COPPER_500,
    "fontWeight": "700",
    "fontSize": "10px",
    "letterSpacing": "0.08em",
    "textTransform": "uppercase",
    "marginBottom": "6px",
    "paddingBottom": "6px",
    "borderBottom": f"1px solid rgba(201,139,42,0.2)",
}
TOOLTIP_PREMIUM_ITEM = {
    "color": TEXT_PRIMARY,
    "fontFamily": "JetBrains Mono, monospace",
    "fontSize": "11px",
    "padding": "2px 0",
}
TOOLTIP_CURSOR_PREMIUM = {
    "fill": "rgba(201,139,42,0.04)",
    "stroke": f"rgba(201,139,42,0.15)",
    "strokeWidth": 1,
}
TOOLTIP_CURSOR_LINE = {
    "stroke": f"rgba(201,139,42,0.3)",
    "strokeWidth": 1,
    "strokeDasharray": "4 2",
}

TOOLTIP_CURSOR = {"fill": "rgba(255, 255, 255, 0.03)"}

AXIS_TICK = {"fill": TEXT_MUTED, "fontSize": 10, "fontFamily": "JetBrains Mono"}
AXIS_TICK_LABEL = {"fill": TEXT_MUTED, "fontSize": 12}
