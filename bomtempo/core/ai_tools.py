import json
from bomtempo.core.supabase_client import sb_rpc
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

# --- Tool Definitions for OpenAI API ---

AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "strict": True,
            "description": (
                "Busca por termos ou cláusulas em documentos anexados à linha do tempo de um contrato. "
                "Use quando o usuário perguntar sobre cláusulas contratuais, multas, prazos, garantias, "
                "rescisão, ou qualquer conteúdo de documentos (contratos, atas, notas técnicas). "
                "Retorna trechos relevantes dos documentos encontrados. "
                "Se o usuário não especificar o contrato, use o contrato do contexto atual."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo ou frase a buscar nos documentos. Ex: 'multa por atraso', 'garantia', 'rescisão', 'prazo de entrega'."
                    },
                    "contrato": {
                        "type": "string",
                        "description": "Código do contrato a pesquisar. Ex: 'BOM-029'. Use '' para buscar em todos os contratos disponíveis."
                    }
                },
                "required": ["query", "contrato"],
                "additionalProperties": False,
            },
        },
    },
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
                        "description": "Título descritivo. Ex: 'Faturamento por Contrato — 1º Sem 2025'",
                    },
                    "data": {
                        "type": "array",
                        "description": "Pontos do gráfico. Cada item deve ter 'name' (string) e 'value' (número).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Label do ponto (eixo X ou fatia da pizza).",
                                },
                                "value": {
                                    "type": "number",
                                    "description": "Valor numérico do ponto.",
                                },
                            },
                            "required": ["name", "value"],
                            "additionalProperties": False,
                        },
                    },
                    "value_prefix": {
                        "type": "string",
                        "description": "Prefixo para o tooltip. Use 'R$' para moeda, '%' para percentual, '' para número puro.",
                    },
                },
                "required": ["chart_type", "title", "data", "value_prefix"],
                "additionalProperties": False,
            },
        },
    },
]

# --- Tool Execution Logic ---

import re

# Block mutating commands (word boundaries prevent partial matches like "selectall")
_BLOCKED_CMD_RE = re.compile(
    r"\b(drop|delete|update|insert|truncate|alter|grant|revoke|create)\b",
    re.IGNORECASE,
)

# Tables that must never be accessed via AI SQL — regardless of RPC whitelist
_SENSITIVE_TABLES = re.compile(
    r"\b(login|roles|system_logs|llm_usage|information_schema)\b|pg_\w+",
    re.IGNORECASE,
)


def execute_tool(name: str, args: dict):
    """Executes the tool logic based on the tool name and arguments."""
    try:
        if name == "execute_sql":
            query = args.get("query", "").strip()
            if not query:
                return json.dumps({"error": "Query não fornecida."})

            # Strip SQL comments before checking (bypass prevention)
            clean_query = re.sub(r"--[^\n]*", "", query)
            clean_query = re.sub(r"/\*.*?\*/", "", clean_query, flags=re.DOTALL)

            if _BLOCKED_CMD_RE.search(clean_query):
                return json.dumps({"error": "Operação não permitida. Apenas SELECT é autorizado."})

            if _SENSITIVE_TABLES.search(clean_query):
                return json.dumps({"error": "Acesso a tabelas sensíveis não permitido via IA."})

            logger.info(f"🛠️ Tool: execute_sql → {query[:120]}")
            result = sb_rpc("execute_safe_query", {"query_string": query})
            return json.dumps(result or [])
        
        elif name == "get_schema_info":
            logger.info("🛠️ Tool: get_schema_info")
            result = sb_rpc("get_schema_context")
            return json.dumps(result or [])
            
        elif name == "generate_chart_data":
            chart_type = args.get("chart_type", "bar")
            data = args.get("data", [])
            title = args.get("title", "")
            value_prefix = args.get("value_prefix", "")
            # Retorna JSON com marcador especial que o loop agêntico detecta e injeta na mensagem
            return json.dumps({
                "__chart__": True,
                "chart_type": chart_type,
                "title": title,
                "value_prefix": value_prefix,
                "data": data,
            })

        elif name == "search_documents":
            query_text = args.get("query", "").strip()
            contrato = args.get("contrato", "").strip()
            if not query_text:
                return json.dumps({"error": "Termo de busca não fornecido."})

            logger.info(f"🛠️ Tool: search_documents → query='{query_text[:60]}' contrato='{contrato}'")
            try:
                from bomtempo.core.supabase_client import sb_select

                # Busca documentos na hub_timeline
                filters: dict = {"is_document": True}
                if contrato:
                    filters["contrato"] = contrato
                doc_rows = sb_select("hub_timeline", filters=filters, limit=20) or []

                if not doc_rows:
                    return json.dumps({"resultado": "Nenhum documento encontrado para este contrato."})

                # Importa extractor do global_state (evita duplicar lógica)
                from bomtempo.state.global_state import _extract_document_text

                results = []
                query_lower = query_text.lower()
                query_terms = [t.strip() for t in re.split(r"[\s,;|]+", query_lower) if len(t.strip()) > 2]

                for d in doc_rows:
                    titulo = d.get("titulo", "") or ""
                    descricao = d.get("descricao", "") or ""
                    anexo_url = d.get("anexo_url", "") or ""
                    anexo_nome = d.get("anexo_nome", "") or ""
                    doc_contrato = d.get("contrato", "") or contrato

                    # Quick check: query em título/descrição
                    meta_text = f"{titulo} {descricao}".lower()
                    meta_match = any(term in meta_text for term in query_terms)

                    # Extrai texto do arquivo e busca
                    file_text = ""
                    if anexo_url:
                        file_text = _extract_document_text(anexo_url, anexo_nome, max_chars=15000)

                    file_lower = file_text.lower()
                    file_match = any(term in file_lower for term in query_terms)

                    if not meta_match and not file_match:
                        continue

                    # Extrai trechos relevantes (±300 chars em volta do match)
                    snippets = []
                    if file_text:
                        for term in query_terms:
                            idx = file_lower.find(term)
                            while idx != -1 and len(snippets) < 3:
                                start = max(0, idx - 200)
                                end = min(len(file_text), idx + 300)
                                snippet = file_text[start:end].strip()
                                # Evita duplicatas de snippets muito similares
                                if not any(snippet[:50] in s for s in snippets):
                                    snippets.append(f"...{snippet}...")
                                idx = file_lower.find(term, idx + 1)
                            if len(snippets) >= 3:
                                break

                    results.append({
                        "documento": titulo or anexo_nome,
                        "contrato": doc_contrato,
                        "arquivo": anexo_nome,
                        "trechos_relevantes": snippets if snippets else [f"Termo encontrado no título/descrição: {meta_text[:200]}"],
                    })

                if not results:
                    return json.dumps({
                        "resultado": f"Nenhuma referência a '{query_text}' encontrada nos {len(doc_rows)} documento(s) do contrato.",
                        "documentos_verificados": [d.get("titulo", d.get("anexo_nome", "")) for d in doc_rows],
                    })

                return json.dumps({
                    "total_documentos_verificados": len(doc_rows),
                    "documentos_com_match": len(results),
                    "resultados": results,
                })
            except Exception as e:
                logger.error(f"search_documents error: {e}")
                return json.dumps({"error": f"Erro ao buscar documentos: {str(e)}"})

        return f"Ferramenta {name} não encontrada."
    except Exception as e:
        logger.error(f"Erro ao executar tool {name}: {e}")
        return f"Erro na execução da ferramenta: {str(e)}"
