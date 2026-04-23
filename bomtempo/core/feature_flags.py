"""
Feature Flags Service — controla quais sub-features estão ativas por contrato.

Cada contrato pode ter um conjunto diferente de features habilitadas.
O gestor controla isso em /admin/contract-features.
A tabela `contract_features` armazena: (contract_id, feature_key, is_enabled).

Há dois grupos de flags:

1. FLAGS DE NEGÓCIO (por contrato, granular):
   Controlam comportamentos do produto para cada contrato individualmente.
   Ex: validação GPS, score IA, assinatura digital.

2. FLAGS DE INFRAESTRUTURA (por contrato, mas com default global):
   Controlam features que afetam recursos do servidor.
   Nascem com um default global (ON ou OFF) e podem ser sobrescritas por contrato.
   Ex: pdf_generation está OFF globalmente enquanto o servidor tem 1GB RAM.
       Quando a máquina for upgradeada para 2GB, basta ligar no painel — sem deploy.

   Padrão atual:
     pdf_generation  → OFF  (Chromium usa 300-500MB; servidor tem 1GB; OOM kill)
     email_send      → ON   (SMTP leve, sem impacto de RAM)
     ai_insight      → ON   (API externa, sem impacto de RAM)
     rdo_view        → ON   (só salva view_token no banco, sem custo)
"""

from typing import Dict, List

from bomtempo.core.logging_utils import get_logger
from bomtempo.core.supabase_client import sb_select, sb_upsert

logger = get_logger(__name__)

_TABLE = "contract_features"

# ── Feature Keys — Negócio ───────────────────────────────────────────────────

# Reembolso
FEATURE_GPS_VALIDATION      = "gps_validation"
FEATURE_DUPLICATE_DETECTION = "duplicate_detection"
FEATURE_AI_SCORE            = "ai_score"
FEATURE_DIGITAL_SIGNATURE   = "digital_signature"

# RDO
FEATURE_CONDITIONAL_FIELDS  = "conditional_fields"   # chuva / acidente
FEATURE_AUTO_WEATHER        = "auto_weather"          # clima no check-in

# ── Feature Keys — Infraestrutura ────────────────────────────────────────────
# Flags que controlam recursos do servidor. Default global pode ser OFF.
# Um contrato pode sobrescrever (ex: contrato premium com PDF ativo).

FEATURE_PDF_GENERATION      = "pdf_generation"   # Chromium subprocess — OFF até upgrade de RAM
FEATURE_EMAIL_SEND          = "email_send"        # Envio de e-mails via SMTP
FEATURE_AI_INSIGHT          = "ai_insight"        # Análise IA no RDO (Claude API)
FEATURE_RDO_VIEW            = "rdo_view"          # Geração de link de visualização pública

# ── Defaults globais de infraestrutura ───────────────────────────────────────
# Usado quando o contrato não tem configuração explícita no banco.
# OFF = desligado para todos os tenants até configuração manual.
INFRA_DEFAULTS: Dict[str, bool] = {
    FEATURE_PDF_GENERATION: False,  # OFF — servidor 1GB, Chromium causa OOM
    FEATURE_EMAIL_SEND:     True,
    FEATURE_AI_INSIGHT:     True,
    FEATURE_RDO_VIEW:       True,
}

# Features que ficam OFF por padrão para flags de negócio
FEATURES_OFF_BY_DEFAULT: List[str] = []

# ── Metadata ────────────────────────────────────────────────────────────────

