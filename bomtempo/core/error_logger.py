"""
Error Logger — Bomtempo Intelligence
======================================
Fire-and-forget debug/error logging to Supabase `app_errors` table.

Separado do audit_logger (que é para ações de usuário/auditoria).
Este módulo captura erros lógicos, exceções inesperadas e falhas de backend
para troubleshooting em produção — consultável diretamente no painel Supabase.

SQL para criar a tabela (rodar no SQL Editor do novo banco):
------------------------------------------------------------
    CREATE TABLE app_errors (
        id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        created_at      TIMESTAMPTZ NOT NULL    DEFAULT NOW(),
        severity        TEXT        NOT NULL    DEFAULT 'error',
            -- 'warning' | 'error' | 'critical'
        error_type      TEXT,           -- nome da classe da exceção (ex: 'ValueError')
        module          TEXT,           -- módulo Python onde ocorreu
        function_name   TEXT,           -- nome da função
        error_message   TEXT,           -- str(exception) ou mensagem livre
        traceback       TEXT,           -- stack trace completo
        username        TEXT DEFAULT '',-- usuário logado se disponível
        extra_context   JSONB           -- dados adicionais livres
    );

    CREATE INDEX idx_ae_created_at  ON app_errors (created_at DESC);
    CREATE INDEX idx_ae_severity    ON app_errors (severity);
    CREATE INDEX idx_ae_module      ON app_errors (module);
    CREATE INDEX idx_ae_error_type  ON app_errors (error_type);
------------------------------------------------------------

Uso típico em event handlers:
    from bomtempo.core.error_logger import log_error, log_warning

    try:
        result = some_risky_operation()
    except Exception as e:
        log_error(e, module=__name__, function_name="my_handler", username=self.current_user_name)
        raise  # ou tratar localmente

Instalar hooks globais (feito automaticamente em bomtempo.py):
    from bomtempo.core.error_logger import install_global_handler
    install_global_handler()
"""

import sys
import threading
import traceback as tb
from typing import Any, Dict, Optional

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

_TABLE = "app_errors"


# ── Public helpers ─────────────────────────────────────────────────────────────


def log_error(
    error: Optional[Exception] = None,
    module: str = "",
    function_name: str = "",
    username: str = "",
    severity: str = "error",
    extra_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Fire-and-forget: grava erro em `app_errors` sem bloquear o caller.

    Uso em except blocks:
        except Exception as e:
            log_error(e, module=__name__, function_name="minha_funcao", username=self.current_user_name)
    """
    try:
        exc_type = type(error).__name__ if error else "UnknownError"
        exc_msg = str(error)[:2000] if error else ""
        exc_tb = ""
        if error and error.__traceback__:
            exc_tb = "".join(tb.format_exception(type(error), error, error.__traceback__))[:5000]

        # Auto-detect module/function from caller stack when not provided
        if not module or not function_name:
            try:
                frame = sys._getframe(1)
                if not module:
                    module = frame.f_globals.get("__name__", "unknown")
                if not function_name:
                    function_name = frame.f_code.co_name
            except Exception:
                pass

        _write_async(
            severity=severity,
            error_type=exc_type[:100],
            module=(module or "unknown")[:200],
            function_name=(function_name or "unknown")[:100],
            error_message=exc_msg,
            traceback=exc_tb,
            username=(username or "")[:100],
            extra_context=extra_context,
        )
    except Exception:
        pass  # Never let the logger itself crash


def log_warning(
    message: str,
    module: str = "",
    function_name: str = "",
    username: str = "",
    extra_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Atalho para severity='warning' sem exceção."""
    try:
        if not module or not function_name:
            try:
                frame = sys._getframe(1)
                if not module:
                    module = frame.f_globals.get("__name__", "unknown")
                if not function_name:
                    function_name = frame.f_code.co_name
            except Exception:
                pass

        _write_async(
            severity="warning",
            error_type="Warning",
            module=(module or "unknown")[:200],
            function_name=(function_name or "unknown")[:100],
            error_message=message[:2000],
            traceback="",
            username=(username or "")[:100],
            extra_context=extra_context,
        )
    except Exception:
        pass


def install_global_handler() -> None:
    """
    Instala hooks globais para capturar exceções não tratadas.
    Chamar uma vez em bomtempo.py antes de `app = rx.App(...)`.

    Captura:
    - sys.excepthook   — exceções na thread principal
    - threading.excepthook — exceções em threads daemon
    """
    _original_excepthook = sys.excepthook
    _original_thread_excepthook = threading.excepthook

    def _global_excepthook(exc_type, exc_value, exc_tb_obj):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            _original_excepthook(exc_type, exc_value, exc_tb_obj)
            return
        tb_str = "".join(tb.format_exception(exc_type, exc_value, exc_tb_obj))[:5000]
        _write_async(
            severity="critical",
            error_type=exc_type.__name__[:100],
            module="__main__",
            function_name="unhandled_exception",
            error_message=str(exc_value)[:2000],
            traceback=tb_str,
            username="system",
        )
        _original_excepthook(exc_type, exc_value, exc_tb_obj)

    def _thread_excepthook(args):
        if args.exc_type in (SystemExit, None):
            return
        tb_str = "".join(
            tb.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )[:5000]
        thread_name = getattr(args.thread, "name", "unknown") if args.thread else "unknown"
        _write_async(
            severity="error",
            error_type=(args.exc_type.__name__ if args.exc_type else "Unknown")[:100],
            module=f"thread:{thread_name}"[:200],
            function_name="unhandled_thread_exception",
            error_message=(str(args.exc_value) if args.exc_value else "")[:2000],
            traceback=tb_str,
            username="system",
        )
        _original_thread_excepthook(args)

    sys.excepthook = _global_excepthook
    threading.excepthook = _thread_excepthook
    logger.info("🛡️ error_logger: hooks globais instalados (sys.excepthook + threading.excepthook)")


# ── Internal ───────────────────────────────────────────────────────────────────


def _write_async(
    severity: str,
    error_type: str,
    module: str,
    function_name: str,
    error_message: str,
    traceback: str,
    username: str,
    extra_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Despacha escrita em daemon thread — nunca bloqueia o caller."""
    record: Dict[str, Any] = {
        "severity": severity,
        "error_type": error_type,
        "module": module,
        "function_name": function_name,
        "error_message": error_message,
        "traceback": traceback,
        "username": username,
    }
    if extra_context:
        record["extra_context"] = extra_context

    def _write():
        try:
            from bomtempo.core.supabase_client import sb_insert
            sb_insert(_TABLE, record)
        except Exception as exc:
            # Log to local logger only — never raise from here
            logger.warning(f"error_logger: write failed ({error_type}): {exc}")

    threading.Thread(target=_write, daemon=True, name=f"errlog-{severity}").start()
