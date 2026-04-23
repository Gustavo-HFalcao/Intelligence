"""
Redis Cache — tenant-namespaced para Bomtempo Platform

Substitui o pickle file cache do DataLoader quando REDIS_URL está configurado.
Se Redis não estiver disponível, todas as funções retornam None/False silenciosamente
— o código de chamada cai automaticamente no fallback (Supabase direto).

Namespace: t:{tenant_id_safe}:{resource}
  Exemplo: t:abc12345:data_all  (dados completos de um tenant)
           t:abc12345:contratos (apenas contratos, para invalidação granular)

Por que Redis em vez de arquivo pickle mesmo com 1 worker:
  1. Cache sobrevive a restarts do processo (zero cold-start penalty)
  2. TTL é gerenciado pelo Redis (sem lógica manual de mtime)
  3. Base pronta para multi-worker no futuro (Fase 4)
  4. RAM Redis (~50MB) é muito mais eficiente que DataFrames em memória de processo

Configuração:
  Adicione ao .env:
    REDIS_URL=redis://localhost:6379/0
  Ou use Redis Cloud / Upstash para deploy em produção.

Se REDIS_URL não estiver no .env, o sistema opera normalmente com pickle file cache.
"""

import os
import pickle
from typing import Any, Optional

import bomtempo.core.config  # noqa: F401 — garante que load_dotenv() rode antes de os.getenv
from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

# ── Configuração ──────────────────────────────────────────────────────────────

REDIS_URL: str = os.getenv("REDIS_URL", "")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hora default

_redis_client = None
_redis_available: Optional[bool] = None  # None = não testado ainda


def _get_client():
    """
    Retorna cliente Redis singleton, ou None se não configurado/disponível.
    Testa a conexão uma única vez e memoriza o resultado.
    """
    global _redis_client, _redis_available

    if _redis_available is False:
        return None  # falha anterior — não tenta de novo até reiniciar

    if not REDIS_URL:
        return None  # não configurado

    if _redis_client is not None:
        return _redis_client

    try:
        import redis as _redis
        # ssl_cert_reqs=None necessário para Upstash (rediss://) e alguns Redis Cloud
        # from_url propaga ssl_cert_reqs automaticamente para conexões TLS
        extra_kwargs: dict = {}
        if REDIS_URL.startswith("rediss://"):
            extra_kwargs["ssl_cert_reqs"] = None
        client = _redis.from_url(
            REDIS_URL,
            decode_responses=False,  # bytes — usamos pickle para serializar
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
            **extra_kwargs,
        )
        client.ping()  # valida conexão imediatamente
        _redis_client = client
        _redis_available = True
        logger.info(f"✅ Redis conectado: {REDIS_URL.split('@')[-1]}")  # não loga senha
    except Exception as exc:
        _redis_available = False
        logger.warning(
            f"⚠️ Redis não disponível ({exc}) — usando pickle file cache como fallback. "
            f"Para ativar Redis, configure REDIS_URL no .env"
        )
    return _redis_client


# ── Namespace ─────────────────────────────────────────────────────────────────

def _tenant_key(tenant_id: str, resource: str) -> str:
    """
    Gera chave Redis com namespace explícito por tenant.
    Colisão entre tenants é arquiteturalmente impossível.
    """
    safe_id = (tenant_id[:12] if tenant_id else "global").replace("-", "")
    return f"t:{safe_id}:{resource}"


# ── API pública ───────────────────────────────────────────────────────────────

def cache_get(tenant_id: str, key: str) -> Optional[Any]:
    """Lê do cache Redis. Retorna None se não disponível ou expirado."""
    r = _get_client()
    if r is None:
        return None
    try:
        raw = r.get(_tenant_key(tenant_id, key))
        if raw is None:
            return None
        return pickle.loads(raw)
    except Exception as exc:
        logger.debug(f"cache_get {key}: {exc}")
        return None


def cache_set(tenant_id: str, key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Salva no cache Redis com TTL. Retorna False se Redis não disponível."""
    r = _get_client()
    if r is None:
        return False
    try:
        r.setex(_tenant_key(tenant_id, key), ttl, pickle.dumps(value))
        logger.debug(f"cache_set {key} tenant={tenant_id[:8]} ttl={ttl}s")
        return True
    except Exception as exc:
        logger.debug(f"cache_set {key}: {exc}")
        return False


def cache_invalidate(tenant_id: str, key: str) -> bool:
    """Remove uma chave específica do cache do tenant."""
    r = _get_client()
    if r is None:
        return False
    try:
        deleted = r.delete(_tenant_key(tenant_id, key))
        if deleted:
            logger.info(f"🗑️ Cache Redis invalidado: {key} tenant={tenant_id[:8]}")
        return bool(deleted)
    except Exception as exc:
        logger.debug(f"cache_invalidate {key}: {exc}")
        return False


def cache_invalidate_all(tenant_id: str) -> int:
    """
    Remove TODOS os keys de um tenant — use após operações que afetam múltiplas entidades.
    Retorna o número de chaves removidas.
    """
    r = _get_client()
    if r is None:
        return 0
    try:
        safe_id = (tenant_id[:12] if tenant_id else "global").replace("-", "")
        pattern = f"t:{safe_id}:*"
        keys = r.keys(pattern)
        if keys:
            count = r.delete(*keys)
            logger.info(f"🗑️ Cache Redis: {count} chaves removidas para tenant={tenant_id[:8]}")
            return count
        return 0
    except Exception as exc:
        logger.debug(f"cache_invalidate_all: {exc}")
        return 0


def is_redis_available() -> bool:
    """Retorna True se Redis está conectado e funcional."""
    return _get_client() is not None


def cache_stats(tenant_id: str) -> dict:
    """Diagnóstico: retorna informações sobre o cache do tenant."""
    r = _get_client()
    if r is None:
        return {"available": False, "url_configured": bool(REDIS_URL)}
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
