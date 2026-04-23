"""
Admin AI Tools — Write operations gated behind Human-in-the-Loop (HITL) confirmation.
These tools are ONLY exposed in the Action AI popup, never in the regular chat.

Flow: AI proposes action → returns HITL confirmation dict → user approves → execute_admin_action()
"""

import json
from bomtempo.core.supabase_client import sb_insert, sb_update, sb_select
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

# ── Read tools (same as AI_TOOLS) + write tools ──────────────────────────────

ADMIN_AI_TOOLS = [
    # Read tools (inherited)
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "strict": True,
            "description": (
                "Executa uma consulta SQL SELECT no banco de dados Supabase. "
                "Use para buscar dados reais de contratos, financeiro, obras, RDO, OM, etc. "
                "NUNCA use sem antes chamar get_schema_info para conhecer as colunas disponíveis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query SQL SELECT válida. Ex: SELECT contrato, valor_total FROM financeiro LIMIT 20"
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema_info",
            "strict": True,
            "description": (
                "Retorna as tabelas e colunas disponíveis no banco de dados. "
                "Sempre chame antes de usar execute_sql para conhecer os nomes exatos de tabelas e colunas."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart_data",
            "strict": True,
            "description": (
                "Renderiza um gráfico visual interativo inline no chat. "
                "Use SEMPRE que o usuário pedir gráfico, comparação visual, chart ou visualização. "
                "Fluxo obrigatório: 1) get_schema_info → 2) execute_sql → 3) generate_chart_data. "
                "chart_type: 'bar' para comparações entre categorias, "
                "'area' para evolução temporal (séries mensais/semanais), "
                "'pie' para distribuição proporcional (% por categoria)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": ["area", "bar", "pie"],
                        "description": "Tipo do gráfico.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Título descritivo.",
                    },
                    "data": {
                        "type": "array",
                        "description": "Pontos do gráfico.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "number"},
                            },
                            "required": ["name", "value"],
                            "additionalProperties": False,
                        },
                    },
                    "value_prefix": {
                        "type": "string",
                        "description": "Prefixo do tooltip: 'R$', '%', ou ''.",
                    },
                },
                "required": ["chart_type", "title", "data", "value_prefix"],
                "additionalProperties": False,
            },
        },
    },
    # ── Document search tool ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "strict": True,
            "description": (
                "Busca por termos ou cláusulas em documentos anexados à linha do tempo de um contrato. "
                "Use quando o usuário perguntar sobre cláusulas contratuais, multas, prazos, garantias, "
                "rescisão, ou qualquer conteúdo de documentos (contratos, atas, notas técnicas). "
                "Retorna trechos relevantes dos documentos encontrados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo ou frase a buscar. Ex: 'multa por atraso', 'garantia', 'rescisão'."
                    },
                    "contrato": {
                        "type": "string",
                        "description": "Código do contrato. Use '' para buscar em todos."
                    }
                },
                "required": ["query", "contrato"],
                "additionalProperties": False,
            },
        },
    },
    # ── Navigation tool (immediate, no confirmation needed) ───────────────────
    {
        "type": "function",
        "function": {
            "name": "navigate_to_page",
            "strict": True,
            "description": (
                "Navega imediatamente para uma página do dashboard. "
                "Use quando o usuário disser 'me leva para', 'abre', 'vai para', 'quero ver', etc. "
                "Páginas disponíveis: visao-geral, obras, projetos, financeiro, om, analytics, "
                "previsoes, relatorios, chat-ia, reembolso, reembolso-dash, rdo-form, rdo-historico, rdo-dashboard, "
                "admin/editar_dados, alertas, logs-auditoria, admin/usuarios, admin/observabilidade."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "description": "Slug da página sem barra inicial. Ex: 'obras', 'financeiro', 'admin/usuarios'.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Confirmação curta para o usuário. Ex: 'Abrindo painel de obras...'",
                    },
                },
                "required": ["page", "reason"],
                "additionalProperties": False,
            },
        },
    },
    # ── Form filler tools (immediate, no confirmation) ───────────────────────
    {
        "type": "function",
        "function": {
            "name": "fill_rdo_form",
            "strict": True,
            "description": (
                "Navega para o formulário de RDO e pré-preenche os campos com os valores extraídos da fala. "
                "Use quando o usuário disser 'preenche o RDO', 'criar RDO de hoje', 'registra o diário de obra', etc. "
                "Todos os campos são opcionais — preencha apenas o que o usuário mencionou. "
                "clima: 'Ensolarado', 'Parcialmente Nublado', 'Nublado', 'Chuvoso', 'Chuvoso Forte', 'Nevando'. "
                "turno: 'Diurno', 'Noturno', 'Integral'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string", "description": "Código do contrato. Ex: '001-2025'. Use '' se não informado."},
                    "data": {"type": "string", "description": "Data no formato YYYY-MM-DD. Use hoje se o usuário disser 'hoje'. Use '' se não informado."},
                    "clima": {"type": "string", "description": "Condição climática. Use '' se não informado."},
                    "turno": {"type": "string", "description": "Turno de trabalho. Use '' se não informado."},
                    "observacoes": {"type": "string", "description": "Observações gerais ou atividades descritas. Use '' se não informado."},
                    "orientacao": {"type": "string", "description": "Orientações ou instruções do dia. Use '' se não informado."},
                    "atividade_descricao": {"type": "string", "description": "Descrição de uma atividade a adicionar. Use '' se não informado."},
                    "reason": {"type": "string", "description": "Confirmação curta para o usuário. Ex: 'Abrindo formulário RDO com os dados informados...'"},
                },
                "required": ["contrato", "data", "clima", "turno", "observacoes", "orientacao", "atividade_descricao", "reason"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_reembolso_form",
            "strict": True,
            "description": (
                "Navega para o formulário de reembolso de combustível e pré-preenche os campos. "
                "Use quando o usuário disser 'preenche o reembolso', 'registra reembolso de combustível', etc. "
                "Todos os campos são opcionais — preencha apenas o que foi mencionado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {"type": "string", "description": "Código do contrato. Use '' se não informado."},
                    "data": {"type": "string", "description": "Data no formato YYYY-MM-DD. Use '' se não informado."},
                    "km_rodado": {"type": "string", "description": "Km rodado. Ex: '120'. Use '' se não informado."},
                    "valor_litro": {"type": "string", "description": "Valor do litro em reais. Ex: '5.89'. Use '' se não informado."},
                    "litros": {"type": "string", "description": "Litros abastecidos. Ex: '40'. Use '' se não informado."},
                    "reason": {"type": "string", "description": "Confirmação curta para o usuário."},
                },
                "required": ["contrato", "data", "km_rodado", "valor_litro", "litros", "reason"],
                "additionalProperties": False,
            },
        },
    },
    # ── Admin write tools (HITL-gated) ───────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "propose_change_own_password",
            "strict": True,
            "description": (
                "Propõe alterar a senha do usuário ATUALMENTE LOGADO. "
                "Use SEMPRE que o usuário disser 'troca minha senha', 'muda minha senha', 'alterar senha', etc. "
                "FLUXO OBRIGATÓRIO: se o usuário NÃO forneceu a nova senha na mensagem, PERGUNTE 'Qual será a nova senha?' "
                "antes de chamar esta tool. Só chame quando tiver a nova senha confirmada. "
                "O campo logged_user DEVE ser preenchido com o username do usuário logado (fornecido no contexto). "
                "NÃO use propose_update_record para senhas — use ESTE tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "logged_user": {"type": "string", "description": "Username do usuário logado (do contexto do sistema)."},
                    "new_password": {"type": "string", "description": "Nova senha desejada — NUNCA chame com string vazia. Peça ao usuário se não souber."},
                    "summary": {"type": "string", "description": "Resumo da ação para o admin confirmar."},
                },
                "required": ["logged_user", "new_password", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_change_user_password",
            "strict": True,
            "description": (
                "Propõe alterar a senha de OUTRO usuário (não o logado). "
                "Use quando o admin disser 'troca a senha do João', 'reseta a senha de renato', etc. "
                "Para a PRÓPRIA senha, use propose_change_own_password."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_user": {"type": "string", "description": "Username do usuário alvo."},
                    "new_password": {"type": "string", "description": "Nova senha."},
                    "summary": {"type": "string", "description": "Resumo da ação para confirmação."},
                },
                "required": ["target_user", "new_password", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_alert",
            "strict": True,
            "description": (
                "Propõe a criação de um alerta personalizado no sistema. "
                "Use quando o usuário disser 'cria um alerta', 'me avisa quando', 'quero notificação de prazo', "
                "'me avise quando RDO não for enviado', 'alerta de saldo baixo', etc. "
                "Os alertas são salvos na tabela custom_alerts e executados pelo scheduler diário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alert_name": {
                        "type": "string",
                        "description": "Nome curto e descritivo do alerta. Ex: 'RDO ausente - Contrato 001'.",
                    },
                    "alert_type": {
                        "type": "string",
                        "description": "Tipo: 'rdo_ausente' (RDO não enviado), 'prazo_contrato' (contrato vence), 'medicao_pendente' (medição não realizada), 'saldo_baixo' (saldo orçamentário crítico), 'custom' (condição livre).",
                    },
                    "contrato": {
                        "type": "string",
                        "description": "Código do contrato monitorado, ou 'todos' para todos os contratos.",
                    },
                    "condition_field": {
                        "type": "string",
                        "description": "Campo do banco a monitorar. Ex: 'data_entrega', 'saldo_percentual', 'ultima_medicao'. Use '' para alertas por tipo.",
                    },
                    "condition_op": {
                        "type": "string",
                        "description": "Operador: '=' (igual), '<' (menor), '>' (maior), 'missing' (ausente/não enviado), 'overdue' (vencido/atrasado).",
                    },
                    "condition_value": {
                        "type": "string",
                        "description": "Valor limiar ou referência. Ex: '7' (dias), '10' (percentual), '' para 'missing'/'overdue'.",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "Frequência: 'daily' (uma vez por dia), 'hourly' (a cada hora), 'on_event' (ao detectar o evento).",
                    },
                    "notify_emails": {
                        "type": "string",
                        "description": "E-mails separados por vírgula para notificação. Use '' para apenas painel.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição completa do alerta em português para o usuário.",
                    },
                    "summary": {"type": "string", "description": "Resumo de 1 frase para confirmação HITL."},
                },
                "required": ["alert_name", "alert_type", "contrato", "condition_field", "condition_op",
                             "condition_value", "schedule", "notify_emails", "description", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_send_document",
            "strict": True,
            "description": (
                "Propõe o envio de um documento (RDO, relatório) para um usuário via e-mail e/ou WhatsApp. "
                "Use quando o usuário disser 'envie o RDO de ontem para renato', 'manda o relatório do contrato X para fulano', etc. "
                "Antes de chamar, use execute_sql para buscar o documento e o contato do destinatário na tabela login."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "description": "Tipo: 'rdo' ou 'relatorio'.",
                    },
                    "document_id": {
                        "type": "string",
                        "description": "ID do documento no banco (uuid ou identificador único).",
                    },
                    "document_label": {
                        "type": "string",
                        "description": "Descrição legível. Ex: 'RDO Contrato 001 - 19/03/2026'.",
                    },
                    "document_url": {
                        "type": "string",
                        "description": "URL pública do PDF do documento.",
                    },
                    "recipient_username": {
                        "type": "string",
                        "description": "Username do destinatário (tabela login).",
                    },
                    "recipient_email": {
                        "type": "string",
                        "description": "E-mail do destinatário. Use '' se não disponível.",
                    },
                    "recipient_whatsapp": {
                        "type": "string",
                        "description": "Número WhatsApp do destinatário com DDI. Ex: '+5571999998888'. Use '' se não disponível.",
                    },
                    "channels": {
                        "type": "string",
                        "description": "Canais separados por vírgula: 'email', 'whatsapp', ou 'email,whatsapp'.",
                    },
                    "message": {
                        "type": "string",
                        "description": "Mensagem personalizada opcional a incluir no envio.",
                    },
                    "summary": {"type": "string", "description": "Resumo de 1 frase para confirmação HITL."},
                },
                "required": ["document_type", "document_id", "document_label", "document_url",
                             "recipient_username", "recipient_email", "recipient_whatsapp",
                             "channels", "message", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_user",
            "strict": True,
            "description": (
                "Propõe a criação de um novo usuário. "
                "IMPORTANTE: este tool NÃO executa imediatamente — retorna uma proposta que o admin deve CONFIRMAR. "
                "Use quando o admin pedir para criar um usuário novo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Nome de login do usuário (sem espaços, lowercase)."},
                    "password": {"type": "string", "description": "Senha inicial do usuário."},
                    "user_role": {"type": "string", "description": "Papel do usuário: Administrador, Engenheiro, Gestão-Mobile, Mestre de Obras, etc."},
                    "project": {"type": "string", "description": "Contrato/Projeto associado ao usuário, ou 'Todos' para acesso geral."},
                    "summary": {"type": "string", "description": "Resumo em português da ação proposta para mostrar ao admin."},
                },
                "required": ["username", "password", "user_role", "project", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_record",
            "strict": True,
            "description": (
                "Propõe a atualização de um registro existente no banco de dados. "
                "IMPORTANTE: este tool NÃO executa imediatamente — retorna uma proposta que o admin deve CONFIRMAR. "
                "Use quando o admin pedir para alterar um dado específico (ex: atualizar status de uma obra, "
                "corrigir um valor de contrato, etc.). "
                "Passe as colunas e novos valores como lista de pares: [{\"column\": \"status\", \"value\": \"Concluído\"}]."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nome da tabela a ser atualizada."},
                    "filter_column": {"type": "string", "description": "Coluna usada como filtro (ex: 'id', 'contrato')."},
                    "filter_value": {"type": "string", "description": "Valor do filtro."},
                    "fields": {
                        "type": "array",
                        "description": "Lista de pares coluna/valor a atualizar.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string", "description": "Nome da coluna."},
                                "value": {"type": "string", "description": "Novo valor (como string)."},
                            },
                            "required": ["column", "value"],
                            "additionalProperties": False,
                        },
                    },
                    "summary": {"type": "string", "description": "Resumo em português da ação proposta para mostrar ao admin."},
                },
                "required": ["table", "filter_column", "filter_value", "fields", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_record",
            "strict": True,
            "description": (
                "Propõe a criação de um NOVO registro em uma tabela do banco de dados. "
                "IMPORTANTE: NÃO executa imediatamente — retorna uma proposta para o admin CONFIRMAR via HITL. "
                "Use quando o admin pedir 'adicionar um contrato', 'criar novo projeto', 'cadastrar uma obra', "
                "'incluir nova medição', 'adicionar funcionário', etc. "
                "Tabelas disponíveis: contratos, projetos, obras, financeiro, om. "
                "FLUXO CORRETO para criar via voz: o usuário pode fornecer campos em múltiplas falas — "
                "acumule os campos mencionados e só chame este tool quando tiver informação suficiente "
                "(pelo menos o campo principal: contrato, nome, ou código). "
                "Use execute_sql + get_schema_info ANTES para conhecer as colunas exatas da tabela alvo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Nome da tabela onde criar o registro. Ex: 'contratos', 'projetos', 'obras'.",
                    },
                    "fields": {
                        "type": "array",
                        "description": "Lista de pares coluna/valor para o novo registro.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string", "description": "Nome exato da coluna na tabela."},
                                "value": {"type": "string", "description": "Valor para a coluna (sempre como string)."},
                            },
                            "required": ["column", "value"],
                            "additionalProperties": False,
                        },
                    },
                    "summary": {
                        "type": "string",
                        "description": "Resumo em 1 frase para confirmação HITL. Ex: 'Criar contrato 005-2026 - Obra Residencial Norte'.",
                    },
                },
                "required": ["table", "fields", "summary"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_users",
            "strict": True,
            "description": (
                "Lista os usuários cadastrados no sistema para encontrar emails por nome. "
                "Use ANTES de propose_generate_report quando o usuário mencionar um destinatário por nome "
                "(ex: 'envie para Renato', 'manda para o Gustavo'). "
                "Retorna username, user_role e projeto de cada usuário — sem senhas."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_generate_report",
            "strict": True,
            "description": (
                "Propõe a geração de um relatório executivo para um contrato específico. "
                "Use quando o usuário pedir 'gere um relatório', 'crie um relatório do contrato X', "
                "'relatório semanal de Y', 'manda relatório para Z', etc. "
                "IMPORTANTE: este tool NÃO executa imediatamente — retorna uma proposta HITL para confirmação. "
                "FLUXO: 1) execute_sql para buscar contratos disponíveis, "
                "2) list_users se o usuário mencionou destinatário por nome, "
                "3) propose_generate_report com os dados coletados. "
                "Tipos disponíveis: 'ia_mcp' (completo, consulta banco em tempo real), "
                "'estatico' (estruturado com dados atuais), 'ia_snapshot' (IA com snapshot)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contrato": {
                        "type": "string",
                        "description": "Código do contrato. Ex: 'BOM-029'. Use o código exato do banco.",
                    },
                    "tipo": {
                        "type": "string",
                        "description": "Tipo de relatório: 'ia_mcp' (recomendado), 'estatico', 'ia_snapshot'.",
                        "enum": ["ia_mcp", "estatico", "ia_snapshot"],
                    },
                    "abordagem": {
                        "type": "string",
                        "description": "Abordagem da análise IA: 'estrategica', 'analitica', 'descritiva', 'operacional', 'custom'.",
                        "enum": ["estrategica", "analitica", "descritiva", "operacional", "custom"],
                    },
                    "periodo": {
                        "type": "string",
                        "description": "Período desejado: 'hoje', 'semana', 'mes', 'total', ou datas 'YYYY-MM-DD:YYYY-MM-DD'.",
                    },
                    "recipient_emails": {
                        "type": "string",
                        "description": "Emails dos destinatários separados por vírgula. Use '' se não houver destinatário.",
                    },
                    "recipient_names": {
                        "type": "string",
                        "description": "Nomes dos destinatários separados por vírgula (para personalização).",
                    },
                    "instrucao_adicional": {
                        "type": "string",
                        "description": "Instrução adicional para personalizar o relatório. Ex: 'foque nos desvios financeiros'.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Resumo em 1 frase para o card de confirmação HITL.",
                    },
                },
                "required": ["contrato", "tipo", "abordagem", "periodo", "recipient_emails",
                             "recipient_names", "instrucao_adicional", "summary"],
                "additionalProperties": False,
            },
        },
    },
]


