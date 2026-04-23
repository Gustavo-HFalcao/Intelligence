"""
Windy Map Widget — Interactive meteorological map with layer toggles.
Replaces the legacy text-based weather_widget.py inside the Project Hub
"Visão Geral" tab.  Uses the free Windy iframe embed (no API key required).
"""
import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState

# ── Layer configuration ─────────────────────────────────────────────────────
# Each layer toggles the Windy overlay via URL rebuild
_LAYERS = [
    ("Chuva",      "🌧",  "rain"),
    ("Satélite",   "🛰",  "satellite"),
    ("Vento",      "💨",  "wind"),
    ("Temp",       "🌡",  "temp"),
]


def _layer_chip(label: str, emoji: str, overlay: str) -> rx.Component:
    """A single toggle chip for the Windy layer selector."""
    is_active = GlobalState.windy_layer == overlay
    return rx.box(
        rx.hstack(
            rx.text(emoji, font_size="13px"),
            rx.text(
                label,
                font_size="10px",
                font_weight="700",
                color=rx.cond(is_active, S.BG_VOID, S.TEXT_MUTED),
            ),
            spacing="1",
            align="center",
        ),
        padding="4px 10px",
        border_radius=S.R_CONTROL,
        cursor="pointer",
        bg=rx.cond(is_active, S.COPPER, "rgba(255,255,255,0.04)"),
        border=rx.cond(
            is_active,
            f"1px solid {S.COPPER}",
            f"1px solid {S.BORDER_SUBTLE}",
        ),
        on_click=GlobalState.set_windy_layer(overlay),
        _hover={
            "border_color": S.COPPER,
            "bg": rx.cond(is_active, S.COPPER, "rgba(201,139,42,0.08)"),
        },
        transition="all 0.18s ease",
    )


