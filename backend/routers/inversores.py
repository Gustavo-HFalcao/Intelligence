"""
Inversores router — /api/inversores
Sistema de Inteligência Energética: gestão de inversores + sync em tempo real + análise.

Plataformas suportadas (padrão horizontal — cada uma é um adapter isolado):
  shinemonitor | growatt | solarman
  (próximas: sungrow, huawei — só adicionar adapter + entry em PLATFORMS)
"""

import asyncio
import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from backend.integrations.supabase import (
    sb_delete, sb_insert, sb_select, sb_update,
)
from backend.middleware.auth import get_current_user
from backend.middleware.tenant import get_current_tenant

router = APIRouter(prefix="/api/inversores", tags=["inversores"])

# ── Platform catalogue (horizontal scale: add new platforms here) ─────────────

PLATFORMS: Dict[str, Dict] = {
    "shinemonitor": {
        "slug": "shinemonitor",
        "name": "ShineMonitor / Eybond",
        "app_names": ["ShineMonitor", "SmartClient", "DESS Monitor", "Elgin Solar", "Renovigi"],
        "auth_type": "sha1_sign",
        "market_coverage": "Elgin, Renovigi, Solarmust, Sofar, Easun e +190 marcas via Eybond",
        "status": "active",
        "fields_form": [
            {"key": "usr",     "label": "Usuário (login do portal)",    "type": "text",     "required": True},
            {"key": "pwd",     "label": "Senha",                        "type": "password", "required": True},
            {"key": "pn",      "label": "PN do Datalogger",             "type": "text",     "required": True,
             "hint": "Encontrado na página de dispositivos do portal"},
            {"key": "sn",      "label": "Número de Série do Inversor",  "type": "text",     "required": True},
            {"key": "devcode", "label": "Devcode",                      "type": "text",     "required": True,
             "hint": "Ex: 518 — encontrado na página de dispositivos"},
        ],
        "capabilities_default": {
            "has_temperature": True, "dc_strings": 4, "phases": 3,
            "has_battery": False, "has_history": True,
        },
    },
    "growatt": {
        "slug": "growatt",
        "name": "Growatt ShineServer",
        "app_names": ["ShinePhone", "Growatt", "ShineServer"],
        "auth_type": "sha256_cookie",
        "market_coverage": "Inversores Growatt exclusivamente",
        "status": "active",
        "fields_form": [
            {"key": "usr",      "label": "Usuário (email ou login)", "type": "text",     "required": True},
            {"key": "pwd",      "label": "Senha",                    "type": "password", "required": True},
            {"key": "plant_id", "label": "Plant ID (opcional)",      "type": "text",     "required": False,
             "hint": "Deixe em branco para descoberta automática"},
            {"key": "sn",       "label": "Número de Série",          "type": "text",     "required": True},
        ],
        "capabilities_default": {
            "has_temperature": True, "dc_strings": 2, "phases": 1,
            "has_battery": False, "has_history": True,
        },
    },
    "solarman": {
        "slug": "solarman",
        "name": "Solarman / IGEN / Deye",
        "app_names": ["SolarmanPV", "Solarman Smart", "IGEN", "Deye Smart"],
        "auth_type": "sha256_bearer",
        "market_coverage": "Deye (~17% mercado BR) + 190 outras marcas via datalogger Solarman",
        "status": "active",
        "fields_form": [
            {"key": "usr",        "label": "E-mail da conta",         "type": "text",     "required": True},
            {"key": "pwd",        "label": "Senha",                   "type": "password", "required": True},
            {"key": "app_id",     "label": "App ID",                  "type": "text",     "required": True,
             "hint": "Solicite em service@solarmanpv.com"},
            {"key": "app_secret", "label": "App Secret",              "type": "password", "required": True,
             "hint": "Recebido junto com o App ID"},
            {"key": "sn",         "label": "Serial do Inversor",      "type": "text",     "required": True,
             "hint": "Número de série do inversor (não do logger)"},
        ],
        "capabilities_default": {
            "has_temperature": True, "dc_strings": 4, "phases": 3,
            "has_battery": False, "has_history": True,
        },
    },
}

# ── Credential helpers ────────────────────────────────────────────────────────

def _enc(data: dict) -> str:
    return base64.b64encode(json.dumps(data).encode()).decode()


def _dec(encoded: str) -> dict:
    try:
        return json.loads(base64.b64decode(encoded).decode())
    except Exception:
        return {}


# ── Format helpers ────────────────────────────────────────────────────────────

