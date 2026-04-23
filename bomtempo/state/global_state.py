"""
Global State Management
"""

import asyncio
import base64
import json
import math
import re
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import reflex as rx

from bomtempo.core import weather_api
from bomtempo.core.ai_client import ai_client
from bomtempo.core.ai_context import AIContext
from bomtempo.core.analysis_service import AnalysisService
from bomtempo.core.data_loader import DataLoader
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.audit_logger import audit_log, audit_error, AuditCategory
from bomtempo.core.executors import (
    get_ai_executor,
    get_db_executor,
    get_http_executor,
    get_heavy_executor,
)
from bomtempo.core.supabase_client import sb_select, sb_insert, sb_rpc
from bomtempo.core.ai_tools import AI_TOOLS, execute_tool
from bomtempo.core.auth_utils import verify_password

logger = get_logger(__name__)

from datetime import timezone
_BRT = timezone(timedelta(hours=-3))


# ── Schema context cache (TTL 5 min) — avoid 1 RPC call per chat message ──────
_schema_cache: dict = {"text": None, "fetched_at": 0.0}
_SCHEMA_TTL = 300.0  # 5 minutes


def _get_schema_context() -> str:
    import time as _time
    now = _time.monotonic()
    if _schema_cache["text"] and (now - _schema_cache["fetched_at"]) < _SCHEMA_TTL:
        return _schema_cache["text"]
    try:
        result = sb_rpc("get_schema_context")
        text = str(result) if result else ""
        _schema_cache["text"] = text
        _schema_cache["fetched_at"] = now
        return text
    except Exception:
        return _schema_cache["text"] or ""


def _extract_document_text(url: str, nome: str, max_chars: int = 8000) -> str:
    """Baixa um arquivo do Supabase Storage e extrai texto para contexto da IA.
    Suporta PDF (via PyPDF2), TXT, e ignora binários não suportados.
    Retorna string com o texto extraído (máx max_chars), ou "" em caso de falha.
    """
    if not url:
        return ""
    try:
        import httpx
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return ""
        raw = resp.content
        ext = (nome.rsplit(".", 1)[-1].lower() if "." in nome else "").strip()

        if ext == "pdf":
            try:
                import io
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(raw))
                pages_text = []
                for page in reader.pages[:30]:  # max 30 páginas
                    t = page.extract_text() or ""
                    if t.strip():
                        pages_text.append(t.strip())
                text = "\n".join(pages_text)
            except ImportError:
                # PyPDF2 não instalado — tenta extração bruta
                text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""
        elif ext in ("txt", "md", "csv"):
            text = raw.decode("utf-8", errors="replace")
        elif ext in ("docx",):
            try:
                import io
                from docx import Document as DocxDocument
                doc = DocxDocument(io.BytesIO(raw))
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception:
                text = ""
        else:
            # Tenta decode como texto; se parecer binário, ignora
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                text = ""

        # Remove excesso de linhas em branco
        import re as _re
        text = _re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


def _fmt_date_br(ts: str) -> str:
    """YYYY-MM-DD (or ISO timestamp) → DD/MM/YYYY. Returns '—' for empty/invalid."""
    if not ts or ts in ("—", "None", "nan"):
        return "—"
    try:
        parts = ts[:10].split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return ts[:10]


def _fmt_datetime_brt(ts: str) -> str:
    """ISO UTC timestamp → DD/MM/YYYY HH:MM (BRT, UTC-3)."""
    if not ts or ts in ("—", "None", "nan"):
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")[:32])
        brt = dt.astimezone(_BRT)
        return brt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ts[:16].replace("T", " ")


def _msg(role: str, content: str, chart_json: str = "", chart_id: str = "") -> dict:
    """Cria um dict de mensagem com todos os campos esperados pelo chat_bubble."""
    return {"role": role, "content": content, "chart_json": chart_json, "chart_id": chart_id}