def windy_map_widget() -> rx.Component:
    """
    Full-featured Windy map embedded as an iframe inside a glass card.
    The iframe src is rebuilt whenever weather_lat / weather_lon / windy_layer change.
    """
    # Build the Windy embed URL from state vars
    # Using rx.cond chains to assemble the src string safely
    base = "https://embed.windy.com/embed2.html"
    params = (
        "?zoom=8"
        "&level=surface"
        "&product=ecmwf"
        "&menu="
        "&message=true"
        "&marker=true"
        "&calendar=now"
        "&pressure=true"
        "&type=map"
        "&location=coordinates"
        "&detail="
        "&metricWind=km%2Fh"
        "&metricTemp=%C2%B0C"
        "&radarRange=-1"
    )

    # Compose the full src as a computed string — Reflex evaluates at render
    windy_src = (
        base
        + "?lat=" + GlobalState.weather_lat.to_string()
        + "&lon=" + GlobalState.weather_lon.to_string()
        + "&detailLat=" + GlobalState.weather_lat.to_string()
        + "&detailLon=" + GlobalState.weather_lon.to_string()
        + "&zoom=8&level=surface&overlay=" + GlobalState.windy_layer
        + "&product=ecmwf&menu=&message=true&marker=true&calendar=now"
        + "&pressure=true&type=map&location=coordinates&detail="
        + "&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1"
    )

    return rx.box(
        rx.vstack(
            # ── Header row ───────────────────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.center(
                        rx.icon(tag="map", size=14, color=S.COPPER),
                        padding="6px",
                        bg=S.COPPER_GLOW,
                        border_radius=S.R_CONTROL,
                        border=f"1px solid {S.BORDER_ACCENT}",
                    ),
                    rx.vstack(
                        rx.text(
                            "MAPA METEOROLÓGICO",
                            font_size="9px",
                            font_weight="700",
                            color=S.TEXT_MUTED,
                            text_transform="uppercase",
                            letter_spacing="0.12em",
                        ),
                        rx.text(
                            GlobalState.weather_location_name,
                            font_size="14px",
                            font_weight="700",
                            color="var(--text-main)",
                            font_family=S.FONT_TECH,
                        ),
                        spacing="0",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.spacer(),
                # Weather risk badge
                rx.box(
                    rx.hstack(
                        rx.box(
                            width="6px",
                            height="6px",
                            border_radius="50%",
                            bg=rx.cond(
                                GlobalState.weather_risk_level == "High",
                                S.DANGER,
                                rx.cond(
                                    GlobalState.weather_risk_level == "Medium",
                                    S.WARNING,
                                    S.PATINA,
                                ),
                            ),
                        ),
                        rx.text(
                            rx.cond(
                                GlobalState.weather_risk_level == "High",
                                "Risco Alto",
                                rx.cond(
                                    GlobalState.weather_risk_level == "Medium",
                                    "Risco Médio",
                                    rx.cond(
                                        GlobalState.weather_risk_level == "Unknown",
                                        "Carregando",
                                        "Risco Baixo",
                                    ),
                                ),
                            ),
                            font_size="9px",
                            font_weight="700",
                            color=rx.cond(
                                GlobalState.weather_risk_level == "High",
                                S.DANGER,
                                rx.cond(
                                    GlobalState.weather_risk_level == "Medium",
                                    S.WARNING,
                                    S.PATINA,
                                ),
                            ),
                        ),
                        spacing="1",
                        align="center",
                    ),
                    padding="4px 10px",
                    border_radius=S.R_CONTROL,
                    bg=rx.cond(
                        GlobalState.weather_risk_level == "High",
                        S.DANGER_BG,
                        rx.cond(
                            GlobalState.weather_risk_level == "Medium",
                            S.WARNING_BG,
                            S.SUCCESS_BG,
                        ),
                    ),
                    border=rx.cond(
                        GlobalState.weather_risk_level == "High",
                        "1px solid rgba(239,68,68,0.3)",
                        rx.cond(
                            GlobalState.weather_risk_level == "Medium",
                            "1px solid rgba(245,158,11,0.3)",
                            "1px solid rgba(42,157,143,0.3)",
                        ),
                    ),
                ),
                align="center",
                width="100%",
                margin_bottom="12px",
            ),
            # ── Layer selector chips ───────────────────────────────────
            rx.hstack(
                *[_layer_chip(lbl, emoji, overlay) for lbl, emoji, overlay in _LAYERS],
                spacing="2",
                flex_wrap="wrap",
                margin_bottom="12px",
            ),
            # ── Windy iframe ───────────────────────────────────────────
            rx.cond(
                GlobalState.weather_loading,
                # Loading shimmer
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3", color=S.COPPER),
                        rx.text(
                            "Carregando mapa meteorológico...",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            font_style="italic",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    height="380px",
                    width="100%",
                    bg="rgba(0,0,0,0.2)",
                    border_radius=S.R_CARD,
                    border=f"1px solid {S.BORDER_SUBTLE}",
                ),
                # Windy iframe
                rx.box(
                    rx.el.iframe(
                        src=windy_src,
                        width="100%",
                        height="380px",
                        frameborder="0",
                        allow="fullscreen",
                        style={
                            "border": "none",
                            "borderRadius": S.R_CARD,
                            "display": "block",
                        },
                    ),
                    width="100%",
                    border_radius=S.R_CARD,
                    overflow="hidden",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                ),
            ),
            # ── Footer: temperature + analyze button  ─────────────────
            rx.cond(
                GlobalState.weather_data != {},
                rx.hstack(
                    rx.hstack(
                        rx.icon(tag="thermometer", size=13, color=S.PATINA),
                        rx.text(
                            GlobalState.weather_data["temp"].to_string() + "°C",
                            font_family=S.FONT_MONO,
                            font_size="13px",
                            font_weight="700",
                            color="var(--text-main)",
                        ),
                        spacing="1",
                        align="center",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.hstack(
                            rx.icon("scan-eye", size=13),
                            rx.text("Analisar Impacto", font_size="10px"),
                            spacing="2",
                            align="center",
                        ),
                        size="1",
                        variant="ghost",
                        color=S.COPPER,
                        on_click=GlobalState.analyze_weather_impact,
                        _hover={"bg": S.COPPER_GLOW},
                    ),
                    width="100%",
                    align="center",
                    margin_top="8px",
                ),
            ),
            width="100%",
            spacing="0",
        ),
        **{**S.GLASS_CARD, "padding": "20px 24px"},
        width="100%",
    )
