"""
Editor de Dados — Inteligência Bomtempo
Acesso direto às tabelas do banco de dados com tema Deep Tectonic.
"""
import reflex as rx
from bomtempo.state.edit_state import EditState
from bomtempo.state.global_state import GlobalState
from bomtempo.core import styles as S
from bomtempo.components.skeletons import page_centered_loader

# ── Tema escuro para o rx.data_editor (Glide Data Grid) ─────────────────────
_GDG_DARK_THEME = {
    "accentColor": S.COPPER,
    "accentLight": "rgba(201,139,42,0.15)",
    "textDark": "#E0E0E0",
    "textMedium": "#889999",
    "textLight": "#5a7070",
    "textHeader": S.COPPER,
    "textHeaderSelected": "#FFFFFF",
    # Synced with S.BG_ELEVATED so the empty canvas area to the right
    # of the last column blends seamlessly with the container background
    "bgCell": S.BG_ELEVATED,        # "#142420"
    "bgCellMedium": "#122020",
    "bgHeader": S.BG_DEPTH,         # "#081210"
    "bgHeaderHasFocus": "#0c1a17",
    "borderColor": "rgba(255,255,255,0.06)",
    "drilldownBorder": S.COPPER,
    "linkColor": S.PATINA,
    "headerFontStyle": "700 11px Rajdhani",
    "baseFontStyle": "13px JetBrains Mono",
    "fontFamily": "'JetBrains Mono', monospace",
}


# ── Page Header Banner ───────────────────────────────────────────────────────

def _page_header() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                # Ícone + título
                rx.hstack(
                    rx.box(
                        rx.icon(tag="database", size=22, color=S.COPPER),
                        bg="rgba(201,139,42,0.12)",
                        padding="10px",
                        border_radius="10px",
                        border=f"1px solid {S.BORDER_ACCENT}",
                    ),
                    rx.vstack(
                        rx.text(
                            "EDITOR DE DADOS",
                            font_family=S.FONT_TECH,
                            font_size="22px",
                            font_weight="700",
                            color=S.TEXT_WHITE,
                            letter_spacing="0.04em",
                            line_height="1",
                        ),
                        rx.text(
                            "Gerenciamento direto de tabelas do banco de dados",
                            font_size="12px",
                            color=S.TEXT_MUTED,
                            letter_spacing="0.01em",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.spacer(),
                # Status pills
                rx.hstack(
                    # Unsaved changes indicator
                    rx.cond(
                        EditState.has_unsaved_changes,
                        rx.hstack(
                            rx.box(
                                width="6px",
                                height="6px",
                                border_radius="50%",
                                bg=S.WARNING,
                                box_shadow=f"0 0 6px {S.WARNING}",
                                class_name="stepper-dot-active",
                            ),
                            rx.text(
                                "alterações não salvas",
                                font_size="11px",
                                color=S.WARNING,
                                font_family=S.FONT_MONO,
                                font_weight="600",
                                white_space="nowrap",
                            ),
                            spacing="2",
                            align="center",
                            padding_x="10px",
                            padding_y="4px",
                            bg=S.WARNING_BG,
                            border_radius="20px",
                            border=f"1px solid rgba(245,158,11,0.3)",
                        ),
                    ),
                    rx.cond(
                        EditState.raw_data.length() > 0,
                        rx.hstack(
                            rx.box(
                                width="6px",
                                height="6px",
                                border_radius="50%",
                                bg=S.SUCCESS,
                                box_shadow=f"0 0 6px {S.SUCCESS}",
                            ),
                            rx.text(
                                EditState.raw_data.length().to_string() + " registros",
                                font_size="12px",
                                color=S.SUCCESS,
                                font_family=S.FONT_MONO,
                                font_weight="500",
                            ),
                            spacing="2",
                            align="center",
                            padding_x="12px",
                            padding_y="5px",
                            bg="rgba(42,157,143,0.1)",
                            border_radius="20px",
                            border=f"1px solid rgba(42,157,143,0.25)",
                        ),
                        rx.hstack(
                            rx.box(
                                width="6px",
                                height="6px",
                                border_radius="50%",
                                bg=S.TEXT_MUTED,
                            ),
                            rx.text(
                                "Sem dados",
                                font_size="12px",
                                color=S.TEXT_MUTED,
                                font_family=S.FONT_MONO,
                            ),
                            spacing="2",
                            align="center",
                            padding_x="12px",
                            padding_y="5px",
                            bg="rgba(255,255,255,0.03)",
                            border_radius="20px",
                            border=f"1px solid {S.BORDER_SUBTLE}",
                        ),
                    ),
                    rx.box(
                        rx.text(
                            EditState.selected_tabela,
                            font_size="11px",
                            color=S.COPPER,
                            font_family=S.FONT_MONO,
                            font_weight="600",
                            text_transform="uppercase",
                            letter_spacing="0.06em",
                        ),
                        padding_x="12px",
                        padding_y="5px",
                        bg=S.COPPER_GLOW,
                        border_radius="20px",
                        border=f"1px solid {S.BORDER_ACCENT}",
                    ),
                    spacing="2",
                    align="center",
                ),
                width="100%",
                align="center",
            ),
            # Linha divisória copper
            rx.box(
                height="1px",
                width="100%",
                background=f"linear-gradient(90deg, {S.COPPER} 0%, rgba(201,139,42,0.2) 60%, transparent 100%)",
                margin_top="4px",
            ),
            spacing="3",
            width="100%",
        ),
        margin_bottom="14px",
    )


