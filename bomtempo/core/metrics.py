"""
Cálculos de métricas e KPIs
"""

import numpy as np

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


class MetricsCalculator:
    """Calcula todas as métricas do projeto"""

    @staticmethod
    def calcular_avanco_fisico(df_obras):
        """Avanço físico médio ponderado"""
        if df_obras.empty:
            return 0.0

        # Pegar último registro por projeto/contrato
        df_sorted = df_obras.sort_values("data")
        latest = df_sorted.groupby("projeto").last().reset_index()

        # Média ponderada pela potência ou simples
        if "potencia_kwp" in latest.columns and latest["potencia_kwp"].sum() > 0:
            return float(np.average(latest["realizado_pct"], weights=latest["potencia_kwp"]))
        return float(latest["realizado_pct"].mean())

    @staticmethod
    def calcular_avanco_financeiro(df_financeiro):
        """Avanço financeiro (realizado vs contratado)"""
        if df_financeiro.empty:
            return 0.0

        total_contratado = (
            df_financeiro["servico_contratado"].sum() + df_financeiro["material_contratado"].sum()
        )
        total_realizado = (
            df_financeiro["servico_realizado"].sum() + df_financeiro["material_realizado"].sum()
        )

        return (total_realizado / total_contratado * 100) if total_contratado > 0 else 0.0

    @staticmethod
    def calcular_psi(df_projeto, df_obras, df_financeiro):
        """
        Calcula o PSI (Portfolio Status Index) - 0 a 100
        Composto por:
        - Prazo (SPI) - 40%
        - Custo (CPI/Margem) - 30%
        - Qualidade/Riscos - 30%
        """
        score = 100.0

        # 1. Prazo (SPI)
        if not df_projeto.empty and "conclusao_pct" in df_projeto.columns:
            # Projetos atrasados (>5% de desvio)
            atrasados = len(
                df_projeto[(df_projeto["conclusao_pct"] < 95) & (df_projeto["critico"] == "Sim")]
            )
            total = len(df_projeto)
            fator_prazo = max(0, 1 - (atrasados / total * 2)) if total > 0 else 1
            score -= (1 - fator_prazo) * 40

        # 2. Financeiro (Margem)
        if not df_financeiro.empty:
            margem_alvo = 0.15  # 15%
            total_contratado = (
                df_financeiro["servico_contratado"].sum()
                + df_financeiro["material_contratado"].sum()
            )
            total_realizado = (
                df_financeiro["servico_realizado"].sum() + df_financeiro["material_realizado"].sum()
            )
            margem_atual = (
                ((total_contratado - total_realizado) / total_contratado)
                if total_contratado > 0
                else 0
            )

            # Se margem < 50% da meta, perde pontos
            if margem_atual < margem_alvo:
                perda = min(1, (margem_alvo - margem_atual) / margem_alvo)
                score -= perda * 30

        # 3. Penalidade por Multas
        if not df_financeiro.empty and "multa" in df_financeiro.columns:
            multas = df_financeiro["multa"].sum()
            if multas > 0:
                score -= min(30, (multas / 100000) * 10)

        return max(0, min(100, score))
