"""
Supabase REST API Client — Bomtempo Backend (FastAPI)
Portado diretamente de bomtempo/core/supabase_client.py.
Sem alterações de lógica — apenas mudança de import path.
"""

import threading
from typing import Any, Dict, List, Optional

import httpx

from backend.core.config import Config

SUPABASE_URL = Config.SUPABASE_URL
SUPABASE_KEY = Config.SUPABASE_SERVICE_KEY
REST_BASE = f"{SUPABASE_URL}/rest/v1"

# ── Connection Pool ────────────────────────────────────────────────────────────
_client_lock = threading.Lock()
_http_client: Optional[httpx.Client] = None

_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=20,
)
_TIMEOUT = httpx.Timeout(timeout=20.0, connect=8.0)
_WRITE_TIMEOUT = httpx.Timeout(timeout=30.0, connect=8.0)


def _get_client() -> httpx.Client:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        with _client_lock:
            if _http_client is None or _http_client.is_closed:
                _http_client = httpx.Client(limits=_LIMITS, timeout=_TIMEOUT)
    return _http_client


def _request_with_retry(method: str, url: str, max_retries: int = 2, **kwargs):
    global _http_client
    for attempt in range(max_retries + 1):
        try:
            client = _get_client()
            return getattr(client, method)(url, **kwargs)
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as exc:
            if attempt < max_retries:
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

        resp = _request_with_retry("get", f"{REST_BASE}/{table}", headers=h, params=params)
        if resp.status_code in (200, 206):
            rows = resp.json()
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
        return [], 0
    except Exception:
        return [], 0


def sb_select(
    table: str,
    filters: Dict[str, Any] = None,
    order: str = "",
    limit: int = 1000,
    raw_filters: Dict[str, str] = None,
    client_id: Optional[str] = None,
) -> List[Dict]:
    try:
        merged_filters: Dict[str, Any] = dict(filters or {})
        if client_id:
            merged_filters["client_id"] = client_id
        params: Dict[str, str] = {"select": "*"}
        for k, v in merged_filters.items():
            if v is not None:
                params[k] = f"eq.{v}"
        for k, v in (raw_filters or {}).items():
            params[k] = v
        if order:
            params["order"] = order
        params["limit"] = str(limit)

        resp = _request_with_retry("get", f"{REST_BASE}/{table}", headers=_headers(), params=params)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def sb_insert(table: str, data: Dict[str, Any], client_id: Optional[str] = None) -> Optional[Dict]:
    payload = dict(data)
    if client_id and "client_id" not in payload:
        payload["client_id"] = client_id
    resp = _request_with_retry(
        "post", f"{REST_BASE}/{table}",
        headers=_headers(prefer_return=True),
        json=payload,
        timeout=_WRITE_TIMEOUT,
    )
    if resp.status_code in (200, 201):
        result = resp.json()
        return result[0] if isinstance(result, list) and result else result
    raise ValueError(f"Supabase INSERT {table} → {resp.status_code}: {resp.text[:400]}")


def sb_upsert(table: str, record: Dict[str, Any], on_conflict: str = "id") -> Dict:
    h = _headers()
    h["Prefer"] = "return=representation,resolution=merge-duplicates"
    resp = _request_with_retry(
        "post", f"{REST_BASE}/{table}",
        headers=h,
        params={"on_conflict": on_conflict},
        json=record,
        timeout=_WRITE_TIMEOUT,
    )
    if resp.status_code in (200, 201):
        return {"upserted": 1}
    raise ValueError(f"Supabase UPSERT {table} → {resp.status_code}: {resp.text[:400]}")


def sb_bulk_upsert(
    table: str,
    records: list,
    on_conflict: str = "id",
    chunk_size: int = 100,
) -> Dict[str, Any]:
    if not records:
        return {"upserted": 0, "errors": []}
    h = _headers()
    h["Prefer"] = "return=minimal,resolution=merge-duplicates"
    total_upserted = 0
    errors = []
    for i in range(0, len(records), chunk_size):
        chunk = records[i: i + chunk_size]
        try:
            resp = _request_with_retry(
                "post", f"{REST_BASE}/{table}",
                headers=h,
                params={"on_conflict": on_conflict},
                json=chunk,
                timeout=_WRITE_TIMEOUT,
            )
            if resp.status_code in (200, 201, 204):
                total_upserted += len(chunk)
            else:
                errors.append(f"chunk {i // chunk_size}: HTTP {resp.status_code}")
        except Exception as ex:
            errors.append(f"chunk {i // chunk_size}: {str(ex)[:120]}")
    return {"upserted": total_upserted, "errors": errors}


