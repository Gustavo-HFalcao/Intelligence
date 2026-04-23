"""
Supabase REST API Client — Bomtempo Dashboard
Usa httpx (já disponível) para comunicar com a API PostgREST do Supabase.

Usa SUPABASE_SERVICE_KEY (service_role) — chave server-side que bypassa RLS.
Nunca é exposta ao browser (Reflex roda Python no servidor).
"""

import os
import threading
from typing import Any, Dict, List, Optional

import httpx
from bomtempo.core.config import Config
from dotenv import load_dotenv

from bomtempo.core.logging_utils import get_logger

load_dotenv()

logger = get_logger(__name__)

# ── Credentials ────────────────────────────────────────────────────────────────
# Service role key lida via Config (que lê do .env) — bypassa RLS com segurança (server-side only).
SUPABASE_URL = Config.SUPABASE_URL
SUPABASE_KEY = Config.SUPABASE_SERVICE_KEY
REST_BASE = f"{SUPABASE_URL}/rest/v1"
 
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error(
        "SUPABASE_URL ou SUPABASE_SERVICE_KEY não encontradas no .env. "
        "Verifique a configuração do projeto."
    )

# ── Connection Pool ────────────────────────────────────────────────────────────
# Singleton httpx.Client com keep-alive e connection pooling.
# Evita abrir um novo TCP a cada request (era o principal gargalo de latência).
_client_lock = threading.Lock()
_http_client: Optional[httpx.Client] = None

_LIMITS = httpx.Limits(
    max_connections=100,       # was 30 — supports 100+ concurrent users
    max_keepalive_connections=20,
    keepalive_expiry=20,   # conservative — Supabase closes idle connections early
)
_TIMEOUT = httpx.Timeout(timeout=20.0, connect=8.0)   # 20s for writes (was 10s)
_WRITE_TIMEOUT = httpx.Timeout(timeout=30.0, connect=8.0)  # heavier ops (upsert, upload)


