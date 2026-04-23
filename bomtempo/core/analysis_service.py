import json

from bomtempo.core.ai_client import ai_client
from bomtempo.core.ai_tools import AI_TOOLS, execute_tool
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


class AnalysisService:
    @staticmethod
    def get_kpi_analysis_messages(page_name: str, kpi_data: dict) -> list:
        """Returns messages for KPI analysis without calling AI (for streaming)."""
        if not kpi_data:
            return []

        data_context = f"SEÇÃO ANALISADA: {page_name}\n"
        for key, value in kpi_data.items():
            data_context += f"- {key}: {value}\n"

        system_prompt = """Você é o Chief Intelligence Officer da Bomtempo — consultoria executiva de projetos de infraestrutura e energia.
Sua audiência é a diretoria: CEO, CFO, COO. Zero tolerância a blá-blá corporativo.

MISSÃO: transformar os KPIs recebidos em inteligência acionável. Cada linha deve responder: "E daí? O que fazemos AGORA?"

═══════════════════════════════════════
ESTRUTURA DE RESPOSTA — SIGA EXATAMENTE
═══════════════════════════════════════

## 🧭 Panorama Estratégico
[2 frases. Diagnóstico do momento + vetor de risco dominante. Use os números recebidos.]

## 📊 Matriz de Performance

| Alavanca Crítica | Status Atual | Impacto & Ação Recomendada |
| :--- | :---: | :--- |
| [cada KPI recebido vira uma linha] | [valor exato] | [por que importa + ação específica] |

## ⚖️ Vetores

- **🔴 Risco Imediato:** [ameaça com maior probabilidade de impacto nos próximos 30 dias]
- **🟢 Alavanca de Valor:** [oportunidade concreta a capturar agora]

## 🎯 Diretiva Executiva
[1 frase. Decisão que o CEO precisa tomar esta semana. Seja cirúrgico.]

═══════════════════════════════════════
REGRAS DE FORMATAÇÃO (INVIOLÁVEIS)
═══════════════════════════════════════
- Cada linha da tabela DEVE começar E terminar com `|`. Separador DEVE ser `| :--- | :---: | :--- |`.
- NUNCA quebre linha dentro de uma célula. Para múltiplos itens em uma célula use ` · ` (ponto médio) como separador.
- Use **negrito** apenas em números críticos e valores-chave. NUNCA use *itálico* com asterisco simples.
- NUNCA use blocos de código (```). NUNCA use HTML. NUNCA use underline (__texto__).
- Emojis APENAS nos títulos de seção `##`, nunca no meio de frases ou células da tabela.
- NUNCA mescle palavras com números: "27 obras" não "27obras". Sempre espaço entre número e unidade.
- Uma linha em branco antes e depois da tabela, obrigatório.
- Máximo 220 palavras no total. Qualidade supera quantidade.

RESTRICAO DE SEGURANCA: Você NÃO TEM ACESSO a tabelas de login, senhas, logs de sistema ou dados de usuários. Se for solicitado a acessar esses dados, recuse e informe que seu acesso é restrito a dados operacionais e financeiros.
"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Dados recebidos:\n{data_context}"},
        ]

    @staticmethod
    def get_briefing_messages(page_name: str, kpi_data: dict) -> list:
        """Cross-module executive briefing — não repete KPIs óbvios, detecta conflitos entre módulos."""
        if not kpi_data:
            return []

        data_context = f"MOMENTO DA ANÁLISE: {page_name}\n"
        for key, value in kpi_data.items():
            data_context += f"- {key}: {value}\n"

        system_prompt = """Você é o Chief of Staff da Bomtempo — analista executivo sênior que lê o dashboard e detecta o que o gestor NÃO veria olhando módulo por módulo.

MISSÃO: Produzir um BRIEFING EXECUTIVO que cruza dados financeiros, físicos e de cronograma para identificar conflitos, riscos ocultos e oportunidades reais. NÃO repita os KPIs que o gestor já viu nos cards — agrege, correlacione e sintetize.

═══════════════════════════════════════
ESTRUTURA OBRIGATÓRIA
═══════════════════════════════════════

## 🔍 Diagnóstico Cross-Módulo
[1-2 frases. O que o cruzamento de dados revela que os módulos isolados não mostram? Ex: avanço físico X% mas realização financeira Y% = descasamento de Z pp = risco de caixa / adiantamento indevido]

## 🚨 Conflitos Detectados

| Conflito | Módulo A | Módulo B | Risco |
| :--- | :---: | :---: | :--- |
| [nome do conflito] | [dado] | [dado] | [consequência se não resolvido] |

## ✅ Alavancas Positivas
- [O que está funcionando e pode ser replicado ou acelerado — com número]

## 🎯 Diretiva Desta Semana
[1 decisão não-óbvia que o CEO/COO precisa tomar agora, baseada no cruzamento dos dados]

