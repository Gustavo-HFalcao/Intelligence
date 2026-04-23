"""
Relatórios — Bomtempo Intelligence (Enterprise Revamp)
Rich configurator: scope, period, stage, recipients, agendamento, mode toggle.
"""

import reflex as rx

from bomtempo.core import styles as S
from bomtempo.state.global_state import GlobalState
from bomtempo.state.relatorios_state import RelatoriosState


# ── Helpers ────────────────────────────────────────────────────────────────────

def _label(text: str) -> rx.Component:
    return rx.text(
        text,
        font_family=S.FONT_TECH,
        font_size="0.65rem",
        font_weight="700",
        color=S.TEXT_MUTED,
        letter_spacing="0.14em",
        text_transform="uppercase",
    )


def _section_card(*children, title: str = "", icon: str = "", accent: str = S.COPPER,
                  **kwargs) -> rx.Component:
    header = rx.hstack(
        rx.center(
            rx.icon(tag=icon, size=15, color=accent),
            width="30px",
            height="30px",
            border_radius="8px",
            bg=f"rgba(0,0,0,0.2)",
            border=f"1px solid {accent}30",
        ),
        rx.text(
            title,
            font_family=S.FONT_TECH,
            font_size="0.8rem",
            font_weight="700",
            letter_spacing="0.1em",
            color="white",
            text_transform="uppercase",
        ),
        spacing="2",
        align="center",
        margin_bottom="12px",
    ) if title else rx.box()

    return rx.vstack(
        header,
        *children,
        spacing="3",
        width="100%",
        **{**S.GLASS_CARD, "padding": "20px", **kwargs},
    )


# ── Page header ───────────────────────────────────────────────────────────────

def _page_header() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(
                "CENTRAL DE RELATÓRIOS",
                font_family=S.FONT_TECH,
                font_size="1.6rem",
                font_weight="700",
                letter_spacing="0.1em",
                color="white",
                line_height="1",
            ),
            rx.text(
                "Geração enterprise com IA, dados reais e exportação PDF profissional",
                font_size="0.85rem",
                color=S.TEXT_MUTED,
                font_family=S.FONT_BODY,
            ),
            spacing="1",
            align="start",
        ),
        rx.spacer(),
        rx.hstack(
            rx.icon(tag="file-text", size=14, color=S.COPPER),
            rx.text(
                RelatoriosState.reports_history.length().to_string() + " gerados",
                font_size="12px",
                color=S.TEXT_MUTED,
                font_family=S.FONT_MONO,
            ),
            spacing="2",
            align="center",
            padding="8px 16px",
            border=f"1px solid {S.BORDER_SUBTLE}",
            border_radius="8px",
            bg=S.BG_INPUT,
        ),
        width="100%",
        align="center",
    )


# ── Contract selector ─────────────────────────────────────────────────────────

def _contract_selector() -> rx.Component:
    return _section_card(
        rx.select.root(
            rx.select.trigger(
                placeholder="Selecionar contrato para gerar relatório...",
                width="100%",
            ),
            rx.select.content(
                rx.foreach(
                    GlobalState.contratos_list,
                    lambda c: rx.select.item(c["contrato"], value=c["contrato"]),
                ),
                bg=S.BG_ELEVATED,
                border=f"1px solid {S.BORDER_SUBTLE}",
            ),
            value=RelatoriosState.selected_contrato,
            on_change=[
                RelatoriosState.set_selected_contrato,
                GlobalState.set_obras_selected_contract,
            ],
            width="100%",
        ),
        title="Contrato",
        icon="building-2",
    )


# ── Mode toggle ───────────────────────────────────────────────────────────────

