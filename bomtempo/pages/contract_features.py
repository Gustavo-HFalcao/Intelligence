"""
Página de Gerenciamento de Feature Flags por Contrato
Rota: /admin/contract-features
Acesso: Administrador
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.feature_flags_state import FeatureFlagsState

# ── Design tokens locais ─────────────────────────────────────────────────────

_MODULE_REEMBOLSO_COLOR  = "#C98B2A"   # copper
_MODULE_REEMBOLSO_BG     = "rgba(201,139,42,0.08)"
_MODULE_REEMBOLSO_BORDER = "rgba(201,139,42,0.18)"

_MODULE_RDO_COLOR  = "#2A9D8F"         # patina
_MODULE_RDO_BG     = "rgba(42,157,143,0.08)"
_MODULE_RDO_BORDER = "rgba(42,157,143,0.18)"

_MODULE_AMBOS_COLOR  = "#8B6FBF"       # slate-violet
_MODULE_AMBOS_BG     = "rgba(139,111,191,0.08)"
_MODULE_AMBOS_BORDER = "rgba(139,111,191,0.18)"

_MODULE_INFRA_COLOR  = "#E05252"       # vermelho alerta — infra crítica
_MODULE_INFRA_BG     = "rgba(224,82,82,0.08)"
_MODULE_INFRA_BORDER = "rgba(224,82,82,0.18)"

_ROW_ON_BG      = "rgba(201,139,42,0.04)"
_ROW_ON_BORDER  = "rgba(201,139,42,0.16)"
_ROW_OFF_BG     = "transparent"
_ROW_OFF_BORDER = "rgba(255,255,255,0.05)"

_SECTION_DIVIDER = "rgba(255,255,255,0.06)"


# ── Module badge — refinado, sem cores Radix padrão ──────────────────────────

def _module_chip(module: str) -> rx.Component:
    """Chip de módulo com estilo manual — sem depender do Radix color_scheme."""
    color  = rx.match(module,
        ("reembolso", _MODULE_REEMBOLSO_COLOR),
        ("rdo",       _MODULE_RDO_COLOR),
        ("ambos",     _MODULE_AMBOS_COLOR),
        ("infra",     _MODULE_INFRA_COLOR),
        S.TEXT_MUTED,
    )
    bg     = rx.match(module,
        ("reembolso", _MODULE_REEMBOLSO_BG),
        ("rdo",       _MODULE_RDO_BG),
        ("ambos",     _MODULE_AMBOS_BG),
        ("infra",     _MODULE_INFRA_BG),
        "rgba(255,255,255,0.04)",
    )
    border = rx.match(module,
        ("reembolso", _MODULE_REEMBOLSO_BORDER),
        ("rdo",       _MODULE_RDO_BORDER),
        ("ambos",     _MODULE_AMBOS_BORDER),
        ("infra",     _MODULE_INFRA_BORDER),
        "rgba(255,255,255,0.08)",
    )
    label  = rx.match(module,
        ("reembolso", "Reembolso"),
        ("rdo",       "RDO"),
        ("ambos",     "Ambos"),
        ("infra",     "Infra"),
        module,
    )
    return rx.box(
        rx.text(
            label,
            font_size="10px",
            font_weight="700",
            font_family=S.FONT_TECH,
            letter_spacing="0.06em",
            color=color,
            style={"text_transform": "uppercase"},
        ),
        px="8px",
        py="3px",
        bg=bg,
        border=rx.el.span(border).to_string().replace("(","").replace(")",""),  # workaround
        border_radius="4px",
        style={"border": f"1px solid"},
        # Aplica border via style dict para aceitar Var
    )


def _module_tag(module: str) -> rx.Component:
    """Tag de módulo inline com cor manual."""
    return rx.box(
        rx.match(
            module,
            ("reembolso", rx.text(
                "REEMBOLSO",
                font_size="9px", font_weight="700", font_family=S.FONT_TECH,
                letter_spacing="0.07em", color=_MODULE_REEMBOLSO_COLOR,
            )),
            ("rdo", rx.text(
                "RDO",
                font_size="9px", font_weight="700", font_family=S.FONT_TECH,
                letter_spacing="0.07em", color=_MODULE_RDO_COLOR,
            )),
            ("ambos", rx.text(
                "AMBOS",
                font_size="9px", font_weight="700", font_family=S.FONT_TECH,
                letter_spacing="0.07em", color=_MODULE_AMBOS_COLOR,
            )),
            ("infra", rx.text(
                "INFRA",
                font_size="9px", font_weight="700", font_family=S.FONT_TECH,
                letter_spacing="0.07em", color=_MODULE_INFRA_COLOR,
            )),
            rx.text(module, font_size="9px", color=S.TEXT_MUTED),
        ),
        px="7px",
        py="2px",
        border_radius="3px",
        style={
            "background": rx.match(
                module,
                ("reembolso", _MODULE_REEMBOLSO_BG),
                ("rdo",       _MODULE_RDO_BG),
                ("ambos",     _MODULE_AMBOS_BG),
                ("infra",     _MODULE_INFRA_BG),
                "rgba(255,255,255,0.04)",
            ),
            "border": rx.match(
                module,
                ("reembolso", f"1px solid {_MODULE_REEMBOLSO_BORDER}"),
                ("rdo",       f"1px solid {_MODULE_RDO_BORDER}"),
                ("ambos",     f"1px solid {_MODULE_AMBOS_BORDER}"),
                ("infra",     f"1px solid {_MODULE_INFRA_BORDER}"),
                "1px solid rgba(255,255,255,0.08)",
            ),
        },
    )


# ── Section header (separador de módulo) ────────────────────────────────────

def _section_header(label: str, module: str) -> rx.Component:
    _color_map  = {"reembolso": _MODULE_REEMBOLSO_COLOR, "rdo": _MODULE_RDO_COLOR, "ambos": _MODULE_AMBOS_COLOR, "infra": _MODULE_INFRA_COLOR}
    _bg_map     = {"reembolso": _MODULE_REEMBOLSO_BG,    "rdo": _MODULE_RDO_BG,    "ambos": _MODULE_AMBOS_BG,    "infra": _MODULE_INFRA_BG}
    _border_map = {"reembolso": _MODULE_REEMBOLSO_BORDER,"rdo": _MODULE_RDO_BORDER,"ambos": _MODULE_AMBOS_BORDER,"infra": _MODULE_INFRA_BORDER}
    _icon_map   = {"reembolso": "credit-card", "rdo": "clipboard-list", "ambos": "layers", "infra": "server"}
    color  = _color_map.get(module, _MODULE_AMBOS_COLOR)
    bg     = _bg_map.get(module, _MODULE_AMBOS_BG)
    border = _border_map.get(module, _MODULE_AMBOS_BORDER)
    icon   = _icon_map.get(module, "layers")

    return rx.hstack(
        rx.box(
            rx.icon(tag=icon, size=12, color=color),
            p="5px",
            bg=bg,
            border=f"1px solid {border}",
            border_radius="6px",
        ),
        rx.text(
            label,
            font_size="11px",
            font_weight="700",
            font_family=S.FONT_TECH,
            letter_spacing="0.08em",
            color=color,
            style={"text_transform": "uppercase"},
        ),
        rx.box(
            height="1px",
            flex="1",
            bg=f"linear-gradient(90deg, {border}, transparent)",
        ),
        spacing="2",
        align="center",
        width="100%",
        padding_x="2px",
        padding_y="4px",
    )


# ── Feature Row ──────────────────────────────────────────────────────────────

def _feature_row(row: dict) -> rx.Component:
    is_on = row["enabled"] == "true"
    return rx.hstack(
        # Toggle
        rx.switch(
            checked=is_on,
            on_change=FeatureFlagsState.toggle_feature(row["key"]),
            color_scheme="amber",
            size="2",
        ),
        # Info
        rx.vstack(
            rx.text(
                row["label"],
                font_size="13px",
                font_weight="600",
                color=rx.cond(is_on, S.TEXT_PRIMARY, S.TEXT_MUTED),
                line_height="1.3",
            ),
            rx.text(
                row["key"],
                font_size="10px",
                color="rgba(136,153,153,0.5)",
                font_family=S.FONT_MONO,
                letter_spacing="0.02em",
            ),
            spacing="0",
            align="start",
            flex="1",
        ),
        # Module tag
        _module_tag(row["module"]),
        # Status dot
        rx.cond(
            is_on,
            rx.hstack(
                rx.box(
                    width="6px", height="6px",
                    border_radius="50%",
                    bg=S.SUCCESS,
                    style={"box_shadow": f"0 0 6px {S.SUCCESS}"},
                ),
                rx.text("ATIVO", font_size="9px", font_weight="700",
                        font_family=S.FONT_TECH, letter_spacing="0.06em",
                        color=S.SUCCESS),
                spacing="1",
                align="center",
            ),
            rx.hstack(
                rx.box(
                    width="6px", height="6px",
                    border_radius="50%",
                    bg="rgba(255,255,255,0.15)",
                ),
                rx.text("INATIVO", font_size="9px", font_weight="700",
                        font_family=S.FONT_TECH, letter_spacing="0.06em",
                        color="rgba(136,153,153,0.5)"),
                spacing="1",
                align="center",
            ),
        ),
        spacing="3",
        align="center",
        width="100%",
        padding="11px 14px",
        bg=rx.cond(is_on, _ROW_ON_BG, _ROW_OFF_BG),
        border_radius="8px",
        border=rx.cond(is_on, f"1px solid {_ROW_ON_BORDER}", f"1px solid {_ROW_OFF_BORDER}"),
        transition="all 0.15s ease",
    )


# ── Cards base ───────────────────────────────────────────────────────────────

def _card(*children, **kwargs) -> rx.Component:
    return rx.box(
        *children,
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="14px",
        padding="20px",
        **kwargs,
    )


# ── Page ─────────────────────────────────────────────────────────────────────

def contract_features_page() -> rx.Component:
    return rx.vstack(

        # ── Header ──────────────────────────────────────────────────────────
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        rx.icon(tag="sliders-horizontal", size=16, color=S.COPPER),
                        p="8px",
                        bg=S.COPPER_GLOW,
                        border=f"1px solid {S.BORDER_ACCENT}",
                        border_radius="8px",
                    ),
                    rx.vstack(
                        rx.text(
                            "FEATURE FLAGS",
                            font_size="18px",
                            font_weight="900",
                            font_family=S.FONT_TECH,
                            letter_spacing="0.07em",
                            color=S.TEXT_PRIMARY,
                            line_height="1",
                        ),
                        rx.text(
                            "Controle de funcionalidades por contrato",
                            font_size="11px",
                            color=S.TEXT_MUTED,
                            letter_spacing="0.04em",
                            font_family=S.FONT_TECH,
                        ),
                        spacing="1",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                ),
                spacing="0",
                align="start",
            ),
            rx.spacer(),
            # Status feedback
            rx.cond(
                FeatureFlagsState.save_status != "",
                rx.hstack(
                    rx.cond(
                        FeatureFlagsState.save_status.contains("✅"),
                        rx.icon(tag="check-circle-2", size=14, color=S.SUCCESS),
                        rx.icon(tag="alert-circle", size=14, color="#E05252"),
                    ),
                    rx.text(
                        FeatureFlagsState.save_status,
                        font_size="12px",
                        font_weight="600",
                        font_family=S.FONT_TECH,
                        color=rx.cond(
                            FeatureFlagsState.save_status.contains("✅"),
                            S.SUCCESS,
                            "#E05252",
                        ),
                    ),
                    spacing="2",
                    align="center",
                    px="12px",
                    py="7px",
                    bg=rx.cond(
                        FeatureFlagsState.save_status.contains("✅"),
                        S.SUCCESS_BG,
                        "rgba(224,82,82,0.08)",
                    ),
                    border=rx.cond(
                        FeatureFlagsState.save_status.contains("✅"),
                        f"1px solid rgba(42,157,143,0.25)",
                        "1px solid rgba(224,82,82,0.25)",
                    ),
                    border_radius="8px",
                ),
            ),
            align="center",
            width="100%",
        ),

        # Divider copper
        rx.box(
            height="1px",
            bg=f"linear-gradient(90deg, {S.COPPER}, transparent 70%)",
            width="100%",
            opacity="0.6",
        ),

        # ── Contract Selector ────────────────────────────────────────────────
        _card(
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="building-2", size=15, color=S.COPPER),
                    rx.text(
                        "CONTRATO",
                        font_size="10px",
                        font_weight="700",
                        font_family=S.FONT_TECH,
                        letter_spacing="0.1em",
                        color=S.TEXT_MUTED,
                        style={"text_transform": "uppercase"},
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.cond(
                    FeatureFlagsState.has_contract_selected,
                    rx.hstack(
                        rx.box(
                            width="6px", height="6px",
                            border_radius="50%",
                            bg=S.COPPER,
                        ),
                        rx.text(
                            FeatureFlagsState.selected_contract,
                            font_size="12px",
                            font_weight="700",
                            font_family=S.FONT_TECH,
                            color=S.COPPER,
                        ),
                        spacing="2",
                        align="center",
                    ),
                ),
                align="center",
                width="100%",
                margin_bottom="12px",
            ),
            rx.cond(
                FeatureFlagsState.contracts_options.length() > 0,
                rx.select.root(
                    rx.select.trigger(
                        width="100%",
                        height="42px",
                        bg="rgba(255,255,255,0.03)",
                        border=f"1px solid rgba(255,255,255,0.1)",
                        border_radius="8px",
                        font_size="14px",
                        font_family=S.FONT_BODY,
                        color=S.TEXT_PRIMARY,
                        padding_x="14px",
                        style={"_hover": {"border_color": S.COPPER}},
                    ),
                    rx.select.content(
                        rx.foreach(
                            FeatureFlagsState.contracts_options,
                            lambda c: rx.select.item(c, value=c),
                        ),
                        bg=S.BG_ELEVATED,
                    ),
                    value=FeatureFlagsState.selected_contract,
                    on_change=FeatureFlagsState.set_selected_contract,
                    width="100%",
                ),
                rx.text("Nenhum contrato encontrado.", color=S.TEXT_MUTED, font_size="13px"),
            ),
            width="100%",
        ),

        # ── Features List ────────────────────────────────────────────────────
        rx.cond(
            FeatureFlagsState.is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color=S.COPPER),
                    rx.text("Carregando configurações...", color=S.TEXT_MUTED,
                            font_size="12px", font_family=S.FONT_TECH),
                    spacing="3",
                    align="center",
                ),
                padding="60px",
                width="100%",
            ),
            rx.cond(
                FeatureFlagsState.has_contract_selected,
                _card(
                    # Card header
                    rx.hstack(
                        rx.icon(tag="toggle-right", size=15, color=S.TEXT_MUTED),
                        rx.text(
                            "MÓDULOS ATIVOS",
                            font_size="10px",
                            font_weight="700",
                            font_family=S.FONT_TECH,
                            letter_spacing="0.1em",
                            color=S.TEXT_MUTED,
                        ),
                        rx.spacer(),
                        # Legend chips
                        rx.hstack(
                            rx.hstack(
                                rx.box(width="8px", height="8px", border_radius="2px",
                                       bg=_MODULE_REEMBOLSO_BG,
                                       border=f"1px solid {_MODULE_REEMBOLSO_BORDER}"),
                                rx.text("Reembolso", font_size="10px", color=_MODULE_REEMBOLSO_COLOR,
                                        font_family=S.FONT_TECH, font_weight="600"),
                                spacing="1", align="center",
                            ),
                            rx.hstack(
                                rx.box(width="8px", height="8px", border_radius="2px",
                                       bg=_MODULE_RDO_BG,
                                       border=f"1px solid {_MODULE_RDO_BORDER}"),
                                rx.text("RDO", font_size="10px", color=_MODULE_RDO_COLOR,
                                        font_family=S.FONT_TECH, font_weight="600"),
                                spacing="1", align="center",
                            ),
                            rx.hstack(
                                rx.box(width="8px", height="8px", border_radius="2px",
                                       bg=_MODULE_AMBOS_BG,
                                       border=f"1px solid {_MODULE_AMBOS_BORDER}"),
                                rx.text("Ambos", font_size="10px", color=_MODULE_AMBOS_COLOR,
                                        font_family=S.FONT_TECH, font_weight="600"),
                                spacing="1", align="center",
                            ),
                            rx.hstack(
                                rx.box(width="8px", height="8px", border_radius="2px",
                                       bg=_MODULE_INFRA_BG,
                                       border=f"1px solid {_MODULE_INFRA_BORDER}"),
                                rx.text("Infra", font_size="10px", color=_MODULE_INFRA_COLOR,
                                        font_family=S.FONT_TECH, font_weight="600"),
                                spacing="1", align="center",
                            ),
                            spacing="3",
                        ),
                        align="center",
                        width="100%",
                        padding_bottom="16px",
                        border_bottom=f"1px solid {_SECTION_DIVIDER}",
                        margin_bottom="16px",
                    ),

                    # Grupo Infraestrutura
                    _section_header("Infraestrutura do Sistema", "infra"),
                    rx.box(height="8px"),
                    rx.vstack(
                        rx.foreach(
                            FeatureFlagsState.feature_rows,
                            lambda row: rx.cond(
                                row["module"] == "infra",
                                _feature_row(row),
                                rx.fragment(),
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),

                    rx.box(height="16px"),

                    # Grupo Reembolso
                    _section_header("Módulo Reembolso", "reembolso"),
                    rx.box(height="8px"),
                    rx.vstack(
                        rx.foreach(
                            FeatureFlagsState.feature_rows,
                            lambda row: rx.cond(
                                row["module"] == "reembolso",
                                _feature_row(row),
                                rx.fragment(),
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),

                    rx.box(height="16px"),

                    # Grupo RDO
                    _section_header("Módulo RDO", "rdo"),
                    rx.box(height="8px"),
                    rx.vstack(
                        rx.foreach(
                            FeatureFlagsState.feature_rows,
                            lambda row: rx.cond(
                                row["module"] == "rdo",
                                _feature_row(row),
                                rx.fragment(),
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),

                    # Grupo Ambos (só renderiza se existir)
                    rx.vstack(
                        rx.foreach(
                            FeatureFlagsState.feature_rows,
                            lambda row: rx.cond(
                                row["module"] == "ambos",
                                rx.vstack(
                                    rx.box(height="16px"),
                                    _section_header("Módulos Compartilhados", "ambos"),
                                    rx.box(height="8px"),
                                    _feature_row(row),
                                    spacing="0",
                                    width="100%",
                                ),
                                rx.fragment(),
                            ),
                        ),
                        spacing="0",
                        width="100%",
                    ),

                    rx.box(height="12px"),
                    rx.box(
                        height="1px",
                        bg=_SECTION_DIVIDER,
                        width="100%",
                    ),
                    rx.box(height="12px"),

                    # Footer note
                    rx.hstack(
                        rx.icon(tag="zap", size=12, color=S.COPPER),
                        rx.text(
                            "Alterações entram em vigor imediatamente. "
                            "Formulários e dashboards refletem as mudanças na próxima carga.",
                            font_size="11px",
                            color="rgba(136,153,153,0.7)",
                            line_height="1.5",
                            font_family=S.FONT_BODY,
                        ),
                        spacing="2",
                        align="start",
                    ),
                    width="100%",
                ),
                # Empty state
                rx.center(
                    rx.vstack(
                        rx.box(
                            rx.icon(tag="sliders-horizontal", size=24, color=S.TEXT_MUTED),
                            p="16px",
                            bg="rgba(255,255,255,0.02)",
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            border_radius="12px",
                        ),
                        rx.text(
                            "Selecione um contrato",
                            font_size="14px",
                            font_weight="600",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_TECH,
                        ),
                        rx.text(
                            "As flags de funcionalidades serão exibidas aqui.",
                            font_size="12px",
                            color="rgba(136,153,153,0.5)",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    padding="48px",
                    width="100%",
                ),
            ),
        ),

        # ── Info Box ─────────────────────────────────────────────────────────
        rx.box(
            rx.hstack(
                rx.icon(tag="info", size=13, color=S.PATINA),
                rx.text(
                    "COMO FUNCIONA",
                    font_size="9px",
                    font_weight="700",
                    font_family=S.FONT_TECH,
                    letter_spacing="0.1em",
                    color=S.PATINA,
                ),
                spacing="2",
                align="center",
                margin_bottom="10px",
            ),
            rx.vstack(
                rx.hstack(
                    rx.box(width="3px", height="3px", border_radius="50%",
                           bg="rgba(136,153,153,0.4)", margin_top="6px", flex_shrink="0"),
                    rx.text(
                        "Features desligadas ocultam campos do formulário — sem GPS, o campo de localização fica simples",
                        font_size="11px", color="rgba(136,153,153,0.7)", line_height="1.6",
                    ),
                    spacing="2", align="start",
                ),
                rx.hstack(
                    rx.box(width="3px", height="3px", border_radius="50%",
                           bg="rgba(136,153,153,0.4)", margin_top="6px", flex_shrink="0"),
                    rx.text(
                        "Gráficos de features desligadas são ocultados no dashboard — sem dados zerados",
                        font_size="11px", color="rgba(136,153,153,0.7)", line_height="1.6",
                    ),
                    spacing="2", align="start",
                ),
                rx.hstack(
                    rx.box(width="3px", height="3px", border_radius="50%",
                           bg="rgba(136,153,153,0.4)", margin_top="6px", flex_shrink="0"),
                    rx.text(
                        "Configurações são independentes por contrato — contratos diferentes podem ter combinações distintas",
                        font_size="11px", color="rgba(136,153,153,0.7)", line_height="1.6",
                    ),
                    spacing="2", align="start",
                ),
                rx.hstack(
                    rx.box(width="3px", height="3px", border_radius="50%",
                           bg=f"{_MODULE_INFRA_COLOR}55", margin_top="6px", flex_shrink="0"),
                    rx.text(
                        "Flags de Infraestrutura têm padrão global — PDF desligado por padrão (servidor 1 GB RAM). "
                        "Ligue por contrato após upgrade de máquina.",
                        font_size="11px", color=f"{_MODULE_INFRA_COLOR}BB", line_height="1.6",
                    ),
                    spacing="2", align="start",
                ),
                spacing="2",
                align="start",
            ),
            bg="rgba(42,157,143,0.04)",
            border=f"1px solid rgba(42,157,143,0.12)",
            border_radius="12px",
            padding="16px 18px",
            width="100%",
        ),

        spacing="4",
        width="100%",
        max_width="860px",
        padding_x=["16px", "24px"],
        padding_y="24px",
    )