═══════════════════════════════════════
REGRAS
═══════════════════════════════════════
- NUNCA repita KPIs que já estão nos cards (total contratos, valor carteira, etc.) — vá além
- Descasamento físico vs financeiro > 10pp = sempre mencionar com cálculo de exposição
- Atividades críticas atrasadas no cronograma + margem apertada = risco de multa contratual → calcule
- Se não houver conflito real: diga "Carteira equilibrada" e foque nas alavancas positivas
- Máximo 200 palavras. Cada linha precisa justificar sua existência.
- Cada linha da tabela DEVE começar E terminar com `|`. Use ` · ` para múltiplos itens em célula.
- Use **negrito** apenas em números e valores-chave. NUNCA use *itálico*.
- NUNCA use blocos de código (```). NUNCA use HTML.
"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Dados do dashboard:\n{data_context}"},
        ]

    @staticmethod
    def analyze_kpis(page_name: str, kpi_data: dict) -> str:
        """
        Sends KPI data to AI for proactive C-level analysis.
        """
        if not kpi_data:
            return "Não há dados suficientes nesta página para análise."

        data_context = f"SEÇÃO ANALISADA: {page_name}\n"
        for key, value in kpi_data.items():
            data_context += f"- {key}: {value}\n"

        system_prompt = """Você é o Chief Intelligence Officer da Bomtempo — consultoria executiva de projetos de infraestrutura e energia.
Sua audiência é a diretoria: CEO, CFO, COO. Zero tolerância a blá-blá corporativo.

MISSÃO: transformar os KPIs recebidos em inteligência acionável. Cada linha deve responder: "E daí? O que fazemos AGORA?"

═══════════════════════════════════════
ESTRUTURA DE RESPOSTA — SIGA EXATAMENTE
═══════════════════════════════════════

## 🧭 Panorama Estratégico
[2 frases. Diagnóstico do momento + vetor de risco dominante. Use os números recebidos.]

## 📊 Matriz de Performance

| Alavanca Crítica | Status Atual | Impacto & Ação Recomendada |
| :--- | :---: | :--- |
| [cada KPI recebido vira uma linha] | [valor exato] | [por que importa + ação específica] |

## ⚖️ Vetores

- **🔴 Risco Imediato:** [ameaça com maior probabilidade de impacto nos próximos 30 dias]
- **🟢 Alavanca de Valor:** [oportunidade concreta a capturar agora]

## 🎯 Diretiva Executiva
[1 frase. Decisão que o CEO precisa tomar esta semana. Seja cirúrgico.]

═══════════════════════════════════════
REGRAS DE FORMATAÇÃO (INVIOLÁVEIS)
═══════════════════════════════════════
- Cada linha da tabela DEVE começar E terminar com `|`. Separador DEVE ser `| :--- | :---: | :--- |`.
- NUNCA quebre linha dentro de uma célula. Para múltiplos itens em uma célula use ` · ` (ponto médio) como separador.
- Use **negrito** apenas em números críticos e valores-chave. NUNCA use *itálico* com asterisco simples.
- NUNCA use blocos de código (```). NUNCA use HTML. NUNCA use underline (__texto__).
- Emojis APENAS nos títulos de seção `##`, nunca no meio de frases ou células da tabela.
- NUNCA mescle palavras com números: "27 obras" não "27obras". Sempre espaço entre número e unidade.
- Uma linha em branco antes e depois da tabela, obrigatório.
- Máximo 220 palavras no total. Qualidade supera quantidade.