def _mode_btn(value: str, label: str, icon: str, desc: str, color: str) -> rx.Component:
    is_active = RelatoriosState.generation_mode == value
    return rx.box(
        rx.vstack(
            rx.center(
                rx.icon(tag=icon, size=18, color=color),
                width="40px",
                height="40px",
                border_radius="10px",
                bg=rx.cond(is_active, f"rgba(0,0,0,0.3)", S.BG_INPUT),
                border=rx.cond(is_active, f"1px solid {color}60", f"1px solid {S.BORDER_SUBTLE}"),
            ),
            rx.text(
                label,
                font_family=S.FONT_TECH,
                font_size="0.75rem",
                font_weight="700",
                color=rx.cond(is_active, "white", S.TEXT_MUTED),
                text_align="center",
                letter_spacing="0.05em",
            ),
            rx.text(
                desc,
                font_size="10px",
                color=S.TEXT_MUTED,
                text_align="center",
                line_height="1.3",
                display=["none", "none", "block"],
            ),
            spacing="2",
            align="center",
        ),
        padding="14px 12px",
        border_radius="12px",
        border=rx.cond(is_active, f"2px solid {color}", f"1px solid {S.BORDER_SUBTLE}"),
        bg=rx.cond(is_active, f"rgba(0,0,0,0.2)", "transparent"),
        cursor="pointer",
        transition="all 0.15s ease",
        _hover={"border_color": color},
        on_click=RelatoriosState.set_generation_mode(value),
        flex="1",
        text_align="center",
    )


def _mode_selector() -> rx.Component:
    return _section_card(
        rx.hstack(
            _mode_btn("ia_mcp", "IA Enterprise", "sparkles", "Dados reais via execute_sql", S.PATINA),
            _mode_btn("static", "Dossier Estático", "file-text", "Layout estruturado fixo", S.COPPER),
            _mode_btn("custom", "Customizado", "wand-sparkles", "Prompt livre em linguagem natural", "#8B5CF6"),
            spacing="3",
            width="100%",
        ),
        title="Modo de Geração",
        icon="settings-2",
    )


# ── Enterprise configurator ────────────────────────────────────────────────────

def _scope_toggle(label: str, icon: str, value: bool, setter) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.icon(tag=icon, size=13, color=rx.cond(value, S.PATINA, S.TEXT_MUTED)),
            width="28px",
            height="28px",
            border_radius="6px",
            bg=rx.cond(value, S.PATINA_GLOW, S.BG_INPUT),
            border=rx.cond(value, f"1px solid rgba(42,157,143,0.3)", f"1px solid {S.BORDER_SUBTLE}"),
            transition="all 0.15s ease",
        ),
        rx.text(
            label,
            font_size="12px",
            font_weight="600",
            color=rx.cond(value, "white", S.TEXT_MUTED),
            flex="1",
        ),
        rx.switch(
            checked=value,
            on_change=setter,
            size="1",
            color_scheme="teal",
        ),
        spacing="2",
        align="center",
        width="100%",
        padding="8px 12px",
        border_radius="8px",
        bg=rx.cond(value, "rgba(42,157,143,0.05)", "transparent"),
        border=rx.cond(value, "1px solid rgba(42,157,143,0.15)", "1px solid transparent"),
        transition="all 0.15s ease",
    )