_BLOCKED_KEYWORDS = {"drop", "delete", "update", "insert", "truncate", "alter", "grant", "revoke", "create"}


def execute_admin_tool(name: str, args: dict) -> tuple[str, dict | None]:
    """
    Execute an admin tool.

    Returns:
        (result_str, hitl_proposal | None)
        If hitl_proposal is not None, execution is paused pending user confirmation.
    """
    try:
        if name in ("execute_sql", "get_schema_info", "generate_chart_data", "search_documents"):
            from bomtempo.core.ai_tools import execute_tool as _exec
            return _exec(name, args), None

        elif name == "navigate_to_page":
            page = args.get("page", "").strip("/")
            reason = args.get("reason", f"Navegando para /{page}...")
            proposal = {
                "__hitl__": False,
                "__navigate__": True,
                "page": page,
                "reason": reason,
            }
            return json.dumps(proposal), proposal

        elif name == "fill_rdo_form":
            fields = {k: v for k, v in args.items() if k != "reason" and v}
            reason = args.get("reason", "Abrindo formulário RDO...")
            proposal = {
                "__hitl__": False,
                "__navigate__": True,
                "__prefill__": "rdo",
                "page": "rdo-form",
                "reason": reason,
                "fields": fields,
            }
            return json.dumps(proposal), proposal

        elif name == "fill_reembolso_form":
            # Remove contrato — it's bound to the logged user in GlobalState
            fields = {k: v for k, v in args.items() if k not in ("reason", "contrato") and v}
            reason = args.get("reason", "Abrindo formulário de reembolso...")
            proposal = {
                "__hitl__": False,
                "__navigate__": True,
                "__prefill__": "reembolso",
                "page": "reembolso",
                "reason": reason,
                "fields": fields,
            }
            return json.dumps(proposal), proposal

        elif name == "propose_change_own_password":
            logged_user = args.get("logged_user", "")
            new_password = args.get("new_password", "")
            if not new_password:
                return json.dumps({"error": "Nova senha não fornecida. Peça ao usuário a nova senha antes de chamar esta ferramenta."}), None
            masked = "*" * min(len(new_password), 8)
            proposal = {
                "__hitl__": True,
                "action": "change_own_password",
                "summary": args.get("summary", f"Alterar senha de {logged_user}"),
                "data": {
                    "logged_user": logged_user,
                    "new_password": new_password,
                },
                "preview_lines": [
                    f"Usuário: {logged_user}",
                    f"Nova senha: {masked} ({len(new_password)} caracteres)",
                    "Confirme para aplicar a alteração no banco.",
                ],
            }
            return json.dumps(proposal), proposal

        elif name == "propose_create_user":
            # Return HITL proposal — caller shows confirmation UI
            proposal = {
                "__hitl__": True,
                "action": "create_user",
                "summary": args.get("summary", "Criar novo usuário"),
                "data": {
                    "username": args.get("username", ""),
                    "password": args.get("password", ""),
                    "user_role": args.get("user_role", ""),
                    "project": args.get("project", "Todos"),
                },
                "preview_lines": [
                    f"👤 Usuário: **{args.get('username', '')}**",
                    f"🔑 Senha: `{args.get('password', '')}`",
                    f"🏷️ Papel: {args.get('user_role', '')}",
                    f"📋 Projeto: {args.get('project', 'Todos')}",
                ],
            }
            return json.dumps(proposal), proposal

        elif name == "propose_change_user_password":
            target = args.get("target_user", "")
            new_pw = args.get("new_password", "")
            proposal = {
                "__hitl__": True,
                "action": "change_user_password",
                "summary": args.get("summary", f"Alterar senha de {target}"),
                "data": {"target_user": target, "new_password": new_pw},
                "preview_lines": [
                    f"👤 Usuário alvo: {target}",
                    f"🔑 Nova senha: {new_pw}",
                ],
            }
            return json.dumps(proposal), proposal

        elif name == "propose_create_alert":
            contrato = args.get("contrato", "todos")
            notify_emails = args.get("notify_emails", "")
            channels = ["in-app"]
            notify_list = [e.strip() for e in notify_emails.split(",") if e.strip()]
            if notify_list:
                channels.append("email")
            proposal = {
                "__hitl__": True,
                "action": "create_alert",
                "summary": args.get("summary", "Criar alerta personalizado"),
                "data": {
                    "alert_name": args.get("alert_name", "Alerta personalizado"),
                    "alert_type": args.get("alert_type", "custom"),
                    "contrato": contrato,
                    "condition_field": args.get("condition_field", ""),
                    "condition_op": args.get("condition_op", "missing"),
                    "condition_value": args.get("condition_value", ""),
                    "schedule": args.get("schedule", "daily"),
                    "notify_channels": channels,
                    "notify_emails": notify_list,
                    "notify_whatsapp": [],
                    "description": args.get("description", ""),
                },
                "preview_lines": [
                    f"🔔 Nome: {args.get('alert_name', '')}",
                    f"📋 Contrato: {contrato}",
                    f"⚡ Tipo: {args.get('alert_type', '')} | {args.get('condition_op', '')}",
                    f"📝 {args.get('description', '')}",
                    f"📧 Notificar: {notify_emails or 'apenas painel'}",
                    f"⏱ Frequência: {args.get('schedule', 'daily')}",
                ],
            }
            return json.dumps(proposal), proposal

        elif name == "propose_send_document":
            channels_raw = args.get("channels", "email")
            recipient = args.get("recipient_username", "")
            doc_label = args.get("document_label", "")
            proposal = {
                "__hitl__": True,
                "action": "send_document",
                "summary": args.get("summary", f"Enviar {doc_label} para {recipient}"),
                "data": {
                    "document_type": args.get("document_type", "rdo"),
                    "document_id": args.get("document_id", ""),
                    "document_label": doc_label,
                    "document_url": args.get("document_url", ""),
                    "recipient_username": recipient,
                    "recipient_email": args.get("recipient_email", ""),
                    "recipient_whatsapp": args.get("recipient_whatsapp", ""),
                    "channels": channels_raw,
                    "message": args.get("message", ""),
                },
                "preview_lines": [
                    f"📄 Documento: {doc_label}",
                    f"👤 Destinatário: {recipient}",
                    f"📬 Canais: {channels_raw}",
                    f"📧 E-mail: {args.get('recipient_email', 'não cadastrado')}",
                    f"📱 WhatsApp: {args.get('recipient_whatsapp', 'não cadastrado')}",
                ],
            }
            return json.dumps(proposal), proposal

        elif name == "propose_update_record":
            fields = args.get("fields", [])
            # Convert list of {column, value} to dict for execution
            updates = {f["column"]: f["value"] for f in fields}
            preview = [f"📋 Tabela: **{args.get('table', '')}**",
                       f"🔍 Filtro: `{args.get('filter_column', '')} = {args.get('filter_value', '')}`"]
            for item in fields:
                preview.append(f"✏️ {item['column']}: `{item['value']}`")
            proposal = {
                "__hitl__": True,
                "action": "update_record",
                "summary": args.get("summary", "Atualizar registro"),
                "data": {
                    "table": args.get("table", ""),
                    "filter_column": args.get("filter_column", ""),
                    "filter_value": args.get("filter_value", ""),
                    "updates": updates,
                },
                "preview_lines": preview,
            }
            return json.dumps(proposal), proposal

        elif name == "propose_create_record":
            table = args.get("table", "")
            fields = args.get("fields", [])
            record = {f["column"]: f["value"] for f in fields}
            preview = [f"📋 Tabela: **{table}**", f"➕ Novo registro:"]
            for item in fields:
                preview.append(f"  • {item['column']}: `{item['value']}`")
            proposal = {
                "__hitl__": True,
                "action": "create_record",
                "summary": args.get("summary", f"Criar registro em {table}"),
                "data": {
                    "table": table,
                    "record": record,
                },
                "preview_lines": preview,
            }
            return json.dumps(proposal), proposal

        elif name == "list_users":
            # Lista usuários sem senhas — para o Action AI encontrar destinatários por nome
            try:
                from bomtempo.core.supabase_client import sb_select
                rows = sb_select("login", filters={}, limit=50) or []
                users = []
                for r in rows:
                    users.append({
                        "username": r.get("user") or r.get("username", ""),
                        "user_role": r.get("user_role", ""),
                        "project": r.get("project", ""),
                    })
                return json.dumps({"users": users, "count": len(users)}), None
            except Exception as e:
                return f"Erro ao listar usuários: {str(e)}", None

        elif name == "propose_generate_report":
            contrato = args.get("contrato", "")
            tipo = args.get("tipo", "ia_mcp")
            abordagem = args.get("abordagem", "estrategica")
            periodo = args.get("periodo", "total")
            recipient_emails_str = args.get("recipient_emails", "")
            recipient_names_str = args.get("recipient_names", "")
            instrucao = args.get("instrucao_adicional", "")

            # Monta lista de destinatários
            emails = [e.strip() for e in recipient_emails_str.split(",") if e.strip()]
            names = [n.strip() for n in recipient_names_str.split(",") if n.strip()]
            recipients = [
                {"email": e, "name": names[i] if i < len(names) else e}
                for i, e in enumerate(emails)
            ]

            # Labels legíveis
            tipo_labels = {"ia_mcp": "IA Enterprise (banco em tempo real)", "estatico": "Estático", "ia_snapshot": "IA (snapshot)"}
            abordagem_labels = {"estrategica": "Estratégica", "analitica": "Analítica", "descritiva": "Auditoria Técnica", "operacional": "Operacional de Campo", "custom": "Personalizado"}
            tipo_label = tipo_labels.get(tipo, tipo)
            ab_label = abordagem_labels.get(abordagem, abordagem)

            preview = [
                f"📋 Contrato: **{contrato}**",
                f"📄 Tipo: {tipo_label}",
                f"🎯 Abordagem: {ab_label}",
                f"📅 Período: {periodo}",
            ]
            if recipients:
                preview.append(f"📧 Destinatários: {', '.join(r['name'] for r in recipients)}")
            if instrucao:
                preview.append(f"💬 Instrução: {instrucao[:80]}")

            proposal = {
                "__hitl__": True,
                "action": "generate_report",
                "summary": args.get("summary", f"Gerar relatório {ab_label} do contrato {contrato}"),
                "data": {
                    "contrato": contrato,
                    "tipo": tipo,
                    "abordagem": abordagem,
                    "periodo": periodo,
                    "recipients": recipients,
                    "instrucao_adicional": instrucao,
                },
                "preview_lines": preview,
            }
            return json.dumps(proposal), proposal

        return f"Ferramenta {name} não encontrada.", None
    except Exception as e:
        logger.error(f"Error in admin tool {name}: {e}")
        return f"Erro ao executar {name}: {str(e)}", None