# ── Toolbar ──────────────────────────────────────────────────────────────────

def _select(items, value, on_change, placeholder="", width="140px") -> rx.Component:
    """Select compacto para a command bar."""
    return rx.select(
        items,
        value=value,
        on_change=on_change,
        placeholder=placeholder,
        width=width,
        size="2",
        variant="surface",
        color_scheme="amber",
    )


def _ctx_field(tag: str, items, value, on_change, placeholder="", width="130px") -> rx.Component:
    """Campo de contexto com label inline — alinha na mesma baseline dos botões."""
    return rx.hstack(
        rx.text(
            tag,
            font_size="9px",
            font_family=S.FONT_TECH,
            font_weight="700",
            color="rgba(136,153,153,0.65)",
            letter_spacing="0.12em",
            white_space="nowrap",
            user_select="none",
        ),
        _select(items, value, on_change, placeholder=placeholder, width=width),
        spacing="2",
        align="center",
    )


def _toolbar() -> rx.Component:
    """Command bar — 2-row responsive layout for small screens.
    Row 1: Context filters (Tabela, Projeto, Contrato, Carregar)
    Row 2: Actions (Nova Linha, Deletar, Desfazer | Exportar, Importar | Salvar)
    """

    # ── Shared button style with hover micro-animations ──────────────────
    _action_btn_style = {
        "font_family": S.FONT_TECH,
        "font_weight": "600",
        "font_size": "11px",
        "cursor": "pointer",
        "white_space": "nowrap",
        "transition": "all 0.2s ease",
        "_hover": {
            "transform": "translateY(-1px)",
            "box_shadow": "0 4px 12px rgba(0,0,0,0.3)",
        },
    }

    def _thin_sep() -> rx.Component:
        """Minor separator inside a zone."""
        return rx.box(
            width="1px", height="24px",
            bg=S.BORDER_SUBTLE,
            flex_shrink="0",
        )

    # ── Row 1: Context Filters ───────────────────────────────────────────
    row_filters = rx.hstack(
        # Tabela
        _ctx_field(
            "TABELA",
            EditState.tabelas,
            EditState.selected_tabela,
            EditState.set_selected_tabela,
            width="130px",
        ),
        _thin_sep(),
        # Projeto
        _ctx_field(
            "PROJETO",
            EditState.projetos,
            EditState.selected_projeto,
            EditState.set_selected_projeto,
            placeholder="Todos",
            width="150px",
        ),
        # Contrato
        _ctx_field(
            "CONTRATO",
            EditState.contratos,
            EditState.selected_contrato,
            EditState.set_selected_contrato,
            placeholder="Todos",
            width="150px",
        ),
        # Filtro ativo badge
        rx.cond(
            (EditState.selected_projeto != "") | (EditState.selected_contrato != ""),
            rx.hstack(
                rx.box(width="5px", height="5px", border_radius="50%", bg=S.WARNING, flex_shrink="0"),
                rx.text("filtro ativo", font_size="8px", color=S.WARNING,
                        font_family=S.FONT_MONO, font_weight="600", white_space="nowrap"),
                rx.icon(tag="x", size=9, color=S.WARNING, cursor="pointer",
                        on_click=EditState.clear_filters),
                spacing="1", align="center",
                padding_x="6px", padding_y="2px",
                bg="rgba(245,158,11,0.07)",
                border_radius="8px",
                border="1px solid rgba(245,158,11,0.18)",
                flex_shrink="0",
            ),
        ),
        # Carregar button
        rx.tooltip(
            rx.button(
                rx.cond(EditState.is_loading_table, rx.spinner(size="2"), rx.icon(tag="database-zap", size=14)),
                rx.cond(EditState.is_loading_table, "Carregando...", "Carregar"),
                on_click=EditState.load_table,
                disabled=EditState.is_loading_table,
                size="2",
                style={
                    "background": S.COPPER,
                    "color": "white",
                    "font_family": S.FONT_TECH,
                    "font_weight": "700",
                    "font_size": "11px",
                    "letter_spacing": "0.04em",
                    "cursor": "pointer",
                    "opacity": rx.cond(EditState.is_loading_table, "0.7", "1"),
                    "white_space": "nowrap",
                    "flex_shrink": "0",
                    "transition": "all 0.2s ease",
                    "_hover": {
                        "background": S.COPPER_LIGHT,
                        "transform": "translateY(-1px)",
                        "box_shadow": f"0 4px 16px rgba(201,139,42,0.4)",
                    },
                },
            ),
            content="Busca os registros da tabela. Projeto/Contrato são opcionais.",
            side="bottom",
        ),
        spacing="2",
        align="center",
        flex_wrap="wrap",
        row_gap="8px",
        width="100%",
    )

    # ── Row 2: Action Buttons ────────────────────────────────────────────
    row_actions = rx.hstack(
        # ── Data actions group ───────────────────────────────────────
        rx.tooltip(
            rx.button(
                rx.icon(tag="plus", size=13),
                "Nova Linha",
                on_click=EditState.add_row,
                size="2",
                variant="soft",
                color_scheme="teal",
                style=_action_btn_style,
            ),
            content="Insere uma linha em branco no topo do grid (salve para persistir)",
            side="bottom",
        ),
        rx.tooltip(
            rx.button(
                rx.icon(tag="trash-2", size=13),
                "Deletar",
                on_click=EditState.delete_selected_row,
                size="2",
                variant="soft",
                color_scheme="red",
                disabled=EditState.selected_row_idx < 0,
                style={
                    **_action_btn_style,
                    "cursor": rx.cond(EditState.selected_row_idx >= 0, "pointer", "not-allowed"),
                    "opacity": rx.cond(EditState.selected_row_idx >= 0, "1", "0.35"),
                },
            ),
            content=rx.cond(
                EditState.selected_row_idx >= 0,
                "Remove a linha selecionada do banco permanentemente",
                "Clique em uma célula para selecionar a linha",
            ),
            side="bottom",
        ),
        rx.tooltip(
            rx.button(
                rx.icon(tag="undo-2", size=13),
                "Desfazer",
                rx.cond(
                    EditState.undo_count > 0,
                    rx.badge(
                        EditState.undo_count.to_string(),
                        color_scheme="amber",
                        variant="soft",
                        size="1",
                        style={
                            "font_family": S.FONT_MONO,
                            "font_size": "9px",
                            "padding": "0 3px",
                        },
                    ),
                ),
                on_click=EditState.undo_last,
                disabled=EditState.undo_count == 0,
                size="2",
                variant="soft",
                color_scheme="amber",
                style={
                    **_action_btn_style,
                    "cursor": rx.cond(EditState.undo_count > 0, "pointer", "not-allowed"),
                    "opacity": rx.cond(EditState.undo_count > 0, "1", "0.35"),
                    "gap": "4px",
                },
            ),
            content=rx.cond(
                EditState.undo_count > 0,
                "Desfaz a última edição de célula ou adição de linha",
                "Nenhuma ação para desfazer",
            ),
            side="bottom",
        ),

        _thin_sep(),

        # ── Import/Export group ───────────────────────────────────────
        rx.tooltip(
            rx.button(
                rx.icon(tag="download", size=13),
                "Exportar",
                on_click=EditState.download_excel,
                size="2",
                variant="soft",
                color_scheme="blue",
                style=_action_btn_style,
            ),
            content="Baixa os dados atuais do grid como planilha Excel",
            side="bottom",
        ),
        rx.upload(
            rx.tooltip(
                rx.button(
                    rx.icon(tag="cloud-upload", size=13, color=S.COPPER),
                    "Importar",
                    size="2",
                    variant="soft",
                    color_scheme="gray",
                    style={
                        **_action_btn_style,
                        "color": S.COPPER,
                        "border": f"1px solid {S.BORDER_ACCENT}",
                    },
                ),
                content="Importa CSV ou XLSX — mostra preview antes de absorver no grid",
                side="bottom",
            ),
            id="csv_upload",
            accept={
                "text/csv": [".csv"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
            },
            max_files=1,
            no_drag=True,
            no_keyboard=True,
            border="none",
            padding="0",
            background="transparent",
            style={"min_height": "auto", "display": "inline-block"},
            on_drop=EditState.handle_csv_upload(rx.upload_files(upload_id="csv_upload")),
        ),

        # ── Spacer → Save CTA right-aligned ──────────────────────────
        rx.spacer(),

        rx.cond(
            EditState.raw_data.length() > 0,
            rx.tooltip(
                rx.button(
                    rx.cond(EditState.is_saving, rx.spinner(size="2"), rx.icon(tag="save", size=13)),
                    rx.cond(EditState.is_saving, "Salvando...", "Salvar no Banco"),
                    on_click=EditState.commit_csv_upload,
                    disabled=EditState.is_saving,
                    size="2",
                    style={
                        "background": rx.cond(
                            EditState.has_unsaved_changes,
                            f"linear-gradient(135deg, {S.COPPER} 0%, {S.COPPER_LIGHT} 100%)",
                            "rgba(201,139,42,0.18)",
                        ),
                        "color": rx.cond(EditState.has_unsaved_changes, "#0A1F1A", S.COPPER),
                        "border": rx.cond(
                            EditState.has_unsaved_changes,
                            "none",
                            f"1px solid {S.BORDER_ACCENT}",
                        ),
                        "font_family": S.FONT_TECH,
                        "font_weight": "700",
                        "font_size": "12px",
                        "letter_spacing": "0.04em",
                        "box_shadow": rx.cond(
                            EditState.has_unsaved_changes,
                            "0 0 20px rgba(201,139,42,0.5)",
                            "none",
                        ),
                        "cursor": "pointer",
                        "flex_shrink": "0",
                        "white_space": "nowrap",
                        "_hover": {
                            "box_shadow": "0 0 28px rgba(201,139,42,0.7)",
                            "transform": "translateY(-1px)",
                            "background": f"linear-gradient(135deg, {S.COPPER_LIGHT} 0%, {S.COPPER} 100%)",
                            "color": "#0A1F1A",
                        },
                        "transition": "all 0.2s ease",
                    },
                ),
                content=rx.cond(
                    EditState.has_unsaved_changes,
                    "Persiste todas as alterações via upsert (atualiza pelo ID, insere novos)",
                    "Nenhuma alteração pendente",
                ),
                side="bottom",
            ),
        ),

        spacing="2",
        align="center",
        flex_wrap="wrap",
        row_gap="8px",
        width="100%",
    )

    return rx.box(
        # ── Copper top accent line ──────────────────────────────────────────
        rx.box(
            position="absolute",
            top="0", left="0", right="0",
            height="2px",
            background=f"linear-gradient(90deg, transparent 0%, {S.COPPER}50 25%, {S.COPPER} 50%, {S.COPPER}50 75%, transparent 100%)",
            pointer_events="none",
        ),

        # ── Content: 2 rows ─────────────────────────────────────────────────
        rx.vstack(
            row_filters,
            # Subtle divider between rows
            rx.box(
                height="1px",
                width="100%",
                background=f"linear-gradient(90deg, transparent 0%, {S.BORDER_SUBTLE} 20%, {S.BORDER_SUBTLE} 80%, transparent 100%)",
            ),
            row_actions,
            spacing="2",
            width="100%",
        ),

        # ── Container ───────────────────────────────────────────────────────
        position="relative",
        width="100%",
        bg=S.BG_DEPTH,
        border=f"1px solid {S.BORDER_SUBTLE}",
        border_radius="12px",
        padding="10px 16px",
        overflow="visible",
        box_shadow=f"0 2px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
        margin_bottom="12px",
        class_name="animate-enter",
    )


# ── Empty State ──────────────────────────────────────────────────────────────

def _empty_state() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.box(
                rx.icon(tag="database", size=40, color=S.COPPER),
                bg="rgba(201,139,42,0.08)",
                padding="24px",
                border_radius="50%",
                border=f"1px solid {S.BORDER_ACCENT}",
            ),
            rx.text(
                "Nenhuma tabela carregada",
                font_size="16px",
                font_weight="600",
                color=S.TEXT_PRIMARY,
                font_family=S.FONT_TECH,
                letter_spacing="0.02em",
            ),
            rx.vstack(
                rx.hstack(
                    rx.box(
                        rx.text("1", font_size="11px", color=S.COPPER, font_weight="700"),
                        bg=S.COPPER_GLOW,
                        border_radius="50%",
                        width="20px",
                        height="20px",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        flex_shrink="0",
                    ),
                    rx.text("Selecione a Tabela — Projeto e Contrato são filtros opcionais", font_size="12px", color=S.TEXT_MUTED),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.box(
                        rx.text("2", font_size="11px", color=S.COPPER, font_weight="700"),
                        bg=S.COPPER_GLOW,
                        border_radius="50%",
                        width="20px",
                        height="20px",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        flex_shrink="0",
                    ),
                    rx.text('Clique em "Carregar" para buscar os registros do banco', font_size="12px", color=S.TEXT_MUTED),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.box(
                        rx.text("3", font_size="11px", color=S.COPPER, font_weight="700"),
                        bg=S.COPPER_GLOW,
                        border_radius="50%",
                        width="20px",
                        height="20px",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        flex_shrink="0",
                    ),
                    rx.text('Ou importe um arquivo CSV / XLSX via "Importar Planilha"', font_size="12px", color=S.TEXT_MUTED),
                    spacing="2",
                    align="center",
                ),
                spacing="3",
                align="start",
                padding="16px 20px",
                bg="rgba(255,255,255,0.02)",
                border_radius="10px",
                border=f"1px solid {S.BORDER_SUBTLE}",
            ),
            align="center",
            spacing="4",
        ),
        height="62vh",
    )


