"""
Validação de dados
"""

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


class DataValidator:
    """Valida estrutura e integridade dos dados"""

    REQUIRED_COLUMNS = {
        "projeto": ["contrato", "cliente", "projeto", "fase", "atividade"],
        "obras": ["contrato", "cliente", "projeto"],  # derived in-memory from contratos
        "fin_custos": ["contrato", "categoria_nome", "descricao"],
        "hub_atividades": ["contrato", "cliente", "projeto", "fase", "atividade"],
        "om": ["contrato", "cliente", "projeto", "mes_ano"],
        "contratos": ["contrato", "cliente", "projeto"],
    }

    def validate_all(self, data):
        """Valida todos os dataframes"""
        for key, df in data.items():
            self.validate_dataframe(df, key)

    def validate_dataframe(self, df, name):
        """Valida um dataframe específico"""
        if df.empty:
            logger.warning(f"⚠️ DataFrame '{name}' está vazio")
            return False

        required = self.REQUIRED_COLUMNS.get(name, [])
        missing = [col for col in required if col not in df.columns]

        if missing:
            logger.warning(f"⚠️ '{name}' - Colunas faltando: {missing}")
            return False

        key_cols = ["contrato", "cliente", "projeto"]
        for col in key_cols:
            if col in df.columns:
                nulls = df[col].isna().sum()
                if nulls > 0:
                    logger.warning(f"⚠️ '{name}' - {nulls} valores nulos em '{col}'")

        logger.info(f"✅ '{name}' validado: {len(df)} registros")
        return True