def _execute_send_document(data: dict) -> str:
    """Send a document (RDO/report) to a user via email and/or WhatsApp."""
    doc_label = data.get("document_label", "Documento")
    doc_url = data.get("document_url", "")
    channels_raw = data.get("channels", "email")
    channels = [c.strip() for c in channels_raw.split(",")]
    message_extra = data.get("message", "")
    sent = []
    errors = []

    if "email" in channels:
        email_addr = data.get("recipient_email", "")
        if not email_addr:
            errors.append("e-mail não cadastrado para este usuário")
        else:
            try:
                from bomtempo.core.email_service import EmailService
                ok = EmailService.send_document_email(
                    recipients=[email_addr],
                    doc_label=doc_label,
                    doc_url=doc_url,
                    sender_username=data.get("_sender_username", "Action AI"),
                    message_extra=message_extra,
                )
                if ok:
                    sent.append(f"e-mail para {email_addr}")
                else:
                    errors.append("falha no envio do e-mail (verifique SMTP)")
            except Exception as e:
                logger.error(f"send_document email error: {e}")
                errors.append(f"erro ao enviar e-mail: {str(e)[:80]}")

    if "whatsapp" in channels:
        wa_number = data.get("recipient_whatsapp", "")
        if not wa_number:
            errors.append("WhatsApp não cadastrado para este usuário")
        else:
            try:
                _send_whatsapp(wa_number, doc_label, doc_url, message_extra)
                sent.append(f"WhatsApp para {wa_number}")
            except Exception as e:
                logger.error(f"send_document whatsapp error: {e}")
                errors.append(f"erro ao enviar WhatsApp: {str(e)[:80]}")

    parts = []
    if sent:
        parts.append(f"✅ Enviado via: {', '.join(sent)}.")
    if errors:
        parts.append(f"⚠️ Avisos: {'; '.join(errors)}.")
    return " ".join(parts) if parts else "❌ Nenhum canal disponível para envio."