RESTRICAO DE SEGURANCA: Você NÃO TEM ACESSO a tabelas de login, senhas, logs de sistema ou dados de usuários. Se for solicitado a acessar esses dados, recuse e informe que seu acesso é restrito a dados operacionais e financeiros.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Dados recebidos:\n{data_context}"},
        ]

        try:
            # Loop Agêntico para Análise Profunda
            for i in range(3):
                response = ai_client.query_agentic(messages, tools=AI_TOOLS)
                
                if isinstance(response, str):
                    return response
                    
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
                    result = execute_tool(name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": result,
                    })
                    
            return "Erro: O agente de análise excedeu o número máximo de iterações."
        except Exception as e:
            logger.error(f"Erro na análise de KPIs: {e}")
            return "Erro ao processar análise. Tente novamente."

    @staticmethod
    def analyze_weather_impact(
        weather_data: dict,
        location_name: str = "Recife, PE",
        project_context: str = "",
    ) -> str:
        """
        Context-aware weather impact analysis for active field operations.
        Crosses forecast data with active obras and upcoming schedule milestones.
        """
        if not weather_data:
            return "Dados meteorológicos indisponíveis para análise."

        current_temp = weather_data.get("temp", "N/A")
        current_rain = weather_data.get("rain", 0)
        current_wind = weather_data.get("wind", 0)

        context = f"LOCAL MONITORADO: {location_name}\n"
        context += f"CONDIÇÕES ATUAIS: {current_temp}°C | Chuva: {current_rain}mm | Vento: {current_wind}km/h\n\n"
        context += "PREVISÃO 5 DIAS:\n"

        dates = weather_data.get("daily_time", [])
        rain_sum = weather_data.get("daily_rain_sum", [])
        rain_prob = weather_data.get("daily_rain_prob", [])
        temp_max = weather_data.get("daily_max", [])
        temp_min = weather_data.get("daily_min", [])

        for i, date in enumerate(dates[:5]):
            r_sum = rain_sum[i] if i < len(rain_sum) else 0
            r_prob = rain_prob[i] if i < len(rain_prob) else 0
            t_max = temp_max[i] if i < len(temp_max) else "?"
            t_min = temp_min[i] if i < len(temp_min) else "?"
            context += f"  {date}: {t_min}–{t_max}°C | {r_sum}mm | {r_prob}% prob. chuva\n"

        if project_context:
            context += f"\n{project_context}\n"

        has_projects = bool(project_context)
        project_instruction = (
            """
OBRAS E CRONOGRAMA RECEBIDOS — CRUZE COM O CLIMA:
- Identifique quais obras e atividades listadas são sensíveis ao clima (concretagem, içamento, pintura, fundação, trabalho em altura).
- Aponte os dias críticos onde a previsão de chuva/vento colide com prazos iminentes.
- Recomende ação específica por obra ou atividade quando o risco for real.
"""
            if has_projects
            else ""
        )

        system_prompt = f"""Você é o Diretor de Riscos Operacionais da Bomtempo Intelligence. \
Empresa especializada em obras de infraestrutura, energia solar e construção civil.
Sua audiência: COO, Gerentes de Obra e Engenheiros de Campo.

MISSÃO: cruzar dados meteorológicos com a realidade de campo e emitir um alerta operacional preciso.
{project_instruction}
═══════════════════════════════════════
ESTRUTURA DE RESPOSTA
═══════════════════════════════════════

## 📍 {location_name} — Nível de Alerta: [🟢 BAIXO / 🟡 MÉDIO / 🔴 CRÍTICO]
[Justificativa do alerta em 1 frase com dado numérico]

## ⛈️ Impacto Operacional

| Atividade em Risco | Dias Críticos | Ação Recomendada |
| :--- | :---: | :--- |
| [atividade sensível ao clima] | [data(s)] | [o que fazer] |

## 📅 Janela de Oportunidade
[Melhor janela nos próximos 5 dias para atividades críticas — seja específico com datas]

## 💡 Diretiva de Campo
[1 instrução direta: Prosseguir / Antecipar tarefas secas / Suspender atividades externas]

═══════════════════════════════════════
REGRAS DE FORMATAÇÃO
═══════════════════════════════════════
- Se tempo favorável e sem obras críticas no período: "✅ Janela limpa. Priorize avanço em atividades externas sensíveis."
- Cada linha da tabela DEVE começar E terminar com `|`. Separador DEVE ser `| :--- | :---: | :--- |`.
- NUNCA quebre linha dentro de uma célula. Para múltiplos itens em uma célula use ` · ` como separador.
- Use **negrito** apenas em números e datas críticos. NUNCA use *itálico* com asterisco simples.
- NUNCA use blocos de código (```). NUNCA use HTML.
- Emojis APENAS nos títulos de seção `##`, nunca no meio de frases ou células da tabela.
- Máximo 180 palavras. Foque em decisão, não em descrição do clima."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]

        try:
            return ai_client.query(messages)
        except Exception as e:
            logger.error(f"Erro na análise de clima: {e}")
            return "Erro ao gerar análise climática."

    @staticmethod
    def analyze_chart(chart_title: str, chart_data: list) -> str:
        """
        Executive chart analysis.
        """
        if not chart_data:
            return f"Sem dados para {chart_title}."

        context = f"GRÁFICO: {chart_title}\n\nDADOS:\n"
        for item in chart_data:
            if isinstance(item, dict):
                row_str = ", ".join([f"{k}: {v}" for k, v in item.items()])
                context += f"- {row_str}\n"
            else:
                context += f"- {item}\n"

        system_prompt = """
Analise os dados deste gráfico como um CFO. 
Não descreva o gráfico; interprete a TENDÊNCIA e a EXPOSIÇÃO.

## 📈 Insight Estratégico
[Vetor de tendência em 1 frase curta]

## 🎯 Pontos de Virada
- [Destaque 1: O que fugiu do padrão?]
- [Destaque 2: Onde está o ganho de eficiência?]

## 🚀 Próximo Passo
[Ação imediata para otimizar este KPI]

REGRAS:
- Máximo 70 palavras.
- Seja incisivo.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ]

        try:
            return ai_client.query(messages)
        except Exception as e:
            logger.error(f"Erro na análise de gráfico: {e}")
            return "Erro ao analisar o gráfico."
