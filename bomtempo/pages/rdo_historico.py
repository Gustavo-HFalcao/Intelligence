"""
RDO v2 Histórico — Lista de RDOs com dados da tabela rdo_master.
Rota: /rdo2-historico
"""

import asyncio
import json as _json
from typing import Any, Dict, List

import reflex as rx

from bomtempo.state.global_state import GlobalState
from bomtempo.state.rdo_state import RDOState
from bomtempo.core.rdo_service import RDOService
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.executors import (
    get_db_executor,
)

logger = get_logger(__name__)

_BG      = "#0B1A15"
_CARD    = "rgba(255,255,255,0.04)"
_BORDER  = "rgba(255,255,255,0.10)"
_COPPER  = "#C98B2A"
_PATINA  = "#2A9D8F"
_TEXT    = "#E8F0EE"
_MUTED   = "#6B9090"
_BTN_PRI = "linear-gradient(135deg,#C98B2A,#9B6820)"


# ── State ────────────────────────────────────────────────────────────────────

class RDOHistoricoState(rx.State):
    rdos_list: List[Dict[str, str]] = []
    is_loading: bool = False
    filter_status: str = "todos"  # todos | rascunho | finalizado

    # ── Email notification management ─────────────────────────
    emails_list: List[Dict[str, str]] = []
    emails_loading: bool = False
    new_email_input: str = ""
    emails_error: str = ""

    @rx.var
    def filtered_rdos(self) -> List[Dict[str, str]]:
        if self.filter_status == "todos":
            return self.rdos_list
        return [r for r in self.rdos_list if r.get("status", "") == self.filter_status]

    @rx.var
    def count_rascunho(self) -> int:
        # Inclui processando_pdf — são drafts que falharam no PDF e podem ser reenviados
        return sum(1 for r in self.rdos_list if r.get("status") in ("rascunho", "processando_pdf"))

    @rx.var
    def count_finalizado(self) -> int:
        return sum(1 for r in self.rdos_list if r.get("status") == "finalizado")

    @rx.event(background=True)
    async def load_rdos(self):
        async with self:
            self.is_loading = True
            gs = await self.get_state(GlobalState)
            user = str(gs.current_user_name)
            role = str(gs.current_user_role)
            contrato = str(gs.current_user_contrato).strip()

        loop = asyncio.get_running_loop()
        client_id = str(gs.current_client_id or "")

        try:
            # Filtrar por role + tenant (client_id sempre passado para isolamento multi-tenant)
            if role in ("Administrador", "admin", "Gestão-Mobile"):
                rdos = await loop.run_in_executor(get_db_executor(), lambda: RDOService.get_rdos_list(limit=200, client_id=client_id))
            elif role == "Mestre de Obras":
                rdos = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: RDOService.get_rdos_list(contrato=contrato, mestre_id=user, limit=100, client_id=client_id),
                )
            else:
                rdos = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: RDOService.get_rdos_list(contrato=contrato, limit=100, client_id=client_id),
                )

            def _fmt_date(val: str) -> str:
                """Converte YYYY-MM-DD ou ISO datetime → DD/MM/YYYY."""
                v = str(val or "")[:10]
                if len(v) == 10 and v[4] == "-":
                    try:
                        parts = v.split("-")
                        return f"{parts[2]}/{parts[1]}/{parts[0]}"
                    except Exception:
                        pass
                return v

            def _fmt_datetime(val: str) -> str:
                """Converte ISO UTC datetime → DD/MM/YYYY HH:MM (BRT, UTC-3)."""
                from datetime import datetime as _dt, timezone as _tz, timedelta as _td
                _BRT = _tz(_td(hours=-3))
                v = str(val or "")
                if not v or len(v) < 16:
                    return v
                try:
                    dt = _dt.fromisoformat(v.replace("Z", "+00:00")[:32])
                    brt = dt.astimezone(_BRT)
                    return brt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass
                return v[:16].replace("T", " ")

            # Normalizar para exibição
            normalized = []
            for r in (rdos or []):
                normalized.append({
                    "id_rdo":     str(r.get("id_rdo", "")),
                    "contrato":   str(r.get("contrato", "")),
                    "data":       _fmt_date(r.get("data", "")),
                    "status":     str(r.get("status", "rascunho")),
                    "clima":      str(r.get("condicao_climatica", "")),
                    "turno":      str(r.get("turno", "")),
                    "mestre":     str(r.get("mestre_id", "")),
                    "pdf_url":    str(r.get("pdf_url", "")),
                    "view_token": str(r.get("view_token", "")),
                    "checkin":    "✓" if r.get("checkin_lat") else "—",
                    "created_at": _fmt_datetime(r.get("created_at", "")),
                })

            async with self:
                self.rdos_list = normalized
        except Exception as e:
            logger.error(f"load_rdos error: {e}", exc_info=True)
            async with self:
                yield rx.toast("❌ Erro ao carregar RDOs.", position="top-center", duration=5000)
        finally:
            async with self:
                self.is_loading = False

    def set_filter(self, status: str):
        self.filter_status = status

    def set_new_email_input(self, v: str):
        self.new_email_input = v

    def handle_email_keydown(self, key: str):
        if key == "Enter":
            return RDOHistoricoState.add_email

    @rx.event(background=True)
    async def load_emails(self):
        import asyncio as _aio
        async with self:
            self.emails_loading = True
            self.emails_error = ""
        loop = _aio.get_running_loop()
        normalized: list = []
        try:
            from bomtempo.core.supabase_client import sb_select as _sel
            rows = await loop.run_in_executor(
                get_db_executor(),
                lambda: _sel("email_sender", filters={"module": "rdo"}, order="created_at.asc", limit=50) or [],
            )
            normalized = [{"id": str(r.get("id", "")), "email": str(r.get("email", ""))} for r in rows]
        except Exception as e:
            async with self:
                self.emails_error = f"Erro ao carregar e-mails: {str(e)[:80]}"
        async with self:
            self.emails_list = normalized
            self.emails_loading = False

    @rx.event(background=True)
    async def add_email(self):
        email = ""
        async with self:
            email = self.new_email_input.strip().lower()
        if not email or "@" not in email:
            async with self:
                self.emails_error = "E-mail inválido."
            return
        from bomtempo.core.supabase_client import sb_insert as _ins
        try:
            _ins("email_sender", {"module": "rdo", "email": email})
        except Exception as e:
            async with self:
                self.emails_error = f"Erro ao adicionar: {str(e)[:80]}"
            return
        async with self:
            self.new_email_input = ""
            self.emails_error = ""
        yield RDOHistoricoState.load_emails

    @rx.event(background=True)
    async def remove_email(self, email_id: str):
        from bomtempo.core.supabase_client import sb_delete as _del
        try:
            _del("email_sender", filters={"id": email_id})
        except Exception as e:
            async with self:
                self.emails_error = f"Erro ao remover: {str(e)[:80]}"
            return
        yield RDOHistoricoState.load_emails

    def open_external_url(self, url: str):
        """Abre URL em nova aba via JS — bypassa o router SPA/PWA."""
        if url and url.startswith("http"):
            safe = _json.dumps(url)
            return rx.call_script(f"window.open({safe}, '_blank', 'noopener,noreferrer')")

    @rx.event(background=True)
    async def regenerate_pdf(self, id_rdo: str):
        """Regenera o PDF de um RDO finalizado que não tem PDF ou teve falha na geração."""
        if not id_rdo:
            return
        async with self:
            yield rx.toast("⏳ Gerando PDF...", position="top-center", duration=5000)

        loop = asyncio.get_running_loop()
        try:
            rdo_data = await loop.run_in_executor(
                get_db_executor(),
                lambda: RDOService.get_full_rdo(id_rdo),
            )
            if not rdo_data:
                async with self:
                    yield rx.toast("❌ RDO não encontrado.", position="top-center")
                return

            from bomtempo.core.executors import get_heavy_executor
            pdf_result = await loop.run_in_executor(
                get_heavy_executor(),
                lambda: RDOService.generate_pdf(rdo_data, is_preview=False, id_rdo=id_rdo),
            )
            pdf_path = pdf_result[0] if pdf_result else ""
            if not pdf_path:
                async with self:
                    yield rx.toast("❌ Falha ao gerar PDF. Tente novamente.", position="top-center")
                return

            pdf_url = await loop.run_in_executor(
                get_heavy_executor(),
                lambda: RDOService.upload_pdf(pdf_path, id_rdo),
            )
            await loop.run_in_executor(
                get_db_executor(),
                lambda: RDOService.finalize_rdo(id_rdo, pdf_path, pdf_url, rdo_data),
            )
            # Update local list so PDF button appears immediately
            async with self:
                self.rdos_list = [
                    {**r, "pdf_url": pdf_url} if r.get("id_rdo") == id_rdo else r
                    for r in self.rdos_list
                ]
                yield rx.toast("✅ PDF gerado com sucesso!", position="top-center")
        except Exception as e:
            logger.error(f"regenerate_pdf: {e}", exc_info=True)
            async with self:
                yield rx.toast(f"❌ Erro ao gerar PDF: {str(e)[:80]}", position="top-center")

    @rx.event(background=True)
    async def delete_draft_rdo(self, id_rdo: str):
        """Exclui um RDO com status=rascunho. Recusa excluir finalizados."""
        if not id_rdo:
            return
        loop = asyncio.get_running_loop()
        # Safety check: only delete drafts
        rows = await loop.run_in_executor(
            get_db_executor(),
            lambda: RDOService.get_full_rdo(id_rdo),
        )
        if not rows:
            async with self:
                yield rx.toast("❌ RDO não encontrado.", position="top-center")
            return
        if rows.get("status") == "finalizado":
            async with self:
                yield rx.toast("❌ RDOs finalizados não podem ser excluídos.", position="top-center")
            return
        ok = await loop.run_in_executor(get_db_executor(), lambda: RDOService.delete_draft(id_rdo))
        async with self:
            if ok:
                self.rdos_list = [r for r in self.rdos_list if r.get("id_rdo") != id_rdo]
                # Limpa o RDOState para que o formulário não retome este rascunho excluído
                yield RDOState.reset_for_new
                yield rx.toast("🗑️ Rascunho excluído.", position="top-center")
            else:
                yield rx.toast("❌ Falha ao excluir rascunho.", position="top-center")