def _send_whatsapp(number: str, doc_label: str, doc_url: str, message: str = "") -> None:
    """
    Send WhatsApp message via Twilio (if configured) or log the intent.
    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM in env.
    """
    import os
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    _placeholder = ("your_", "placeholder", "xxx", "test", "changeme")
    _is_placeholder = any(p in account_sid.lower() or p in auth_token.lower() for p in _placeholder)
    if not account_sid or not auth_token or _is_placeholder:
        logger.info(f"[WhatsApp stub] Would send '{doc_label}' to {number}. Configure Twilio env vars to enable.")
        return

    try:
        from twilio.rest import Client  # type: ignore
        client = Client(account_sid, auth_token)
        body = f"*{doc_label}*\n"
        if message:
            body += f"{message}\n"
        body += f"PDF: {doc_url}"
        client.messages.create(
            body=body,
            from_=from_number,
            to=f"whatsapp:{number}",
        )
        logger.info(f"WhatsApp sent to {number}")
    except ImportError:
        logger.warning("twilio package not installed — WhatsApp not sent.")
    except Exception as e:
        raise RuntimeError(str(e)) from e


def execute_confirmed_action(action: str, data: dict) -> str:
    """Execute a HITL-confirmed admin action."""
    try:
        if action == "change_user_password":
            target = data.get("target_user", "")
            new_pw = data.get("new_password", "")
            if not target or not new_pw:
                return "❌ Dados insuficientes."
            existing = sb_select("login", filters={"username": target}, limit=1)
            if not existing:
                return f"❌ Usuário '{target}' não encontrado."
            sb_update("login", {"username": target}, {"password": new_pw})
            return f"✅ Senha de **{target}** alterada com sucesso."

        elif action == "create_alert":
            from bomtempo.core.supabase_client import sb_insert
            result = sb_insert("custom_alerts", {
                "created_by": data.get("_created_by", "action_ai"),
                "alert_name": data.get("alert_name", "Alerta"),
                "alert_type": data.get("alert_type", "custom"),
                "contrato": data.get("contrato") if data.get("contrato") != "todos" else None,
                "condition_field": data.get("condition_field") or None,
                "condition_op": data.get("condition_op", "missing"),
                "condition_value": data.get("condition_value") or None,
                "schedule": data.get("schedule", "daily"),
                "notify_channels": data.get("notify_channels", ["in-app"]),
                "notify_emails": data.get("notify_emails", []),
                "notify_whatsapp": data.get("notify_whatsapp", []),
                "description": data.get("description", ""),
                "is_active": True,
            })
            if result:
                return f"✅ Alerta **{data.get('alert_name', '')}** criado com sucesso."
            return "❌ Falha ao criar alerta. Verifique se a tabela custom_alerts existe no banco."

        elif action == "send_document":
            return _execute_send_document(data)

        elif action == "create_user":
            result = sb_insert("login", {
                "username": data["username"],
                "password": data["password"],
                "user_role": data["user_role"],
                "project": data.get("project", "Todos"),
                "client_id": data.get("_client_id") or None,
            })
            if result:
                return f"✅ Usuário **{data['username']}** criado com sucesso."
            return "❌ Falha ao criar usuário. Verifique se o nome já existe."

        elif action == "change_own_password":
            # Dedicated safe path — uses current_user from session, not AI guess
            logged_user = data.get("logged_user", "")
            new_password = data.get("new_password", "")
            if not logged_user or not new_password:
                return "❌ Dados insuficientes para alterar senha."
            rows_before = sb_select("login", filters={"username": logged_user}, limit=1)
            if not rows_before:
                return f"❌ Usuário '{logged_user}' não encontrado no banco."
            sb_update("login", {"username": logged_user}, {"password": new_password})
            return f"✅ Senha de **{logged_user}** alterada com sucesso."

        elif action == "update_record":
            table = data["table"]
            filter_col = data["filter_column"]
            filter_val = data["filter_value"]
            updates = data["updates"]

            # Safety: block dangerous tables (login allowed for password updates via HITL)
            PROTECTED = {"roles", "llm_observability", "system_logs", "alert_history"}
            if table in PROTECTED:
                return f"❌ Tabela `{table}` é protegida. Não é possível atualizar via Action AI."

            # For login table updates: verify the username exists first
            if table == "login" and filter_col == "username":
                existing = sb_select("login", filters={"username": filter_val}, limit=1)
                if not existing:
                    return f"❌ Usuário '{filter_val}' não encontrado na tabela login."

            sb_update(table, {filter_col: filter_val}, updates)
            return f"✅ Registro em `{table}` atualizado com sucesso."

        elif action == "create_record":
            table = data.get("table", "")
            record = data.get("record", {})

            # Safety: only allow writable business tables
            ALLOWED_TABLES = {"contratos", "hub_atividades", "fin_custos", "om", "login", "custom_alerts", "email_sender"}
            if table not in ALLOWED_TABLES:
                return f"❌ Tabela `{table}` não permitida para criação via Action AI. Tabelas disponíveis: {', '.join(sorted(ALLOWED_TABLES))}."
            if not record:
                return "❌ Nenhum campo fornecido para criar o registro."

            result = sb_insert(table, record)
            if result:
                # Invalidate data cache so dashboard reflects new record immediately
                try:
                    from bomtempo.core.data_loader import DataLoader
                    DataLoader.invalidate_cache()
                except Exception:
                    pass
                return f"✅ Registro criado em `{table}` com sucesso."
            return f"❌ Falha ao criar registro em `{table}`. Verifique se os campos são válidos."

        elif action == "generate_report":
            contrato = data.get("contrato", "")
            tipo = data.get("tipo", "ia_mcp")
            abordagem = data.get("abordagem", "estrategica")
            periodo = data.get("periodo", "total")
            recipients = data.get("recipients", [])
            instrucao = data.get("instrucao_adicional", "")
            client_id = data.get("_client_id", "")
            created_by = data.get("_created_by", "Action AI")

            if not contrato:
                return "❌ Contrato não especificado. Informe o código do contrato para gerar o relatório."

            try:
                from bomtempo.core.report_service import ReportService
                import unicodedata, threading
                from datetime import datetime as _dt

                # Para relatório ia_mcp, usamos o prompt enterprise com acesso ao banco
                if tipo == "ia_mcp":
                    # Determina período
                    periodo_inicio = ""
                    periodo_fim = ""
                    if periodo == "hoje":
                        d = _dt.now().strftime("%Y-%m-%d")
                        periodo_inicio = periodo_fim = d
                    elif periodo == "semana":
                        from datetime import timedelta
                        hoje = _dt.now()
                        periodo_inicio = (hoje - timedelta(days=7)).strftime("%Y-%m-%d")
                        periodo_fim = hoje.strftime("%Y-%m-%d")
                    elif periodo == "mes":
                        from datetime import timedelta
                        hoje = _dt.now()
                        periodo_inicio = (hoje - timedelta(days=30)).strftime("%Y-%m-%d")
                        periodo_fim = hoje.strftime("%Y-%m-%d")
                    elif ":" in (periodo or ""):
                        parts = periodo.split(":")
                        periodo_inicio = parts[0].strip()
                        periodo_fim = parts[1].strip() if len(parts) > 1 else ""

                    messages = ReportService.build_ai_prompt_with_mcp(
                        approach=abordagem,
                        contrato=contrato,
                        client_id=client_id,
                        periodo_inicio=periodo_inicio,
                        periodo_fim=periodo_fim,
                        custom_instruction=instrucao,
                        gerado_por=created_by,
                    )

                    # Chama a IA de forma síncrona (estamos em run_in_executor)
                    from bomtempo.core.ai_client import ai_client
                    ai_text = ai_client.query(messages, max_tokens=4000) or ""

                    if not ai_text:
                        return "❌ A IA não retornou conteúdo. Tente novamente."

                    data_for_html = {
                        "contrato": contrato, "cliente": "—",
                        "gerado_por": created_by, "fmt": {}, "obra": {}, "disciplinas": [],
                    }
                    html = ReportService.build_ai_html(ai_text, data_for_html, abordagem)
                else:
                    # Relatório estático — usa dados disponíveis
                    data_for_html = {
                        "contrato": contrato, "cliente": "—",
                        "gerado_por": created_by, "fmt": {}, "obra": {}, "disciplinas": [],
                    }
                    html = ReportService.build_static_html(data_for_html)

                # Gera PDF
                ts = _dt.now().strftime("%Y%m%d_%H%M%S")
                _raw = contrato.replace(" ", "_").replace("/", "-")[:30]
                safe_name = unicodedata.normalize("NFKD", _raw).encode("ascii", "ignore").decode("ascii")
                filename = f"relatorio_ai_{safe_name}_{ts}.pdf"
                pdf_path, pdf_url = ReportService.generate_pdf(html, filename)

                # Salva no banco
                record_report = {
                    "contrato": contrato, "cliente": "—",
                    "tipo": tipo, "abordagem": abordagem,
                    "titulo": f"Relatório {abordagem.title()} — {contrato} (Action AI)",
                    "pdf_path": pdf_path, "pdf_url": pdf_url,
                    "created_by": created_by,
                    "recipients": recipients,
                }
                if client_id:
                    record_report["client_id"] = client_id
                sb_insert("relatorios", record_report)

                # Envia emails em background
                if recipients:
                    def _send():
                        try:
                            from bomtempo.core.email_service import EmailService
                            email_list = [r.get("email") for r in recipients if r.get("email")]
                            if email_list:
                                EmailService.send_document_email(
                                    recipients=email_list,
                                    doc_label=f"Relatório {contrato} — {_dt.now().strftime('%d/%m/%Y')}",
                                    doc_url=pdf_url,
                                    sender_username=created_by,
                                )
                        except Exception as _em:
                            logger.warning(f"send_report email error: {_em}")
                    threading.Thread(target=_send, daemon=True).start()
                    return (
                        f"✅ Relatório **{contrato}** gerado com sucesso!\n"
                        f"📄 [Abrir PDF]({pdf_url})\n"
                        f"📧 Enviando para {len(recipients)} destinatário(s) em background."
                    )
                return (
                    f"✅ Relatório **{contrato}** gerado com sucesso!\n"
                    f"📄 [Abrir PDF]({pdf_url})"
                )
            except Exception as e:
                logger.error(f"generate_report action error: {e}")
                return f"❌ Erro ao gerar relatório: {str(e)[:200]}"

        return "❌ Ação desconhecida."
    except Exception as e:
        logger.error(f"execute_confirmed_action error: {e}")
        return f"❌ Erro ao executar ação: {str(e)}"
