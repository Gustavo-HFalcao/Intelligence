"""
Logging estruturado — Bomtempo Dashboard

Mantém total compatibilidade com uso existente via `get_logger(name)`.

Adiciona `get_bound_logger(name, **ctx)` para logs com contexto fixo de
tenant_id / user_id — essencial para rastrear problemas em plataforma multi-tenant.

Formato:
  - Desenvolvimento (padrão):  texto humano legível
  - Produção (LOG_FORMAT=json): JSON uma linha por registro — filtrável no Loki/Datadog/CloudWatch
"""
import json
import logging
import os
import sys
from typing import Any


_JSON_FORMAT = os.getenv("LOG_FORMAT", "text").lower() == "json"


# ── Formatadores ──────────────────────────────────────────────────────────────

class _TextFormatter(logging.Formatter):
    """Formato texto com contexto de tenant/user quando disponível."""

    FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    def __init__(self):
        super().__init__(self.FMT, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        # Adiciona contexto extra ao final da linha se presente
        ctx_parts = []
        for key in ("tenant_id", "user_id", "action"):
            val = getattr(record, key, None)
            if val:
                ctx_parts.append(f"{key}={val}")
        if ctx_parts:
            return f"{base} [{', '.join(ctx_parts)}]"
        return base


class _JsonFormatter(logging.Formatter):
    """
    Formato JSON — uma linha por registro.
    Filtrável por tenant_id/user_id/action em qualquer agregador de logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts":     self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        # Contexto extra de tenant/user
        for key in ("tenant_id", "user_id", "action", "trace_id"):
            val = getattr(record, key, None)
            if val is not None:
                data[key] = val
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


# ── Logger adapter com contexto fixo ─────────────────────────────────────────

class _BoundLogger(logging.LoggerAdapter):
    """
    Logger com contexto fixo (tenant_id, user_id, etc.) propagado em todos os registros.

    Uso:
        log = get_bound_logger(__name__, tenant_id=self.current_client_id,
                               user_id=self.current_user_name)
        log.info("projeto salvo")
        log.error("falha ao salvar", extra={"action": "save_projeto"})
    """

    def process(self, msg: str, kwargs: dict):
        extra = kwargs.setdefault("extra", {})
        # Injeta contexto do adapter sem sobrescrever extras explícitos
        for k, v in self.extra.items():
            extra.setdefault(k, v)
        return msg, kwargs


# ── Setup principal ───────────────────────────────────────────────────────────

def setup_logger() -> logging.Logger:
    """
    Configura o logger raiz 'bomtempo'.
    Idempotente — seguro chamar múltiplas vezes.
    """
    root = logging.getLogger("bomtempo")
    if root.handlers:
        return root  # já configurado

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter() if _JSON_FORMAT else _TextFormatter())

    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False
    return root


# ── API pública ───────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """
    Retorna logger para o módulo — compatível com todo uso existente.

    Uso:
        logger = get_logger(__name__)
        logger.info("mensagem")
    """
    return logging.getLogger(f"bomtempo.{name}")


def get_bound_logger(name: str, **ctx) -> _BoundLogger:
    """
    Retorna logger com contexto fixo de tenant/user para rastreabilidade.

    Uso em handlers Reflex:
        log = get_bound_logger(__name__,
                               tenant_id=self.current_client_id,
                               user_id=self.current_user_name)
        log.info("RDO submetido")
        log.error("falha ao gerar PDF", extra={"action": "generate_pdf"})

    Em JSON mode, cada linha terá tenant_id e user_id — filtrável diretamente.
    """
    base = logging.getLogger(f"bomtempo.{name}")
    return _BoundLogger(base, ctx)