def sb_update(table: str, filters: Dict[str, Any], data: Dict[str, Any], client_id: Optional[str] = None) -> bool:
    merged_filters = dict(filters)
    if client_id:
        merged_filters["client_id"] = client_id
    params = {k: f"eq.{v}" for k, v in merged_filters.items()}
    h = _headers()
    h["Prefer"] = "return=representation"
    resp = _request_with_retry(
        "patch", f"{REST_BASE}/{table}",
        headers=h,
        params=params,
        json=data,
        timeout=_WRITE_TIMEOUT,
    )
    if resp.status_code not in (200, 204):
        raise ValueError(f"Supabase UPDATE {table} → {resp.status_code}: {resp.text[:400]}")
    if resp.status_code == 200:
        result = resp.json()
        return result[0] if isinstance(result, list) and result else result
    return True


def sb_delete(table: str, filters: Dict[str, Any]) -> bool:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    resp = _request_with_retry(
        "delete", f"{REST_BASE}/{table}",
        headers=_headers(),
        params=params,
        timeout=_WRITE_TIMEOUT,
    )
    return resp.status_code in (200, 204)


def sb_rpc(fn_name: str, params: Dict[str, Any] = None) -> Any:
    try:
        resp = _request_with_retry(
            "post", f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
            headers=_headers(),
            json=params or {},
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


# ── Storage helpers ────────────────────────────────────────────────────────────

def sb_storage_upload(
    bucket: str, path: str, file_bytes: bytes, content_type: str = "application/octet-stream"
) -> Optional[str]:
    try:
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        resp = _request_with_retry(
            "post", upload_url, headers=headers, content=file_bytes,
            timeout=httpx.Timeout(60.0, connect=8.0),
        )
        if resp.status_code in (200, 201):
            return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
        return None
    except Exception:
        return None


def sb_storage_ensure_bucket(bucket: str, public: bool = True) -> bool:
    try:
        storage_headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        resp = _request_with_retry("get", f"{SUPABASE_URL}/storage/v1/bucket/{bucket}", headers=storage_headers)
        if resp.status_code == 200:
            return True
        create = _request_with_retry(
            "post", f"{SUPABASE_URL}/storage/v1/bucket",
            headers=storage_headers,
            json={"id": bucket, "name": bucket, "public": public},
        )
        return create.status_code in (200, 201)
    except Exception:
        return False


# ── Async Client ───────────────────────────────────────────────────────────────

_async_http_client: Optional[httpx.AsyncClient] = None


def _get_async_client() -> httpx.AsyncClient:
    global _async_http_client
    if _async_http_client is None or _async_http_client.is_closed:
        _async_http_client = httpx.AsyncClient(limits=_LIMITS, timeout=_TIMEOUT)
    return _async_http_client


async def async_sb_select(
    table: str,
    filters: Dict[str, Any] = None,
    order: str = "",
    limit: int = 1000,
    raw_filters: Dict[str, str] = None,
) -> List[Dict]:
    try:
        params: Dict[str, str] = {"select": "*"}
        for k, v in (filters or {}).items():
            params[k] = f"eq.{v}"
        for k, v in (raw_filters or {}).items():
            params[k] = v
        if order:
            params["order"] = order
        params["limit"] = str(limit)

        resp = await _get_async_client().get(f"{REST_BASE}/{table}", headers=_headers(), params=params)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


async def async_sb_insert(table: str, data: Dict[str, Any]) -> Optional[Dict]:
    resp = await _get_async_client().post(
        f"{REST_BASE}/{table}",
        headers=_headers(prefer_return=True),
        json=data,
    )
    if resp.status_code in (200, 201):
        result = resp.json()
        return result[0] if isinstance(result, list) and result else result
    raise ValueError(f"async INSERT {table} → {resp.status_code}: {resp.text[:400]}")


async def async_sb_update(table: str, filters: Dict[str, Any], data: Dict[str, Any]) -> bool:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    resp = await _get_async_client().patch(
        f"{REST_BASE}/{table}",
        headers=_headers(),
        params=params,
        json=data,
    )
    if resp.status_code not in (200, 204):
        raise ValueError(f"async UPDATE {table} → {resp.status_code}: {resp.text[:400]}")
    return True


async def async_sb_delete(table: str, filters: Dict[str, Any]) -> bool:
    try:
        params = {k: f"eq.{v}" for k, v in filters.items()}
        resp = await _get_async_client().delete(f"{REST_BASE}/{table}", headers=_headers(), params=params)
        return resp.status_code in (200, 204)
    except Exception:
        return False
