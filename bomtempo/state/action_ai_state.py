"""
Action AI State — Escutador executivo com TTS + HITL.
Design: não é mini-chat. Mostra apenas a última resposta da IA em destaque.
Histórico de contexto mantido internamente para o loop agêntico.
"""

import asyncio
import json
import re

import reflex as rx

from bomtempo.core.ai_client import ai_client
from bomtempo.core.ai_context import AIContext
from bomtempo.core.admin_tools import ADMIN_AI_TOOLS, execute_admin_tool, execute_confirmed_action
from bomtempo.core.data_loader import DataLoader
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_rpc
from bomtempo.core.executors import (
    get_db_executor,
)

logger = get_logger(__name__)


def _amsg(role: str, content: str) -> dict:
    """Mensagem para o histórico interno do agente (não exibida como chat)."""
    return {"role": role, "content": content}


class ActionAIState(rx.State):
    """State for the Action AI escutador executivo popup."""

    # ── Popup / mode ─────────────────────────────────────────────
    is_open: bool = False
    is_hands_free: bool = False  # Modo contínuo: fala → resposta → TTS → fala
    show_text_input: bool = False  # Fallback: teclado visível

    # ── Recording ────────────────────────────────────────────────
    is_listening: bool = False
    is_processing: bool = False

    # ── Displayed content ─────────────────────────────────────────
    last_response: str = ""   # Última resposta da IA (exibida em destaque)
    input_text: str = ""      # Campo de texto (fallback)
    input_key: int = 0        # Incrementado ao preencher via chip/voz → força remount do input

    # ── Contexto interno do agente (não renderizado) ──────────────
    # Guardamos como list[dict] com role/content para o loop agêntico
    _context: list[dict] = []

    # ── HITL Confirmation ─────────────────────────────────────────
    hitl_pending: bool = False
    hitl_summary: str = ""
    hitl_preview_lines: list[str] = []
    hitl_action: str = ""
    hitl_data: dict = {}

    # ── Open / Close ─────────────────────────────────────────────

    async def open_popup(self):
        self.is_open = True
        yield rx.call_script(
            "if(window.actionAIRequestMicPermission) window.actionAIRequestMicPermission();"
        )

    async def close_popup(self):
        self.is_open = False
        self.is_listening = False
        self.is_hands_free = False
        self.show_text_input = False
        yield rx.call_script("if(window.actionAIStopVoice) window.actionAIStopVoice();")

    def toggle_text_input(self):
        self.show_text_input = not self.show_text_input
        self.input_text = ""
        self.input_key += 1

    def set_input_text(self, text: str):
        """Setter explícito — usado pelo chip para preencher o campo.
        Incrementa input_key para forçar remount do input não-controlado."""
        self.input_text = text
        self.input_key += 1

    async def toggle_hands_free(self):
        self.is_hands_free = not self.is_hands_free
        if not self.is_hands_free:
            self.is_listening = False
            yield rx.call_script("if(window.actionAIStopVoice) window.actionAIStopVoice();")
        else:
            yield ActionAIState.start_listening

    async def start_listening(self):
        self.is_listening = True
        yield rx.call_script("if(window.actionAIStartVoice) window.actionAIStartVoice();")

    async def stop_listening(self):
        self.is_listening = False
        yield rx.call_script("if(window.actionAIStopVoice) window.actionAIStopVoice();")

    # ── Voice callbacks ───────────────────────────────────────────

    async def on_voice_result(self, text: str):
        """Transcript do Web Speech API."""
        if not text.strip():
            if self.is_hands_free:
                yield ActionAIState.start_listening
            return
        self.is_listening = False
        self.input_text = text
        self.input_key += 1
        yield ActionAIState.send_message

    async def on_voice_stopped(self, _val: str):
        """Reconhecimento parou sem resultado."""
        self.is_listening = False
        if self.is_hands_free and not self.is_processing:
            yield ActionAIState.start_listening

    # ── Send (voz ou texto) ───────────────────────────────────────

    async def send_message(self):
        text = self.input_text.strip()
        if not text or self.is_processing:
            return
        # Fecha o teclado após enviar
        self.show_text_input = False
        self.input_text = ""
        self.input_key += 1
        self.is_processing = True
        # Adiciona ao contexto interno
        self._context = list(self._context) + [_amsg("user", text)]
        yield ActionAIState.run_agentic_loop

    async def on_enter_key(self, key: str):
        if key == "Enter":
            yield ActionAIState.send_message

    # ── HITL ─────────────────────────────────────────────────────

    @rx.event(background=True)
    async def confirm_hitl(self):
        async with self:
            action = self.hitl_action
            data = dict(self.hitl_data)
            # Inject real username so create_alert/send_document know who triggered
            try:
                from bomtempo.state.global_state import GlobalState
                gs = await self.get_state(GlobalState)
                _username = gs.current_user_name or "action_ai"
            except Exception:
                _username = "action_ai"
            data["_created_by"] = _username
            data["_sender_username"] = _username
            data["_client_id"] = str(gs.current_client_id or "")
            self.hitl_pending = False
            self.hitl_summary = ""
            self.hitl_preview_lines = []
            self.hitl_action = ""
            self.hitl_data = {}
            self.is_processing = True

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(get_db_executor(), lambda: execute_confirmed_action(action, data))

        async with self:
            self.last_response = result
            self._context = list(self._context) + [_amsg("assistant", result)]
            self.is_processing = False

    def reject_hitl(self):
        self.hitl_pending = False
        self.hitl_summary = ""
        self.hitl_preview_lines = []
        self.hitl_action = ""
        self.hitl_data = {}
        msg = "Ação cancelada. Como posso ajudar de outra forma?"
        self.last_response = msg
        self._context = list(self._context) + [_amsg("assistant", msg)]

    def new_conversation(self):
        self.last_response = ""
        self._context = []
        self.hitl_pending = False
        self.input_text = ""

    # ── Form Prefill Helpers ──────────────────────────────────────
    # Stored temporarily so the navigate handler can read them
    _prefill_type: str = ""
    _prefill_fields: dict = {}

    def store_prefill(self, prefill_type: str, fields: dict):
        """Store prefill data so it can be applied after navigation."""
        self._prefill_type = prefill_type
        self._prefill_fields = fields

    def apply_rdo_prefill(self):
        """Apply stored prefill fields to RDOState. Called on rdo-form page load."""
        from bomtempo.state.rdo_state import RDOState
        fields = self._prefill_fields
        if not fields or self._prefill_type != "rdo":
            return
        self._prefill_type = ""
        self._prefill_fields = {}
        events = []
        if fields.get("contrato"):
            events.append(RDOState.set_rdo_contrato(fields["contrato"]))
        if fields.get("data"):
            events.append(RDOState.set_rdo_data(fields["data"]))
        if fields.get("clima"):
            events.append(RDOState.set_rdo_clima(fields["clima"]))
        if fields.get("turno"):
            events.append(RDOState.set_rdo_turno(fields["turno"]))
        if fields.get("observacoes"):
            events.append(RDOState.set_rdo_observacoes(fields["observacoes"]))
        if fields.get("orientacao"):
            events.append(RDOState.set_rdo_orientacao(fields["orientacao"]))
        if fields.get("atividade_descricao"):
            events.append(RDOState.set_at_desc(fields["atividade_descricao"]))
        return events

    def apply_reembolso_prefill(self):
        """Apply stored prefill fields to ReembolsoState."""
        from bomtempo.state.reembolso_state import ReembolsoState
        fields = self._prefill_fields
        if not fields or self._prefill_type != "reembolso":
            return
        self._prefill_type = ""
        self._prefill_fields = {}
        events = []
        if fields.get("data"):
            events.append(ReembolsoState.set_data_abastecimento(fields["data"]))
        if fields.get("km_rodado"):
            events.append(ReembolsoState.set_km_final(fields["km_rodado"]))
        if fields.get("valor_litro"):
            events.append(ReembolsoState.set_valor_litro_and_calc(fields["valor_litro"]))
        if fields.get("litros"):
            events.append(ReembolsoState.set_litros_and_calc(fields["litros"]))
        return events

    # ── Agentic Loop ─────────────────────────────────────────────

    @rx.event(background=True)
    async def run_agentic_loop(self):
        try:
            async with self:
                username = "admin"
                user_role = "Administrador"
                tenant_name = ""
                client_id = ""
                is_mobile = False
                data = None
                context_snapshot = list(self._context)
                hands_free = self.is_hands_free
                try:
                    from bomtempo.state.global_state import GlobalState
                    gs = await self.get_state(GlobalState)
                    username = gs.current_user_name or "admin"
                    user_role = gs.current_user_role or "Administrador"
                    tenant_name = gs.current_client_name or ""
                    client_id = str(gs.current_client_id or "")
                    is_mobile = user_role == "Gestão-Mobile"
                    data = gs._as_data_dict()
                except Exception as _e:
                    logger.warning(f"ActionAI: falha ao ler GlobalState: {_e}")

            if not data:
                try:
                    loader = DataLoader(client_id=client_id)
                    data = loader.load_all()
                except Exception:
                    data = {}

            # ── Role-based tool filtering ──────────────────────────────
            _FORM_FILL_ONLY_ROLES = {"Mestre de Obras"}
            is_form_fill_only = user_role in _FORM_FILL_ONLY_ROLES
            _FORM_FILL_TOOL_NAMES = {"fill_rdo_form", "fill_reembolso_form"}

            if is_form_fill_only:
                available_tools = [t for t in ADMIN_AI_TOOLS if t["function"]["name"] in _FORM_FILL_TOOL_NAMES]
            else:
                available_tools = ADMIN_AI_TOOLS

            today_str = __import__('datetime').date.today().isoformat()

            system_prompt = AIContext.get_system_prompt(is_mobile=is_mobile, tenant_name=tenant_name, client_id=client_id)
            dashboard_context = "" if is_form_fill_only else (AIContext.get_dashboard_context(data) if data else "")
            raw_schema = "" if is_form_fill_only else (sb_rpc("get_schema_context") or "")
            tenant_sql_hint = (
                f"\n\n⚠️ ISOLAMENTO DE TENANT: SEMPRE inclua `WHERE client_id = '{client_id}'`"
                f" em TODAS as queries SQL quando o client_id for conhecido."
            ) if client_id and not is_form_fill_only else ""
            schema_context = raw_schema + tenant_sql_hint

            if is_form_fill_only:
                system_content = (
                    f"Você é o Assistente de Preenchimento de Formulários do BOMTEMPO. "
                    f"Usuário logado: **{username}** (Mestre de Obras). Data de hoje: {today_str}.\n"
                    "Sua ÚNICA função é ajudar o usuário a preencher formulários de RDO ou Reembolso por voz.\n"
                    "Você NÃO navega para outras páginas, NÃO acessa dados do banco, NÃO executa outras ações.\n\n"
                    "## COLETA MULTI-TURNO\n"
                    "O usuário pode fornecer campos em VÁRIAS falas consecutivas. Você deve ACUMULAR os campos "
                    "mencionados ao longo da conversa e só chamar fill_rdo_form / fill_reembolso_form quando "
                    "o usuário indicar que terminou (ex: 'pode preencher', 'pronto', 'pode ir') OU quando "
                    "tiver campos suficientes para uma ação útil (pelo menos contrato + data ou 2+ campos).\n"
                    "Se o usuário fornecer apenas 1 campo, responda confirmando e perguntando pelo próximo.\n\n"
                    "## TOOLS DISPONÍVEIS\n"
                    "  - fill_rdo_form: preenche formulário de Relatório Diário de Obra.\n"
                    f"    → clima: 'Ensolarado', 'Parcialmente Nublado', 'Nublado', 'Chuvoso', 'Chuvoso Forte', 'Nevando'\n"
                    "    → turno: 'Diurno', 'Noturno', 'Integral'\n"
                    "  - fill_reembolso_form: preenche formulário de reembolso de combustível.\n\n"
                    "## REGRAS\n"
                    "- Sempre confirme o que foi entendido: 'Entendido: contrato 001, clima ensolarado. Qual o turno?'\n"
                    "- Respostas: máximo 1-2 frases curtas.\n"
                    "- Se o usuário pedir algo fora do preenchimento, recuse em 1 frase.\n"
                )
            else:
                system_content = (
                    system_prompt
                    + f"\n\n## VOCÊ É O ACTION AI — Hub de Ações Executivas\n"
                    f"Usuário logado: **{username}**. Papel: {user_role}. Data de hoje: {today_str}.\n"
                    "Você executa ações reais no sistema via comandos de voz ou texto. Seu valor é AGIR, não responder.\n\n"
                    "## AÇÕES DISPONÍVEIS\n"
                    "**Navegação imediata** (navigate_to_page):\n"
                    "  - 'me leva para obras', 'abre o financeiro', 'vai para alertas', 'quero ver usuários'\n"
                    "  - Páginas: visao-geral, obras, projetos, financeiro, om, analytics, previsoes,\n"
                    "    relatorios, chat-ia, reembolso, reembolso-dash, rdo-form, rdo-historico, rdo-dashboard,\n"
                    "    admin/editar_dados, alertas, logs-auditoria, admin/usuarios, admin/observabilidade\n\n"
                    "**Preenchimento de formulário por voz** (multi-turno — acumule campos):\n"
                    "  - fill_rdo_form: 'preenche o RDO', 'registra o diário de obra', 'RDO de hoje ensolarado'\n"
                    f"    → extrai: contrato, data (YYYY-MM-DD), clima, turno, observacoes, orientacao, atividade_descricao\n"
                    "    → IMPORTANTE: o usuário pode fornecer campos em turnos separados — acumule no histórico e\n"
                    "      chame fill_rdo_form só quando tiver ≥2 campos ou o usuário disser 'pronto'/'pode preencher'.\n"
                    "  - fill_reembolso_form: 'preenche o reembolso', 'registra combustível', 'abasteci X litros'\n"
                    "    → extrai: data, km_rodado, valor_litro, litros\n\n"
                    "**Criação de registros no banco** (multi-turno HITL):\n"
                    "  - propose_create_record: 'adiciona um contrato', 'cria novo projeto', 'cadastra obra X'\n"
                    "    → FLUXO: 1) get_schema_info para ver colunas da tabela alvo\n"
                    "             2) Peça campos ao usuário turno a turno se necessário\n"
                    "             3) Quando tiver os campos principais, chame propose_create_record\n"
                    "             4) O usuário confirma via HITL → registro criado no banco\n"
                    "    → Tabelas: contratos, projetos, obras, financeiro, om\n\n"
                    "**Ações com confirmação HITL** (propõe → usuário confirma → executa):\n"
                    f"  - propose_change_own_password: 'troca minha senha' → SEMPRE perguntar nova senha antes de chamar a tool se não fornecida → logged_user='{username}'\n"
                    "  - propose_change_user_password: 'reseta a senha do João'\n"
                    "  - propose_create_user: 'cria usuário renato como Engenheiro'\n"
                    "  - propose_create_alert: 'me avisa quando RDO do contrato X não for enviado'\n"
                    "    → use execute_sql para descobrir código do contrato se necessário\n"
                    "  - propose_send_document: 'envie o RDO de ontem do contrato X para renato'\n"
                    "    → OBRIGATÓRIO: use execute_sql para buscar pdf_url em rdo_master E email/whatsapp em login\n"
                    "  - propose_update_record: alterar campo específico em qualquer tabela\n\n"
                    "**Consultas** (só para suportar uma AÇÃO):\n"
                    "  - execute_sql / get_schema_info\n"
                    "  - search_documents: busca cláusulas/termos em documentos anexados ao contrato (PDF, DOCX, TXT)\n"
                    "    → Use quando perguntar sobre multas, prazos, garantias, rescisão ou qualquer cláusula contratual\n\n"
                    "## REGRAS\n"
                    "- Prefira AGIR a responder com texto. Se o usuário quer ver algo, NAVEGUE.\n"
                    "- Multi-turno: se o usuário diz 'adiciona um contrato' mas não deu o nome ainda, PERGUNTE o nome\n"
                    "  antes de chamar get_schema_info. Acumule campos no contexto antes de propor.\n"
                    "- Respostas: máximo 2 frases. Confirme a ação tomada.\n"
                    "- NÃO use sintaxe de imagem Markdown ![...]().\n"
                    "- Tabela de usuários = 'login' (username, password, user_role, project, email, whatsapp).\n\n"
                    + dashboard_context
                    + f"\n\n## SCHEMA DO BANCO\n{schema_context}"
                )

            messages = [{
                "role": "system",
                "content": system_content,
            }]
            # Últimas 6 mensagens do contexto interno
            messages.extend(context_snapshot[-6:])

            pending_chart_json = ""
            pending_chart_id = ""

            for i in range(6):
                response = ai_client.query_agentic(
                    messages,
                    tools=available_tools,
                    force_tool=False,
                    username=username,
                    session_id="action_ai",
                )

                if isinstance(response, str):
                    final = re.sub(r"!\[.*?\]\(.*?\)", "", response).strip()
                    async with self:
                        self.last_response = final
                        self._context = list(self._context) + [_amsg("assistant", final)]
                        self.is_processing = False
                        if pending_chart_json and pending_chart_id:
                            safe_json = pending_chart_json.replace("`", "\\`")
                            yield rx.call_script(
                                f"window.__btpCharts = window.__btpCharts || {{}}; "
                                f"window.__btpCharts['{pending_chart_id}'] = {safe_json};"
                            )
                    if hands_free:
                        yield ActionAIState.start_listening
                    break

                tool_calls = response.tool_calls
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                })

                for tool_call in tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    result_str, proposal = execute_admin_tool(name, args)

                    if name == "generate_chart_data":
                        try:
                            parsed = json.loads(result_str)
                            if parsed.get("__chart__"):
                                pending_chart_json = result_str
                                pending_chart_id = f"chart_{tool_call.id.replace('-', '_')}"
                        except Exception:
                            pass

                    if proposal and proposal.get("__navigate__"):
                        page = proposal.get("page", "")
                        reason = proposal.get("reason", "")
                        prefill = proposal.get("__prefill__", "")
                        fields = proposal.get("fields", {})
                        async with self:
                            self.last_response = reason
                            self.is_processing = False
                            self.is_open = False
                            if prefill and fields:
                                self._prefill_type = prefill
                                self._prefill_fields = fields
                        yield rx.redirect(f"/{page}")
                        return

                    if proposal and proposal.get("__hitl__"):
                        async with self:
                            self.hitl_pending = True
                            self.hitl_summary = proposal["summary"]
                            self.hitl_preview_lines = proposal.get("preview_lines", [])
                            self.hitl_action = proposal["action"]
                            self.hitl_data = proposal["data"]
                            self.is_processing = False
                        return

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": result_str,
                    })
            else:
                async with self:
                    self.last_response = "Não consegui concluir. Tente reformular."
                    self.is_processing = False

        except Exception as e:
            logger.error(f"ActionAI loop error: {e}")
            async with self:
                self.last_response = "Erro ao processar. Tente novamente."
                self.is_processing = False
