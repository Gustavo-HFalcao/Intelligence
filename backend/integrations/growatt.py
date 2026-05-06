"""
Growatt ShineServer adapter — server.growatt.com
Auth: SHA-256 password hash, session cookie.
Ref: https://github.com/indykoning/PyPi_GrowattServer (community reverse-engineered)
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

import httpx

BASE_URL = "https://server.growatt.com"
TIMEOUT = httpx.Timeout(20.0, connect=8.0)
DEMO_USER = "demo"
DEMO_PASS = "123456"


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _hash_password(pwd: str) -> str:
    """Growatt uses a specific SHA-256 hash scheme."""
    h = _sha256(pwd)
    # Growatt mixes char positions
    result = []
    for i, c in enumerate(h):
        result.append("c" if c == "0" else c)
    return "".join(result)


def authenticate(usr: str, pwd: str) -> Dict[str, Any]:
    """Login and return session cookies + user info."""
    pwd_hash = _hash_password(pwd)
    client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
    resp = client.post(
        f"{BASE_URL}/login",
        data={"account": usr, "password": pwd_hash, "validateCode": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("result") != 1:
        raise ValueError(f"Growatt login failed: {body.get('msg', 'unknown error')}")

    cookies = dict(resp.cookies)
    return {
        "cookies": cookies,
        "user_id": str(body.get("userId", "")),
        "expire_ts": int(time.time()) + 3600,
    }


def get_plants(cookies: dict) -> List[Dict]:
    """List all plants for the user."""
    client = httpx.Client(timeout=TIMEOUT, cookies=cookies)
    resp = client.post(f"{BASE_URL}/index/getPlantListTitle", data={"currPage": 1})
    resp.raise_for_status()
    data = resp.json()
    plants = data.get("data", {})
    if isinstance(plants, list):
        return plants
    return plants.get("plant", []) if isinstance(plants, dict) else []


def get_plant_detail(cookies: dict, plant_id: str) -> Dict:
    """Get plant summary data."""
    client = httpx.Client(timeout=TIMEOUT, cookies=cookies)
    resp = client.get(f"{BASE_URL}/panel/getPlantData/{plant_id}")
    resp.raise_for_status()
    return resp.json().get("data", {})


def get_inverters(cookies: dict, plant_id: str) -> List[Dict]:
    """List inverters for a plant."""
    client = httpx.Client(timeout=TIMEOUT, cookies=cookies)
    resp = client.post(
        f"{BASE_URL}/device/getMAXList",
        data={"plantId": plant_id, "currPage": 1},
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("data", []) or []


def get_latest_reading(cookies: dict, inverter_sn: str) -> Dict[str, Any]:
    """Fetch real-time data for an inverter by serial number."""
    client = httpx.Client(timeout=TIMEOUT, cookies=cookies)
    resp = client.get(f"{BASE_URL}/device/getMAXInfo/{inverter_sn}")
    resp.raise_for_status()
    raw = resp.json().get("data", {})

    def _f(k: str) -> Optional[float]:
        v = raw.get(k)
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return None

    pac = _f("pac") or _f("activePower")
    return {
        "active_power_w":    (pac * 1000) if pac and pac < 100 else pac,
        "energy_today_kwh":  _f("eDay") or _f("todayEnergy"),
        "energy_total_kwh":  _f("eTotal") or _f("totalEnergy"),
        "energy_year_kwh":   _f("eYear") or _f("yearEnergy"),
        "grid_frequency_hz": _f("fac") or _f("gridFrequency"),
        "temp_inverter_c":   _f("tempdc") or _f("temperature"),
        "dc_voltage_1_v":    _f("vpv1"),
        "dc_voltage_2_v":    _f("vpv2"),
        "dc_current_1_a":    _f("ipv1"),
        "dc_current_2_a":    _f("ipv2"),
        "ac_voltage_a_v":    _f("vac1") or _f("vacr"),
        "ac_voltage_b_v":    _f("vac2") or _f("vacs"),
        "ac_voltage_c_v":    _f("vac3") or _f("vact"),
        "ac_current_a_a":    _f("iac1"),
        "ac_current_b_a":    _f("iac2"),
        "ac_current_c_a":    _f("iac3"),
        "battery_soc_pct":   None,
        "battery_power_w":   None,
        "battery_voltage_v": None,
        "status":            "normal" if raw.get("status") in ("1", 1, "normal") else "offline",
        "raw_data":          raw,
    }


def get_energy_history(cookies: dict, plant_id: str, date_str: str = None) -> List[Dict]:
    """Daily energy for a plant. date_str: YYYY-MM."""
    if date_str is None:
        import datetime
        date_str = datetime.date.today().strftime("%Y-%m")

    year, month = date_str[:7].split("-")
    client = httpx.Client(timeout=TIMEOUT, cookies=cookies)
    resp = client.post(
        f"{BASE_URL}/energy/energyMonthGraphic",
        data={"plantId": plant_id, "year": year, "month": month},
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("energy", []) or []


def discover_and_validate(usr: str, pwd: str, plant_id: str = None) -> Dict[str, Any]:
    """Authenticate and discover plants + inverters."""
    auth = authenticate(usr, pwd)
    cookies = auth["cookies"]
    plants = get_plants(cookies)

    if plant_id:
        target = next((p for p in plants if str(p.get("id") or p.get("plantId") or "") == str(plant_id)), None)
        if not target:
            raise ValueError(f"Plant ID '{plant_id}' não encontrado nesta conta.")
        target_plants = [target]
    else:
        target_plants = plants

    devices = []
    for p in target_plants[:3]:
        pid = str(p.get("id") or p.get("plantId") or "")
        if pid:
            inv = get_inverters(cookies, pid)
            devices.extend(inv)

    return {"auth": auth, "plants": target_plants, "devices": devices}