def _fmt_inversor(r: dict) -> dict:
    caps = r.get("capabilities") or {}
    if isinstance(caps, str):
        try:
            caps = json.loads(caps)
        except Exception:
            caps = {}
    meta = r.get("plant_meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    slug = r.get("platform_slug", "")
    return {
        "id":               r.get("id"),
        "client_id":        r.get("client_id"),
        "platform_slug":    slug,
        "platform_name":    PLATFORMS.get(slug, {}).get("name", slug),
        "alias":            r.get("alias") or "Inversor sem nome",
        "plant_name":       r.get("plant_name") or "",
        "nominal_power_kw": float(r.get("nominal_power_kw") or 0),
        "install_date":     (r.get("install_date") or "")[:10],
        "location":         r.get("location") or "",
        "plant_id":         r.get("plant_id") or "",
        "pn":               r.get("pn") or "",
        "sn":               r.get("sn") or "",
        "devcode":          r.get("devcode") or "",
        "devaddr":          r.get("devaddr") or "1",
        "mode":             r.get("mode") or "api",
        "status":           r.get("status") or "pending",
        "capabilities":     caps,
        "plant_meta":       meta,
        "last_sync_at":     r.get("last_sync_at") or "",
        "created_at":       (r.get("created_at") or "")[:10],
    }


def _fmt_reading(r: dict) -> dict:
    def _fv(k):
        v = r.get(k)
        return float(v) if v is not None else None

    return {
        "id":                r.get("id"),
        "inverter_id":       r.get("inverter_id"),
        "ts":                r.get("ts") or r.get("created_at") or "",
        "active_power_w":    _fv("active_power_w"),
        "energy_today_kwh":  _fv("energy_today_kwh"),
        "energy_total_kwh":  _fv("energy_total_kwh"),
        "energy_year_kwh":   _fv("energy_year_kwh"),
        "grid_frequency_hz": _fv("grid_frequency_hz"),
        "temp_inverter_c":   _fv("temp_inverter_c"),
        "dc_voltage_1_v":    _fv("dc_voltage_1_v"),
        "dc_voltage_2_v":    _fv("dc_voltage_2_v"),
        "dc_voltage_3_v":    _fv("dc_voltage_3_v"),
        "dc_voltage_4_v":    _fv("dc_voltage_4_v"),
        "dc_current_1_a":    _fv("dc_current_1_a"),
        "dc_current_2_a":    _fv("dc_current_2_a"),
        "dc_current_3_a":    _fv("dc_current_3_a"),
        "dc_current_4_a":    _fv("dc_current_4_a"),
        "ac_voltage_a_v":    _fv("ac_voltage_a_v"),
        "ac_voltage_b_v":    _fv("ac_voltage_b_v"),
        "ac_voltage_c_v":    _fv("ac_voltage_c_v"),
        "ac_current_a_a":    _fv("ac_current_a_a"),
        "ac_current_b_a":    _fv("ac_current_b_a"),
        "ac_current_c_a":    _fv("ac_current_c_a"),
        "battery_soc_pct":   _fv("battery_soc_pct"),
        "battery_power_w":   _fv("battery_power_w"),
        "battery_voltage_v": _fv("battery_voltage_v"),
        "status":            r.get("status") or "normal",
        "raw_data":          r.get("raw_data") or {},
    }


# ── Auth token cache (in-memory; survives hot reload) ─────────────────────────

_token_cache: Dict[str, Dict] = {}

# ── Backfill task tracker (in-memory; keyed by inversor_id) ──────────────────

_backfill_tasks: Dict[str, Dict] = {}


def _get_cached_auth(inversor_id: str) -> Optional[Dict]:
    entry = _token_cache.get(inversor_id)
    if not entry:
        return None
    if time.time() > entry.get("expire_ts", 0) - 300:
        _token_cache.pop(inversor_id, None)
        return None
    return entry


def _set_cached_auth(inversor_id: str, auth: Dict):
    _token_cache[inversor_id] = auth


# ── Platform sync adapters ────────────────────────────────────────────────────

def _sync_shinemonitor(inversor: dict, creds: dict) -> dict:
    from backend.integrations.shinemonitor import authenticate, get_latest_reading, get_plant_info

    inv_id = inversor["id"]
    auth = _get_cached_auth(inv_id)
    if not auth:
        auth = authenticate(creds["usr"], creds["pwd"])
        _set_cached_auth(inv_id, auth)

    reading = get_latest_reading(
        token=auth["token"],
        secret=auth["secret"],
        pn=inversor.get("pn") or creds.get("pn", ""),
        sn=inversor.get("sn") or creds.get("sn", ""),
        devcode=inversor.get("devcode") or creds.get("devcode", ""),
        devaddr=inversor.get("devaddr") or creds.get("devaddr", "1"),
    )

    # Rich plant metadata enrichment via queryPlantInfo
    # Re-run whenever coords are missing/invalid (coords_valid=False triggers geocode fallback)
    current_meta = inversor.get("plant_meta") or {}
    if isinstance(current_meta, str):
        try:
            current_meta = json.loads(current_meta)
        except Exception:
            current_meta = {}

    needs_enrich = not current_meta.get("coords_valid") or not inversor.get("plant_name")
    if needs_enrich:
        try:
            pid = str(inversor.get("plant_id") or "")
            if pid:
                info = get_plant_info(auth["token"], auth["secret"], pid)
                if info:
                    # If API coords are invalid, try geocoding from city name
                    if not info.get("coords_valid") and info.get("city"):
                        try:
                            import httpx as _httpx
                            city = info["city"].title()
                            province = info.get("province", "").title()
                            query = f"{city}, {province}, Brazil" if province else f"{city}, Brazil"
                            geo = _httpx.get(
                                "https://nominatim.openstreetmap.org/search",
                                params={"q": query, "format": "json", "limit": 1},
                                headers={"User-Agent": "BomtempoIntelligence/2.0"},
                                timeout=8.0,
                            ).json()
                            if geo:
                                info["lat"] = float(geo[0]["lat"])
                                info["lon"] = float(geo[0]["lon"])
                                info["coords_valid"] = True
                                info["coords_source"] = "nominatim"
                        except Exception:
                            pass

                    update: dict = {"plant_meta": info}
                    if info.get("name"):
                        update["plant_name"] = info["name"]
                    if info.get("nominal_power_kw"):
                        update["nominal_power_kw"] = info["nominal_power_kw"]
                    if info.get("install_date"):
                        update["install_date"] = info["install_date"]
                    if info.get("address") or info.get("city"):
                        loc_parts = filter(None, [info.get("address"), info.get("city"), info.get("province")])
                        update["location"] = ", ".join(loc_parts) or inversor.get("location", "")
                    sb_update("client_inverters", {"id": inv_id}, update)
        except Exception:
            pass

    return reading


def _sync_growatt(inversor: dict, creds: dict) -> dict:
    from backend.integrations.growatt import authenticate, get_latest_reading

    inv_id = inversor["id"]
    auth = _get_cached_auth(inv_id)
    if not auth:
        auth = authenticate(creds["usr"], creds["pwd"])
        _set_cached_auth(inv_id, auth)

    return get_latest_reading(
        cookies=auth["cookies"],
        inverter_sn=inversor.get("sn") or creds.get("sn", ""),
    )


def _sync_solarman(inversor: dict, creds: dict) -> dict:
    from backend.integrations.solarman import authenticate, get_latest_reading

    inv_id = inversor["id"]
    auth = _get_cached_auth(inv_id)
    if not auth:
        auth = authenticate(
            creds["usr"], creds["pwd"],
            app_id=creds.get("app_id") or None,
            app_secret=creds.get("app_secret") or None,
        )
        _set_cached_auth(inv_id, auth)

    device_sn = inversor.get("sn") or creds.get("sn", "")
    reading = get_latest_reading(token=auth["token"], device_sn=device_sn)

    # Enrich with station metadata on first successful read
    if not inversor.get("plant_name") and inversor.get("plant_id"):
        try:
            from backend.integrations.solarman import get_station_detail
            detail = get_station_detail(auth["token"], inversor["plant_id"])
            meta = {
                "address":               detail.get("locationAddress", ""),
                "lat":                   detail.get("locationLat"),
                "lng":                   detail.get("locationLng"),
                "installed_capacity_kwp": float(detail.get("installedCapacity", 0) or 0),
                "timezone":              detail.get("timezone", ""),
            }
            sb_update("client_inverters", {"id": inv_id}, {
                "plant_name":       detail.get("name", ""),
                "location":         detail.get("locationAddress", ""),
                "nominal_power_kw": meta["installed_capacity_kwp"],
                "plant_meta":       meta,
            })
        except Exception:
            pass

    return reading


def _do_sync(inversor: dict) -> dict:
    slug = inversor.get("platform_slug", "")
    creds = _dec(inversor.get("credentials_enc", ""))
    if slug == "shinemonitor":
        return _sync_shinemonitor(inversor, creds)
    if slug == "growatt":
        return _sync_growatt(inversor, creds)
    if slug == "solarman":
        return _sync_solarman(inversor, creds)
    raise ValueError(f"Plataforma '{slug}' não suportada para sync automático.")


def _save_reading(inversor_id: str, reading: dict, min_interval_s: int = 240) -> dict:
    """
    Persist a reading. Skips insert if a reading already exists within min_interval_s
    to avoid duplicates from overlapping sync cycles.
    """
    ts_now = datetime.now(timezone.utc).isoformat()

    # Deduplication: skip if last reading is too recent
    recent = sb_select("inverter_readings", filters={"inverter_id": inversor_id},
                       order="ts.desc", limit=1) or []
    if recent:
        try:
            last_ts_str = recent[0].get("ts", "")
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            age_s = (datetime.now(timezone.utc) - last_ts).total_seconds()
            if age_s < min_interval_s:
                return _fmt_reading(recent[0])
        except Exception:
            pass

    raw_data = reading.pop("raw_data", {})
    record: Dict[str, Any] = {
        "inverter_id": inversor_id,
        "ts": ts_now,
        "raw_data": raw_data,
        **{k: v for k, v in reading.items() if k != "status"},
        "status": reading.get("status", "normal"),
    }
    saved = sb_insert("inverter_readings", record)
    sb_update("client_inverters", {"id": inversor_id}, {
        "status": "active",
        "last_sync_at": ts_now,
    })
    return _fmt_reading(saved) if saved else record


# ── Background periodic sync ──────────────────────────────────────────────────

async def run_periodic_sync(interval_seconds: int = 600):
    """
    Async background task: sync all active API-mode inversors every interval.
    Called from main.py lifespan. Errors are isolated per inversor.
    """
    await asyncio.sleep(30)  # give the app time to fully start
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            _sync_all_inversors_background()
        except asyncio.CancelledError:
            break
        except Exception:
            pass


def _auto_backfill_phase1(inv: dict) -> None:
    """Spawn a daemon thread to run Phase 1 backfill on first successful sync."""
    import threading
    inv_id = inv["id"]
    slug   = inv.get("platform_slug", "")
    if slug not in ("shinemonitor", "solarman"):
        return

    _backfill_tasks[inv_id] = {
        "status": "running", "phase": "1", "months": 6, "auto": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "days_done": 0, "days_total": 0, "phase1": None, "phase2": None,
    }

    def _run():
        from backend.integrations.backfill import backfill_shine_phase1, backfill_solarman_phase1
        creds = _dec(inv.get("credentials_enc", ""))
        try:
            if slug == "shinemonitor":
                from backend.integrations.shinemonitor import authenticate
                auth = authenticate(creds["usr"], creds["pwd"])
                ins, sk = backfill_shine_phase1(inv, auth, months=6)
            else:
                from backend.integrations.solarman import authenticate
                auth = authenticate(
                    creds["usr"], creds["pwd"],
                    app_id=creds.get("app_id"), app_secret=creds.get("app_secret"),
                )
                ins, sk = backfill_solarman_phase1(inv, auth, months=6)

            finished = datetime.now(timezone.utc).isoformat()
            _backfill_tasks[inv_id].update({
                "status": "done", "finished_at": finished,
                "phase1": {"inserted": ins, "skipped": sk},
            })
            fresh = (sb_select("client_inverters", filters={"id": inv_id}, limit=1) or [{}])[0]
            meta  = fresh.get("plant_meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            meta.setdefault("backfill", {})
            meta["backfill"].update({
                "done": True, "months": 6, "finished_at": finished,
                "phase1": {"inserted": ins, "skipped": sk},
            })
            sb_update("client_inverters", {"id": inv_id}, {"plant_meta": meta})
        except Exception as exc:
            _backfill_tasks[inv_id].update({
                "status": "error", "error": str(exc)[:300],
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })

    threading.Thread(target=_run, daemon=True).start()


def _sync_all_inversors_background():
    """Sync all active/pending API inversors (called from background task)."""
    from backend.integrations.alerts import run_alert_checks

    rows = sb_select(
        "client_inverters",
        filters={"mode": "api"},
        order="last_sync_at.asc",
        limit=100,
    ) or []

    for inv in rows:
        if inv.get("status") in ("pending",) and not inv.get("credentials_enc"):
            continue
        try:
            reading = _do_sync(inv)
            saved = _save_reading(inv["id"], reading)

            # Alert checks after each successful sync
            recent = sb_select("inverter_readings", filters={"inverter_id": inv["id"]},
                               order="ts.desc", limit=10) or []
            run_alert_checks(inv, last_reading=saved, recent_readings=recent)

            # Auto-trigger Phase 1 backfill on first successful sync (once per inverter)
            inv_meta = inv.get("plant_meta") or {}
            if isinstance(inv_meta, str):
                try:
                    inv_meta = json.loads(inv_meta)
                except Exception:
                    inv_meta = {}
            _bt_status = _backfill_tasks.get(inv["id"], {}).get("status")
            if not inv_meta.get("backfill", {}).get("done") and _bt_status not in ("running", "done"):
                _auto_backfill_phase1(inv)

        except Exception as e:
            err_msg = str(e)[:200]
            # Mark as error but keep trying
            if "requer app_id" not in err_msg.lower():
                sb_update("client_inverters", {"id": inv["id"]}, {"status": "error"})
            # Still check offline alert when sync fails
            try:
                from backend.integrations.alerts import check_offline
                recent = sb_select("inverter_readings", filters={"inverter_id": inv["id"]},
                                   order="ts.desc", limit=1) or []
                check_offline(inv, recent[0] if recent else None)
            except Exception:
                pass


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/platforms")
async def get_platforms() -> Dict[str, Any]:
    """Lista plataformas suportadas e seus formulários de cadastro."""
    return {"platforms": list(PLATFORMS.values())}


@router.get("")
async def list_inversores(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Lista todos os inversores do tenant com KPIs agregados."""
    filters: Dict[str, Any] = {}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("client_inverters", filters=filters, order="platform_slug.asc", limit=200) or []
    inversores = [_fmt_inversor(r) for r in rows]

    active = [i for i in inversores if i["status"] == "active"]
    total_power_kw = sum((i["nominal_power_kw"] or 0) for i in inversores)

    return {
        "inversores": inversores,
        "total": len(inversores),
        "active": len(active),
        "total_nominal_power_kw": total_power_kw,
        "platforms_used": list({i["platform_slug"] for i in inversores}),
    }


@router.get("/sync-all")
async def trigger_sync_all(
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Dispara sync de todos os inversores ativos do tenant (executa em background)."""
    filters: Dict[str, Any] = {"mode": "api"}
    if client_id:
        filters["client_id"] = client_id
    rows = sb_select("client_inverters", filters=filters, limit=100) or []

    results = []
    for inv in rows:
        creds = _dec(inv.get("credentials_enc", ""))
        if not creds.get("usr"):
            results.append({"id": inv["id"], "alias": inv.get("alias"), "status": "skipped", "reason": "sem credenciais"})
            continue
        try:
            reading = _do_sync(inv)
            saved = _save_reading(inv["id"], reading)
            results.append({"id": inv["id"], "alias": inv.get("alias"), "status": "synced",
                            "active_power_w": saved.get("active_power_w")})
        except Exception as e:
            results.append({"id": inv["id"], "alias": inv.get("alias"), "status": "error", "reason": str(e)[:120]})

    return {"results": results, "total": len(results)}


def _fetch_irradiance(lat: float, lon: float, target: str) -> Dict[str, Any]:
    """
    Busca irradiância diária (kWh/m²) para lat/lon/date.
    Fonte primária: NASA POWER (histórico, ~6 dias lag).
    Fallback: Open-Meteo (até ontem/hoje, previsão inclusa).
    """
    import httpx

    date_compact = target.replace("-", "")

    # 1. NASA POWER — dados históricos validados
    try:
        r = httpx.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={
                "parameters": "ALLSKY_SFC_SW_DWN",
                "community":  "RE",
                "longitude":  lon,
                "latitude":   lat,
                "start":      date_compact,
                "end":        date_compact,
                "format":     "JSON",
            },
            timeout=12.0,
        )
        val = (
            r.json()
            .get("properties", {})
            .get("parameter", {})
            .get("ALLSKY_SFC_SW_DWN", {})
            .get(date_compact)
        )
        if val is not None and float(val) >= 0:
            return {"available": True, "irradiance_kwh_m2": round(float(val), 3), "source": "nasa_power"}
    except Exception:
        pass

    # 2. Open-Meteo fallback — shortwave_radiation_sum em MJ/m² ÷ 3.6 = kWh/m²
    try:
        r2 = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":   lat,
                "longitude":  lon,
                "daily":      "shortwave_radiation_sum",
                "past_days":  10,
                "forecast_days": 1,
                "timezone":   "auto",
            },
            timeout=10.0,
        )
        daily = r2.json().get("daily", {})
        times = daily.get("time", [])
        rads  = daily.get("shortwave_radiation_sum", [])
        for t, v in zip(times, rads):
            if t == target and v is not None and float(v) >= 0:
                kwh = round(float(v) / 3.6, 3)
                return {"available": True, "irradiance_kwh_m2": kwh, "source": "open_meteo"}
    except Exception:
        pass

    return {"available": False, "reason": "sem_dados_para_data"}