# ── Components ───────────────────────────────────────────────────────────────

def _status_badge(status: str) -> rx.Component:
    return rx.cond(
        status == "finalizado",
        rx.box(rx.text("✓ Finalizado"), class_name="rdo-status-badge finalizado"),
        rx.cond(
            status == "processando_pdf",
            rx.box(rx.text("⏳ PDF Pendente"), class_name="rdo-status-badge processando"),
            rx.box(rx.text("● Rascunho"), class_name="rdo-status-badge rascunho"),
        ),
    )


def _rdo_card(rdo: Dict[str, Any]) -> rx.Component:
    has_pdf = (rdo["pdf_url"] != "") & rdo["pdf_url"].startswith("http")
    has_token = rdo["view_token"] != ""
    is_draft = (rdo["status"] == "rascunho") | (rdo["status"] == "processando_pdf")

    return rx.box(
        rx.flex(
            # Left: id + meta + status
            rx.vstack(
                rx.hstack(
                    rx.text(rdo["id_rdo"], class_name="rdo-id-text"),
                    _status_badge(rdo["status"]),
                    spacing="2",
                    align="center",
                    flex_wrap="wrap",
                ),
                # Meta row
                rx.hstack(
                    rx.hstack(
                        rx.icon("calendar", size=11, color=_MUTED),
                        rx.text(rdo["data"], size="1", color=_MUTED),
                        spacing="1", align="center",
                    ),
                    rx.box(width="3px", height="3px", border_radius="50%",
                           background="rgba(136,153,153,0.4)", flex_shrink="0"),
                    rx.hstack(
                        rx.icon("user", size=11, color=_MUTED),
                        rx.text(rdo["mestre"], size="1", color=_MUTED),
                        spacing="1", align="center",
                    ),
                    rx.box(width="3px", height="3px", border_radius="50%",
                           background="rgba(136,153,153,0.4)", flex_shrink="0"),
                    rx.hstack(
                        rx.icon("cloud", size=11, color=_MUTED),
                        rx.text(rdo["clima"], size="1", color=_MUTED),
                        spacing="1", align="center",
                    ),
                    rx.cond(
                        rdo["checkin"] == "✓",
                        rx.hstack(
                            rx.box(width="3px", height="3px", border_radius="50%",
                                   background="rgba(136,153,153,0.4)", flex_shrink="0"),
                            rx.icon("map-pin", size=11, color=_PATINA),
                            rx.text("GPS", size="1", color=_PATINA),
                            spacing="1", align="center",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                    flex_wrap="wrap",
                    class_name="rdo-meta-row",
                ),
                spacing="2",
                align="start",
                flex="1",
                min_width="0",
            ),
            # Right: actions
            rx.hstack(
                # PDF action
                rx.cond(
                    has_pdf,
                    rx.button(
                        rx.icon("download", size=13),
                        rx.text("PDF", display=["none", "inline"]),
                        on_click=RDOHistoricoState.open_external_url(rdo["pdf_url"]),
                        class_name="rdo-action-pill pdf",
                    ),
                    rx.cond(
                        rdo["status"] == "finalizado",
                        rx.button(
                            rx.icon("file-plus", size=13),
                            rx.text("Gerar PDF", display=["none", "inline"]),
                            on_click=RDOHistoricoState.regenerate_pdf(rdo["id_rdo"]),
                            class_name="rdo-action-pill generate",
                            title="PDF não disponível — clique para gerar",
                        ),
                        rx.fragment(),
                    ),
                ),
                # View online
                rx.cond(
                    has_token,
                    rx.link(
                        rx.button(
                            rx.icon("eye", size=13),
                            rx.text("Online", display=["none", "inline"]),
                            class_name="rdo-action-pill view",
                        ),
                        href=f"/rdo-view/{rdo['view_token']}",
                        is_external=True,
                    ),
                    rx.fragment(),
                ),
                # Draft actions
                rx.cond(
                    is_draft,
                    rx.hstack(
                        rx.button(
                            rx.icon("pencil", size=13),
                            rx.text(
                                rx.cond(rdo["status"] == "processando_pdf", "Reprocessar", "Continuar"),
                                display=["none", "inline"],
                            ),
                            on_click=[GlobalState.set_navigating, rx.redirect("/rdo-form")],
                            class_name="rdo-action-pill edit",
                        ),
                        rx.button(
                            rx.icon("trash-2", size=13),
                            on_click=RDOHistoricoState.delete_draft_rdo(rdo["id_rdo"]),
                            class_name="rdo-action-pill danger",
                            title="Excluir rascunho",
                        ),
                        spacing="1",
                        align="center",
                    ),
                    rx.fragment(),
                ),
                spacing="1",
                align="center",
                flex_wrap="wrap",
                flex_shrink="0",
            ),
            gap="12px",
            align="center",
            width="100%",
            flex_wrap="wrap",
        ),
        class_name=rx.cond(
            rdo["status"] == "finalizado",
            "rdo-list-card status-finalizado",
            rx.cond(
                rdo["status"] == "processando_pdf",
                "rdo-list-card status-processando",
                "rdo-list-card status-rascunho",
            ),
        ),
    )


# ── Page ─────────────────────────────────────────────────────────────────────

def _email_row(item: Dict[str, str]) -> rx.Component:
    return rx.hstack(
        rx.icon("mail", size=13, color=_MUTED),
        rx.text(item["email"], size="2", color=_TEXT, flex="1"),
        rx.icon_button(
            rx.icon("trash-2", size=13),
            variant="ghost", size="1",
            on_click=RDOHistoricoState.remove_email(item["id"]),
            style={"color": "#EF4444", "cursor": "pointer"},
        ),
        spacing="2", align="center", width="100%",
        padding="8px 12px",
        border_radius="6px",
        background="rgba(255,255,255,0.03)",
        border=f"1px solid {_BORDER}",
    )


def _tab_emails() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Defina quem recebe notificações por e-mail quando um RDO for finalizado.",
            size="2", color=_MUTED, margin_bottom="16px",
        ),
        # Add email row
        rx.hstack(
            rx.input(
                placeholder="novo@email.com",
                value=RDOHistoricoState.new_email_input,
                on_change=RDOHistoricoState.set_new_email_input,
                on_key_down=RDOHistoricoState.handle_email_keydown,
                debounce_timeout=150,
                style={
                    "background": "rgba(255,255,255,0.06)",
                    "border": f"1px solid {_BORDER}",
                    "border_radius": "6px",
                    "color": _TEXT,
                    "flex": "1",
                },
            ),
            rx.button(
                rx.icon("plus", size=14),
                "Adicionar",
                on_click=RDOHistoricoState.add_email,
                size="2",
                style={"background": _BTN_PRI, "color": "#fff", "border_radius": "6px", "cursor": "pointer"},
            ),
            spacing="2", width="100%",
        ),
        rx.cond(
            RDOHistoricoState.emails_error != "",
            rx.text(RDOHistoricoState.emails_error, size="1", color="#EF4444"),
        ),
        rx.separator(width="100%", margin_y="12px"),
        # List
        rx.cond(
            RDOHistoricoState.emails_loading,
            rx.center(rx.spinner(size="2"), padding="24px"),
            rx.cond(
                RDOHistoricoState.emails_list.length() == 0,
                rx.center(
                    rx.vstack(
                        rx.icon("inbox", size=28, color=_MUTED),
                        rx.text("Nenhum e-mail cadastrado", size="2", color=_MUTED),
                        spacing="2", align="center",
                    ),
                    padding="32px",
                ),
                rx.vstack(
                    rx.foreach(RDOHistoricoState.emails_list, _email_row),
                    spacing="2", width="100%",
                ),
            ),
        ),
        spacing="3", width="100%",
    )


