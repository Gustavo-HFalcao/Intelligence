"""
Redis Cache — tenant-namespaced, port direto de bomtempo/core/redis_cache.py.

Namespace: t:{tenant_id_safe}:{resource}
  Exemplo:  t:abc12345:data_all

Se REDIS_URL não estiver configurado ou Redis não responder, todas as funções
retornam None/False silenciosamente — o chamador cai no fallback (pickle / Supabase).
"""

import os
import pickle
from typing import Any, Optional

from backend.core.config import Config as settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

_redis_client = None
_redis_available: Optional[bool] = None


def _get_client():
    global _redis_client, _redis_available

    if _redis_available is False:
        return None

    if not settings.REDIS_URL:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis as _redis

        extra_kwargs: dict = {}
        if settings.REDIS_URL.startswith("rediss://"):
            extra_kwargs["ssl_cert_reqs"] = None

        client = _redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
            **extra_kwargs,
        )
        client.ping()
        _redis_client = client
        _redis_available = True
        logger.info(f"Redis conectado: {settings.REDIS_URL.split('@')[-1]}")
    except Exception as exc:
        _redis_available = False
        logger.warning(f"Redis não disponível ({exc}) — usando pickle file cache como fallback")
    return _redis_client


def _tenant_key(tenant_id: str, resource: str) -> str:
    safe_id = (tenant_id[:12] if tenant_id else "global").replace("-", "")
    return f"t:{safe_id}:{resource}"


def cache_get(tenant_id: str, key: str) -> Optional[Any]:
    r = _get_client()
    if r is None:
        return None
    try:
        raw = r.get(_tenant_key(tenant_id, key))
        return pickle.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug(f"cache_get {key}: {exc}")
        return None


def cache_set(tenant_id: str, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> bool:
    r = _get_client()
    if r is None:
        return False
    try:
        r.setex(_tenant_key(tenant_id, key), ttl, pickle.dumps(value))
        return True
    except Exception as exc:
        logger.debug(f"cache_set {key}: {exc}")
        return False


def cache_invalidate(tenant_id: str, key: str) -> bool:
    r = _get_client()
    if r is None:
        return False
    try:
        deleted = r.delete(_tenant_key(tenant_id, key))
        if deleted:
            logger.info(f"Cache Redis invalidado: {key} tenant={tenant_id[:8]}")
        return bool(deleted)
    except Exception as exc:
        logger.debug(f"cache_invalidate {key}: {exc}")
        return False


def cache_invalidate_all(tenant_id: str) -> int:
    r = _get_client()
    if r is None:
        return 0
    try:
        safe_id = (tenant_id[:12] if tenant_id else "global").replace("-", "")
        keys = r.keys(f"t:{safe_id}:*")
        if keys:
            count = r.delete(*keys)
            logger.info(f"Cache Redis: {count} chaves removidas para tenant={tenant_id[:8]}")
            return count
        return 0
    except Exception as exc:
        logger.debug(f"cache_invalidate_all: {exc}")
        return 0


def is_redis_available() -> bool:
    return _get_client() is not None


def cache_stats(tenant_id: str) -> dict:
    r = _get_client()
    if r is None:
        return {"available": False, "url_configured": bool(settings.REDIS_URL)}
    try:
        safe_id = (tenant_id[:12] if tenant_id else "global").replace("-", "")
        keys = r.keys(f"t:{safe_id}:*")
        return {
            "available": True,
            "tenant_keys": len(keys),
            "keys": [k.decode() if isinstance(k, bytes) else k for k in keys],
        }
    except Exception:
        return {"available": False, "error": "ping failed"}