FEATURE_LABELS: Dict[str, str] = {
    # Negócio
    FEATURE_GPS_VALIDATION:      "Validação GPS (Localização vs Check-in)",
    FEATURE_DUPLICATE_DETECTION: "Detecção de Duplicidade (Hash MD5)",
    FEATURE_AI_SCORE:            "Score de Confiabilidade IA (0–100)",
    FEATURE_DIGITAL_SIGNATURE:   "Assinatura Digital",
    FEATURE_CONDITIONAL_FIELDS:  "Campos Condicionais (Chuvas / Acidentes)",
    FEATURE_AUTO_WEATHER:        "Clima Automático no Check-in (RDO)",
    # Infra
    FEATURE_PDF_GENERATION:      "Geração de PDF (Chromium — requer 2GB RAM)",
    FEATURE_EMAIL_SEND:          "Envio de E-mails (SMTP)",
    FEATURE_AI_INSIGHT:          "Análise IA no RDO (Claude API)",
    FEATURE_RDO_VIEW:            "Link de Visualização Pública (RDO View)",
}

FEATURE_MODULES: Dict[str, str] = {
    # Negócio
    FEATURE_GPS_VALIDATION:      "reembolso",
    FEATURE_DUPLICATE_DETECTION: "reembolso",
    FEATURE_AI_SCORE:            "reembolso",
    FEATURE_DIGITAL_SIGNATURE:   "ambos",
    FEATURE_CONDITIONAL_FIELDS:  "rdo",
    FEATURE_AUTO_WEATHER:        "rdo",
    # Infra
    FEATURE_PDF_GENERATION:      "infra",
    FEATURE_EMAIL_SEND:          "infra",
    FEATURE_AI_INSIGHT:          "infra",
    FEATURE_RDO_VIEW:            "infra",
}

# Ordem fixa para a UI — infra primeiro (mais visível para admin)
FEATURE_ORDER: List[str] = [
    # — Infraestrutura
    FEATURE_PDF_GENERATION,
    FEATURE_EMAIL_SEND,
    FEATURE_AI_INSIGHT,
    FEATURE_RDO_VIEW,
    # — Reembolso
    FEATURE_GPS_VALIDATION,
    FEATURE_DUPLICATE_DETECTION,
    FEATURE_AI_SCORE,
    FEATURE_DIGITAL_SIGNATURE,
    # — RDO
    FEATURE_CONDITIONAL_FIELDS,
    FEATURE_AUTO_WEATHER,
]

# Features ativas por padrão quando não há configuração no banco.
# Infra flags usam INFRA_DEFAULTS; flags de negócio usam opt-out (ON por padrão).
def _build_default_active() -> List[str]:
    result = []
    for fk in FEATURE_ORDER:
        if fk in INFRA_DEFAULTS:
            if INFRA_DEFAULTS[fk]:
                result.append(fk)
        elif fk not in FEATURES_OFF_BY_DEFAULT:
            result.append(fk)
    return result

_DEFAULT_ACTIVE = _build_default_active()


# ── Service ─────────────────────────────────────────────────────────────────

