"""
RDO v2 Form — Formulário unificado, single-page, sem wizard.
Rota: /rdo-form
"""

import reflex as rx

from bomtempo.state.rdo_state import RDOState
from bomtempo.state.global_state import GlobalState


# ── Paleta ──────────────────────────────────────────────────────────────────
_BG         = "#0B1A15"
_CARD       = "rgba(255,255,255,0.04)"
_BORDER     = "rgba(255,255,255,0.10)"
_COPPER     = "#C98B2A"
_PATINA     = "#2A9D8F"
_TEXT       = "#E8F0EE"
_MUTED      = "#6B9090"
_DANGER     = "#E05252"
_INPUT_BG   = "rgba(255,255,255,0.06)"
_BTN_PRI    = "linear-gradient(135deg,#C98B2A,#9B6820)"
_BTN_GHOST  = "rgba(255,255,255,0.06)"


# ── Shared primitives ────────────────────────────────────────────────────────

def _label(text: str) -> rx.Component:
    return rx.text(text, class_name="rdo-field-label")


def _input(
    value: rx.Var,
    on_change,
    placeholder: str = "",
    type_: str = "text",
    width: str = "100%",
    blur_mode: bool = False,
) -> rx.Component:
    """Input field. blur_mode=True uses default_value+on_blur (no keystroke roundtrips)."""
    base_style = {
        "background": _INPUT_BG,
        "border": f"1px solid {_BORDER}",
        "border_radius": "6px",
        "color": _TEXT,
        "padding": "10px 14px",
        "font_size": "16px",  # ≥16px evita zoom no iOS
        "min_height": "44px",  # touch target mínimo
        "_focus": {"border_color": _COPPER, "outline": "none"},
    }
    if blur_mode:
        return rx.el.input(
            default_value=value,
            on_blur=on_change,
            placeholder=placeholder,
            type=type_,
            style={**base_style, "width": width},
        )
    return rx.input(
        value=value,
        on_change=on_change,
        placeholder=placeholder,
        type=type_,
        width=width,
        style=base_style,
    )


def _select(value: rx.Var, on_change, options: list | rx.Var, width: str = "100%") -> rx.Component:
    return rx.select.root(
        rx.select.trigger(width=width),
        rx.select.content(
            rx.foreach(
                options,
                lambda opt: rx.select.item(opt, value=opt),
            ),
        ),
        value=value,
        on_change=on_change,
    )


def _section_card(*children, title: str = "", icon: str = "", badge: str = "") -> rx.Component:
    # Badge element
    if isinstance(badge, rx.Var):
        badge_el = rx.cond(
            badge != "",
            rx.box(
                rx.text(badge, class_name="rdo-section-badge badge-done"),
                display="flex",
                align_items="center",
            ),
            rx.fragment(),
        )
    elif badge == "✓":
        badge_el = rx.box(
            rx.text("✓", class_name="rdo-section-badge badge-done"),
        )
    elif badge:
        badge_el = rx.box(
            rx.text(badge, class_name="rdo-section-badge badge-count"),
        )
    else:
        badge_el = rx.fragment()

    header = rx.hstack(
        # Icon box
        rx.box(
            rx.icon(icon, size=15, color=_COPPER) if icon else rx.fragment(),
            class_name="rdo-section-icon",
        ) if icon else rx.fragment(),
        rx.text(title, class_name="rdo-section-title") if title else rx.fragment(),
        rx.spacer(),
        badge_el,
        align="center",
        class_name="rdo-section-header",
    )

    return rx.box(
        header,
        *children,
        class_name="rdo-section-card",
    )


def _add_btn(on_click, label: str = "Adicionar") -> rx.Component:
    return rx.button(
        rx.icon("plus", size=14),
        label,
        on_click=on_click,
        size="3",
        style={
            "background": "rgba(201,139,42,0.15)",
            "border": f"1px solid {_COPPER}",
            "color": _COPPER,
            "border_radius": "6px",
            "cursor": "pointer",
            "min_height": "44px",
            "_hover": {"background": "rgba(201,139,42,0.25)"},
        },
    )


def _remove_btn(on_click) -> rx.Component:
    return rx.button(
        rx.icon("x", size=12),
        on_click=on_click,
        size="1",
        style={
            "background": "rgba(224,82,82,0.10)",
            "border": "1px solid rgba(224,82,82,0.3)",
            "color": _DANGER,
            "border_radius": "4px",
            "cursor": "pointer",
            "padding": "4px 8px",
            "_hover": {"background": "rgba(224,82,82,0.2)"},
        },
    )


def _readonly_badge(label: str, value: rx.Var, color: str = _TEXT) -> rx.Component:
    return rx.vstack(
        _label(label),
        rx.box(
            rx.text(value, size="2", color=color, weight="medium"),
            padding="7px 12px",
            background="rgba(255,255,255,0.03)",
            border=f"1px solid {_BORDER}",
            border_radius="6px",
            width="100%",
            min_height="36px",
        ),
        spacing="1",
        width="100%",
    )


# ── Progress Tracker ─────────────────────────────────────────────────────────

def _progress_step(label: str, done_condition: rx.Var, icon_done: str = "check") -> rx.Component:
    """Single step pill in the progress tracker."""
    return rx.cond(
        done_condition,
        rx.box(
            rx.hstack(
                rx.icon(icon_done, size=10),
                rx.text(label),
                spacing="1",
                align="center",
            ),
            class_name="rdo-progress-step done",
        ),
        rx.box(
            rx.hstack(
                rx.box(class_name="rdo-progress-dot"),
                rx.text(label),
                spacing="1",
                align="center",
            ),
            class_name="rdo-progress-step",
        ),
    )


def _rdo_progress_tracker() -> rx.Component:
    """Sticky progress bar with section completion indicators."""
    return rx.box(
        _progress_step("Dados", RDOState.rdo_contrato != "", "check"),
        rx.box(width="1px", height="16px", background="rgba(255,255,255,0.08)", flex_shrink="0"),
        _progress_step("GPS", RDOState.checkin_done, "map-pin"),
        rx.box(width="1px", height="16px", background="rgba(255,255,255,0.08)", flex_shrink="0"),
        _progress_step("EPIs", RDOState.epi_foto_url != "", "shield-check"),
        rx.box(width="1px", height="16px", background="rgba(255,255,255,0.08)", flex_shrink="0"),
        _progress_step("Atividades", RDOState.atividades_items.length() > 0, "clipboard-check"),
        rx.box(width="1px", height="16px", background="rgba(255,255,255,0.08)", flex_shrink="0"),
        _progress_step("Fotos", RDOState.evidencias_items.length() > 0, "camera"),
        rx.box(width="1px", height="16px", background="rgba(255,255,255,0.08)", flex_shrink="0"),
        _progress_step("Assinatura", RDOState.signatory_sig_b64 != "", "pen-line"),
        class_name="rdo-progress-bar",
    )


# ── Sticky Header ────────────────────────────────────────────────────────────

def _sticky_header() -> rx.Component:
    return rx.box(
        rx.hstack(
            # Brand + contract info
            rx.hstack(
                rx.box(
                    rx.image(src="/icon.png", width="32px", height="32px", border_radius="6px", object_fit="cover"),
                    position="relative",
                ),
                rx.vstack(
                    rx.hstack(
                        rx.text("DIÁRIO DE OBRA", size="1", color=_COPPER, weight="bold",
                                style={"text_transform": "uppercase", "letter_spacing": "2px",
                                       "font_family": "'Rajdhani', sans-serif"}),
                        rx.box(
                            rx.text("v2", size="1", color=_PATINA, weight="bold",
                                    style={"font_family": "'JetBrains Mono', monospace"}),
                            padding="1px 5px",
                            border="1px solid rgba(42,157,143,0.35)",
                            border_radius="3px",
                            background="rgba(42,157,143,0.08)",
                        ),
                        spacing="2", align="center",
                    ),
                    rx.cond(
                        RDOState.rdo_contrato != "",
                        rx.hstack(
                            rx.text(RDOState.rdo_contrato, size="2", weight="bold", color=_TEXT,
                                    style={"font_family": "'Rajdhani', sans-serif"}),
                            rx.box(width="3px", height="3px", border_radius="50%",
                                   background=_MUTED, flex_shrink="0"),
                            rx.text(RDOState.rdo_data_display, size="1", color=_MUTED),
                            spacing="2", align="center",
                        ),
                        rx.text("Preencha o formulário abaixo", size="1", color=_MUTED),
                    ),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
            ),
            rx.spacer(),
            # Actions
            rx.hstack(
                # Auto-save status — hidden on mobile
                rx.box(
                    rx.cond(
                        RDOState.is_submitting,
                        rx.hstack(
                            rx.spinner(size="1"),
                            rx.text(RDOState.submit_status, size="1", color=_COPPER),
                            spacing="1",
                        ),
                        rx.cond(
                            RDOState.is_draft_saving,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Salvando…", size="1", color=_MUTED),
                                spacing="1",
                            ),
                            rx.cond(
                                RDOState.draft_saved_at != "",
                                rx.hstack(
                                    rx.icon("cloud-check", size=11, color=_PATINA),
                                    rx.text(RDOState.draft_saved_at, size="1", color=_MUTED),
                                    spacing="1",
                                ),
                                rx.fragment(),
                            ),
                        ),
                    ),
                    display=["none", "flex"],
                    align_items="center",
                ),
                # Meus RDOs
                rx.tooltip(
                    rx.button(
                        rx.icon("list", size=14),
                        on_click=rx.redirect("/rdo-historico"),
                        size="2",
                        style={
                            "background": "rgba(255,255,255,0.05)",
                            "border": f"1px solid {_BORDER}",
                            "color": _MUTED,
                            "border_radius": "7px",
                            "cursor": "pointer",
                            "min_height": "40px",
                            "padding": "0 10px",
                            "_hover": {"border_color": _COPPER, "color": _COPPER},
                        },
                    ),
                    content="Histórico de RDOs",
                ),
                # Save draft
                rx.tooltip(
                    rx.button(
                        rx.icon("cloud-upload", size=14),
                        on_click=RDOState.save_draft,
                        size="2",
                        style={
                            "background": "rgba(255,255,255,0.04)",
                            "border": f"1px solid {_BORDER}",
                            "color": _MUTED,
                            "border_radius": "7px",
                            "cursor": "pointer",
                            "min_height": "40px",
                            "padding": "0 10px",
                            "_hover": {"border_color": _COPPER, "color": _TEXT},
                        },
                    ),
                    content="Salvar rascunho",
                ),
                # Delete draft (conditional)
                rx.cond(
                    RDOState.draft_id_rdo != "",
                    rx.tooltip(
                        rx.button(
                            rx.icon("trash-2", size=14),
                            on_click=RDOState.delete_current_draft,
                            size="2",
                            style={
                                "background": "rgba(239,68,68,0.07)",
                                "border": "1px solid rgba(239,68,68,0.2)",
                                "color": "#EF4444",
                                "border_radius": "7px",
                                "cursor": "pointer",
                                "min_height": "40px",
                                "padding": "0 10px",
                            },
                        ),
                        content="Excluir rascunho",
                    ),
                ),
                # Send button — visible on tablet+, hidden on mobile (bottom bar handles it)
                rx.box(
                    rx.button(
                        rx.icon("send", size=14),
                        "Enviar",
                        on_click=RDOState.open_confirm,
                        size="2",
                        loading=RDOState.is_submitting,
                        style={
                            "background": _BTN_PRI,
                            "color": "#fff",
                            "border_radius": "7px",
                            "font_weight": "700",
                            "cursor": "pointer",
                            "min_height": "40px",
                            "padding": "0 16px",
                            "font_family": "'Rajdhani', sans-serif",
                            "letter_spacing": "0.05em",
                            "text_transform": "uppercase",
                        },
                    ),
                    display=["none", "flex"],
                ),
                spacing="2",
                align="center",
            ),
            align="center",
            width="100%",
        ),
        position="sticky",
        top="0",
        z_index="50",
        background="rgba(8,18,16,0.97)",
        border_bottom=f"1px solid rgba(201,139,42,0.12)",
        padding=["10px 14px", "12px 24px"],
        style={"backdrop_filter": "blur(16px)", "-webkit-backdrop-filter": "blur(16px)"},
    )


