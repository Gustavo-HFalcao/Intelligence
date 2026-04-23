"""
Alertas — Bomtempo Intelligence (Enterprise Revamp)
Three tabs: Minhas Regras | Criar Alerta (wizard) | Histórico
"""
from __future__ import annotations

import reflex as rx

from bomtempo.components.skeletons import page_centered_loader
from bomtempo.core import styles as S
from bomtempo.state.alertas_state import AlertasState
from bomtempo.state.global_state import GlobalState

# ── Shared helpers ─────────────────────────────────────────────────────────────

def _section_label(text: str) -> rx.Component:
    return rx.text(
        text,
        font_family=S.FONT_TECH,
        font_size="0.65rem",
        font_weight="700",
        color=S.TEXT_MUTED,
        letter_spacing="0.18em",
        text_transform="uppercase",
    )


def _tab_btn(label: str, icon: str, value: str, current: str) -> rx.Component:
    is_active = current == value
    return rx.box(
        rx.hstack(
            rx.icon(tag=icon, size=14, color=rx.cond(is_active, S.COPPER, S.TEXT_MUTED)),
            rx.text(
                label,
                font_family=S.FONT_TECH,
                font_size="0.8rem",
                font_weight="700",
                letter_spacing="0.08em",
                color=rx.cond(is_active, "white", S.TEXT_MUTED),
            ),
            spacing="2",
            align="center",
        ),
        padding="10px 20px",
        border_radius="10px",
        bg=rx.cond(is_active, S.COPPER_GLOW, "transparent"),
        border=rx.cond(is_active, f"1px solid {S.BORDER_ACCENT}", "1px solid transparent"),
        cursor="pointer",
        transition="all 0.15s ease",
        _hover={"bg": S.COPPER_GLOW, "border_color": S.BORDER_ACCENT},
        on_click=AlertasState.set_active_tab(value),
    )


# ── Page header ───────────────────────────────────────────────────────────────

def _page_header() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(
                    "CENTRAL DE ALERTAS",
                    font_family=S.FONT_TECH,
                    font_size="1.6rem",
                    font_weight="700",
                    letter_spacing="0.1em",
                    color="white",
                    line_height="1",
                ),
                rx.text(
                    "Regras dinâmicas, alertas reativos e monitoramento contínuo de projetos",
                    font_size="0.85rem",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_BODY,
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.button(
                rx.hstack(
                    rx.icon(tag="plus", size=14),
                    rx.text("Nova Regra", font_size="12px", font_family=S.FONT_TECH, font_weight="700"),
                    spacing="2",
                    align="center",
                ),
                on_click=[AlertasState.open_wizard, AlertasState.set_active_tab("criar")],
                bg=S.COPPER,
                color="white",
                border_radius="10px",
                padding="10px 20px",
                _hover={"opacity": "0.85", "transform": "translateY(-1px)"},
                transition="all 0.15s ease",
            ),
            width="100%",
            align="center",
        ),
        # Tab bar
        rx.hstack(
            _tab_btn("Minhas Regras", "shield", "regras", AlertasState.active_tab),
            _tab_btn("Criar Alerta", "plus-circle", "criar", AlertasState.active_tab),
            _tab_btn("Histórico", "history", "historico", AlertasState.active_tab),
            spacing="2",
            padding="4px",
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius="14px",
            width="fit-content",
        ),
        spacing="4",
        width="100%",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MINHAS REGRAS
# ══════════════════════════════════════════════════════════════════════════════

def _category_badge(category: str) -> rx.Component:
    return rx.cond(
        category == "threshold",
        rx.badge("THRESHOLD", color_scheme="amber", variant="soft", size="1", font_family=S.FONT_TECH),
        rx.cond(
            category == "event",
            rx.badge("EVENTO", color_scheme="blue", variant="soft", size="1", font_family=S.FONT_TECH),
            rx.cond(
                category == "ai_custom",
                rx.badge("IA CUSTOM", color_scheme="violet", variant="soft", size="1", font_family=S.FONT_TECH),
                rx.badge("AGENDA", color_scheme="teal", variant="soft", size="1", font_family=S.FONT_TECH),
            ),
        ),
    )