def _rdo_historico_topnav() -> rx.Component:
    """Minimal sticky topnav — standalone page has no global sidebar."""
    return rx.box(
        rx.hstack(
            # Brand
            rx.hstack(
                rx.image(src="/icon.png", width="26px", height="26px",
                         border_radius="4px", object_fit="cover"),
                rx.vstack(
                    rx.hstack(
                        rx.text("BOMTEMPO", weight="bold", size="2", color="#fff",
                                font_family="'Rajdhani', sans-serif", letter_spacing="0.08em", line_height="1"),
                        rx.text("RDO", size="1", color=_COPPER,
                                font_family="'Rajdhani', sans-serif", letter_spacing="0.08em"),
                        spacing="2", align="center",
                    ),
                    rx.text("Relatórios Diários de Obra", size="1", color=_MUTED, line_height="1"),
                    spacing="0",
                ),
                spacing="2", align="center",
            ),
            rx.spacer(),
            align="center", width="100%",
        ),
        padding=["8px 14px", "10px 24px"],
        background="rgba(8,18,16,0.97)",
        border_bottom=f"1px solid rgba(201,139,42,0.10)",
        style={"backdropFilter": "blur(16px)", "-webkit-backdrop-filter": "blur(16px)"},
        position="sticky",
        top="0",
        z_index="50",
        width="100%",
    )