def _configurator() -> rx.Component:
    return rx.cond(
        RelatoriosState.generation_mode != "static",
        rx.hstack(
            # Left: Scope checkboxes
            _section_card(
                rx.grid(
                    _scope_toggle("Cronograma", "calendar", RelatoriosState.escopo_cronograma, RelatoriosState.set_escopo_cronograma),
                    _scope_toggle("Financeiro", "dollar-sign", RelatoriosState.escopo_financeiro, RelatoriosState.set_escopo_financeiro),
                    _scope_toggle("RDOs", "clipboard", RelatoriosState.escopo_rdos, RelatoriosState.set_escopo_rdos),
                    _scope_toggle("Documentos", "file-search", RelatoriosState.escopo_documentos, RelatoriosState.set_escopo_documentos),
                    _scope_toggle("Equipe", "users", RelatoriosState.escopo_equipe, RelatoriosState.set_escopo_equipe),
                    _scope_toggle("Alertas", "bell", RelatoriosState.escopo_alertas, RelatoriosState.set_escopo_alertas),
                    columns="2",
                    spacing="2",
                    width="100%",
                ),
                title="Escopo do Relatório",
                icon="layout-list",
                flex="1",
            ),
            # Right: Period + stage
            rx.vstack(
                _section_card(
                    rx.grid(
                        rx.vstack(
                            _label("INÍCIO"),
                            rx.input(
                                value=RelatoriosState.periodo_inicio,
                                on_change=RelatoriosState.set_periodo_inicio,
                                type="date",
                                bg=S.BG_INPUT,
                                border=f"1px solid {S.BORDER_SUBTLE}",
                                color="white",
                                border_radius="8px",
                                _focus={"border_color": S.COPPER, "outline": "none"},
                                width="100%",
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        rx.vstack(
                            _label("FIM"),
                            rx.input(
                                value=RelatoriosState.periodo_fim,
                                on_change=RelatoriosState.set_periodo_fim,
                                type="date",
                                bg=S.BG_INPUT,
                                border=f"1px solid {S.BORDER_SUBTLE}",
                                color="white",
                                border_radius="8px",
                                _focus={"border_color": S.COPPER, "outline": "none"},
                                width="100%",
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        columns="2",
                        spacing="3",
                        width="100%",
                    ),
                    title="Período",
                    icon="calendar-range",
                ),
                _section_card(
                    rx.vstack(
                        _label("ETAPA ESPECÍFICA (opcional)"),
                        rx.input(
                            value=RelatoriosState.etapa_especifica,
                            on_change=RelatoriosState.set_etapa_especifica,
                            placeholder="Ex: Fundações, Estrutura, Acabamentos...",
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
                    title="Etapa",
                    icon="layers",
                ),
                spacing="3",
                flex="1",
            ),
            spacing="3",
            width="100%",
            align_items="start",
        ),
    )


# ── Abordagem selector (shown for IA modes) ───────────────────────────────────

def _abordagem_card(value: str, label: str, desc: str, icon: str) -> rx.Component:
    is_sel = RelatoriosState.selected_abordagem == value
    return rx.box(
        rx.hstack(
            rx.center(
                rx.icon(tag=icon, size=14, color=rx.cond(is_sel, S.PATINA, S.TEXT_MUTED)),
                width="30px",
                height="30px",
                border_radius="8px",
                bg=rx.cond(is_sel, S.PATINA_GLOW, S.BG_INPUT),
                border=rx.cond(is_sel, "1px solid rgba(42,157,143,0.4)", f"1px solid {S.BORDER_SUBTLE}"),
                flex_shrink="0",
            ),
            rx.vstack(
                rx.text(label, font_size="12px", font_weight="700",
                        color=rx.cond(is_sel, "white", S.TEXT_MUTED)),
                rx.text(desc, font_size="10px", color=S.TEXT_MUTED, line_height="1.3"),
                spacing="0",
                align="start",
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="10px 12px",
        border_radius="8px",
        border=rx.cond(is_sel, "1px solid rgba(42,157,143,0.3)", f"1px solid {S.BORDER_SUBTLE}"),
        bg=rx.cond(is_sel, "rgba(42,157,143,0.05)", "transparent"),
        cursor="pointer",
        transition="all 0.15s ease",
        on_click=RelatoriosState.set_selected_abordagem(value),
    )


def _abordagem_selector() -> rx.Component:
    return rx.cond(
        RelatoriosState.generation_mode != "static",
        _section_card(
            rx.grid(
                _abordagem_card("estrategica", "Estratégica", "Para diretoria e investidores", "trending-up"),
                _abordagem_card("analitica", "Analítica", "Análise financeira detalhada", "bar-chart-2"),
                _abordagem_card("descritiva", "Descritiva", "Auditoria técnica formal", "clipboard-list"),
                _abordagem_card("operacional", "Operacional", "Campo e disciplinas", "hard-hat"),
                columns="2",
                spacing="2",
                width="100%",
            ),
            title="Abordagem",
            icon="brain",
            accent=S.PATINA,
        ),
    )


# ── Recipients ────────────────────────────────────────────────────────────────

def _recipient_chip(r: dict) -> rx.Component:
    return rx.hstack(
        rx.center(
            rx.text(
                r["name"].to(str)[:1].upper(),
                font_size="10px",
                font_weight="700",
                color="white",
            ),
            width="22px",
            height="22px",
            border_radius="50%",
            bg=S.COPPER,
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(r["name"], font_size="11px", font_weight="600", color="white", line_height="1"),
            rx.text(r["email"], font_size="10px", color=S.TEXT_MUTED, font_family=S.FONT_MONO, line_height="1"),
            spacing="0",
            align="start",
        ),
        rx.icon(tag=
            "x",
            size=11,
            color=S.TEXT_MUTED,
            cursor="pointer",
            _hover={"color": S.DANGER},
            on_click=RelatoriosState.remove_recipient(r["email"]),
            margin_left="auto",
        ),
        spacing="2",
        align="center",
        padding="6px 10px",
        bg=S.BG_ELEVATED,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="6px",
        flex="1 1 200px",
    )


def _recipients_section() -> rx.Component:
    return _section_card(
        rx.hstack(
            rx.input(
                value=RelatoriosState.new_recipient_name,
                on_change=RelatoriosState.set_new_recipient_name,
                placeholder="Nome",
                bg=S.BG_INPUT,
                border=f"1px solid {S.BORDER_SUBTLE}",
                color="white",
                border_radius="8px",
                _focus={"border_color": S.COPPER, "outline": "none"},
                _placeholder={"color": S.TEXT_MUTED},
                width="150px",
            ),
            rx.input(
                value=RelatoriosState.new_recipient_email,
                on_change=RelatoriosState.set_new_recipient_email,
                placeholder="email@empresa.com",
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
                on_click=RelatoriosState.add_recipient,
                bg=S.COPPER,
                color="white",
                border_radius="8px",
                padding="0 12px",
                height="36px",
                _hover={"opacity": "0.85"},
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        rx.cond(
            RelatoriosState.report_recipients.length() > 0,
            rx.flex(
                rx.foreach(RelatoriosState.report_recipients, _recipient_chip),
                flex_wrap="wrap",
                gap="2",
                width="100%",
            ),
            rx.text(
                "Nenhum destinatário — o PDF ficará disponível apenas no histórico",
                font_size="11px",
                color=S.TEXT_MUTED,
                font_style="italic",
            ),
        ),
        title="Destinatários (e-mail)",
        icon="send",
    )


# ── Custom prompt (shown when mode = "custom") ────────────────────────────────

def _custom_prompt_section() -> rx.Component:
    return rx.cond(
        RelatoriosState.generation_mode == "custom",
        _section_card(
            rx.text_area(
                value=RelatoriosState.custom_prompt,
                on_change=RelatoriosState.set_custom_prompt,
                placeholder='Ex: "Relatório focado nos riscos financeiros para apresentar ao banco financiador, com ênfase nas variações orçamentárias e projeções de término..."',
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
            title="Prompt Personalizado",
            icon="wand-sparkles",
            border_top=f"2px solid #8B5CF6",
        ),
    )


# ── Generate button ───────────────────────────────────────────────────────────

def _generate_button() -> rx.Component:
    return rx.box(
        rx.hstack(
            # Left: status / streaming indicator
            rx.cond(
                RelatoriosState.is_streaming,
                rx.hstack(
                    rx.spinner(size="1", color=S.PATINA),
                    rx.text(
                        "IA gerando relatório em tempo real...",
                        font_size="12px",
                        color=S.PATINA,
                        font_style="italic",
                    ),
                    rx.box(
                        width="6px",
                        height="6px",
                        border_radius="50%",
                        bg=S.PATINA,
                        class_name="pulse-dot",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    RelatoriosState.selected_contrato == "",
                    rx.hstack(
                        rx.icon(tag="alert-circle", size=14, color=S.WARNING),
                        rx.text(
                            "Selecione um contrato antes de gerar",
                            font_size="12px",
                            color=S.WARNING,
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.box(),
                ),
            ),
            rx.spacer(),
            # Right: generate button
            rx.button(
                rx.cond(
                    RelatoriosState.is_generating,
                    rx.hstack(
                        rx.spinner(size="1", color="white"),
                        rx.text(
                            rx.cond(
                                RelatoriosState.generation_mode == "static",
                                "Gerando dossier...",
                                "Gerando com IA...",
                            ),
                            font_size="13px",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.hstack(
                        rx.cond(
                            RelatoriosState.generation_mode == "static",
                            rx.icon(tag="file-down", size=16),
                            rx.cond(
                                RelatoriosState.generation_mode == "custom",
                                rx.icon(tag="wand-sparkles", size=16),
                                rx.icon(tag="sparkles", size=16),
                            ),
                        ),
                        rx.text(
                            rx.cond(
                                RelatoriosState.generation_mode == "static",
                                "Gerar Dossier PDF",
                                rx.cond(
                                    RelatoriosState.generation_mode == "custom",
                                    "Gerar Relatório Customizado",
                                    "Gerar com IA Enterprise",
                                ),
                            ),
                            font_size="13px",
                            font_family=S.FONT_TECH,
                            font_weight="700",
                        ),
                        spacing="2",
                        align="center",
                    ),
                ),
                on_click=rx.cond(
                    RelatoriosState.generation_mode == "static",
                    RelatoriosState.generate_static_report,
                    rx.cond(
                        RelatoriosState.generation_mode == "custom",
                        RelatoriosState.generate_custom_report,
                        RelatoriosState.generate_ai_report_mcp,
                    ),
                ),
                disabled=RelatoriosState.is_generating | (RelatoriosState.selected_contrato == ""),
                bg=rx.cond(
                    RelatoriosState.generation_mode == "static",
                    S.COPPER,
                    rx.cond(RelatoriosState.generation_mode == "custom", "#8B5CF6", S.PATINA),
                ),
                color="white",
                border_radius="12px",
                padding="12px 28px",
                font_family=S.FONT_TECH,
                font_weight="700",
                letter_spacing="0.05em",
                _hover={"opacity": "0.85", "transform": "translateY(-1px)"},
                transition="all 0.15s ease",
                box_shadow=rx.cond(
                    RelatoriosState.generation_mode != "static",
                    f"0 0 20px rgba(42,157,143,0.25)",
                    "none",
                ),
            ),
            width="100%",
            align="center",
        ),
        **{**S.GLASS_CARD, "padding": "16px 20px", "_hover": {}},
        border_top=rx.cond(
            RelatoriosState.generation_mode == "static",
            f"2px solid {S.COPPER}",
            rx.cond(
                RelatoriosState.generation_mode == "custom",
                "2px solid #8B5CF6",
                f"2px solid {S.PATINA}",
            ),
        ),
    )


# ── Error / success banner ────────────────────────────────────────────────────

def _feedback_banner() -> rx.Component:
    return rx.vstack(
        rx.cond(
            RelatoriosState.error_msg != "",
            rx.hstack(
                rx.icon(tag="triangle-alert", size=14, color=S.DANGER),
                rx.text(RelatoriosState.error_msg, font_size="13px", color=S.DANGER, flex="1"),
                rx.button(
                    rx.icon(tag="x", size=12),
                    variant="ghost",
                    size="1",
                    color=S.TEXT_MUTED,
                    on_click=RelatoriosState.clear_ai_text,
                ),
                spacing="3",
                align="center",
                width="100%",
                padding="12px 16px",
                bg=S.DANGER_BG,
                border=f"1px solid rgba(239,68,68,0.3)",
                border_radius="10px",
            ),
        ),
        rx.cond(
            RelatoriosState.success_msg != "",
            rx.hstack(
                rx.icon(tag="check-circle", size=14, color=S.PATINA),
                rx.text(RelatoriosState.success_msg, font_size="13px", color=S.PATINA, flex="1"),
                spacing="3",
                align="center",
                width="100%",
                padding="12px 16px",
                bg=S.PATINA_GLOW,
                border=f"1px solid rgba(42,157,143,0.3)",
                border_radius="10px",
            ),
        ),
        spacing="2",
        width="100%",
    )


# ── Preview panel ─────────────────────────────────────────────────────────────

def _preview_panel() -> rx.Component:
    return rx.cond(
        (RelatoriosState.report_html_preview != "") | (RelatoriosState.ai_report_text != ""),
        rx.vstack(
            rx.hstack(
                rx.icon(tag="eye", size=15, color=S.COPPER),
                rx.text(
                    "PRÉVIA / RESULTADO",
                    font_family=S.FONT_TECH,
                    font_size="0.8rem",
                    font_weight="700",
                    letter_spacing="0.12em",
                    color=S.TEXT_MUTED,
                ),
                rx.spacer(),
                rx.cond(
                    RelatoriosState.report_pdf_url != "",
                    rx.button(
                        rx.hstack(
                            rx.icon(tag="download", size=13),
                            rx.text("Download PDF", font_size="12px"),
                            spacing="2",
                            align="center",
                        ),
                        on_click=RelatoriosState.open_pdf_url(RelatoriosState.report_pdf_url),
                        size="2",
                        bg=S.COPPER,
                        color="white",
                        border_radius="8px",
                        _hover={"opacity": "0.85"},
                    ),
                ),
                rx.cond(
                    RelatoriosState.ai_report_text != "",
                    rx.button(
                        rx.hstack(
                            rx.icon(tag="copy", size=13),
                            rx.text("Copiar", font_size="12px"),
                            spacing="2",
                            align="center",
                        ),
                        size="2",
                        variant="ghost",
                        color=S.PATINA,
                        border=f"1px solid rgba(42,157,143,0.4)",
                        border_radius="8px",
                        on_click=RelatoriosState.copy_ai_text,
                        _hover={"bg": S.PATINA_GLOW},
                    ),
                ),
                rx.button(
                    rx.icon(tag="x", size=13),
                    size="2",
                    variant="ghost",
                    color=S.TEXT_MUTED,
                    border_radius="8px",
                    on_click=rx.cond(
                        RelatoriosState.ai_report_text != "",
                        RelatoriosState.clear_ai_text,
                        RelatoriosState.clear_static_preview,
                    ),
                    _hover={"color": "white"},
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            # Content
            rx.cond(
                RelatoriosState.report_html_preview != "",
                rx.box(
                    rx.box(
                        rx.html(RelatoriosState.report_html_preview),
                        min_width="800px",
                    ),
                    width="100%",
                    max_height="620px",
                    overflow_x="auto",
                    overflow_y="auto",
                    border_radius="12px",
                    border=f"1px solid {S.BORDER_SUBTLE}",
                    bg=S.BG_SURFACE,
                ),
                rx.box(
                    rx.markdown(
                        RelatoriosState.ai_report_text,
                        component_map={
                            "h1": lambda text: rx.box(
                                rx.text(
                                    text,
                                    font_size="1.4rem", font_weight="900",
                                    color="#C98B2A", font_family="Rajdhani, sans-serif",
                                    letter_spacing="0.06em", line_height="1.2",
                                ),
                                padding_bottom="10px",
                                border_bottom="2px solid rgba(201,139,42,0.45)",
                                margin_bottom="18px",
                                width="100%",
                            ),
                            "h2": lambda text: rx.box(
                                rx.text(
                                    text,
                                    font_size="0.95rem", font_weight="700",
                                    color="#1A1A2E", font_family="Rajdhani, sans-serif",
                                    letter_spacing="0.1em", text_transform="uppercase",
                                ),
                                padding="7px 14px",
                                bg="rgba(201,139,42,0.07)",
                                border_left="3px solid #C98B2A",
                                border_radius="0 6px 6px 0",
                                margin_top="22px",
                                margin_bottom="10px",
                                width="100%",
                            ),
                            "h3": lambda text: rx.box(
                                rx.text(
                                    text,
                                    font_size="0.9rem", font_weight="700",
                                    color="#2A9D8F",
                                ),
                                margin_top="14px",
                                margin_bottom="6px",
                                width="100%",
                            ),
                            "p": lambda text: rx.text(
                                text,
                                font_size="0.875rem", color="#374151",
                                line_height="1.75", margin_bottom="10px",
                            ),
                            "blockquote": lambda text: rx.box(
                                rx.hstack(
                                    rx.box(width="3px", min_height="100%", bg="#C98B2A",
                                           border_radius="2px", flex_shrink="0"),
                                    rx.text(
                                        text,
                                        font_size="0.9rem", font_weight="600",
                                        color="#1A1A2E", line_height="1.6", font_style="italic",
                                    ),
                                    spacing="3", align="stretch", width="100%",
                                ),
                                padding="10px 16px",
                                bg="rgba(201,139,42,0.08)",
                                border_radius="0 8px 8px 0",
                                margin_y="14px",
                                width="100%",
                            ),
                            "code": lambda text: rx.el.code(
                                text,
                                style={
                                    "fontFamily": "JetBrains Mono, monospace",
                                    "fontSize": "0.8rem",
                                    "color": "#2A9D8F",
                                    "background": "rgba(42,157,143,0.08)",
                                    "padding": "1px 6px",
                                    "borderRadius": "4px",
                                },
                            ),
                        },
                    ),
                    width="100%",
                    max_height="640px",
                    overflow_y="auto",
                    padding="28px 36px",
                    bg="linear-gradient(135deg, #FFFEF5 0%, #FFF8E7 50%, #FFFEF5 100%)",
                    border_radius="12px",
                    border="1px solid rgba(201,139,42,0.25)",
                    box_shadow="inset 0 0 40px rgba(201,139,42,0.04), 0 4px 20px rgba(0,0,0,0.15)",
                ),
            ),
            spacing="4",
            width="100%",
            **{**S.GLASS_CARD, "padding": "20px"},
        ),
    )


# ── History ────────────────────────────────────────────────────────────────────

def _history_row(row: dict) -> rx.Component:
    tipo_label = rx.cond(
        row["tipo"] == "ia_mcp",
        "IA MCP",
        rx.cond(
            row["tipo"] == "ia",
            "IA",
            rx.cond(row["tipo"] == "custom", "Custom", "Estático"),
        ),
    )
    tipo_scheme = rx.cond(
        (row["tipo"] == "ia_mcp") | (row["tipo"] == "ia"),
        "teal",
        rx.cond(row["tipo"] == "custom", "violet", "amber"),
    )
    return rx.table.row(
        rx.table.cell(
            rx.text(row["created_at"], font_size="11px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
        ),
        rx.table.cell(
            rx.text(row["contrato"], font_size="12px", color="white", font_weight="500"),
        ),
        rx.table.cell(
            rx.text(row["cliente"], font_size="12px", color=S.TEXT_MUTED),
        ),
        rx.table.cell(
            rx.badge(tipo_label, color_scheme=tipo_scheme, variant="soft", size="1", font_family=S.FONT_TECH),
        ),
        rx.table.cell(
            rx.text(row["abordagem"], font_size="11px", color=S.TEXT_MUTED),
        ),
        rx.table.cell(
            rx.text(row["created_by"], font_size="11px", color=S.TEXT_MUTED),
        ),
        rx.table.cell(
            rx.cond(
                row["pdf_url"] != "",
                rx.button(
                    rx.icon(tag="download", size=12),
                    on_click=RelatoriosState.open_pdf_url(row["pdf_url"]),
                    size="1",
                    variant="ghost",
                    color=S.COPPER,
                    border=f"1px solid {S.BORDER_ACCENT}",
                    border_radius="6px",
                    _hover={"bg": S.COPPER_GLOW},
                ),
                rx.text("—", font_size="11px", color=S.TEXT_MUTED),
            ),
        ),
    )


def _history_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon(tag="history", size=15, color=S.COPPER),
            rx.text(
                "HISTÓRICO DE RELATÓRIOS",
                font_family=S.FONT_TECH,
                font_size="0.8rem",
                font_weight="700",
                letter_spacing="0.12em",
                color=S.TEXT_MUTED,
            ),
            rx.spacer(),
            rx.cond(
                RelatoriosState.is_loading_history,
                rx.spinner(size="1", color=S.COPPER),
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.cond(
            RelatoriosState.reports_history.length() == 0,
            rx.center(
                rx.vstack(
                    rx.icon(tag="file-x", size=28, color=S.TEXT_MUTED),
                    rx.text("Nenhum relatório gerado ainda", font_size="12px", color=S.TEXT_MUTED),
                    spacing="2",
                    align="center",
                ),
                padding_y="28px",
                width="100%",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        *[rx.table.column_header_cell(
                            col,
                            style={"fontSize": "10px", "color": S.TEXT_MUTED,
                                   "letterSpacing": "0.1em", "fontFamily": S.FONT_TECH,
                                   "background": S.BG_SURFACE},
                        ) for col in ["DATA", "CONTRATO", "CLIENTE", "TIPO", "ABORDAGEM", "GERADO POR", "PDF"]],
                    ),
                ),
                rx.table.body(rx.foreach(RelatoriosState.reports_history, _history_row)),
                width="100%",
                variant="ghost",
                size="1",
                style={"background": "transparent"},
            ),
        ),
        spacing="4",
        width="100%",
        **{**S.GLASS_CARD, "padding": "20px"},
    )


# ── Main page ──────────────────────────────────────────────────────────────────

def relatorios_page() -> rx.Component:
    return rx.vstack(
        _page_header(),
        _contract_selector(),
        _mode_selector(),
        _configurator(),
        _abordagem_selector(),
        _custom_prompt_section(),
        _recipients_section(),
        _generate_button(),
        _feedback_banner(),
        _preview_panel(),
        _history_section(),
        spacing="4",
        width="100%",
        padding_bottom="40px",
        class_name="animate-enter",
    )