class FeatureFlagsService:
    """Serviço de feature flags por contrato."""

    @staticmethod
    def is_enabled(feature_key: str, contract_id: str = "") -> bool:
        """
        Verifica se uma feature está habilitada para um contrato.

        Lógica de resolução (precedência):
          1. Se há registro explícito no banco para (contract_id, feature_key) → usa esse valor.
          2. Se não há registro E é flag de infra → usa INFRA_DEFAULTS (global).
          3. Se não há registro E é flag de negócio → assume ON (opt-out padrão).

        Uso:
            if FeatureFlagsService.is_enabled(FEATURE_PDF_GENERATION, contrato):
                # gera PDF
        """
        try:
            if contract_id and contract_id.strip() not in ("", "nan", "None"):
                rows = sb_select(
                    _TABLE,
                    filters={"contract_id": contract_id, "feature_key": feature_key},
                    limit=1,
                ) or []
                if rows:
                    return bool(rows[0].get("is_enabled", True))
            # Sem registro explícito: infra usa default global, negócio usa ON
            if feature_key in INFRA_DEFAULTS:
                return INFRA_DEFAULTS[feature_key]
            return feature_key not in FEATURES_OFF_BY_DEFAULT
        except Exception as e:
            logger.error(f"is_enabled({feature_key}, {contract_id}): {e}")
            # Fail-safe: infra flags ficam no default global, negócio fica ON
            if feature_key in INFRA_DEFAULTS:
                return INFRA_DEFAULTS[feature_key]
            return True

    @staticmethod
    def get_features_for_contract(contract_id: str) -> List[str]:
        """Retorna lista de feature keys habilitadas para um contrato.
        Lógica:
          - Flags com registro explícito no BD → usa o valor do BD.
          - Flags sem registro: infra → usa INFRA_DEFAULTS; negócio → ON (opt-out).
        """
        try:
            if not contract_id or contract_id.strip() in ("", "nan", "None"):
                return list(_DEFAULT_ACTIVE)
            rows = sb_select(_TABLE, filters={"contract_id": contract_id}) or []
            # Monta dict {feature_key: is_enabled} para os registros existentes
            db_map: Dict[str, bool] = {}
            for r in rows:
                fk = r.get("feature_key")
                if fk:
                    db_map[str(fk)] = bool(r.get("is_enabled", True))
            # Para cada feature na ordem, decide se está ativa
            result = []
            for fk in FEATURE_ORDER:
                if fk in db_map:
                    if db_map[fk]:
                        result.append(fk)
                elif fk in INFRA_DEFAULTS:
                    if INFRA_DEFAULTS[fk]:
                        result.append(fk)
                elif fk not in FEATURES_OFF_BY_DEFAULT:
                    result.append(fk)
            return result
        except Exception as e:
            logger.error(f"get_features_for_contract({contract_id}): {e}")
            return list(_DEFAULT_ACTIVE)  # erro → fail-open

    @staticmethod
    def get_all_features_raw() -> List[Dict]:
        """Retorna todos os registros da tabela contract_features."""
        try:
            return sb_select(_TABLE, order="contract_id.asc") or []
        except Exception as e:
            logger.error(f"get_all_features_raw: {e}")
            return []

    @staticmethod
    def set_feature(contract_id: str, feature_key: str, is_enabled: bool, updated_by: str = "") -> bool:
        """Habilita ou desabilita uma feature para um contrato (upsert)."""
        if not contract_id or not feature_key:
            return False
        try:
            sb_upsert(
                _TABLE,
                {
                    "contract_id": contract_id,
                    "feature_key": feature_key,
                    "is_enabled":  is_enabled,
                    "updated_by":  updated_by,
                },
                on_conflict="contract_id,feature_key",
            )
            logger.info(f"✅ Feature flag: {contract_id}/{feature_key} → {is_enabled}")
            return True
        except Exception as e:
            logger.error(f"set_feature({contract_id}/{feature_key}): {e}")
            return False

    @staticmethod
    def build_matrix(contract_ids: List[str]) -> Dict[str, Dict[str, bool]]:
        """
        Retorna dict: contract_id → {feature_key: is_enabled}
        para todos os contratos listados.
        """
        try:
            rows = sb_select(_TABLE) or []
            matrix: Dict[str, Dict[str, bool]] = {
                cid: {fk: False for fk in FEATURE_ORDER}
                for cid in contract_ids
            }
            for r in rows:
                cid = str(r.get("contract_id", ""))
                fk  = str(r.get("feature_key", ""))
                if cid in matrix and fk in matrix[cid]:
                    matrix[cid][fk] = bool(r.get("is_enabled", False))
            return matrix
        except Exception as e:
            logger.error(f"build_matrix: {e}")
            return {}

    @staticmethod
    def get_grid_rows(contract_ids: List[str]) -> List[Dict]:
        """
        Retorna lista de dicts para rx.foreach na UI de admin.
        Cada dict: {"contract_id": "BOM-001", "gps_validation": "true", ...}
        Valores são strings "true"/"false" para compatibilidade com Reflex.
        """
        matrix = FeatureFlagsService.build_matrix(contract_ids)
        rows = []
        for cid in contract_ids:
            row: Dict[str, str] = {"contract_id": cid}
            for fk in FEATURE_ORDER:
                row[fk] = "true" if matrix.get(cid, {}).get(fk, False) else "false"
            rows.append(row)
        return rows