# ── Data Grid ────────────────────────────────────────────────────────────────

def _data_grid() -> rx.Component:
    return rx.box(
        # Loading overlay — cobre o grid enquanto busca dados
        rx.cond(
            EditState.is_loading_table,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color=S.COPPER),
                    rx.text(
                        "Carregando dados...",
                        font_size="13px",
                        color=S.TEXT_MUTED,
                        font_family=S.FONT_TECH,
                        letter_spacing="0.05em",
                    ),
                    spacing="3",
                    align="center",
                ),
                position="absolute",
                top="0",
                left="0",
                right="0",
                bottom="0",
                bg="rgba(3,5,4,0.75)",
                z_index="10",
                border_radius="16px",
            ),
        ),
        rx.cond(
            EditState.raw_data.length() > 0,
            rx.data_editor(
                data=EditState.editor_data,
                columns=EditState.editor_columns,
                on_cell_edited=EditState.on_cell_edited,
                on_cell_clicked=EditState.on_cell_clicked,
                on_cell_activated=EditState.on_cell_activated,
                width="100%",
                height="64vh",
                smooth_scroll_x=True,
                smooth_scroll_y=True,
                theme=_GDG_DARK_THEME,
                row_height=36,
                header_height=40,
            ),
            _empty_state(),
        ),
        position="relative",
        bg=S.BG_ELEVATED,
        border_radius="16px",
        border=f"1px solid {S.BORDER_SUBTLE}",
        overflow="hidden",
        box_shadow="0 4px 24px rgba(0,0,0,0.35)",
        flex="1",
        class_name="animate-enter delay-100",
    )