def _rule_card(rule: dict) -> rx.Component:
    is_active = rule["is_active"]
    return rx.box(
        rx.hstack(
            # Left: icon + status indicator
            rx.box(
                rx.center(
                    rx.cond(
                        rule["icon"] == "trending-up",
                        rx.icon(tag="trending-up", size=18, color=rule["color"]),
                        rx.cond(
                            rule["icon"] == "zap",
                            rx.icon(tag="zap", size=18, color=rule["color"]),
                            rx.cond(
                                rule["icon"] == "sparkles",
                                rx.icon(tag="sparkles", size=18, color=rule["color"]),
                                rx.icon(tag="bell", size=18, color=rule["color"]),
                            ),
                        ),
                    ),
                    width="42px",
                    height="42px",
                    border_radius="10px",
                    bg=f"rgba(0,0,0,0.25)",
                    border=f"1px solid {rule['color']}40",
                ),
                position="relative",
            ),
            # Middle: info
            rx.vstack(
                rx.hstack(
                    rx.text(
                        rule["name"],
                        font_family=S.FONT_TECH,
                        font_size="0.95rem",
                        font_weight="700",
                        color="white",
                        letter_spacing="0.03em",
                    ),
                    _category_badge(rule["category"]),
                    spacing="2",
                    align="center",
                    flex_wrap="wrap",
                ),
                rx.text(
                    rule["description"],
                    font_size="0.75rem",
                    color=S.TEXT_MUTED,
                    line_height="1.4",
                ),
                rx.hstack(
                    rx.hstack(
                        rx.icon(tag="bell", size=10, color=S.TEXT_MUTED),
                        rx.text(rule["frequency"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                        spacing="1",
                        align="center",
                    ),
                    rx.hstack(
                        rx.icon(tag="users", size=10, color=S.TEXT_MUTED),
                        rx.text(
                            rule["recipients_count"],
                            " dest.",
                            font_size="10px",
                            color=S.TEXT_MUTED,
                            font_family=S.FONT_MONO,
                        ),
                        spacing="1",
                        align="center",
                    ),
                    rx.cond(
                        rule["last_fired_at"] != "",
                        rx.hstack(
                            rx.icon(tag="zap", size=10, color=S.COPPER),
                            rx.text(
                                "Último: ", rule["last_fired_at"],
                                font_size="10px",
                                color=S.COPPER,
                                font_family=S.FONT_MONO,
                            ),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    spacing="4",
                    flex_wrap="wrap",
                ),
                spacing="1",
                align="start",
                flex="1",
            ),
            # Right: actions
            rx.vstack(
                # Toggle switch
                rx.hstack(
                    rx.text(
                        rx.cond(is_active, "Ativo", "Inativo"),
                        font_size="10px",
                        color=rx.cond(is_active, S.PATINA, S.TEXT_MUTED),
                        font_family=S.FONT_MONO,
                        font_weight="700",
                    ),
                    rx.switch(
                        checked=is_active,
                        on_change=AlertasState.toggle_rule_active_db(rule["id"]),
                        size="1",
                        color_scheme="teal",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.tooltip(
                        rx.center(
                            rx.icon(tag="zap", size=12, color=S.COPPER),
                            width="28px",
                            height="28px",
                            border_radius="8px",
                            bg=S.COPPER_GLOW,
                            border=f"1px solid {S.BORDER_ACCENT}",
                            cursor="pointer",
                            _hover={"opacity": "0.8"},
                            on_click=AlertasState.run_rules_sweep,
                        ),
                        content="Disparar manualmente",
                    ),
                    rx.tooltip(
                        rx.center(
                            rx.icon(tag="trash-2", size=12, color=S.DANGER),
                            width="28px",
                            height="28px",
                            border_radius="8px",
                            bg=S.DANGER_BG,
                            border=f"1px solid rgba(239,68,68,0.3)",
                            cursor="pointer",
                            _hover={"opacity": "0.8"},
                            on_click=AlertasState.delete_alert_rule(rule["id"]),
                        ),
                        content="Excluir regra",
                    ),
                    spacing="2",
                ),
                spacing="2",
                align="end",
            ),
            spacing="4",
            align="start",
            width="100%",
        ),
        padding="16px 20px",
        bg=rx.cond(is_active, "rgba(8,18,16,0.7)", "rgba(8,18,16,0.4)"),
        border=rx.cond(
            is_active,
            f"1px solid {rule['color']}30",
            f"1px solid {S.BORDER_SUBTLE}",
        ),
        border_left=rx.cond(is_active, f"3px solid {rule['color']}", f"3px solid {S.BORDER_SUBTLE}"),
        border_radius="12px",
        transition="all 0.15s ease",
        opacity=rx.cond(is_active, "1", "0.6"),
    )


def _tab_regras() -> rx.Component:
    return rx.vstack(
        # Stats strip
        rx.hstack(
            rx.box(
                rx.vstack(
                    rx.text(
                        AlertasState.alert_rules.length().to_string(),
                        font_family=S.FONT_MONO,
                        font_size="1.8rem",
                        font_weight="700",
                        color=S.COPPER,
                        line_height="1",
                    ),
                    rx.text("Total de Regras", font_size="11px", color=S.TEXT_MUTED),
                    spacing="1",
                    align="center",
                ),
                flex="1",
                **{**S.GLASS_CARD, "padding": "16px", "text_align": "center"},
            ),
            rx.box(
                rx.vstack(
                    rx.text(
                        AlertasState.active_rules_count.to_string(),
                        font_family=S.FONT_MONO,
                        font_size="1.8rem",
                        font_weight="700",
                        color=S.PATINA,
                        line_height="1",
                    ),
                    rx.text("Regras Ativas", font_size="11px", color=S.TEXT_MUTED),
                    spacing="1",
                    align="center",
                ),
                flex="1",
                **{**S.GLASS_CARD, "padding": "16px", "text_align": "center"},
            ),
            rx.box(
                rx.vstack(
                    rx.text(
                        AlertasState.history_total.to_string(),
                        font_family=S.FONT_MONO,
                        font_size="1.8rem",
                        font_weight="700",
                        color="white",
                        line_height="1",
                    ),
                    rx.text("Disparos Totais", font_size="11px", color=S.TEXT_MUTED),
                    spacing="1",
                    align="center",
                ),
                flex="1",
                **{**S.GLASS_CARD, "padding": "16px", "text_align": "center"},
            ),
            spacing="3",
            width="100%",
        ),
        # Rules list
        rx.cond(
            AlertasState.is_loading_rules,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color=S.COPPER),
                    rx.text("Carregando regras...", font_size="13px", color=S.TEXT_MUTED),
                    spacing="3",
                    align="center",
                ),
                padding_y="60px",
                width="100%",
            ),
            rx.cond(
                AlertasState.alert_rules.length() == 0,
                rx.center(
                    rx.vstack(
                        rx.center(
                            rx.icon(tag="shield-off", size=40, color=S.TEXT_MUTED),
                            width="80px",
                            height="80px",
                            border_radius="20px",
                            bg=S.BG_ELEVATED,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                        ),
                        rx.text(
                            "Nenhuma regra configurada",
                            font_family=S.FONT_TECH,
                            font_size="1.1rem",
                            font_weight="700",
                            color="white",
                        ),
                        rx.text(
                            "Crie sua primeira regra de alerta para monitorar projetos automaticamente.",
                            font_size="13px",
                            color=S.TEXT_MUTED,
                            text_align="center",
                            max_width="380px",
                            line_height="1.6",
                        ),
                        rx.button(
                            rx.hstack(
                                rx.icon(tag="plus", size=14),
                                rx.text("Criar Primeira Regra", font_size="13px"),
                                spacing="2",
                                align="center",
                            ),
                            on_click=[AlertasState.open_wizard, AlertasState.set_active_tab("criar")],
                            bg=S.COPPER,
                            color="white",
                            border_radius="10px",
                            padding="10px 24px",
                            _hover={"opacity": "0.85"},
                        ),
                        spacing="3",
                        align="center",
                    ),
                    padding_y="60px",
                    width="100%",
                ),
                rx.vstack(
                    rx.foreach(AlertasState.alert_rules, _rule_card),
                    spacing="3",
                    width="100%",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CRIAR ALERTA (Wizard 3-step)
# ══════════════════════════════════════════════════════════════════════════════

def _wizard_step_indicator() -> rx.Component:
    steps = [
        ("1", "O que monitorar"),
        ("2", "Quando disparar"),
        ("3", "Quem notificar"),
    ]
    def _step(num: str, label: str) -> rx.Component:
        is_active = AlertasState.wizard_step == int(num)
        is_done = AlertasState.wizard_step > int(num)
        return rx.hstack(
            rx.center(
                rx.cond(
                    is_done,
                    rx.icon(tag="check", size=12, color="white"),
                    rx.text(num, font_size="12px", font_weight="700",
                            color=rx.cond(is_active, "white", S.TEXT_MUTED)),
                ),
                width="28px",
                height="28px",
                border_radius="50%",
                bg=rx.cond(is_done, S.PATINA, rx.cond(is_active, S.COPPER, "transparent")),
                border=rx.cond(
                    is_done, f"2px solid {S.PATINA}",
                    rx.cond(is_active, f"2px solid {S.COPPER}", f"2px solid {S.BORDER_SUBTLE}")
                ),
            ),
            rx.text(
                label,
                font_size="12px",
                font_family=S.FONT_TECH,
                font_weight="700",
                color=rx.cond(is_active, "white", S.TEXT_MUTED),
                display=["none", "none", "block"],
            ),
            spacing="2",
            align="center",
        )

    return rx.hstack(
        _step("1", "O que monitorar"),
        rx.box(height="1px", flex="1", bg=S.BORDER_SUBTLE, margin_x="4px"),
        _step("2", "Quando disparar"),
        rx.box(height="1px", flex="1", bg=S.BORDER_SUBTLE, margin_x="4px"),
        _step("3", "Quem notificar"),
        width="100%",
        align="center",
        padding="16px 24px",
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="12px",
    )


def _category_option(value: str, label: str, desc: str, icon: str, color: str) -> rx.Component:
    is_sel = AlertasState.wizard_category == value
    return rx.box(
        rx.hstack(
            rx.center(
                rx.icon(tag=icon, size=16, color=color),
                width="36px",
                height="36px",
                border_radius="8px",
                bg=f"rgba(0,0,0,0.2)",
                border=f"1px solid {color}40",
                flex_shrink="0",
            ),
            rx.vstack(
                rx.text(label, font_family=S.FONT_TECH, font_size="0.85rem",
                        font_weight="700", color="white"),
                rx.text(desc, font_size="11px", color=S.TEXT_MUTED, line_height="1.3"),
                spacing="0",
                align="start",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        padding="12px 16px",
        border_radius="10px",
        border=rx.cond(is_sel, f"2px solid {color}", f"1px solid {S.BORDER_SUBTLE}"),
        bg=rx.cond(is_sel, f"rgba(0,0,0,0.3)", S.BG_INPUT),
        cursor="pointer",
        transition="all 0.15s ease",
        _hover={"border_color": color},
        on_click=AlertasState.set_wizard_category(value),
    )


def _wizard_step1() -> rx.Component:
    """Step 1: O que monitorar."""
    return rx.vstack(
        # Name + description
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    _section_label("NOME DA REGRA"),
                    rx.input(
                        default_value=AlertasState.wizard_name,
                        on_blur=AlertasState.set_wizard_name,
                        placeholder="Ex: Alerta de atraso crítico",
                        bg=S.BG_INPUT,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        color="white",
                        border_radius="8px",
                        _focus={"border_color": S.COPPER, "outline": "none"},
                        _placeholder={"color": S.TEXT_MUTED},
                        width="100%",
                    ),
                    spacing="1",
                    width="100%",
                ),
                rx.vstack(
                    _section_label("CONTRATOS (vazio = todos)"),
                    rx.input(
                        default_value=AlertasState.wizard_contracts,
                        on_blur=AlertasState.set_wizard_contracts,
                        placeholder="CT-001, CT-002 ou vazio para todos",
                        bg=S.BG_INPUT,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        color="white",
                        border_radius="8px",
                        _focus={"border_color": S.COPPER, "outline": "none"},
                        _placeholder={"color": S.TEXT_MUTED},
                        width="100%",
                    ),
                    spacing="1",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            rx.vstack(
                _section_label("DESCRIÇÃO (opcional)"),
                rx.input(
                    default_value=AlertasState.wizard_description,
                    on_blur=AlertasState.set_wizard_description,
                    placeholder="Descreva quando esse alerta deve disparar...",
                    bg=S.BG_INPUT,
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    color="white",
                    border_radius="8px",
                    _focus={"border_color": S.COPPER, "outline": "none"},
                    _placeholder={"color": S.TEXT_MUTED},
                    width="100%",
                ),
                spacing="1",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        rx.divider(color_scheme="gray", opacity="0.15"),
        # Category selection
        _section_label("TIPO DE ALERTA"),
        rx.grid(
            _category_option("threshold", "Threshold / Métrica", "Dispara quando uma métrica ultrapassa um limite", "trending-up", S.COPPER),
            _category_option("event", "Baseado em Evento", "Dispara quando um evento específico ocorre", "zap", S.PATINA),
            _category_option("ai_custom", "IA em Linguagem Natural", "Descreva em português e a IA interpreta a regra", "sparkles", "#8B5CF6"),
            columns="3",
            spacing="3",
            width="100%",
        ),
        # Sub-options based on category
        rx.cond(
            AlertasState.wizard_category == "threshold",
            rx.vstack(
                rx.divider(color_scheme="gray", opacity="0.15"),
                _section_label("CONFIGURAR THRESHOLD"),
                rx.grid(
                    rx.vstack(
                        _section_label("MÉTRICA"),
                        rx.select.root(
                            rx.select.trigger(width="100%"),
                            rx.select.content(
                                rx.select.item("Desvio de Prazo (%)", value="desvio_prazo_pct"),
                                rx.select.item("Estouro de Orçamento (%)", value="budget_overage_pct"),
                                rx.select.item("Score de Risco", value="risk_score"),
                                rx.select.item("Horas sem RDO", value="rdo_horas_sem_submit"),
                                rx.select.item("Queda de Produção (%)", value="producao_queda_pct"),
                                bg=S.BG_ELEVATED,
                                border=f"1px solid {S.BORDER_SUBTLE}",
                            ),
                            value=AlertasState.wizard_metric,
                            on_change=AlertasState.set_wizard_metric,
                            width="100%",
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    rx.vstack(
                        _section_label("OPERADOR"),
                        rx.select.root(
                            rx.select.trigger(width="100%"),
                            rx.select.content(
                                rx.select.item("Maior que (>)", value="gt"),
                                rx.select.item("Maior ou igual (≥)", value="gte"),
                                rx.select.item("Menor que (<)", value="lt"),
                                rx.select.item("Menor ou igual (≤)", value="lte"),
                                bg=S.BG_ELEVATED,
                                border=f"1px solid {S.BORDER_SUBTLE}",
                            ),
                            value=AlertasState.wizard_operator,
                            on_change=AlertasState.set_wizard_operator,
                            width="100%",
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    rx.vstack(
                        _section_label("VALOR LIMITE"),
                        rx.input(
                            default_value=AlertasState.wizard_threshold,
                            on_blur=AlertasState.set_wizard_threshold,
                            placeholder="Ex: 10",
                            type="number",
                            bg=S.BG_INPUT,
                            border=f"1px solid {S.BORDER_SUBTLE}",
                            color="white",
                            border_radius="8px",
                            _focus={"border_color": S.COPPER, "outline": "none"},
                            _placeholder={"color": S.TEXT_MUTED},
                            width="100%",
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    columns="3",
                    spacing="3",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
        ),
        rx.cond(
            AlertasState.wizard_category == "event",
            rx.vstack(
                rx.divider(color_scheme="gray", opacity="0.15"),
                _section_label("TIPO DE EVENTO"),
                rx.select.root(
                    rx.select.trigger(width="100%"),
                    rx.select.content(
                        rx.select.item("RDO Submetido", value="rdo_submitted"),
                        rx.select.item("Documento Crítico (IA)", value="document_critical_alert"),
                        rx.select.item("Cronograma Atualizado", value="cronograma_updated"),
                        rx.select.item("Financeiro Atualizado", value="financeiro_updated"),
                        bg=S.BG_ELEVATED,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                    ),
                    value=AlertasState.wizard_event_type,
                    on_change=AlertasState.set_wizard_event_type,
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
        ),
        rx.cond(
            AlertasState.wizard_category == "ai_custom",
            rx.vstack(
                rx.divider(color_scheme="gray", opacity="0.15"),
                _section_label("DESCREVA A REGRA EM PORTUGUÊS"),
                rx.text_area(
                    default_value=AlertasState.wizard_natural_language,
                    on_blur=AlertasState.set_wizard_natural_language,
                    placeholder='Ex: "Notifique quando o desvio de prazo for maior que 15% ou quando não houver RDO por mais de 48 horas"',
                    min_height="90px",
                    bg=S.BG_INPUT,
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    color="white",
                    border_radius="8px",
                    _focus={"border_color": "#8B5CF6", "outline": "none"},
                    _placeholder={"color": S.TEXT_MUTED},
                    resize="vertical",
                    width="100%",
                ),
                rx.button(
                    rx.cond(
                        AlertasState.is_interpreting_rule,
                        rx.hstack(
                            rx.spinner(size="1", color="white"),
                            rx.text("Interpretando...", font_size="12px"),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.icon(tag="sparkles", size=13),
                            rx.text("Interpretar com IA", font_size="12px"),
                            spacing="2",
                            align="center",
                        ),
                    ),
                    on_click=AlertasState.interpret_ai_rule,
                    disabled=AlertasState.is_interpreting_rule,
                    bg="#8B5CF6",
                    color="white",
                    border_radius="8px",
                    padding="8px 16px",
                    _hover={"opacity": "0.85"},
                    font_family=S.FONT_TECH,
                    font_weight="700",
                ),
                # AI interpretation result
                rx.cond(
                    AlertasState.ai_rule_interpretation != "",
                    rx.box(
                        rx.hstack(
                            rx.icon(tag="check-circle", size=14, color=S.PATINA),
                            rx.text(
                                "INTERPRETAÇÃO DA IA",
                                font_size="10px",
                                font_weight="700",
                                letter_spacing="0.1em",
                                color=S.PATINA,
                                font_family=S.FONT_TECH,
                            ),
                            spacing="2",
                            align="center",
                            margin_bottom="8px",
                        ),
                        rx.text(
                            AlertasState.ai_rule_interpretation,
                            font_size="12px",
                            color=S.TEXT_PRIMARY,
                            line_height="1.6",
                        ),
                        padding="12px 16px",
                        bg=S.PATINA_GLOW,
                        border=f"1px solid rgba(42,157,143,0.3)",
                        border_radius="8px",
                        width="100%",
                    ),
                ),
                spacing="3",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )


def _wizard_step2() -> rx.Component:
    """Step 2: Quando disparar."""
    freq_options = [
        ("always", "Sempre que detectado", "Dispara toda vez que a condição for verdadeira"),
        ("daily", "Uma vez por dia", "Máximo 1 disparo por dia por contrato"),
        ("weekly", "Uma vez por semana", "Máximo 1 disparo por semana"),
        ("monthly", "Uma vez por mês", "Relatório mensal consolidado"),
    ]
    def _freq_opt(value: str, label: str, desc: str) -> rx.Component:
        is_sel = AlertasState.wizard_frequency == value
        return rx.box(
            rx.hstack(
                rx.box(
                    width="16px",
                    height="16px",
                    border_radius="50%",
                    bg=rx.cond(is_sel, S.COPPER, "transparent"),
                    border=rx.cond(is_sel, f"2px solid {S.COPPER}", f"2px solid {S.BORDER_SUBTLE}"),
                    flex_shrink="0",
                    transition="all 0.1s ease",
                ),
                rx.vstack(
                    rx.text(label, font_size="13px", font_weight="600", color="white"),
                    rx.text(desc, font_size="11px", color=S.TEXT_MUTED),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
                width="100%",
            ),
            padding="12px 16px",
            border_radius="10px",
            border=rx.cond(is_sel, f"1px solid {S.COPPER}", f"1px solid {S.BORDER_SUBTLE}"),
            bg=rx.cond(is_sel, S.COPPER_GLOW, S.BG_INPUT),
            cursor="pointer",
            transition="all 0.15s ease",
            on_click=AlertasState.set_wizard_frequency(value),
        )

    return rx.vstack(
        _section_label("FREQUÊNCIA DE DISPARO"),
        rx.vstack(
            *[_freq_opt(v, l, d) for v, l, d in freq_options],
            spacing="2",
            width="100%",
        ),
        rx.divider(color_scheme="gray", opacity="0.15"),
        rx.vstack(
            _section_label("COOLDOWN (horas mínimas entre disparos)"),
            rx.hstack(
                rx.input(
                    default_value=AlertasState.wizard_cooldown_hours,
                    on_blur=AlertasState.set_wizard_cooldown_hours,
                    type="number",
                    placeholder="24",
                    bg=S.BG_INPUT,
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    color="white",
                    border_radius="8px",
                    _focus={"border_color": S.COPPER, "outline": "none"},
                    width="120px",
                ),
                rx.text(
                    "horas",
                    font_size="13px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_MONO,
                ),
                spacing="3",
                align="center",
            ),
            rx.text(
                "Evita spam: mesmo que a condição persista, o alerta só dispara novamente após o cooldown.",
                font_size="11px",
                color=S.TEXT_MUTED,
                line_height="1.5",
            ),
            spacing="2",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def _wizard_recipient_chip(r: dict) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.text(r["name"].to(str)[:1].upper(), font_size="11px", font_weight="700", color="white"),
            width="24px",
            height="24px",
            border_radius="50%",
            bg=S.COPPER,
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(r["name"], font_size="12px", color="white", font_weight="600", line_height="1"),
            rx.text(r["email"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, line_height="1"),
            spacing="0",
            align="start",
        ),
        rx.icon(tag=
            "x",
            size=12,
            color=S.TEXT_MUTED,
            cursor="pointer",
            _hover={"color": S.DANGER},
            on_click=AlertasState.wizard_remove_recipient(r["email"]),
            margin_left="auto",
        ),
        spacing="2",
        align="center",
        padding="8px 12px",
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="8px",
        width="100%",
    )


def _wizard_step3() -> rx.Component:
    """Step 3: Quem notificar."""
    return rx.vstack(
        _section_label("ADICIONAR DESTINATÁRIO"),
        rx.hstack(
            rx.input(
                default_value=AlertasState.wizard_recipient_name,
                on_blur=AlertasState.set_wizard_recipient_name,
                placeholder="Nome",
                bg=S.BG_INPUT,
                border=f"1px solid {S.BORDER_SUBTLE}",
                color="white",
                border_radius="8px",
                _focus={"border_color": S.COPPER, "outline": "none"},
                _placeholder={"color": S.TEXT_MUTED},
                width="160px",
            ),
            rx.input(
                default_value=AlertasState.wizard_recipient_email,
                on_blur=AlertasState.set_wizard_recipient_email,
                placeholder="email@exemplo.com",
                type="email",
                bg=S.BG_INPUT,
                border=f"1px solid {S.BORDER_SUBTLE}",
                color="white",
                border_radius="8px",
                _focus={"border_color": S.COPPER, "outline": "none"},
                _placeholder={"color": S.TEXT_MUTED},
                flex="1",
            ),
            rx.button(
                rx.icon(tag="user-plus", size=14),
                on_click=AlertasState.wizard_add_recipient,
                bg=S.COPPER,
                color="white",
                border_radius="8px",
                padding="0 14px",
                height="36px",
                _hover={"opacity": "0.85"},
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        rx.cond(
            AlertasState.wizard_recipients.length() > 0,
            rx.vstack(
                _section_label("DESTINATÁRIOS CONFIGURADOS"),
                rx.foreach(AlertasState.wizard_recipients, _wizard_recipient_chip),
                spacing="2",
                width="100%",
            ),
            rx.box(
                rx.vstack(
                    rx.icon(tag="inbox", size=24, color=S.TEXT_MUTED),
                    rx.text(
                        "Nenhum destinatário adicionado ainda",
                        font_size="12px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="2",
                    align="center",
                ),
                padding="24px",
                border=f"1px dashed {S.BORDER_SUBTLE}",
                border_radius="10px",
                width="100%",
                text_align="center",
            ),
        ),
        rx.box(
            rx.hstack(
                rx.icon(tag="info", size=13, color=S.COPPER),
                rx.text(
                    "Os e-mails recebidos incluem contexto do projeto, valor atual da métrica e recomendação da IA.",
                    font_size="11px",
                    color=S.TEXT_MUTED,
                    line_height="1.4",
                ),
                spacing="2",
                align="start",
            ),
            padding="10px 14px",
            bg=S.COPPER_GLOW,
            border=f"1px solid {S.BORDER_ACCENT}",
            border_radius="8px",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def _tab_criar() -> rx.Component:
    return rx.vstack(
        _wizard_step_indicator(),
        rx.box(
            rx.cond(AlertasState.wizard_step == 1, _wizard_step1()),
            rx.cond(AlertasState.wizard_step == 2, _wizard_step2()),
            rx.cond(AlertasState.wizard_step == 3, _wizard_step3()),
            width="100%",
            **{**S.GLASS_CARD, "padding": "24px"},
        ),
        # Navigation buttons
        rx.hstack(
            rx.cond(
                AlertasState.wizard_step > 1,
                rx.button(
                    rx.hstack(
                        rx.icon(tag="arrow-left", size=14),
                        rx.text("Voltar", font_size="13px"),
                        spacing="2",
                        align="center",
                    ),
                    on_click=AlertasState.wizard_prev,
                    variant="ghost",
                    color=S.TEXT_MUTED,
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    border_radius="10px",
                    padding="10px 20px",
                    _hover={"color": "white", "border_color": S.BORDER_HIGHLIGHT},
                ),
                rx.box(),
            ),
            rx.spacer(),
            # Save button (only on step 3)
            rx.cond(
                AlertasState.wizard_step == 3,
                rx.button(
                    rx.cond(
                        AlertasState.is_saving_rule,
                        rx.hstack(
                            rx.spinner(size="1", color="white"),
                            rx.text("Salvando...", font_size="13px"),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.icon(tag="save", size=14),
                            rx.text("Salvar Regra", font_size="13px", font_family=S.FONT_TECH, font_weight="700"),
                            spacing="2",
                            align="center",
                        ),
                    ),
                    on_click=AlertasState.save_alert_rule,
                    disabled=AlertasState.is_saving_rule,
                    bg=S.PATINA,
                    color="white",
                    border_radius="10px",
                    padding="10px 24px",
                    _hover={"opacity": "0.85"},
                ),
                rx.button(
                    rx.hstack(
                        rx.text("Próximo", font_size="13px", font_family=S.FONT_TECH, font_weight="700"),
                        rx.icon(tag="arrow-right", size=14),
                        spacing="2",
                        align="center",
                    ),
                    on_click=AlertasState.wizard_next,
                    bg=S.COPPER,
                    color="white",
                    border_radius="10px",
                    padding="10px 24px",
                    _hover={"opacity": "0.85"},
                ),
            ),
            width="100%",
            align="center",
        ),
        # Feedback message
        rx.cond(
            AlertasState.rule_form_message != "",
            rx.hstack(
                rx.icon(tag=
                    rx.cond(AlertasState.rule_form_is_error, "x-circle", "check-circle"),
                    size=14,
                    color=rx.cond(AlertasState.rule_form_is_error, S.DANGER, S.PATINA),
                ),
                rx.text(
                    AlertasState.rule_form_message,
                    font_size="13px",
                    color=rx.cond(AlertasState.rule_form_is_error, S.DANGER, S.PATINA),
                ),
                spacing="2",
                align="center",
                padding="12px 16px",
                bg=rx.cond(AlertasState.rule_form_is_error, S.DANGER_BG, S.PATINA_GLOW),
                border=rx.cond(
                    AlertasState.rule_form_is_error,
                    "1px solid rgba(239,68,68,0.3)",
                    "1px solid rgba(42,157,143,0.3)",
                ),
                border_radius="10px",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HISTÓRICO
# ══════════════════════════════════════════════════════════════════════════════

def _history_row(h: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(h["timestamp"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
        ),
        rx.table.cell(
            rx.hstack(
                rx.box(
                    width="8px",
                    height="8px",
                    border_radius="50%",
                    bg=h["alert_color"],
                    flex_shrink="0",
                ),
                rx.text(h["alert_label"], font_size="12px", color="white", font_weight="500"),
                spacing="2",
                align="center",
            ),
        ),
        rx.table.cell(
            rx.badge(h["contract"], color_scheme="gray", variant="soft", size="1", font_family=S.FONT_MONO),
        ),
        rx.table.cell(
            rx.text(h["message"], font_size="11px", color=S.TEXT_MUTED, line_height="1.4"),
            max_width="400px",
        ),
        rx.table.cell(
            rx.cond(
                h["is_read"],
                rx.badge("Lido", color_scheme="gray", variant="soft", size="1"),
                rx.badge("Novo", color_scheme="amber", variant="soft", size="1"),
            ),
        ),
    )


def _tab_historico() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AlertasState.history.length() == 0,
            rx.center(
                rx.vstack(
                    rx.icon(tag="inbox", size=32, color=S.TEXT_MUTED),
                    rx.text("Nenhum disparo registrado ainda", font_size="13px", color=S.TEXT_MUTED),
                    spacing="2",
                    align="center",
                ),
                padding_y="48px",
                width="100%",
            ),
            rx.vstack(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            *[rx.table.column_header_cell(
                                col,
                                style={"fontSize": "10px", "color": S.TEXT_MUTED,
                                       "letterSpacing": "0.1em", "fontFamily": S.FONT_TECH,
                                       "background": S.BG_SURFACE},
                            ) for col in ["DATA/HORA", "TIPO", "CONTRATO", "MENSAGEM", "STATUS"]],
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(AlertasState.history, _history_row),
                    ),
                    width="100%",
                    variant="ghost",
                    size="1",
                    style={"background": "transparent"},
                ),
                # Pagination
                rx.hstack(
                    rx.text(
                        AlertasState.history_page_info,
                        font_size="12px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_MONO,
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="chevron-left", size=14),
                        on_click=AlertasState.history_prev,
                        disabled=~AlertasState.history_has_prev,
                        variant="ghost",
                        color=S.TEXT_MUTED,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="8px",
                        size="2",
                        _hover={"color": "white"},
                    ),
                    rx.button(
                        rx.icon(tag="chevron-right", size=14),
                        on_click=AlertasState.history_next,
                        disabled=~AlertasState.history_has_next,
                        variant="ghost",
                        color=S.TEXT_MUTED,
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="8px",
                        size="2",
                        _hover={"color": "white"},
                    ),
                    spacing="2",
                    align="center",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
        **{**S.GLASS_CARD, "padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def alertas_page() -> rx.Component:
    return rx.cond(
        AlertasState.is_loading,
        page_centered_loader("Carregando alertas..."),
        rx.vstack(
            _page_header(),
            rx.cond(AlertasState.active_tab == "regras", _tab_regras()),
            rx.cond(AlertasState.active_tab == "criar", _tab_criar()),
            rx.cond(AlertasState.active_tab == "historico", _tab_historico()),
            spacing="4",
            width="100%",
            padding_bottom="40px",
            class_name="animate-enter",
        ),
    )
