"""
Audit Logger — FastAPI version (ported from bomtempo/core/audit_logger.py)

Fire-and-forget: every call spawns a daemon thread so the request/response
cycle is never blocked by database I/O.

Usage:
    from backend.core.audit import audit_log, AuditCategory

    audit_log(
        category=AuditCategory.RDO_CREATE,
        action="RDO submetido",
        username=user["login"],
        entity_type="rdo_master",
        entity_id=rdo_id,
        client_id=client_id,
    )
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.core.logging import get_logger

logger = get_logger(__name__)


class AuditCategory:
    LOGIN             = "LOGIN"
    LOGOUT            = "LOGOUT"
    DATA_EDIT         = "DATA_EDIT"
    DATA_UPLOAD       = "DATA_UPLOAD"
    DATA_SAVE         = "DATA_SAVE"
    DATA_DELETE       = "DATA_DELETE"
    RDO_CREATE        = "RDO_CREATE"
    REEMBOLSO_CREATE  = "REEMBOLSO_CREATE"
    REPORT_GEN        = "REPORT_GEN"
    AI_CHAT           = "AI_CHAT"
    AI_INSIGHT        = "AI_INSIGHT"
    ALERT_TRIGGER     = "ALERT_TRIGGER"
    ALERT_CONFIG      = "ALERT_CONFIG"
    USER_MGMT         = "USER_MGMT"
    ERROR             = "ERROR"
    SYSTEM            = "SYSTEM"


ALL_CATEGORIES = [
    AuditCategory.LOGIN, AuditCategory.LOGOUT, AuditCategory.DATA_EDIT,
    AuditCategory.DATA_UPLOAD, AuditCategory.DATA_SAVE, AuditCategory.DATA_DELETE,
    AuditCategory.RDO_CREATE, AuditCategory.REEMBOLSO_CREATE, AuditCategory.REPORT_GEN,
    AuditCategory.AI_CHAT, AuditCategory.AI_INSIGHT, AuditCategory.ALERT_TRIGGER,
    AuditCategory.ALERT_CONFIG, AuditCategory.USER_MGMT, AuditCategory.ERROR,
    AuditCategory.SYSTEM,
]

CATEGORY_LABELS: Dict[str, str] = {
    AuditCategory.LOGIN:            "Login",
    AuditCategory.LOGOUT:           "Logout",
    AuditCategory.DATA_EDIT:        "Edição de Dados",
    AuditCategory.DATA_UPLOAD:      "Upload de Dados",
    AuditCategory.DATA_SAVE:        "Salvar no Banco",
    AuditCategory.DATA_DELETE:      "Exclusão de Registro",
    AuditCategory.RDO_CREATE:       "RDO Criado",
    AuditCategory.REEMBOLSO_CREATE: "Reembolso Submetido",
    AuditCategory.REPORT_GEN:       "Relatório Gerado",
    AuditCategory.AI_CHAT:          "Chat IA",
    AuditCategory.AI_INSIGHT:       "Insight IA",
    AuditCategory.ALERT_TRIGGER:    "Alerta Disparado",
    AuditCategory.ALERT_CONFIG:     "Config. de Alertas",
    AuditCategory.USER_MGMT:        "Gestão de Usuários",
    AuditCategory.ERROR:            "Erro",
    AuditCategory.SYSTEM:           "Sistema",
}

CATEGORY_COLORS: Dict[str, str] = {
    AuditCategory.LOGIN:            "#2A9D8F",
    AuditCategory.LOGOUT:           "#889999",
    AuditCategory.DATA_EDIT:        "#C98B2A",
    AuditCategory.DATA_UPLOAD:      "#E0A63B",
    AuditCategory.DATA_SAVE:        "#2A9D8F",
    AuditCategory.DATA_DELETE:      "#EF4444",
    AuditCategory.RDO_CREATE:       "#3B82F6",
    AuditCategory.REEMBOLSO_CREATE: "#8B5CF6",
    AuditCategory.REPORT_GEN:       "#06B6D4",
    AuditCategory.AI_CHAT:          "#F59E0B",
    AuditCategory.AI_INSIGHT:       "#F59E0B",
    AuditCategory.ALERT_TRIGGER:    "#EF4444",
    AuditCategory.ALERT_CONFIG:     "#C98B2A",
    AuditCategory.USER_MGMT:        "#8B5CF6",
    AuditCategory.ERROR:            "#EF4444",
    AuditCategory.SYSTEM:           "#6B7280",
}


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
    Fire-and-forget audit log entry.  Never blocks the request.
    All parameters are snapshot-copied before threading.
    """
    record: Dict[str, Any] = {
        "username":        (username or "system")[:100],
        "action_category": str(category),
        "action":          action[:500],
        "status":          status,
        "created_at":      datetime.now(timezone.utc).isoformat(),
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

    def _write() -> None:
        try:
            from backend.integrations.supabase import sb_insert
            sb_insert("system_logs", record)
        except Exception as exc:
            logger.warning(f"audit_log write failed ({category}): {exc}")

    threading.Thread(target=_write, daemon=True, name=f"audit-{category[:20]}").start()


def audit_error(
    action: str,
    username: str = "",
    entity_type: str = "",
    error: Optional[Exception] = None,
    metadata: Optional[Dict[str, Any]] = None,
    client_id: str = "",
) -> None:
    meta = dict(metadata or {})
    if error:
        meta["error_type"] = type(error).__name__
        meta["error_msg"]  = str(error)[:400]
    audit_log(
        category=AuditCategory.ERROR,
        action=action,
        username=username,
        entity_type=entity_type,
        metadata=meta,
        status="error",
        client_id=client_id,
    )