class GlobalState(rx.State):
    """Estado global da aplicação"""

    # --- AI & Voice Chat State ---
    chat_history: list[dict] = []
    chat_input: str = ""
    current_question: str = ""
    is_processing_chat: bool = False
    chat_tool_label: str = ""   # Status interno da tool em execução (exibido no typing indicator)
    chat_session_id: str = ""

    # Gráfico pendente — preenchido quando IA chama generate_chart_data
    # Injetado como campo "chart_json" na mensagem final antes de limpar
    _pending_chart_json: str = ""  # JSON serializado do gráfico

    # Conversation Mode (Hands-Free)
    is_recording: bool = False  # Legacy compatibility
    is_talking_mode: bool = False
    is_recording_voice: bool = False
    is_processing_voice: bool = False
    is_listening: bool = True  # Ready for next loop
    is_speaking: bool = False  # UI State for "AI Speaking"
    latest_audio_src: str = ""
    last_spoken_response: str = ""  # Subtitles/Legenda

    def _as_data_dict(self) -> dict:
        """Reconstrói o dict de DataFrames a partir das vars por domínio.
        Usado pelos módulos de IA que precisam do dict completo como contexto."""
        return {
            "contratos":    self._contratos_df,
            "projeto":      self._projetos_df,
            "obras":        self._obras_df,
            "financeiro":   self._financeiro_df,
            "om":           self._om_df,
            "hub_historico": self._hub_historico_df,
        }

    def update_projetos_list_progress(self, contrato: str, progress_map: dict):
        """Update conclusao_pct and peso_pct in projetos_list for a given contract.
        projetos_list is a reactive Reflex var — updating it triggers filtered_contratos recompute.
        progress_map: {row_id: {"conclusao_pct": float, "peso_pct": float}}
        """
        if not contrato or not progress_map:
            return
        updated = []
        for row in self.projetos_list:
            if str(row.get("contrato", "")) == contrato:
                row_id = str(row.get("id", ""))
                if row_id in progress_map:
                    row = dict(row)
                    vals = progress_map[row_id]
                    row["conclusao_pct"] = float(vals.get("conclusao_pct", row.get("conclusao_pct", 0)))
                    row["peso_pct"] = float(vals.get("peso_pct", row.get("peso_pct", 1)))
            updated.append(row)
        self.projetos_list = updated

    def patch_projetos_progress(self, contrato: str, progress_map: dict):
        """Patch ONLY conclusao_pct and peso_pct in _projetos_df for rows matching this contract.
        Uses id-keyed map so existing rows are updated in-place — all other columns preserved.
        Called by HubState.load_cronograma after a fresh Supabase fetch.
        progress_map: {row_id: {"conclusao_pct": float, "peso_pct": float}}
        """
        if not contrato or not progress_map or self._projetos_df is None or self._projetos_df.empty:
            return
        df = self._projetos_df
        if "contrato" not in df.columns or "id" not in df.columns:
            return
        try:
            mask = df["contrato"] == contrato
            for idx in df[mask].index:
                row_id = str(df.at[idx, "id"])
                if row_id in progress_map:
                    vals = progress_map[row_id]
                    if "conclusao_pct" in vals:
                        df.at[idx, "conclusao_pct"] = float(vals["conclusao_pct"])
                    if "peso_pct" in vals:
                        df.at[idx, "peso_pct"] = float(vals["peso_pct"])
            self._projetos_df = df
        except Exception:
            pass  # Non-critical

    async def ensure_data_loaded(self):
        """Lazy load data if not present"""
        if self._contratos_df.empty and self._projetos_df.empty:
            loader = DataLoader(client_id=self.current_client_id)
            raw = loader.load_all()
            self._contratos_df    = raw.get("contratos",      pd.DataFrame())
            self._projetos_df     = raw.get("projeto",        pd.DataFrame())
            self._obras_df        = raw.get("obras",          pd.DataFrame())
            self._financeiro_df   = raw.get("financeiro",     pd.DataFrame())
            self._om_df           = raw.get("om",             pd.DataFrame())
            self._hub_historico_df = raw.get("hub_historico", pd.DataFrame())
            self.data_version += 1


    async def send_message(self):
        """Envia mensagem para a IA e processa resposta com streaming real."""
        question = self.current_question
        if not question.strip():
            return

        self.chat_history.append(_msg("user", question))
        self.current_question = ""
        self.is_processing_chat = True
        yield rx.call_script("window.scrollToBottom('chat-container')")
        yield GlobalState.stream_chat_bg

    async def load_chat_history(self):
        """Abre o chat sempre com sessão limpa. O banco existe só para contexto da IA."""
        import asyncio as _asyncio
        username = self.current_user_name or "anonymous"
        client_id = self.current_client_id or None
        loop = _asyncio.get_running_loop()
        new_sess = await loop.run_in_executor(
            get_db_executor(),
            lambda: sb_insert("chat_sessions", {"title": "Conversa", "username": username, "client_id": client_id})
        )
        if new_sess:
            self.chat_session_id = new_sess["id"] if isinstance(new_sess, dict) else new_sess[0]["id"]
        self.chat_history = [_msg("assistant", "👋 Olá! Sou o Bomtempo Intelligence. Como posso ajudar com seus dados hoje?")]
        self.is_processing_chat = False
        yield rx.call_script("setTimeout(function(){ window.scrollToBottom('chat-container'); }, 150);")

    async def new_conversation(self):
        """Inicia uma nova conversa — cria nova sessão no banco e limpa o histórico local."""
        import asyncio as _asyncio
        username = self.current_user_name or "anonymous"
        client_id = self.current_client_id or None
        loop = _asyncio.get_running_loop()
        new_sess = await loop.run_in_executor(
            get_db_executor(),
            lambda: sb_insert("chat_sessions", {"title": "Conversa", "username": username, "client_id": client_id})
        )
        if new_sess:
            self.chat_session_id = new_sess["id"] if isinstance(new_sess, dict) else new_sess[0]["id"]
        self.chat_history = [_msg("assistant", "👋 Conversa reiniciada! Como posso ajudar?")]
        self.is_processing_chat = False
        yield rx.call_script("window.scrollToBottom('chat-container')")

    @rx.event(background=True)
    async def save_chat_msg(self, role: str, content: str, tool_calls: any = None, tool_call_id: str = None):
        """Salva mensagem no DB — background para não bloquear event loop."""
        async with self:
            session_id = self.chat_session_id
        if not session_id:
            return
        data = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "tool_call_id": tool_call_id,
        }
        try:
            import asyncio as _aio_msg
            _msg_loop = _aio_msg.get_running_loop()
            await _msg_loop.run_in_executor(get_db_executor(), lambda: sb_insert("chat_messages", data))
            await _msg_loop.run_in_executor(get_db_executor(), lambda: sb_rpc("update_session_timestamp", {"sess_id": session_id}))
        except Exception as e:
            logger.warning(f"save_chat_msg falhou (não crítico): {e}")

    @rx.event(background=True)
    async def stream_chat_bg(self):
        """Loop Agêntico com suporte a Tools e persistência."""
        import time

        # ── Bloco único: lê todo o state necessário de uma vez, sem I/O dentro do lock ──
        async with self:
            question = self.chat_history[-1]["content"] if self.chat_history and self.chat_history[-1]["role"] == "user" else ""
            is_mobile = self.current_user_role == "Gestão-Mobile"
            tenant_name = self.current_client_name
            # Garantia: se qualquer exceção não capturada ocorrer abaixo,
            # is_processing_chat é resetado via try/except no final desse handler.
            _stream_client_id = str(self.current_client_id or "")
            _selected_contrato = self.selected_contrato or self.obras_selected_contract or ""
            _needs_data_load = self._contratos_df.empty and self._projetos_df.empty
            _client_id_for_loader = self.current_client_id
            self.save_chat_msg("user", question)

        system_prompt = AIContext.get_system_prompt(is_mobile=is_mobile, tenant_name=tenant_name, client_id=_stream_client_id)

        # Injeta dados reais do painel (contexto do dashboard) + schema para o agente
        # DataLoader.load_all() roda FORA do lock para não bloquear o state mutex
        if _needs_data_load:
            import asyncio as _aio_load
            _load_loop = _aio_load.get_running_loop()
            raw = await _load_loop.run_in_executor(
                None, lambda: DataLoader(client_id=_client_id_for_loader).load_all()
            )
            async with self:
                self._contratos_df    = raw.get("contratos",      pd.DataFrame())
                self._projetos_df     = raw.get("projeto",        pd.DataFrame())
                self._obras_df        = raw.get("obras",          pd.DataFrame())
                self._financeiro_df   = raw.get("financeiro",     pd.DataFrame())
                self._om_df           = raw.get("om",             pd.DataFrame())
                self._hub_historico_df = raw.get("hub_historico", pd.DataFrame())
                self.data_version += 1

        async with self:
            data_snapshot = self._as_data_dict()

        dashboard_context = AIContext.get_dashboard_context(data_snapshot)
        schema_context = _get_schema_context()

        # Inject doc awareness from hub_timeline — inclui conteúdo real dos arquivos
        doc_context_str = ""
        try:
            # _selected_contrato já lido no bloco inicial acima
            if _selected_contrato:
                _tl_filters: dict = {"contrato": _selected_contrato, "is_document": True}
                if _stream_client_id:
                    _tl_filters["client_id"] = _stream_client_id
                import asyncio as _aio_doc
                _doc_loop = _aio_doc.get_running_loop()
                doc_rows = await _doc_loop.run_in_executor(
                    get_db_executor(),
                    lambda: sb_select("hub_timeline", filters=_tl_filters)
                )
                if doc_rows:
                    doc_sections = []
                    for d in doc_rows:
                        titulo = d.get("titulo", "") or ""
                        descricao = d.get("descricao", "") or ""
                        anexo_url = d.get("anexo_url", "") or ""
                        anexo_nome = d.get("anexo_nome", "") or ""
                        section = f"### {titulo}"
                        if anexo_nome:
                            section += f" [{anexo_nome}]"
                        if descricao:
                            section += f"\nDescrição: {descricao[:300]}"
                        # Tenta extrair texto do arquivo
                        if anexo_url:
                            file_text = _extract_document_text(anexo_url, anexo_nome)
                            if file_text:
                                section += f"\nConteúdo:\n{file_text}"
                        doc_sections.append(section)
                    doc_context_str = (
                        "\n\n## DOCUMENTOS DO CONTRATO " + _selected_contrato +
                        " (leia com atenção para responder perguntas sobre o contrato):\n\n" +
                        "\n\n".join(doc_sections)
                    )
        except Exception:
            pass

        tenant_sql_hint = (
            f"\n\n⚠️ ISOLAMENTO DE TENANT: SEMPRE inclua `WHERE client_id = '{_stream_client_id}'`"
            f" em TODAS as queries SQL quando o client_id for conhecido."
        ) if _stream_client_id else ""

        messages = [{
            "role": "system",
            "content": (
                system_prompt
                + dashboard_context
                + f"\n\n## SCHEMA DO BANCO (para queries SQL)\n{schema_context}{tenant_sql_hint}"
                + doc_context_str
            ),
        }]
        
        async with self:
            history = [m for m in self.chat_history if m["content"]][-6:]
        messages.extend(history)

        # LOOP AGÊNTICO
        max_iterations = 5
        pending_chart_json = ""
        pending_chart_id = ""
        for i in range(max_iterations):
            # force_tool=True na primeira iteração evita que a IA "anuncie" antes de agir
            try:
                response = ai_client.query_agentic(messages, tools=AI_TOOLS, force_tool=(i == 0))
            except Exception as _ai_err:
                logger.error(f"stream_chat_bg: ai_client falhou na iteração {i}: {_ai_err}")
                async with self:
                    self.chat_history.append(_msg("assistant", "❌ Erro ao processar. Tente novamente."))
                    self.is_processing_chat = False
                    self.chat_tool_label = ""
                    yield rx.call_script("window.scrollToBottom('chat-container')")
                break

            if isinstance(response, str):
                final_content = re.sub(r'!\[.*?\]\(.*?\)', '', response).strip()
                async with self:
                    self.chat_history.append(_msg("assistant", final_content, chart_json=pending_chart_json, chart_id=pending_chart_id))
                    self.save_chat_msg("assistant", final_content)
                    self.is_processing_chat = False
                    self.chat_tool_label = ""
                    self._pending_chart_json = ""
                    if pending_chart_json and pending_chart_id:
                        safe_json = pending_chart_json.replace("`", "\\`")
                        yield rx.call_script(
                            f"window.__btpCharts = window.__btpCharts || {{}}; "
                            f"window.__btpCharts['{pending_chart_id}'] = {safe_json};"
                        )
                    yield rx.call_script("window.scrollToBottom('chat-container')")
                break

            # tool_call — serializa como dict para a API
            tool_calls = response.tool_calls
            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            for tool_call in tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                # Atualiza label interno — exibido no typing_indicator, não no chat
                async with self:
                    self.chat_tool_label = "gerando gráfico..." if name == "generate_chart_data" else "consultando banco..."

                result = execute_tool(name, args)

                if name == "generate_chart_data":
                    try:
                        parsed = json.loads(result)
                        if parsed.get("__chart__"):
                            pending_chart_json = result
                            pending_chart_id = f"chart_{tool_call.id.replace('-', '_')}"
                    except Exception:
                        pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result,
                })
        else:
            fallback = "Não consegui concluir a análise. Tente reformular a pergunta."
            async with self:
                self.chat_history.append(_msg("assistant", fallback))
                self.is_processing_chat = False
                self.chat_tool_label = ""
                self._pending_chart_json = ""
                yield rx.call_script("window.scrollToBottom('chat-container')")

    @rx.event(background=True)
    async def reset_chat_processing(self):
        """Safety valve: reseta is_processing_chat se o stream_chat_bg falhar."""
        async with self:
            if self.is_processing_chat:
                self.is_processing_chat = False
                self.chat_tool_label = ""
                self.chat_history.append(_msg("assistant", "❌ Erro interno no processamento. Tente novamente."))
                yield rx.call_script("window.scrollToBottom('chat-container')")

    async def process_voice_input(self, text: str):
        """Receives transcribed text — funnels through the same agentic pipeline as typed messages."""
        if not text:
            return
        self.is_recording = False
        self.is_recording_voice = False
        # Reutiliza exatamente o mesmo fluxo do send_message: agentic loop + tool calls + charts
        self.current_question = text
        async for ev in self.send_message():
            yield ev

    async def process_audio_blob(self, base64_data: str):
        """Receives base64 audio and transcribes."""
        if not base64_data:
            return
        self.is_processing_chat = True
        self.is_recording = False
        self.is_recording_voice = False
        try:
            if "," in base64_data:
                header, encoded = base64_data.split(",", 1)
            else:
                encoded = base64_data
            ext = ".webm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(base64.b64decode(encoded))
                tmp_path = tmp_file.name
            transcript = ai_client.transcribe_audio(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
            if transcript:
                self.chat_input = transcript
                await self.send_message()
            else:
                yield rx.window_alert("Não foi possível transcrever o áudio.")
                self.is_processing_chat = False
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            self.is_processing_chat = False

    def start_recording(self):
        self.is_recording = True

    def stop_recording(self):
        self.is_recording = False

    def toggle_talking_mode(self):
        self.is_talking_mode = not self.is_talking_mode
        if not self.is_talking_mode:
            self.disable_talking_mode()

    def disable_talking_mode(self):
        self.is_talking_mode = False
        self.is_recording_voice = False
        self.is_processing_voice = False
        self.is_speaking = False
        self.latest_audio_src = ""
        self.last_spoken_response = ""
        self.is_recording = False

    def toggle_voice_recording(self):
        self.is_recording_voice = not self.is_recording_voice
        self.is_recording = self.is_recording_voice
        if self.is_recording_voice:
            return rx.call_script("if(window.startRecording) window.startRecording()")

    def audio_loaded(self):
        pass

    def audio_error(self):
        self.is_speaking = False

    def audio_ended(self):
        self.is_speaking = False
        if self.is_talking_mode:
            return rx.call_script(
                "if(window.startRecording) setTimeout(() => window.startRecording(), 500)"
            )

    def inject_conversation(self, user_text: str, ai_text: str):
        """
        Updates chat history with externally processed conversation (e.g., from API).
        Used to sync UI after JS-driven Audio/Text fetch.
        """
        if user_text:
            self.chat_history.append(_msg("user", user_text))
        if ai_text:
            self.chat_history.append(_msg("assistant", ai_text))
            self.last_spoken_response = ai_text

        self.is_processing_chat = False
        self.is_listening = True  # Ready for next loop
        self.current_question = ""
        yield rx.call_script("window.clearChatInput()")
        yield rx.call_script("window.scrollToBottom('chat-container')")

    def inject_conversation_json(self, json_data: str):
        """
        Wrapper for inject_conversation that parses JSON string.
        Bound to hidden input for JS-to-Python communication.
        """
        try:
            data = json.loads(json_data)
            self.inject_conversation(data.get("user", ""), data.get("ai", ""))
        except Exception as e:
            print(f"Error injecting conversation: {e}")

    # Dados brutos — vars separadas por domínio para que o Reflex rastreie
    # dependências granulares. Quando só _contratos_df muda, apenas as @rx.var
    # que dependem dela são invalidadas (em vez de todos os 40+ vars de _data).
    _contratos_df: pd.DataFrame = pd.DataFrame()
    _projetos_df: pd.DataFrame = pd.DataFrame()
    _obras_df: pd.DataFrame = pd.DataFrame()
    _financeiro_df: pd.DataFrame = pd.DataFrame()
    _om_df: pd.DataFrame = pd.DataFrame()
    _hub_historico_df: pd.DataFrame = pd.DataFrame()

    # Versão dos dados — incrementa a cada recarga. Lida por @rx.cached_var
    # para garantir invalidação do cache quando os dados mudam (var privada).
    data_version: int = 0

    # Flags de carregamento
    is_loading: bool = False
    is_navigating: bool = False       # Feedback imediato no clique de navegação (antes do round-trip)
    initial_loading: bool = False  # Loading screen after login
    show_loading_screen: bool = False  # Full-screen loading overlay
    is_authenticating: bool = False   # Intermediate auth button state (login page)
    error_message: str = ""

    # --- Forgot Password State ---
    forgot_password_email: str = ""
    forgot_password_error: str = ""
    forgot_password_success: bool = False
    is_sending_reset: bool = False
    show_forgot_password: bool = False

    def toggle_forgot_password(self):
        self.show_forgot_password = not self.show_forgot_password
        self.forgot_password_error = ""
        self.forgot_password_success = False
        self.forgot_password_email = ""

    @rx.event(background=True)
    async def send_reset_link(self):
        import asyncio as _asyncio
        async with self:
            if not self.forgot_password_email or "@" not in self.forgot_password_email:
                self.forgot_password_error = "Por favor, digite um email válido."
                return
            self.is_sending_reset = True
            self.forgot_password_error = ""
            _email = str(self.forgot_password_email)

        def _do_reset(email: str):
            from bomtempo.core.supabase_client import sb_select, sb_insert
            user = sb_select("login", filters={"email": email}, limit=1)
            if user:
                import secrets as _secrets
                token = _secrets.token_urlsafe(32)
                expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
                sb_insert("password_reset_tokens", {
                    "user_id": user[0]["id"],
                    "token": token,
                    "expires_at": expires_at,
                })
                from bomtempo.core.email_service import EmailService
                from bomtempo.core.config import Config
                reset_link = f"{Config.APP_URL}/reset-password?token={token}"
                EmailService.send_password_reset_email(email, reset_link)

        try:
            loop = _asyncio.get_running_loop()
            await loop.run_in_executor(get_db_executor(), lambda: _do_reset(_email))
            async with self:
                self.forgot_password_success = True
        except Exception as e:
            logger.error(f"Reset link error: {e}")
            async with self:
                self.forgot_password_error = "Ocorreu um erro no servidor. Tente novamente."
        finally:
            async with self:
                self.is_sending_reset = False

    # Dados processados para UI
    contratos_list: List[Dict[str, Any]] = []
    projetos_list: List[Dict[str, Any]] = []
    obras_list: List[Dict[str, Any]] = []
    financeiro_list: List[Dict[str, Any]] = []
    om_list: List[Dict[str, Any]] = []
    users_list: List[Dict[str, Any]] = []

    # Métricas Globais
    total_contratos: int = 0
    valor_tcv: float = 0.0
    contratos_ativos: int = 0

    # Projetos page state
    selected_contrato: str = ""
    projetos_search: str = ""
    projetos_fase_filter: str = ""

    # Obras page state (legacy — kept for backwards compat with relatorios.py etc.)
    obras_selected_contract: str = ""
    obra_insight_text: str = ""
    obra_insight_loading: bool = False
    obra_insight_generated_at: str = ""   # ISO timestamp of last cached insight
    obras_navigating: bool = False   # True while transitioning list→detail or back
    _insight_target: str = ""  # Contrato alvo do último disparo de insight (cancel guard)

    # ── Unified Gestão de Projetos Hub ──────────────────────────
    selected_project: str = ""          # Unified: contract code e.g. "BOM010-24"
    project_hub_tab: str = "visao_geral"  # Active tab
    project_search: str = ""            # Search term for pulse cards list
    project_status_filter: str = ""     # Status filter
    project_campo_rdos: List[Dict[str, Any]] = []
    project_campo_loading: bool = False

    # ── Dashboard filters ────────────────────────────────────────────────────
    dash_filter_period: str = "all"       # "7d" | "30d" | "90d" | "all"
    dash_filter_macro: str = ""           # fase_macro filter (empty = all)
    dash_filter_responsavel: str = ""     # responsavel filter (empty = all)

    def set_dash_filter_period(self, v: str): self.dash_filter_period = v
    def set_dash_filter_macro(self, v: str): self.dash_filter_macro = v
    def set_dash_filter_responsavel(self, v: str): self.dash_filter_responsavel = v

    # ── Theme toggle ─────────────────────────────────────────────────────────
    is_light_mode: bool = False

    def toggle_theme(self):
        self.is_light_mode = not self.is_light_mode
        if self.is_light_mode:
            return rx.call_script(
                "(function(){"
                # Set on <html> — survives before body is available; CSS targets html[data-theme='light']
                "document.documentElement.setAttribute('data-theme','light');"
                # Also swap Radix root classes for their own theming
                "['[data-is-root-theme]','.radix-themes'].forEach(function(sel){"
                "  var el=document.querySelector(sel);"
                "  if(el){el.classList.remove('dark');el.classList.add('light');"
                "  el.setAttribute('data-appearance','light');}"
                "});"
                "try{localStorage.setItem('bomtempo-theme','light');}catch(e){}"
                "})()"
            )
        else:
            return rx.call_script(
                "(function(){"
                "document.documentElement.removeAttribute('data-theme');"
                "['[data-is-root-theme]','.radix-themes'].forEach(function(sel){"
                "  var el=document.querySelector(sel);"
                "  if(el){el.classList.remove('light');el.classList.add('dark');"
                "  el.setAttribute('data-appearance','dark');}"
                "});"
                "try{localStorage.setItem('bomtempo-theme','dark');}catch(e){}"
                "})()"
            )

    # ── Hub filters panel ────────────────────────────────────────────────────
    hub_show_filters: bool = False
    hub_filter_tipo: str = ""        # EPC | O&M | Fornecimento | Consultoria | ""
    hub_filter_priority: str = ""    # Alta | Média | Baixa | ""

    # ── Duplicar Projeto ─────────────────────────────────────────────────────
    show_duplicar_projeto: bool = False
    dup_source_contrato: str = ""

    # ── Novo Projeto form ────────────────────────────────────────────────────
    show_novo_projeto: bool = False
    np_form_key: int = 0           # incrementado ao abrir → força remount dos inputs
    np_contrato: str = ""
    np_projeto: str = ""
    np_cliente: str = ""
    np_terceirizado: str = ""
    np_localizacao: str = ""
    # HITL geocoding validation
    np_loc_validating: bool = False
    np_loc_geocoded_name: str = ""    # "Guaiúba, Ceará, Brasil" — shown for confirmation
    np_loc_geocoded_lat: str = ""
    np_loc_geocoded_lon: str = ""
    np_loc_confirmed: bool = False    # True after user confirms
    np_loc_error: str = ""
    np_loc_input_key: int = 0         # incremented on reject → forces input remount (clears field)
    # Edit projeto geocoding
    ep_loc_validating: bool = False
    ep_loc_geocoded_name: str = ""
    ep_loc_geocoded_lat: str = ""
    ep_loc_geocoded_lon: str = ""
    ep_loc_confirmed: bool = False
    ep_loc_error: str = ""
    ep_loc_input_key: int = 0         # incremented on reject → forces input remount
    np_data_inicio: str = ""
    np_data_termino: str = ""
    np_tipo: str = "EPC"
    np_potencia_kwp: str = ""
    np_prazo_dias: str = ""
    np_priority: str = "Média"
    np_efetivo_planejado: str = ""
    np_valor_contratado: str = ""
    np_dias_uteis: List[str] = ["seg", "ter", "qua", "qui", "sex"]
    np_saving: bool = False
    np_error: str = ""

    # ── Editar Projeto ───────────────────────────────────────────────────────
    show_edit_projeto: bool = False
    ep_form_key: int = 0
    ep_id: str = ""                # UUID da row em contratos
    ep_contrato: str = ""
    ep_projeto: str = ""
    ep_cliente: str = ""
    ep_terceirizado: str = ""
    ep_localizacao: str = ""
    ep_data_inicio: str = ""
    ep_data_termino: str = ""
    ep_tipo: str = "EPC"
    ep_potencia_kwp: str = ""
    ep_prazo_dias: str = ""
    ep_priority: str = "Média"
    ep_efetivo_planejado: str = ""
    ep_dias_uteis: List[str] = ["seg", "ter", "qua", "qui", "sex"]
    ep_saving: bool = False
    ep_deleting: bool = False
    ep_error: str = ""
    ep_confirm_delete: bool = False

    # ── Hub de Operações (replaces separate obras/projetos) ──────────────────
    hub_tab: str = "visao_geral"  # visao_geral|dashboard|cronograma|auditoria|timeline
    global_search: str = ""

    # O&M page state
    om_time_filter: str = ""  # Empty = no time filter applied

    # ── GLOBAL FILTERS (Visão Geral, O&M, Financeiro) ──────────
    global_project_filter: str = ""  # "" means "Todos"
    om_project_filter: str = ""  # "" means "Todos"
    fin_project_filter: str = ""  # "" means "Todos"

    # ── Financeiro chart cache — calculado só ao mudar dados/filtro ──────────
    # Substitui @rx.var com groupby+cumsum que rodavam em CADA render
    financeiro_cockpit_chart: List[Dict[str, Any]] = []
    financeiro_scurve_chart: List[Dict[str, Any]] = []

    # ── KPI Popup rows cache — calculado em load_data e set_fin_project_filter ──
    # Substitui @rx.var com DataFrame+groupby que rodavam em CADA render
    fin_contrato_rows: List[Dict[str, Any]] = []
    fin_cockpit_popup_rows: List[Dict[str, Any]] = []
    contratos_ativos_rows: List[Dict[str, Any]] = []

    # Weather State
    weather_data: Dict[str, Any] = {}
    weather_loading: bool = False
    weather_risk_level: str = "Low"

    # Analysis Service State
    current_page_kpis: Dict[str, Any] = {}
    analysis_result: str = ""
    is_analyzing: bool = False
    is_streaming: bool = False  # True while chunks arriving, False when done
    show_analysis_dialog: bool = False
    _pending_page_name: str = ""  # Used by background streaming event

    # KPI Detail Popup State
    show_kpi_detail: str = ""  # "" | "total_contratado" | "total_medido" | "saldo_medir" | "contratos_ativos" | "receita_total"

    def set_analysis_dialog_open(self, value: bool):
        self.show_analysis_dialog = value
        if not value:
            self.analysis_result = ""
            self.is_streaming = False

    def close_analysis_dialog(self):
        self.set_analysis_dialog_open(False)

    def handle_detail_open_change(self, is_open: bool):
        if not is_open:
            self.show_kpi_detail = ""

    @rx.event(background=True)
    async def analyze_current_view(self):
        """Processes current page KPIs — fully non-blocking background event."""
        # ── Step 1: Read all state vars inside lock ───────────────────────────
        data = {}
        page_name = "Visão Geral"

        async with self:
            path = self.router.url.strip("/") or "index"
            if path in ["index", "visão geral", ""]:
                page_name = "Briefing Executivo — Visão Geral"
                # Cross-module context: financeiro + físico + cronograma para briefing real
                acts = list(self.filtered_projetos) if self.filtered_projetos else []
                criticos_pend = [p for p in acts if str(p.get("critico", "")).lower() == "sim" and float(p.get("conclusao_pct", 0) or 0) < 100]
                criticos_atrasados = []
                from datetime import date as _dtoday
                _hoje = _dtoday.today().isoformat()
                for p in criticos_pend:
                    term = str(p.get("termino_previsto", ""))[:10]
                    if term and term < _hoje:
                        criticos_atrasados.append(f"{p.get('atividade','')} ({p.get('contrato','')}): {p.get('conclusao_pct',0)}%")
                data = {
                    "__briefing_mode__": "cross_module",
                    "Total Contratos Ativos": self.total_contratos,
                    "Valor em Carteira": self.valor_carteira_formatado,
                    "Volume Financeiro Realizado": self.financeiro_realizado_fmt,
                    "Margem Operacional Global": self.margem_pct_fmt,
                    "Avanço Físico Global": self.avanco_fisico_geral_fmt,
                    "Obras em Atraso": self.obras_atrasadas_count,
                    "Atividades Críticas Pendentes": len(criticos_pend),
                    "Caminho Crítico em Atraso": "; ".join(criticos_atrasados[:3]) if criticos_atrasados else "Nenhum detectado",
                    "Exec. Financeira vs Físico": f"{self.margem_pct_fmt} margem | {self.avanco_fisico_geral_fmt} avanço — detectar descasamento",
                }
            elif "obras" in path:
                page_name = "Operações de Campo"
                data = {
                    "Total de Obras": self.total_obras_andamento,
                    "Avanço Físico Médio": self.avanco_fisico_geral_fmt,
                    "Obras em Atraso": self.obras_atrasadas_count,
                }
                if self.obras_selected_contract:
                    data["Recorte"] = f"Contrato: {self.obras_selected_contract}"
                    data["Status da Obra Selecionada"] = self.obra_selected_data.get("status", "Em Execução")
            elif "financeiro" in path:
                page_name = "Performance Financeira"
                data = {
                    "Volume Contratado": self.financeiro_contratado_fmt,
                    "Volume Realizado": self.financeiro_realizado_fmt,
                    "Saldo de Medição": self.margem_bruta_fmt,
                    "Margem Perc.": self.margem_pct_fmt,
                }
            elif "projetos" in path or "hub" in path:
                if self.selected_contrato:
                    acts = list(self.filtered_projetos)
                    total_acts = len(acts)
                    avg_progress = round(sum(float(p.get("conclusao_pct", 0) or 0) for p in acts) / max(total_acts, 1), 1)
                    criticos = len([p for p in acts if str(p.get("critico", "")).lower() == "sim"])
                    atrasados = len([p for p in acts if str(p.get("critico", "")).lower() == "sim" and float(p.get("conclusao_pct", 0) or 0) < 100])
                    page_name = f"Projeto: {self.selected_contrato_data.get('cliente', self.selected_contrato)}"
                    data = {
                        "Contrato": self.selected_contrato_data.get("contrato", self.selected_contrato),
                        "Status Atual": self.selected_contrato_data.get("status", "Em Execução"),
                        "Progresso Global": f"{avg_progress}%",
                        "Total de Atividades": total_acts,
                        "Marcos Críticos (total)": criticos,
                        "Marcos Críticos (pendentes)": atrasados,
                        "Atividades Concluídas": len([p for p in acts if float(p.get("conclusao_pct", 0) or 0) >= 100]),
                    }
                else:
                    page_name = "Hub de Operações"
                    data = {
                        "Total Atividades": self.total_atividades,
                        "Atividades Concluídas": self.atividades_concluidas,
                        "Caminho Crítico (Alertas)": self.atividades_criticas_count,
                    }
            elif "om" in path:
                page_name = "O&M - Performance Energética"
                data = {
                    "Energia Injetada (Total)": self.om_energia_injetada_fmt,
                    "Performance Hidráulica/Solar": self.om_performance_fmt,
                    "Faturamento Líquido": self.om_fat_liquido_fmt,
                    "Geração Acumulada": self.om_acumulado_fmt,
                }
            elif "analytics" in path:
                page_name = "Análise Preditiva"
                data = {
                    "Atraso Médio Estimado": f"{self.analytics_atraso_medio}%",
                    "Risco de Churn": self.analytics_churn_risk,
                    "Eficiência de Entrega": f"{self.analytics_conclusao_rate}%",
                }
            else:
                # Fallback
                data = {
                    "Visão": "Geral da Plataforma",
                    "Total Contratos": self.total_contratos,
                    "Valor Carteira": self.valor_carteira_formatado,
                }

        # ── Step 2: Heavy I/O outside lock ───────────────────────────────────
        if "rdo" in path and not data:
            try:
                from bomtempo.core.rdo_service import RDOService
                from bomtempo.core.supabase_client import sb_select as _sbsel
                import asyncio
                loop = asyncio.get_running_loop()
                rdos, mo, eq = await asyncio.gather(
                    loop.run_in_executor(get_db_executor(), lambda: RDOService.get_all_rdos(limit=200, client_id=self.current_client_id or "")),
                    loop.run_in_executor(get_db_executor(), lambda: _sbsel("rdo_mao_obra", limit=1000) or []),
                    loop.run_in_executor(get_db_executor(), lambda: _sbsel("rdo_equipamentos", limit=1000) or []),
                )
                page_name = "Dashboard RDO Analytics"
                data = {
                    "Total de RDOs Emitidos": len(rdos),
                    "Obras Operando": len(set(r.get("contrato") for r in rdos if r.get("contrato"))),
                    "Profissionais em Campo": sum(int(r.get("Quantidade", 0) or 0) for r in mo),
                    "Registros de Equipamentos": len(eq),
                }
            except Exception as e:
                logger.warning(f"Erro KPI RDO: {e}")
                data = {"Seção": "RDO Analytics", "Status": "Erro ao carregar dados"}

        if not data:
            data = {"Visão": "Geral da Plataforma"}

        # ── Step 3: Set up dialog + kick off streaming inline ────────────────
        async with self:
            self.current_page_kpis = data
            self._pending_page_name = page_name
            self.is_analyzing = True
            self.show_analysis_dialog = True
            self.analysis_result = ""

        await self._run_streaming(page_name, data)

    @rx.event(background=True)
    async def stream_analysis_bg(self):
        """Background streaming event — reads pending state then delegates to _run_streaming."""
        async with self:
            page_name = self._pending_page_name
            kpis = dict(self.current_page_kpis)

        await self._run_streaming(page_name, kpis)

    async def _run_streaming(self, page_name: str, kpis: dict):
        """Core streaming logic — safe to call from both background events."""
        import threading
        import time

        if not kpis:
            async with self:
                self.is_analyzing = False
            return

        is_briefing = kpis.pop("__briefing_mode__", "") == "cross_module"
        if is_briefing:
            messages = AnalysisService.get_briefing_messages(page_name, kpis)
        else:
            messages = AnalysisService.get_kpi_analysis_messages(page_name, kpis)
        if not messages:
            async with self:
                self.analysis_result = "Não há dados suficientes para análise."
                self.is_analyzing = False
            return

        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        def _run_stream():
            try:
                for chunk in ai_client.query_stream(messages):
                    asyncio.run_coroutine_threadsafe(q.put(chunk), loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(q.put(f"__STREAM_ERROR__:{e}"), loop)
            finally:
                asyncio.run_coroutine_threadsafe(q.put(None), loop)

        thread = threading.Thread(target=_run_stream, daemon=True)
        thread.start()

        full_text = ""
        last_update = time.monotonic()
        received_first_chunk = False

        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=90.0)
            except asyncio.TimeoutError:
                logger.error("Streaming timeout after 90s")
                break

            if chunk is None:
                break

            if isinstance(chunk, str) and chunk.startswith("__STREAM_ERROR__:"):
                async with self:
                    self.analysis_result = f"Erro na análise: {chunk[17:]}"
                    self.is_analyzing = False
                    self.is_streaming = False
                return

            full_text += chunk

            now = time.monotonic()
            if not received_first_chunk or (now - last_update >= 0.35):
                async with self:
                    if not received_first_chunk:
                        self.is_analyzing = False
                        self.is_streaming = True
                        received_first_chunk = True
                    self.analysis_result = full_text + "▌"
                last_update = now

        async with self:
            self.analysis_result = self._sanitize_markdown(full_text)
            self.is_streaming = False
            self.is_analyzing = False

    # ── Navigation / Loading Computed Vars ──────────────────────────────────────

    @rx.var
    def show_progress_bar(self) -> bool:
        """True quando está navegando entre páginas OU carregando dados."""
        return self.is_loading or self.is_navigating

    @rx.var
    def is_fullscreen_page(self) -> bool:
        """True para páginas de preenchimento — sem sidebar/header."""
        path = self.router.page.path
        _fullscreen_paths = ["/rdo-form", "/rdo_form", "/rdo-historico", "/reembolso"]
        for p in _fullscreen_paths:
            if path == p or path.startswith(p + "/"):
                return True
        return False

    # ── KPI Detail Popup rows — populados em _recompute_popup_rows() ────────────
    # (declarados no bloco de vars acima junto com financeiro_cockpit_chart)

    def _recompute_popup_rows(self):
        """Recalcula as 3 listas de popup KPI. Chamado em load_data e set_fin_project_filter."""
        data = self.financeiro_list
        if self.fin_project_filter and self.fin_project_filter != "Todos":
            data = [f for f in data if f.get("contrato") == self.fin_project_filter]

        # ── fin_contrato_rows ──────────────────────────────────────────────────
        if not data:
            self.fin_contrato_rows = []
            self.fin_cockpit_popup_rows = []
        else:
            df = pd.DataFrame(data)
            # Normalizar colunas novas de fin_custos
            for col in ["valor_previsto", "valor_executado"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                else:
                    df[col] = 0.0

            if "contrato" in df.columns:
                grouped = (
                    df.groupby("contrato")
                    .agg({"valor_previsto": "sum", "valor_executado": "sum"})
                    .reset_index()
                )
                grouped["total_contratado"] = grouped["valor_previsto"]
                grouped["total_realizado"] = grouped["valor_executado"]
                grouped["saldo"] = grouped["total_contratado"] - grouped["total_realizado"]
                grouped["pct_medido"] = (
                    (grouped["total_realizado"] / grouped["total_contratado"].replace(0, float("nan")) * 100)
                    .fillna(0).round(1)
                )
                result = []
                for _, row in grouped.iterrows():
                    vc, vr, vs, pct = float(row["total_contratado"]), float(row["total_realizado"]), float(row["saldo"]), float(row["pct_medido"])
                    result.append({"contrato": str(row["contrato"]), "total_contratado_fmt": self._fmt_money(vc), "total_realizado_fmt": self._fmt_money(vr), "saldo_fmt": self._fmt_money(vs), "pct_medido": f"{pct:.1f}%"})
                self.fin_contrato_rows = result
            else:
                self.fin_contrato_rows = []

            # Cockpit popup: agora agrupa por categoria_nome
            group_col2 = "categoria_nome" if "categoria_nome" in df.columns else None
            if group_col2:
                grouped2 = (
                    df.groupby(group_col2)
                    .agg({"valor_previsto": "sum", "valor_executado": "sum"})
                    .reset_index()
                )
                grouped2["total_contratado"] = grouped2["valor_previsto"]
                grouped2["total_realizado"] = grouped2["valor_executado"]
                grouped2["pct_medido"] = (
                    (grouped2["total_realizado"] / grouped2["total_contratado"].replace(0, float("nan")) * 100)
                    .fillna(0).round(1)
                )
                grouped2 = grouped2.sort_values("total_contratado", ascending=False)
                result2 = []
                for _, row in grouped2.iterrows():
                    vc, vr, pct = float(row["total_contratado"]), float(row["total_realizado"]), float(row["pct_medido"])
                    result2.append({"cockpit": str(row[group_col2]) or "—", "total_contratado_fmt": self._fmt_money(vc), "total_realizado_fmt": self._fmt_money(vr), "pct_medido": f"{pct:.1f}%"})
                self.fin_cockpit_popup_rows = result2
            else:
                self.fin_cockpit_popup_rows = []

        # ── contratos_ativos_rows ──────────────────────────────────────────────
        active = [c for c in self.contratos_list if str(c.get("status", "")).strip() == "Em Execução"]
        self.contratos_ativos_rows = [
            {"contrato": str(c.get("contrato", "—")), "cliente": str(c.get("cliente", "—")), "status": str(c.get("status", "—")), "valor_fmt": self._fmt_money(float(c.get("valor_contratado", 0) or 0))}
            for c in active[:25]
        ]

    def _sanitize_markdown(self, text: str) -> str:
        """Extreme Failsafe: Fixes mashed tables, missing pipes, and broken column alignment."""
        if not text:
            return ""
        import re

        # Ensure spaces around bold markers so rx.markdown doesn't concatenate adjacent words.
        # e.g. "R**4M**em" → "R **4M** em"
        text = re.sub(r'(\w)\*\*', r'\1 **', text)
        text = re.sub(r'\*\*(\w)', r'** \1', text)

        lines = text.split("\n")
        sanitized = []
        in_table = False

        # Table header keywords for the C-Level KPI matrix (reconstruct if mashed by AI)
        headers_keywords = ["Alavanca Crítica", "Status Atual", "Impacto & Ação Recomendada"]

        for i, line in enumerate(lines):
            trimmed = line.strip()

            # Detect Table Block Start (even if mashed)
            is_potential_header = any(
                kw.replace(" ", "") in trimmed.replace(" ", "") for kw in headers_keywords
            )

            if is_potential_header and not in_table:
                # Forcefully reconstruct the header line
                line = "| Alavanca Crítica | Status Atual | Impacto & Ação Recomendada |"
                sanitized.append(line)
                # Inject separator
                sanitized.append("| :--- | :--- | :--- |")
                in_table = True
                continue

            if in_table:
                # Check for end of table (empty line or new header)
                if trimmed == "" or (trimmed.startswith("#")):
                    in_table = False
                elif re.match(r'^[\|\s:\-]+$', trimmed):
                    # Skip separator rows — already injected on header detection
                    continue
                elif "|" not in trimmed:
                    # Attempt to split data row into 3 columns aggressively
                    # Look for markers like "R$", "%", or multiple spaces
                    parts = []
                    # 1. First column: The indicator name (usually first few words)
                    # 2. Second column: The value (usually has numbers, R$, or %)
                    # 3. Third column: The impact (the rest)

                    # Heuristic: split by double space first
                    raw_parts = [p.strip() for p in re.split(r"\s{2,}", trimmed) if p.strip()]

                    if len(raw_parts) >= 3:
                        parts = raw_parts[:3]
                    elif len(raw_parts) == 2:
                        # Split the part that contains a value
                        m = re.search(r"([R\$]?\s?\d+[\.,]?\d*\s?[%]?\w*)", raw_parts[1])
                        if m:
                            val = m.group(1).strip()
                            impact = raw_parts[1].replace(m.group(1), "").strip()
                            parts = [raw_parts[0], val, impact]
                    else:
                        # Fallback for single-space mashed sentence
                        # Find the first value-like thing (R$, %, or number)
                        m = re.search(r"(\s[R\$]?\s?\d+[\.,]?\d*\s?[%]?\w*)", trimmed)
                        if m:
                            val = m.group(1).strip()
                            idx = trimmed.find(m.group(1))
                            if idx > 0:
                                p1 = trimmed[:idx].strip()
                                p3 = trimmed[idx + len(m.group(1)) :].strip()
                                if p1 and p3:
                                    parts = [p1, val, p3]

                    if len(parts) >= 2:
                        while len(parts) < 3:
                            parts.append("-")
                        line = "| " + " | ".join(parts[:3]) + " |"
                    else:
                        in_table = False

            sanitized.append(line)

        return "\n".join(sanitized)

    # Navigation State
    current_path: str = ""

    # Authentication State
    is_authenticated: bool = False
    username_input: str = ""
    password_input: str = ""
    login_error: str = ""
    current_user_name: str = ""
    current_user_role: str = ""
    current_user_contrato: str = ""  # Contrato associado ao usuário (Mestre de Obras)
    current_client_id: str = ""       # ID do Tenant (BOMTEMPO, PLENO, etc.)
    current_client_name: str = ""     # Nome legível do Tenant
    client_is_master: bool = False    # Se o cliente logado é o BTP MASTER
    allowed_modules: List[str] = []  # Module slugs from roles table
    active_features: List[str] = []  # Feature flags habilitadas para o contrato do usuário

    # Avatar personalization
    current_user_role_icon: str = "user"     # default icon from role row (roles.icon)
    current_user_avatar_icon: str = ""       # user-chosen icon (login.avatar_icon)
    current_user_avatar_type: str = "initial"  # "initial" or "icon" (login.avatar_type)
    show_avatar_modal: bool = False
    avatar_edit_icon: str = ""
    avatar_edit_type: str = "initial"

    # Contact info
    current_user_email: str = ""
    current_user_whatsapp: str = ""

    # Avatar modal tab ("avatar" | "senha" | "contato") + password fields
    avatar_modal_tab: str = "avatar"
    pw_current: str = ""
    pw_new: str = ""
    pw_confirm: str = ""
    pw_error: str = ""
    pw_success: bool = False
    # Contato edit fields
    contact_edit_email: str = ""
    contact_edit_whatsapp: str = ""
    contact_error: str = ""
    contact_success: bool = False

    # ── In-app Notifications ─────────────────────────────────
    # Each dict: {id, message, source_type, source_id, contrato, read, created_at_fmt}
    notifications_list: List[Dict[str, str]] = []
    notif_unread_count: int = 0

    async def check_login_on_enter(self, key: str):
        """Login apenas se Enter for pressionado"""
        if key == "Enter":
            yield GlobalState.check_login

    async def logout(self):
        """Sai da plataforma"""
        audit_log(
            category=AuditCategory.LOGOUT,
            action=f"Usuário '{self.current_user_name}' fez logout",
            username=self.current_user_name,
            status="success",
            client_id=str(self.current_client_id or ""),
        )
        # Invalida cache do tenant antes de limpar o client_id
        DataLoader.invalidate_cache(self.current_client_id)
        self.is_authenticated = False
        self.username_input = ""
        self.password_input = ""
        self.allowed_modules = []
        self.current_user_name = ""
        self.current_user_role = ""
        self.current_user_role_icon = "user"
        self.current_user_avatar_icon = ""
        self.current_user_avatar_type = "initial"
        self.show_avatar_modal = False
        self.avatar_modal_tab = "avatar"
        self.pw_current = ""
        self.pw_new = ""
        self.pw_confirm = ""
        self.pw_error = ""
        self.pw_success = False
        self.current_user_email = ""
        self.current_user_whatsapp = ""
        self.contact_edit_email = ""
        self.contact_edit_whatsapp = ""
        self.contact_error = ""
        self.contact_success = False
        # Limpa identidade do tenant
        self.current_client_id = ""
        self.current_client_name = ""
        self.client_is_master = False
        # Limpa dados carregados para não vazar entre tenants na mesma sessão
        self.contratos_list = []
        self.projetos_list = []
        self.obras_list = []
        self.financeiro_list = []
        self._contratos_df    = pd.DataFrame()
        self._projetos_df     = pd.DataFrame()
        self._obras_df        = pd.DataFrame()
        self._financeiro_df   = pd.DataFrame()
        self._om_df           = pd.DataFrame()
        self._hub_historico_df = pd.DataFrame()
        # Limpa sessão de chat para não vazar histórico entre usuários
        self.chat_session_id = ""
        self.chat_history = []
        # Clear notifications
        self.notifications_list = []
        self.notif_unread_count = 0
        # Limpa HubState para evitar flicker de dados sensíveis ao fazer login com outro usuário
        # cron_rows, agente_insights, etc. ficam em memória e aparecem brevemente no próximo login
        try:
            from bomtempo.state.hub_state import HubState as _HS
            yield _HS.reset_for_logout
        except Exception:
            pass

    # ── Notifications ─────────────────────────────────────────

    @rx.event(background=True)
    async def load_notifications(self):
        """Load unread @mention notifications for the current user from user_notifications."""
        username = ""
        client_id = ""
        async with self:
            username = str(self.current_user_name)
            client_id = str(self.current_client_id or "")
        if not username:
            return

        from bomtempo.core.supabase_client import sb_select as _sel, sb_update as _upd
        _filters: dict = {"recipient": username}
        if client_id:
            _filters["client_id"] = client_id
        try:
            rows = _sel(
                "user_notifications",
                filters=_filters,
                order="created_at.desc",
                limit=50,
            )
        except Exception as e:
            logger.warning(f"load_notifications error: {e}")
            return

        def _fmt_ts(ts: str) -> str:
            if not ts:
                return ""
            try:
                from datetime import timezone, timedelta
                _brt = timezone(timedelta(hours=-3))
                from datetime import datetime as _dt
                d = _dt.fromisoformat(ts.replace("Z", "+00:00")[:32]).astimezone(_brt)
                return d.strftime("%d/%m %H:%M")
            except Exception:
                return ts[:16]

        notifs = [
            {
                "id": str(r.get("id", "")),
                "message": str(r.get("message", "")),
                "source_type": str(r.get("source_type", "mention")),
                "source_id": str(r.get("source_id", "")),
                "contrato": str(r.get("contrato", "")),
                "read": "1" if str(r.get("read", "false")).lower() in ("true", "1") else "0",
                "created_at_fmt": _fmt_ts(str(r.get("created_at", ""))),
                "sender": str(r.get("sender", "")),
            }
            for r in (rows or [])
        ]
        unread = sum(1 for n in notifs if n["read"] == "0")

        async with self:
            self.notifications_list = notifs
            self.notif_unread_count = unread

    @rx.event(background=True)
    async def mark_all_notifs_read(self):
        """Mark all notifications as read for the current user."""
        username = ""
        client_id = ""
        async with self:
            username = str(self.current_user_name)
            client_id = str(self.current_client_id or "")
        if not username:
            return
        from bomtempo.core.supabase_client import sb_update as _upd
        _upd_filters: dict = {"recipient": username}
        if client_id:
            _upd_filters["client_id"] = client_id
        try:
            _upd("user_notifications", filters=_upd_filters, data={"read": True})
        except Exception as e:
            logger.warning(f"mark_all_notifs_read error: {e}")
        async with self:
            self.notif_unread_count = 0
            self.notifications_list = [
                dict(n, read="1") for n in self.notifications_list
            ]

    def set_current_path(self, path: str):
        self.current_path = path

    def set_username_input(self, value: str):
        self.username_input = value

    def set_password_input(self, value: str):
        self.password_input = value

    # ── Avatar personalization ─────────────────────────────────────────────────

    @rx.var
    def avatar_fallback(self) -> str:
        """First letter of the logged-in username for avatar display."""
        name = self.current_user_name
        return name[0].upper() if name else "?"

    @rx.var
    def effective_avatar_icon(self) -> str:
        """Resolved icon slug to display when avatar_type == 'icon'."""
        return self.current_user_avatar_icon or self.current_user_role_icon or "user"

    def open_avatar_modal(self):
        self.avatar_edit_icon = self.current_user_avatar_icon
        self.avatar_edit_type = self.current_user_avatar_type
        self.avatar_modal_tab = "avatar"
        self.pw_current = ""
        self.pw_new = ""
        self.pw_confirm = ""
        self.pw_error = ""
        self.pw_success = False
        self.contact_edit_email = self.current_user_email
        self.contact_edit_whatsapp = self.current_user_whatsapp
        self.contact_error = ""
        self.contact_success = False
        self.show_avatar_modal = True

    def close_avatar_modal(self):
        self.show_avatar_modal = False

    def set_avatar_modal_tab(self, tab: str):
        self.avatar_modal_tab = tab
        self.pw_error = ""
        self.pw_success = False
        self.contact_error = ""
        self.contact_success = False

    def set_avatar_edit_type(self, val: str):
        self.avatar_edit_type = val

    def set_avatar_edit_icon(self, val: str):
        self.avatar_edit_icon = val

    @rx.event(background=True)
    async def save_avatar_pref(self):
        """Persist avatar preferences to login table — background para não bloquear event loop."""
        from bomtempo.core.supabase_client import sb_update
        async with self:
            avatar_icon = self.avatar_edit_icon
            avatar_type = self.avatar_edit_type
            username = self.current_user_name
        try:
            sb_update(
                "login",
                filters={"username": username},
                data={"avatar_icon": avatar_icon, "avatar_type": avatar_type},
            )
            async with self:
                self.current_user_avatar_icon = avatar_icon
                self.current_user_avatar_type = avatar_type
        except Exception as e:
            logger.error(f"Erro ao salvar preferência de avatar: {e}")
        async with self:
            self.show_avatar_modal = False

    # ── Change password ────────────────────────────────────────────────────────

    def set_pw_current(self, val: str):
        self.pw_current = val

    def set_pw_new(self, val: str):
        self.pw_new = val

    def set_pw_confirm(self, val: str):
        self.pw_confirm = val

    @rx.event(background=True)
    async def save_password(self):
        """Troca senha — background para não bloquear event loop durante queries de DB."""
        import asyncio as _aio_pw
        from bomtempo.core.supabase_client import sb_select, sb_update
        from bomtempo.core.executors import get_db_executor as _get_db
        async with self:
            pw_new = self.pw_new.strip()
            pw_current = self.pw_current.strip()
            pw_confirm = self.pw_confirm.strip()
            username = self.current_user_name
            self.pw_error = ""
            self.pw_success = False

        if not pw_new:
            async with self:
                self.pw_error = "A nova senha não pode estar vazia."
            return
        if len(pw_new) < 3:
            async with self:
                self.pw_error = "A nova senha deve ter ao menos 3 caracteres."
            return
        if pw_new != pw_confirm:
            async with self:
                self.pw_error = "As senhas não coincidem."
            return

        loop = _aio_pw.get_running_loop()
        try:
            rows = await loop.run_in_executor(
                _get_db(), lambda: sb_select("login", filters={"username": username})
            )
            if not rows:
                async with self:
                    self.pw_error = "Usuário não encontrado."
                return
            db_pw = str(rows[0].get("password", ""))
            if pw_current != db_pw:
                async with self:
                    self.pw_error = "Senha atual incorreta."
                return
            await loop.run_in_executor(
                _get_db(),
                lambda: sb_update("login", filters={"username": username}, data={"password": pw_new}),
            )
            async with self:
                self.pw_current = ""
                self.pw_new = ""
                self.pw_confirm = ""
                self.pw_success = True
        except Exception as e:
            logger.error(f"Erro ao alterar senha: {e}")
            async with self:
                self.pw_error = "Erro ao salvar. Tente novamente."

    # ── Contact info ───────────────────────────────────────────────────────────

    def set_contact_edit_email(self, val: str):
        self.contact_edit_email = val

    def set_contact_edit_whatsapp(self, val: str):
        self.contact_edit_whatsapp = val

    @rx.event(background=True)
    async def save_contact(self):
        """Salva email e whatsapp — background para não bloquear event loop."""
        from bomtempo.core.supabase_client import sb_update
        async with self:
            email = self.contact_edit_email.strip()
            whatsapp = self.contact_edit_whatsapp.strip()
            username = self.current_user_name
            self.contact_error = ""
            self.contact_success = False
        try:
            sb_update(
                "login",
                filters={"username": username},
                data={"email": email, "whatsapp": whatsapp},
            )
            async with self:
                self.current_user_email = email
                self.current_user_whatsapp = whatsapp
                self.contact_success = True
        except Exception as e:
            logger.error(f"Erro ao salvar contato: {e}")
            async with self:
                self.contact_error = "Erro ao salvar. Tente novamente."

    @rx.var
    def page_title(self) -> str:
        """Returns the current page title for display."""
        path = self.router.page.path.strip("/")
        if not path or path == "index" or path == "/":
            return "Visão Geral"
        return path.replace("-", " ").title()

    def set_projetos_search(self, value: str):
        self.projetos_search = value

    def set_current_question(self, value: str):
        self.current_question = value

    def set_projetos_fase_filter(self, value: str):
        if self.projetos_fase_filter == value:
            self.projetos_fase_filter = ""
        else:
            self.projetos_fase_filter = value

    def set_om_time_filter(self, value: str):
        self.om_time_filter = value

    def set_obras_selected_contract(self, value: str):
        self.obras_selected_contract = value

    def set_global_project_filter(self, value: str):
        self.global_project_filter = value

    def set_om_project_filter(self, value: str):
        self.om_project_filter = value

    def _recompute_fin_charts(self):
        """Recalcula os gráficos financeiros pesados e armazena em state vars.
        Usa fin_custos (migrado): colunas valor_previsto, valor_executado, categoria_nome.
        Chamado apenas ao carregar dados ou mudar filtro — nunca em cada render.
        """
        data = self.financeiro_list
        if self.fin_project_filter and self.fin_project_filter != "Todos":
            data = [f for f in data if f.get("contrato") == self.fin_project_filter]

        if not data:
            self.financeiro_cockpit_chart = []
            self.financeiro_scurve_chart = []
            return

        df = pd.DataFrame(data)

        # Normalizar colunas de valor (vêm como float do Supabase)
        for col in ["valor_previsto", "valor_executado"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0.0

        # Usar categoria_nome como agrupador (equivale ao antigo "cockpit")
        group_col = "categoria_nome" if "categoria_nome" in df.columns else None
        if group_col is None:
            self.financeiro_cockpit_chart = []
            self.financeiro_scurve_chart = []
            return

        grouped = (
            df.groupby(group_col)
            .agg({"valor_previsto": "sum", "valor_executado": "sum"})
            .reset_index()
        )
        grouped.rename(columns={group_col: "cockpit"}, inplace=True)
        grouped["total_contratado"] = grouped["valor_previsto"].round(2)
        grouped["total_realizado"] = grouped["valor_executado"].round(2)
        grouped["margem"] = grouped["total_contratado"] - grouped["total_realizado"]
        grouped["margem_pct"] = (
            (grouped["margem"] / grouped["total_contratado"].replace(0, float("nan")) * 100)
            .fillna(0).round(1)
        )
        grouped["formatted_total"] = grouped["total_contratado"].apply(
            lambda x: (
                f"R$ {x/1_000_000:.1f}M".replace(".", ",")
                if x >= 1_000_000
                else (f"R$ {x/1_000:.0f}k".replace(".", ",") if x >= 1_000 else f"R$ {x:.0f}")
            )
        )
        self.financeiro_cockpit_chart = grouped.to_dict("records")

        # S-Curve acumulada por DATA (temporal) — padrão para análise de obra
        if "data_custo" in df.columns:
            df2 = df.copy()
            df2["data_custo"] = df2["data_custo"].astype(str).str[:10]
            df2 = df2[df2["data_custo"].str.len() == 10]
            if not df2.empty:
                by_date = (
                    df2.groupby("data_custo")
                    .agg({"valor_previsto": "sum", "valor_executado": "sum"})
                    .sort_index()
                    .reset_index()
                )
                by_date["cumulative_planned"] = by_date["valor_previsto"].cumsum().round(0)
                by_date["cumulative_actual"] = by_date["valor_executado"].cumsum().round(0)
                # Format date label as DD/MM/YY
                def _fmt_date(d: str) -> str:
                    try:
                        parts = d.split("-")
                        return f"{parts[2]}/{parts[1]}/{parts[0][2:]}"
                    except Exception:
                        return d
                by_date["cockpit"] = by_date["data_custo"].apply(_fmt_date)
                self.financeiro_scurve_chart = by_date[["cockpit", "cumulative_planned", "cumulative_actual"]].to_dict("records")
                return
        # Fallback: S-curve por categoria (quando não há datas)
        g2 = grouped.copy().sort_values("total_contratado")
        g2["cumulative_planned"] = g2["total_contratado"].cumsum().round(0)
        g2["cumulative_actual"] = g2["total_realizado"].cumsum().round(0)
        self.financeiro_scurve_chart = g2[["cockpit", "cumulative_planned", "cumulative_actual"]].to_dict("records")

    def set_fin_project_filter(self, value: str):
        self.fin_project_filter = value
        self._recompute_fin_charts()
        self._recompute_popup_rows()

    async def load_data(self):
        """Carrega dados iniciais com guard de autentização"""
        import asyncio as _asyncio

        if not self.is_authenticated:
            logger.warning("🚫 Tentativa de load_data sem autenticação.")
            yield rx.redirect("/")
            return

        self.is_navigating = False  # Encerra feedback de navegação ao chegar na nova página
        # Se já temos dados, não recarrega (Persistência na Sessão)
        if self.contratos_list:
            logger.info("⚡ Dados já em cache. Pulando recarregamento.")
            self.is_loading = False
            return

        self.is_loading = True
        yield

        try:
            loader = DataLoader(client_id=self.current_client_id)
            _loop = _asyncio.get_running_loop()
            raw = await _loop.run_in_executor(get_db_executor(), loader.load_all)
            self.data_version += 1

            def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
                """Single-pass: convert datetime cols to str + fillna by dtype."""
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].astype(str)
                    elif pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].fillna(0)
                    else:
                        df[col] = df[col].fillna("")
                return df

            # Armazena DFs por domínio — Reflex rastreia dependência por var,
            # então alterar _contratos_df não invalida @rx.var que leem _projetos_df.
            self._contratos_df    = _norm_df(raw.get("contratos",      pd.DataFrame()))
            self._projetos_df     = _norm_df(raw.get("projeto",        pd.DataFrame()))
            self._obras_df        = _norm_df(raw.get("obras",          pd.DataFrame()))
            self._financeiro_df   = _norm_df(raw.get("financeiro",     pd.DataFrame()))
            self._om_df           = _norm_df(raw.get("om",             pd.DataFrame()))
            self._hub_historico_df = _norm_df(raw.get("hub_historico", pd.DataFrame()))

            # Serializa listas para o browser
            if not self._contratos_df.empty:
                df = self._contratos_df
                self.contratos_list = df.to_dict("records")
                self.total_contratos = len(df)
                self.valor_tcv = (
                    float(df["valor_contratado"].sum())
                    if "valor_contratado" in df.columns
                    else 0.0
                )
                self.contratos_ativos = (
                    len(df[df["status"] == "Em Execução"]) if "status" in df.columns else 0
                )

            if not self._projetos_df.empty:
                self.projetos_list = self._projetos_df.to_dict("records")

            if not self._obras_df.empty:
                self.obras_list = self._obras_df.to_dict("records")

            if not self._financeiro_df.empty:
                self.financeiro_list = self._financeiro_df.to_dict("records")

            if not self._om_df.empty:
                self.om_list = self._om_df.to_dict("records")

            # Login agora vem do Supabase — users_list não é mais populado a partir de sheets
            # (check_login usa Supabase diretamente como primário + hardcoded fallback)

            # RDO dados agora são lidos do Supabase diretamente (rdo_service.py / rdo_historico.py)

            # Recalcula gráficos e popups financeiros pesados uma única vez após carga
            self._recompute_fin_charts()
            self._recompute_popup_rows()

            # ── #12: Guard de tamanho — aviso se listas excederem threshold ──
            _FIN_WARN = 500
            if len(self.financeiro_list) > _FIN_WARN:
                logger.warning(
                    f"⚠️ financeiro_list tem {len(self.financeiro_list)} linhas → "
                    f"considere paginar no Supabase (limit + filtro por ano/contrato)"
                )

            logger.info("✅ Estado global atualizado com sucesso")

        except Exception as e:
            self.error_message = str(e)
            logger.error(f"❌ Erro no estado global: {e}")

        finally:
            self.is_loading = False

    @rx.event(background=True)
    async def force_refresh_data(self):
        """Recarrega TODOS os dados do Supabase, ignorando cache e guard.

        Chamado após commit no Editor de Dados para manter todas as páginas
        sincronizadas com as alterações mais recentes do banco.
        """
        import asyncio as _asyncio

        async with self:
            _client_id = self.current_client_id
            DataLoader.invalidate_cache(_client_id)
            logger.info("🗑️ Cache invalidado via force_refresh_data")
            self.contratos_list = []
            self.projetos_list = []
            self.obras_list = []
            self.financeiro_list = []
            self.om_list = []
            self._contratos_df    = pd.DataFrame()
            self._projetos_df     = pd.DataFrame()
            self._obras_df        = pd.DataFrame()
            self._financeiro_df   = pd.DataFrame()
            self._om_df           = pd.DataFrame()
            self._hub_historico_df = pd.DataFrame()

        logger.info("🔄 force_refresh_data: recarregando dados do Supabase...")
        try:
            loop = _asyncio.get_running_loop()
            loader = DataLoader(_client_id)
            raw = await loop.run_in_executor(get_db_executor(), loader.load_all)

            def _norm_df(df: pd.DataFrame) -> pd.DataFrame:
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].astype(str)
                    elif pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].fillna(0)
                    else:
                        df[col] = df[col].fillna("")
                return df

            c_df  = _norm_df(raw.get("contratos",      pd.DataFrame()))
            p_df  = _norm_df(raw.get("projeto",        pd.DataFrame()))
            o_df  = _norm_df(raw.get("obras",          pd.DataFrame()))
            f_df  = _norm_df(raw.get("financeiro",     pd.DataFrame()))
            om_df = _norm_df(raw.get("om",             pd.DataFrame()))
            hh_df = _norm_df(raw.get("hub_historico",  pd.DataFrame()))

            total_contratos = len(c_df) if not c_df.empty else 0
            valor_tcv = float(c_df["valor_contratado"].sum()) if not c_df.empty and "valor_contratado" in c_df.columns else 0.0
            contratos_ativos = len(c_df[c_df["status"] == "Em Execução"]) if not c_df.empty and "status" in c_df.columns else 0

            async with self:
                self._contratos_df    = c_df
                self._projetos_df     = p_df
                self._obras_df        = o_df
                self._financeiro_df   = f_df
                self._om_df           = om_df
                self._hub_historico_df = hh_df
                self.contratos_list   = c_df.to_dict("records")  if not c_df.empty  else []
                self.projetos_list    = p_df.to_dict("records")  if not p_df.empty  else []
                self.obras_list       = o_df.to_dict("records")  if not o_df.empty  else []
                self.financeiro_list  = f_df.to_dict("records")  if not f_df.empty  else []
                self.om_list          = om_df.to_dict("records") if not om_df.empty else []
                self.total_contratos  = total_contratos
                self.valor_tcv        = valor_tcv
                self.contratos_ativos = contratos_ativos
                self.data_version    += 1
                self.is_loading       = False
            logger.info("✅ force_refresh_data: estado global re-sincronizado")
        except Exception as e:
            async with self:
                self.is_loading = False
            logger.error(f"❌ force_refresh_data falhou: {e}")

    def set_navigating(self):
        """Seta is_navigating=True para exibir top-bar imediatamente ao clicar na sidebar.
        A navegação SPA em si é feita pelo rx.link(href=...) — não usamos redirect aqui
        para evitar full page reload e o null-state error no frontend."""
        self.is_navigating = True

    def prefetch_route(self, route: str):
        """Aquece conexão HTTP ao passar o mouse sobre item do sidebar (#14).
        Dispara em daemon thread para não bloquear — o pool httpx já mantém
        o socket aberto, reduzindo latência do primeiro request ao navegar.
        """
        import threading as _t

        def _warm():
            try:
                from bomtempo.core.supabase_client import sb_select
                if route in ("/alertas",):
                    sb_select("alert_subscriptions", limit=1)
                elif route in ("/logs-auditoria",):
                    sb_select("system_logs", limit=1)
                elif route in ("/rdo-dashboard",):
                    sb_select("rdo_master", limit=1)
                elif route in ("/reembolso-dash",):
                    sb_select("fuel_reimbursements", limit=1)
            except Exception:
                pass

        _t.Thread(target=_warm, daemon=True).start()

    def check_mobile_access(self):
        """Redireciona se não tiver permissão mobile"""
        if self.current_user_role != "Gestão-Mobile":
            return rx.redirect("/")

    def select_contrato(self, contrato: str):
        self.selected_contrato = contrato

    def deselect_contrato(self):
        self.selected_contrato = ""

    # ── Authentication ──────────────────────────────────────────

    @rx.event(background=True)
    async def check_login(self):
        """Verifica credenciais no Supabase.

        background=True: todo I/O Supabase acontece FORA de async with self:
        — a lock Redis é segurada por milissegundos (apenas para leitura/escrita
        de variáveis em memória), não durante queries de rede de 1–2s.
        Isso elimina os warnings 'Lock was held too long' em check_login.
        """
        # ── Read inputs outside lock ───────────────────────────────────────
        username = ""
        password = ""
        async with self:
            username = self.username_input.strip().lower()
            password = self.password_input.strip()

        logger.info(f"Tentativa de login: User='{username}'")

        if not username or not password:
            async with self:
                self.login_error = "Preencha usuário e senha"
            return

        # ── Show spinner ───────────────────────────────────────────────────
        async with self:
            self.is_authenticating = True
            self.login_error = ""

        # ── All Supabase I/O happens here — OUTSIDE any state lock ─────────
        try:
            import os

            if not os.getenv("SUPABASE_SERVICE_KEY"):
                logger.error("CRITICAL: SUPABASE_SERVICE_KEY não encontrada.")
                async with self:
                    self.is_authenticating = False
                    self.show_loading_screen = False
                    self.login_error = "Erro de Configuração: Chave de API não encontrada no servidor."
                    self.is_authenticated = False
                return

            from bomtempo.core.supabase_client import async_sb_select

            user_rows = await async_sb_select("login", filters={"username": username}, limit=1)
            logger.info(f"Supabase login: query filtrada p/ '{username}' → {len(user_rows)} linha(s)")

            def _get_password_field(row: dict) -> str:
                for key in ("pw_hash", "password", "senha", "pass", "pwd"):
                    val = row.get(key)
                    if val is not None:
                        return str(val).strip()
                return ""

            def _get_role_field(row: dict) -> str:
                for key in ("user_role", "role", "permissao", "perfil"):
                    val = row.get(key)
                    if val is not None:
                        return str(val).strip()
                return "Visitante"

            matched = user_rows[0] if user_rows else None

            if matched is None:
                logger.warning(f"Usuário '{username}' não encontrado no Supabase.")
                audit_log(
                    category=AuditCategory.LOGIN,
                    action=f"Tentativa de login falhou — usuário '{username}' não encontrado",
                    username=username,
                    status="error",
                )
                async with self:
                    self.is_authenticating = False
                    self.show_loading_screen = False
                    self.login_error = "Usuário ou senha inválidos"
                    self.is_authenticated = False
                return

            if not verify_password(_get_password_field(matched), password):
                logger.warning(f"Senha incorreta para '{username}'")
                audit_log(
                    category=AuditCategory.LOGIN,
                    action=f"Tentativa de login falhou — senha incorreta para '{username}'",
                    username=username,
                    status="error",
                )
                async with self:
                    self.is_authenticating = False
                    self.show_loading_screen = False
                    self.login_error = "Usuário ou senha inválidos"
                    self.is_authenticated = False
                return

            # ── Login OK — fetch all remaining data BEFORE writing state ─────
            role = _get_role_field(matched)
            _user_name_val = str(
                matched.get("username") or matched.get("user") or matched.get("login") or username
            )
            _contrato = str(matched.get("project") or matched.get("contrato") or "")
            _client_id = str(matched.get("client_id") or "")

            # Fetch client info
            _client_is_master = False
            _client_name = ""
            if _client_id:
                client_info = await async_sb_select("clients", filters={"id": _client_id}, limit=1)
                if client_info:
                    _client_name = str(client_info[0].get("name", ""))
                    _client_is_master = bool(client_info[0].get("is_master", False))

            # Fetch module permissions + role icon
            _allowed_modules: list = []
            _role_icon = "user"
            try:
                from bomtempo.state.usuarios_state import MODULE_SLUGS
                role_rows = await async_sb_select("roles", filters={"name": role, "client_id": _client_id})
                if role_rows:
                    _allowed_modules = list(role_rows[0].get("modules", []))
                    _role_icon = str(role_rows[0].get("icon", "user") or "user")
                    logger.info(f"Permissões carregadas: {len(_allowed_modules)} módulos")
                else:
                    if _client_is_master or role == "Administrador":
                        _allowed_modules = list(MODULE_SLUGS)
                        _role_icon = "crown" if _client_is_master else "user"
                        logger.info(f"Role '{role}' não encontrado — acesso total (master/admin)")
                    else:
                        _allowed_modules = []
                        _role_icon = "user"
                        logger.warning(f"Role '{role}' não encontrado — sem permissões")
            except Exception as role_err:
                logger.error(f"Erro ao carregar permissões do role '{role}': {role_err}")
                from bomtempo.state.usuarios_state import MODULE_SLUGS
                _allowed_modules = list(MODULE_SLUGS) if role == "Administrador" else []
                _role_icon = "user"

            # Fetch feature flags
            _active_features: list = []
            if _contrato and _contrato not in ("nan", "None", ""):
                try:
                    from bomtempo.core.feature_flags import FeatureFlagsService
                    _active_features = FeatureFlagsService.get_features_for_contract(_contrato)
                    logger.info(f"Feature flags carregadas: {_active_features}")
                except Exception as ff_err:
                    logger.warning(f"Erro ao carregar feature flags: {ff_err}")

            # ── Commit all state in ONE async with self: block ────────────────
            # All I/O done — lock held for <1ms now instead of 1–2s.
            async with self:
                self.is_authenticating = False
                self.show_loading_screen = True
                self.is_authenticated = True
                self.current_user_name = _user_name_val
                self.current_user_role = role
                self.current_user_contrato = _contrato
                self.current_client_id = _client_id
                self.current_client_name = _client_name
                self.client_is_master = _client_is_master
                self.allowed_modules = _allowed_modules
                self.current_user_role_icon = _role_icon
                self.active_features = _active_features
                self.current_user_avatar_icon = str(matched.get("avatar_icon", "") or "")
                self.current_user_avatar_type = str(matched.get("avatar_type", "initial") or "initial")
                self.current_user_email = str(matched.get("email", "") or "")
                self.current_user_whatsapp = str(matched.get("whatsapp", "") or "")
                self.login_error = ""
                self.username_input = ""
                self.password_input = ""

            logger.info(f"✅ Login OK via Supabase. Role: {role}")

            audit_log(
                category=AuditCategory.LOGIN,
                action=f"Login bem-sucedido — role: {role}",
                username=_user_name_val,
                metadata={"role": role},
                status="success",
                client_id=_client_id,
            )

            # Master redirect
            if _client_is_master:
                async with self:
                    self.initial_loading = False
                    self.show_loading_screen = False
                yield GlobalState.load_notifications
                yield rx.redirect("/admin/master-gestion")
                return

            yield GlobalState.load_initial_data_smooth
            yield GlobalState.load_notifications

            if role == "Gestão-Mobile":
                yield rx.redirect("/mobile-chat")
            elif role == "Mestre de Obras":
                yield rx.redirect("/rdo-historico")
            elif role == "solicitacao_reembolso":
                yield rx.redirect("/reembolso")
            elif role == "engenheiro":
                yield rx.redirect("/projetos")
            else:
                if ("rdo_form" in _allowed_modules or "rdo_historico" in _allowed_modules) and "visao_geral" not in _allowed_modules:
                    yield rx.redirect("/rdo-historico")
                elif "reembolso" in _allowed_modules and "visao_geral" not in _allowed_modules:
                    yield rx.redirect("/reembolso")
                else:
                    yield rx.redirect("/")

        except Exception as e:
            logger.error(f"❌ Erro ao conectar com Supabase: {e}")
            audit_error(
                action=f"Erro crítico ao autenticar usuário '{username}'",
                username=username,
                error=e,
            )
            async with self:
                self.is_authenticating = False
                self.show_loading_screen = False
                self.login_error = "Erro ao conectar com o servidor. Tente novamente."
                self.is_authenticated = False

    async def guard_index_page(self):
        """on_load da página /: redireciona roles sem permissão ou usuários não autenticados."""
        if not self.is_authenticated:
            # Se não estiver logado, não carrega dados e deixa na página de login (index renderiza condicionalmente)
            # Na verdade bomtempo.py usa index_page() wrapped em default_layout()
            # Precisamos garantir que o layout mostre o login se is_authenticated for False.
            return

        if self.client_is_master:
            yield rx.redirect("/admin/master-gestion")
            return

        if self.current_user_role == "Mestre de Obras":
            yield rx.redirect("/rdo-historico")
            return
        if self.current_user_role == "solicitacao_reembolso":
            yield rx.redirect("/reembolso")
            return
        yield GlobalState.load_data

    @rx.event(background=True)
    async def load_initial_data_smooth(self):
        """Loading screen pós-login com duração mínima garantida pela animação CSS.

        background=True: o asyncio.sleep(5s) agora fica FORA de qualquer lock Redis.
        Antes (handler regular), o lock era segurado por 5s inteiros causando
        'Lock was held too long time_taken=5.1s' para TODOS os eventos do usuário.
        Agora a lock é liberada em <1ms (apenas para leitura/escrita de vars).

        Fluxo:
        - Marca loading = True (async with self: rápido)
        - Despacha load_data como evento separado (roda concorrentemente)
        - Dorme 5s FORA da lock — outros eventos do usuário processam normalmente
        - Marca loading = False
        """
        import asyncio
        import time

        ANIMATION_DURATION = 4.5  # deve coincidir com loaderProgress em style.css
        BUFFER = 0.5               # tempo extra após animação completar
        MIN_DISPLAY = ANIMATION_DURATION + BUFFER  # 5.0s mínimo total

        async with self:
            self.initial_loading = True
            self.show_loading_screen = True

        start = time.monotonic()

        # Despacha load_data como evento separado — roda concorrentemente à animação.
        # Quando on_load disparar na página destino, os dados já estarão no cache.
        has_data = False
        async with self:
            has_data = bool(self.contratos_list)

        if not has_data:
            yield GlobalState.load_data

        # Aquece connection pool para módulos pesados em background durante a animação
        _role = ""
        async with self:
            _role = self.current_user_role

        import threading as _threading

        def _warm_module_connections():
            """Pré-aquece HTTP keep-alive para tabelas dos módulos secundários."""
            try:
                from bomtempo.core.supabase_client import sb_select
                sb_select("alert_subscriptions", limit=1)
                if _role in ("Administrador", "admin", "Gestão-Mobile"):
                    sb_select("system_logs", limit=1)
                    sb_select("rdo_master", limit=1)
            except Exception as _warm_err:
                logger.warning(f"⚠️ Module connection warmup failed (non-fatal): {_warm_err}")

        _threading.Thread(target=_warm_module_connections, daemon=True).start()

        data_elapsed = time.monotonic() - start

        # ── asyncio.sleep FORA de qualquer async with self: ───────────────────
        # Antes: sleep dentro de handler regular → lock segurada 5s → todos os
        # eventos do usuário bloqueados. Agora: lock liberada, sleep não impacta ninguém.
        remaining = max(MIN_DISPLAY - data_elapsed, BUFFER)
        await asyncio.sleep(remaining)

        async with self:
            self.initial_loading = False
            self.show_loading_screen = False

    # ── Filter Options ───────────────────────────────────────────

    @rx.var
    def project_filter_options(self) -> List[str]:
        """List of all project names for filter dropdowns"""
        if not self.contratos_list:
            return ["Todos"]
        # Fast list comprehension is fine here
        projects = sorted(
            set(c.get("contrato", "") for c in self.contratos_list if c.get("contrato"))
        )
        return ["Todos"] + projects

    @rx.var
    def om_time_filters(self) -> List[str]:
        return ["Mês", "Trimestre", "Ano"]

    @rx.var
    def contract_ids_list(self) -> List[str]:
        """Pure contract IDs for user→project assignment."""
        return [str(c.get("contrato", "")) for c in self.contratos_list if c.get("contrato")]

    @rx.var
    def contract_options_list(self) -> List[str]:
        """Contract IDs prefixed with 'Nenhum' sentinel for user dialog select."""
        return ["Nenhum"] + [str(c.get("contrato", "")) for c in self.contratos_list if c.get("contrato")]

    @rx.var
    def obras_contract_options(self) -> List[str]:
        """List of contract identifiers for obras dropdown"""
        if not self.contratos_list:
            return []
        # Build "Contrato - Cliente" strings
        options = []
        for c in self.contratos_list:
            label = c.get("contrato", "")
            cliente = c.get("cliente", "")
            if cliente:
                label = f"{label} - {cliente}"
            options.append(label)
        return options

    # ── Projetos ─────────────────────────────────────────────────

    @rx.var
    def fases_disponiveis(self) -> List[str]:
        """Returns unique fase_macro values directly from DB column, sorted by numeric prefix."""
        if not self.projetos_list:
            return []
        # Build ordered unique list preserving the numeric sort from 'fase' field
        seen: set = set()
        # Collect (numeric_prefix, macro_name) pairs
        pairs: list = []
        for p in self.projetos_list:
            macro = str(p.get("fase_macro", "")).strip()
            if not macro or macro in seen:
                continue
            seen.add(macro)
            try:
                prefix_num = int(float(str(p.get("fase", "99"))))
            except Exception:
                prefix_num = 99
            pairs.append((prefix_num, macro))
        pairs.sort(key=lambda x: x[0])
        return [m for _, m in pairs]

    @rx.var
    def filtered_contratos(self) -> List[Dict[str, Any]]:
        # Calcula progresso direto de projetos_list (var Reflex reativa).
        # Isso garante que ao atualizar projetos_list o Progress Pulse recalcula imediatamente.
        result = self.contratos_list
        if self.projetos_search:
            term = self.projetos_search.lower()
            result = [
                c
                for c in result
                if term in c.get("contrato", "").lower() or term in c.get("cliente", "").lower()
            ]
        if self.projetos_fase_filter:
            contratos_with_fase = {
                p.get("contrato", "")
                for p in self.projetos_list
                if p.get("fase_macro") == self.projetos_fase_filter
            }
            result = [c for c in result if c.get("contrato") in contratos_with_fase]

        # Calculate progress and dates from activities
        if not self.projetos_list:
            return [dict(c, progress=0, data_inicio="—", prazo_contratual="—") for c in result]

        # Build progress_map from projetos_list (reactive var — always fresh)
        progress_map: dict = {}
        dates_map: dict = {}

        # Group by contract for weighted progress calculation
        from collections import defaultdict
        _by_contract: dict = defaultdict(list)
        for p in self.projetos_list:
            cod = str(p.get("contrato", "") or "")
            if cod:
                _by_contract[cod].append(p)

        for cod, rows in _by_contract.items():
            # Filter to micro level first, fall back to macro
            micros = [r for r in rows if str(r.get("nivel", "")) == "micro"]
            macros = [r for r in rows if str(r.get("nivel", "")) == "macro"]
            working = micros if micros else (macros if macros else rows)

            total_peso = 0.0
            weighted_sum = 0.0
            for r in working:
                pct = float(r.get("conclusao_pct", 0) or 0)
                peso = float(r.get("peso_pct", 1) or 1) or 1.0
                total_peso += peso
                weighted_sum += pct * peso
            progress_map[cod] = (weighted_sum / total_peso) if total_peso > 0 else 0.0

            # Dates from all rows
            starts = [r.get("inicio_previsto") for r in rows if r.get("inicio_previsto")]
            ends = [r.get("termino_previsto") for r in rows if r.get("termino_previsto")]
            if starts and ends:
                try:
                    s = min(str(x) for x in starts)
                    e = max(str(x) for x in ends)
                    def _iso_to_br(v: str) -> str:
                        v = str(v or "")[:10]
                        if len(v) == 10 and v[4] == "-":
                            p = v.split("-")
                            return f"{p[2]}/{p[1]}/{p[0]}"
                        return v
                    dates_map[cod] = {"start": _iso_to_br(s), "end": _iso_to_br(e)}
                except Exception:
                    pass

            # Dates
        enriched_result = []
        for c in result:
            contract_code = c.get("contrato")
            p = progress_map.get(contract_code, 0)
            dates = dates_map.get(contract_code, {"start": "—", "end": "—"})

            # Create copy and update
            c_new = c.copy()
            c_new["progress"] = round(p, 1)
            c_new["data_inicio"] = dates["start"]
            c_new["prazo_contratual"] = dates["end"]
            enriched_result.append(c_new)

        return enriched_result

    @rx.var
    def selected_contrato_data(self) -> Dict[str, Any]:
        if not self.selected_contrato:
            return {}

        target = next(
            (c for c in self.contratos_list if c.get("contrato") == self.selected_contrato), None
        )
        if not target:
            return {}

        contract = target.copy()

        # Initialize date fields with default values
        if "projeto_inicio" not in contract:
            contract["projeto_inicio"] = "—"
        if "termino_estimado" not in contract:
            contract["termino_estimado"] = "—"

        # Optimization: Use stored DataFrame
        df = self._projetos_df
        if df is not None and not df.empty and "contrato" in df.columns:
            # Filter for this contract using optimized pandas indexing
            mask = df["contrato"] == self.selected_contrato
            if mask.any():
                df_c = df.loc[mask]
                # Dates - use correct column names from normalization
                if "inicio_previsto" in df_c.columns:
                    s = df_c["inicio_previsto"].min()
                    if pd.notnull(s) and hasattr(s, "strftime"):
                        contract["projeto_inicio"] = s.strftime("%d/%m/%Y")
                    elif pd.notnull(s) and str(s) != "NaT":
                        contract["projeto_inicio"] = str(s)[:10]  # Get date part only

                if "termino_previsto" in df_c.columns:
                    e = df_c["termino_previsto"].max()
                    if pd.notnull(e) and hasattr(e, "strftime"):
                        contract["termino_estimado"] = e.strftime("%d/%m/%Y")
                    elif pd.notnull(e) and str(e) != "NaT":
                        contract["termino_estimado"] = str(e)[:10]  # Get date part only

        return contract

    @rx.var
    def filtered_projetos(self) -> List[Dict[str, Any]]:
        """Activities filtered by selected contract and optionally by phase

        Deduplicates activities with same name, keeping the one with highest completion.
        """
        if not self.selected_contrato or not self.projetos_list:
            return []

        # Filter by contract
        result = [p for p in self.projetos_list if p.get("contrato") == self.selected_contrato]

        # Filter by phase if set (prefix match: "1 — Projeto Básico" → fase starts with "1.")
        if self.projetos_fase_filter:
            result = [p for p in result if p.get("fase_macro") == self.projetos_fase_filter]

        # Deduplicate: Keep activity with highest completion %
        deduplicated = {}
        for activity in result:
            activity_name = activity.get("atividade", "")
            if not activity_name:
                continue

            # Get current completion percentage
            current_pct = float(activity.get("conclusao_pct", 0) or 0)

            # If activity not seen yet, or this one has higher completion
            if activity_name not in deduplicated:
                deduplicated[activity_name] = activity
            else:
                existing_pct = float(deduplicated[activity_name].get("conclusao_pct", 0) or 0)
                if current_pct > existing_pct:
                    deduplicated[activity_name] = activity

        return list(deduplicated.values())

    @rx.var
    def total_atividades(self) -> int:
        return len(self.projetos_list)

    @rx.var
    def atividades_concluidas(self) -> int:
        return len([p for p in self.projetos_list if p.get("conclusao_pct", 0) >= 100])

    @rx.var
    def atividades_criticas_count(self) -> int:
        return len([p for p in self.projetos_list if p.get("critico") == "Sim"])

    @rx.var
    def atividades_criticas_atrasadas(self) -> int:
        return len(
            [
                p
                for p in self.projetos_list
                if p.get("critico") == "Sim" and p.get("conclusao_pct", 0) < 100
            ]
        )

    @rx.var
    def project_fase_macros(self) -> List[str]:
        """Unique fase_macro values for the selected contract, sorted."""
        if not self.selected_contrato or not self.projetos_list:
            return []
        seen = []
        for p in self.projetos_list:
            if p.get("contrato") == self.selected_contrato:
                fase = str(p.get("fase_macro") or "").strip()
                if fase and fase not in seen:
                    seen.append(fase)
        return seen

    @rx.var
    def gantt_rows(self) -> List[Dict[str, str]]:
        """
        Real Gantt data for filtered activities.
        Each row: {label, color, start_iso, end_iso, pct, critico, responsavel}
        """
        import datetime as _dt

        COLOR_MAP = {
            "civil": "#C98B2A",
            "eletrica": "#3B82F6",
            "elétrica": "#3B82F6",
            "hidraulica": "#2A9D8F",
            "hidráulica": "#2A9D8F",
            "estrutural": "#E89845",
            "mecanica": "#A855F7",
            "mecânica": "#A855F7",
        }

        rows = []
        activities = self.filtered_projetos
        for act in activities[:20]:  # Cap at 20 rows for readability
            label = str(act.get("atividade") or act.get("fase") or "Atividade")[:30]
            fase = str(act.get("fase") or "").lower().strip()
            critico = str(act.get("critico") or "").strip()
            color = "#EF4444" if critico == "Sim" else COLOR_MAP.get(fase, "#889999")
            pct = str(int(float(act.get("conclusao_pct") or 0)))
            responsavel = str(act.get("responsavel") or "—")

            # Parse dates — stored as pandas Timestamp or ISO string
            start_raw = act.get("inicio_previsto") or act.get("inicio") or ""
            end_raw = act.get("termino_previsto") or act.get("termino") or ""

            def _iso(v: object) -> str:
                if not v or str(v) in ("NaT", "nan", "None", ""):
                    return ""
                s = str(v)
                # pandas Timestamp repr: '2025-01-15 00:00:00'
                return s[:10]

            rows.append({
                "label": label,
                "color": color,
                "start_iso": _iso(start_raw),
                "end_iso": _iso(end_raw),
                "pct": pct,
                "critico": "1" if critico == "Sim" else "0",
                "responsavel": responsavel,
                "fase": str(act.get("fase") or "—"),
            })
        return rows

    @rx.var
    def atividades_por_fase_chart(self) -> List[Dict[str, Any]]:
        df = self._projetos_df
        if df is None or df.empty or "fase" not in df.columns:
            return []

        dist = df["fase"].value_counts().reset_index()
        dist.columns = ["name", "value"]
        dist["value"] = dist["value"].astype(int)
        return dist.to_dict("records")

    @rx.var
    def projetos_em_andamento(self) -> List[Dict[str, Any]]:
        """Projects in progress for overview cards"""
        df = self._projetos_df
        if (
            df is None
            or df.empty
            or "conclusao_pct" not in df.columns
            or "contrato" not in df.columns
        ):
            return []

        # Build aggregation dict only with existing columns
        agg_dict = {"conclusao_pct": "mean"}
        if "fase" in df.columns:
            agg_dict["fase"] = "first"
        if "projeto" in df.columns:
            agg_dict["projeto"] = "first"

        grouped = df.groupby("contrato").agg(agg_dict).reset_index()
        grouped = grouped[grouped["conclusao_pct"] < 100].sort_values(
            "conclusao_pct", ascending=False
        )
        grouped["conclusao_pct"] = grouped["conclusao_pct"].round(1)
        return grouped.to_dict("records")

    # ── Formatação Global ────────────────────────────────────────

    @rx.var
    def valor_carteira_formatado(self) -> str:
        v = self.valor_tcv
        if v >= 1_000_000:
            return f"R$ {v/1_000_000:,.1f}M".replace(",", "X").replace(".", ",").replace("X", ".")
        if v >= 1_000:
            return f"R$ {v/1_000:,.1f}k".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @rx.var
    def total_projetos_andamento(self) -> int:
        return len([p for p in self.projetos_list if p.get("conclusao_pct", 0) < 100])

    # ── Contratos / Overview ─────────────────────────────────────

    @rx.var
    def faturamento_por_cliente(self) -> List[Dict[str, Any]]:
        df = self._contratos_df
        if (
            df is None
            or df.empty
            or "cliente" not in df.columns
            or "valor_contratado" not in df.columns
        ):
            return []

        # Apply global project filter
        if self.global_project_filter and self.global_project_filter != "Todos":
            if "contrato" in df.columns:
                df = df[df["contrato"] == self.global_project_filter]

        grouped = df.groupby("cliente")["valor_contratado"].sum().reset_index()
        grouped = grouped.sort_values("valor_contratado", ascending=False).head(10)
        grouped["valor_contratado"] = grouped["valor_contratado"].round(2)
        # Pre-format for charts
        grouped["formatted_valor"] = grouped["valor_contratado"].apply(
            lambda x: (
                f"{x/1_000_000:.1f}M"
                if x >= 1_000_000
                else (f"{x/1_000:.0f}k" if x >= 1_000 else f"{x:.0f}")
            )
        )
        return grouped.to_dict("records")

    @rx.var
    def status_contratos_dist(self) -> List[Dict[str, Any]]:
        df = self._contratos_df
        if df is None or df.empty or "status" not in df.columns:
            return []

        # Apply global project filter
        if self.global_project_filter and self.global_project_filter != "Todos":
            if "contrato" in df.columns:
                df = df[df["contrato"] == self.global_project_filter]

        dist = df["status"].value_counts().reset_index()
        dist.columns = ["name", "value"]
        dist["value"] = dist["value"].astype(int)
        colors = ["#C98B2A", "#2A9D8F", "#E0E0E0", "#E89845", "#3B82F6"]
        dist["fill"] = [colors[i % len(colors)] for i in range(len(dist))]
        return dist.to_dict("records")

    @rx.var
    def contratos_recentes(self) -> List[Dict[str, Any]]:
        return self.contratos_list[-5:] if self.contratos_list else []

    # ── Financeiro ───────────────────────────────────────────────

    @rx.var
    def _financeiro_filtered(self) -> List[Dict[str, Any]]:
        """Helper: financeiro data filtered by project"""
        # Kept as list processing for now, simpler for small lists
        data = self.financeiro_list
        if self.fin_project_filter and self.fin_project_filter != "Todos":
            data = [f for f in data if f.get("contrato") == self.fin_project_filter]
        return data

    @rx.var
    def total_financeiro_contratado(self) -> float:
        data = self._financeiro_filtered
        if not data:
            return 0.0
        # fin_custos: valor_previsto = planejado/contratado
        return sum(float(d.get("valor_previsto", 0) or 0) for d in data)

    @rx.var
    def total_financeiro_realizado(self) -> float:
        data = self._financeiro_filtered
        if not data:
            return 0.0
        # fin_custos: valor_executado = medido/realizado
        return sum(float(d.get("valor_executado", 0) or 0) for d in data)

    @rx.var
    def margem_bruta(self) -> float:
        return self.total_financeiro_contratado - self.total_financeiro_realizado

    @rx.var
    def margem_pct(self) -> float:
        if self.total_financeiro_contratado > 0:
            return round((self.margem_bruta / self.total_financeiro_contratado) * 100, 1)
        return 0.0

    # financeiro_cockpit_chart e financeiro_scurve_chart são agora state vars
    # (declaradas no bloco de vars acima) — calculadas em _recompute_fin_charts()
    # chamado em load_data() e set_fin_project_filter(). Não rodam mais em cada render.

    def _fmt_money(self, value: float) -> str:
        """Format money values in Brazilian format"""
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @rx.var
    def financeiro_contratado_fmt(self) -> str:
        return self._fmt_money(self.total_financeiro_contratado)

    @rx.var
    def financeiro_realizado_fmt(self) -> str:
        return self._fmt_money(self.total_financeiro_realizado)

    @rx.var
    def margem_bruta_fmt(self) -> str:
        return self._fmt_money(self.margem_bruta)

    @rx.var
    def margem_pct_fmt(self) -> str:
        return f"{self.margem_pct:.1f}%"

    @rx.var
    def fin_total_itens(self) -> int:
        return len(self._financeiro_filtered)

    @rx.var
    def fin_itens_concluidos(self) -> int:
        return sum(1 for d in self._financeiro_filtered if d.get("status") == "concluido")

    @rx.var
    def fin_itens_andamento(self) -> int:
        return sum(1 for d in self._financeiro_filtered if d.get("status") == "em_andamento")

    @rx.var
    def fin_itens_previstos(self) -> int:
        return sum(1 for d in self._financeiro_filtered if d.get("status") == "previsto")

    @rx.var
    def fin_pct_concluido_fmt(self) -> str:
        total = self.fin_total_itens
        if total == 0:
            return "0.0%"
        return f"{self.fin_itens_concluidos / total * 100:.1f}%"

    @rx.var
    def fin_contratos_com_custo(self) -> int:
        """Nº de contratos distintos com pelo menos 1 custo registrado."""
        return len({d.get("contrato", "") for d in self._financeiro_filtered if d.get("contrato")})

    @rx.var
    def fin_status_dist(self) -> List[Dict[str, Any]]:
        """Distribuição de itens por status para donut chart."""
        from collections import Counter
        counts = Counter(d.get("status", "previsto") for d in self._financeiro_filtered)
        color_map = {
            "previsto":     "#C98B2A",
            "em_andamento": "#3B82F6",
            "concluido":    "#22c55e",
            "cancelado":    "#EF4444",
        }
        label_map = {
            "previsto":     "Previsto",
            "em_andamento": "Em Andamento",
            "concluido":    "Concluído",
            "cancelado":    "Cancelado",
        }
        return [
            {"name": label_map.get(k, k), "value": v, "fill": color_map.get(k, "#889999")}
            for k, v in counts.items() if v > 0
        ]

    @rx.var
    def fin_top_categoria(self) -> str:
        """Categoria com maior valor previsto."""
        data = self._financeiro_filtered
        if not data:
            return "—"
        cat_totals: dict = {}
        for d in data:
            cat = d.get("categoria_nome", "Outros") or "Outros"
            cat_totals[cat] = cat_totals.get(cat, 0.0) + float(d.get("valor_previsto", 0) or 0)
        if not cat_totals:
            return "—"
        return max(cat_totals, key=lambda k: cat_totals[k])

    # ── Obras ────────────────────────────────────────────────────

    @rx.var
    def avanco_fisico_geral(self) -> float:
        # Utilize 'projeto' or 'obras'? Usually average completion of active projects.
        # Previous code used 'projetos_list' (activities).
        df = self._projetos_df
        if df is None or df.empty:
            return 0.0

        # Filter by selected contract if set
        target = self.obras_selected_contract
        if target:
            code = target.split(" - ")[0].strip() if " - " in target else target
            if "contrato" in df.columns:
                df = df[df["contrato"] == code]

        if df.empty:
            return 0.0

        if "conclusao_pct" in df.columns:
            return round(float(df["conclusao_pct"].mean()), 1)
        return 0.0

    @rx.var
    def avanco_fisico_geral_fmt(self) -> str:
        return f"{self.avanco_fisico_geral:.1f}%"

    @rx.var
    def total_obras_andamento(self) -> int:
        df = self._obras_df
        if df is None or df.empty or "contrato" not in df.columns:
            return 0
        return int(df["contrato"].nunique())

    @rx.var
    def obras_atrasadas_count(self) -> int:
        df = self._obras_df
        if df is None or df.empty:
            return 0

        if "realizado_pct" in df.columns and "previsto_pct" in df.columns:
            # Need to handle potential string/numeric issues if not cleaned
            # But loader cleans it.
            try:
                atrasadas = df[df["realizado_pct"] < (df["previsto_pct"] - 5)]
                return (
                    int(atrasadas["contrato"].nunique()) if "contrato" in atrasadas.columns else 0
                )
            except Exception:
                return 0
        return 0

    @rx.var
    def disciplina_progress_chart(self) -> List[Dict[str, Any]]:
        """Progresso por fase_macro (disciplina) — construído a partir de hub_atividades.
        Usa selected_project (hub) como fonte primária, fallback obras_selected_contract."""
        df = self._projetos_df
        if df is None or df.empty:
            return []

        # Determina contrato: hub tem precedência
        code = self.selected_project
        if not code:
            target = self.obras_selected_contract
            code = target.split(" - ")[0].strip() if " - " in target else target

        if code and "contrato" in df.columns:
            df = df[df["contrato"] == code].copy()

        if df.empty:
            return []

        if "fase_macro" not in df.columns or "conclusao_pct" not in df.columns:
            return []

        df["conclusao_pct"] = pd.to_numeric(df["conclusao_pct"], errors="coerce").fillna(0)
        df["peso_pct"] = pd.to_numeric(df.get("peso_pct", pd.Series([1] * len(df))), errors="coerce").fillna(1)

        # Calcula progresso ponderado por fase_macro
        # previsto: para cada fase, assume que todas as atividades deveriam estar prontas até hoje
        # (simplificação: previsto = média de quanto deveria estar completo pelo calendário)
        from datetime import date as _date
        today = pd.Timestamp(_date.today())

        rows = []
        for macro, grp in df.groupby("fase_macro"):
            if not macro or str(macro).strip() == "":
                continue
            peso_total = grp["peso_pct"].sum()
            if peso_total == 0:
                continue
            # Realizado ponderado
            realizado = round(float((grp["conclusao_pct"] * grp["peso_pct"]).sum() / peso_total), 0)

            # Previsto: progresso esperado pelo calendário até hoje
            previsto = 0.0
            if "inicio_previsto" in grp.columns and "termino_previsto" in grp.columns:
                g = grp.copy()
                g["inicio_previsto"] = pd.to_datetime(g["inicio_previsto"], errors="coerce")
                g["termino_previsto"] = pd.to_datetime(g["termino_previsto"], errors="coerce")
                for _, row in g.iterrows():
                    p = float(row["peso_pct"]) / peso_total * 100
                    ini = row["inicio_previsto"]
                    fim = row["termino_previsto"]
                    if pd.isna(ini) or pd.isna(fim):
                        previsto += realizado * p / 100  # sem data = assume igual ao realizado
                    else:
                        dur = max(1, (fim - ini).days)
                        if today >= fim:
                            previsto += p
                        elif today <= ini:
                            previsto += 0.0
                        else:
                            previsto += (today - ini).days / dur * p
            else:
                previsto = realizado  # sem datas: não há base para desvio

            rows.append({
                "label": str(macro),
                "previsto_pct": int(round(previsto)),
                "realizado_pct": int(realizado),
            })

        rows.sort(key=lambda x: -x["previsto_pct"])
        return rows

    @rx.var
    def status_por_obra_chart(self) -> List[Dict[str, Any]]:
        df = self._obras_df
        if df is None or df.empty:
            return []

        if "data" in df.columns and "projeto" in df.columns:
            latest = df.sort_values("data").groupby("projeto").last().reset_index()

            # Check if required columns exist before sorting
            if "realizado_pct" in latest.columns and "previsto_pct" in latest.columns:
                latest = latest.sort_values("realizado_pct", ascending=True).head(10)
                latest["realizado_pct"] = (
                    pd.to_numeric(latest["realizado_pct"], errors="coerce").fillna(0).round(1)
                )
                latest["previsto_pct"] = (
                    pd.to_numeric(latest["previsto_pct"], errors="coerce").fillna(0).round(1)
                )
                return latest[["projeto", "realizado_pct", "previsto_pct"]].to_dict("records")
        return []

    # ... sidebar/params vars skip ...

    @rx.var
    def evolucao_obras_chart(self) -> List[Dict[str, Any]]:
        df = self._obras_df
        if df is None or df.empty:
            return []

        if "data" not in df.columns or "realizado_pct" not in df.columns:
            return []

        # Create a copy to not mutate stored DF
        df = df.copy()
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df["mes"] = df["data"].dt.to_period("M").astype(str)
        grouped = df.groupby("mes")["realizado_pct"].mean().reset_index()
        grouped["realizado_pct"] = grouped["realizado_pct"].round(1)
        return grouped.to_dict("records")

    # ── Obras Detail ─────────────────────────────────────────────

    @rx.var
    def obra_selected_data(self) -> Dict[str, Any]:
        """Data for the selected contract in Obras page"""
        target = self.obras_selected_contract
        # Extract contract code from "BOM010-24 - Escola A" format
        if target and " - " in target:
            target_code = target.split(" - ")[0].strip()
        elif target:
            target_code = target
        else:
            target_code = ""

        if not target_code and self.contratos_list:
            target_code = self.contratos_list[0].get("contrato", "")

        # Start with contract info
        result: Dict[str, Any] = {}
        for c in self.contratos_list:
            if c.get("contrato") == target_code:
                result = dict(c)
                break

        if not result and self.contratos_list:
            result = dict(self.contratos_list[0])
            target_code = result.get("contrato", "")

        # Merge with obras data for construction-specific fields
        if target_code:
            df = self._obras_df
            if df is not None and not df.empty and "contrato" in df.columns:
                # Optimized filter
                obras_for_contract = df[df["contrato"] == target_code]
                if not obras_for_contract.empty:
                    first_row = obras_for_contract.iloc[0]
                    for key in ["os", "potencia_kwp", "terceirizado", "localizacao", "tipo"]:
                        if key in first_row.index:
                            val = first_row[key]
                            result[key] = str(val) if pd.notna(val) else "—"

                    # Compute prazo from início → término
                    if "data" in obras_for_contract.columns:
                        dates = pd.to_datetime(obras_for_contract["data"], errors="coerce")
                        if not dates.isna().all():
                            days = (dates.max() - dates.min()).days
                            result["prazo_dias"] = f"{days} dias"
                        else:
                            result["prazo_dias"] = "—"
                    else:
                        result["prazo_dias"] = "—"

        return result

    # ── Unified Gestão de Projetos Hub computed vars ───────────────

    @rx.var
    def project_pulse_cards(self) -> List[Dict[str, Any]]:
        """Enriched pulse cards for the unified project list view.
        One card per contract with obras KPIs + sparkline + days to deadline.
        """
        if not self.contratos_list:
            return []

        import math
        from datetime import datetime

        df_obras = self._obras_df
        df_proj = self._projetos_df
        today = datetime.now()

        search = self.project_search.lower()
        status_filter = self.project_status_filter
        tipo_filter = self.hub_filter_tipo
        priority_filter = self.hub_filter_priority

        cards = []
        for c in self.contratos_list:
            code = str(c.get("contrato", ""))
            cliente = str(c.get("cliente", ""))
            status = str(c.get("status", ""))
            tipo = str(c.get("tipo", ""))
            priority = str(c.get("priority", ""))

            # Search filter
            if search and search not in code.lower() and search not in cliente.lower():
                continue
            # Status filter
            if status_filter and status != status_filter:
                continue
            # Tipo filter
            if tipo_filter and tipo != tipo_filter:
                continue
            # Priority filter
            if priority_filter and priority != priority_filter:
                continue

            # ── Obras data ────────────────────────────────────────
            avanco = 0.0
            risco = 0
            equipe = 0
            efetivo = 0
            budget_p = 0.0
            budget_r = 0.0
            localizacao = str(c.get("localizacao", "—"))

            # avanco from hub_atividades micro weighted avg (matches cronograma KPI + Progress Pulse)
            if df_proj is not None and not df_proj.empty and "contrato" in df_proj.columns:
                _sp = df_proj[df_proj["contrato"] == code].copy()
                if not _sp.empty and "conclusao_pct" in _sp.columns:
                    _sp["conclusao_pct"] = pd.to_numeric(_sp["conclusao_pct"], errors="coerce").fillna(0)
                    _sp["peso_pct"] = pd.to_numeric(_sp.get("peso_pct", 1), errors="coerce").fillna(1).replace(0, 1)
                    if "nivel" in _sp.columns:
                        _mi = _sp[_sp["nivel"] == "micro"]
                        if not _mi.empty:
                            _sp = _mi
                        else:
                            _ma = _sp[_sp["nivel"] == "macro"]
                            if not _ma.empty:
                                _sp = _ma
                    _tp = _sp["peso_pct"].sum()
                    avanco = round(float((_sp["conclusao_pct"] * _sp["peso_pct"]).sum() / _tp) if _tp > 0 else float(_sp["conclusao_pct"].mean()), 1)

            if df_obras is not None and not df_obras.empty and "contrato" in df_obras.columns:
                sub = df_obras[df_obras["contrato"] == code]
                if not sub.empty:
                    if "risco_geral_score" in sub.columns:
                        risco = int(sub["risco_geral_score"].max())
                    if "equipe_presente_hoje" in sub.columns:
                        equipe = int(sub["equipe_presente_hoje"].max())
                    if "efetivo_planejado" in sub.columns:
                        efetivo = int(sub["efetivo_planejado"].max())
                    if "budget_planejado" in sub.columns:
                        budget_p = float(sub["budget_planejado"].max())
                    if "budget_realizado" in sub.columns:
                        budget_r = float(sub["budget_realizado"].max())
                    if "localizacao" in sub.columns:
                        lv = sub["localizacao"].dropna()
                        if not lv.empty:
                            localizacao = str(lv.iloc[0])

            # ── Sparkline: last 7 daily avg realizado_pct ────────
            spark = [0.0] * 7
            if df_obras is not None and not df_obras.empty and "contrato" in df_obras.columns:
                sub = df_obras[df_obras["contrato"] == code].copy()
                if not sub.empty and "data" in sub.columns and "realizado_pct" in sub.columns:
                    sub["data"] = pd.to_datetime(sub["data"], errors="coerce")
                    daily = sub.dropna(subset=["data"]).sort_values("data")
                    daily = daily.groupby("data")["realizado_pct"].mean().tail(7).tolist()
                    while len(daily) < 7:
                        daily.insert(0, 0.0)
                    spark = [round(float(v), 1) for v in daily]

            spark_max = max(spark) if any(v > 0 for v in spark) else 1.0

            # ── Progress from projetos DF ─────────────────────────
            progress = avanco
            if df_proj is not None and not df_proj.empty and "contrato" in df_proj.columns:
                ps = df_proj[df_proj["contrato"] == code]
                if not ps.empty and "conclusao_pct" in ps.columns:
                    progress = round(float(ps["conclusao_pct"].mean()), 1)

            # ── Days to deadline ──────────────────────────────────
            days_fmt = "—"
            days_int = 9999  # sentinel: no deadline defined → not overdue
            if df_proj is not None and not df_proj.empty and "contrato" in df_proj.columns:
                ps = df_proj[df_proj["contrato"] == code]
                if not ps.empty and "termino_previsto" in ps.columns:
                    td = pd.to_datetime(ps["termino_previsto"], errors="coerce").max()
                    if pd.notna(td):
                        days_int = (td.to_pydatetime().replace(tzinfo=None) - today).days
                        if days_int < 0:
                            days_fmt = "Vencido"
                        elif days_int == 0:
                            days_fmt = "Hoje"
                        else:
                            days_fmt = f"{days_int}d"

            # ── Risk label ────────────────────────────────────────
            if risco >= 60:
                risco_label = "CRÍTICO"
                risco_color = "#EF4444"
                risco_bg = "rgba(239,68,68,0.12)"
            elif risco >= 30:
                risco_label = "ATENÇÃO"
                risco_color = "#F59E0B"
                risco_bg = "rgba(245,158,11,0.12)"
            else:
                risco_label = "SAUDÁVEL"
                risco_color = "#2A9D8F"
                risco_bg = "rgba(42,157,143,0.12)"

            # ── Status color ──────────────────────────────────────
            if status == "Em Execução":
                status_color = "#2A9D8F"
                status_bg = "rgba(42,157,143,0.12)"
            elif status == "Concluído":
                status_color = "#C98B2A"
                status_bg = "rgba(201,139,42,0.12)"
            else:
                status_color = "#889999"
                status_bg = "rgba(136,153,153,0.1)"

            cards.append({
                "contrato": code,
                "label": f"{code} - {cliente}",
                "cliente": cliente,
                "status": status,
                "status_color": status_color,
                "status_bg": status_bg,
                "localizacao": localizacao,
                "progress": round(progress, 1),
                "progress_fmt": f"{round(progress, 1):.1f}%",
                "risco_geral_score": risco,
                "risco_label": risco_label,
                "risco_color": risco_color,
                "risco_bg": risco_bg,
                "days_to_deadline": days_int,
                "days_fmt": days_fmt,
                "equipe": equipe,
                "efetivo": efetivo,
                "budget_planejado": budget_p,
                "budget_realizado": budget_r,
                # Sparkline: 7 explicit fields to avoid chained subscript
                "spark0": spark[0], "spark1": spark[1], "spark2": spark[2],
                "spark3": spark[3], "spark4": spark[4], "spark5": spark[5],
                "spark6": spark[6],
                "spark_max": spark_max,
            })

        return cards

    @rx.var
    def project_scurve_chart(self) -> List[Dict[str, Any]]:
        """Curva S — previsto vs realizado acumulado.
        Previsto: interpolação linear por data de cada atividade (inicio→término).
        Realizado: reconstruído a partir do hub_atividade_historico — para cada dia,
        usa o conclusao_pct mais recente registrado até aquele dia por atividade."""
        from datetime import date as _date
        code = self.selected_project
        if not code:
            return []
        df = self._projetos_df
        if df is None or df.empty:
            return []
        if "contrato" in df.columns:
            df = df[df["contrato"] == code].copy()
        if df.empty:
            return []
        for col in ["inicio_previsto", "termino_previsto", "conclusao_pct", "peso_pct"]:
            if col not in df.columns:
                return []
        df = df.dropna(subset=["inicio_previsto", "termino_previsto"]).copy()
        if df.empty:
            return []
        df["inicio_previsto"] = pd.to_datetime(df["inicio_previsto"], errors="coerce")
        df["termino_previsto"] = pd.to_datetime(df["termino_previsto"], errors="coerce")
        df = df.dropna(subset=["inicio_previsto", "termino_previsto"])
        df["conclusao_pct"] = pd.to_numeric(df["conclusao_pct"], errors="coerce").fillna(0)
        df["peso_pct"] = pd.to_numeric(df["peso_pct"], errors="coerce").fillna(1)
        if df.empty:
            return []
        peso_total = df["peso_pct"].sum()
        if peso_total == 0:
            return []

        import numpy as _np

        def _bdays(a: pd.Timestamp, b: pd.Timestamp) -> int:
            """Dias úteis (seg-sex) entre a (inclusive) e b (exclusive). Mínimo 1."""
            return max(1, int(_np.busday_count(a.date(), b.date())))


        # ── Reconstruir histórico de conclusao_pct por atividade por data ──────
        # Para cada dia d, conclusao_hist[ativ_id][d] = último conclusao_pct_novo <= d
        hist_df = self._hub_historico_df
        # Mapeia ativ_id → lista de (date, conclusao_pct_novo) ordenada
        hist_map: Dict[str, list] = {}
        if hist_df is not None and not hist_df.empty:
            hf = hist_df.copy()
            if "contrato" in hf.columns:
                hf = hf[hf["contrato"] == code]
            if not hf.empty and "created_at" in hf.columns and "atividade_id" in hf.columns:
                hf["created_at"] = pd.to_datetime(hf["created_at"], errors="coerce", utc=True)
                hf = hf.dropna(subset=["created_at"])
                hf["hist_date"] = hf["created_at"].dt.tz_localize(None).dt.normalize()
                hf["conclusao_pct_novo"] = pd.to_numeric(hf.get("conclusao_pct_novo", 0), errors="coerce").fillna(0)
                for aid, grp in hf.groupby("atividade_id"):
                    sorted_grp = grp.sort_values("hist_date")
                    hist_map[str(aid)] = list(zip(
                        sorted_grp["hist_date"].tolist(),
                        sorted_grp["conclusao_pct_novo"].tolist(),
                    ))

        def _hist_pct(ativ_id: str, as_of: pd.Timestamp) -> float:
            """Retorna o conclusao_pct mais recente para ativ_id até 'as_of'."""
            records = hist_map.get(str(ativ_id), [])
            val = 0.0
            for dt, pct in records:
                if dt <= as_of:
                    val = float(pct)
                else:
                    break
            return val

        today = pd.Timestamp(_date.today())
        start_date = df["inicio_previsto"].min()
        end_date = df["termino_previsto"].max()
        duration_days = max(1, (end_date - start_date).days)
        if duration_days <= 60:
            freq = "D"
            date_fmt = "%d/%m"
        elif duration_days <= 180:
            freq = "W-MON"
            date_fmt = "%d/%m"
        else:
            freq = "MS"
            date_fmt = "%m/%y"
        plot_end = max(end_date, today + pd.Timedelta(days=1))
        dates = pd.date_range(start=start_date, end=plot_end, freq=freq)
        result = []
        for d in dates:
            if freq == "MS":
                d_end = (d + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
            elif freq == "W-MON":
                d_end = d + pd.Timedelta(days=6)
            else:
                d_end = d
            previsto_acc = 0.0
            realizado_acc = 0.0
            for _, row in df.iterrows():
                inicio = row["inicio_previsto"]
                termino = row["termino_previsto"]
                peso = float(row["peso_pct"]) / peso_total * 100
                duracao = _bdays(inicio, termino)
                # Previsto: interpolação linear em dias úteis até d_end
                if d_end < inicio:
                    frac_prev = 0.0
                elif d_end >= termino:
                    frac_prev = 1.0
                else:
                    frac_prev = _bdays(inicio, d_end) / duracao
                previsto_acc += frac_prev * peso
                # Realizado: conclusao_pct histórico para este dia
                if d.date() <= today.date():
                    ativ_id = str(row.get("id", ""))
                    if ativ_id and ativ_id in hist_map:
                        pct_hist = _hist_pct(ativ_id, d_end.normalize() if freq != "D" else d)
                    else:
                        # Sem histórico: usa conclusao_pct atual apenas no último dia
                        pct_hist = float(row["conclusao_pct"]) if d.date() == today.date() else 0.0
                    realizado_acc += pct_hist / 100.0 * peso
            point: Dict[str, Any] = {"data": d.strftime(date_fmt), "previsto": round(previsto_acc, 1)}
            if d.date() <= today.date():
                point["realizado"] = round(realizado_acc, 1)
            result.append(point)
        return result

    @rx.var
    def project_campo_rdos_display(self) -> List[Dict[str, str]]:
        """Pre-formatted RDO rows for foreach in Campo tab."""
        return [
            {
                "id": str(r.get("id", "")),
                "data_rdo": _fmt_date_br(str(r.get("data_rdo", "—"))),
                "responsavel": str(r.get("responsavel_tecnico", r.get("responsavel", "—"))),
                "atividade": str(r.get("atividade_principal", r.get("descricao", "—")))[:60],
                "pdf_url": str(r.get("pdf_url", r.get("pdf_path", ""))),
                "status": str(r.get("status", "enviado")),
            }
            for r in self.project_campo_rdos
        ]

    # ── Obras Enterprise (Revamp) ─────────────────────────────────

    @rx.var
    def obras_cards_list(self) -> List[Dict[str, Any]]:
        """One enriched card per contract for the Obras list view."""
        if not self.contratos_list:
            return []

        df_obras = self._obras_df
        cards = []

        for c in self.contratos_list:
            code = c.get("contrato", "")
            cliente = c.get("cliente", "")
            label = f"{code} - {cliente}" if cliente else code

            card: Dict[str, Any] = {
                "contrato": code,
                "label": label,
                "cliente": cliente or "—",
                "localizacao": c.get("localizacao", "—"),
                "status": c.get("status", "Em Execução"),
                "avanco_pct": 0.0,
                "budget_planejado": 0.0,
                "budget_realizado": 0.0,
                "equipe_presente_hoje": 0,
                "efetivo_planejado": 0,
                "chuva_acumulada_mm": 0.0,
                "risco_geral_score": 0,
            }

            if df_obras is not None and not df_obras.empty and "contrato" in df_obras.columns:
                sub = df_obras[df_obras["contrato"] == code]
                if not sub.empty:
                    if "realizado_pct" in sub.columns:
                        card["avanco_pct"] = round(float(sub["realizado_pct"].mean()), 1)

                    first = sub.iloc[0]
                    for col, default in [
                        ("budget_planejado", 0.0),
                        ("budget_realizado", 0.0),
                        ("equipe_presente_hoje", 0),
                        ("efetivo_planejado", 0),
                        ("chuva_acumulada_mm", 0.0),
                        ("risco_geral_score", 0),
                    ]:
                        if col in first.index:
                            raw = first[col]
                            if pd.notna(raw):
                                try:
                                    card[col] = (
                                        float(raw)
                                        if isinstance(default, float)
                                        else int(float(raw))
                                    )
                                except (ValueError, TypeError):
                                    card[col] = default
                            else:
                                card[col] = default
                        else:
                            card[col] = default

            cards.append(card)

        return cards

    @rx.var
    def obra_enterprise_data(self) -> Dict[str, Any]:
        """Extends obra_selected_data with enterprise columns (budget, equipe, risco)."""
        base = dict(self.obra_selected_data)

        target = self.obras_selected_contract
        if not target:
            return base

        code = target.split(" - ")[0].strip() if " - " in target else target
        df = self._obras_df

        # avanco_pct: use hub_atividades micro-level weighted avg (same as Progress Pulse + cronograma KPI)
        df_proj = self._projetos_df
        if df_proj is not None and not df_proj.empty and "contrato" in df_proj.columns:
            sub_proj = df_proj[df_proj["contrato"] == code].copy()
            if not sub_proj.empty and "conclusao_pct" in sub_proj.columns:
                sub_proj["conclusao_pct"] = pd.to_numeric(sub_proj["conclusao_pct"], errors="coerce").fillna(0)
                sub_proj["peso_pct"] = pd.to_numeric(sub_proj.get("peso_pct", 1), errors="coerce").fillna(1).replace(0, 1)
                if "nivel" in sub_proj.columns:
                    _micro = sub_proj[sub_proj["nivel"] == "micro"]
                    if not _micro.empty:
                        sub_proj = _micro
                    else:
                        _macro = sub_proj[sub_proj["nivel"] == "macro"]
                        if not _macro.empty:
                            sub_proj = _macro
                total_peso = sub_proj["peso_pct"].sum()
                if total_peso > 0:
                    avanco_calc = (sub_proj["conclusao_pct"] * sub_proj["peso_pct"]).sum() / total_peso
                else:
                    avanco_calc = sub_proj["conclusao_pct"].mean()
                base["avanco_pct"] = round(float(avanco_calc), 1)

        if df is not None and not df.empty and "contrato" in df.columns:
            sub = df[df["contrato"] == code]
            if not sub.empty:
                pass  # avanco_pct now comes from hub_atividades above

                first = sub.iloc[0]
                for col, default in [
                    ("budget_planejado", 0.0),
                    ("budget_realizado", 0.0),
                    ("equipe_presente_hoje", 0),
                    ("efetivo_planejado", 0),
                    ("chuva_acumulada_mm", 0.0),
                    ("risco_geral_score", 0),
                ]:
                    if col in first.index:
                        raw = first[col]
                        if pd.notna(raw):
                            try:
                                base[col] = (
                                    float(raw)
                                    if isinstance(default, float)
                                    else int(float(raw))
                                )
                            except (ValueError, TypeError):
                                base[col] = default
                        else:
                            base[col] = default
                    else:
                        base[col] = default

        return base

    @rx.var
    def obra_budget_chart(self) -> List[Dict[str, Any]]:
        """Orçamento previsto vs executado por categoria de custo."""
        code = self.selected_project
        if not code:
            return []
        fin_df = self._financeiro_df
        if fin_df is None or fin_df.empty:
            return []
        if "contrato" in fin_df.columns:
            fin_df = fin_df[fin_df["contrato"] == code].copy()
        if fin_df.empty:
            return []
        fin_df["valor_previsto"] = pd.to_numeric(fin_df.get("valor_previsto", 0), errors="coerce").fillna(0)
        fin_df["valor_executado"] = pd.to_numeric(fin_df.get("valor_executado", 0), errors="coerce").fillna(0)
        col = "categoria_nome" if "categoria_nome" in fin_df.columns else None
        if col:
            grp = fin_df.groupby(col).agg(
                planejado=("valor_previsto", "sum"),
                realizado=("valor_executado", "sum"),
            ).reset_index().rename(columns={col: "categoria"})
        else:
            data = self.obra_enterprise_data
            bp = float(data.get("budget_planejado", 0) or 0)
            br = float(data.get("budget_realizado", 0) or 0)
            if bp == 0 and br == 0:
                return []
            return [{"categoria": "Total", "planejado": bp, "realizado": br}]
        grp = grp[grp["planejado"] + grp["realizado"] > 0]
        return grp.to_dict("records")

    @rx.var(cache=False)
    def dash_today_str(self) -> str:
        """Today's date in dd/mm format for Curva S reference line."""
        from datetime import date as _dt_date
        return _dt_date.today().strftime("%d/%m")

    @rx.var
    def dash_scurve_chart(self) -> List[Dict[str, Any]]:
        """S-Curve para Dashboard — igual ao project_scurve_chart mas filtrável por período."""
        base = list(self.project_scurve_chart)
        if not base:
            return []
        period = self.dash_filter_period
        if period == "7d":
            return base[-7:] if len(base) >= 7 else base
        if period == "30d":
            return base[-30:] if len(base) >= 30 else base
        if period == "90d":
            return base[-90:] if len(base) >= 90 else base
        return base

    @rx.var
    def dash_producao_diaria_chart(self) -> List[Dict[str, Any]]:
        """Produtividade diária — avanço ponderado por peso_pct por dia.
        realizado = Σ(delta_pct_i * peso_i / peso_total)  → % do projeto avançado no dia
        meta      = incremento diário previsto da S-curve (previsto[d] - previsto[d-1])"""
        code = self.selected_project
        if not code:
            return []
        hist_df = self._hub_historico_df
        if hist_df is None or hist_df.empty:
            return []
        if "contrato" in hist_df.columns:
            hist_df = hist_df[hist_df["contrato"] == code].copy()
        if hist_df.empty:
            return []
        if "created_at" not in hist_df.columns and "data" not in hist_df.columns:
            return []

        # Busca pesos das atividades
        ativ_df = self._projetos_df
        peso_map: Dict[str, float] = {}
        peso_total = 1.0
        if ativ_df is not None and not ativ_df.empty and "contrato" in ativ_df.columns:
            sub = ativ_df[ativ_df["contrato"] == code]
            if not sub.empty and "peso_pct" in sub.columns and "id" in sub.columns:
                sub = sub.copy()
                sub["peso_pct"] = pd.to_numeric(sub["peso_pct"], errors="coerce").fillna(1)
                pt = float(sub["peso_pct"].sum())
                if pt > 0:
                    peso_total = pt
                for _, r in sub.iterrows():
                    peso_map[str(r["id"])] = float(r["peso_pct"])

        # Prefer `data` (RDO reference date) over `created_at` (submission timestamp).
        # Retroactive RDOs filed late would otherwise create false spikes on the submission day.
        if "data" in hist_df.columns and hist_df["data"].notna().any():
            hist_df = hist_df.copy()
            hist_df["data"] = pd.to_datetime(hist_df["data"], errors="coerce").dt.strftime("%d/%m")
            hist_df = hist_df.dropna(subset=["data"])
        else:
            hist_df["created_at"] = pd.to_datetime(hist_df["created_at"], errors="coerce", utc=True)
            hist_df = hist_df.dropna(subset=["created_at"])
            hist_df["data"] = hist_df["created_at"].dt.tz_convert("America/Sao_Paulo").dt.strftime("%d/%m")
        hist_df["conclusao_pct_novo"] = pd.to_numeric(hist_df.get("conclusao_pct_novo", 0), errors="coerce").fillna(0)
        hist_df["conclusao_pct_anterior"] = pd.to_numeric(hist_df.get("conclusao_pct_anterior", 0), errors="coerce").fillna(0)
        hist_df["delta_raw"] = hist_df["conclusao_pct_novo"] - hist_df["conclusao_pct_anterior"]
        # Aplica peso: contribuição ao progresso total do projeto
        hist_df["atividade_id"] = hist_df["atividade_id"].astype(str)
        hist_df["peso"] = hist_df["atividade_id"].map(lambda aid: peso_map.get(aid, 1.0))
        hist_df["delta_ponderado"] = hist_df["delta_raw"] * hist_df["peso"] / peso_total

        grp = hist_df.groupby("data")["delta_ponderado"].sum().reset_index()
        grp = grp.rename(columns={"delta_ponderado": "realizado"})
        grp["realizado"] = grp["realizado"].clip(lower=0).round(2)

        # Meta diária: derivada da S-curve (incremento previsto por dia)
        scurve = list(self.project_scurve_chart)
        meta_map: Dict[str, float] = {}
        for i, pt in enumerate(scurve):
            prev_val = float(scurve[i - 1].get("previsto", 0)) if i > 0 else 0.0
            meta_map[pt["data"]] = round(max(0.0, float(pt.get("previsto", 0)) - prev_val), 2)

        grp["meta"] = grp["data"].map(lambda d: meta_map.get(d, 0.0))

        period = self.dash_filter_period
        if period == "7d":
            grp = grp.tail(7)
        elif period == "30d":
            grp = grp.tail(30)
        elif period == "90d":
            grp = grp.tail(90)
        return grp.to_dict("records")

    @rx.var
    def dash_spi_trend_chart(self) -> List[Dict[str, Any]]:
        """Tendência de SPI (Schedule Performance Index) ao longo do tempo.
        SPI = realizado / previsto — 1.0 = no prazo, <1.0 = atrasado, >1.0 = adiantado."""
        base = list(self.project_scurve_chart)
        if not base:
            return []
        result = []
        for pt in base:
            r = float(pt.get("realizado", 0) or 0)
            p = float(pt.get("previsto", 0) or 0)
            spi = round(r / p, 2) if p > 0.5 else None
            if spi is not None:
                result.append({"data": pt.get("data", ""), "spi": spi, "baseline": 1.0})
        period = self.dash_filter_period
        if period == "7d":
            return result[-7:] if len(result) >= 7 else result
        if period == "30d":
            return result[-30:] if len(result) >= 30 else result
        if period == "90d":
            return result[-90:] if len(result) >= 90 else result
        return result

    @rx.var
    def dash_disciplinas_chart(self) -> List[Dict[str, Any]]:
        """Progresso por disciplina — filtrável por macro se selecionada."""
        data = list(self.disciplina_progress_chart)
        macro_filter = self.dash_filter_macro
        if not macro_filter:
            return data
        return [d for d in data if macro_filter.lower() in str(d.get("label", d.get("categoria", ""))).lower()]

    @rx.var
    def dash_macro_options(self) -> List[str]:
        """Lista de fase_macro únicas para filtro do dashboard."""
        disc = self.disciplina_progress_chart
        seen: list = []
        for d in disc:
            v = str(d.get("label", d.get("categoria", "")))
            if v and v not in seen:
                seen.append(v)
        return seen

    @rx.var
    def obra_kpi_fmt(self) -> Dict[str, Any]:
        """Pre-formatted KPI display strings for the obras detail view.
        All rounding and formatting done server-side to avoid float display issues.
        """
        data = self.obra_enterprise_data
        bp = float(data.get("budget_planejado", 0) or 0)
        br = float(data.get("budget_realizado", 0) or 0)
        equipe = int(data.get("equipe_presente_hoje", 0) or 0)
        efetivo = int(data.get("efetivo_planejado", 0) or 0)
        risco = int(data.get("risco_geral_score", 0) or 0)
        avanco = float(data.get("avanco_pct", 0) or 0)

        # Disciplinas em risco
        disc_data = self.disciplina_progress_chart
        disc_total = len(disc_data)
        disc_em_risco = sum(
            1
            for d in disc_data
            if float(d.get("realizado_pct", 0)) < float(d.get("previsto_pct", 0))
        )
        disc_val = f"{disc_em_risco} / {disc_total}" if disc_total > 0 else "— / —"
        if disc_total == 0:
            disc_sub = "Sem dados de disciplina"
            disc_icon_color = "#2A9D8F"
        elif disc_em_risco == 0:
            disc_sub = "✓ Todas em dia"
            disc_icon_color = "#2A9D8F"
        elif disc_em_risco <= 2:
            disc_sub = f"⚠ {disc_em_risco} com atraso"
            disc_icon_color = "#F59E0B"
        else:
            disc_sub = f"✕ {disc_em_risco} em atraso"
            disc_icon_color = "#EF4444"

        # Budget
        bp_fmt = f"R$ {bp / 1_000_000:.1f}M" if bp > 0 else "—"
        br_fmt = f"R$ {br / 1_000_000:.1f}M" if br > 0 else "—"
        budget_over = False
        var_fmt = "Orçamento não configurado"
        budget_bar_pct = 0
        budget_exec_rate_fmt = "—"
        budget_bar_label = "—"
        budget_color = "#2A9D8F"
        if bp > 0:
            exec_rate = br / bp * 100
            budget_over = exec_rate > 100
            budget_color = "#EF4444" if budget_over else "#2A9D8F"
            if budget_over:
                var_fmt = f"▲ {exec_rate:.1f}% do orçamento executado"
            else:
                var_fmt = f"▼ {exec_rate:.1f}% do orçamento executado"
            budget_bar_pct = min(int(exec_rate), 100)
            budget_exec_rate_fmt = f"{exec_rate:.1f}%"
            budget_bar_label = f"{exec_rate:.1f}% do orçamento executado"

        # Equipe
        equipe_val = f"{equipe} / {efetivo}"
        if efetivo > 0:
            equipe_pct = equipe / efetivo * 100
            equipe_sub = (
                f"⚠ {equipe_pct:.0f}% do efetivo"
                if equipe_pct < 70
                else f"✓ {equipe_pct:.0f}% do efetivo"
            )
        else:
            equipe_sub = "Planejado não definido"

        # Risco
        if risco >= 60:
            risco_label = "CRÍTICO"
            risco_color = "#EF4444"
            risco_bg = "rgba(239, 68, 68, 0.1)"
        elif risco >= 30:
            risco_label = "MODERADO"
            risco_color = "#F59E0B"
            risco_bg = "rgba(245, 158, 11, 0.12)"
        else:
            risco_label = "CONTROLADO"
            risco_color = "#2A9D8F"
            risco_bg = "rgba(42, 157, 143, 0.15)"

        return {
            "budget_planejado_fmt": bp_fmt,
            "budget_realizado_fmt": br_fmt,
            "budget_variacao_fmt": var_fmt,
            "budget_over": budget_over,
            "budget_bar_pct": budget_bar_pct,
            "budget_exec_rate_fmt": budget_exec_rate_fmt,
            "budget_bar_label": budget_bar_label,
            "budget_color": budget_color,
            "equipe_val": equipe_val,
            "equipe_sub": equipe_sub,
            "risco_val": str(risco),
            "risco_label": risco_label,
            "risco_color": risco_color,
            "risco_bg": risco_bg,
            "avanco_fmt": f"{avanco:.1f}%",
            "avanco_pct": round(avanco, 1),   # numeric — used by S-Curve reference_line
            "disc_val": disc_val,
            "disc_sub": disc_sub,
            "disc_icon_color": disc_icon_color,
        }

    @rx.var
    def risk_score_data(self) -> Dict[str, Any]:
        """
        Calcula Nota de Risco 0-10 para o projeto selecionado com 7 fatores ponderados.
        Retorna nota final, label, cor, e lista de fatores para popup breakdown.

        Fatores e pesos:
          - Atraso cronograma  30%  (SPI, tarefas vencidas, desvio PP)
          - Criticidade        20%  (atividades críticas atrasadas)
          - Clima              10%  (chuva acumulada, janelas perdidas)
          - Produtividade      15%  (realizado vs planejado)
          - Restrições         10%  (equipe abaixo do planejado)
          - Custo/desvio       10%  (budget exec rate)
          - Qualidade           5%  (placeholder — auditoria futura)
        """
        from datetime import date as _date

        # ── Fonte de dados ────────────────────────────────────────────────────
        data = self.obra_enterprise_data
        kpi = self.obra_kpi_fmt
        bp = float(data.get("budget_planejado", 0) or 0)
        br = float(data.get("budget_realizado", 0) or 0)
        avanco = float(data.get("avanco_pct", 0) or 0)
        equipe = int(data.get("equipe_presente_hoje", 0) or 0)
        efetivo = int(data.get("efetivo_planejado", 0) or 0)
        chuva = float(data.get("chuva_acumulada_mm", 0) or 0)

        # Dados de cronograma via hub_state (acessíveis via _data)
        # Usamos disciplina_progress_chart e project_scurve_chart como proxy
        disc_data = self.disciplina_progress_chart
        disc_total = len(disc_data)
        disc_atrasadas = sum(
            1 for d in disc_data
            if float(d.get("realizado_pct", 0)) < float(d.get("previsto_pct", 0)) - 5
        )

        # Curva S — último ponto COM realizado para desvio real vs previsto
        scurve = self.project_scurve_chart
        desvio_pp = 0.0
        if scurve:
            # Usa o último ponto que contém "realizado" (ignora pontos futuros)
            realized_points = [pt for pt in scurve if "realizado" in pt]
            last = realized_points[-1] if realized_points else scurve[-1]
            r_last = float(last.get("realizado", 0) or 0)
            p_last = float(last.get("previsto", 0) or 0)
            if p_last > 0:
                desvio_pp = r_last - p_last  # positivo = adiantado, negativo = atrasado

        # ── FATOR 1 — Atraso de cronograma (peso 30%) ─────────────────────────
        # Score 0-10: 0 = adiantado, 10 = muito atrasado
        if desvio_pp >= 5:
            f1_score = 0.0
        elif desvio_pp >= 0:
            f1_score = 1.0
        elif desvio_pp >= -5:
            f1_score = 3.0
        elif desvio_pp >= -15:
            f1_score = 6.0
        elif desvio_pp >= -25:
            f1_score = 8.0
        else:
            f1_score = 10.0

        disc_atrasadas_pct = (disc_atrasadas / disc_total * 100) if disc_total > 0 else 0
        f1_score = min(10.0, f1_score + disc_atrasadas_pct * 0.06)

        f1_desc = f"Desvio: {desvio_pp:+.1f}% | {disc_atrasadas}/{disc_total} disciplinas atrasadas"

        # ── FATOR 2 — Criticidade (peso 20%) ──────────────────────────────────
        disc_criticas = sum(
            1 for d in disc_data
            if float(d.get("realizado_pct", 0)) < float(d.get("previsto_pct", 0)) - 15
        )
        f2_score = min(10.0, disc_criticas * 2.5)
        f2_desc = f"{disc_criticas} disciplinas com atraso crítico (>15pp)"

        # ── FATOR 3 — Clima (peso 10%) ─────────────────────────────────────────
        if chuva > 100:
            f3_score = 8.0
        elif chuva > 50:
            f3_score = 5.0
        elif chuva > 20:
            f3_score = 2.0
        else:
            f3_score = 0.0
        f3_desc = f"Chuva acumulada: {chuva:.0f}mm"

        # ── FATOR 4 — Produtividade (peso 15%) ────────────────────────────────
        # Proxy: equipe presente vs planejado — só avalia se há RDO (equipe > 0)
        has_rdo_data_risco = any(float(pt.get("realizado", 0) or 0) > 0 for pt in scurve) if scurve else False
        if efetivo > 0 and equipe > 0 and has_rdo_data_risco:
            prod_ratio = equipe / efetivo
            if prod_ratio >= 0.9:
                f4_score = 1.0
            elif prod_ratio >= 0.7:
                f4_score = 4.0
            elif prod_ratio >= 0.5:
                f4_score = 7.0
            else:
                f4_score = 9.0
            f4_desc = f"Efetivo: {equipe}/{efetivo} pessoas ({prod_ratio*100:.0f}% do planejado)"
        elif efetivo > 0 and not has_rdo_data_risco:
            f4_score = 1.0  # sem RDOs ainda — não penalizar
            f4_desc = "Aguardando primeiro RDO"
        else:
            f4_score = 2.0
            f4_desc = "Efetivo planejado não configurado"

        # ── FATOR 5 — Restrições operacionais (peso 10%) ─────────────────────
        # Proxy: % atividades em risco no forecast (via disc_atrasadas como sinal)
        f5_score = min(10.0, disc_atrasadas_pct * 0.1)
        f5_desc = f"Disciplinas em risco: {disc_atrasadas_pct:.0f}%"

        # ── FATOR 6 — Custo/desvio (peso 10%) ────────────────────────────────
        if bp > 0:
            exec_rate = br / bp * 100
            if exec_rate > 110:
                f6_score = 9.0
            elif exec_rate > 100:
                f6_score = 6.0
            elif exec_rate > 90:
                f6_score = 2.0
            else:
                f6_score = 1.0
            f6_desc = f"Orçamento executado: {exec_rate:.1f}%"
        else:
            f6_score = 2.0
            f6_desc = "Orçamento não configurado"

        # ── FATOR 7 — Qualidade/retrabalho (peso 5%) ─────────────────────────
        # Placeholder — futuro: não conformidades de auditoria
        f7_score = 2.0
        f7_desc = "Qualidade — baseado em auditoria de campo"

        # ── Score final ponderado ─────────────────────────────────────────────
        PESOS = [0.30, 0.20, 0.10, 0.15, 0.10, 0.10, 0.05]
        SCORES = [f1_score, f2_score, f3_score, f4_score, f5_score, f6_score, f7_score]
        nota = round(sum(p * s for p, s in zip(PESOS, SCORES)), 1)

        # ── Label e cor ───────────────────────────────────────────────────────
        if nota <= 3:
            label = "BAIXO"
            color = "#22c55e"
            bg = "rgba(34,197,94,0.12)"
        elif nota <= 6:
            label = "ATENÇÃO"
            color = "#F59E0B"
            bg = "rgba(245,158,11,0.12)"
        elif nota <= 8:
            label = "ALTO"
            color = "#EF4444"
            bg = "rgba(239,68,68,0.12)"
        else:
            label = "CRÍTICO"
            color = "#dc2626"
            bg = "rgba(220,38,38,0.18)"

        FATORES = [
            {"nome": "Atraso de Cronograma", "peso": "30%", "score": f1_score, "desc": f1_desc, "icon": "calendar-x"},
            {"nome": "Criticidade de Atividades", "peso": "20%", "score": f2_score, "desc": f2_desc, "icon": "alert-triangle"},
            {"nome": "Clima", "peso": "10%", "score": f3_score, "desc": f3_desc, "icon": "cloud-rain"},
            {"nome": "Produtividade", "peso": "15%", "score": f4_score, "desc": f4_desc, "icon": "users"},
            {"nome": "Restrições Operacionais", "peso": "10%", "score": f5_score, "desc": f5_desc, "icon": "wrench"},
            {"nome": "Custo / Desvio", "peso": "10%", "score": f6_score, "desc": f6_desc, "icon": "dollar-sign"},
            {"nome": "Qualidade / Campo", "peso": "5%", "score": f7_score, "desc": f7_desc, "icon": "camera"},
        ]

        fatores_serialized = [
            {
                "nome": str(f["nome"]),
                "peso": str(f["peso"]),
                "score": str(round(float(f["score"]), 1)),
                "desc": str(f["desc"]),
                "icon": str(f["icon"]),
            }
            for f in sorted(FATORES, key=lambda x: -x["score"])
        ]

        return {
            "nota": str(nota),
            "label": label,
            "color": color,
            "bg": bg,
            "fatores": fatores_serialized,
            "desvio_pp": f"{desvio_pp:+.1f}",
        }

    @rx.var
    def risk_score_fatores(self) -> List[Dict[str, str]]:
        """Retorna apenas a lista de fatores do risk_score_data, tipada para rx.foreach."""
        return self.risk_score_data.get("fatores", [])  # type: ignore[return-value]

    @rx.var
    def risk_desvio_is_negative(self) -> bool:
        """True se o desvio de prazo do risk score é negativo (atraso)."""
        v = self.risk_score_data.get("desvio_pp", "+0.0")
        try:
            return float(str(v)) < 0
        except Exception:
            return False

    @rx.var
    def ia_alertas_list(self) -> List[Dict[str, str]]:
        """
        Gera alertas IA baseados em triggers reais de dados do projeto.
        Triggers:
          - Desvio físico negativo > 10pp (macro atraso)
          - Disciplina com atraso > 20pp (caminho crítico)
          - Equipe < 60% do planejado
          - Budget > 105% (estouro de custo)
          - Chuva acumulada > 50mm (impacto climático)
        Retorna lista de dicts {severity, icon, title, desc, modulo}
        """
        alertas = []
        data = self.obra_enterprise_data
        disc_data = self.disciplina_progress_chart
        scurve = self.project_scurve_chart

        bp = float(data.get("budget_planejado", 0) or 0)
        br = float(data.get("budget_realizado", 0) or 0)
        equipe = int(data.get("equipe_presente_hoje", 0) or 0)
        efetivo = int(data.get("efetivo_planejado", 0) or 0)
        chuva = float(data.get("chuva_acumulada_mm", 0) or 0)

        # Gate: só acionar alertas temporais se o projeto já tem RDOs submetidos
        # "tem RDO" = há pelo menos 1 ponto de scurve com realizado > 0
        has_rdo_data = any(float(pt.get("realizado", 0) or 0) > 0 for pt in scurve) if scurve else False

        # Desvio físico global — usa último ponto COM realizado
        # Só aciona se já há RDOs reais (evita falso alarme no dia 0)
        if scurve and has_rdo_data:
            realized_pts = [pt for pt in scurve if float(pt.get("realizado", 0) or 0) > 0]
            last = realized_pts[-1] if realized_pts else None
            if last:
                r_last = float(last.get("realizado", 0) or 0)
                p_last = float(last.get("previsto", 0) or 0)
                if p_last > 0:
                    desvio = r_last - p_last
                    if desvio <= -20:
                        alertas.append({
                            "severity": "critical",
                            "icon": "calendar-x",
                            "title": "Atraso crítico no cronograma",
                            "desc": f"Físico realizado {abs(desvio):.1f}% abaixo do previsto. Risco de perda de prazo contratual.",
                            "modulo": "cronograma",
                        })
                    elif desvio <= -10:
                        alertas.append({
                            "severity": "high",
                            "icon": "clock",
                            "title": "Desvio de prazo relevante",
                            "desc": f"Cronograma {abs(desvio):.1f}% abaixo do planejado. Monitorar tendência.",
                            "modulo": "cronograma",
                        })

        # Disciplinas críticas — só com RDO real
        if has_rdo_data:
            for d in disc_data:
                r_val = float(d.get("realizado_pct", 0))
                p_val = float(d.get("previsto_pct", 0))
                nome = str(d.get("label", d.get("categoria", "—")))
                if p_val > 0 and (p_val - r_val) > 25:
                    alertas.append({
                        "severity": "critical",
                        "icon": "alert-triangle",
                        "title": f"Disciplina crítica: {nome}",
                        "desc": f"{nome} com {p_val-r_val:.0f}pp de atraso. Impacto em caminho crítico.",
                        "modulo": "cronograma",
                    })
                    break  # só 1 disciplina crítica no card

        # Equipe abaixo do planejado — só aciona se já há RDO do dia (equipe > 0 indica RDO enviado)
        # Se equipe == 0 antes do primeiro RDO, é óbvio e não deve alertar
        if efetivo > 0 and equipe > 0 and equipe < efetivo * 0.6:
            alertas.append({
                "severity": "high",
                "icon": "users",
                "title": "Equipe abaixo do planejado",
                "desc": f"Apenas {equipe}/{efetivo} pessoas em campo ({equipe/efetivo*100:.0f}%). Meta de produção em risco.",
                "modulo": "dashboard",
            })

        # Estouro de custo
        if bp > 0 and br > bp * 1.05:
            exec_rate = br / bp * 100
            alertas.append({
                "severity": "high",
                "icon": "dollar-sign",
                "title": "Orçamento acima do planejado",
                "desc": f"Execução financeira em {exec_rate:.1f}% do orçamento. Revisar EAC.",
                "modulo": "financeiro",
            })

        # Chuva acumulada
        if chuva > 80:
            alertas.append({
                "severity": "medium",
                "icon": "cloud-rain",
                "title": "Chuva acumulada elevada",
                "desc": f"{chuva:.0f}mm acumulados. Verificar impacto em frentes expostas.",
                "modulo": "visao_geral",
            })

        return [
            {
                "severity": str(a["severity"]),
                "icon": str(a["icon"]),
                "title": str(a["title"]),
                "desc": str(a["desc"]),
                "modulo": str(a["modulo"]),
            }
            for a in alertas[:5]
        ]

    @rx.var
    def disciplina_gauges_list(self) -> List[Dict[str, Any]]:
        """Pre-computed semi-circle gauge data for each discipline.
        SVG stroke-dasharray values calculated server-side.
        r=38, C=2*pi*38≈238.76, SEMI=C/2≈119.38
        stroke-dashoffset=-119.38 positions arc start at 9-o'clock (left).
        """
        data = self.disciplina_progress_chart
        r_svg = 38  # SVG circle radius
        cx, cy = 50, 50  # SVG circle center
        C = 2 * math.pi * r_svg  # ≈ 238.76
        SEMI = C / 2  # ≈ 119.38
        gauges = []
        for item in data:
            r_val = float(item.get("realizado_pct", 0))
            p_val = float(item.get("previsto_pct", 0))
            filled_r = round((r_val / 100) * SEMI, 2)

            if r_val >= p_val:
                color = "#2A9D8F"
                status = "on_track"
            elif r_val >= p_val - 15:
                color = "#F59E0B"
                status = "warning"
            else:
                color = "#EF4444"
                status = "delayed"

            # Previsto marker dot: position on the arc
            # Arc goes from 180° to 360° (left → top → right)
            angle = math.pi + (p_val / 100) * math.pi
            mx = round(cx + r_svg * math.cos(angle), 2)
            my = round(cy + r_svg * math.sin(angle), 2)

            gauges.append(
                {
                    "categoria": item.get("categoria", ""),
                    "realizado_pct": r_val,
                    "previsto_pct": p_val,
                    "realizado_pct_fmt": f"{r_val:.0f}%",
                    "previsto_pct_fmt": f"{p_val:.0f}%",
                    "pr_label": f"P:{p_val:.0f}% · R:{r_val:.0f}%",
                    "realizado_dash": f"{filled_r} {round(C, 2)}",
                    "status": status,
                    "color": color,
                    "marker_cx": str(mx),
                    "marker_cy": str(my),
                }
            )
        return gauges

    # ── O&M ──────────────────────────────────────────────────────

    @rx.var
    def _om_filtered(self) -> List[Dict[str, Any]]:
        """O&M data filtered by project and time period with lifetime cumulative calculation"""
        from datetime import datetime, timedelta

        import pandas as pd

        # 1. Start with full O&M list
        data = self.om_list
        if not data:
            return []

        df = pd.DataFrame(data)
        if df.empty:
            return []

        # Ensure data column is datetime for sorting
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"], errors="coerce")

        # 2. Filter by project FIRST to calculate project-specific running total
        if self.om_project_filter and self.om_project_filter != "Todos":
            df = df[df["contrato"] == self.om_project_filter]

        if df.empty:
            return []

        # 3. Calculate Cumulative Lifetime Production for this project
        # Sort chronologically to ensure cumsum is correct regardless of source order
        df = df.sort_values("data")

        # Recalculate accumulated since source CSV might be missing it or have partial data
        # 'energia_injetada_kwh' is our base value
        if "energia_injetada_kwh" in df.columns:
            df["acumulado_kwh"] = pd.to_numeric(df["energia_injetada_kwh"], errors="coerce").fillna(0).cumsum()

        # 4. Apply time filtering AFTER cumulative calculation
        # This allows us to see 'Total Accumulated' for a month even if previous months are hidden
        if self.om_time_filter:
            now = datetime.now()
            if self.om_time_filter == "Mês":
                cutoff = now - timedelta(days=30)
                df = df[df["data"] >= cutoff]
            elif self.om_time_filter == "Trimestre":
                cutoff = now - timedelta(days=90)
                df = df[df["data"] >= cutoff]
            elif self.om_time_filter == "Ano":
                cutoff = now - timedelta(days=365)
                df = df[df["data"] >= cutoff]

        return df.to_dict("records")

    @rx.var
    def om_energia_injetada_fmt(self) -> str:
        data = self._om_filtered
        if not data:
            return "0 kWh"
        total = sum(float(d.get("energia_injetada_kwh", 0) or 0) for d in data)
        return f"{total:,.0f} kWh".replace(",", ".")

    @rx.var
    def om_acumulado_fmt(self) -> str:
        data = self._om_filtered
        if not data:
            return "0 kWh"
        # Cumulative running total is the maximum reached in the filtered window
        total = max(float(d.get("acumulado_kwh", 0) or 0) for d in data)
        return f"{total:,.0f} kWh".replace(",", ".")

    @rx.var
    def om_performance_fmt(self) -> str:
        data = self._om_filtered
        if not data:
            return "0%"
        prev = sum(float(d.get("geracao_prevista_kwh", 0) or 0) for d in data)
        inj = sum(float(d.get("energia_injetada_kwh", 0) or 0) for d in data)
        if prev > 0:
            return f"{(inj / prev * 100):.1f}%"
        return "0%"

    @rx.var
    def om_fat_liquido_fmt(self) -> str:
        data = self._om_filtered
        if not data:
            return "R$ 0,00"
        val = sum(float(d.get("faturamento_liquido", 0) or 0) for d in data)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @rx.var
    def om_geracao_chart(self) -> List[Dict[str, Any]]:
        data = self._om_filtered
        if not data:
            return []
        df = pd.DataFrame(data)
        if "mes_ano" not in df.columns:
            return []

        # Ensure chronological order
        if "data" in df.columns:
            df = df.sort_values("data")

        agg_dict = {}
        for col, func in [
            ("geracao_prevista_kwh", "sum"),
            ("energia_injetada_kwh", "sum"),
            ("acumulado_kwh", "max"),
        ]:
            if col in df.columns:
                agg_dict[col] = func
        if not agg_dict:
            return []

        grouped = (
            df.groupby("mes_ano", sort=False)
            .agg(agg_dict)
            .reset_index()
        )

        for col in ["geracao_prevista_kwh", "energia_injetada_kwh", "acumulado_kwh"]:
            if col in grouped.columns:
                grouped[col] = pd.to_numeric(grouped[col], errors="coerce").fillna(0).round(0)
        return grouped.to_dict("records")

    @rx.var
    def om_table_data(self) -> List[Dict[str, Any]]:
        """O&M table data grouped by month"""
        data = self._om_filtered
        if not data:
            return []
        df = pd.DataFrame(data)
        if "mes_ano" not in df.columns:
            return []

        # Ensure chronological order
        if "data" in df.columns:
            df = df.sort_values("data")

        agg_cols = {}
        for col in [
            "energia_injetada_kwh",
            "compensado_kwh",
            "acumulado_kwh",
            "valor_faturado",
            "gestao",
            "faturamento_liquido",
        ]:
            if col in df.columns:
                # Cumulative values get 'max' (end of month value), others get 'sum'
                agg_cols[col] = "sum" if col != "acumulado_kwh" else "max"

        grouped = df.groupby("mes_ano", sort=False).agg(agg_cols).reset_index()
        for col in grouped.select_dtypes(include=["float64", "float32"]).columns:
            grouped[col] = grouped[col].round(2)
        return grouped.to_dict("records")

    # ── Analytics ────────────────────────────────────────────────

    @rx.var
    def analytics_atraso_medio(self) -> float:
        if not self.obras_list:
            return 0.0
        diffs = []
        for o in self.obras_list:
            r = float(o.get("realizado_pct", 0) or 0)
            p = float(o.get("previsto_pct", 0) or 0)
            d = r - p
            if d < 0:
                diffs.append(d)
        if diffs:
            return round(sum(diffs) / len(diffs), 1)
        return 0.0

    @rx.var
    def analytics_churn_risk(self) -> int:
        if not self.contratos_list:
            return 0
        return len([c for c in self.contratos_list if c.get("status") in ["Em Risco", "Atrasado"]])

    @rx.var
    def analytics_conclusao_rate(self) -> float:
        if not self.projetos_list:
            return 0.0
        concluidos = len([p for p in self.projetos_list if p.get("conclusao_pct", 0) >= 100])
        return (
            round((concluidos / len(self.projetos_list) * 100), 1)
            if len(self.projetos_list) > 0
            else 0.0
        )

    @rx.var
    def forecast_revenue_chart(self) -> List[Dict[str, Any]]:
        months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun"]
        data = []
        base = 100000.0
        for i, m in enumerate(months):
            data.append(
                {
                    "name": m,
                    "real": round(base * (1 + i * 0.1), 2),
                    "previsto": round(base * (1 + i * 0.12), 2),
                }
            )
        return data

    # ── Chat ─────────────────────────────────────────────────────
    # Chat implementation moved to async send_message() at line 68

    # ── Weather ──────────────────────────────────────────────────

    weather_data: Optional[Dict[str, Any]] = None
    weather_loading: bool = False
    weather_risk_level: str = "Unknown"
    weather_location_name: str = "Recife, PE"
    weather_lat: float = -8.0543
    weather_lon: float = -34.8813
    windy_layer: str = "rain"  # active Windy overlay: rain | satellite | wind | temp

    # ── Unified Project Hub handlers ─────────────────────────────────────────────

    def set_project_search(self, value: str):
        self.project_search = value

    def open_novo_projeto(self):
        self.show_novo_projeto = True
        self.np_form_key += 1      # força remount dos inputs (fix typing)
        self.np_contrato = ""
        self.np_projeto = ""
        self.np_cliente = ""
        self.np_terceirizado = ""
        self.np_localizacao = ""
        self.np_data_inicio = ""
        self.np_data_termino = ""
        self.np_tipo = "EPC"
        self.np_potencia_kwp = ""
        self.np_prazo_dias = ""
        self.np_priority = "Média"
        self.np_efetivo_planejado = ""
        self.np_valor_contratado = ""
        self.np_dias_uteis = ["seg", "ter", "qua", "qui", "sex"]
        self.np_saving = False
        self.np_error = ""

    def toggle_np_dia(self, dia: str):
        """Toggle a working day in the novo projeto form."""
        current = list(self.np_dias_uteis)
        if dia in current:
            if len(current) > 1:  # mínimo 1 dia
                current.remove(dia)
        else:
            current.append(dia)
        self.np_dias_uteis = current

    def close_novo_projeto(self):
        self.show_novo_projeto = False

    def set_show_novo_projeto(self, v: bool):
        self.show_novo_projeto = v

    def set_np_contrato(self, v: str):
        import re as _re, unicodedata as _ud
        # Permite apenas A-Z, 0-9, hífen e ponto — bloqueia caracteres inválidos para storage paths
        nfkd = _ud.normalize("NFKD", v or "")
        ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
        sanitized = _re.sub(r"[^A-Za-z0-9.\-]", "-", ascii_str).upper()
        self.np_contrato = sanitized
        if sanitized != (v or "").upper():
            self.np_error = "Código do contrato: use apenas letras, números e hífen (ex: BOM306-2026)."
        else:
            self.np_error = ""

    def set_np_projeto(self, v: str):
        self.np_projeto = v

    def set_np_cliente(self, v: str):
        self.np_cliente = v

    def set_np_terceirizado(self, v: str):
        self.np_terceirizado = v

    def set_np_localizacao(self, v: str):
        self.np_localizacao = v
        # Reset validation when user changes the field
        self.np_loc_confirmed = False
        self.np_loc_geocoded_name = ""
        self.np_loc_error = ""

    @rx.event(background=True)
    async def validate_np_localizacao(self):
        """Geocode the entered location and show result for user confirmation."""
        loc = ""
        async with self:
            loc = self.np_localizacao.strip()
            if not loc:
                return
            self.np_loc_validating = True
            self.np_loc_geocoded_name = ""
            self.np_loc_confirmed = False
            self.np_loc_error = ""
        try:
            from bomtempo.core.weather_api import _geocode_one
            import httpx
            async with httpx.AsyncClient() as client:
                result = await _geocode_one(client, loc)
            if result:
                # _geocode_one returns {"lat", "lon", "name"} where name is already "Cidade, Estado"
                geocoded = str(result.get("name", ""))
                lat = str(round(float(result.get("lat", 0)), 4))
                lon = str(round(float(result.get("lon", 0)), 4))
                async with self:
                    self.np_loc_geocoded_name = geocoded
                    self.np_loc_geocoded_lat = lat
                    self.np_loc_geocoded_lon = lon
                    self.np_loc_validating = False
            else:
                async with self:
                    self.np_loc_error = f"Localidade não encontrada: '{loc}'. Tente ser mais específico (ex: 'Guaiúba, Ceará')."
                    self.np_loc_validating = False
        except Exception as e:
            async with self:
                self.np_loc_error = f"Erro ao validar localidade: {str(e)[:100]}"
                self.np_loc_validating = False

    def confirm_np_localizacao(self):
        """User confirmed the geocoded location — also updates the text field."""
        if self.np_loc_geocoded_name:
            self.np_localizacao = self.np_loc_geocoded_name
            self.np_loc_confirmed = True

    def reject_np_localizacao(self):
        """User wants to change location — clear everything and remount the input."""
        self.np_localizacao = ""
        self.np_loc_geocoded_name = ""
        self.np_loc_geocoded_lat = ""
        self.np_loc_geocoded_lon = ""
        self.np_loc_confirmed = False
        self.np_loc_validating = False
        self.np_loc_error = ""
        self.np_loc_input_key += 1  # forces React to remount the input as empty

    @rx.event(background=True)
    async def validate_ep_localizacao(self):
        """Geocode for the edit projeto form."""
        loc = ""
        async with self:
            loc = self.ep_localizacao.strip()
            if not loc:
                return
            self.ep_loc_validating = True
            self.ep_loc_geocoded_name = ""
            self.ep_loc_confirmed = False
            self.ep_loc_error = ""
        try:
            from bomtempo.core.weather_api import _geocode_one
            import httpx
            async with httpx.AsyncClient() as client:
                result = await _geocode_one(client, loc)
            if result:
                geocoded = str(result.get("name", ""))
                lat = str(round(float(result.get("lat", 0)), 4))
                lon = str(round(float(result.get("lon", 0)), 4))
                async with self:
                    self.ep_loc_geocoded_name = geocoded
                    self.ep_loc_geocoded_lat = lat
                    self.ep_loc_geocoded_lon = lon
                    self.ep_loc_validating = False
            else:
                async with self:
                    self.ep_loc_error = f"Localidade não encontrada: '{loc}'. Tente ser mais específico."
                    self.ep_loc_validating = False
        except Exception as e:
            async with self:
                self.ep_loc_error = f"Erro ao validar: {str(e)[:100]}"
                self.ep_loc_validating = False

    def confirm_ep_localizacao(self):
        """User confirmed the geocoded location — also updates the text field."""
        if self.ep_loc_geocoded_name:
            self.ep_localizacao = self.ep_loc_geocoded_name
            self.ep_loc_confirmed = True

    def reject_ep_localizacao(self):
        self.ep_localizacao = ""
        self.ep_loc_geocoded_name = ""
        self.ep_loc_geocoded_lat = ""
        self.ep_loc_geocoded_lon = ""
        self.ep_loc_confirmed = False
        self.ep_loc_validating = False
        self.ep_loc_error = ""
        self.ep_loc_input_key += 1  # forces React to remount the input as empty

    def set_ep_localizacao(self, v: str):
        self.ep_localizacao = v
        self.ep_loc_confirmed = False
        self.ep_loc_geocoded_name = ""
        self.ep_loc_error = ""

    def _recalc_np_termino(self):
        """inicio + prazo_dias → termino (dias corridos)."""
        try:
            from datetime import date, timedelta
            inicio = self.np_data_inicio.strip()
            prazo = self.np_prazo_dias.strip()
            if inicio and prazo and int(prazo) > 0:
                dt = date.fromisoformat(inicio) + timedelta(days=int(prazo) - 1)
                self.np_data_termino = dt.isoformat()
        except Exception:
            pass

    def _recalc_np_prazo(self):
        """inicio + termino → prazo_dias (dias corridos, inclusivo)."""
        try:
            from datetime import date
            inicio = self.np_data_inicio.strip()
            termino = self.np_data_termino.strip()
            if inicio and termino:
                d0 = date.fromisoformat(inicio)
                d1 = date.fromisoformat(termino)
                if d1 >= d0:
                    self.np_prazo_dias = str((d1 - d0).days + 1)
        except Exception:
            pass

    def set_np_data_inicio(self, v: str):
        self.np_data_inicio = v
        # Se termino preenchido mas sem prazo, recalcula prazo; caso contrário recalcula termino
        if self.np_data_termino and not self.np_prazo_dias:
            self._recalc_np_prazo()
        else:
            self._recalc_np_termino()

    def set_np_data_termino(self, v: str):
        self.np_data_termino = v
        # Ao preencher o termino manualmente → recalcular prazo_dias
        self._recalc_np_prazo()

    def set_np_tipo(self, v: str):
        self.np_tipo = v

    def set_np_potencia_kwp(self, v: str):
        self.np_potencia_kwp = v

    def set_np_prazo_dias(self, v: str):
        self.np_prazo_dias = v
        self._recalc_np_termino()

    def set_np_priority(self, v: str):
        self.np_priority = v

    def set_np_efetivo_planejado(self, v: str):
        self.np_efetivo_planejado = v

    # ── Editar Projeto handlers ──────────────────────────────────────────────

    def open_edit_projeto(self, contrato: str):
        """Abre o dialog de edição pré-preenchido com os dados do contrato."""
        row = next((c for c in self.contratos_list if c.get("contrato") == contrato), None)
        if not row:
            return
        self.show_edit_projeto = True
        self.ep_form_key += 1
        self.ep_id = str(row.get("id", ""))
        self.ep_contrato = str(row.get("contrato", ""))
        self.ep_projeto = str(row.get("projeto", ""))
        self.ep_cliente = str(row.get("cliente", ""))
        self.ep_terceirizado = str(row.get("terceirizado", "") or "")
        self.ep_localizacao = str(row.get("localizacao", "") or "")
        # Auto-confirm: location already saved = previously validated
        self.ep_loc_confirmed = bool(self.ep_localizacao)
        self.ep_loc_geocoded_name = ""
        self.ep_loc_error = ""
        self.ep_data_inicio = str(row.get("data_inicio", "") or "")
        self.ep_data_termino = str(row.get("data_termino", "") or "")
        self.ep_tipo = str(row.get("tipo", "EPC") or "EPC")
        self.ep_potencia_kwp = str(row.get("potencia_kwp", "") or "")
        self.ep_prazo_dias = str(row.get("prazo_contratual_dias", "") or "")
        self.ep_priority = str(row.get("priority", "Média") or "Média")
        self.ep_efetivo_planejado = str(row.get("efetivo_planejado", "") or "")
        dias_raw = str(row.get("dias_uteis_semana", "") or "seg,ter,qua,qui,sex")
        self.ep_dias_uteis = [d.strip() for d in dias_raw.split(",") if d.strip()] or ["seg", "ter", "qua", "qui", "sex"]
        self.ep_saving = False
        self.ep_deleting = False
        self.ep_error = ""
        self.ep_confirm_delete = False

    def close_edit_projeto(self):
        self.show_edit_projeto = False
        self.ep_confirm_delete = False

    def set_ep_projeto(self, v: str): self.ep_projeto = v
    def set_ep_cliente(self, v: str): self.ep_cliente = v
    def set_ep_terceirizado(self, v: str): self.ep_terceirizado = v
    def set_ep_data_inicio(self, v: str):
        self.ep_data_inicio = v
        if self.ep_data_termino and not self.ep_prazo_dias:
            self._recalc_ep_prazo()
        else:
            self._recalc_ep_termino()

    def set_ep_data_termino(self, v: str):
        self.ep_data_termino = v
        self._recalc_ep_prazo()

    def _recalc_ep_termino(self):
        try:
            from datetime import date, timedelta
            inicio = self.ep_data_inicio.strip()
            prazo = self.ep_prazo_dias.strip()
            if inicio and prazo and int(prazo) > 0:
                dt = date.fromisoformat(inicio) + timedelta(days=int(prazo) - 1)
                self.ep_data_termino = dt.isoformat()
        except Exception:
            pass

    def _recalc_ep_prazo(self):
        try:
            from datetime import date
            inicio = self.ep_data_inicio.strip()
            termino = self.ep_data_termino.strip()
            if inicio and termino:
                d0 = date.fromisoformat(inicio)
                d1 = date.fromisoformat(termino)
                if d1 >= d0:
                    self.ep_prazo_dias = str((d1 - d0).days + 1)
        except Exception:
            pass

    def set_ep_tipo(self, v: str): self.ep_tipo = v
    def set_ep_potencia_kwp(self, v: str): self.ep_potencia_kwp = v
    def set_ep_prazo_dias(self, v: str):
        self.ep_prazo_dias = v
        self._recalc_ep_termino()
    def set_ep_priority(self, v: str): self.ep_priority = v
    def set_ep_efetivo_planejado(self, v: str): self.ep_efetivo_planejado = v
    def toggle_ep_confirm_delete(self): self.ep_confirm_delete = not self.ep_confirm_delete

    def toggle_ep_dia(self, dia: str):
        """Toggle a working day in the edit projeto form."""
        current = list(self.ep_dias_uteis)
        if dia in current:
            if len(current) > 1:  # mínimo 1 dia
                current.remove(dia)
        else:
            current.append(dia)
        self.ep_dias_uteis = current

    @rx.event(background=True)
    async def save_edit_projeto(self):
        async with self:
            projeto = self.ep_projeto.strip()
            cliente = self.ep_cliente.strip()
            if not projeto or not cliente:
                self.ep_error = "Projeto e cliente são obrigatórios."
                return
            if self.ep_localizacao.strip() and not self.ep_loc_confirmed:
                self.ep_error = "Valide a localização antes de salvar (clique em 'Validar' e depois 'Confirmar')."
                return
            self.ep_saving = True
            self.ep_error = ""
            contrato = self.ep_contrato

        from bomtempo.core.supabase_client import sb_update
        try:
            async with self:
                potencia_raw = self.ep_potencia_kwp.strip().replace(",", ".")
                prazo_raw = self.ep_prazo_dias.strip()
                efetivo_raw = self.ep_efetivo_planejado.strip()
                dias_uteis_str = ",".join(self.ep_dias_uteis) if self.ep_dias_uteis else "seg,ter,qua,qui,sex"
                payload = {
                    "projeto":             projeto,
                    "cliente":             cliente,
                    "terceirizado":        self.ep_terceirizado.strip(),
                    "localizacao":         self.ep_localizacao.strip(),
                    "data_inicio":         self.ep_data_inicio or None,
                    "data_termino":        self.ep_data_termino or None,
                    "tipo":                self.ep_tipo,
                    "potencia_kwp":        float(potencia_raw) if potencia_raw else None,
                    "prazo_contratual_dias": int(prazo_raw) if prazo_raw else None,
                    "priority":            self.ep_priority,
                    "efetivo_planejado":   int(efetivo_raw) if efetivo_raw else None,
                    "dias_uteis_semana":   dias_uteis_str,
                }

            sb_update("contratos", {"contrato": contrato}, {k: v for k, v in payload.items() if v is not None or k in ("data_inicio", "data_termino")})

            async with self:
                self.ep_saving = False
                self.show_edit_projeto = False
                # Força recarga: limpa lista e invalida cache de disco
                self.contratos_list = []
                DataLoader.invalidate_cache(self.current_client_id)

            yield GlobalState.load_data()

        except Exception as e:
            async with self:
                self.ep_error = f"Erro ao salvar: {str(e)[:100]}"
                self.ep_saving = False

    @rx.event(background=True)
    async def delete_projeto(self):
        async with self:
            contrato = self.ep_contrato
            self.ep_deleting = True
            self.ep_error = ""

        from bomtempo.core.supabase_client import sb_delete
        try:
            sb_delete("contratos", {"contrato": contrato})
            async with self:
                self.ep_deleting = False
                self.show_edit_projeto = False
                # Força recarga: limpa lista e invalida cache de disco
                self.contratos_list = []
                DataLoader.invalidate_cache(self.current_client_id)

            yield GlobalState.load_data()

        except Exception as e:
            async with self:
                self.ep_error = f"Erro ao excluir: {str(e)[:100]}"
                self.ep_deleting = False

    @rx.event(background=True)
    async def save_novo_projeto(self):
        async with self:
            contrato = self.np_contrato.strip().upper()
            projeto = self.np_projeto.strip()
            cliente = self.np_cliente.strip()
            if not contrato or not projeto or not cliente:
                self.np_error = "Contrato, projeto e cliente são obrigatórios."
                return
            # Bloquear se localização foi preenchida mas não validada
            if self.np_localizacao.strip() and not self.np_loc_confirmed:
                self.np_error = "Valide a localização antes de salvar (clique em 'Validar' e depois 'Confirmar')."
                return
            import re as _re2
            if not _re2.match(r'^[A-Z0-9.\-]+$', contrato):
                self.np_error = "Código do contrato: use apenas letras, números e hífen (ex: BOM306-2026)."
                return
            self.np_saving = True
            self.np_error = ""
            potencia = float(self.np_potencia_kwp.replace(",", ".")) if self.np_potencia_kwp.strip() else 0.0
            prazo = int(self.np_prazo_dias.strip()) if self.np_prazo_dias.strip() else 0
            efetivo = int(self.np_efetivo_planejado.strip()) if self.np_efetivo_planejado.strip() else 0
            _raw_valor = self.np_valor_contratado.strip().replace(".", "").replace(",", ".")
            valor = float(_raw_valor) if _raw_valor else 0.0
            client_id = str(self.current_client_id or "")
            localizacao = self.np_localizacao.strip()
            dias_uteis_str = ",".join(self.np_dias_uteis) if self.np_dias_uteis else "seg,ter,qua,qui,sex"
            payload = {
                "contrato":              contrato,
                "projeto":               projeto,
                "cliente":               cliente,
                "terceirizado":          self.np_terceirizado.strip(),
                "localizacao":           localizacao,
                "data_inicio":           self.np_data_inicio or None,
                "data_termino":          self.np_data_termino or None,
                "tipo":                  self.np_tipo,
                "potencia_kwp":          potencia,
                "prazo_contratual_dias": prazo,
                "priority":              self.np_priority,
                "efetivo_planejado":     efetivo,
                "status":                "Em Execução",
                "valor_contratado":      valor,
                "client_id":             client_id or None,
                "dias_uteis_semana":     dias_uteis_str,
            }

        from bomtempo.core.supabase_client import sb_insert, sb_select

        # Verificar se contrato já existe
        existing = sb_select("contratos", filters={"contrato": contrato}, limit=1)
        if existing:
            async with self:
                self.np_error = f"Contrato '{contrato}' já existe."
                self.np_saving = False
            return

        try:
            sb_insert("contratos", payload)

            # Auto-geocode if localizacao provided (Nominatim) — run in executor to avoid blocking event loop
            if localizacao:
                try:
                    import asyncio as _asyncio
                    import requests as _req
                    from bomtempo.core.supabase_client import sb_update
                    _loc = localizacao
                    _contrato = contrato
                    def _geocode():
                        resp = _req.get(
                            "https://nominatim.openstreetmap.org/search",
                            params={"q": _loc, "format": "json", "limit": 1},
                            headers={"User-Agent": "bomtempo-dashboard/1.0"},
                            timeout=8,
                        )
                        return resp.json()
                    results = await _asyncio.get_running_loop().run_in_executor(get_http_executor(), _geocode)
                    if results:
                        lat = float(results[0].get("lat", 0))
                        lng = float(results[0].get("lon", 0))
                        if lat or lng:
                            sb_update("contratos", {"contrato": _contrato}, {"lat": lat, "lng": lng})
                except Exception:
                    pass  # geocode failure is non-fatal

            async with self:
                self.np_saving = False
                self.show_novo_projeto = False
                self.contratos_list = []  # força recarga
                DataLoader.invalidate_cache(self.current_client_id)
            yield GlobalState.load_data()

        except Exception as e:
            async with self:
                self.np_error = f"Erro ao salvar: {str(e)[:100]}"
                self.np_saving = False

    def set_project_status_filter(self, value: str):
        if self.project_status_filter == value:
            self.project_status_filter = ""
        else:
            self.project_status_filter = value

    def set_hub_filter_tipo(self, value: str):
        self.hub_filter_tipo = "" if self.hub_filter_tipo == value else value

    def set_hub_filter_priority(self, value: str):
        self.hub_filter_priority = "" if self.hub_filter_priority == value else value

    def toggle_hub_filters(self):
        self.hub_show_filters = not self.hub_show_filters

    def clear_hub_filters(self):
        self.project_status_filter = ""
        self.hub_filter_tipo = ""
        self.hub_filter_priority = ""

    def open_duplicar_projeto(self):
        self.show_duplicar_projeto = True
        self.dup_source_contrato = ""

    def close_duplicar_projeto(self):
        self.show_duplicar_projeto = False
        self.dup_source_contrato = ""

    def set_show_duplicar_projeto(self, v: bool):
        self.show_duplicar_projeto = v

    def set_dup_source_contrato(self, value: str):
        self.dup_source_contrato = value

    def confirm_duplicar_projeto(self):
        """Copy source contract fields into novo projeto form and open it."""
        src = next(
            (c for c in self.contratos_list if c.get("contrato") == self.dup_source_contrato),
            None,
        )
        self.show_duplicar_projeto = False
        self.dup_source_contrato = ""
        # Reset form
        self.np_contrato = ""
        self.np_saving = False
        self.np_error = ""
        if src:
            self.np_projeto = str(src.get("projeto", ""))
            self.np_cliente = str(src.get("cliente", ""))
            self.np_terceirizado = str(src.get("terceirizado", ""))
            self.np_localizacao = str(src.get("localizacao", ""))
            self.np_data_inicio = str(src.get("data_inicio", "") or "")[:10]
            self.np_data_termino = str(src.get("data_termino", "") or "")[:10]
            self.np_tipo = str(src.get("tipo", "EPC") or "EPC")
            self.np_potencia_kwp = str(src.get("potencia_kwp", "") or "")
            self.np_prazo_dias = str(src.get("prazo_contratual_dias", "") or "")
            self.np_priority = str(src.get("priority", "Média") or "Média")
            self.np_efetivo_planejado = str(src.get("efetivo_planejado", "") or "")
        else:
            self.np_projeto = ""
            self.np_cliente = ""
            self.np_terceirizado = ""
            self.np_localizacao = ""
            self.np_data_inicio = ""
            self.np_data_termino = ""
            self.np_tipo = "EPC"
            self.np_potencia_kwp = ""
            self.np_prazo_dias = ""
            self.np_priority = "Média"
            self.np_efetivo_planejado = ""
        self.show_novo_projeto = True

    @rx.event(background=True)
    async def set_project_hub_tab(self, tab: str):
        """Troca a tab ativa e dispara lazy load de auditoria/timeline na 1ª visita."""
        from bomtempo.state.hub_state import HubState
        contrato = ""
        async with self:
            self.project_hub_tab = tab
            contrato = self.selected_project

        if not contrato:
            return

        hub = await self.get_state(HubState)

        if tab == "auditoria" and hub._audit_loaded_contrato != contrato:
            yield HubState.load_auditoria(contrato)
        elif tab == "timeline" and hub._timeline_loaded_contrato != contrato:
            yield HubState.load_timeline(contrato)

    def set_windy_layer(self, layer: str):
        """Switch the active Windy map overlay layer."""
        self.windy_layer = layer

    @rx.event(background=True)
    async def select_project(self, code: str):
        """Unified entry point for Gestão de Projetos Hub.
        Sets both legacy vars (for backward compat) and new unified var.
        State update released immediately so UI can navigate; heavy loads fire as separate events.
        """
        from bomtempo.state.hub_state import HubState
        from bomtempo.state.fin_state import FinState

        # ── 1. Sync state update — released before any I/O ───────────────────
        async with self:
            self.selected_project = code
            self.selected_contrato = code
            self.obras_selected_contract = code
            self.hub_tab = "visao_geral"
            self.project_hub_tab = "visao_geral"
            self.projetos_fase_filter = ""
            self.obra_insight_text = ""
            self.obra_insight_loading = True
            self.obra_insight_generated_at = ""
            self._insight_target = code  # cancel guard: só este código é válido
            self.weather_loading = True
            self.weather_data = {}
            self.weather_location_name = ""
            self.weather_risk_level = "Unknown"
            self.project_campo_rdos = []
            self.project_campo_loading = False

        # ── 2. Fire heavy loaders OUTSIDE the lock — each runs independently ─
        # Auditoria e Timeline carregam lazy (só quando a tab for aberta pela 1ª vez)
        yield GlobalState.load_weather_data
        yield GlobalState.generate_obra_insight_bg
        yield HubState.load_cronograma(code)
        yield FinState.load_financeiro(code)

    @rx.event(background=True)
    async def deselect_project(self):
        """Return to the project pulse list view."""
        async with self:
            self.selected_project = ""
            self.selected_contrato = ""
            self.obras_selected_contract = ""
            self.obra_insight_text = ""
            self.obra_insight_loading = False
            self.obra_insight_generated_at = ""
            self._insight_target = ""  # cancela qualquer insight em background
            self.project_hub_tab = "visao_geral"
            self.project_campo_rdos = []
            self.project_campo_loading = False

    def set_hub_selected_project(self, contrato: str):
        """Select a project in the Hub de Operações — maps to existing selected_project."""
        self.selected_project = contrato
        self.hub_tab = "visao_geral"
        self.project_hub_tab = "visao_geral"

    @rx.event(background=True)
    async def set_hub_tab(self, tab: str):
        """Set hub sub-page tab — mirrors project_hub_tab.
        When switching to Dashboard, auto-trigger Agente de Atividades.
        Lazy loads Auditoria and Timeline on first visit."""
        from bomtempo.state.hub_state import HubState
        contrato = ""
        async with self:
            self.hub_tab = tab
            self.project_hub_tab = tab
            contrato = self.selected_project

        if not contrato:
            return

        audit_loaded = ""
        timeline_loaded = ""
        async with self:
            hub = await self.get_state(HubState)
            audit_loaded = hub._audit_loaded_contrato
            timeline_loaded = hub._timeline_loaded_contrato

        if tab == "dashboard":
            yield HubState.run_agente_atividades(contrato)
        elif tab == "auditoria" and audit_loaded != contrato:
            yield HubState.load_auditoria(contrato)
        elif tab == "timeline" and timeline_loaded != contrato:
            yield HubState.load_timeline(contrato)

    @rx.event(background=True)
    async def sync_financeiro_list(self):
        """Recarrega fin_custos do Supabase e recomputa gráficos do módulo /financeiro.
        Chamado pelo FinState após save/delete para manter o dashboard sidebar sincronizado."""
        import asyncio
        from bomtempo.core.supabase_client import sb_select
        try:
            loop = asyncio.get_running_loop()
            rows = await loop.run_in_executor(
                get_db_executor(),
                lambda: sb_select("fin_custos", limit=2000) or [],
            )
            records = []
            for r in rows:
                prev = float(r.get("valor_previsto", 0) or 0)
                exec_ = float(r.get("valor_executado", 0) or 0)
                records.append({
                    "id":             str(r.get("id", "")),
                    "contrato":       str(r.get("contrato", "") or ""),
                    "categoria_id":   str(r.get("categoria_id", "") or ""),
                    "categoria_nome": str(r.get("categoria_nome", "") or "—"),
                    "empresa":        str(r.get("empresa", "") or ""),
                    "descricao":      str(r.get("descricao", "") or "—"),
                    "valor_previsto": prev,
                    "valor_executado": exec_,
                    "status":         str(r.get("status", "previsto") or "previsto"),
                    "data_custo":     str(r.get("data_custo", "") or "")[:10],
                    "atividade_id":   str(r.get("atividade_id", "") or ""),
                    "observacoes":    str(r.get("observacoes", "") or ""),
                    "created_by":     str(r.get("created_by", "") or ""),
                })
            async with self:
                self.financeiro_list = records
                self._recompute_fin_charts()
                self._recompute_popup_rows()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"sync_financeiro_list error: {e}")

    @rx.event(background=True)
    async def load_project_campo_rdos(self):
        """Load recent RDOs for the selected project (Campo tab)."""
        import asyncio
        async with self:
            code = self.selected_project
            self.project_campo_loading = True
        if not code:
            async with self:
                self.project_campo_loading = False
            return
        from bomtempo.core.supabase_client import sb_select
        loop = asyncio.get_running_loop()
        rdos = await loop.run_in_executor(
            get_db_executor(),
            lambda: sb_select("rdo_master", filters={"contrato": code}, limit=20) or []
        )
        rdos_sorted = sorted(rdos, key=lambda r: str(r.get("data_rdo", "")), reverse=True)
        async with self:
            self.project_campo_rdos = rdos_sorted
            self.project_campo_loading = False

    @rx.event(background=True)
    async def select_obra_detail(self, label: str):
        """Navigate to obra detail view and trigger AI + weather in parallel."""
        async with self:
            self.obras_selected_contract = label
            self.obra_insight_text = ""
            self.obra_insight_loading = True
            self.obra_insight_generated_at = ""
            # Pre-set weather loading so the widget shows immediately
            self.weather_loading = True
            self.weather_data = {}
            yield GlobalState.load_weather_data
            yield GlobalState.generate_obra_insight_bg

    @rx.event(background=True)
    async def deselect_obra(self):
        """Return to obras list view."""
        async with self:
            self.obras_selected_contract = ""
            self.obra_insight_text = ""
            self.obra_insight_loading = False
            self.obra_insight_generated_at = ""

    @rx.event(background=True)
    async def generate_obra_insight_bg(self):
        """Background fire-and-forget AI insight for the selected obra.
        Caches result in hub_intelligence for 24h — no unnecessary AI calls."""
        from bomtempo.core.supabase_client import sb_select, sb_insert, sb_update

        async with self:
            data = dict(self.obra_enterprise_data)
            disciplines = list(self.disciplina_progress_chart)
            selected = self.obras_selected_contract or self.selected_project
            client_id = str(self.current_client_id or "")
            target_at_start = str(self._insight_target or "")

        if not selected:
            async with self:
                self.obra_insight_loading = False
            return

        # ── Cancel guard: aborta se o usuário já navegou para outro projeto ──
        if target_at_start and target_at_start != selected:
            async with self:
                self.obra_insight_loading = False
            return

        # ── Check 24h cache ──────────────────────────────────────────────────
        try:
            _cache_filters = {"contrato": selected, "insight_type": "obra_insight"}
            if client_id:
                _cache_filters["client_id"] = client_id
            cached = sb_select("hub_intelligence", filters=_cache_filters, limit=1)
            if cached:
                row = cached[0]
                gen_at_str = str(row.get("generated_at") or "")
                if gen_at_str:
                    from datetime import timezone as _tz
                    gen_dt = datetime.fromisoformat(gen_at_str.replace("Z", "+00:00"))
                    age_h = (datetime.now(_tz.utc) - gen_dt).total_seconds() / 3600
                    if age_h < 24:
                        cached_text = str(row.get("insight_text") or "")
                        cached_label = gen_dt.astimezone(
                            timezone(timedelta(hours=-3))
                        ).strftime("%d/%m %H:%M")
                        if cached_text:
                            async with self:
                                self.obra_insight_text = cached_text
                                self.obra_insight_generated_at = cached_label
                                self.obra_insight_loading = False
                            return
        except Exception:
            pass  # cache miss → generate fresh

        if not data:
            async with self:
                self.obra_insight_loading = False
            return

        # ── Data completeness guard — never hallucinate on empty projects ────
        bp = float(data.get("budget_planejado", 0) or 0)
        br = float(data.get("budget_realizado", 0) or 0)
        avanco_check = float(data.get("avanco_pct", 0) or 0)
        efetivo_check = int(data.get("efetivo_planejado", 0) or 0)
        equipe_presente = int(data.get("equipe_presente_hoje", 0) or 0)
        has_financeiro = bp > 0 or br > 0
        has_cronograma = len(disciplines) > 0 and any(
            float(d.get("previsto_pct", 0) or 0) > 0 or float(d.get("realizado_pct", 0) or 0) > 0
            for d in disciplines
        )
        has_equipe = efetivo_check > 0
        # Operational activity: obra has some actual execution happening
        has_operational_data = avanco_check > 0 or equipe_presente > 0 or br > 0
        data_score = sum([has_financeiro, has_cronograma, has_equipe])

        # Block AI when there is no meaningful operational data to analyze.
        # Having only planned/contract values (bp, efetivo_planejado) with everything
        # else at zero means the obra hasn't started — nothing real to analyze.
        if data_score == 0 or (data_score <= 1 and not has_operational_data):
            no_data_msg = (
                f"O projeto {data.get('contrato', selected)} ainda não possui dados operacionais suficientes para análise. "
                "Preencha o cronograma de atividades com avanço real, registre o orçamento executado "
                "e a equipe em campo para que o Feed de Inteligência possa gerar diagnósticos baseados em fatos."
            )
            now_brt_label = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m %H:%M")
            async with self:
                self.obra_insight_text = no_data_msg
                self.obra_insight_generated_at = now_brt_label
                self.obra_insight_loading = False
            return

        # ── Fetch timeline documents for doc-awareness ───────────────────────
        doc_context = ""
        try:
            _tl_f = {"contrato": selected, "is_document": True}
            if client_id:
                _tl_f["client_id"] = client_id
            tl_docs = sb_select("hub_timeline", filters=_tl_f, limit=20)
            if tl_docs:
                doc_lines = []
                for d in tl_docs:
                    titulo = str(d.get("titulo") or "")
                    descricao = str(d.get("descricao") or "")
                    nome = str(d.get("anexo_nome") or "")
                    entry = f"• {titulo}"
                    if nome:
                        entry += f" [{nome}]"
                    if descricao:
                        entry += f": {descricao[:200]}"
                    doc_lines.append(entry)
                doc_context = "\n\nDOCUMENTOS DO PROJETO (da timeline):\n" + "\n".join(doc_lines)
        except Exception:
            pass

        # Build context
        delayed = [
            d.get("label", d.get("categoria", ""))
            for d in disciplines
            if float(d.get("realizado_pct", 0)) < float(d.get("previsto_pct", 0))
        ]
        on_track = [
            d.get("label", d.get("categoria", ""))
            for d in disciplines
            if float(d.get("realizado_pct", 0)) >= float(d.get("previsto_pct", 0))
        ]

        # bp, br, avanco_check, efetivo_check already computed in guard block above
        if bp > 0:
            variance = ((br - bp) / bp) * 100
            if variance > 10:
                budget_status = f"estourado em {variance:.0f}%"
            elif variance > 0:
                budget_status = f"levemente acima em {variance:.0f}%"
            else:
                budget_status = f"dentro do previsto ({abs(variance):.0f}% de sobra)"
        else:
            budget_status = "orçamento não configurado"

        risco = int(data.get("risco_geral_score", 0) or 0)
        avanco = avanco_check
        equipe_hoje = int(data.get("equipe_presente_hoje", 0) or 0)
        efetivo_plan = efetivo_check
        chuva = float(data.get("chuva_acumulada_mm", 0) or 0)

        context = (
            f"Obra: {data.get('contrato', '—')} — {data.get('cliente', '—')}\n"
            f"Localização: {data.get('localizacao', '—')}\n"
            f"Avanço físico médio: {avanco:.1f}%\n"
            f"Orçamento: {budget_status}\n"
            f"Equipe hoje: {equipe_hoje} pessoas (planejado: {efetivo_plan})\n"
            f"Chuva acumulada: {chuva:.0f}mm\n"
            f"Score de risco: {risco}/100\n"
            f"Disciplinas em dia: {', '.join(on_track) if on_track else 'nenhuma'}\n"
            f"Disciplinas em atraso: {', '.join(delayed) if delayed else 'nenhuma'}"
            + doc_context
        )

        data_partial_warn = ""
        if data_score == 1:
            data_partial_warn = (
                " ATENÇÃO: os dados deste projeto são parciais — apenas "
                + ("orçamento" if has_financeiro else ("cronograma" if has_cronograma else "equipe"))
                + " está preenchido. Baseie-se ESTRITAMENTE nos dados fornecidos."
                " NÃO infira, assuma, extrapole ou invente informações sobre o que não está nos dados."
                " Se faltar informação para uma recomendação, diga explicitamente que o dado não está disponível."
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "Você é um analista sênior de obras de engenharia civil. "
                    "Gere UM parágrafo executivo (2 a 3 frases) de diagnóstico desta obra, em português. "
                    "Baseie-se EXCLUSIVAMENTE nos dados numéricos fornecidos — jamais invente, assuma ou extrapole informações ausentes. "
                    "Se um campo estiver zerado ou não configurado, mencione isso como uma lacuna, não como dado real. "
                    "Destaque o status geral, o principal risco e o ponto de atenção mais crítico COM BASE NOS DADOS. "
                    "Se houver documentos do projeto (contratos, cláusulas, especificações), considere multas, "
                    "critérios de aceite e obrigações contratuais ao avaliar riscos. "
                    "NÃO use markdown, bullets ou títulos — apenas texto corrido profissional."
                    + data_partial_warn
                ),
            },
            {"role": "user", "content": context},
        ]

        # Cancel guard pré-IA: verifica se usuário ainda está no mesmo projeto
        async with self:
            _current_target = str(self._insight_target or "")
        if _current_target and _current_target != selected:
            async with self:
                self.obra_insight_loading = False
            return

        import asyncio as _asyncio

        def run_ai():
            try:
                from bomtempo.core.ai_client import ai_client as _ai
                return _ai.query(messages)
            except Exception:
                risco_lvl = "crítico" if risco >= 60 else ("moderado" if risco >= 30 else "controlado")
                return (
                    f"Obra com risco {risco_lvl} ({risco}/100). "
                    f"Avanço físico em {avanco:.0f}% com orçamento {budget_status}. "
                    + (
                        f"Atenção às disciplinas: {', '.join(delayed)}."
                        if delayed
                        else "Todas as disciplinas dentro do prazo."
                    )
                )

        loop = _asyncio.get_running_loop()
        try:
            ai_text = await loop.run_in_executor(get_ai_executor(), run_ai)
        except Exception as e:
            logger.error(f"generate_obra_insight_bg executor error: {e}", exc_info=True)
            async with self:
                self.obra_insight_loading = False
                self.obra_insight_text = "Erro ao gerar análise. Tente novamente."
            return

        # Persist to cache
        now_utc = datetime.now(timezone(timedelta(hours=0))).isoformat()
        now_brt_label = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m %H:%M")
        try:
            _exist_filters = {"contrato": selected, "insight_type": "obra_insight"}
            if client_id:
                _exist_filters["client_id"] = client_id
            existing = sb_select("hub_intelligence", filters=_exist_filters, limit=1)
            record = {
                "contrato": selected,
                "client_id": client_id or None,
                "insight_type": "obra_insight",
                "insight_text": ai_text or "",
                "generated_at": now_utc,
            }
            if existing:
                sb_update("hub_intelligence", {"id": existing[0]["id"]}, record)
            else:
                sb_insert("hub_intelligence", record)
        except Exception:
            pass

        try:
            async with self:
                self.obra_insight_text = ai_text or "Análise em processamento..."
                self.obra_insight_generated_at = now_brt_label
                self.obra_insight_loading = False
            # Notify user that analysis is done (only if it was freshly generated, not from cache)
            yield rx.toast.success(
                "✦ Análise IA concluída — painel Inteligência atualizado.",
                duration=6000,
                position="bottom-right",
            )
        except Exception as e:
            logger.error(f"generate_obra_insight_bg state write error: {e}", exc_info=True)
            try:
                async with self:
                    self.obra_insight_loading = False
            except Exception:
                pass

    @rx.event(background=True)
    async def force_refresh_insight(self):
        """Force regenerate the AI insight, bypassing the 24h cache."""
        from bomtempo.core.supabase_client import sb_select, sb_update, sb_delete
        async with self:
            selected = self.obras_selected_contract or self.selected_project
            client_id = str(self.current_client_id or "")
            self.obra_insight_loading = True
            self.obra_insight_text = ""
            self.obra_insight_generated_at = ""
        # Invalidate cache entry so generate_obra_insight_bg skips the cache check
        try:
            _inv_filters = {"contrato": selected, "insight_type": "obra_insight"}
            if client_id:
                _inv_filters["client_id"] = client_id
            existing = sb_select("hub_intelligence", filters=_inv_filters, limit=1)
            if existing:
                # Set generated_at to 2 days ago to force cache miss
                old_ts = (datetime.now(timezone(timedelta(hours=0))) - timedelta(hours=25)).isoformat()
                sb_update("hub_intelligence", {"id": existing[0]["id"]}, {"generated_at": old_ts})
        except Exception:
            pass
        yield GlobalState.generate_obra_insight_bg

    async def select_obra_and_load_weather(self, value: str):
        """Sets the selected contract and reloads weather data."""
        self.set_obras_selected_contract(value)
        return GlobalState.load_weather_data

    @rx.event(background=True)
    async def load_weather_data(self):
        """Fetches weather data from OpenMeteo with Dynamic Geocoding.
        Background event — HTTP calls happen outside the state lock so card
        clicks are never blocked while weather is loading.
        """
        # ── Step 1: read needed state under the lock (no I/O here) ──────────
        async with self:
            contract_to_use = self.obras_selected_contract
            df_obras_ref = self._obras_df
            df_contratos_ref = self._contratos_df
            # Auto-detect first available contract when none is selected
            if not contract_to_use or contract_to_use == "Todos":
                for df_auto in (self._obras_df, self._contratos_df):
                    if (
                        df_auto is not None
                        and not df_auto.empty
                        and "localizacao" in df_auto.columns
                    ):
                        first_loc = df_auto["localizacao"].dropna()
                        first_loc = first_loc[first_loc.str.strip() != ""]
                        if not first_loc.empty and "contrato" in df_auto.columns:
                            contract_to_use = df_auto.loc[first_loc.index[0], "contrato"]
                        break

        # ── Step 2: pandas lookups outside the lock (CPU, no I/O) ──────────
        lat, lon = -8.05428, -34.8813  # Recife (fallback)
        location_name = "Recife, PE"
        city = None

        if contract_to_use and contract_to_use != "Todos":
            target_code = (
                contract_to_use.split(" - ")[0].strip()
                if " - " in contract_to_use
                else contract_to_use
            )
            logger.debug(f"Processing weather for contract: '{target_code}'")

            if df_obras_ref is not None and not df_obras_ref.empty:
                for _, row in df_obras_ref.iterrows():
                    contrato_val = str(row.get("contrato", "")).strip()
                    if contrato_val and (
                        target_code in contrato_val or contrato_val in target_code
                    ):
                        city = str(row.get("localizacao", "")).strip()
                        logger.debug(f"Weather lookup: found city '{city}' via OBRA")
                        break

            if not city and df_contratos_ref is not None and not df_contratos_ref.empty:
                for _, row in df_contratos_ref.iterrows():
                    contrato_val = str(row.get("contrato", "")).strip()
                    if contrato_val and (
                        target_code in contrato_val or contrato_val in target_code
                    ):
                        city = str(row.get("localizacao", "")).strip()
                        logger.debug(f"Weather lookup: found city '{city}' via CONTRATOS")
                        break

        # ── Step 2b: fallback — query Supabase directly if cache miss ──────────
        if (not city or city.lower() in ("", "nan")) and contract_to_use and contract_to_use != "Todos":
            try:
                from bomtempo.core.supabase_client import sb_select as _sb_select
                target_code = (
                    contract_to_use.split(" - ")[0].strip()
                    if " - " in contract_to_use
                    else contract_to_use
                )
                rows = _sb_select("contratos", filters={"contrato": target_code}, limit=1)
                if rows and rows[0].get("localizacao"):
                    city = str(rows[0]["localizacao"]).strip()
                    logger.debug(f"Weather lookup: found city '{city}' via Supabase direct")
            except Exception as sb_err:
                logger.warning(f"Weather Supabase fallback error: {sb_err}")

        # ── Step 3: geocoding HTTP call — outside the lock ──────────────────
        if city and city.lower() not in ("", "nan"):
            logger.debug(f"Geocoding city: '{city}'")
            try:
                coords = await weather_api.get_coordinates(city)
                if coords:
                    lat = coords["lat"]
                    lon = coords["lon"]
                    location_name = coords["name"]
            except Exception as geo_err:
                logger.error(f"Geocoding Error: {geo_err}")

        # ── Step 4: mark loading (brief lock) ───────────────────────────────
        async with self:
            self.weather_location_name = location_name
            self.weather_lat = lat
            self.weather_lon = lon
            self.weather_loading = True

        # ── Step 5: forecast HTTP call — outside the lock ───────────────────
        weather_result = None
        risk = "Unknown"
        try:
            weather_result = await weather_api.get_forecast(lat=lat, lon=lon)
            if weather_result:
                today_rain = weather_result.get("daily_rain_sum", [0])[0]
                today_prob = weather_result.get("daily_rain_prob", [0])[0]
                current_rain = weather_result.get("rain", 0)
                if current_rain > 5 or today_rain > 15 or today_prob > 80:
                    risk = "High"
                elif current_rain > 0.5 or today_rain > 5 or today_prob > 50:
                    risk = "Medium"
                else:
                    risk = "Low"
        except Exception as e:
            logger.error(f"Error loading weather: {e}")

        # ── Step 6: write results to state (brief lock) ──────────────────────
        try:
            async with self:
                if weather_result:
                    self.weather_data = weather_result
                self.weather_risk_level = risk
                self.weather_loading = False
        except Exception as e:
            logger.error(f"load_weather_data state write error: {e}", exc_info=True)
            try:
                async with self:
                    self.weather_loading = False
            except Exception:
                pass

    def _build_project_context_for_weather(self) -> str:
        """Extracts active obras and upcoming schedule milestones for weather cross-reference."""
        try:
            lines = []

            # Active obras — latest physical progress per project
            if not self._obras_df.empty:
                df = self._obras_df.copy()
                if "projeto" in df.columns:
                    if "data" in df.columns:
                        df["data"] = pd.to_datetime(df["data"], errors="coerce")
                        agg_cols = [
                            c
                            for c in ["previsto_pct", "realizado_pct", "comentario"]
                            if c in df.columns
                        ]
                        latest = (
                            df.sort_values("data")
                            .dropna(subset=["data"])
                            .groupby("projeto")[agg_cols]
                            .last()
                            .reset_index()
                        )
                    else:
                        agg_cols = [
                            c
                            for c in ["previsto_pct", "realizado_pct"]
                            if c in df.columns
                        ]
                        latest = df.groupby("projeto")[agg_cols].last().reset_index()

                    # Only obras not yet 100% complete
                    if "realizado_pct" in latest.columns:
                        active = latest[latest["realizado_pct"] < 100]
                    else:
                        active = latest

                    if not active.empty:
                        lines.append(f"OBRAS EM EXECUÇÃO ({len(active)} ativas):")
                        for _, row in active.head(8).iterrows():
                            proj = row.get("projeto", "—")
                            realizado = row.get("realizado_pct", "?")
                            previsto = row.get("previsto_pct", "?")
                            lines.append(
                                f"  - {proj}: {realizado}% realizado / {previsto}% previsto"
                            )

            # Upcoming activities in project schedule (next 10 days)
            if not self._projetos_df.empty:
                df = self._projetos_df.copy()
                if "termino_previsto" in df.columns and "conclusao_pct" in df.columns:
                    today = pd.Timestamp.now()
                    df["termino_previsto"] = pd.to_datetime(
                        df["termino_previsto"], errors="coerce"
                    )
                    upcoming = df[
                        (df["termino_previsto"] >= today)
                        & (df["termino_previsto"] <= today + pd.Timedelta(days=10))
                        & (df["conclusao_pct"] < 100)
                    ]
                    if not upcoming.empty:
                        lines.append(
                            f"\nATIVIDADES COM PRAZO NOS PRÓXIMOS 10 DIAS ({len(upcoming)}):"
                        )
                        for _, row in upcoming.head(8).iterrows():
                            ativ = row.get("atividade", "—")
                            fase = row.get("fase", "—")
                            termino = row.get("termino_previsto")
                            pct = row.get("conclusao_pct", 0)
                            termino_str = str(termino.date()) if pd.notna(termino) else "—"
                            lines.append(
                                f"  - [{fase}] {ativ} — prazo {termino_str}, {pct}% concluído"
                            )

            return "\n".join(lines) if lines else ""
        except Exception as e:
            logger.warning(f"Erro ao extrair contexto de projetos para clima: {e}")
            return ""

    async def analyze_weather_impact(self):
        """Context-aware weather impact analysis — crosses forecast with active obras and schedule."""
        if not self.weather_data:
            return

        self.is_analyzing = True
        self.show_analysis_dialog = True
        self.analysis_result = ""
        yield

        try:
            project_context = self._build_project_context_for_weather()
            result = AnalysisService.analyze_weather_impact(
                self.weather_data, self.weather_location_name, project_context
            )
            self.analysis_result = self._sanitize_markdown(result)
        except Exception as e:
            self.analysis_result = f"Erro na análise: {str(e)}"
            logger.error(f"Erro analyze_weather_impact: {e}")
        finally:
            self.is_analyzing = False