def rdo_historico_page() -> rx.Component:
    return rx.box(
        _rdo_historico_topnav(),
        # ── Hero Section ────────────────────────────────────────────────────
        rx.box(
            rx.flex(
                # Left: title + description
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            rx.icon("file-text", size=18, color=_COPPER),
                            width="40px", height="40px",
                            border_radius="10px",
                            background="rgba(201,139,42,0.1)",
                            border="1px solid rgba(201,139,42,0.2)",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            flex_shrink="0",
                        ),
                        rx.vstack(
                            rx.text("Histórico de RDOs", class_name="rdo-lobby-title"),
                            rx.text("Relatórios Diários de Obra · Campo", class_name="rdo-lobby-subtitle"),
                            spacing="0",
                            align="start",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    spacing="0",
                    align="start",
                    flex="1",
                ),
                # Right: Novo RDO CTA
                rx.button(
                    rx.icon("plus", size=16),
                    "Novo RDO",
                    on_click=[GlobalState.set_navigating, RDOState.reset_for_new, rx.redirect("/rdo-form")],
                    class_name="rdo-new-btn",
                ),
                direction={"initial": "column", "sm": "row"},
                align={"initial": "start", "sm": "center"},
                gap="16px",
                width="100%",
            ),
            class_name="rdo-lobby-hero",
        ),

        # ── Stats ────────────────────────────────────────────────────────
        rx.grid(
            _stat_card("Total de RDOs", RDOHistoricoState.rdos_list.length().to_string(),
                       "file-text", _COPPER, "copper"),
            _stat_card("Finalizados", RDOHistoricoState.count_finalizado.to_string(),
                       "check-circle-2", _PATINA, "patina"),
            _stat_card("Rascunhos", RDOHistoricoState.count_rascunho.to_string(),
                       "clock", "#E0A030", "amber"),
            columns={"initial": "3"},
            gap=["8px", "12px"],
            margin_bottom="20px",
        ),

        # ── Main tabs ──────────────────────────────────────────────────────
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    rx.hstack(rx.icon("file-text", size=14), rx.text("Meus RDOs"), spacing="2", align="center"),
                    value="rdos",
                    style={"cursor": "pointer"},
                ),
                rx.tabs.trigger(
                    rx.hstack(rx.icon("mail", size=14), rx.text("E-mails"), spacing="2", align="center"),
                    value="emails",
                    on_click=RDOHistoricoState.load_emails,
                    style={"cursor": "pointer"},
                ),
                margin_bottom="16px",
            ),

            # Tab: RDOs
            rx.tabs.content(
                rx.vstack(
                    # Filter bar + refresh
                    rx.hstack(
                        _filter_tab("Todos", "todos", RDOHistoricoState.filter_status),
                        _filter_tab("Finalizados", "finalizado", RDOHistoricoState.filter_status),
                        _filter_tab("Rascunhos", "rascunho", RDOHistoricoState.filter_status),
                        rx.spacer(),
                        rx.button(
                            rx.icon("refresh-cw", size=14),
                            on_click=RDOHistoricoState.load_rdos,
                            size="1", variant="ghost",
                            style={"color": _MUTED, "cursor": "pointer"},
                        ),
                        spacing="2",
                        align="center",
                        width="100%",
                    ),

                    # List
                    rx.cond(
                        RDOHistoricoState.is_loading,
                        rx.center(
                            rx.vstack(
                                rx.spinner(size="3", color_scheme="amber"),
                                rx.text("Carregando RDOs…", size="2", color=_MUTED),
                                spacing="3", align="center",
                            ),
                            padding="60px",
                        ),
                        rx.cond(
                            RDOHistoricoState.filtered_rdos.length() == 0,
                            rx.box(
                                rx.vstack(
                                    rx.box(
                                        rx.icon("inbox", size=32, color=_MUTED),
                                        class_name="rdo-empty-icon",
                                    ),
                                    rx.text("Nenhum RDO encontrado", size="3", weight="bold", color=_TEXT,
                                            style={"font_family": "'Rajdhani', sans-serif", "letter_spacing": "0.04em"}),
                                    rx.text("Crie seu primeiro relatório diário de obra", size="2", color=_MUTED),
                                    rx.button(
                                        rx.icon("plus", size=16),
                                        "Criar primeiro RDO",
                                        on_click=[GlobalState.set_navigating, RDOState.reset_for_new, rx.redirect("/rdo-form")],
                                        class_name="rdo-new-btn",
                                        margin_top="8px",
                                    ),
                                    spacing="2", align="center",
                                ),
                                class_name="rdo-empty-state",
                            ),
                            rx.vstack(
                                rx.foreach(RDOHistoricoState.filtered_rdos, _rdo_card),
                                spacing="2", width="100%",
                            ),
                        ),
                    ),
                    spacing="3", width="100%",
                ),
                value="rdos",
            ),

            # Tab: E-mails
            rx.tabs.content(
                _tab_emails(),
                value="emails",
            ),
            default_value="rdos",
            width="100%",
        ),

        padding=["14px", "28px"],
        max_width="960px",
        margin="0 auto",
        min_height="100vh",
        background=_BG,
        class_name="animate-enter",
    )


def _stat_card(label: str, value: rx.Var, icon: str, color: str, icon_class: str = "copper") -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(label, class_name="rdo-stat-label"),
                rx.text(value, class_name="rdo-stat-value", color=color),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            rx.box(
                rx.icon(icon, size=20, color=color),
                class_name=f"rdo-stat-icon {icon_class}",
            ),
            align="center",
        ),
        class_name="rdo-stat-card",
    )


def _filter_tab(label: str, value: str, current: rx.Var) -> rx.Component:
    is_active = current == value
    return rx.button(
        label,
        on_click=RDOHistoricoState.set_filter(value),
        class_name=rx.cond(is_active, "rdo-filter-pill active", "rdo-filter-pill"),
    )
