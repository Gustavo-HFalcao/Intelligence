"""
Audit Logger — Bomtempo Intelligence
=====================================
Fire-and-forget audit logging to Supabase `system_logs` table.

All calls are 100% non-blocking: launched in a daemon thread so the
UI event loop / WebSocket is NEVER delayed by database I/O.

SQL para criar a tabela (rodar no Supabase SQL Editor):
------------------------------------------------------
    CREATE TABLE system_logs (
        id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        created_at   TIMESTAMPTZ NOT NULL    DEFAULT NOW(),
        username     TEXT        NOT NULL    DEFAULT 'system',
        action_category TEXT     NOT NULL,   -- ver AuditCategory abaixo
        action       TEXT        NOT NULL,
        entity_type  TEXT,                   -- 'contratos', 'rdo', 'reembolso', etc.
        entity_id    TEXT,
        metadata     JSONB,
        status       TEXT        NOT NULL    DEFAULT 'success',
        ip_address   TEXT
    );

    -- Índices para a página de auditoria (filtros rápidos)
    CREATE INDEX idx_sl_created_at ON system_logs (created_at DESC);
    CREATE INDEX idx_sl_category   ON system_logs (action_category);
    CREATE INDEX idx_sl_username   ON system_logs (username);
    CREATE INDEX idx_sl_status     ON system_logs (status);
------------------------------------------------------
"""

import threading
from typing import Any, Dict, Optional

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)


# ── Category constants (string enum, compatível com Reflex vars) ──────────────


class AuditCategory:
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    DATA_EDIT = "DATA_EDIT"
    DATA_UPLOAD = "DATA_UPLOAD"
    DATA_SAVE = "DATA_SAVE"
    DATA_DELETE = "DATA_DELETE"
    RDO_CREATE = "RDO_CREATE"
    REEMBOLSO_CREATE = "REEMBOLSO_CREATE"
    REPORT_GEN = "REPORT_GEN"
    AI_CHAT = "AI_CHAT"
    AI_INSIGHT = "AI_INSIGHT"
    ALERT_TRIGGER = "ALERT_TRIGGER"
    ALERT_CONFIG = "ALERT_CONFIG"
    USER_MGMT = "USER_MGMT"
    ERROR = "ERROR"
    SYSTEM = "SYSTEM"


# All categories as an ordered list (for UI filter chips)
ALL_CATEGORIES: list = [
    AuditCategory.LOGIN,
    AuditCategory.LOGOUT,
    AuditCategory.DATA_EDIT,
    AuditCategory.DATA_UPLOAD,
    AuditCategory.DATA_SAVE,
    AuditCategory.DATA_DELETE,
    AuditCategory.RDO_CREATE,
    AuditCategory.REEMBOLSO_CREATE,
    AuditCategory.REPORT_GEN,
    AuditCategory.AI_CHAT,
    AuditCategory.AI_INSIGHT,
    AuditCategory.ALERT_TRIGGER,
    AuditCategory.ALERT_CONFIG,
    AuditCategory.USER_MGMT,
    AuditCategory.ERROR,
    AuditCategory.SYSTEM,
]

# Human-readable labels for the UI
CATEGORY_LABELS: Dict[str, str] = {
    AuditCategory.LOGIN: "Login",
    AuditCategory.LOGOUT: "Logout",
    AuditCategory.DATA_EDIT: "Edição de Dados",
    AuditCategory.DATA_UPLOAD: "Upload de Dados",
    AuditCategory.DATA_SAVE: "Salvar no Banco",
    AuditCategory.DATA_DELETE: "Exclusão de Registro",
    AuditCategory.RDO_CREATE: "RDO Criado",
    AuditCategory.REEMBOLSO_CREATE: "Reembolso Submetido",
    AuditCategory.REPORT_GEN: "Relatório Gerado",
    AuditCategory.AI_CHAT: "Chat IA",
    AuditCategory.AI_INSIGHT: "Insight IA",
    AuditCategory.ALERT_TRIGGER: "Alerta Disparado",
    AuditCategory.ALERT_CONFIG: "Config. de Alertas",
    AuditCategory.USER_MGMT: "Gestão de Usuários",
    AuditCategory.ERROR: "Erro",
    AuditCategory.SYSTEM: "Sistema",
}

