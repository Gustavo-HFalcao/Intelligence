"""
Rate Limiter — in-process com Redis quando disponível

Protege handlers críticos contra abuso por tenant sem necessidade de Nginx.
Usa sliding window counter no Redis (quando configurado) ou fallback in-process.

Por que não Nginx nesse ambiente:
  - 1 CPU + 1GB RAM: adicionar Nginx aumenta overhead de memória sem necessidade
  - Com 1 worker e async I/O, Reflex já lida bem com concorrência
  - Rate limiting no app level é suficiente para multi-tenant com usuários legítimos

Uso em handlers Reflex:
    from bomtempo.core.rate_limiter import rate_limit_check

    @rx.event(background=True)
    async def submit_rdo(self):
        async with self:
            tenant = self.current_client_id
            user = self.current_user_name

        allowed, retry_after = rate_limit_check(tenant, "rdo_submit", limit=5, window=60)
        if not allowed:
            async with self:
                self.submit_error = f"Muitas submissões. Aguarde {retry_after}s."
            return
        # ... continua normalmente

Limites sugeridos por ação:
    rdo_submit:    5 por minuto por tenant
    login:         10 por minuto por IP/usuário
    geocode:       3 por minuto por tenant
    pdf_generate:  3 por minuto por tenant
    ia_analyze:    5 por minuto por tenant
"""

import os
import time
import threading
from typing import Tuple

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

# ── Fallback in-process (quando Redis não disponível) ─────────────────────────
# Dict: { "tenant:action:window_bucket" -> count }
# Thread-safe via lock global simples (1 worker = 1 processo)
_in_process_store: dict = {}
_store_lock = threading.Lock()


def _in_process_check(key: str, limit: int, window: int) -> Tuple[bool, int]:
    """Sliding window counter em memória. Suficiente para 1 worker."""
    bucket = int(time.time() // window)
    full_key = f"{key}:{bucket}"

    with _store_lock:
        # Limpa buckets antigos periodicamente para evitar memory leak
        old_bucket = bucket - 2
        old_keys = [k for k in _in_process_store if k.endswith(f":{old_bucket}")]
        for k in old_keys:
            del _in_process_store[k]

        count = _in_process_store.get(full_key, 0) + 1
        _in_process_store[full_key] = count

    if count > limit:
        retry_after = window - (int(time.time()) % window)
        return False, retry_after
    return True, 0


# ── Redis sliding window (quando disponível) ──────────────────────────────────

def _redis_check(tenant_id: str, action: str, limit: int, window: int) -> Tuple[bool, int]:
    """
    Redis sliding window counter com namespace por tenant.
    Mais preciso que in-process porque sobrevive a restarts.
    """
    try:
        from bomtempo.core.redis_cache import _get_client
        r = _get_client()
        if r is None:
            return _in_process_check(f"{tenant_id}:{action}", limit, window)

        safe_tenant = (tenant_id[:12] if tenant_id else "global").replace("-", "")
        bucket = int(time.time() // window)
        key = f"rl:{safe_tenant}:{action}:{bucket}"

        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window * 2)  # 2x window para garantir TTL
        results = pipe.execute()
        count = results[0]

        if count > limit:
            retry_after = window - (int(time.time()) % window)
            logger.warning(
                f"[RateLimit] tenant={tenant_id[:8]} action={action} "
                f"count={count}/{limit} — bloqueado por {retry_after}s"
            )
            return False, retry_after
        return True, 0

    except Exception as exc:
        logger.debug(f"Redis rate limit falhou, usando in-process: {exc}")
        return _in_process_check(f"{tenant_id}:{action}", limit, window)


# ── API pública ───────────────────────────────────────────────────────────────

def rate_limit_check(
    tenant_id: str,
    action: str,
    limit: int = 10,
    window: int = 60,
) -> Tuple[bool, int]:
    """
    Verifica se o tenant está dentro do limite de taxa para a ação.

    Args:
        tenant_id: ID do tenant (client_id)
        action:    Identificador da ação (ex: "rdo_submit", "pdf_generate")
        limit:     Máximo de requisições no período
        window:    Período em segundos

    Returns:
        (allowed: bool, retry_after: int)
        - allowed=True: chamada permitida
        - allowed=False: limite atingido; retry_after=segundos até próxima janela
    """
    if not tenant_id:
        return True, 0  # sem tenant_id (não autenticado) — não aplica limite aqui

    return _redis_check(tenant_id, action, limit, window)


# ── Limites padrão da plataforma ─────────────────────────────────────────────
# Importe e use diretamente nos handlers críticos.

LIMITS = {
    "rdo_submit":    (5,  60),   # 5 RDOs por minuto por tenant
    "pdf_generate":  (3,  60),   # 3 PDFs por minuto
    "ia_analyze":    (5,  60),   # 5 análises IA por minuto
    "geocode":       (3,  60),   # 3 geocodings por minuto
    "login":         (10, 60),   # 10 tentativas de login por minuto
    "email_send":    (3, 300),   # 3 emails por 5 minutos
}


def check(tenant_id: str, action: str) -> Tuple[bool, int]:
    """
    Versão simplificada usando os limites padrão definidos em LIMITS.

    Uso:
        allowed, retry = check(self.current_client_id, "rdo_submit")
        if not allowed:
            yield rx.toast(f"Aguarde {retry}s antes de submeter outro RDO.")
            return
    """
    limit, window = LIMITS.get(action, (20, 60))
    return rate_limit_check(tenant_id, action, limit, window)