# ── Draft resume banner ──────────────────────────────────────────────────────

def _draft_banner() -> rx.Component:
    return rx.cond(
        RDOState.has_draft_to_resume,
        rx.box(
            rx.hstack(
                rx.icon("file-clock", size=16, color=_COPPER),
                rx.text("Você tem um rascunho não enviado.", size="2", color=_TEXT),
                rx.spacer(),
                rx.button(
                    "Retomar",
                    on_click=RDOState.resume_draft,
                    size="1",
                    style={"background": _BTN_PRI, "color": "#fff", "border_radius": "6px"},
                ),
                rx.button(
                    "Descartar",
                    on_click=RDOState.discard_draft_offer,
                    size="1",
                    variant="ghost",
                    color=_MUTED,
                ),
                spacing="3",
                align="center",
            ),
            padding="12px 20px",
            background="rgba(201,139,42,0.12)",
            border="1px solid rgba(201,139,42,0.3)",
            border_radius="8px",
            margin_bottom="16px",
        ),
    )


# ── Section: Header info (read-only badges + editable fields) ────────────────

def _section_header_info() -> rx.Component:
    return _section_card(
        # Contrato — selector para admin/gestor, badge readonly para peão
        rx.cond(
            RDOState.can_choose_contrato,
            rx.vstack(
                rx.text("Contrato *", style={"fontSize": "11px", "fontFamily": "monospace", "color": _MUTED, "letterSpacing": "0.06em", "textTransform": "uppercase"}),
                rx.select.root(
                    rx.select.trigger(
                        placeholder="Selecione o contrato...",
                        style={"background": "rgba(14,26,23,0.8)", "border": f"1px solid rgba(255,255,255,0.12)", "borderRadius": "6px", "color": _COPPER, "fontSize": "14px", "width": "100%", "fontFamily": "'Rajdhani', sans-serif", "fontWeight": "700"},
                    ),
                    rx.select.content(
                        rx.select.item("— Selecione —", value="__none__"),
                        rx.foreach(
                            GlobalState.contract_ids_list,
                            lambda c: rx.select.item(c, value=c),
                        ),
                        bg="#0e1a17",
                        border="1px solid rgba(255,255,255,0.12)",
                    ),
                    value=rx.cond(RDOState.rdo_contrato, RDOState.rdo_contrato, "__none__"),
                    on_change=RDOState.select_rdo_contrato,
                    width="100%",
                ),
                spacing="1",
                width="100%",
                margin_bottom="4px",
            ),
            _readonly_badge("Contrato", RDOState.rdo_contrato, _COPPER),
        ),
        # Read-only: projeto, cliente, localização, tipo tarefa
        rx.grid(
            _readonly_badge("Projeto", RDOState.rdo_projeto),
            _readonly_badge("Cliente", RDOState.rdo_cliente),
            _readonly_badge("Localização / Endereço da Obra", RDOState.rdo_localizacao),
            _readonly_badge("Tipo de Tarefa", RDOState.rdo_tipo_tarefa),
            columns={"initial": "1", "sm": "2"},
            gap="12px",
            width="100%",
        ),
        rx.box(height="12px"),
        # Editable fields
        rx.grid(
            # Data
            rx.vstack(
                _label("Data *"),
                _input(RDOState.rdo_data, RDOState.set_rdo_data, type_="date"),
                spacing="1",
            ),
            # Clima
            rx.vstack(
                _label("Clima"),
                _select(RDOState.rdo_clima, RDOState.set_rdo_clima, RDOState.clima_options),
                spacing="1",
            ),
            # Turno
            rx.vstack(
                _label("Turno"),
                _select(RDOState.rdo_turno, RDOState.set_rdo_turno, RDOState.turno_options),
                spacing="1",
            ),
            # Equipe alocada
            rx.vstack(
                _label("Equipe (pessoas no dia)"),
                _input(RDOState.rdo_equipe_alocada, RDOState.set_rdo_equipe_alocada,
                       placeholder="Ex: 8", type_="number", blur_mode=False),
                spacing="1",
            ),
            columns={"initial": "1", "sm": "4"},
            gap="12px",
            width="100%",
        ),
        rx.box(height="12px"),
        # Orientação / Escopo
        rx.vstack(
            _label("Orientação / Escopo do Dia"),
            rx.el.textarea(
                default_value=RDOState.rdo_orientacao,
                on_blur=RDOState.set_rdo_orientacao,
                placeholder="Ex: Fixação de 24 painéis fotovoltaicos, cabamento da subestrutura do módulo L12…",
                rows="3",
                spell_check=True,
                lang="pt-BR",
                style={
                    "background": _INPUT_BG,
                    "border": f"1px solid {_BORDER}",
                    "border_radius": "6px",
                    "color": _TEXT,
                    "padding": "10px 12px",
                    "font_size": "16px",
                    "width": "100%",
                    "outline": "none",
                    "_focus": {"border_color": _COPPER},
                    "resize": "vertical",
                },
            ),
            spacing="1",
            width="100%",
        ),
        rx.box(height="12px"),
        # Interrupção
        rx.hstack(
            rx.checkbox(
                "Houve interrupção no dia",
                checked=RDOState.rdo_houve_interrupcao,
                on_change=RDOState.set_rdo_houve_interrupcao,
                color_scheme="amber",
            ),
            spacing="2",
            align="center",
        ),
        rx.cond(
            RDOState.rdo_houve_interrupcao,
            rx.box(
                rx.vstack(
                    _label("Motivo da Interrupção"),
                    _input(RDOState.rdo_motivo_interrupcao, RDOState.set_rdo_motivo_interrupcao,
                           placeholder="Descreva o motivo da interrupção", blur_mode=True),
                    spacing="1",
                    width="100%",
                ),
                margin_top="12px",
            ),
        ),
        title="Informações do RDO",
        icon="file-text",
    )


# ── Section: GPS Check-in / Check-out ────────────────────────────────────────

def _gps_tag(lat: rx.Var, lng: rx.Var, endereco: rx.Var, _ts: rx.Var, label: str, show_dist: bool = False) -> rx.Component:
    dist_row = rx.cond(
        RDOState.checkin_distancia_str != "",
        rx.hstack(
            rx.icon("ruler", size=11, color=RDOState.checkin_distancia_color),
            rx.text(
                RDOState.checkin_distancia_str,
                size="1",
                weight="bold",
                color=RDOState.checkin_distancia_color,
            ),
            spacing="1",
            align="center",
            margin_top="3px",
        ),
    ) if show_dist else rx.fragment()

    return rx.cond(
        lat != 0.0,
        rx.box(
            rx.hstack(
                rx.icon("map-pin", size=14, color=_PATINA),
                rx.vstack(
                    rx.text(label, size="1", color=_MUTED, weight="bold",
                            style={"text_transform": "uppercase"}),
                    rx.text(endereco, size="2", color=_TEXT),
                    rx.text(
                        rx.text.span(lat.to_string()),
                        rx.text.span(", "),
                        rx.text.span(lng.to_string()),
                        size="1",
                        color=_MUTED,
                        style={"font_family": "monospace"},
                    ),
                    dist_row,
                    spacing="0",
                    align="start",
                ),
                spacing="2",
                align="start",
            ),
            padding="10px 14px",
            background="rgba(42,157,143,0.10)",
            border="1px solid rgba(42,157,143,0.3)",
            border_radius="8px",
        ),
    )


