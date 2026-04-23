import pandas as pd

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


class AIContext:
    """Prepares dashboard data for AI context injection."""

    @staticmethod
    def get_dashboard_context(data: dict) -> str:
        """
        Converts the data dictionary into a prompt-friendly string.
        Optimized for signal density: margin alerts, physical vs financial deltas,
        and latest field intelligence from RDOs.
        """
        try:
            context_parts = []

            # 1. Contratos
            if "contratos" in data and not data["contratos"].empty:
                df = data["contratos"]
                cols = ["contrato", "projeto", "cliente", "valor_contratado", "status"]
                valid_cols = [c for c in cols if c in df.columns]
                context_parts.append("## CONTRATOS")
                context_parts.append(df[valid_cols].to_markdown(index=False))
                context_parts.append("")

            # 2. Projetos (Cronograma — resumo por contrato + top atividades pendentes)
            if "projeto" in data and not data["projeto"].empty:
                df = data["projeto"].copy()
                if "conclusao_pct" in df.columns:
                    df["conclusao_pct"] = pd.to_numeric(df["conclusao_pct"], errors="coerce").fillna(0)

                if "contrato" in df.columns:
                    # ── Resumo por contrato ──────────────────────────────────────
                    summary_rows = []
                    for contrato, grp in df.groupby("contrato"):
                        total = len(grp)
                        done = int((grp["conclusao_pct"] == 100).sum()) if "conclusao_pct" in grp.columns else 0
                        avg_pct = round(grp["conclusao_pct"].mean(), 1) if "conclusao_pct" in grp.columns else 0
                        pending = total - done
                        critico_col = next((c for c in grp.columns if "critico" in c.lower()), None)
                        critico_pend = 0
                        if critico_col:
                            critico_pend = int(
                                ((grp[critico_col].str.lower() == "sim") & (grp["conclusao_pct"] < 100)).sum()
                            )
                        summary_rows.append({
                            "contrato": contrato,
                            "total_atividades": total,
                            "concluidas": done,
                            "pendentes": pending,
                            "avanco_medio_%": avg_pct,
                            "criticos_pendentes": critico_pend,
                        })
                    context_parts.append("## CRONOGRAMA — Resumo por Contrato")
                    context_parts.append(pd.DataFrame(summary_rows).to_markdown(index=False))
                    context_parts.append("")

                    # ── Top 4 atividades mais críticas por contrato ──────────────
                    context_parts.append("## CRONOGRAMA — Atividades Pendentes Críticas (top 4 por contrato)")
                    act_cols = [c for c in ["contrato", "fase", "atividade", "conclusao_pct", "termino_previsto"] if c in df.columns]
                    if "conclusao_pct" in df.columns:
                        pending_df = df[df["conclusao_pct"] < 100].copy()
                        critico_col = next((c for c in df.columns if "critico" in c.lower()), None)
                        if critico_col:
                            # Critical first, then by lowest completion
                            pending_df["_critico_sort"] = (pending_df[critico_col].str.lower() != "sim").astype(int)
                            pending_df = pending_df.sort_values(["contrato", "_critico_sort", "conclusao_pct"])
                        else:
                            pending_df = pending_df.sort_values(["contrato", "conclusao_pct"])
                        top_pending = pending_df.groupby("contrato").head(4)
                        context_parts.append(top_pending[act_cols].to_markdown(index=False))
                    context_parts.append("")
                else:
                    # Fallback: no contrato column
                    act_cols = [c for c in ["fase", "atividade", "conclusao_pct", "termino_previsto"] if c in df.columns]
                    if "conclusao_pct" in df.columns:
                        context_parts.append("## CRONOGRAMA (Atividades Pendentes)")
                        context_parts.append(df[df["conclusao_pct"] < 100][act_cols].head(20).to_markdown(index=False))
                    context_parts.append("")

            # 3. Obras (Último Status Físico por Projeto)
            if "obras" in data and not data["obras"].empty:
                df = data["obras"].copy()
                cols = ["projeto", "data", "previsto_pct", "realizado_pct", "comentario"]
                valid_cols = [c for c in cols if c in df.columns]

                if "projeto" in df.columns and "data" in df.columns:
                    df["data"] = pd.to_datetime(df["data"], errors="coerce")
                    agg_cols = [c for c in valid_cols if c != "projeto"]
                    latest_status = (
                        df.sort_values("data")
                        .dropna(subset=["data"])
                        .groupby("projeto")[agg_cols]
                        .last()
                        .reset_index()
                    )
                    # Flag desvio físico
                    if "previsto_pct" in latest_status.columns and "realizado_pct" in latest_status.columns:
                        latest_status["desvio_pct"] = (
                            latest_status["realizado_pct"] - latest_status["previsto_pct"]
                        ).round(1)
                    context_parts.append("## AVANÇO FÍSICO (último registro por projeto)")
                    context_parts.append(latest_status.to_markdown(index=False))
                else:
                    context_parts.append("## AVANÇO FÍSICO")
                    context_parts.append(df[valid_cols].tail(20).to_markdown(index=False))
                context_parts.append("")

            # 4. Financeiro — acumulado por contrato + alertas de margem
            if "financeiro" in data and not data["financeiro"].empty:
                df = data["financeiro"].copy()
                money_cols = ["servico_contratado", "servico_realizado", "material_contratado", "material_realizado", "multa"]
                for col in money_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

                agg_cols_base = ["servico_contratado", "material_contratado", "servico_realizado", "material_realizado"]
                valid_agg = [c for c in agg_cols_base if c in df.columns]

                if "contrato" in df.columns and valid_agg:
                    extra = [c for c in ["multa"] if c in df.columns]
                    agg = df.groupby("contrato")[valid_agg + extra].sum().reset_index()
                    agg["total_contratado"] = agg.get("servico_contratado", 0) + agg.get("material_contratado", 0)
                    agg["total_realizado"] = agg.get("servico_realizado", 0) + agg.get("material_realizado", 0)
                    agg["margem_R$"] = agg["total_contratado"] - agg["total_realizado"]
                    agg["exec_%"] = (
                        (agg["total_realizado"] / agg["total_contratado"] * 100)
                        .replace([float("inf"), float("-inf")], 0)
                        .fillna(0)
                        .round(1)
                    )
                    # Flag contratos em sobre-custo
                    over_budget = agg[agg["margem_R$"] < 0]
                    if not over_budget.empty:
                        context_parts.append("## ⚠️ ALERTAS DE SOBRE-CUSTO (realizado > contratado)")
                        context_parts.append(over_budget[["contrato", "total_contratado", "total_realizado", "margem_R$"]].to_markdown(index=False))
                        context_parts.append("")

                    display_cols = ["contrato", "total_contratado", "total_realizado", "margem_R$", "exec_%"]
                    if "multa" in agg.columns:
                        multas = agg[agg["multa"] > 0]
                        if not multas.empty:
                            context_parts.append("## ⚠️ MULTAS APLICADAS")
                            context_parts.append(multas[["contrato", "multa"]].to_markdown(index=False))
                            context_parts.append("")
                    context_parts.append("## FINANCEIRO (Acumulado por Contrato)")
                    context_parts.append(agg[display_cols].to_markdown(index=False))
                elif len(df) < 15:
                    context_parts.append("## FINANCEIRO (Detalhado)")
                    context_parts.append(df.to_markdown(index=False))
                context_parts.append("")

            # 5. O&M (Operação e Manutenção — último por projeto)
            if "om" in data and not data["om"].empty:
                df = data["om"].copy()
                cols = [
                    "contrato",
                    "projeto",
                    "data",
                    "energia_injetada_kwh",
                    "geracao_prevista_kwh",
                    "faturamento_liquido",
                ]
                valid_cols = [c for c in cols if c in df.columns]

                if "projeto" in df.columns and "data" in df.columns:
                    df["data"] = pd.to_datetime(df["data"], errors="coerce")
                    agg_cols = [c for c in valid_cols if c != "projeto"]
                    latest_om = (
                        df.sort_values("data")
                        .dropna(subset=["data"])
                        .groupby("projeto")[agg_cols]
                        .last()
                        .reset_index()
                    )
                    # Performance ratio
                    if "energia_injetada_kwh" in latest_om.columns and "geracao_prevista_kwh" in latest_om.columns:
                        latest_om["performance_%"] = (
                            (latest_om["energia_injetada_kwh"] / latest_om["geracao_prevista_kwh"].replace(0, float("nan")) * 100)
                            .fillna(0).round(1)
                        )
                    context_parts.append("## O&M (Performance Energética — último mês por projeto)")
                    context_parts.append(latest_om.to_markdown(index=False))
                else:
                    context_parts.append("## O&M")
                    context_parts.append(df[valid_cols].tail(10).to_markdown(index=False))
                context_parts.append("")

            # 6. RDO — últimos registros com atividades do campo
            try:
                from bomtempo.core.supabase_client import sb_select

                rdos = sb_select("rdo_cabecalho", order="ID_RDO.desc", limit=10)
                if rdos:
                    context_parts.append("## RDO (Últimos Relatórios de Campo)")
                    rdo_rows = []
                    for r in rdos:
                        rdo_rows.append({
                            "Contrato": r.get("Contrato"),
                            "Data": r.get("Data"),
                            "Clima": r.get("Condicao_Climatica"),
                            "Turno": r.get("Turno"),
                        })
                    df_rdo = pd.DataFrame(rdo_rows)
                    context_parts.append(df_rdo.to_markdown(index=False))
                    context_parts.append("")

                    # RDO activities — pull atividades for these RDOs
                    rdo_ids = [r.get("ID_RDO") for r in rdos if r.get("ID_RDO")]
                    if rdo_ids:
                        atividades = sb_select("rdo_atividades", limit=30)
                        if atividades:
                            recent = [a for a in atividades if a.get("ID_RDO") in rdo_ids]
                            if recent:
                                ativ_rows = []
                                for a in recent[:20]:
                                    ativ_rows.append({
                                        "RDO": a.get("ID_RDO"),
                                        "Atividade": a.get("Descricao_Atividade") or a.get("atividade"),
                                        "Status": a.get("Status_Atividade") or a.get("status"),
                                    })
                                context_parts.append("### Atividades de Campo (RDO)")
                                context_parts.append(pd.DataFrame(ativ_rows).to_markdown(index=False))
                                context_parts.append("")
            except Exception as e:
                logger.warning(f"Erro ao incluir RDOs no contexto AI: {e}")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Erro ao gerar contexto AI: {e}")
            return "Nota: O detalhamento completo do dashboard está temporariamente indisponível. Por favor, tente perguntar sobre um contrato específico (ex: BOM-029)."

    @staticmethod
    def get_system_prompt(is_mobile: bool = False, tenant_name: str = "", client_id: str = "") -> str:
        """Returns the guardrails and persona definition."""

        mobile_instruction = ""
        if is_mobile:
            mobile_instruction = """
ATENÇÃO: Usuário em MOBILE — sem tabelas largas. Use listas e max 3 colunas.
"""

        tenant_instruction = ""
        if client_id or tenant_name:
            client_id_clause = (
                f"'{client_id}'"
                if client_id
                else f"(SELECT id FROM clients WHERE name = '{tenant_name}')"
            )
            tenant_instruction = f"""
## CONTEXTO OPERACIONAL
Você está operando em ambiente isolado — todos os dados já foram pré-filtrados para esta plataforma.
- Ao usar `execute_sql`, SEMPRE inclua `WHERE client_id = {client_id_clause}` nas queries para garantir o isolamento correto.
- Nas respostas ao usuário, use sempre "sua plataforma", "seus contratos", "seus dados". NUNCA mencione outros clientes, a palavra "tenant" ou detalhes técnicos de infraestrutura.
"""

        return f"""
{mobile_instruction}{tenant_instruction}
## IDENTIDADE
Você é o BOMTEMPO Intelligence — mordomo financeiro e estratégico da carteira de projetos.
Fale como CFO/CPO sênior: direto, sem preâmbulos, sem explicar o que é um dado.

## CAPACIDADES (o que você PODE fazer)
Você tem acesso a ferramentas reais de banco de dados e documentos:
- `get_schema_info` — descobre tabelas e colunas disponíveis
- `execute_sql` — executa SELECT em contratos, financeiro, obras, RDO, O&M, projetos
- `generate_chart_data` — gera gráfico visual interativo inline
- `search_documents` — busca cláusulas, termos e conteúdo em documentos (PDFs, contratos, atas) anexados à linha do tempo

**Sempre que o usuário perguntar sobre dados** (contratos, valores, obras, RDOs, etc.), use `execute_sql` para buscar a informação real. Nunca diga "não localizado" sem antes tentar uma query.

**REGRA CRÍTICA PARA DOCUMENTOS**: Quando o usuário perguntar sobre cláusulas contratuais, multas, garantias, rescisão, prazos, ou "o que diz o contrato sobre X", você DEVE:
1. Chamar `search_documents` com o termo relevante e o contrato (se conhecido)
2. Apresentar os trechos encontrados com contexto
3. Nunca inventar cláusulas — cite apenas o que encontrou no documento

**REGRA CRÍTICA PARA GRÁFICOS**: Quando o usuário pedir "gráfico", "chart", "visualização", "comparação visual" ou qualquer representação gráfica de dados, você DEVE obrigatoriamente:
1. Chamar `get_schema_info` para descobrir colunas
2. Chamar `execute_sql` para buscar os dados reais
3. Chamar `generate_chart_data` com os dados obtidos — NUNCA descreva o gráfico em texto
Nunca diga "aqui está o gráfico" ou descreva o gráfico textualmente — use SEMPRE a ferramenta.

## LIMITAÇÕES (o que você NÃO pode fazer)
- Você NÃO tem acesso a escrita no banco (sem INSERT, UPDATE, DELETE)
- Você NÃO pode alterar senhas, usuários ou configurações do sistema — oriente o usuário a usar a tela de Gerenciar Usuários em `/admin/usuarios`
- Você NÃO pode deletar contratos ou registros — oriente o usuário ao módulo Editor de Dados em `/editar-dados`
- Para pedidos fora do escopo de engenharia/financeiro/gestão de obras, recuse com elegância

## REGRAS DE OURO
1. **Use as ferramentas**: para qualquer pergunta sobre dados, chame `get_schema_info` depois `execute_sql`. Não adivinhe.
2. **Sem alucinação**: nunca invente valores, datas ou percentuais. Se a query retornar vazio, diga isso.
3. **Desvio crítico primeiro**: se houver sobre-custo, atraso, multa ou performance abaixo de 90 %, mencione ANTES de qualquer elogio.
4. **Ação > Diagnóstico**: toda resposta com risco deve ter pelo menos 1 ação concreta e prazo.

## FORMATO
- **Negrito** (`**texto**`) apenas em números críticos e nomes de contratos. NUNCA use *itálico* com asterisco simples.
- ⚠️ para riscos, ✅ para pontos saudáveis, 🔴 para crítico, 🟡 para atenção — apenas no início de linha ou título.
- Respostas longas: use seções com `##`. Respostas curtas: bullet points com `-`.
- Valores em BRL: "R$ 1,3 M" ou "R$ 450 k". Percentuais: "68 %". Sempre espaço entre número e unidade.
- NUNCA use blocos de código (```). NUNCA use HTML. NUNCA use underline (__texto__).
- NUNCA use sintaxe de imagem Markdown `![...]()` — quando gerar um gráfico via `generate_chart_data`, ele aparece automaticamente abaixo da resposta; não o mencione com imagem.
- Tabelas: `|` no início e fim de cada linha, separador `| :--- | :---: |`. NUNCA quebre linha dentro de uma célula — use ` · ` para separar múltiplos itens.
- Se os dados de um módulo forem escassos, aprofunde a análise do que existe e projete tendências ou ações preventivas.

## REGRAS DE NEGÓCIO (use para inferência)
- Margem negativa (realizado > contratado) = sobre-custo → acionar plano de recuperação.
- Desvio físico > 10 pp (previsto − realizado) = risco de multa contratual.
- Performance O&M < 95 % = possível falha de equipamento ou sujidade → manutenção preventiva.
- exec_% > 80 % com desvio físico negativo = adiantamento financeiro não coberto por avanço → risco de caixa.

DADOS DO PAINEL:
"""