@router.get("/{inversor_id}/irradiance")
async def get_irradiance(
    inversor_id: str,
    date: str = Query(None, description="YYYY-MM-DD; omitir = hoje"),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Irradiância diária — NASA POWER primário, Open-Meteo fallback.
    Retorna available=False se coords ausentes ou sem dado disponível.
    """
    from datetime import date as _date

    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Inversor não encontrado")

    inv = rows[0]
    meta = inv.get("plant_meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    if not meta.get("coords_valid") or meta.get("lat") is None:
        return {"available": False, "reason": "coords_pending", "inversor_id": inversor_id}

    target = date or str(_date.today())
    result = _fetch_irradiance(float(meta["lat"]), float(meta["lon"]), target)
    return {**result, "date": target, "lat": meta["lat"], "lon": meta["lon"],
            "coords_source": meta.get("coords_source", "portal")}


@router.get("/{inversor_id}/performance")
async def get_performance(
    inversor_id: str,
    date: str = Query(None, description="YYYY-MM-DD; omitir = hoje"),
    efficiency: float = Query(0.80, description="Eficiência do sistema (0–1)"),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Performance Ratio, desvio e perda financeira para um dia.
    E_prevista = irradiância × kWp × eficiência.
    Só calcula PR com irradiância válida e energia_real > 0.5 kWh.
    """
    from datetime import date as _date, datetime as _dt, timezone, timedelta

    BRT = timezone(timedelta(hours=-3))

    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Inversor não encontrado")

    inv = rows[0]
    meta = inv.get("plant_meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    target = date or _date.today().isoformat()
    kWp = float(inv.get("nominal_power_kw") or 0)
    tariff = float(meta.get("tariff_kwh") or 0) or 0.8  # fallback R$0,80

    # Supabase sb_select doesn't support range filters natively — fetch recent and filter in Python.
    # 1 day × 10-min interval = 144 readings max; fetch 300 to be safe.
    readings = sb_select(
        "inverter_readings",
        filters={"inverter_id": inversor_id},
        order="ts.desc",
        limit=300,
    ) or []

    def _brt_date(ts_str: str) -> str:
        try:
            return _dt.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(BRT).date().isoformat()
        except Exception:
            return ""

    day_readings = [r for r in readings if _brt_date(r.get("ts") or "") == target]
    e_real = max((float(r.get("energy_today_kwh") or 0) for r in day_readings), default=0.0)

    # Fetch irradiance (NASA primary, Open-Meteo fallback)
    if meta.get("coords_valid") and meta.get("lat") is not None and kWp > 0:
        irr_data = _fetch_irradiance(float(meta["lat"]), float(meta["lon"]), target)
    elif not meta.get("coords_valid"):
        irr_data = {"available": False, "reason": "coords_pending"}
    else:
        irr_data = {"available": False, "reason": "no_kwp"}

    # Flag Open-Meteo data for today/future as forecast (not measured)
    import datetime as _datetime_mod
    if irr_data.get("source") == "open_meteo" and target >= _datetime_mod.date.today().isoformat():
        irr_data["is_forecast"] = True

    # Calculate performance metrics
    pr = desvio_pct = e_prevista = perda_rs = None
    status = "sem_dados"

    if irr_data.get("available") and kWp > 0 and e_real >= 0.5:
        e_prevista = round(irr_data["irradiance_kwh_m2"] * kWp * efficiency, 2)
        if e_prevista > 0:
            pr = round(e_real / e_prevista, 3)
            desvio_pct = round((e_real - e_prevista) / e_prevista * 100, 1)
            perda_rs = round(max(0.0, e_prevista - e_real) * tariff, 2)
            if pr >= 0.85:
                status = "normal"
            elif pr >= 0.70:
                status = "atencao"
            else:
                status = "critico"
    elif e_real < 0.5:
        status = "sem_geracao"

    return {
        "date":              target,
        "inversor_id":       inversor_id,
        "e_real_kwh":        round(e_real, 2),
        "e_prevista_kwh":    e_prevista,
        "pr":                pr,
        "desvio_pct":        desvio_pct,
        "perda_rs":          perda_rs,
        "status":            status,
        "tariff_kwh":        tariff,
        "kWp":               kWp,
        "efficiency":        efficiency,
        "irradiance":        irr_data,
        "readings_count":    len(day_readings),
    }


@router.get("/{inversor_id}/pr-history")
async def get_pr_history(
    inversor_id: str,
    days: int = Query(30, ge=7, le=90, description="Número de dias retroativos"),
    efficiency: float = Query(0.80),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    PR diário dos últimos N dias.
    Irradiância: NASA POWER (batch, single request) + Open-Meteo fallback para datas recentes.
    Energia real: max(energy_today_kwh) por dia BRT.
    """
    import httpx
    from datetime import date as _date, datetime as _dt, timedelta, timezone as _tz

    BRT = _tz(timedelta(hours=-3))

    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Inversor não encontrado")

    inv = rows[0]
    meta = inv.get("plant_meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    kWp = float(inv.get("nominal_power_kw") or 0)
    tariff = float(meta.get("tariff_kwh") or 0) or 0.8

    if not meta.get("coords_valid") or not meta.get("lat") or kWp <= 0:
        return {"available": False, "reason": "coords_or_kwp_missing", "days": [], "summary": {}}

    lat = float(meta["lat"])
    lon = float(meta["lon"])

    today_brt = _dt.now(BRT).date()
    start_date = today_brt - timedelta(days=days - 1)

    # ── Daily energy from readings (BRT date grouping) ────────────────────────
    readings = sb_select(
        "inverter_readings",
        filters={"inverter_id": inversor_id},
        order="ts.desc",
        limit=days * 160,  # 144 readings/day + buffer
    ) or []

    daily_energy: Dict[str, float] = {}
    for r in readings:
        ts_str = r.get("ts") or ""
        e = r.get("energy_today_kwh")
        if not ts_str or e is None:
            continue
        try:
            d = _dt.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(BRT).date()
            if d < start_date or d > today_brt:
                continue
            ds = d.isoformat()
            daily_energy[ds] = max(daily_energy.get(ds, 0.0), float(e))
        except Exception:
            pass

    # ── Irradiance — NASA POWER batch (single HTTP request) ──────────────────
    irr_map: Dict[str, float] = {}
    start_compact = start_date.strftime("%Y%m%d")
    end_compact   = today_brt.strftime("%Y%m%d")

    try:
        r = httpx.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={
                "parameters": "ALLSKY_SFC_SW_DWN",
                "community":  "RE",
                "longitude":  lon,
                "latitude":   lat,
                "start":      start_compact,
                "end":        end_compact,
                "format":     "JSON",
            },
            timeout=20.0,
        )
        raw = (
            r.json()
            .get("properties", {})
            .get("parameter", {})
            .get("ALLSKY_SFC_SW_DWN", {})
        )
        for compact, val in raw.items():
            if val is not None and float(val) >= 0:  # -999 = sentinel "no data"
                iso = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
                irr_map[iso] = float(val)
    except Exception:
        pass

    # ── Open-Meteo fallback for recent dates NASA hasn't processed (~6d lag) ─
    missing = [
        (start_date + timedelta(days=i)).isoformat()
        for i in range(days)
        if (start_date + timedelta(days=i)).isoformat() not in irr_map
    ]
    if missing:
        try:
            r2 = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":       lat,
                    "longitude":      lon,
                    "daily":          "shortwave_radiation_sum",
                    "past_days":      min(days + 7, 92),
                    "forecast_days":  1,
                    "timezone":       "auto",
                },
                timeout=12.0,
            )
            om = r2.json().get("daily", {})
            for t, v in zip(om.get("time", []), om.get("shortwave_radiation_sum", [])):
                if t in missing and v is not None and float(v) >= 0:
                    irr_map[t] = float(v) / 3.6  # MJ/m² → kWh/m²
        except Exception:
            pass

    # ── Build daily series ────────────────────────────────────────────────────
    result_days = []
    for i in range(days):
        d = (start_date + timedelta(days=i)).isoformat()
        e_real   = daily_energy.get(d)
        irr      = irr_map.get(d)
        e_prev   = round(irr * kWp * efficiency, 2) if irr else None
        pr       = (
            round(e_real / e_prev, 3)
            if (e_real is not None and e_prev and e_real >= 0.5 and e_prev > 0)
            else None
        )
        perda    = (
            round(max(0.0, (e_prev or 0) - (e_real or 0)) * tariff, 2)
            if e_prev is not None
            else None
        )
        result_days.append({
            "date":            d,
            "e_real_kwh":      round(e_real, 2) if e_real is not None else None,
            "irr_kwh_m2":      round(irr, 3)   if irr   is not None else None,
            "e_prevista_kwh":  e_prev,
            "pr":              pr,
            "perda_rs":        perda,
        })

    days_with_pr   = [d for d in result_days if d["pr"] is not None]
    avg_pr         = round(sum(d["pr"] for d in days_with_pr) / len(days_with_pr), 3) if days_with_pr else None
    total_perda    = round(sum(d["perda_rs"] or 0 for d in result_days), 2)
    best_pr        = max((d["pr"] for d in days_with_pr), default=None)
    worst_pr       = min((d["pr"] for d in days_with_pr), default=None)

    return {
        "available":    True,
        "inversor_id":  inversor_id,
        "kWp":          kWp,
        "efficiency":   efficiency,
        "tariff_kwh":   tariff,
        "period_days":  days,
        "days":         result_days,
        "summary": {
            "avg_pr":          avg_pr,
            "best_pr":         round(best_pr, 3) if best_pr else None,
            "worst_pr":        round(worst_pr, 3) if worst_pr else None,
            "days_with_pr":    len(days_with_pr),
            "total_perda_rs":  total_perda,
        },
    }


@router.get("/{inversor_id}/alerts")
async def get_alerts(
    inversor_id: str,
    status: str = Query("open", description="open | resolved | all"),
    limit: int = Query(50, le=200),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Alertas do inversor ordenados por data de abertura desc."""
    filters: Dict[str, Any] = {"inverter_id": inversor_id}
    if status != "all":
        filters["status"] = status
    rows = sb_select("inverter_alerts", filters=filters, order="opened_at.desc", limit=limit) or []
    open_count = sum(1 for r in rows if r.get("status") == "open")
    critical_count = sum(1 for r in rows if r.get("status") == "open" and r.get("severity") == "critical")
    return {
        "inversor_id": inversor_id,
        "alerts": rows,
        "open_count": open_count,
        "critical_count": critical_count,
    }


@router.patch("/{inversor_id}/alerts/{alert_id}/resolve")
async def resolve_alert(
    inversor_id: str,
    alert_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Fecha manualmente um alerta aberto."""
    rows = sb_select("inverter_alerts", filters={"id": alert_id, "inverter_id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Alerta não encontrado")
    sb_update("inverter_alerts", {"id": alert_id},
              {"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "alert_id": alert_id}


@router.patch("/{inversor_id}/alerts/{alert_id}/mute")
async def mute_alert(
    inversor_id: str,
    alert_id: str,
    hours: int = Query(24, description="Silenciar por quantas horas"),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Silencia um alerta por N horas."""
    from datetime import timedelta
    rows = sb_select("inverter_alerts", filters={"id": alert_id, "inverter_id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Alerta não encontrado")
    muted_until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    sb_update("inverter_alerts", {"id": alert_id},
              {"status": "muted", "muted_until": muted_until})
    return {"ok": True, "alert_id": alert_id, "muted_until": muted_until}


@router.post("/{inversor_id}/backfill")
async def trigger_backfill(
    inversor_id: str,
    months: int = Query(6, ge=1, le=6, description="Meses retroativos (1–6)"),
    phase: str = Query("both", description="Fases a executar: 1 | 2 | both"),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Dispara backfill histórico em background.
    Phase 1 (daily, fast)  : 6 chamadas de API para 6 meses de dados diários.
    Phase 2 (intraday, slow): até 180 chamadas para curva intraday completa.
    Retorna imediatamente; acompanhe o progresso via GET /backfill-status.
    """
    if phase not in ("1", "2", "both"):
        raise HTTPException(400, "phase deve ser '1', '2' ou 'both'")

    running = _backfill_tasks.get(inversor_id, {})
    if running.get("status") == "running":
        return {"status": "already_running", **running}

    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Inversor não encontrado")

    inv  = rows[0]
    slug = inv.get("platform_slug", "")
    if slug not in ("shinemonitor", "solarman"):
        raise HTTPException(400, f"Backfill ainda não suportado para '{slug}'.")

    creds = _dec(inv.get("credentials_enc", ""))
    if not creds.get("usr"):
        raise HTTPException(400, "Credenciais não encontradas.")

    _backfill_tasks[inversor_id] = {
        "status":     "running",
        "phase":      phase,
        "months":     months,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "days_done":  0,
        "days_total": 0,
        "phase1":     None,
        "phase2":     None,
    }

    def _run():
        from backend.integrations.backfill import run_backfill
        try:
            if slug == "shinemonitor":
                from backend.integrations.shinemonitor import authenticate
                auth = authenticate(creds["usr"], creds["pwd"])
            else:
                from backend.integrations.solarman import authenticate
                auth = authenticate(
                    creds["usr"], creds["pwd"],
                    app_id=creds.get("app_id"), app_secret=creds.get("app_secret"),
                )

            def _progress(_phase: str, done: int, total: int):
                _backfill_tasks[inversor_id]["days_done"]  = done
                _backfill_tasks[inversor_id]["days_total"] = total

            result = run_backfill(inv, auth, months=months, phase=phase, progress_cb=_progress)

            finished = datetime.now(timezone.utc).isoformat()
            _backfill_tasks[inversor_id].update({
                "status":      "done",
                "finished_at": finished,
                **result,
            })

            # Persist summary into plant_meta so it survives restarts
            fresh = (sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or [{}])[0]
            meta  = fresh.get("plant_meta") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            meta.setdefault("backfill", {})
            meta["backfill"].update({
                "done":        True,
                "months":      months,
                "finished_at": finished,
                "phase1":      result.get("phase1"),
                "phase2":      result.get("phase2"),
            })
            sb_update("client_inverters", {"id": inversor_id}, {"plant_meta": meta})

        except Exception as exc:
            _backfill_tasks[inversor_id].update({
                "status":      "error",
                "error":       str(exc)[:300],
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })

    import threading
    threading.Thread(target=_run, daemon=True).start()

    return {
        "status":      "started",
        "inversor_id": inversor_id,
        "months":      months,
        "phase":       phase,
    }


@router.get("/{inversor_id}/backfill-status")
async def get_backfill_status(
    inversor_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Progresso do backfill em andamento, ou último resultado persistido."""
    task = _backfill_tasks.get(inversor_id)
    if task:
        return task

    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if rows:
        meta = rows[0].get("plant_meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if meta.get("backfill"):
            return {"status": "done", **meta["backfill"]}

    return {"status": "not_started"}


@router.get("/{inversor_id}")
async def get_inversor(
    inversor_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Detalhe de um inversor: metadados + última leitura + séries agregadas."""
    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Inversor não encontrado")
    inv = _fmt_inversor(rows[0])

    # Latest 500 readings for charts (ordered asc for charts, desc for latest)
    readings_raw = sb_select(
        "inverter_readings",
        filters={"inverter_id": inversor_id},
        order="ts.desc",
        limit=500,
    ) or []
    readings = [_fmt_reading(r) for r in readings_raw]
    latest = readings[0] if readings else None

    # Monthly aggregated series (max energy per month)
    monthly: Dict[str, Dict] = {}
    for r in readings:
        ts = r["ts"][:7] if r["ts"] else ""
        if not ts:
            continue
        if ts not in monthly:
            monthly[ts] = {"month": ts, "energy_kwh": 0.0, "max_power_w": 0.0, "count": 0}
        monthly[ts]["energy_kwh"] = max(monthly[ts]["energy_kwh"], r.get("energy_today_kwh") or 0)
        monthly[ts]["max_power_w"] = max(monthly[ts]["max_power_w"], r.get("active_power_w") or 0)
        monthly[ts]["count"] += 1

    serie_mensal = sorted(monthly.values(), key=lambda x: x["month"])

    return {
        "inversor":      inv,
        "latest":        latest,
        "serie_mensal":  serie_mensal,
        "total_readings": len(readings),
    }


@router.post("/validate")
async def validate_inversor(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Valida credenciais antes de salvar. Retorna info da planta descoberta."""
    platform = body.get("platform_slug", "")
    creds = {k: v for k, v in body.items() if k != "platform_slug"}

    try:
        if platform == "shinemonitor":
            from backend.integrations.shinemonitor import discover_and_validate
            result = discover_and_validate(
                usr=creds["usr"], pwd=creds["pwd"], pn=creds.get("pn", "")
            )
            plant = result["plant"]
            devices = result["devices"]
            device = next(
                (d for d in devices if str(d.get("sn", "")) == str(creds.get("sn", ""))),
                devices[0] if devices else {}
            )
            return {
                "ok": True,
                "platform": "shinemonitor",
                "plant_id":   str(plant.get("pid") or ""),
                "plant_name": plant.get("pname") or "",
                "plant_meta": {
                    "address": plant.get("addr", ""),
                    "city": plant.get("city", ""),
                    "installed_capacity_kwp": float(plant.get("installed_power", 0) or 0),
                },
                "devices": devices,
                "device":  device,
                "devaddr": str(device.get("devaddr", "1")),
            }

        elif platform == "growatt":
            from backend.integrations.growatt import discover_and_validate
            result = discover_and_validate(
                usr=creds["usr"], pwd=creds["pwd"],
                plant_id=creds.get("plant_id"),
            )
            return {"ok": True, "platform": "growatt",
                    "plants": result["plants"], "devices": result["devices"]}

        elif platform == "solarman":
            from backend.integrations.solarman import discover_and_validate
            result = discover_and_validate(
                usr=creds["usr"], pwd=creds["pwd"],
                app_id=creds.get("app_id") or None,
                app_secret=creds.get("app_secret") or None,
                device_sn=creds.get("sn"),
            )
            stations = result["stations"]
            devices = result["devices"]
            target = result.get("target_station") or (stations[0] if stations else {})
            return {
                "ok": True,
                "platform":  "solarman",
                "plant_id":  str(target.get("id") or target.get("stationId") or ""),
                "plant_name": target.get("name") or target.get("stationName") or "",
                "stations":  stations,
                "devices":   devices,
            }

        raise HTTPException(400, f"Plataforma '{platform}' não suportada")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Falha na validação: {str(e)}")


@router.post("")
async def create_inversor(
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
    client_id: Optional[str] = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Cria inversor. mode=api salva credenciais; mode=manual só metadados."""
    platform_slug = body.get("platform_slug", "")
    mode = body.get("mode", "api")

    if mode == "api" and platform_slug not in PLATFORMS:
        raise HTTPException(400, f"Plataforma '{platform_slug}' não reconhecida")

    cred_keys = {"usr", "pwd", "pn", "sn", "devcode", "devaddr",
                 "plant_id", "logger_sn", "app_id", "app_secret"}
    creds_raw = {k: v for k, v in body.items() if k in cred_keys}

    caps = body.get("capabilities") or (
        PLATFORMS.get(platform_slug, {}).get("capabilities_default", {}) if mode == "api" else {}
    )
    meta = body.get("plant_meta") or {}

    payload: Dict[str, Any] = {
        "client_id":        client_id,
        "platform_slug":    platform_slug,
        "alias":            body.get("alias") or "Meu Inversor",
        "plant_name":       body.get("plant_name") or "",
        "mode":             mode,
        "nominal_power_kw": float(body.get("nominal_power_kw") or 0),
        "install_date":     body.get("install_date") or None,
        "location":         body.get("location") or "",
        "plant_id":         body.get("plant_id") or "",
        "pn":               creds_raw.get("pn") or "",
        "sn":               creds_raw.get("sn") or "",
        "devcode":          creds_raw.get("devcode") or "",
        "devaddr":          creds_raw.get("devaddr") or "1",
        "credentials_enc":  _enc(creds_raw) if mode == "api" else "",
        "capabilities":     json.dumps(caps),
        "plant_meta":       meta,
        "status":           "pending",
    }

    row = sb_insert("client_inverters", payload)
    if not row:
        raise HTTPException(500, "Falha ao salvar inversor")

    return {"ok": True, "inversor": _fmt_inversor(row)}


@router.patch("/{inversor_id}")
async def update_inversor(
    inversor_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    allowed = {"alias", "plant_name", "nominal_power_kw", "install_date", "location",
               "status", "capabilities", "plant_id", "pn", "sn", "devcode", "devaddr", "plant_meta"}
    data = {k: v for k, v in body.items() if k in allowed}
    if "capabilities" in data and isinstance(data["capabilities"], dict):
        data["capabilities"] = json.dumps(data["capabilities"])
    if "nominal_power_kw" in data:
        data["nominal_power_kw"] = float(data["nominal_power_kw"] or 0)

    # Credential patch: merge with existing
    cred_keys = {"usr", "pwd", "pn", "sn", "devcode", "devaddr",
                 "plant_id", "logger_sn", "app_id", "app_secret"}
    new_creds = {k: v for k, v in body.items() if k in cred_keys}
    if new_creds:
        rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
        existing = _dec(rows[0].get("credentials_enc", "")) if rows else {}
        existing.update(new_creds)
        data["credentials_enc"] = _enc(existing)
        data["status"] = "pending"  # re-validate on next sync
        _token_cache.pop(inversor_id, None)

    sb_update("client_inverters", {"id": inversor_id}, data)
    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    return {"ok": True, "inversor": _fmt_inversor(rows[0]) if rows else {}}


@router.delete("/{inversor_id}")
async def delete_inversor(
    inversor_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    sb_delete("client_inverters", {"id": inversor_id})
    _token_cache.pop(inversor_id, None)
    return {"ok": True}


@router.post("/{inversor_id}/sync")
async def sync_inversor(
    inversor_id: str,
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Puxa leitura em tempo real, persiste e retorna."""
    rows = sb_select("client_inverters", filters={"id": inversor_id}, limit=1) or []
    if not rows:
        raise HTTPException(404, "Inversor não encontrado")

    inv = rows[0]
    if inv.get("mode") == "manual":
        raise HTTPException(400, "Inversor em modo manual não suporta sync automático")

    try:
        reading = _do_sync(inv)
    except Exception as e:
        sb_update("client_inverters", {"id": inversor_id}, {"status": "error"})
        raise HTTPException(502, f"Erro ao sincronizar: {str(e)}")

    saved = _save_reading(inversor_id, reading)
    return {"ok": True, "reading": saved}


@router.post("/{inversor_id}/sync-history")
async def sync_history(
    _inversor_id: str,
    _months_back: int = Query(3, le=12),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Backfill histórico — DESABILITADO temporariamente.

    Investigação identificou que queryDeviceDataOneDay (datetype=month) retorna
    dados de nível de PLANTA (todos os dispositivos somados), não por inversor
    individual. Os valores de energy_total_kwh e active_power_w são inconsistentes
    com os dados do sync em tempo real. Reabilitar após identificar o endpoint
    correto para histórico per-dispositivo na API ShineMonitor.
    """
    raise HTTPException(
        503,
        detail=(
            "Backfill histórico desabilitado: a API ShineMonitor (queryDeviceDataOneDay) "
            "retorna agregados de planta, não por inversor. "
            "Dados acumulados via sync em tempo real (a cada 10min) são confiáveis. "
            "Reabilitar quando identificado endpoint per-dispositivo."
        ),
    )


@router.post("/{inversor_id}/readings")
async def add_manual_reading(
    inversor_id: str,
    body: Dict[str, Any] = Body(...),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Adiciona leitura manual (modo manual ou override pontual)."""
    ts = body.get("ts") or datetime.now(timezone.utc).isoformat()
    record: Dict[str, Any] = {
        "inverter_id":       inversor_id,
        "ts":                ts,
        "active_power_w":    body.get("active_power_w"),
        "energy_today_kwh":  body.get("energy_today_kwh"),
        "energy_total_kwh":  body.get("energy_total_kwh"),
        "energy_year_kwh":   body.get("energy_year_kwh"),
        "grid_frequency_hz": body.get("grid_frequency_hz"),
        "temp_inverter_c":   body.get("temp_inverter_c"),
        "dc_voltage_1_v":    body.get("dc_voltage_1_v"),
        "dc_voltage_2_v":    body.get("dc_voltage_2_v"),
        "dc_current_1_a":    body.get("dc_current_1_a"),
        "dc_current_2_a":    body.get("dc_current_2_a"),
        "ac_voltage_a_v":    body.get("ac_voltage_a_v"),
        "battery_soc_pct":   body.get("battery_soc_pct"),
        "status":            body.get("status", "normal"),
        "raw_data":          json.dumps({"source": "manual", "input": body}),
    }
    saved = sb_insert("inverter_readings", {k: v for k, v in record.items() if v is not None})
    return {"ok": True, "reading": _fmt_reading(saved) if saved else {}}


@router.get("/{inversor_id}/readings")
async def get_readings(
    inversor_id: str,
    limit: int = Query(288, le=5000),
    order: str = Query("asc"),
    days: int = Query(1, description="Quantos dias de histórico retornar"),
    _user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Histórico de leituras com série diária agregada."""
    readings_raw = sb_select(
        "inverter_readings",
        filters={"inverter_id": inversor_id},
        order=f"ts.{order}",
        limit=min(limit, days * 300),
    ) or []
    readings = [_fmt_reading(r) for r in readings_raw]

    # Daily energy series (max reading per day = total energy generated that day)
    daily: Dict[str, float] = {}
    for r in readings:
        day = r["ts"][:10] if r["ts"] else ""
        if day and r.get("energy_today_kwh") is not None:
            if day not in daily or r["energy_today_kwh"] > daily[day]:
                daily[day] = r["energy_today_kwh"]

    serie_diaria = [{"day": d, "energy_kwh": v} for d, v in sorted(daily.items())]

    return {
        "readings":     readings,
        "serie_diaria": serie_diaria,
        "total":        len(readings),
    }
