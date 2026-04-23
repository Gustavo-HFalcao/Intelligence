"""
Data Augmentation - Geração de dados sintéticos coerentes
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from bomtempo.core.config import Config
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


class DataAugmentor:
    """Gera dados sintéticos mantendo relacionamentos"""

    def __init__(self, seed=None):
        self.seed = seed or Config.SYNTHETIC_SEED
        self.rng = np.random.default_rng(self.seed)

        # Listas para geração
        self.clientes_base = [
            "Energia Solar Nordeste",
            "Parque Eólico Sul",
            "Hidrelétrica Centro-Oeste",
            "Fotovoltaica PE",
            "Renováveis BA",
            "Green Power RN",
            "Solar Tech CE",
            "EcoEnergia PB",
            "PowerPlant AL",
            "Sustentável SE",
        ]

        self.terceirizados_base = [
            "Construtora Alpha",
            "Engenharia Beta",
            "Infraestrutura Gamma",
            "Delta Obras",
            "Epsilon Instalações",
            "Zeta Construções",
            "Eta Projetos",
            "Theta Montagem",
            "Iota Elétrica",
            "Kappa Civil",
        ]

        self.localizacoes_base = [
            "Recife/PE",
            "Caruaru/PE",
            "Petrolina/PE",
            "Salvador/BA",
            "Feira de Santana/BA",
            "Fortaleza/CE",
            "Natal/RN",
            "João Pessoa/PB",
            "Maceió/AL",
            "Aracaju/SE",
        ]

    def augment_all(self, data):
        """Aumenta todos os dataframes mantendo coerência"""
        multiplier = Config.SYNTHETIC_MULTIPLIER

        # Contratos (base)
        data["contratos"] = self._augment_contratos(
            data.get("contratos", pd.DataFrame()), multiplier
        )

        # Extrair chaves únicas
        contratos_list = data["contratos"]["contrato"].unique().tolist()
        clientes_list = data["contratos"]["cliente"].unique().tolist()
        projetos_list = data["contratos"]["projeto"].unique().tolist()

        # Projeto
        data["projeto"] = self._augment_projeto(
            data.get("projeto", pd.DataFrame()),
            contratos_list,
            clientes_list,
            projetos_list,
            multiplier,
        )

        # Obras
        data["obras"] = self._augment_obras(
            data.get("obras", pd.DataFrame()),
            contratos_list,
            clientes_list,
            projetos_list,
            multiplier,
        )

        # Financeiro
        data["financeiro"] = self._augment_financeiro(
            data.get("financeiro", pd.DataFrame()),
            contratos_list,
            clientes_list,
            projetos_list,
            multiplier,
        )

        # O&M
        data["om"] = self._augment_om(
            data.get("om", pd.DataFrame()), contratos_list, clientes_list, projetos_list, multiplier
        )

        return data

    def _augment_contratos(self, df, multiplier):
        """Gera contratos sintéticos"""
        if df.empty:
            n_rows = 20
        else:
            n_rows = len(df) * multiplier

        rows = []
        for i in range(n_rows):
            ano = int(self.rng.choice([23, 24, 25]))
            num = str(i + 10).zfill(3)
            contrato = f"BOM{num}-{ano}"

            cliente = self.rng.choice(self.clientes_base)
            projeto = f"Projeto {cliente.split()[0]} {ano}"
            terceirizado = self.rng.choice(self.terceirizados_base)
            localizacao = self.rng.choice(self.localizacoes_base)

            # Valores mais espaçados e realistas
            valor_choices = [
                self.rng.uniform(300_000, 1_500_000),  # Pequeno porte
                self.rng.uniform(1_500_000, 5_000_000),  # Médio porte
                self.rng.uniform(5_000_000, 15_000_000),  # Grande porte
            ]
            valor = float(self.rng.choice(valor_choices))

            status = self.rng.choice(
                ["Em Execução", "Concluído", "Em Planejamento"], p=[0.5, 0.35, 0.15]
            )

            # Datas mais variadas entre 2022-2025
            inicio = datetime(
                2022 + int(self.rng.integers(0, 4)),
                int(self.rng.integers(1, 13)),
                int(self.rng.integers(1, 28)),
            )
            vigencia_meses = int(self.rng.choice([6, 12, 18, 24, 30, 36]))
            fim = inicio + timedelta(days=vigencia_meses * 30)
            vigencia = f"{inicio.strftime('%d/%m/%Y')} - {fim.strftime('%d/%m/%Y')}"

            rows.append(
                {
                    "contrato": contrato,
                    "cliente": cliente,
                    "projeto": projeto,
                    "terceirizado": terceirizado,
                    "localizacao": localizacao,
                    "valor_contratado": valor,
                    "status": status,
                    "vigencia": vigencia,
                }
            )

        return pd.DataFrame(rows)

    def _augment_projeto(self, df, contratos, clientes, projetos, multiplier):
        """Gera atividades de projeto"""
        n_projetos = len(projetos)

        fases = [
            "Planejamento",
            "Projeto Executivo",
            "Fundação",
            "Estrutura",
            "Montagem",
            "Instalação Elétrica",
            "Comissionamento",
            "Entrega",
        ]

        rows = []
        for projeto in projetos[: min(n_projetos, 50)]:
            contrato = self.rng.choice(
                [c for c in contratos if projeto.split()[1] in c] or contratos[:1]
            )
            cliente = self.rng.choice(
                [cl for cl in clientes if projeto.split()[1] in cl] or clientes[:1]
            )

            data_inicio_projeto = datetime(2024, int(self.rng.integers(1, 13)), 1)

            for i, fase in enumerate(fases):
                for j in range(int(self.rng.integers(1, 4))):
                    atividade = f"{fase} - Etapa {j+1}"

                    inicio = data_inicio_projeto + timedelta(days=int(i * 30 + j * 10))
                    duracao = int(self.rng.integers(10, 45))
                    termino = inicio + timedelta(days=duracao)

                    # Conclusão mais realista baseada na data
                    if termino < datetime.now():
                        conclusao = float(
                            self.rng.choice(
                                [100, self.rng.uniform(85, 100), self.rng.uniform(60, 85)],
                                p=[0.6, 0.3, 0.1],
                            )
                        )
                    else:
                        dias_decorridos = (datetime.now() - inicio).days
                        dias_totais = (termino - inicio).days
                        conclusao_esperada = (
                            (dias_decorridos / dias_totais) * 100 if dias_totais > 0 else 0
                        )
                        conclusao = float(
                            max(0, min(95, conclusao_esperada + self.rng.uniform(-15, 15)))
                        )

                    rows.append(
                        {
                            "contrato": contrato,
                            "cliente": cliente,
                            "projeto": projeto,
                            "fase": fase,
                            "atividade": atividade,
                            "inicio_previsto": inicio,
                            "termino_previsto": termino,
                            "conclusao_pct": conclusao,
                            "responsavel": self.rng.choice(
                                ["João Silva", "Maria Costa", "Pedro Santos", "Ana Lima"]
                            ),
                            "critico": self.rng.choice(["Sim", "Não"], p=[0.2, 0.8]),
                            "dependencia": "" if i == 0 else fases[i - 1],
                        }
                    )

        return pd.DataFrame(rows)

    def _augment_obras(self, df, contratos, clientes, projetos, multiplier):
        """Gera evolução de obras"""
        categorias = ["Civil", "Estrutura", "Módulo", "Elétrica", "Infraestrutura"]

        rows = []
        for projeto in projetos[: min(len(projetos), 50)]:
            contrato = self.rng.choice(
                [c for c in contratos if projeto.split()[1] in c] or contratos[:1]
            )
            cliente = self.rng.choice(
                [cl for cl in clientes if projeto.split()[1] in cl] or clientes[:1]
            )
            terceirizado = self.rng.choice(self.terceirizados_base)
            localizacao = self.rng.choice(self.localizacoes_base)

            data_inicio = datetime(2024, int(self.rng.integers(1, 13)), 1)

            # Gerar série temporal
            for dias in range(0, 180, 7):
                data = data_inicio + timedelta(days=dias)

                for idx, categoria in enumerate(categorias):
                    # Categorias progridem em ritmos diferentes
                    atraso_variacao = self.rng.choice(
                        [-20, -10, 0, 5, 10], p=[0.1, 0.2, 0.4, 0.2, 0.1]
                    )
                    progresso = min(100, max(0, (dias / 180) * 100 + atraso_variacao + (idx * 5)))
                    previsto = min(100, (dias / 180) * 100 + (idx * 3))

                    rows.append(
                        {
                            "contrato": contrato,
                            "cliente": cliente,
                            "projeto": projeto,
                            "terceirizado": terceirizado,
                            "localizacao": localizacao,
                            "data": data,
                            "categoria": categoria,
                            "previsto_pct": previsto,
                            "realizado_pct": progresso,
                            "os": f"OS-{int(self.rng.integers(1000, 9999))}",
                            "potencia_kwp": float(self.rng.uniform(100, 5000)),
                            "prazo_contratual": int(self.rng.integers(90, 365)),
                            "inicio": data_inicio,
                            "termino": data_inicio
                            + timedelta(days=int(self.rng.integers(180, 365))),
                        }
                    )

        return pd.DataFrame(rows)

    def _augment_financeiro(self, df, contratos, clientes, projetos, multiplier):
        """Gera dados financeiros"""
        marcos = [
            "Mobilização",
            "Fundação",
            "Estrutura",
            "Módulos",
            "Elétrica",
            "Comissionamento",
        ]
        cockpits = ["Contrato", "Terceirizado", "Operação"]

        rows = []
        for projeto in projetos[: min(len(projetos), 50)]:
            contrato = self.rng.choice(
                [c for c in contratos if projeto.split()[1] in c] or contratos[:1]
            )
            cliente = self.rng.choice(
                [cl for cl in clientes if projeto.split()[1] in cl] or clientes[:1]
            )

            for marco in marcos:
                for cockpit in cockpits:
                    # Valores mais variados por cockpit
                    if cockpit == "Contrato":
                        valor_base = float(self.rng.uniform(100_000, 800_000))
                    elif cockpit == "Terceirizado":
                        valor_base = float(self.rng.uniform(50_000, 400_000))
                    else:  # Operação
                        valor_base = float(self.rng.uniform(30_000, 200_000))

                    # Realização mais realista
                    realizacao_pct = self.rng.choice(
                        [
                            self.rng.uniform(0.95, 1.05),  # Normal
                            self.rng.uniform(0.75, 0.95),  # Atrasado
                            self.rng.uniform(0.50, 0.75),  # Muito atrasado
                        ],
                        p=[0.7, 0.2, 0.1],
                    )

                    rows.append(
                        {
                            "contrato": contrato,
                            "cliente": cliente,
                            "projeto": projeto,
                            "marco": marco,
                            "cockpit": cockpit,
                            "servico_contratado": valor_base,
                            "servico_realizado": valor_base * float(realizacao_pct),
                            "material_contratado": valor_base * self.rng.uniform(0.3, 0.5),
                            "material_realizado": valor_base
                            * self.rng.uniform(0.3, 0.5)
                            * float(realizacao_pct * self.rng.uniform(0.9, 1.0)),
                            "multa": float(
                                self.rng.choice(
                                    [0, 0, 0, 0, self.rng.uniform(2000, 25000)],
                                    p=[0.85, 0.05, 0.05, 0.03, 0.02],
                                )
                            ),
                            "justificativa": self.rng.choice(
                                [
                                    "N/A",
                                    "Atraso de fornecedor",
                                    "Condições climáticas",
                                    "Retrabalho",
                                ],
                                p=[0.85, 0.08, 0.05, 0.02],
                            ),
                        }
                    )

        return pd.DataFrame(rows)

    def _augment_om(self, df, contratos, clientes, projetos, multiplier):
        """Gera dados de O&M"""
        rows = []

        for projeto in projetos[: min(len(projetos), 30)]:
            contrato = self.rng.choice(
                [c for c in contratos if projeto.split()[1] in c] or contratos[:1]
            )
            cliente = self.rng.choice(
                [cl for cl in clientes if projeto.split()[1] in cl] or clientes[:1]
            )
            terceirizado = self.rng.choice(self.terceirizados_base)
            localizacao = self.rng.choice(self.localizacoes_base)

            # 12 meses de dados
            for mes in range(1, 13):
                data = datetime(2025, mes, 1)

                # Variação sazonal de geração (verão gera mais)
                fator_sazonal = 1.2 if mes in [10, 11, 12, 1, 2, 3] else 0.85
                geracao_prevista = float(self.rng.uniform(80_000, 350_000) * fator_sazonal)

                # Performance realista
                performance = self.rng.choice(
                    [
                        self.rng.uniform(0.90, 0.98),  # Ótimo
                        self.rng.uniform(0.80, 0.90),  # Bom
                        self.rng.uniform(0.65, 0.80),  # Regular
                    ],
                    p=[0.6, 0.3, 0.1],
                )

                energia_injetada = geracao_prevista * float(performance)
                compensado = energia_injetada * float(self.rng.uniform(0.88, 0.96))

                rows.append(
                    {
                        "contrato": contrato,
                        "cliente": cliente,
                        "projeto": projeto,
                        "terceirizado": terceirizado,
                        "localizacao": localizacao,
                        "data": data,
                        "mes_ano": f"{mes:02d}/2025",
                        "geracao_prevista_kwh": geracao_prevista,
                        "energia_injetada_kwh": energia_injetada,
                        "compensado_kwh": compensado,
                        "acumulado_kwh": energia_injetada * mes,
                        "valor_faturado": energia_injetada * float(self.rng.uniform(0.4, 0.6)),
                        "gestao": float(self.rng.uniform(5_000, 15_000)),
                        "faturamento_liquido": energia_injetada
                        * float(self.rng.uniform(0.35, 0.55)),
                    }
                )

        return pd.DataFrame(rows)