# ── Preview Dialog ───────────────────────────────────────────────────────────

def _preview_dialog() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            # Header com ícone copper
            rx.hstack(
                rx.box(
                    rx.icon(tag="file-search", size=18, color=S.COPPER),
                    bg=S.COPPER_GLOW,
                    padding="8px",
                    border_radius="8px",
                    border=f"1px solid {S.BORDER_ACCENT}",
                ),
                rx.vstack(
                    rx.alert_dialog.title(
                        "Resumo do Arquivo",
                        font_family=S.FONT_TECH,
                        font_size="16px",
                        font_weight="700",
                        color=S.TEXT_WHITE,
                        letter_spacing="0.03em",
                    ),
                    rx.text(
                        "Revise antes de absorver os dados na tela",
                        font_size="11px",
                        color=S.TEXT_MUTED,
                    ),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
                width="100%",
                margin_bottom="16px",
            ),
            # Linha divisória
            rx.box(
                height="1px",
                width="100%",
                background=f"linear-gradient(90deg, {S.COPPER} 0%, rgba(201,139,42,0.1) 100%)",
                margin_bottom="16px",
            ),
            rx.alert_dialog.description(
                rx.vstack(
                    # Stats em card mono
                    rx.box(
                        rx.text(
                            EditState.preview_stats,
                            color=S.TEXT_PRIMARY,
                            white_space="pre-line",
                            font_family=S.FONT_MONO,
                            font_size="12px",
                            line_height="2",
                        ),
                        bg="rgba(0,0,0,0.2)",
                        border=f"1px solid {S.BORDER_SUBTLE}",
                        border_radius="8px",
                        padding="14px 16px",
                        width="100%",
                    ),
                    # Aviso amarelo
                    rx.hstack(
                        rx.icon(tag="triangle-alert", size=14, color=S.WARNING),
                        rx.text(
                            "Os dados entram no grid para revisão. Use 'Salvar no Banco' para efetivar o upsert.",
                            font_size="11px",
                            color=S.WARNING,
                            line_height="1.5",
                        ),
                        spacing="2",
                        align="start",
                        padding="10px 14px",
                        bg=S.WARNING_BG,
                        border_radius="8px",
                        border=f"1px solid rgba(245,158,11,0.25)",
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                )
            ),
            # Botões
            rx.flex(
                rx.alert_dialog.cancel(
                    rx.button(
                        rx.icon(tag="x", size=14),
                        "Rejeitar Arquivo",
                        variant="soft",
                        color_scheme="red",
                        on_click=EditState.cancel_preview_upload,
                        style={
                            "font_family": S.FONT_TECH,
                            "font_weight": "600",
                            "cursor": "pointer",
                        },
                    )
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.icon(tag="check", size=14),
                        "Absorver no Grid",
                        on_click=EditState.confirm_preview_upload,
                        style={
                            "background": S.PATINA,
                            "color": "white",
                            "font_family": S.FONT_TECH,
                            "font_weight": "700",
                            "cursor": "pointer",
                            "_hover": {"background": S.PATINA_DARK},
                        },
                    )
                ),
                spacing="3",
                margin_top="20px",
                justify="end",
            ),
            # Estilos do dialog
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_ACCENT}",
            border_radius="16px",
            box_shadow="0 16px 48px rgba(0,0,0,0.6)",
            padding="24px",
            max_width="480px",
        ),
        open=EditState.show_preview_dialog,
    )