def _section_gps() -> rx.Component:
    return _section_card(
        rx.flex(
            # Check-in
            rx.vstack(
                rx.hstack(
                    rx.text("Check-in", size="2", weight="bold", color=_TEXT),
                    rx.cond(
                        RDOState.checkin_hora_str != "",
                        rx.badge(
                            rx.icon("clock", size=11),
                            rx.text.span(" "),
                            rx.text.span(RDOState.checkin_hora_str),
                            color_scheme="teal",
                            variant="soft",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    RDOState.checkin_done,
                    _gps_tag(RDOState.checkin_lat, RDOState.checkin_lng,
                             RDOState.checkin_endereco, RDOState.checkin_timestamp, "Check-in",
                             show_dist=True),
                    rx.box(),
                ),
                rx.button(
                    rx.cond(
                        RDOState.is_getting_checkin,
                        rx.hstack(rx.spinner(size="1"), rx.text("Obtendo localização…"), spacing="1"),
                        rx.hstack(
                            rx.icon("map-pin", size=15),
                            rx.text(rx.cond(RDOState.checkin_done, "Atualizar Check-in", "Registrar Check-in")),
                            spacing="2",
                        ),
                    ),
                    on_click=RDOState.do_checkin,
                    disabled=RDOState.is_getting_checkin,
                    size="3",
                    width="100%",
                    class_name=rx.cond(RDOState.checkin_done, "rdo-gps-btn done", "rdo-gps-btn"),
                ),
                spacing="2",
                align="start",
                flex="1",
                width=["100%", "auto"],
            ),
            # Divider + km badge (oculto no mobile — layout vertical)
            rx.vstack(
                rx.icon("arrow-right", size=20, color=_MUTED),
                rx.cond(
                    RDOState.km_percorrido_calc != "",
                    rx.badge(
                        rx.icon("navigation", size=11),
                        rx.text.span(" "),
                        rx.text.span(RDOState.km_percorrido_calc),
                        color_scheme="amber",
                        variant="soft",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                align="center",
                spacing="1",
                padding_top="24px",
                display=["none", "flex"],
            ),
            # Check-out
            rx.vstack(
                rx.hstack(
                    rx.text("Check-out", size="2", weight="bold", color=_TEXT),
                    rx.cond(
                        RDOState.checkout_hora_str != "",
                        rx.badge(
                            rx.icon("clock", size=11),
                            rx.text.span(" "),
                            rx.text.span(RDOState.checkout_hora_str),
                            color_scheme="teal",
                            variant="soft",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    RDOState.checkout_done,
                    _gps_tag(RDOState.checkout_lat, RDOState.checkout_lng,
                             RDOState.checkout_endereco, RDOState.checkout_timestamp, "Check-out"),
                    rx.box(),
                ),
                rx.button(
                    rx.cond(
                        RDOState.is_getting_checkout,
                        rx.hstack(rx.spinner(size="1"), rx.text("Obtendo localização…"), spacing="1"),
                        rx.hstack(
                            rx.icon("map-pin", size=15),
                            rx.text(rx.cond(RDOState.checkout_done, "Atualizar Check-out", "Registrar Check-out")),
                            spacing="2",
                        ),
                    ),
                    on_click=RDOState.do_checkout,
                    disabled=RDOState.is_getting_checkout,
                    size="3",
                    width="100%",
                    class_name=rx.cond(RDOState.checkout_done, "rdo-gps-btn done", "rdo-gps-btn"),
                ),
                spacing="2",
                align="start",
                flex="1",
                width=["100%", "auto"],
            ),
            direction={"initial": "column", "sm": "row"},
            gap="16px",
            align="start",
            width="100%",
        ),
        title="GPS — Check-in / Check-out",
        icon="map-pin",
        badge=rx.cond(RDOState.checkin_done, "✓", ""),
    )


# ── Section: Foto EPIs ───────────────────────────────────────────────────────

def _upload_photo_zone(
    upload_id: str,
    on_drop,
    is_uploading: rx.Var,
    existing_url: rx.Var,
    label: str,
    icon_name: str,
    on_remove=None,
) -> rx.Component:
    feedback_id = f"{upload_id}_scan_feedback"
    smart_scan_script = f"""
<script src="/js/smart_scan.js"></script>
<div id="{feedback_id}" style="display:none;font-size:12px;font-weight:600;padding:6px 10px;border-radius:8px;margin-bottom:6px;background:rgba(255,255,255,0.06);transition:all 0.3s ease;"></div>
<script>
(function(){{
  var _scanner = null;
  var _video   = null;
  var _canvas  = null;

  function _initSmartScan(){{
    var zone = document.getElementById('{upload_id}');
    if(!zone) return;
    var inp = zone.querySelector('input[type="file"]');
    if(!inp || inp._smartScanBound) return;
    inp._smartScanBound = true;

    inp.addEventListener('click', function(){{
      if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
      var feedback = document.getElementById('{feedback_id}');
      if(!_video){{
        _video  = document.createElement('video');
        _canvas = document.createElement('canvas');
        _video.style.display  = 'none';
        _canvas.style.display = 'none';
        document.body.appendChild(_video);
        document.body.appendChild(_canvas);
      }}
      if(window.SmartScanPreview){{
        if(_scanner) _scanner.stopCamera();
        _scanner = new SmartScanPreview(null, null, null);
        _scanner.video    = _video;
        _scanner.canvas   = _canvas;
        _scanner.ctx      = _canvas.getContext('2d');
        _scanner.updateFeedback = function(msg, color){{
          if(!feedback) return;
          feedback.textContent = msg;
          feedback.style.color = color;
          feedback.style.display = 'block';
        }};
        _scanner.startCamera();
      }}
    }});

    inp.addEventListener('change', function(){{
      if(_scanner){{ _scanner.stopCamera(); _scanner = null; }}
      var feedback = document.getElementById('{feedback_id}');
      if(feedback) feedback.style.display = 'none';
    }});
  }}

  if(document.readyState === 'loading'){{
    document.addEventListener('DOMContentLoaded', _initSmartScan);
  }} else {{
    setTimeout(_initSmartScan, 800);
  }}
}})();
</script>
"""
    return rx.vstack(
        rx.html(smart_scan_script),
        # Existing photo preview with lightbox + X
        rx.cond(
            existing_url != "",
            rx.box(
                # Image with hover overlay (lightbox)
                rx.box(
                    rx.image(
                        src=existing_url,
                        width="100%",
                        height="180px",
                        object_fit="cover",
                        style={"border_radius": "8px 8px 0 0" if on_remove else "8px", "display": "block"},
                    ),
                    rx.box(
                        rx.icon("zoom-in", size=24, color="white"),
                        position="absolute",
                        top="0", left="0", right="0", bottom="0",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        background="rgba(0,0,0,0)",
                        border_radius="8px 8px 0 0" if on_remove else "8px",
                        style={
                            "transition": "background 0.2s",
                            "cursor": "pointer",
                            "_hover": {"background": "rgba(0,0,0,0.45)"},
                        },
                        on_click=RDOState.open_lightbox(existing_url),
                    ),
                    position="relative",
                ),
                # X button row (only when on_remove provided)
                rx.cond(
                    on_remove is not None,
                    rx.hstack(
                        rx.spacer(),
                        rx.button(
                            rx.icon("x", size=12),
                            "Remover",
                            on_click=on_remove,
                            size="1",
                            variant="ghost",
                            style={
                                "color": _DANGER,
                                "cursor": "pointer",
                                "padding": "4px 8px",
                                "border_radius": "0 0 8px 8px",
                                "_hover": {"background": "rgba(224,82,82,0.15)"},
                            },
                        ),
                        width="100%",
                        padding="4px 8px",
                        background="rgba(255,255,255,0.04)",
                        border_radius="0 0 8px 8px",
                    ),
                    rx.fragment(),
                ),
                border=f"1px solid {_BORDER}",
                border_radius="8px",
                overflow="hidden",
                margin_bottom="10px",
            ),
        ),
        # Upload zone
        rx.upload(
            rx.vstack(
                rx.cond(
                    is_uploading,
                    rx.hstack(
                        rx.spinner(size="2", color_scheme="amber"),
                        rx.vstack(
                            rx.text("Processando imagem…", size="2", color=_TEXT, weight="medium"),
                            rx.text("Aguarde…", size="1", color=_MUTED),
                            spacing="0",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    rx.vstack(
                        rx.box(
                            rx.icon(icon_name, size=22, color=_COPPER),
                            class_name="rdo-upload-icon",
                        ),
                        rx.text(label, size="2", color=_TEXT, weight="medium", text_align="center"),
                        rx.text("JPG · PNG · HEIC · Câmera ou galeria",
                                size="1", color=_MUTED, text_align="center",
                                style={"opacity": "0.6"}),
                        spacing="2",
                        align="center",
                        padding_y="4px",
                    ),
                ),
                align="center",
                width="100%",
            ),
            id=upload_id,
            accept={"image/*": [".jpg", ".jpeg", ".png", ".webp", ".heic"]},
            multiple=False,
            max_size=15_000_000,
            on_drop=on_drop,
            class_name="rdo-upload-zone",
            width="100%",
        ),
        width="100%",
        spacing="0",
    )


def _section_epi() -> rx.Component:
    return _section_card(
        _upload_photo_zone(
            upload_id="rdo_epi_upload",
            on_drop=RDOState.upload_epi_files(rx.upload_files(upload_id="rdo_epi_upload")),
            is_uploading=RDOState.is_uploading_epi,
            existing_url=RDOState.epi_foto_url,
            label="Foto da Equipe com EPIs — toque para capturar",
            icon_name="shield-check",
            on_remove=RDOState.remove_epi_photo,
        ),
        title="Equipe com EPIs",
        icon="shield-check",
        badge=rx.cond(RDOState.epi_foto_url != "", "✓", ""),
    )


# ── Section: Atividades ──────────────────────────────────────────────────────

def _section_atividades() -> rx.Component:
    return _section_card(
        rx.vstack(
            rx.foreach(
                RDOState.atividades_items,
                lambda item, index: rx.box(
                    rx.flex(
                        rx.text(item["atividade"], size="2", color=_TEXT, flex="1", min_width="0"),
                        rx.hstack(
                            rx.badge(
                                rx.text.span(item.get("progresso_percentual", "0")),
                                rx.text.span("%"),
                                color_scheme="teal", variant="soft", size="1",
                            ),
                            rx.badge(item.get("status", "Em andamento"), color_scheme="amber", variant="outline", size="1"),
                            _remove_btn(RDOState.remove_at(index)),
                            spacing="2",
                            align="center",
                            flex_shrink="0",
                        ),
                        gap="8px",
                        align="center",
                        wrap="wrap",
                    ),
                    padding="8px 10px",
                    background="rgba(255,255,255,0.03)",
                    border_radius="6px",
                    border=f"1px solid {_BORDER}",
                    width="100%",
                ),
            ),
            spacing="2",
            width="100%",
        ),
        rx.box(height="8px"),
        rx.vstack(
            # Linha 1: Descrição — largura total
            _input(RDOState.at_desc, RDOState.set_at_desc, "Descrição do serviço executado"),
            # Linha 2: Controles — % + status + botão (wrappam em telas muito pequenas)
            rx.flex(
                _input(RDOState.at_pct, RDOState.set_at_pct, "% concluído", type_="number", width="90px"),
                rx.box(
                    _select(RDOState.at_status, RDOState.set_at_status, RDOState.at_status_options),
                    flex="1",
                    min_width="130px",
                ),
                _add_btn(RDOState.add_at, "Adicionar"),
                gap="8px",
                align="end",
                wrap="wrap",
                width="100%",
            ),
            spacing="2",
            width="100%",
        ),
        title="Serviços Executados",
        icon="clipboard-check",
        badge=RDOState.atividades_items.length().to_string(),
    )


# ── Section: Evidências (fotos do dia) ───────────────────────────────────────

def _ev_card(item) -> rx.Component:
    return rx.box(
        # Imagem clicável para lightbox
        rx.box(
            rx.image(
                src=item["foto_url"],
                width="100%",
                height=["160px", "140px"],
                object_fit="cover",
                style={"border_radius": "6px 6px 0 0", "display": "block"},
            ),
            # Overlay hover: ícone lupa
            rx.box(
                rx.icon("zoom-in", size=24, color="white"),
                position="absolute",
                top="0", left="0", right="0", bottom="0",
                display="flex",
                align_items="center",
                justify_content="center",
                background="rgba(0,0,0,0)",
                border_radius="6px 6px 0 0",
                style={
                    "transition": "background 0.2s",
                    "cursor": "pointer",
                    "_hover": {"background": "rgba(0,0,0,0.45)"},
                },
                on_click=RDOState.open_lightbox(item["foto_url"]),
            ),
            position="relative",
        ),
        rx.box(
            rx.hstack(
                rx.vstack(
                    # Caption area — click to edit inline
                    rx.cond(
                        RDOState.ev_editing_url == item["foto_url"],
                        # Editing mode: input + save/cancel
                        rx.hstack(
                            rx.el.input(
                                default_value=RDOState.ev_editing_draft,
                                on_blur=RDOState.save_edit_caption_blur,
                                auto_focus=True,
                                placeholder="Legenda da foto…",
                                style={
                                    "background": "rgba(255,255,255,0.08)",
                                    "border": f"1px solid {_PATINA}",
                                    "border_radius": "4px",
                                    "color": _TEXT,
                                    "font_size": "11px",
                                    "padding": "2px 6px",
                                    "width": "100%",
                                    "outline": "none",
                                },
                            ),
                            rx.icon(
                                "check", size=13,
                                color=_PATINA,
                                style={"cursor": "pointer"},
                                on_click=RDOState.save_edit_caption,
                            ),
                            rx.icon(
                                "x", size=13,
                                color=_MUTED,
                                style={"cursor": "pointer"},
                                on_click=RDOState.cancel_edit_caption,
                            ),
                            spacing="1",
                            align="center",
                            width="100%",
                        ),
                        # Display mode: click anywhere on caption to edit
                        rx.hstack(
                            rx.text(
                                rx.cond(item["legenda"] != "", item["legenda"], "Toque para adicionar legenda…"),
                                size="1",
                                color=rx.cond(item["legenda"] != "", _TEXT, _MUTED),
                                weight="medium",
                                style={"cursor": "pointer", "flex": "1"},
                            ),
                            rx.icon("pencil", size=10, color=_MUTED, style={"flex_shrink": "0"}),
                            spacing="1",
                            align="center",
                            width="100%",
                            on_click=RDOState.start_edit_caption(item["foto_url"]),
                        ),
                    ),
                    rx.cond(
                        item["exif_endereco"] != "",
                        rx.hstack(
                            rx.icon("map-pin", size=10, color=_PATINA),
                            rx.text(item["exif_endereco"], size="1", color=_PATINA),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    spacing="1",
                    align="start",
                    flex="1",
                ),
                # Botão X excluir
                rx.button(
                    rx.icon("x", size=12),
                    on_click=RDOState.remove_evidence(item["foto_url"]),
                    size="1",
                    variant="ghost",
                    style={
                        "color": _DANGER,
                        "cursor": "pointer",
                        "padding": "2px 4px",
                        "border_radius": "4px",
                        "_hover": {"background": "rgba(224,82,82,0.15)"},
                    },
                ),
                align="start",
                width="100%",
                spacing="1",
            ),
            padding="7px 8px",
            background="rgba(255,255,255,0.05)",
        ),
        border=f"1px solid {_BORDER}",
        border_radius="8px",
        overflow="hidden",
    )


def _section_evidencias() -> rx.Component:
    return _section_card(
        # exifr CDN + interceptor — fires before on_drop, sends EXIF to Reflex via hidden input
        rx.html("""
<script src="https://cdn.jsdelivr.net/npm/exifr@7/dist/lite.umd.js"></script>
<script>
(function(){
  function _sendExifToState(meta){
    var inp = document.getElementById('rdo-exif-bridge');
    if(!inp){ console.warn('[exifr] bridge input not found'); return; }
    var json = JSON.stringify(meta);
    console.log('[exifr] sending meta:', json);
    try {
      var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
      setter.call(inp, json);
    } catch(e){ inp.value = json; }
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    inp.dispatchEvent(new Event('change', {bubbles:true}));
  }

  function _initExifrInterceptor(){
    var uploadZone = document.getElementById('rdo_evidence_upload');
    if(!uploadZone) return;
    var fileInput = uploadZone.querySelector('input[type="file"]');
    if(!fileInput || fileInput._exifrBound) return;
    fileInput._exifrBound = true;
    console.log('[exifr] interceptor bound to upload input');

    fileInput.addEventListener('change', async function(e){
      var files = e.target.files;
      if(!files || !files.length) return;
      var file = files[0];
      var meta = {datetime:'', lat:0, lng:0, lastModified: String(file.lastModified || 0)};
      console.log('[exifr] file selected:', file.name, 'lastModified:', new Date(file.lastModified).toISOString());
      try {
        if(window.exifr){
          // Use exifr.gps() for most reliable GPS extraction (handles all formats)
          var gpsData = await exifr.gps(file).catch(function(){ return null; });
          if(gpsData && typeof gpsData.latitude === 'number'){
            meta.lat = gpsData.latitude;
            meta.lng = gpsData.longitude;
            console.log('[exifr] GPS found:', meta.lat, meta.lng);
          }
          // Parse full EXIF for DateTimeOriginal
          var parsed = await exifr.parse(file, {tiff:true, exif:true, gps:false}).catch(function(){ return null; });
          if(parsed && parsed.DateTimeOriginal){
            var d = parsed.DateTimeOriginal;
            meta.datetime = (d instanceof Date) ? d.toISOString() : String(d);
            console.log('[exifr] DateTimeOriginal:', meta.datetime);
          }
        } else {
          console.warn('[exifr] library not loaded yet');
        }
      } catch(ex){ console.warn('[exifr] parse error:', ex); }
      _sendExifToState(meta);
    });
  }

  var _t;
  var _obs = new MutationObserver(function(){clearTimeout(_t);_t=setTimeout(_initExifrInterceptor,80);});
  _obs.observe(document.body,{childList:true,subtree:true});
  [100,300,700,1500,3000].forEach(function(ms){setTimeout(_initExifrInterceptor,ms);});
})();
</script>
"""),
        # Invisible bridge input — JS sets value + dispatches change, Reflex on_change fires receive_exif_json
        rx.el.input(
            id="rdo-exif-bridge",
            default_value="",
            on_change=RDOState.receive_exif_json,
            style={
                "position": "absolute",
                "width": "1px",
                "height": "1px",
                "opacity": "0",
                "pointerEvents": "none",
                "overflow": "hidden",
            },
        ),
        # Photo grid
        rx.cond(
            RDOState.evidencias_items.length() > 0,
            rx.box(
                rx.grid(
                    rx.foreach(RDOState.evidencias_items, _ev_card),
                    columns={"initial": "2", "sm": "3"},
                    gap="12px",
                    width="100%",
                ),
                margin_bottom="16px",
            ),
        ),
        # Caption input
        rx.vstack(
            _label("Legenda para as próximas fotos (opcional)"),
            _input(RDOState.ev_legenda, RDOState.set_ev_legenda,
                   "Ex: Fundação concluída, armação do pilar…"),
            spacing="1",
            width="100%",
        ),
        rx.box(height="10px"),
        # Upload drop zone
        rx.upload(
            rx.vstack(
                rx.cond(
                    RDOState.is_uploading_evidence,
                    rx.hstack(
                        rx.spinner(size="2", color_scheme="amber"),
                        rx.vstack(
                            rx.text("Processando imagem…", size="2", color=_TEXT, weight="medium"),
                            rx.text("GPS + watermark automático", size="1", color=_MUTED),
                            spacing="0",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    rx.vstack(
                        rx.box(
                            rx.icon("camera", size=22, color=_COPPER),
                            class_name="rdo-upload-icon",
                        ),
                        rx.text("Adicionar fotos do dia",
                                size="2", color=_TEXT, weight="medium", text_align="center"),
                        rx.text("GPS extraído do EXIF · Marca d'água automática",
                                size="1", color=_MUTED, text_align="center",
                                style={"opacity": "0.6"}),
                        spacing="2",
                        align="center",
                        padding_y="4px",
                    ),
                ),
                align="center",
                width="100%",
            ),
            id="rdo_evidence_upload",
            accept={"image/jpeg": [".jpg", ".jpeg"], "image/png": [".png"], "image/webp": [".webp"], "image/heic": [".heic"]},
            multiple=True,
            max_size=15_000_000,
            on_drop=RDOState.upload_evidence_files(rx.upload_files(upload_id="rdo_evidence_upload")),
            class_name="rdo-upload-zone",
            width="100%",
        ),
        title="Fotos do Dia",
        icon="camera",
        badge=RDOState.evidencias_items.length().to_string(),
    )


# ── Section: Atualizar Cronograma ────────────────────────────────────────────

_CARD_INPUT = {"background": "rgba(14,26,23,0.8)", "border": f"1px solid rgba(255,255,255,0.10)", "borderRadius": "8px", "color": "#E8F0EE", "padding": "8px 10px", "fontSize": "13px", "width": "100%", "outline": "none"}


def _nova_atividade_row(item: dict) -> rx.Component:
    """Row for an unmapped activity pending approval — uses _key for handlers."""
    return rx.box(
        rx.hstack(
            rx.box(
                rx.hstack(
                    rx.icon(tag="alert-triangle", size=12, color="#E89845"),
                    rx.text("Pendente de aprovação", size="1", color="#E89845"),
                    spacing="1", align="center",
                ),
                padding="3px 8px", border_radius="4px",
                bg="rgba(232,152,69,0.08)", border="1px solid rgba(232,152,69,0.2)",
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="x", size=13),
                variant="ghost", size="1", cursor="pointer",
                color="rgba(255,255,255,0.3)",
                on_click=RDOState.remove_nova_atividade(item["_key"]),
            ),
            width="100%", align="center",
        ),
        rx.flex(
            rx.vstack(
                rx.text("Nome da atividade *", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                rx.el.input(
                    default_value=item["nome"],
                    on_blur=RDOState.set_nova_atividade_nome(item["_key"]),
                    placeholder="Ex: Instalação de quadro elétrico",
                    style=_CARD_INPUT,
                ),
                spacing="1", flex="1",
            ),
            rx.vstack(
                rx.text("Fase / Disciplina", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                rx.el.input(
                    default_value=item["fase"],
                    on_blur=RDOState.set_nova_atividade_fase(item["_key"]),
                    placeholder="Ex: Elétrica",
                    style=dict(_CARD_INPUT, **{"width": "150px"}),
                ),
                spacing="1",
            ),
            rx.vstack(
                rx.text("%", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                rx.el.input(
                    type="number", min="0", max="100",
                    default_value=item["progresso"],
                    on_blur=RDOState.set_nova_atividade_progresso(item["_key"]),
                    style=dict(_CARD_INPUT, **{"width": "80px"}),
                ),
                spacing="1",
            ),
            gap="10px", flex_wrap="wrap", width="100%",
        ),
        padding="10px 12px",
        background="rgba(232,152,69,0.04)",
        border="1px dashed rgba(232,152,69,0.25)",
        border_radius="8px",
        width="100%",
        display="flex",
        flex_direction="column",
        gap="8px",
    )


def _extra_atividade_row(extra: dict) -> rx.Component:
    """Row for a single extra activity - two-step macro then activity selection."""
    return rx.vstack(
        rx.hstack(
            # Step 1: Macro phase select
            rx.vstack(
                rx.text("Disciplina", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                rx.select.root(
                    rx.select.trigger(placeholder="Disciplina", style=dict(_CARD_INPUT, **{"min_width": "150px"})),
                    rx.select.content(
                        rx.select.item("Nenhuma", value="__none__"),
                        rx.foreach(
                            RDOState.hub_atividades_macros,
                            lambda m: rx.select.item(m, value=m),
                        ),
                        style={"background": "#0D201C", "border": "1px solid rgba(255,255,255,0.1)"},
                    ),
                    value=rx.cond(extra["fase_macro_sel"] == "", "__none__", extra["fase_macro_sel"]),
                    on_change=RDOState.set_extra_fase_macro(extra["_key"]),
                ),
                spacing="1",
            ),
            # Step 2: Activity select (shown after macro selected)
            rx.cond(
                extra["fase_macro_sel"] != "",
                rx.vstack(
                    rx.text("Atividade adicional", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                    rx.select.root(
                        rx.select.trigger(placeholder="Atividade", style=dict(_CARD_INPUT, **{"min_width": "200px"})),
                        rx.select.content(
                            rx.select.item("Nenhuma", value="__none__"),
                            rx.foreach(
                                RDOState.hub_atividades_options,
                                lambda opt: rx.cond(
                                    opt["fase_macro"] == extra["fase_macro_sel"],
                                    rx.select.item(opt["label"], value=opt["id"]),
                                    rx.fragment(),
                                ),
                            ),
                            style={"background": "#0D201C", "border": "1px solid rgba(255,255,255,0.1)"},
                        ),
                        value=rx.cond(extra["id"] == "", "__none__", extra["id"]),
                        on_change=RDOState.set_extra_atividade_id(extra["_key"]),
                    ),
                    spacing="1", flex="1",
                ),
                rx.fragment(),
            ),
            rx.icon_button(
                rx.icon(tag="x", size=14),
                variant="ghost", size="1", cursor="pointer",
                color="rgba(255,255,255,0.3)",
                on_click=RDOState.remove_extra_atividade(extra["_key"]),
                margin_top="18px",
            ),
            spacing="2", align="end", width="100%", flex_wrap="wrap",
        ),
        # Progress fields shown after activity selected
        rx.cond(
            extra["id"] != "",
            rx.vstack(
                # Qty tracker badge
                rx.cond(
                    extra["total_qty"] != "0",
                    rx.box(
                        rx.hstack(
                            rx.icon(tag="layers", size=13, color="rgba(201,139,42,0.7)"),
                            rx.text(
                                extra["exec_qty"] + " / " + extra["total_qty"] + " " + extra["unidade"] + " executados",
                                size="1", color="rgba(201,139,42,0.9)", font_family="var(--font-mono)",
                            ),
                            spacing="2", align="center",
                        ),
                        padding="6px 10px", border_radius="6px",
                        bg="rgba(201,139,42,0.07)", border="1px solid rgba(201,139,42,0.2)",
                        width="100%",
                    ),
                ),
                # Production qty + efetivo side by side
                rx.hstack(
                    rx.cond(
                        extra["total_qty"] != "0",
                        rx.vstack(
                            rx.text(
                                "Producao de hoje (" + extra["unidade"] + ")",
                                size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                            rx.hstack(
                                rx.el.input(
                                    type="number", min="0",
                                    placeholder="Ex: 120",
                                    default_value=extra["producao_dia"],
                                    on_change=RDOState.set_extra_atividade_producao(extra["_key"]),
                                    style=dict(_CARD_INPUT, **{"width": "130px"}),
                                ),
                                rx.text("% auto", size="1", color="rgba(255,255,255,0.3)", font_style="italic"),
                                spacing="2", align="center",
                            ),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Progresso (%)", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                            rx.el.input(
                                type="number", min="0", max="100",
                                default_value=extra["progresso"],
                                on_blur=RDOState.set_extra_atividade_progresso(extra["_key"]),
                                style=dict(_CARD_INPUT, **{"width": "100px"}),
                            ),
                            spacing="1",
                        ),
                    ),
                    # Efetivo alocado nesta atividade — inline
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="users", size=11, color="rgba(201,139,42,0.8)"),
                            rx.text("Pessoas hoje", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                            spacing="1", align="center",
                        ),
                        rx.el.input(
                            type="number", min="0",
                            placeholder="Ex: 4",
                            default_value=extra["efetivo_alocado"],
                            on_change=RDOState.set_extra_atividade_efetivo(extra["_key"]),
                            style=dict(_CARD_INPUT, **{"width": "90px", "color": "#C98B2A", "fontWeight": "700"}),
                        ),
                        spacing="1",
                    ),
                    spacing="4", align="end", flex_wrap="wrap",
                ),
                spacing="2", width="100%",
                padding_left="8px",
                border_left="2px solid rgba(201,139,42,0.2)",
            ),
        ),
        spacing="2", width="100%",
    )


def _section_cronograma() -> rx.Component:
    """Section to link RDO to a cronograma activity and report progress."""

    def _progress_fields():
        return rx.cond(
            RDOState.rdo_atividade_id != "",
            rx.vstack(
                # Qty tracker badge — read-only, mostra acumulado
                rx.cond(
                    RDOState.rdo_ativ_total_qty != "0",
                    rx.box(
                        rx.hstack(
                            rx.icon(tag="layers", size=13, color="rgba(201,139,42,0.7)"),
                            rx.vstack(
                                rx.text(
                                    RDOState.rdo_ativ_exec_qty + " / " + RDOState.rdo_ativ_total_qty
                                    + " " + RDOState.rdo_ativ_unidade + " executados",
                                    size="1", color="rgba(201,139,42,0.95)",
                                    font_family="var(--font-mono)", weight="bold",
                                ),
                                rx.text(
                                    "Total planejado: " + RDOState.rdo_ativ_total_qty
                                    + " " + RDOState.rdo_ativ_unidade
                                    + ". Informe quantas foram realizadas HOJE.",
                                    size="1", color="rgba(201,139,42,0.5)", font_style="italic",
                                ),
                                spacing="0",
                            ),
                            spacing="2", align="start",
                        ),
                        padding="8px 12px", border_radius="6px",
                        bg="rgba(201,139,42,0.07)", border="1px solid rgba(201,139,42,0.25)",
                        width="100%",
                    ),
                ),
                # Qty input or manual % fallback
                rx.cond(
                    RDOState.rdo_ativ_total_qty != "0",
                    rx.vstack(
                        rx.text(
                            "Producao de hoje (" + RDOState.rdo_ativ_unidade + ")",
                            size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)",
                        ),
                        rx.hstack(
                            rx.el.input(
                                type="number", min="0",
                                placeholder="Ex: 120",
                                default_value=RDOState.rdo_producao_dia,
                                on_change=RDOState.set_rdo_producao_dia,
                                style=dict(_CARD_INPUT, **{"width": "160px"}),
                            ),
                            rx.text(
                                "O % sera calculado automaticamente.",
                                size="1", color="rgba(255,255,255,0.3)", font_style="italic",
                            ),
                            spacing="2", align="center",
                        ),
                        spacing="1",
                    ),
                    # Fallback: manual % when no total_qty configured
                    rx.vstack(
                        rx.text("Progresso atual (%)", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                        rx.hstack(
                            rx.el.input(
                                type="number", min="0", max="100",
                                default_value=RDOState.rdo_progresso_atividade,
                                on_blur=RDOState.set_rdo_progresso_atividade,
                                style=dict(_CARD_INPUT, **{"width": "120px"}),
                            ),
                            rx.text("%", size="2", color="rgba(255,255,255,0.4)"),
                            spacing="2", align="center",
                        ),
                        rx.text(
                            "Atividade sem quantidade definida. Configure no cronograma para medicao automatica.",
                            size="1", color="rgba(255,255,255,0.25)", font_style="italic",
                        ),
                        spacing="1",
                    ),
                ),
                spacing="2", width="100%",
            ),
        )

    def _today_panel() -> rx.Component:
        """Painel: atividades previstas para hoje + atrasadas."""
        def _ativ_chip(item: dict, color: str) -> rx.Component:
            return rx.hstack(
                rx.text(item["label"], size="1", color=color, flex="1", min_width="0",
                        style={"overflow": "hidden", "text-overflow": "ellipsis", "white-space": "nowrap"}),
                rx.text(item["pct"] + "%", size="1", color=color, font_family="var(--font-mono)", white_space="nowrap"),
                spacing="2", align="center", width="100%",
            )

        return rx.cond(
            (RDOState.today_planned_atividades.length() > 0) | (RDOState.overdue_atividades.length() > 0),
            rx.vstack(
                # Previstas hoje
                rx.cond(
                    RDOState.today_planned_atividades.length() > 0,
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="calendar-check", size=12, color="rgba(42,157,143,0.9)"),
                            rx.text("Previstas para hoje", size="1", color="rgba(42,157,143,0.9)",
                                    font_family="var(--font-mono)", weight="bold"),
                            spacing="1", align="center",
                        ),
                        rx.foreach(
                            RDOState.today_planned_atividades,
                            lambda item: _ativ_chip(item, "rgba(42,157,143,0.85)"),
                        ),
                        spacing="1", width="100%",
                        padding="8px 10px", border_radius="6px",
                        bg="rgba(42,157,143,0.06)", border="1px solid rgba(42,157,143,0.2)",
                    ),
                    rx.fragment(),
                ),
                # Atrasadas
                rx.cond(
                    RDOState.overdue_atividades.length() > 0,
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="alert-circle", size=12, color="rgba(224,82,82,0.9)"),
                            rx.text("Atrasadas (prazo vencido)", size="1", color="rgba(224,82,82,0.9)",
                                    font_family="var(--font-mono)", weight="bold"),
                            spacing="1", align="center",
                        ),
                        rx.foreach(
                            RDOState.overdue_atividades,
                            lambda item: _ativ_chip(item, "rgba(224,82,82,0.85)"),
                        ),
                        spacing="1", width="100%",
                        padding="8px 10px", border_radius="6px",
                        bg="rgba(224,82,82,0.06)", border="1px solid rgba(224,82,82,0.2)",
                    ),
                    rx.fragment(),
                ),
                spacing="2", width="100%",
            ),
            rx.fragment(),
        )

    def _allocation_counter() -> rx.Component:
        """Contador de alocação: X/Y alocados · Z disponíveis."""
        return rx.cond(
            RDOState.equipe_allocation_text != "",
            rx.hstack(
                rx.icon(tag="users", size=13, color="rgba(201,139,42,0.8)"),
                rx.text(
                    RDOState.equipe_allocation_text,
                    size="1", color="rgba(201,139,42,0.9)",
                    font_family="var(--font-mono)", weight="bold",
                ),
                spacing="2", align="center",
                padding="6px 10px", border_radius="6px",
                bg="rgba(201,139,42,0.06)", border="1px solid rgba(201,139,42,0.2)",
                width="100%",
            ),
            rx.fragment(),
        )

    return _section_card(
        rx.vstack(
            # Painel de atividades de hoje + atrasadas
            _today_panel(),
            # Contador de alocação
            _allocation_counter(),
            # Loading state
            rx.cond(
                RDOState.hub_atividades_loading,
                rx.hstack(
                    rx.spinner(size="2"),
                    rx.text("Carregando atividades...", size="2", color="rgba(255,255,255,0.4)"),
                    spacing="2", align="center",
                ),
                rx.cond(
                    RDOState.hub_atividades_options.length() == 0,
                    rx.text(
                        "Nenhuma atividade mapeada neste contrato.",
                        size="2", color="rgba(255,255,255,0.4)", font_style="italic",
                    ),
                    # Two-step: disciplina -> atividade
                    rx.vstack(
                        # Step 1 — disciplina (fase macro)
                        rx.vstack(
                            rx.text("Disciplina", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Selecionar disciplina", style=_CARD_INPUT),
                                rx.select.content(
                                    rx.select.item("Nenhuma", value="__none__"),
                                    rx.foreach(
                                        RDOState.hub_atividades_macros,
                                        lambda m: rx.select.item(m, value=m),
                                    ),
                                    style={"background": "#0D201C", "border": "1px solid rgba(255,255,255,0.1)"},
                                ),
                                value=rx.cond(
                                    RDOState.rdo_fase_macro_sel == "", "__none__", RDOState.rdo_fase_macro_sel
                                ),
                                on_change=RDOState.set_rdo_fase_macro,
                            ),
                            spacing="1", width="100%",
                        ),
                        # Step 2 — atividade (filtrada pela disciplina)
                        rx.cond(
                            RDOState.rdo_fase_macro_sel != "",
                            rx.vstack(
                                rx.text("Atividade vinculada", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                                rx.select.root(
                                    rx.select.trigger(placeholder="Selecionar atividade", style=_CARD_INPUT),
                                    rx.select.content(
                                        rx.select.item("Nenhuma", value="__none__"),
                                        rx.foreach(
                                            RDOState.hub_atividades_filtradas,
                                            lambda opt: rx.select.item(opt["label"], value=opt["id"]),
                                        ),
                                        style={"background": "#0D201C", "border": "1px solid rgba(255,255,255,0.1)"},
                                    ),
                                    value=rx.cond(
                                        RDOState.rdo_atividade_id == "", "__none__", RDOState.rdo_atividade_id
                                    ),
                                    on_change=RDOState.set_rdo_atividade_id,
                                ),
                                spacing="1", width="100%",
                            ),
                            rx.fragment(),
                        ),
                        # Step 2b — hierarchy context badge (shown when a sub is selected)
                        rx.cond(
                            RDOState.rdo_ativ_nivel == "sub",
                            rx.hstack(
                                rx.icon(tag="git-branch", size=12, color="#8B5CF6"),
                                rx.text(
                                    "Sub-atividade  —  o progresso aqui atualiza automaticamente a micro e a macro pai.",
                                    font_size="11px",
                                    color="#8B5CF6",
                                    font_style="italic",
                                ),
                                spacing="2",
                                align="center",
                                padding="6px 10px",
                                border_radius="6px",
                                bg="rgba(139,92,246,0.08)",
                                border="1px solid rgba(139,92,246,0.25)",
                                width="100%",
                            ),
                            rx.fragment(),
                        ),
                        # Step 3 — campos de progresso
                        _progress_fields(),
                        # Step 4 — Pessoas hoje (efetivo nesta atividade)
                        rx.cond(
                            RDOState.rdo_atividade_id != "",
                            rx.vstack(
                                rx.text("Pessoas hoje nesta atividade", size="1", color="rgba(255,255,255,0.5)", font_family="var(--font-mono)"),
                                rx.hstack(
                                    rx.icon(tag="users", size=13, color="rgba(201,139,42,0.6)"),
                                    rx.el.input(
                                        type="number", min="0",
                                        placeholder="Ex: 4",
                                        default_value=RDOState.rdo_efetivo_primaria,
                                        on_change=RDOState.set_rdo_efetivo_primaria,
                                        style=dict(_CARD_INPUT, **{"width": "100px"}),
                                    ),
                                    rx.text("pessoas", size="2", color="rgba(255,255,255,0.3)"),
                                    spacing="2", align="center",
                                ),
                                # macro bloqueada — aviso
                                rx.cond(
                                    RDOState.macro_has_pending_micros,
                                    rx.hstack(
                                        rx.icon(tag="alert-triangle", size=13, color="#E05252"),
                                        rx.text(
                                            "Macro com sub-atividades pendentes — o progresso nao pode ser marcado como 100% ate que todas as micros sejam concluidas.",
                                            size="1", color="#E05252", font_style="italic",
                                        ),
                                        spacing="2", align="start",
                                        padding="6px 10px", border_radius="6px",
                                        bg="rgba(224,82,82,0.07)", border="1px solid rgba(224,82,82,0.25)",
                                        width="100%",
                                    ),
                                    rx.fragment(),
                                ),
                                spacing="1", width="100%",
                            ),
                            rx.fragment(),
                        ),
                        spacing="3", width="100%",
                    ),
                ),
            ),
            # Atividades adicionais
            rx.cond(
                RDOState.hub_atividades_options.length() > 0,
                rx.vstack(
                    rx.foreach(RDOState.rdo_extra_atividades, _extra_atividade_row),
                    rx.button(
                        rx.icon(tag="circle-plus", size=14),
                        "+ Outra atividade",
                        variant="ghost", size="1", cursor="pointer",
                        color="rgba(201,139,42,0.8)",
                        on_click=RDOState.add_extra_atividade,
                        _hover={"color": _COPPER},
                    ),
                    spacing="2", width="100%",
                ),
                rx.fragment(),
            ),
            # Atividades nao mapeadas
            rx.foreach(RDOState.rdo_novas_atividades, _nova_atividade_row),
            rx.button(
                rx.icon(tag="plus-circle", size=13),
                "Registrar atividade nao mapeada",
                variant="ghost", size="1", cursor="pointer",
                color="rgba(232,152,69,0.8)",
                on_click=RDOState.add_nova_atividade_nao_mapeada,
                _hover={"color": "#E89845"},
                style={"border": "1px dashed rgba(232,152,69,0.3)", "borderRadius": "6px", "padding": "6px 12px"},
            ),
            spacing="3", width="100%",
        ),
        title="ATIVIDADES EXECUTADAS",
        icon="git-branch",
    )


def _section_observacoes() -> rx.Component:
    return _section_card(
        rx.el.textarea(
            default_value=RDOState.rdo_observacoes,
            on_blur=RDOState.set_rdo_observacoes,
            placeholder="Descreva ocorrências gerais, problemas encontrados, decisões tomadas, pendências para o próximo dia…",
            rows="5",
            spell_check=True,
            lang="pt-BR",
            style={
                "background": _INPUT_BG,
                "border": f"1px solid {_BORDER}",
                "border_radius": "6px",
                "color": _TEXT,
                "padding": "10px 12px",
                "font_size": "14px",
                "width": "100%",
                "outline": "none",
                "_focus": {"border_color": _COPPER},
                "resize": "vertical",
            },
        ),
        title="Observações Gerais",
        icon="message-square",
    )


# ── Section: Ferramentas ─────────────────────────────────────────────────────

def _section_ferramentas() -> rx.Component:
    return _section_card(
        _upload_photo_zone(
            upload_id="rdo_ferramentas_upload",
            on_drop=RDOState.upload_ferramentas_files(rx.upload_files(upload_id="rdo_ferramentas_upload")),
            is_uploading=RDOState.is_uploading_ferramentas,
            existing_url=RDOState.ferramentas_foto_url,
            label="Foto das Ferramentas Limpas e Organizadas — toque para capturar",
            icon_name="wrench",
            on_remove=RDOState.remove_ferramentas_photo,
        ),
        title="Ferramentas Limpas e Organizadas",
        icon="wrench",
        badge=rx.cond(RDOState.ferramentas_foto_url != "", "✓", ""),
    )


# ── Section: Assinatura ──────────────────────────────────────────────────────

def _section_assinatura() -> rx.Component:
    return _section_card(
        rx.grid(
            rx.vstack(
                _label("Nome do Responsável"),
                _input(RDOState.signatory_name, RDOState.set_signatory_name,
                       placeholder="Nome completo do responsável", blur_mode=True),
                spacing="1",
            ),
            rx.vstack(
                _label("CPF ou RG"),
                _input(RDOState.signatory_doc, RDOState.set_signatory_doc,
                       placeholder="000.000.000-00", blur_mode=True),
                spacing="1",
            ),
            columns={"initial": "1", "sm": "2"},
            gap="12px",
            width="100%",
        ),
        rx.box(height="16px"),
        rx.vstack(
            _label("Assinatura Digital"),
            rx.text(
                "Assine com o dedo ou mouse abaixo. A assinatura é salva automaticamente ao enviar.",
                size="1",
                color=_MUTED,
                margin_bottom="6px",
            ),
            rx.el.canvas(
                id="sig-canvas",
                width="800",
                height="240",
                style={
                    "border": "1px solid rgba(255,255,255,0.15)",
                    "borderRadius": "6px",
                    "background": "rgba(255,255,255,0.04)",
                    "width": "100%",
                    "minHeight": "180px",
                    "cursor": "crosshair",
                    "touchAction": "none",
                    "display": "block",
                    "userSelect": "none",
                },
            ),
            rx.hstack(
                rx.button(
                    rx.icon("trash-2", size=13),
                    "Limpar",
                    on_click=RDOState.clear_signature_canvas,
                    size="1",
                    style={
                        "background": "rgba(224,82,82,0.10)",
                        "border": "1px solid rgba(224,82,82,0.3)",
                        "color": _DANGER,
                        "border_radius": "6px",
                        "cursor": "pointer",
                        "padding": "5px 14px",
                    },
                ),
                rx.button(
                    rx.icon("check", size=13),
                    "Confirmar Assinatura",
                    on_click=RDOState.capture_signature,
                    size="1",
                    style={
                        "background": "rgba(42,157,143,0.12)",
                        "border": "1px solid rgba(42,157,143,0.3)",
                        "color": _PATINA,
                        "border_radius": "6px",
                        "cursor": "pointer",
                        "padding": "5px 14px",
                    },
                ),
                rx.cond(
                    RDOState.signatory_sig_b64 != "",
                    rx.hstack(
                        rx.icon("check-circle", size=14, color=_PATINA),
                        rx.text("Assinatura capturada ✓", size="1", color=_PATINA, weight="medium"),
                        spacing="1",
                        align="center",
                    ),
                    rx.text("Aguardando confirmação…", size="1", color=_MUTED),
                ),
                spacing="2",
                align="center",
                margin_top="8px",
                flex_wrap="wrap",
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        title="Assinatura do Responsável",
        icon="pen-line",
        badge=rx.cond(RDOState.signatory_sig_b64 != "", "✓", ""),
    )


# ── Section: Eventos Condicionais (feature flag: conditional_fields) ─────────

def _section_eventos_condicionais() -> rx.Component:
    """Campos de Chuva e Acidente — aparecem somente se feature 'conditional_fields' estiver ativa."""
    return rx.cond(
        RDOState.feat_conditional_fields,
        _section_card(
            # ── Chuva ──
            rx.vstack(
                rx.hstack(
                    rx.checkbox(
                        "Houve chuva no período",
                        checked=RDOState.rdo_houve_chuva,
                        on_change=RDOState.set_rdo_houve_chuva,
                        color_scheme="amber",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    RDOState.rdo_houve_chuva,
                    rx.box(
                        rx.vstack(
                            _label("Intensidade da Chuva"),
                            _select(
                                RDOState.rdo_quantidade_chuva,
                                RDOState.set_rdo_quantidade_chuva,
                                RDOState.chuva_options,
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        margin_top="12px",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            rx.box(height="16px"),
            # ── Acidente ──
            rx.vstack(
                rx.hstack(
                    rx.checkbox(
                        "Houve acidente / ocorrência no dia",
                        checked=RDOState.rdo_houve_acidente,
                        on_change=RDOState.set_rdo_houve_acidente,
                        color_scheme="red",
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.cond(
                    RDOState.rdo_houve_acidente,
                    rx.box(
                        rx.vstack(
                            _label("Descrição da Ocorrência"),
                            rx.el.textarea(
                                default_value=RDOState.rdo_descricao_acidente,
                                on_blur=RDOState.set_rdo_descricao_acidente,
                                placeholder="Descreva o acidente/ocorrência, providências tomadas e envolvidos...",
                                rows="4",
                                spell_check=True,
                                lang="pt-BR",
                                style={
                                    "background": _INPUT_BG,
                                    "border": f"1px solid rgba(224,82,82,0.4)",
                                    "border_radius": "6px",
                                    "color": _TEXT,
                                    "padding": "10px 14px",
                                    "font_size": "15px",
                                    "width": "100%",
                                    "resize": "vertical",
                                    "outline": "none",
                                    "_focus": {"border_color": "#E05252"},
                                },
                            ),
                            spacing="1",
                            width="100%",
                        ),
                        margin_top="12px",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            title="Eventos do Dia",
            icon="alert-triangle",
        ),
        rx.fragment(),
    )


# ── Confirm Dialog ───────────────────────────────────────────────────────────

def _confirm_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Confirmar Envio"),
            rx.dialog.description(
                "O RDO será finalizado, o PDF gerado e enviado por e-mail. Deseja continuar?"
            ),
            rx.vstack(
                rx.hstack(
                    rx.icon("file-text", size=14, color=_MUTED),
                    rx.text("Contrato: ", rx.text.span(RDOState.rdo_contrato, color=_COPPER), size="2"),
                    spacing="2",
                ),
                rx.hstack(
                    rx.icon("calendar", size=14, color=_MUTED),
                    rx.text("Data: ", rx.text.span(RDOState.rdo_data_display), size="2"),
                    spacing="2",
                ),
                rx.hstack(
                    rx.icon("clipboard-check", size=14, color=_MUTED),
                    rx.text(
                        rx.text.span(RDOState.atividades_items.length()),
                        rx.text.span(" serviço(s) executado(s) · "),
                        rx.text.span(RDOState.evidencias_items.length()),
                        rx.text.span(" foto(s)"),
                        size="2",
                    ),
                    spacing="2",
                ),
                rx.cond(
                    RDOState.signatory_name != "",
                    rx.hstack(
                        rx.icon("pen-line", size=14, color=_MUTED),
                        rx.text("Responsável: ", rx.text.span(RDOState.signatory_name), size="2"),
                        spacing="2",
                    ),
                ),
                spacing="2",
                padding="16px",
                background="rgba(255,255,255,0.04)",
                border_radius="8px",
                margin_y="16px",
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button("Cancelar", variant="soft", color_scheme="gray", on_click=RDOState.close_confirm),
                ),
                rx.button(
                    rx.icon("send", size=14),
                    "Enviar RDO",
                    on_click=RDOState.submit_rdo,
                    loading=RDOState.is_submitting,
                    style={"background": _BTN_PRI, "color": "#fff", "border_radius": "6px"},
                ),
                justify="end",
                spacing="2",
            ),
            style={"max_width": "min(480px, 96vw)", "width": "100%"},
        ),
        open=RDOState.show_confirm_dialog,
    )


# ── Page ─────────────────────────────────────────────────────────────────────

def _sig_capture_init() -> rx.Component:
    """Placeholder — captura de assinatura ocorre em open_confirm via rx.call_script."""
    return rx.fragment()


def _photo_lightbox() -> rx.Component:
    """Lightbox fullscreen para visualizar fotos com zoom + download."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header bar
                rx.hstack(
                    rx.hstack(
                        rx.icon("image", size=14, color=_COPPER),
                        rx.dialog.title(
                            rx.text(
                                "Visualizar Foto",
                                size="2",
                                weight="bold",
                                color=_TEXT,
                                font_family="'Rajdhani', sans-serif",
                                letter_spacing="0.04em",
                            ),
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.spacer(),
                    rx.hstack(
                        rx.el.a(
                            rx.icon("download", size=14),
                            href=RDOState.photo_lightbox_url,
                            download=True,
                            target="_blank",
                            style={
                                "color": _COPPER,
                                "cursor": "pointer",
                                "padding": "6px 10px",
                                "border": f"1px solid rgba(201,139,42,0.4)",
                                "borderRadius": "6px",
                                "display": "flex",
                                "alignItems": "center",
                                "textDecoration": "none",
                                "background": "rgba(201,139,42,0.06)",
                            },
                        ),
                        rx.dialog.close(
                            rx.button(
                                rx.icon("x", size=14),
                                on_click=RDOState.close_lightbox,
                                size="1",
                                variant="ghost",
                                style={
                                    "color": _MUTED,
                                    "cursor": "pointer",
                                    "border": "1px solid rgba(255,255,255,0.08)",
                                    "border_radius": "6px",
                                    "padding": "6px",
                                },
                            )
                        ),
                        spacing="2",
                        align="center",
                    ),
                    align="center",
                    width="100%",
                    padding_bottom="12px",
                    border_bottom=f"1px solid rgba(255,255,255,0.07)",
                    margin_bottom="14px",
                ),
                # Foto — scrollable se muito alta
                rx.box(
                    rx.image(
                        src=RDOState.photo_lightbox_url,
                        max_width="100%",
                        max_height="100%",
                        object_fit="contain",
                        border_radius="8px",
                        style={
                            "display": "block",
                            "margin": "0 auto",
                            "boxShadow": "0 8px 32px rgba(0,0,0,0.5)",
                        },
                    ),
                    overflow_y="auto",
                    max_height="70vh",
                    width="100%",
                    style={"display": "flex", "alignItems": "center", "justifyContent": "center"},
                ),
                spacing="0",
                width="100%",
            ),
            style={
                "background": "#0B1A15",
                "border": "1px solid rgba(201,139,42,0.2)",
                "borderRadius": "14px",
                "padding": "18px 20px 20px",
                "maxWidth": "min(92vw, 900px)",
                "width": "92vw",
                "maxHeight": "92vh",
                "overflow": "hidden",
                "boxShadow": "0 24px 64px rgba(0,0,0,0.7)",
            },
        ),
        open=RDOState.photo_lightbox_url != "",
        on_open_change=RDOState.close_lightbox,
    )


def _mobile_bottom_bar() -> rx.Component:
    """Fixed bottom action bar — shown only on mobile."""
    return rx.box(
        rx.hstack(
            # Save draft icon button
            rx.tooltip(
                rx.button(
                    rx.icon("cloud-upload", size=16),
                    on_click=RDOState.save_draft,
                    style={
                        "background": "rgba(255,255,255,0.06)",
                        "border": f"1px solid {_BORDER}",
                        "color": _MUTED,
                        "border_radius": "9px",
                        "cursor": "pointer",
                        "height": "50px",
                        "width": "50px",
                        "flex_shrink": "0",
                    },
                ),
                content="Salvar rascunho",
            ),
            # Send button
            rx.button(
                rx.icon("send", size=16),
                "Finalizar e Enviar RDO",
                on_click=RDOState.open_confirm,
                loading=RDOState.is_submitting,
                class_name="rdo-submit-btn",
            ),
            spacing="2",
            width="100%",
        ),
        class_name="rdo-bottom-bar",
        display=["flex", "none"],  # visible mobile only
    )


def _standalone_submit_overlay() -> rx.Component:
    """Minimal RDO submit overlay — position:fixed, root-level for rdo_form standalone."""
    _MUTED_OVERLAY = "rgba(255,255,255,0.45)"
    _COPPER_OVERLAY = "#C98B2A"
    steps = [
        ("[save]", "Salvando RDO no banco de dados…"),
        ("[doc]", "Gerando PDF…"),
        ("☁️", "Enviando PDF para a nuvem…"),
        ("✅", "Finalizando e enviando e-mails…"),
    ]

    def _step_row(icon: str, label: str) -> rx.Component:
        active = RDOState.submit_status.contains(icon)
        return rx.hstack(
            rx.text(icon, font_size="18px"),
            rx.text(label, size="2", color=rx.cond(active, "white", _MUTED_OVERLAY),
                    font_weight=rx.cond(active, "600", "400")),
            spacing="3", align="center",
            opacity=rx.cond(active, "1", "0.45"),
            style={"transition": "opacity 0.3s"},
        )

    return rx.cond(
        RDOState.is_submitting,
        rx.box(
            rx.vstack(
                rx.spinner(size="3", color=_COPPER_OVERLAY),
                rx.text("Processando seu RDO", size="4", weight="bold", color="white",
                        font_family="'Rajdhani', sans-serif", letter_spacing="0.5px"),
                rx.vstack(
                    *[_step_row(icon, label) for icon, label in steps],
                    spacing="3",
                    padding="16px 20px",
                    background="rgba(255,255,255,0.05)",
                    border="1px solid rgba(255,255,255,0.1)",
                    border_radius="6px",
                    width="100%",
                ),
                rx.text("Não feche esta tela", size="1", color=_MUTED_OVERLAY, opacity="0.6"),
                spacing="4", align="center",
                padding="32px 28px",
                background="#0d2219",
                border="1px solid rgba(201,139,42,0.35)",
                border_radius="8px",
                max_width="340px", width="90vw",
                box_shadow="0 32px 80px rgba(0,0,0,0.8)",
            ),
            position="fixed", top="0", left="0", right="0", bottom="0",
            display="flex", align_items="center", justify_content="center",
            background="rgba(0,0,0,0.75)",
            z_index="9999",
            style={"backdropFilter": "blur(4px)"},
        ),
    )


def rdo_form_page() -> rx.Component:
    return rx.box(
        _sig_capture_init(),
        _sticky_header(),
        _rdo_progress_tracker(),
        rx.box(
            _draft_banner(),
            # 1. Header info (locked badges + editable: data, clima, turno, orientação, interrupção)
            _section_header_info(),
            rx.box(height="14px"),
            # 2. GPS Check-in / Check-out (with auto hora badge + km calc)
            _section_gps(),
            rx.box(height="14px"),
            # 3. Foto EPIs
            _section_epi(),
            rx.box(height="14px"),
            # 4. Atividades Executadas (cronograma integration)
            _section_cronograma(),
            rx.box(height="14px"),
            # 5. Fotos do Dia (evidências)
            _section_evidencias(),
            rx.box(height="14px"),
            # 6. Observações
            _section_observacoes(),
            rx.box(height="14px"),
            # 7. Ferramentas Limpas e Organizadas
            _section_ferramentas(),
            rx.box(height="14px"),
            # 8. Eventos Condicionais (Chuva / Acidente) — feature flag
            _section_eventos_condicionais(),
            rx.cond(
                RDOState.feat_conditional_fields,
                rx.box(height="14px"),
                rx.fragment(),
            ),
            # 9. Assinatura
            _section_assinatura(),
            rx.box(height="24px"),
            # Desktop submit — hidden on mobile (bottom bar handles it)
            rx.box(
                rx.button(
                    rx.icon("send", size=16),
                    "Finalizar e Enviar RDO",
                    on_click=RDOState.open_confirm,
                    size="3",
                    loading=RDOState.is_submitting,
                    style={
                        "background": _BTN_PRI,
                        "color": "#fff",
                        "border_radius": "9px",
                        "font_weight": "700",
                        "font_family": "'Rajdhani', sans-serif",
                        "letter_spacing": "0.06em",
                        "text_transform": "uppercase",
                        "font_size": "14px",
                        "padding": "0 32px",
                        "height": "50px",
                        "cursor": "pointer",
                        "box_shadow": "0 4px 20px rgba(201,139,42,0.35)",
                        "_hover": {"box_shadow": "0 6px 28px rgba(201,139,42,0.5)", "transform": "translateY(-1px)"},
                        "transition": "all 0.15s ease",
                    },
                ),
                display=["none", "flex"],
                justify_content="flex-end",
            ),
            # Extra space for mobile bottom bar
            rx.box(height=["80px", "24px"]),
            padding=["14px", "24px"],
            max_width="960px",
            margin="0 auto",
            class_name="rdo-form-content",
        ),
        _mobile_bottom_bar(),
        _confirm_dialog(),
        _photo_lightbox(),
        _standalone_submit_overlay(),
        min_height="100vh",
        background=_BG,
    )
