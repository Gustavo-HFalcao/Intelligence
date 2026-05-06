"""
Solarman / IGEN / Deye platform adapter.

API Base: https://globalapi.solarmanpv.com
Auth: appId + SHA-256(password) + appSecret → Bearer token.
Covers: Deye (~17% BR market) + 190 other brands via Solarman dataloggers.

Credentials required per client:
  usr, pwd, app_id, app_secret
  (request app_id/secret at service@solarmanpv.com)
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

import httpx

BASE_URL = "https://globalapi.solarmanpv.com"
TIMEOUT = httpx.Timeout(25.0, connect=10.0)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def authenticate(usr: str, pwd: str, app_id: str = None, app_secret: str = None) -> Dict[str, Any]:
    """
    Authenticate via Solarman Global API.
    Requires app_id + app_secret from the client's Solarman business account.
    Request access at: service@solarmanpv.com
    """
    if not app_id or not app_secret:
        raise ValueError(
            "SolarmanPV requer app_id e app_secret do cliente. "
            "Aguardando credenciais via service@solarmanpv.com"
        )

    pwd_hash = _sha256(pwd)
    payload = {
        "appSecret": app_secret,
        "email": usr,
        "password": pwd_hash,
    }
    resp = httpx.post(
        f"{BASE_URL}/account/v1.0/token?appId={app_id}&language=pt",
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()

    # returnCode 0 = success; anything else is an error
    if body.get("returnCode", -1) != 0:
        code = body.get("returnCode") or body.get("code")
        msg = body.get("msg") or body.get("message") or str(body)
        raise ValueError(f"Solarman auth falhou [{code}]: {msg}")

    return {
        "token": body["access_token"],
        "user_id": str(body.get("uid", "")),
        "expire_ts": int(time.time()) + int(body.get("expires_in", 7200)),
    }


def get_stations(token: str) -> List[Dict]:
    """List all stations (plants) for the authenticated account."""
    resp = httpx.post(
        f"{BASE_URL}/station/v1.0/list?language=pt",
        json={"page": 1, "size": 100},
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("stationList", []) or []


def get_station_detail(token: str, station_id: str) -> Dict:
    """Get detailed info (address, lat, lng, capacity) for a station."""
    resp = httpx.post(
        f"{BASE_URL}/station/v1.0/detail?language=pt",
        json={"stationId": station_id},
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json() or {}


def get_devices(token: str, station_id: str) -> List[Dict]:
    """List inverters and loggers for a station. Returns only INVERTER type."""
    resp = httpx.post(
        f"{BASE_URL}/station/v1.0/device?language=pt",
        json={"stationId": station_id},
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    # API may return deviceListItems or deviceList depending on version
    devices = body.get("deviceListItems") or body.get("deviceList") or []
    return [d for d in devices if str(d.get("deviceType", "")).upper() == "INVERTER"]


def get_latest_reading(token: str, device_sn: str) -> Dict[str, Any]:
    """Real-time data for a device by serial number."""
    resp = httpx.post(
        f"{BASE_URL}/device/v1.0/currentData?language=pt",
        json={"deviceSn": device_sn},
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    raw = resp.json()

    data_list = raw.get("dataList", [])
    mapped: Dict[str, Any] = {}
    for item in data_list:
        key = (item.get("key") or "").strip()
        mapped[key] = item.get("value")

    def _f(k: str) -> Optional[float]:
        v = mapped.get(k)
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _first(*keys) -> Optional[float]:
        for k in keys:
            v = _f(k)
            if v is not None:
                return v
        return None

    # Solarman returns power in W (activePower) or kW (generationPower) depending on model
    raw_power = _first("activePower", "pac", "generationPower", "outputPower")
    # activePower comes in kW from some models — convert if < 500 and energy today > 1 kWh
    energy_today = _first("dailyEnergy", "eToday", "todayEnergy", "Daily Generation", "Generation today")
    total_energy = _first("totalEnergy", "eTotal", "Total Generation", "Cumulative Generation")

    # Heuristic: if activePower looks like kW (< 200) and we have plausible energy, convert to W
    active_power_w = raw_power
    if active_power_w is not None and active_power_w < 500 and (energy_today or 0) > 0.1:
        active_power_w = active_power_w * 1000

    device_state = raw.get("deviceState")
    status = "normal" if device_state == 1 else ("offline" if device_state == 0 else "fault")

    return {
        "active_power_w":    active_power_w,
        "energy_today_kwh":  energy_today,
        "energy_total_kwh":  total_energy,
        "energy_year_kwh":   _first("monthEnergy", "yearEnergy", "Year Generation"),
        "grid_frequency_hz": _first("gridFrequency", "frequency", "fac"),
        "temp_inverter_c":   _first("dcTemperature", "temperature", "tempdc", "Inverter Temperature"),
        "dc_voltage_1_v":    _first("pv1Voltage", "vpv1"),
        "dc_voltage_2_v":    _first("pv2Voltage", "vpv2"),
        "dc_voltage_3_v":    _first("pv3Voltage", "vpv3"),
        "dc_voltage_4_v":    _first("pv4Voltage", "vpv4"),
        "dc_current_1_a":    _first("pv1Current", "ipv1"),
        "dc_current_2_a":    _first("pv2Current", "ipv2"),
        "dc_current_3_a":    _first("pv3Current", "ipv3"),
        "dc_current_4_a":    _first("pv4Current", "ipv4"),
        "ac_voltage_a_v":    _first("gridVoltage", "uac1", "phase1Voltage", "R-phase Voltage"),
        "ac_voltage_b_v":    _first("uac2", "phase2Voltage", "S-phase Voltage"),
        "ac_voltage_c_v":    _first("uac3", "phase3Voltage", "T-phase Voltage"),
        "ac_current_a_a":    _first("iac1", "phase1Current", "R-phase Current"),
        "ac_current_b_a":    _first("iac2", "phase2Current", "S-phase Current"),
        "ac_current_c_a":    _first("iac3", "phase3Current", "T-phase Current"),
        "battery_soc_pct":   _first("batterySoc", "soc"),
        "battery_power_w":   _first("batteryPower"),
        "battery_voltage_v": _first("batteryVoltage"),
        "status":            status,
        "raw_data":          {"dataList": data_list, "mapped": mapped, "deviceState": device_state},
    }


def get_historical_readings(
    token: str,
    device_sn: str,
    start_ts: int,
    end_ts: int,
    time_type: int = 2,
) -> List[Dict]:
    """
    Historical readings for a device.
    time_type: 1=5min, 2=hour, 3=day
    Returns list of {time, dataList} records.
    """
    try:
        resp = httpx.post(
            f"{BASE_URL}/device/v1.0/historical?language=pt",
            json={
                "deviceSn": device_sn,
                "startTime": start_ts,
                "endTime": end_ts,
                "timeType": time_type,
            },
            headers=_headers(token),
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("dataList", []) or []
    except Exception:
        return []


def get_station_energy_history(
    token: str,
    station_id: str,
    year: int,
    month: int,
) -> List[Dict]:
    """Monthly energy breakdown (daily values) for a station."""
    try:
        resp = httpx.post(
            f"{BASE_URL}/station/v1.0/energy/month?language=pt",
            json={"stationId": station_id, "year": year, "month": month},
            headers=_headers(token),
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("energies", []) or []
    except Exception:
        return []


def discover_and_validate(
    usr: str,
    pwd: str,
    app_id: str = None,
    app_secret: str = None,
    device_sn: str = None,
) -> Dict[str, Any]:
    """
    Authenticate, discover all stations and their devices.
    If device_sn provided, filters to that specific device.
    """
    auth = authenticate(usr, pwd, app_id, app_secret)
    token = auth["token"]
    stations = get_stations(token)

    all_devices = []
    target_station = None

    for st in stations:
        sid = str(st.get("id") or st.get("stationId") or "")
        devs = get_devices(token, sid)
        if device_sn:
            match = [d for d in devs if str(d.get("deviceSn", "")) == device_sn]
            if match:
                target_station = st
                all_devices = devs
                break
        else:
            all_devices.extend(devs)
            if not target_station and devs:
                target_station = st

    return {
        "auth": auth,
        "stations": stations,
        "devices": all_devices,
        "target_station": target_station,
    }
