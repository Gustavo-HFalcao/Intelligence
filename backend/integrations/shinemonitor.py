"""
ShineMonitor / Eybond platform adapter.

Auth: SHA-1 sign over HMAC chain (validated 2026-05-04 with real inverter data).
Covers: elgin.shinemonitor.com, renovigi.shinemonitor.com, solarmust.shinemonitor.com,
        sofar.shinemonitor.com, pi.shinemonitor.com — all share the same company_key.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

import httpx

COMPANY_KEY = "bnrl_frRFjEz8Mkn"
BASE_URL = "http://api.shinemonitor.com/public/"
TIMEOUT = httpx.Timeout(20.0, connect=8.0)


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()


def _salt() -> str:
    return str(int(time.time() * 1000))


def _sign_auth(salt: str, pwd_sha1: str, usr: str) -> str:
    action_str = f"&action=auth&usr={usr}&company-key={COMPANY_KEY}"
    return _sha1(salt + pwd_sha1 + action_str)


def _sign_data(salt: str, secret: str, token: str, action_str: str) -> str:
    return _sha1(salt + secret + token + action_str)


def _get(params: dict) -> dict:
    r = httpx.get(BASE_URL, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("dat") and data.get("err") and data["err"] != "0":
        raise ValueError(f"ShineMonitor API error: {data.get('err')} — {data.get('msg', '')}")
    return data


def authenticate(usr: str, pwd: str) -> Dict[str, Any]:
    """Returns {token, secret, expire_ts}. Raises on failure."""
    salt = _salt()
    pwd_sha1 = _sha1(pwd)
    sign = _sign_auth(salt, pwd_sha1, usr)
    data = _get({
        "sign": sign,
        "salt": salt,
        "action": "auth",
        "usr": usr,
        "company-key": COMPANY_KEY,
    })
    dat = data["dat"]
    return {
        "token": dat["token"],
        "secret": dat["secret"],
        "expire_ts": int(time.time()) + int(dat.get("expire", 432000)),
    }


def _signed_params(token: str, secret: str, action: str, extra: dict = None) -> dict:
    salt = _salt()
    extra = extra or {}
    # Order MUST match the URL param order — ShineMonitor sign is order-sensitive
    extra_str = "".join(f"&{k}={v}" for k, v in extra.items())
    action_str = f"&action={action}{extra_str}"
    sign = _sign_data(salt, secret, token, action_str)
    params = {"sign": sign, "salt": salt, "token": token, "action": action}
    params.update(extra)
    return params


def get_plant_info(token: str, secret: str, plant_id: str) -> Dict[str, Any]:
    """
    Full plant metadata via queryPlantInfo.
    Returns normalized dict with address, coords, tariff, install date, nominal power.
    """
    params = _signed_params(token, secret, "queryPlantInfo", {"plantid": str(plant_id)})
    try:
        data = _get(params)
    except Exception:
        return {}
    dat = data.get("dat") or {}
    if not dat:
        return {}

    addr = dat.get("address") or {}
    profit = dat.get("profit") or {}

    raw_lat = addr.get("lat")
    raw_lon = addr.get("lon")

    # ShineMonitor uses Beijing (116°E, 39°N) as default placeholder — detect and reject
    def _coord_is_china(lat, lon) -> bool:
        try:
            la, lo = float(lat), float(lon)
            return (18 < la < 55) and (70 < lo < 140)
        except (TypeError, ValueError):
            return True

    lat = float(raw_lat) if raw_lat and not _coord_is_china(raw_lat, raw_lon) else None
    lon = float(raw_lon) if raw_lon and not _coord_is_china(raw_lat, raw_lon) else None

    return {
        "plant_id":              dat.get("pid"),
        "name":                  dat.get("name", ""),
        "country":               addr.get("country", ""),
        "province":              addr.get("province", ""),
        "city":                  addr.get("city", ""),
        "address":               addr.get("address", ""),
        "lat":                   lat,
        "lon":                   lon,
        "coords_valid":          lat is not None,
        "timezone_offset_s":     addr.get("timezone", -10800),
        "nominal_power_kw":      float(dat.get("nominalPower") or 0) or None,
        "tariff_kwh":            float(profit.get("unitProfit") or 0) or None,
        "currency":              profit.get("currency", "R$"),
        "energy_year_estimate":  float(dat.get("energyYearEstimate") or 0) or None,
        "install_date":          (dat.get("install") or "")[:10] or None,
        "design_company":        dat.get("designCompany", ""),
    }


def get_plants(token: str, secret: str) -> List[Dict]:
    """List all plants for the authenticated user."""
    params = _signed_params(token, secret, "queryPlantsInfo")
    data = _get(params)
    plants = data.get("dat", {})
    if isinstance(plants, list):
        return plants
    if isinstance(plants, dict):
        return plants.get("info", []) or plants.get("plant", []) or []
    return []


def get_devices(token: str, secret: str, plant_id: str, pn: str) -> List[Dict]:
    """List devices (inverters) for a plant."""
    extra = {"plantid": plant_id, "pn": pn}
    params = _signed_params(token, secret, "queryDevices", extra)
    data = _get(params)
    dat = data.get("dat", {})
    if isinstance(dat, list):
        return dat
    if isinstance(dat, dict):
        return dat.get("device", []) or []
    return []


def get_latest_reading(
    token: str, secret: str, pn: str, sn: str, devcode: str, devaddr: str = "1"
) -> Dict[str, Any]:
    """Fetch real-time data for a device. Returns normalised dict + raw_data."""
    extra = {"pn": pn, "devcode": devcode, "sn": sn, "devaddr": devaddr}
    params = _signed_params(token, secret, "queryDeviceLastData", extra)
    data = _get(params)
    dat = data.get("dat", [])

    raw: Dict[str, Any] = {}
    for item in (dat if isinstance(dat, list) else []):
        key = item.get("title", "").lower().strip()
        val = item.get("val")
        raw[key] = val

    def _f(k: str) -> Optional[float]:
        v = raw.get(k)
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

    return {
        "active_power_w":    _first("active power", "pac", "output power"),
        "energy_today_kwh":  _first("today energy", "eday", "daily energy"),
        "energy_total_kwh":  _first("total energy", "etotal", "total generating capacity"),
        "energy_year_kwh":   _first("current year generating capacity", "eyear"),
        "grid_frequency_hz": _first("grid frequency", "fac"),
        "temp_inverter_c":   _first("inverter temperature", "tempdc", "temperature"),
        "dc_voltage_1_v":    _first("dc voltage 1", "vpv1"),
        "dc_voltage_2_v":    _first("dc voltage 2", "vpv2"),
        "dc_voltage_3_v":    _first("dc voltage 3", "vpv3"),
        "dc_voltage_4_v":    _first("dc voltage 4", "vpv4"),
        "dc_current_1_a":    _first("dc current 1", "ipv1"),
        "dc_current_2_a":    _first("dc current 2", "ipv2"),
        "dc_current_3_a":    _first("dc current 3", "ipv3"),
        "dc_current_4_a":    _first("dc current 4", "ipv4"),
        "ac_voltage_a_v":    _first("ab voltage/a phase voltage", "ab voltage", "uac1", "r-phase voltage"),
        "ac_voltage_b_v":    _first("bc voltage/b phase voltage", "bc voltage", "uac2", "s-phase voltage"),
        "ac_voltage_c_v":    _first("ca voltage/c phase voltage", "ca voltage", "uac3", "t-phase voltage"),
        "ac_current_a_a":    _first("a phase current", "iac1"),
        "ac_current_b_a":    _first("b phase current", "iac2"),
        "ac_current_c_a":    _first("c phase current", "iac3"),
        "battery_soc_pct":   _first("battery soc", "soc"),
        "battery_power_w":   _first("battery power", "pbat"),
        "battery_voltage_v": _first("battery voltage", "vbat"),
        "status":            "normal",
        "raw_data":          {"items": dat, "mapped": raw},
    }


def get_energy_history(
    token: str, secret: str, pn: str, sn: str, devcode: str,
    devaddr: str = "1", date_str: str = None
) -> List[Dict]:
    """
    Daily energy totals for a month.
    date_str: 'YYYY-MM' (defaults to current month).
    Returns list of {date: 'YYYY-MM-DD', val: kWh, unit: 'kWh'}.
    """
    if date_str is None:
        import datetime
        date_str = datetime.date.today().strftime("%Y-%m")

    extra = {
        "pn": pn, "devcode": devcode, "sn": sn, "devaddr": devaddr,
        "date": date_str, "datetype": "month",
    }
    params = _signed_params(token, secret, "queryDeviceDataOneDay", extra)
    try:
        data = _get(params)
        return data.get("dat", []) or []
    except Exception:
        return []


def get_monthly_history(
    token: str, secret: str, pn: str, sn: str, devcode: str,
    devaddr: str = "1", months_back: int = 3
) -> List[Dict]:
    """
    Pull historical readings for the past N months.
    ShineMonitor returns a title/row table — we parse and normalize each row
    into a full reading dict (same shape as get_latest_reading but without raw_data).
    Returns list of normalized reading dicts with 'ts' field.
    """
    import datetime
    results = []
    today = datetime.date.today()

    for i in range(months_back):
        month = (today.replace(day=1) - datetime.timedelta(days=i * 28)).replace(day=1)
        date_str = month.strftime("%Y-%m")
        raw = get_energy_history(token, secret, pn, sn, devcode, devaddr, date_str)

        # raw is the dat field: {"title": [...], "row": [...]}
        if not isinstance(raw, dict):
            continue
        titles = [t.get("title", "").lower().strip() for t in raw.get("title", [])]
        rows = raw.get("row", [])

        def _col(fields: list, *names) -> Optional[float]:
            for name in names:
                try:
                    idx = titles.index(name)
                    v = fields[idx]
                    return float(str(v).replace(",", ".")) if v not in (None, "", "null") else None
                except (ValueError, IndexError):
                    pass
            return None

        for row in rows:
            fields = row.get("field", [])
            if not fields:
                continue
            # Timestamp is always index 1
            ts_str = fields[1] if len(fields) > 1 else ""
            if not ts_str or ts_str == "null":
                continue
            # Convert "YYYY-MM-DD HH:MM:SS" → ISO UTC (ShineMonitor uses local time BR -3)
            try:
                dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                # Treat as UTC-3 (Brasília) → add 3h for UTC
                dt_utc = dt + datetime.timedelta(hours=3)
                ts_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            except ValueError:
                continue

            reading = {
                "ts":               ts_iso,
                "active_power_w":   _col(fields, "active power"),
                "energy_today_kwh": _col(fields, "today energy"),
                "energy_total_kwh": _col(fields, "total energy"),
                "energy_year_kwh":  _col(fields, "current year generating capacity"),
                "temp_inverter_c":  _col(fields, "inverter temperature"),
                "grid_frequency_hz": _col(fields, "grid frequency"),
                "dc_voltage_1_v":   _col(fields, "dc voltage 1"),
                "dc_voltage_2_v":   _col(fields, "dc voltage 2"),
                "dc_voltage_3_v":   _col(fields, "dc voltage 3"),
                "dc_voltage_4_v":   _col(fields, "dc voltage 4"),
                "dc_current_1_a":   _col(fields, "dc current 1"),
                "dc_current_2_a":   _col(fields, "dc current 2"),
                "dc_current_3_a":   _col(fields, "dc current 3"),
                "dc_current_4_a":   _col(fields, "dc current 4"),
                "ac_voltage_a_v":   _col(fields, "ab voltage/a phase voltage"),
                "ac_voltage_b_v":   _col(fields, "bc voltage/b phase voltage"),
                "ac_voltage_c_v":   _col(fields, "ca voltage/c phase voltage"),
                "ac_current_a_a":   _col(fields, "a phase current"),
                "ac_current_b_a":   _col(fields, "b phase current"),
                "ac_current_c_a":   _col(fields, "c phase current"),
                "status":           "normal",
            }
            results.append(reading)

    return results


def discover_and_validate(usr: str, pwd: str, pn: str) -> Dict[str, Any]:
    """
    Full discovery flow:
    1. Authenticate
    2. Find plant containing the datalogger PN
    3. List devices for that plant
    Returns the device info + auth tokens.
    """
    auth = authenticate(usr, pwd)
    token, secret = auth["token"], auth["secret"]

    plants = get_plants(token, secret)
    target_plant = None
    target_devices = []

    for plant in plants:
        pid = str(plant.get("pid") or plant.get("plant_id") or "")
        devices = get_devices(token, secret, pid, pn)
        if devices:
            target_plant = plant
            target_devices = devices
            break

    if not target_plant:
        raise ValueError(f"Datalogger PN '{pn}' não encontrado em nenhuma planta desta conta.")

    return {
        "auth": auth,
        "plant": target_plant,
        "devices": target_devices,
    }
