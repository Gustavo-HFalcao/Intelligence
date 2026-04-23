"""
RelatoriosState — Bomtempo Intelligence
State and event handlers for the Relatórios module (Feature 3).
"""

from __future__ import annotations

import asyncio
import threading
import time
import unicodedata
from datetime import datetime

import reflex as rx

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.report_service import ReportService
from bomtempo.core.audit_logger import audit_log, audit_error, AuditCategory
from bomtempo.core.executors import (
    get_ai_executor,
    get_db_executor,
    get_heavy_executor,
    get_http_executor,
)

logger = get_logger(__name__)


class RelatoriosState(rx.State):
    # ── Seleção ──────────────────────────────────────────────────────────────
    selected_contrato: str = ""
    selected_abordagem: str = "estrategica"

    # ── Configurador Enterprise (novo) ─────────────────────────────────────
    # Escopo de seções
    escopo_cronograma: bool = True
    escopo_financeiro: bool = True
    escopo_rdos: bool = True
    escopo_documentos: bool = True
    escopo_equipe: bool = True
    escopo_alertas: bool = True
    # Período
    periodo_inicio: str = ""
    periodo_fim: str = ""
    # Etapa específica (dropdown das macro-etapas)
    etapa_especifica: str = ""
    etapas_disponiveis: list[str] = []
    # Destinatários
    report_recipients: list[dict] = []   # [{email, name}]
    new_recipient_email: str = ""
    new_recipient_name: str = ""
    # Agendamento
    schedule_cron: str = ""
    schedule_active: bool = False
    # Modo de geração: "static" | "ia_mcp" | "ia_snapshot" | "custom"
    generation_mode: str = "ia_mcp"

    # ── Static Dossier ────────────────────────────────────────────────────────
    report_html_preview: str = ""
    report_pdf_url: str = ""
    is_generating_static: bool = False

    # ── AI Report ────────────────────────────────────────────────────────────
    ai_report_text: str = ""
    is_generating_ai: bool = False

    # ── Custom Chatbox ────────────────────────────────────────────────────────
    custom_prompt: str = ""
    is_generating_custom: bool = False

    # ── Shared streaming flag ────────────────────────────────────────────────
    is_streaming: bool = False

    # ── History ───────────────────────────────────────────────────────────────
    reports_history: list[dict] = []
    is_loading_history: bool = False

    # ── Error / UI feedback ───────────────────────────────────────────────────
    error_msg: str = ""
    success_msg: str = ""

    # ── Setters (Reflex compiler requirement — no dynamic setattr) ────────────

    def set_selected_contrato(self, val: str):
        self.selected_contrato = val
        # Reset previous output when contrato changes
        self.report_html_preview = ""
        self.report_pdf_url = ""
        self.ai_report_text = ""
        self.error_msg = ""
        self.success_msg = ""

    def set_selected_abordagem(self, val: str):
        self.selected_abordagem = val

    def set_custom_prompt(self, val: str):
        self.custom_prompt = val

    def set_generation_mode(self, val: str):
        self.generation_mode = val
        self.ai_report_text = ""
        self.report_html_preview = ""
        self.report_pdf_url = ""
        self.error_msg = ""

    def set_periodo_inicio(self, val: str): self.periodo_inicio = val
    def set_periodo_fim(self, val: str): self.periodo_fim = val
    def set_etapa_especifica(self, val: str): self.etapa_especifica = val
    def set_new_recipient_email(self, val: str): self.new_recipient_email = val
    def set_new_recipient_name(self, val: str): self.new_recipient_name = val
    def set_schedule_cron(self, val: str): self.schedule_cron = val
    def set_escopo_cronograma(self, val: bool): self.escopo_cronograma = val
    def set_escopo_financeiro(self, val: bool): self.escopo_financeiro = val
    def set_escopo_rdos(self, val: bool): self.escopo_rdos = val
    def set_escopo_documentos(self, val: bool): self.escopo_documentos = val
    def set_escopo_equipe(self, val: bool): self.escopo_equipe = val
    def set_escopo_alertas(self, val: bool): self.escopo_alertas = val

    def add_recipient(self):
        email = self.new_recipient_email.strip()
        name = self.new_recipient_name.strip()
        if email and "@" in email:
            existing = [r.get("email") for r in self.report_recipients]
            if email not in existing:
                self.report_recipients = list(self.report_recipients) + [{"email": email, "name": name or email}]
            self.new_recipient_email = ""
            self.new_recipient_name = ""

    def remove_recipient(self, email: str):
        self.report_recipients = [r for r in self.report_recipients if r.get("email") != email]

    def toggle_schedule_active(self):
        self.schedule_active = not self.schedule_active

    def clear_ai_text(self):
        self.ai_report_text = ""
        self.error_msg = ""

    def clear_static_preview(self):
        self.report_html_preview = ""
        self.report_pdf_url = ""
        self.error_msg = ""

    @rx.var
    def escopo_dict(self) -> dict:
        return {
            "cronograma": self.escopo_cronograma,
            "financeiro": self.escopo_financeiro,
            "rdos": self.escopo_rdos,
            "documentos": self.escopo_documentos,
            "equipe": self.escopo_equipe,
            "alertas": self.escopo_alertas,
        }

    @rx.var
    def has_recipients(self) -> bool:
        return len(self.report_recipients) > 0

    @rx.var
    def is_generating(self) -> bool:
        return self.is_generating_static or self.is_generating_ai or self.is_generating_custom

    # ── On Load ───────────────────────────────────────────────────────────────

    async def load_page(self):
        """Called on page load — fetches report history from Supabase."""
        self.is_loading_history = True
        yield
        client_id = ""
        try:
            from bomtempo.state.global_state import GlobalState as _GS
            _gs = await self.get_state(_GS)
            client_id = str(_gs.current_client_id or "")
        except Exception:
            pass
        try:
            history = await loop.run_in_executor(
                get_db_executor(),
                lambda: ReportService.load_history(client_id=client_id)
            )
            self.reports_history = history
        except Exception as e:
            logger.error(f"RelatoriosState.load_page error: {e}")
        finally:
            self.is_loading_history = False

    # ── Generate Static Report ────────────────────────────────────────────────

    @rx.event(background=True)
    async def generate_static_report(self):
        """Build static HTML dossier, generate PDF, upload to Supabase."""
        # Collect ALL state reads inside async with self: (including get_state)
        contrato = ""
        cliente = "—"
        current_user = "Sistema"
        fmt: dict = {}
        obra: dict = {}
        disciplinas: list = []

        from bomtempo.state.global_state import GlobalState
        async with self:
            gs = await self.get_state(GlobalState)
            contrato = self.selected_contrato or "Geral / Portfólio"
            self.is_generating_static = True
            self.report_html_preview = ""
            self.report_pdf_url = ""
            self.error_msg = ""
            fmt = dict(gs.obra_kpi_fmt)
            obra = dict(gs.obra_enterprise_data)
            disciplinas = list(gs.disciplina_progress_chart)
            current_user = str(gs.current_user_name)
            _report_client_id = str(gs.current_client_id or "")
            for c in gs.contratos_list:
                if c.get("contrato", "") == contrato:
                    cliente = c.get("cliente", "—")
                    break

        data = {
            "contrato": contrato,
            "cliente": cliente,
            "gerado_por": current_user,
            "fmt": fmt,
            "obra": obra,
            "disciplinas": disciplinas,
        }

        loop = asyncio.get_running_loop()

        try:
            # Build HTML (CPU-bound — run in heavy executor)
            html = await loop.run_in_executor(
                get_heavy_executor(),
                lambda: ReportService.build_static_html(data)
            )

            # Show preview immediately
            async with self:
                self.report_html_preview = html

            # Generate PDF + upload to Supabase Storage
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            _raw = contrato.replace(" ", "_").replace("/", "-")[:30]
            safe_name = unicodedata.normalize("NFKD", _raw).encode("ascii", "ignore").decode("ascii")
            filename = f"relatorio_{safe_name}_{ts}.pdf"

            pdf_path, pdf_url = await loop.run_in_executor(
                get_heavy_executor(),
                lambda: ReportService.generate_pdf(html, filename)
            )

            # Save record to Supabase
            record = {
                "contrato": contrato,
                "cliente": cliente,
                "tipo": "estatico",
                "titulo": f"Relatório Estático — {contrato}",
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "created_by": current_user,
            }
            if _report_client_id:
                record["client_id"] = _report_client_id
            
            await loop.run_in_executor(
                get_db_executor(),
                lambda: ReportService.save_report(record)
            )

            # Reload history
            history = await loop.run_in_executor(
                get_db_executor(),
                lambda: ReportService.load_history(client_id=_report_client_id)
            )

            audit_log(
                category=AuditCategory.REPORT_GEN,
                action=f"Relatório estático gerado — contrato '{contrato}' por '{current_user}'",
                username=current_user,
                entity_type="relatorio",
                metadata={"contrato": contrato, "tipo": "estatico", "pdf_url": pdf_url},
                status="success",
            )
            async with self:
                self.report_pdf_url = pdf_url
                self.reports_history = history
                self.is_generating_static = False

        except Exception as e:
            logger.error(f"generate_static_report failed: {e}")
            audit_error(
                action=f"Falha ao gerar relatório estático — contrato '{contrato}'",
                username=current_user,
                entity_type="relatorio",
                error=e,
            )
            async with self:
                self.error_msg = f"Erro ao gerar relatório: {str(e)[:200]}"
                self.is_generating_static = False

    # ── Generate AI Report ────────────────────────────────────────────────────

    @rx.event(background=True)
    async def generate_ai_report(self):
        """Stream AI-generated report based on selected approach."""
        contrato = ""
        cliente = "—"
        current_user = "Sistema"
        abordagem = "estrategica"
        fmt: dict = {}
        obra: dict = {}
        disciplinas: list = []

        from bomtempo.state.global_state import GlobalState
        async with self:
            gs = await self.get_state(GlobalState)
            contrato = self.selected_contrato or "Geral / Portfólio"
            abordagem = self.selected_abordagem
            self.is_generating_ai = True
            self.is_streaming = True
            self.ai_report_text = ""
            self.error_msg = ""
            fmt = dict(gs.obra_kpi_fmt)
            obra = dict(gs.obra_enterprise_data)
            disciplinas = list(gs.disciplina_progress_chart)
            current_user = str(gs.current_user_name)
            _report_client_id = str(gs.current_client_id or "")
            for c in gs.contratos_list:
                if c.get("contrato", "") == contrato:
                    cliente = c.get("cliente", "—")
                    break

        data = {
            "contrato": contrato,
            "cliente": cliente,
            "gerado_por": current_user,
            "fmt": fmt,
            "obra": obra,
            "disciplinas": disciplinas,
        }

        try:
            messages = ReportService.build_ai_prompt(abordagem, data)
            full_text = await self._stream_ai_text(messages)
        except Exception as _e:
            logger.error(f"generate_ai_report: stream falhou: {_e}")
            yield RelatoriosState.reset_generating_ai
            return

        # Generate PDF + save to Supabase
        if full_text:
            loop = asyncio.get_running_loop()
            pdf_path = ""
            pdf_url = ""
            try:
                # Build styled HTML from AI markdown
                ai_html = await loop.run_in_executor(
                    get_heavy_executor(),
                    lambda: ReportService.build_ai_html(full_text, data, abordagem)
                )
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                _raw = contrato.replace(" ", "_").replace("/", "-")[:30]
                safe_name = unicodedata.normalize("NFKD", _raw).encode("ascii", "ignore").decode("ascii")
                filename = f"relatorio_ia_{safe_name}_{ts}.pdf"
                pdf_path, pdf_url = await loop.run_in_executor(
                    get_heavy_executor(),
                    lambda: ReportService.generate_pdf(ai_html, filename)
                )
            except Exception as e:
                logger.error(f"Error generating AI report PDF: {e}")

            try:
                record = {
                    "contrato": contrato,
                    "cliente": cliente,
                    "tipo": "ia",
                    "abordagem": abordagem,
                    "titulo": f"Análise IA ({abordagem.capitalize()}) — {contrato}",
                    "ai_text": full_text,
                    "pdf_path": pdf_path,
                    "pdf_url": pdf_url,
                    "created_by": current_user,
                }
                if _report_client_id:
                    record["client_id"] = _report_client_id
                await loop.run_in_executor(get_db_executor(), lambda: ReportService.save_report(record))
                history = await loop.run_in_executor(get_db_executor(), lambda: ReportService.load_history(client_id=_report_client_id))
                async with self:
                    self.report_pdf_url = pdf_url
                    self.reports_history = history
            except Exception as e:
                logger.error(f"Error saving AI report to Supabase: {e}")

        audit_log(
            category=AuditCategory.REPORT_GEN,
            action=f"Relatório IA ({abordagem}) gerado — contrato '{contrato}' por '{current_user}'",
            username=current_user,
            entity_type="relatorio",
            metadata={"contrato": contrato, "tipo": "ia", "abordagem": abordagem},
            status="success",
        )
        async with self:
            self.is_generating_ai = False
            self.is_streaming = False

    @rx.event(background=True)
    async def reset_generating_ai(self):
        """Safety valve: reseta is_generating_ai/is_streaming se o handler falhar."""
        async with self:
            self.is_generating_ai = False
            self.is_streaming = False
            self.is_generating_custom = False
            self.is_generating_static = False
            if not self.error_msg:
                self.error_msg = "Erro inesperado ao gerar relatório. Tente novamente."

    # ── Generate Custom Report (Chatbox) ──────────────────────────────────────

    @rx.event(background=True)
    async def generate_custom_report(self):
        """Stream custom AI report from user's natural language prompt."""
        contrato = ""
        cliente = "—"
        current_user = "Sistema"
        prompt = ""
        fmt: dict = {}
        obra: dict = {}
        disciplinas: list = []

        from bomtempo.state.global_state import GlobalState
        async with self:
            gs = await self.get_state(GlobalState)
            contrato = self.selected_contrato or "Geral / Portfólio"
            prompt = self.custom_prompt.strip()

            if not prompt:
                self.error_msg = "Descreva o relatório desejado."
                return

            self.is_generating_custom = True
            self.is_streaming = True
            self.ai_report_text = ""
            self.error_msg = ""
            fmt = dict(gs.obra_kpi_fmt)
            obra = dict(gs.obra_enterprise_data)
            disciplinas = list(gs.disciplina_progress_chart)
            current_user = str(gs.current_user_name)
            _report_client_id = str(gs.current_client_id or "")
            for c in gs.contratos_list:
                if c.get("contrato", "") == contrato:
                    cliente = c.get("cliente", "—")
                    break

        data = {
            "contrato": contrato,
            "cliente": cliente,
            "gerado_por": current_user,
            "fmt": fmt,
            "obra": obra,
            "disciplinas": disciplinas,
        }

        try:
            messages = ReportService.build_ai_prompt("custom", data, custom_instruction=prompt)
            full_text = await self._stream_ai_text(messages)
        except Exception as _e:
            logger.error(f"generate_custom_report: stream falhou: {_e}")
            yield RelatoriosState.reset_generating_ai
            return

        if full_text:
            loop = asyncio.get_running_loop()
            pdf_path = ""
            pdf_url = ""
            try:
                ai_html = await loop.run_in_executor(
                    get_heavy_executor(),
                    lambda: ReportService.build_ai_html(full_text, data, "custom")
                )
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                _raw = contrato.replace(" ", "_").replace("/", "-")[:30]
                import unicodedata
                safe_name = unicodedata.normalize("NFKD", _raw).encode("ascii", "ignore").decode("ascii")
                filename = f"relatorio_custom_{safe_name}_{ts}.pdf"
                pdf_path, pdf_url = await loop.run_in_executor(
                    get_heavy_executor(),
                    lambda: ReportService.generate_pdf(ai_html, filename)
                )
            except Exception as e:
                logger.error(f"Error generating custom report PDF: {e}")

            try:
                short_prompt = prompt[:60] + ("..." if len(prompt) > 60 else "")
                record = {
                    "contrato": contrato,
                    "cliente": cliente,
                    "tipo": "custom",
                    "abordagem": short_prompt,
                    "titulo": f"Relatório Customizado — {contrato}",
                    "ai_text": full_text,
                    "pdf_path": pdf_path,
                    "pdf_url": pdf_url,
                    "created_by": current_user,
                }
                if _report_client_id:
                    record["client_id"] = _report_client_id
                await loop.run_in_executor(get_db_executor(), lambda: ReportService.save_report(record))
                history = await loop.run_in_executor(get_db_executor(), lambda: ReportService.load_history(client_id=_report_client_id))
                async with self:
                    self.report_pdf_url = pdf_url
                    self.reports_history = history
                    self.custom_prompt = ""
            except Exception as e:
                logger.error(f"Error saving custom report: {e}")

        audit_log(
            category=AuditCategory.REPORT_GEN,
            action=f"Relatório custom gerado — contrato '{contrato}' por '{current_user}'",
            username=current_user,
            entity_type="relatorio",
            metadata={"contrato": contrato, "tipo": "custom", "prompt_preview": (prompt or "")[:120]},
            status="success",
        )
        async with self:
            self.is_generating_custom = False
            self.is_streaming = False

    # ── Copy AI Text ──────────────────────────────────────────────────────────

    async def copy_ai_text(self):
        yield rx.set_clipboard(self.ai_report_text)

    def open_pdf_url(self, url: str):
        """Abre PDF em nova aba via JS — bypassa SPA/PWA router."""
        if url and url.startswith("http"):
            return rx.call_script(f"window.open({repr(url)}, '_blank', 'noopener,noreferrer')")

    # ── Internal: Streaming Helper ────────────────────────────────────────────

    async def _stream_ai_text(self, messages: list[dict]) -> str:
        """
        Stream AI response tokens via thread + asyncio.Queue.
        Updates self.ai_report_text every 200ms with live cursor.
        Returns full text on completion (or "" on error).
        """
        from bomtempo.core.ai_client import ai_client

        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        def _run():
            try:
                for chunk in ai_client.query_stream(messages):
                    asyncio.run_coroutine_threadsafe(q.put(chunk), loop)
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(q.put(f"__STREAM_ERROR__:{exc}"), loop)
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)

        threading.Thread(target=_run, daemon=True).start()

        full_text = ""
        last_update = time.monotonic()
        received_first = False

        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=90.0)
            except asyncio.TimeoutError:
                logger.error("AI report streaming timeout after 90s")
                break

            if chunk is None:
                break

            if isinstance(chunk, str) and chunk.startswith("__STREAM_ERROR__:"):
                err = chunk.split(":", 1)[1] if ":" in chunk else "Erro desconhecido"
                async with self:
                    self.ai_report_text = (
                        f"**Erro ao conectar com a IA:** {err[:200]}\n\nTente novamente."
                    )
                    self.error_msg = err[:200]
                    self.is_streaming = False
                    self.is_generating_ai = False
                    self.is_generating_custom = False
                return ""

            full_text += chunk
            now = time.monotonic()

            if not received_first or (now - last_update >= 0.20):
                async with self:
                    self.ai_report_text = full_text + "▌"
                received_first = True
                last_update = now

        if full_text:
            async with self:
                self.ai_report_text = full_text

    # ── Generate AI Report MCP (acesso direto ao banco) ───────────────────────

    @rx.event(background=True)
    async def generate_ai_report_mcp(self):
        """
        Gera relatório IA com acesso direto ao banco via execute_sql + search_documents.
        Diferente do generate_ai_report clássico: a IA consulta dados em tempo real,
        não recebe snapshot estático do GlobalState.
        LGPD: client_id injetado no system_prompt — IA não pode acessar outro tenant.
        """
        contrato = ""
        cliente = "—"
        current_user = "Sistema"
        abordagem = "estrategica"
        client_id = ""
        periodo_inicio = ""
        periodo_fim = ""
        etapa_especifica = ""
        escopo: dict = {}
        recipients: list = []

        from bomtempo.state.global_state import GlobalState
        async with self:
            gs = await self.get_state(GlobalState)
            contrato = self.selected_contrato or "Geral / Portfólio"
            abordagem = self.selected_abordagem
            periodo_inicio = self.periodo_inicio
            periodo_fim = self.periodo_fim
            etapa_especifica = self.etapa_especifica
            escopo = dict(self.escopo_dict)
            recipients = list(self.report_recipients)
            self.is_generating_ai = True
            self.is_streaming = True
            self.ai_report_text = ""
            self.error_msg = ""
            self.success_msg = ""
            current_user = str(gs.current_user_name)
            client_id = str(gs.current_client_id or "")
            for c in gs.contratos_list:
                if c.get("contrato", "") == contrato:
                    cliente = c.get("cliente", "—")
                    break

        # Usa o prompt MCP enterprise com ferramentas diretas no banco
        messages = ReportService.build_ai_prompt_with_mcp(
            approach=abordagem,
            contrato=contrato,
            client_id=client_id,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            escopo=escopo,
            etapa_especifica=etapa_especifica,
            gerado_por=current_user,
        )

        # Streaming com tools (execute_sql, search_documents, get_schema_info)
        full_text = await self._stream_ai_text_with_tools(messages, client_id, contrato)

        if full_text:
            loop = asyncio.get_running_loop()
            pdf_path = ""
            pdf_url = ""
            try:
                data = {
                    "contrato": contrato,
                    "cliente": cliente,
                    "gerado_por": current_user,
                    "fmt": {},
                    "obra": {},
                    "disciplinas": [],
                }
                ai_html = await loop.run_in_executor(
                    get_heavy_executor(),
                    lambda: ReportService.build_ai_html(full_text, data, abordagem)
                )
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                # ...
                filename = f"relatorio_mcp_{safe_name}_{ts}.pdf"
                pdf_path, pdf_url = await loop.run_in_executor(
                    get_heavy_executor(),
                    lambda: ReportService.generate_pdf(ai_html, filename)
                )
            except Exception as e:
                logger.error(f"MCP report PDF error: {e}")

            # Salva no banco
            try:
                record = {
                    "contrato": contrato,
                    "cliente": cliente,
                    "tipo": "ia_mcp",
                    "abordagem": abordagem,
                    "titulo": f"Relatório IA Enterprise — {contrato}",
                    "ai_text": full_text,
                    "pdf_path": pdf_path,
                    "pdf_url": pdf_url,
                    "created_by": current_user,
                    "periodo_inicio": periodo_inicio or None,
                    "periodo_fim": periodo_fim or None,
                    "escopo": escopo,
                    "etapa_especifica": etapa_especifica or None,
                    "recipients": recipients,
                }
                if client_id:
                    record["client_id"] = client_id
                await loop.run_in_executor(
                    get_db_executor(),
                    lambda: ReportService.save_report(record)
                )

                # Envia por email se houver destinatários
                if recipients and pdf_url:
                    def _send_emails():
                        try:
                            from bomtempo.core.email_service import EmailService
                            email_list = [r.get("email") for r in recipients if r.get("email")]
                            if email_list:
                                # Reutiliza o send_document do EmailService para enviar PDF
                                from bomtempo.core.admin_tools import AdminTools
                                subject = f"[Bomtempo] Relatório {contrato} — {datetime.now().strftime('%d/%m/%Y')}"
                                AdminTools.send_report_email(email_list, subject, contrato, pdf_url, pdf_path)
                        except Exception as _em:
                            logger.warning(f"Falha no envio de email do relatório MCP: {_em}")
                    threading.Thread(target=_send_emails, daemon=True).start()

                history = await loop.run_in_executor(
                    get_db_executor(),
                    lambda: ReportService.load_history(client_id=client_id)
                )
                async with self:
                    self.report_pdf_url = pdf_url
                    self.reports_history = history
                    self.success_msg = f"Relatório gerado com sucesso! {'Enviado para ' + str(len(recipients)) + ' destinatários.' if recipients else ''}"
            except Exception as e:
                logger.error(f"MCP report save error: {e}")

        audit_log(
            category=AuditCategory.REPORT_GEN,
            action=f"Relatório IA MCP ({abordagem}) gerado — contrato '{contrato}' por '{current_user}'",
            username=current_user,
            entity_type="relatorio",
            metadata={"contrato": contrato, "tipo": "ia_mcp", "abordagem": abordagem, "recipients_count": len(recipients)},
            status="success",
        )
        async with self:
            self.is_generating_ai = False
            self.is_streaming = False

    async def _stream_ai_text_with_tools(self, messages: list[dict], client_id: str, contrato: str) -> str:
        """
        Streaming com suporte a tool calls (execute_sql, search_documents, get_schema_info).
        Usa o mesmo ai_client do Chat IA + processa tool calls inline.
        """
        from bomtempo.core.ai_client import ai_client
        from bomtempo.core.ai_tools import AI_TOOLS, execute_tool

        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        # Extrai system_msg e converte para formato sem "system" role inline
        system_msg = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        user_msgs = [m for m in messages if m["role"] != "system"]

        def _run():
            try:
                # Fase 1: Agentic loop — IA pode fazer múltiplas tool calls antes de escrever
                current_messages = list(user_msgs)
                MAX_TOOL_ROUNDS = 8
                for _round in range(MAX_TOOL_ROUNDS):
                    # Feedback visual de progresso MCP
                    asyncio.run_coroutine_threadsafe(
                        q.put(f"__FEEDBACK__:Consultando dados do projeto (Rodada {_round + 1})..."),
                        loop
                    )
                    
                    # Tenta com tools primeiro via AI executor pool
                    resp_future = get_ai_executor().submit(
                        ai_client.query,
                        messages=current_messages,
                        system_prompt=system_msg,
                        tools=AI_TOOLS,
                        max_tokens=4000,
                    )
                    resp = resp_future.result()
                    if not resp:
                        break

                    # Se a resposta contém tool_calls, processa e continua
                    if isinstance(resp, dict) and resp.get("tool_calls"):
                        tool_results = []
                        for tc in resp["tool_calls"]:
                            tool_name = tc.get("function", {}).get("name", "")
                            try:
                                import json as _j
                                args = _j.loads(tc.get("function", {}).get("arguments", "{}"))
                                # Injeta filtros de tenant automaticamente
                                if tool_name == "execute_sql":
                                    query = args.get("query", "")
                                    # Valida que a query filtra por tenant
                                    if client_id and f"'{client_id}'" not in query and client_id not in query:
                                        if "WHERE" in query.upper():
                                            query = query + f" AND client_id = '{client_id}'"
                                        else:
                                            query = query + f" WHERE client_id = '{client_id}'"
                                    args["query"] = query
                                result = execute_tool(tool_name, args, client_id=client_id, contrato=contrato)
                            except Exception as te:
                                result = f"Erro na tool {tool_name}: {te}"
                            tool_results.append({"tool_call_id": tc.get("id", ""), "content": str(result)})

                        current_messages.append({"role": "assistant", "tool_calls": resp["tool_calls"]})
                        for tr in tool_results:
                            current_messages.append({"role": "tool", **tr})
                        continue  # próxima rodada

                    # Resposta textual final — streama
                    text_resp = resp if isinstance(resp, str) else str(resp)
                    for chunk in text_resp:
                        asyncio.run_coroutine_threadsafe(q.put(chunk), loop)
                    break

                # Fallback: streaming simples sem tools se o agentic loop falhou
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(q.put(f"__STREAM_ERROR__:{exc}"), loop)
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)

        threading.Thread(target=_run, daemon=True).start()

        full_text = ""
        last_update = time.monotonic()
        received_first = False

        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.error("MCP report streaming timeout after 120s")
                break

            if chunk is None:
                break

            if isinstance(chunk, str) and chunk.startswith("__STREAM_ERROR__:"):
                err = chunk.split(":", 1)[1] if ":" in chunk else "Erro desconhecido"
                async with self:
                    self.ai_report_text = f"**Erro:** {err[:300]}\n\nTente novamente."
                    self.error_msg = err[:200]
                return ""

            if isinstance(chunk, str) and chunk.startswith("__FEEDBACK__:"):
                msg = chunk.split(":", 1)[1]
                async with self:
                    self.ai_report_text = f"_{msg}_"
                continue

            full_text += chunk
            now = time.monotonic()

            if not received_first or (now - last_update >= 0.20):
                async with self:
                    self.ai_report_text = full_text + "▌"
                received_first = True
                last_update = now

        if full_text:
            async with self:
                self.ai_report_text = full_text
        return full_text

    # ── Enviar relatório por email ─────────────────────────────────────────────

    @rx.event(background=True)
    async def send_report_email(self, report_id: str = ""):
        """Envia o relatório atual por email para os destinatários configurados."""
        from bomtempo.state.global_state import GlobalState
        async with self:
            gs = await self.get_state(GlobalState)
            recipients = list(self.report_recipients)
            pdf_url = self.report_pdf_url
            contrato = self.selected_contrato
            if not recipients:
                self.error_msg = "Adicione pelo menos um destinatário."
                return
            if not pdf_url:
                self.error_msg = "Gere o relatório antes de enviar."
                return
            current_user = str(gs.current_user_name)

        def _send():
            try:
                from bomtempo.core.admin_tools import AdminTools
                email_list = [r.get("email") for r in recipients if r.get("email")]
                subject = f"[Bomtempo] Relatório {contrato} — {datetime.now().strftime('%d/%m/%Y')}"
                AdminTools.send_report_email(email_list, subject, contrato, pdf_url, "")
            except Exception as e:
                logger.error(f"send_report_email error: {e}")

        import asyncio as _aio
        loop = _aio.get_running_loop()
        await loop.run_in_executor(get_http_executor(), _send)
        async with self:
            self.success_msg = f"Relatório enviado para {len(recipients)} destinatário(s)."

        return full_text