# ── Inline Cell Edit Dialog ──────────────────────────────────────────────────

def _edit_cell_dialog() -> rx.Component:
    """Modal de edição inline — abre com duplo-clique na célula.
    Fallback universal para produção. Enter=salvar, Escape=cancelar.
    """
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            # Header
            rx.hstack(
                rx.box(
                    rx.icon(tag="pencil", size=16, color=S.COPPER),
                    bg=S.COPPER_GLOW,
                    padding="8px",
                    border_radius="8px",
                    border=f"1px solid {S.BORDER_ACCENT}",
                ),
                rx.vstack(
                    rx.text(
                        "Editar Célula",
                        font_family=S.FONT_TECH,
                        font_size="15px",
                        font_weight="700",
                        color=S.TEXT_WHITE,
                        letter_spacing="0.03em",
                    ),
                    rx.text(
                        EditState.edit_modal_col_name,
                        font_size="11px",
                        color=S.COPPER,
                        font_family=S.FONT_MONO,
                        font_weight="600",
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                    ),
                    spacing="0",
                    align="start",
                ),
                spacing="3",
                align="center",
                width="100%",
                margin_bottom="12px",
            ),
            # Divider
            rx.box(
                height="1px",
                width="100%",
                background=f"linear-gradient(90deg, {S.COPPER} 0%, rgba(201,139,42,0.1) 100%)",
                margin_bottom="14px",
            ),
            # Row info
            rx.hstack(
                rx.icon(tag="info", size=12, color=S.TEXT_MUTED),
                rx.text(
                    "Linha " + (EditState.edit_modal_row + 1).to(str),
                    font_size="10px",
                    color=S.TEXT_MUTED,
                    font_family=S.FONT_MONO,
                ),
                spacing="1",
                align="center",
                margin_bottom="8px",
            ),
            # Input field
            rx.input(
                value=EditState.edit_modal_value,
                on_change=EditState.set_edit_modal_value,
                on_key_down=EditState.handle_edit_key_down,
                debounce_timeout=150,
                placeholder="Valor da célula...",
                auto_focus=True,
                size="3",
                style={
                    "background": "rgba(0,0,0,0.3)",
                    "border": f"1px solid {S.BORDER_ACCENT}",
                    "color": S.TEXT_WHITE,
                    "font_family": S.FONT_MONO,
                    "font_size": "14px",
                    "border_radius": "8px",
                    "width": "100%",
                    "_focus": {
                        "border_color": S.COPPER,
                        "box_shadow": f"0 0 12px rgba(201,139,42,0.25)",
                    },
                },
            ),
            # Keyboard hint
            rx.hstack(
                rx.text("Enter", font_size="9px", color=S.COPPER, font_family=S.FONT_MONO,
                        font_weight="700", padding="1px 5px",
                        bg="rgba(201,139,42,0.1)", border_radius="3px",
                        border=f"1px solid {S.BORDER_ACCENT}"),
                rx.text("salvar", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                rx.text("Esc", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO,
                        font_weight="700", padding="1px 5px",
                        bg="rgba(255,255,255,0.04)", border_radius="3px",
                        border=f"1px solid {S.BORDER_SUBTLE}"),
                rx.text("cancelar", font_size="9px", color=S.TEXT_MUTED, font_family=S.FONT_MONO),
                spacing="1",
                align="center",
                margin_top="6px",
            ),
            # Buttons
            rx.flex(
                rx.alert_dialog.cancel(
                    rx.button(
                        rx.icon(tag="x", size=14),
                        "Cancelar",
                        variant="soft",
                        color_scheme="red",
                        on_click=EditState.cancel_edit_modal,
                        style={
                            "font_family": S.FONT_TECH,
                            "font_weight": "600",
                            "cursor": "pointer",
                        },
                    ),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.icon(tag="check", size=14),
                        "Salvar",
                        on_click=EditState.confirm_edit_modal,
                        style={
                            "background": f"linear-gradient(135deg, {S.COPPER} 0%, {S.COPPER_LIGHT} 100%)",
                            "color": "#0A1F1A",
                            "font_family": S.FONT_TECH,
                            "font_weight": "700",
                            "cursor": "pointer",
                            "_hover": {
                                "box_shadow": f"0 0 20px rgba(201,139,42,0.5)",
                                "transform": "translateY(-1px)",
                            },
                            "transition": "all 0.2s ease",
                        },
                    ),
                ),
                spacing="3",
                margin_top="16px",
                justify="end",
            ),
            # Dialog styling
            bg=S.BG_ELEVATED,
            border=f"1px solid {S.BORDER_ACCENT}",
            border_radius="16px",
            box_shadow="0 16px 48px rgba(0,0,0,0.6)",
            padding="20px",
            max_width="420px",
        ),
        open=EditState.edit_modal_open,
    )