# Color coding per category for the UI badges
CATEGORY_COLORS: Dict[str, str] = {
    AuditCategory.LOGIN: "#2A9D8F",           # patina — green
    AuditCategory.LOGOUT: "#889999",          # muted
    AuditCategory.DATA_EDIT: "#C98B2A",       # copper
    AuditCategory.DATA_UPLOAD: "#E0A63B",     # copper light
    AuditCategory.DATA_SAVE: "#2A9D8F",       # patina
    AuditCategory.DATA_DELETE: "#EF4444",     # danger
    AuditCategory.RDO_CREATE: "#3B82F6",      # blue
    AuditCategory.REEMBOLSO_CREATE: "#8B5CF6",# purple
    AuditCategory.REPORT_GEN: "#06B6D4",      # cyan
    AuditCategory.AI_CHAT: "#F59E0B",         # amber
    AuditCategory.AI_INSIGHT: "#F59E0B",      # amber
    AuditCategory.ALERT_TRIGGER: "#EF4444",   # red
    AuditCategory.ALERT_CONFIG: "#C98B2A",    # copper
    AuditCategory.USER_MGMT: "#8B5CF6",       # purple
    AuditCategory.ERROR: "#EF4444",           # danger
    AuditCategory.SYSTEM: "#6B7280",          # gray
}


# ── Public API ────────────────────────────────────────────────────────────────


def audit_log(
    category: str,
    action: str,
    username: str = "",
    entity_type: str = "",
    entity_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "success",
    ip_address: str = "",
    client_id: str = "",
) -> None:
    """
    Fire-and-forget: grava um registro em `system_logs` sem bloquear a chamada.

    Parâmetros:
        category    — AuditCategory.XXX (string constant)
        action      — Descrição legível da ação, ex: "Usuário gustavo fez login"
        username    — Nome do usuário (current_user_name do GlobalState)
        entity_type — Tipo da entidade afetada: 'contratos', 'rdo', 'reembolso', etc.
        entity_id   — ID da entidade (UUID ou string)
        metadata    — Dict com dados extras: old_value, new_value, detalhes, etc.
        status      — 'success' | 'error' | 'warning'
        ip_address  — IP do cliente se disponível
    """
    # Snapshot all args before threading to avoid closure issues
    record: Dict[str, Any] = {
        "username": (username or "system")[:100],
        "action_category": str(category),
        "action": action[:500],
        "status": status,
    }
    if client_id:
        record["client_id"] = client_id
    if entity_type:
        record["entity_type"] = entity_type[:100]
    if entity_id:
        record["entity_id"] = str(entity_id)[:200]
    if metadata:
        record["metadata"] = metadata
    if ip_address:
        record["ip_address"] = ip_address[:60]

    def _write():
        try:
            from bomtempo.core.supabase_client import sb_insert
            sb_insert("system_logs", record)
        except Exception as exc:
            # Never let audit failures surface to the user
            logger.warning(f"audit_log write failed ({category}): {exc}")

    threading.Thread(target=_write, daemon=True, name=f"audit-{category}").start()


def audit_error(
    action: str,
    username: str = "",
    entity_type: str = "",
    error: Optional[Exception] = None,
    metadata: Optional[Dict[str, Any]] = None,
    client_id: str = "",
) -> None:
    """Atalho para logar erros com status='error'."""
    meta = dict(metadata or {})
    if error:
        meta["error_type"] = type(error).__name__
        meta["error_msg"] = str(error)[:400]
    audit_log(
        category=AuditCategory.ERROR,
        action=action,
        username=username,
        entity_type=entity_type,
        metadata=meta,
        status="error",
        client_id=client_id,
    )