def _get_client() -> httpx.Client:
    """Retorna o httpx.Client singleton thread-safe, criando se necessário."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        with _client_lock:
            if _http_client is None or _http_client.is_closed:
                _http_client = httpx.Client(limits=_LIMITS, timeout=_TIMEOUT)
                logger.info("🔌 HTTP connection pool criado (max_conn=100, keepalive=20s)")
    return _http_client


def _request_with_retry(method: str, url: str, max_retries: int = 2, **kwargs):
    """Execute an httpx request with automatic retry on connection-reset errors.

    Supabase/load-balancers can silently close idle keep-alive connections.
    When httpx tries to reuse such a connection it raises RemoteProtocolError /
    ConnectError.  One transparent retry with a fresh client resolves this.
    """
    global _http_client
    for attempt in range(max_retries + 1):
        try:
            client = _get_client()
            return getattr(client, method)(url, **kwargs)
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as exc:
            if attempt < max_retries:
                logger.warning(f"HTTP {method.upper()} connection error (attempt {attempt+1}), recycling pool: {exc}")
                with _client_lock:
                    try:
                        if _http_client and not _http_client.is_closed:
                            _http_client.close()
                    except Exception:
                        pass
                    _http_client = None
            else:
                raise


def _headers(prefer_return: bool = False) -> Dict[str, str]:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer_return:
        h["Prefer"] = "return=representation"
    return h


# ── CRUD helpers ───────────────────────────────────────────────────────────────


def sb_select_paginated(
    table: str,
    page: int = 1,
    limit: int = 50,
    filters: Dict[str, Any] = None,
    ilike_filters: Dict[str, str] = None,
    order: str = "created_at.desc",
    select: str = "*",
) -> tuple:
    """
    SELECT with server-side pagination using PostgREST Range header.
    Returns (rows: List[Dict], total_count: int).

    filters       — exact match: {"column": "value"}
    ilike_filters — case-insensitive LIKE: {"column": "pattern"}
    """
    try:
        offset = (page - 1) * limit
        range_end = offset + limit - 1
        h = _headers()
        h["Prefer"] = "count=exact"
        h["Range-Unit"] = "items"
        h["Range"] = f"{offset}-{range_end}"

        params: Dict[str, str] = {"select": select, "order": order}
        for k, v in (filters or {}).items():
            params[k] = f"eq.{v}"
        for k, v in (ilike_filters or {}).items():
            params[k] = f"ilike.*{v}*"

        resp = _request_with_retry(
            "get",
            f"{REST_BASE}/{table}",
            headers=h,
            params=params,
        )
        if resp.status_code in (200, 206):
            rows = resp.json()
            # Content-Range: 0-49/150
            total = 0
            cr = resp.headers.get("Content-Range", "")
            if "/" in cr:
                try:
                    total = int(cr.split("/")[1])
                except ValueError:
                    total = len(rows)
            else:
                total = len(rows)
            return rows, total
        logger.error(f"sb_select_paginated {table} → {resp.status_code}: {resp.text[:300]}")
        return [], 0
    except Exception as e:
        logger.error(f"sb_select_paginated {table} exception: {e}")
        return [], 0


def sb_select(
    table: str,
    filters: Dict[str, Any] = None,
    order: str = "",
    limit: int = 1000,
    raw_filters: Dict[str, str] = None,
) -> List[Dict]:
    """SELECT * FROM table WHERE ... ORDER BY ... LIMIT n.
    filters — exact match eq.{v}; raw_filters — passed verbatim (e.g. {"parent_id": "is.null"})"""
    try:
        params: Dict[str, str] = {"select": "*"}
        for k, v in (filters or {}).items():
            params[k] = f"eq.{v}"
        for k, v in (raw_filters or {}).items():
            params[k] = v
        if order:
            params["order"] = order
        params["limit"] = str(limit)

        resp = _request_with_retry(
            "get",
            f"{REST_BASE}/{table}",
            headers=_headers(),
            params=params,
        )
        if resp.status_code == 200:
            result = resp.json()
            logger.debug(f"Supabase SELECT {table}: {len(result)} linhas")
            return result
        logger.error(f"Supabase SELECT {table} → {resp.status_code}: {resp.text[:400]}")
        return []
    except Exception as e:
        logger.error(f"Supabase SELECT {table} exception: {e}")
        return []


def sb_insert(table: str, data: Dict[str, Any]) -> Optional[Dict]:
    """INSERT a row; returns the inserted record or None on failure."""
    try:
        resp = _request_with_retry(
            "post",
            f"{REST_BASE}/{table}",
            headers=_headers(prefer_return=True),
            json=data,
            timeout=_WRITE_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            result = resp.json()
            return result[0] if isinstance(result, list) and result else result
        err_msg = f"Supabase INSERT {table} → {resp.status_code}: {resp.text[:400]}"
        logger.error(err_msg)
        raise ValueError(err_msg)
    except Exception as e:
        logger.error(f"Supabase INSERT {table} exception: {e}")
        raise e


def sb_upsert(
    table: str,
    record: Dict[str, Any],
    on_conflict: str = "ID",
) -> Dict:
    """INSERT OR UPDATE a single record using PostgREST conflict resolution.

    If the row with the given `on_conflict` column value exists → UPDATE.
    If it doesn't exist → INSERT a new row.
    Unlike sb_update, never silently skips when the ID is not found.

    Returns {"upserted": 1} on success, raises ValueError on failure.
    """
    try:
        h = _headers()
        h["Prefer"] = "return=representation,resolution=merge-duplicates"
        resp = _request_with_retry(
            "post",
            f"{REST_BASE}/{table}",
            headers=h,
            params={"on_conflict": on_conflict},
            json=record,
            timeout=_WRITE_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            return {"upserted": 1}
        err_msg = f"Supabase UPSERT {table} → {resp.status_code}: {resp.text[:400]}"
        logger.error(err_msg)
        raise ValueError(err_msg)
    except Exception as e:
        logger.error(f"Supabase UPSERT {table} exception: {e}")
        raise e


def sb_bulk_upsert(
    table: str,
    records: list,
    on_conflict: str = "id",
    chunk_size: int = 100,
) -> Dict[str, Any]:
    """Bulk upsert up to `chunk_size` records per HTTP request using PostgREST array body.

    Dramatically faster than calling sb_upsert() in a loop:
      - 200 rows × 1 call each ≈ 200 round-trips (~10s)
      - 200 rows ÷ 100/chunk  =   2 round-trips (~100ms)

    Returns {"upserted": n, "errors": [...]}.
    """
    if not records:
        return {"upserted": 0, "errors": []}
    h = _headers()
    h["Prefer"] = "return=minimal,resolution=merge-duplicates"
    total_upserted = 0
    errors = []
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        try:
            resp = _request_with_retry(
                "post",
                f"{REST_BASE}/{table}",
                headers=h,
                params={"on_conflict": on_conflict},
                json=chunk,
                timeout=_WRITE_TIMEOUT,
            )
            if resp.status_code in (200, 201, 204):
                total_upserted += len(chunk)
            else:
                errors.append(f"chunk {i//chunk_size}: HTTP {resp.status_code} — {resp.text[:200]}")
                logger.error(f"sb_bulk_upsert {table} chunk {i//chunk_size} → {resp.status_code}: {resp.text[:300]}")
        except Exception as ex:
            errors.append(f"chunk {i//chunk_size}: {str(ex)[:120]}")
            logger.error(f"sb_bulk_upsert {table} chunk {i//chunk_size} exception: {ex}")
    return {"upserted": total_upserted, "errors": errors}


def sb_update(
    table: str,
    filters: Dict[str, Any],
    data: Dict[str, Any],
) -> bool:
    """PATCH rows matching filters with data."""
    try:
        params = {k: f"eq.{v}" for k, v in filters.items()}
        resp = _request_with_retry(
            "patch",
            f"{REST_BASE}/{table}",
            headers=_headers(),
            params=params,
            json=data,
            timeout=_WRITE_TIMEOUT,
        )
        if resp.status_code not in (200, 204):
            err_msg = f"Supabase UPDATE {table} → {resp.status_code}: {resp.text[:400]}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        return True
    except Exception as e:
        logger.error(f"Supabase UPDATE {table} exception: {e}")
        raise e


# ── Storage helpers ────────────────────────────────────────────────────────────


def sb_storage_ensure_bucket(bucket: str, public: bool = True) -> bool:
    """Create Storage bucket if it doesn't exist. Safe to call on every upload."""
    try:
        storage_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        # Check existence first
        resp = _request_with_retry(
            "get",
            f"{SUPABASE_URL}/storage/v1/bucket/{bucket}",
            headers=storage_headers,
        )
        if resp.status_code == 200:
            return True
        # Not found — create it
        create = _request_with_retry(
            "post",
            f"{SUPABASE_URL}/storage/v1/bucket",
            headers=storage_headers,
            json={"id": bucket, "name": bucket, "public": public},
        )
        if create.status_code in (200, 201):
            logger.info(f"✅ Storage bucket criado: {bucket}")
            return True
        logger.error(f"sb_storage_ensure_bucket {bucket} → {create.status_code}: {create.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"sb_storage_ensure_bucket {bucket}: {e}")
        return False


def sb_storage_upload(
    bucket: str, path: str, file_bytes: bytes, content_type: str = "application/octet-stream"
) -> Optional[str]:
    """
    Upload de arquivo para o Supabase Storage.
    Retorna a URL pública permanente ou None em caso de erro.

    Padrão de uso:
        url = sb_storage_upload("rdo-pdfs", f"{id_rdo}.pdf", pdf_bytes, "application/pdf")
        # Armazene url no banco — funciona independente de restarts/deploys.

    Para imagens de NF, fotos de obra etc.:
        url = sb_storage_upload("reembolso-fotos", f"{id_reembolso}/nota.jpg", img_bytes, "image/jpeg")
    """
    try:
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",  # sobrescreve se já existir
        }
        resp = _request_with_retry(
            "post", upload_url, headers=headers, content=file_bytes,
            timeout=httpx.Timeout(60.0, connect=8.0),
        )
        if resp.status_code in (200, 201):
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
            logger.info(f"✅ Storage upload: {bucket}/{path} → {public_url}")
            return public_url
        logger.error(f"Storage upload {bucket}/{path} → {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as e:
        logger.error(f"Storage upload exception: {e}")
        return None


def sb_delete(table: str, filters: Dict[str, Any]) -> bool:
    """DELETE rows matching filters."""
    try:
        params = {k: f"eq.{v}" for k, v in filters.items()}
        resp = _request_with_retry(
            "delete",
            f"{REST_BASE}/{table}",
            headers=_headers(),
            params=params,
            timeout=_WRITE_TIMEOUT,
        )
        ok = resp.status_code in (200, 204)
        if not ok:
            logger.error(f"Supabase DELETE {table} → HTTP {resp.status_code}: {resp.text[:300]}")
        return ok
    except Exception as e:
        logger.error(f"Supabase DELETE {table} exception: {e}")
        return False


def sb_rpc(fn_name: str, params: Dict[str, Any] = None) -> Any:
    """Call a Supabase RPC (Stored Procedure)."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
        resp = _request_with_retry(
            "post",
            url,
            headers=_headers(),
            json=params or {},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Supabase RPC {fn_name} → {resp.status_code}: {resp.text[:400]}")
        return None
    except Exception as e:
        logger.error(f"Supabase RPC {fn_name} exception: {e}")
        return None


# ── Async Client ───────────────────────────────────────────────────────────────
# httpx.AsyncClient singleton — para uso em handlers async Reflex sem run_in_executor.
# Elimina overhead de thread pool para operações de DB em handlers async diretos.
#
# Uso:
#   from bomtempo.core.supabase_client import async_sb_select, async_sb_update
#   rows = await async_sb_select("contratos", filters={"client_id": tenant_id})
#
# Quando usar async vs sync:
#   - async_sb_*: handlers async sem @rx.event(background=True) — não usa thread pool
#   - sb_*:       dentro de @rx.event(background=True) ou executors — OK chamar sync

_async_http_client: Optional[httpx.AsyncClient] = None


def _get_async_client() -> httpx.AsyncClient:
    """Retorna AsyncClient singleton, criando se necessário."""
    global _async_http_client
    if _async_http_client is None or _async_http_client.is_closed:
        _async_http_client = httpx.AsyncClient(limits=_LIMITS, timeout=_TIMEOUT)
        logger.info("🔌 Async HTTP connection pool criado")
    return _async_http_client


async def async_sb_select(
    table: str,
    filters: Dict[str, Any] = None,
    order: str = "",
    limit: int = 1000,
    raw_filters: Dict[str, str] = None,
) -> List[Dict]:
    """Async SELECT — use em handlers async para não bloquear o event loop."""
    try:
        params: Dict[str, str] = {"select": "*"}
        for k, v in (filters or {}).items():
            params[k] = f"eq.{v}"
        for k, v in (raw_filters or {}).items():
            params[k] = v
        if order:
            params["order"] = order
        params["limit"] = str(limit)

        resp = await _get_async_client().get(
            f"{REST_BASE}/{table}",
            headers=_headers(),
            params=params,
        )
        if resp.status_code == 200:
            result = resp.json()
            logger.debug(f"async SELECT {table}: {len(result)} linhas")
            return result
        logger.error(f"async SELECT {table} → {resp.status_code}: {resp.text[:400]}")
        return []
    except Exception as e:
        logger.error(f"async SELECT {table} exception: {e}")
        return []


async def async_sb_insert(table: str, data: Dict[str, Any]) -> Optional[Dict]:
    """Async INSERT — retorna o registro inserido ou None em caso de falha."""
    try:
        resp = await _get_async_client().post(
            f"{REST_BASE}/{table}",
            headers=_headers(prefer_return=True),
            json=data,
        )
        if resp.status_code in (200, 201):
            result = resp.json()
            return result[0] if isinstance(result, list) and result else result
        err_msg = f"async INSERT {table} → {resp.status_code}: {resp.text[:400]}"
        logger.error(err_msg)
        raise ValueError(err_msg)
    except Exception as e:
        logger.error(f"async INSERT {table} exception: {e}")
        raise


async def async_sb_update(
    table: str,
    filters: Dict[str, Any],
    data: Dict[str, Any],
) -> bool:
    """Async PATCH rows matching filters."""
    try:
        params = {k: f"eq.{v}" for k, v in filters.items()}
        resp = await _get_async_client().patch(
            f"{REST_BASE}/{table}",
            headers=_headers(),
            params=params,
            json=data,
        )
        if resp.status_code not in (200, 204):
            err_msg = f"async UPDATE {table} → {resp.status_code}: {resp.text[:400]}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        return True
    except Exception as e:
        logger.error(f"async UPDATE {table} exception: {e}")
        raise


async def async_sb_delete(table: str, filters: Dict[str, Any]) -> bool:
    """Async DELETE rows matching filters."""
    try:
        params = {k: f"eq.{v}" for k, v in filters.items()}
        resp = await _get_async_client().delete(
            f"{REST_BASE}/{table}",
            headers=_headers(),
            params=params,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"async DELETE {table} exception: {e}")
        return False