# ── Acesso Negado ────────────────────────────────────────────────────────────

def _acesso_negado() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.box(
                rx.icon(tag="shield-alert", size=48, color=S.WARNING),
                bg=S.WARNING_BG,
                padding="24px",
                border_radius="50%",
                border=f"1px solid rgba(245,158,11,0.3)",
            ),
            rx.text(
                "ACESSO RESTRITO",
                font_family=S.FONT_TECH,
                font_size="20px",
                font_weight="700",
                color=S.TEXT_WHITE,
                letter_spacing="0.06em",
            ),
            rx.text(
                "Apenas usuários com permissão Administrador ou data_edit podem acessar o Editor de Dados.",
                font_size="13px",
                color=S.TEXT_MUTED,
                text_align="center",
                max_width="360px",
                line_height="1.6",
            ),
            align="center",
            spacing="4",
            padding="48px",
            bg=S.BG_GLASS,
            backdrop_filter="blur(12px)",
            border=f"1px solid rgba(245,158,11,0.2)",
            border_radius="20px",
            box_shadow="0 8px 32px rgba(0,0,0,0.5)",
        ),
        height="100vh",
    )


# ── Overlay de Loading Global ────────────────────────────────────────────────

def _loading_overlay() -> rx.Component:
    """Full-screen enterprise loader — replaces the plain spinner."""
    return rx.cond(
        EditState.is_loading_table | EditState.is_saving,
        rx.box(
            rx.center(
                rx.box(
                    page_centered_loader(
                        title=rx.cond(EditState.is_saving, "SALVANDO DADOS", "CARREGANDO TABELA"),
                        subtitle=rx.cond(
                            EditState.is_saving,
                            "Persistindo registros no banco de dados…",
                            "Buscando registros no banco de dados…",
                        ),
                        icon="database",
                    ),
                    max_width="480px",
                    width="90vw",
                ),
                width="100%",
                height="100%",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            bg="rgba(3,5,4,0.88)",
            z_index="999",
            backdrop_filter="blur(6px)",
            style={"pointer_events": "all"},
        ),
    )


# ── Main Page ────────────────────────────────────────────────────────────────

def editar_dados_page() -> rx.Component:
    return rx.cond(
        (GlobalState.current_user_role == "Administrador")
        | (GlobalState.current_user_role == "admin")
        | (GlobalState.current_user_role == "data_edit"),
        rx.box(
            _loading_overlay(),
            rx.vstack(
                _page_header(),
                _toolbar(),
                _data_grid(),
                _preview_dialog(),
                _edit_cell_dialog(),
                width="100%",
                align="stretch",
                spacing="0",
            ),
            width="100%",
            max_width="1440px",
            margin_x="auto",
            padding=rx.breakpoints(initial="8px", md="16px", xl="24px"),
            min_height="100vh",
            position="relative",
            # Auto-load default table on page open — no manual "Carregar" needed
            on_mount=EditState.load_table,
        ),
        _acesso_negado(),
    )
